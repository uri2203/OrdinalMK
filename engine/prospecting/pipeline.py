"""
OrdinalMK — Prospección: pipeline por proyecto.

Orquesta el embudo de prospección:
  descubrir (Places) -> enriquecer (correo) -> guardar como 'nuevo' (cola de
  aprobación).  Luego, tras aprobación humana:  enviar outreach.

Segmentado por proyecto. El envío NUNCA es automático desde 'nuevo': requiere
que un humano apruebe (store.update_status -> 'aprobado').
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine.prospecting import icp as icp_mod
from engine.prospecting import discovery, enrich as enrich_mod, store, outreach


def discover_project(project_id: str, config: dict, prospects: list = None,
                     base: Path = None) -> dict:
    """Descubre + enriquece + guarda prospectos nuevos de un proyecto.
    `prospects` opcional permite inyectar una lista (test / carga manual)."""
    icp = icp_mod.get_icp(config)
    if not icp['enabled']:
        return {'project': project_id, 'skipped': 'prospección desactivada'}

    kwargs = {'base': base} if base else {}

    if prospects is None:
        disc = discovery.discover(icp['categories'], icp['locations'],
                                  max_results=icp['max_discover_per_run'],
                                  language=icp['language'])
        if not disc['available']:
            return {'project': project_id, 'available': False, 'reason': disc.get('reason')}
        prospects = disc['prospects']

    enriched = []
    for p in prospects:
        p = p if p.get('email') else enrich_mod.enrich(p)
        enriched.append(p)

    with_email = [p for p in enriched if p.get('email')]
    res = store.add_prospects(project_id, with_email, **kwargs)
    return {'project': project_id, 'available': True,
            'descubiertos': len(enriched), 'con_correo': len(with_email),
            'nuevos_guardados': res['added'], 'total': res['total']}


def approve_all_new(project_id: str, base: Path = None) -> int:
    """Aprueba todos los prospectos 'nuevo' que tengan correo (uso masivo)."""
    kwargs = {'base': base} if base else {}
    n = 0
    for p in store.by_status(project_id, 'nuevo', **kwargs):
        if p.get('email'):
            store.update_status(project_id, p.get('key') or p['email'], 'aprobado', **kwargs)
            n += 1
    return n


def send_project(project_id: str, config: dict, base: Path = None) -> dict:
    return outreach.send_to_approved(project_id, config, base=base) if base \
        else outreach.send_to_approved(project_id, config)


if __name__ == "__main__":
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp(prefix='pipeline_'))
    try:
        cfg = {
            'name': 'TuIAlista', 'domain': 'tuialista.com', 'primary_language': 'es',
            'concept': 'agentes de IA locales', 'landing': {'es': {'cta_link': 'https://tuialista.com/'}},
            'prospecting': {'enabled': True, 'max_emails_per_day': 5,
                            'categories': ['despacho contable'], 'locations': ['CDMX'],
                            'sender': {'from_name': 'TuIAlista', 'from_email': 'hola@mail.tuialista.com',
                                       'company': 'TuIAlista', 'address': 'México'}},
        }
        base = tmp / 'prospects'
        # Inyecto 2 prospectos (con correo) como si vinieran de Places+enrich
        injected = [
            {'name': 'Despacho A', 'website': 'https://a.mx', 'email': 'contacto@a.mx', 'query': 'despacho contable en CDMX'},
            {'name': 'Despacho B', 'website': 'https://b.mx', 'email': 'info@b.mx', 'query': 'despacho contable en CDMX'},
        ]
        r = discover_project('demo', cfg, prospects=injected, base=base)
        print('discover:', r)
        assert r['nuevos_guardados'] == 2 and r['con_correo'] == 2

        # Puerta humana: sin aprobar, no se envía nada
        out0 = outreach.send_to_approved('demo', cfg, base=base, queue_dir=tmp / 'q')
        assert out0['aprobados'] == 0, 'sin aprobar no hay a quién enviar'

        # Aprobar y enviar
        n = approve_all_new('demo', base=base)
        print('aprobados:', n)
        out = outreach.send_to_approved('demo', cfg, base=base, queue_dir=tmp / 'q')
        print('outreach:', {k: out[k] for k in ('aprobados', 'encolados')})
        assert n == 2 and out['encolados'] == 2
        print('OK: pipeline descubrir->guardar + puerta humana + aprobar->enviar')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
