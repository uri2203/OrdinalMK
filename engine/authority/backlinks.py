"""
OrdinalMK — Construcción de backlinks (autoridad).

Los backlinks siguen siendo el factor de autoridad #1. Este módulo reutiliza la
lógica de prospección para LINK BUILDING legal:

  - Sugiere TIPOS de oportunidad por nicho (directorios, blogs para guest post,
    páginas de recursos, alianzas).
  - Redacta el pitch por tipo (guest post / alianza / directorio) SIEMPRE con
    identidad + opt-out (se añade en código, no se delega a la IA).
  - Lleva un embudo propio por proyecto: nuevo -> contactado -> publicado
    (y rechazado), con la DA (autoridad de dominio) del enlace conseguido.

Almacén: reports/backlinks/<project>.json. Funciones con rutas override (test).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

BACKLINKS_DIR = REPO_ROOT / "reports" / "backlinks"
STATUSES = ['nuevo', 'contactado', 'publicado', 'rechazado']

# Plantillas de tipo de oportunidad por nicho (queries para buscar prospectos).
OPP_TEMPLATES = {
    'guest_post': "blog sobre {niche} escribir para nosotros",
    'directory': "directorio de {niche}",
    'resource_page': "{niche} recursos herramientas",
    'partner': "{niche} alianzas partners",
}


def _niche(config: dict) -> str:
    cats = ((config.get('prospecting') or {}).get('categories')
            or (config.get('audience', {}) or {}).get('interests') or [])
    if cats:
        return cats[0]
    return (config.get('concept') or config.get('name') or 'negocio').lower()


def suggest_targets(config: dict) -> list:
    """Oportunidades de enlace por tipo (queries listas para descubrir)."""
    niche = _niche(config)
    out = []
    for kind, tmpl in OPP_TEMPLATES.items():
        out.append({'kind': kind, 'query': tmpl.format(niche=niche)})
    return out


def _footer(config: dict) -> str:
    sender = (config.get('prospecting') or {}).get('sender', {}) or {}
    company = sender.get('company') or config.get('name', '')
    address = sender.get('address') or (config.get('audience', {}) or {}).get('location', '')
    optout = sender.get('unsubscribe', 'Responde BAJA y no vuelvo a escribirte.')
    return f"\n\n—\n{company} · {address}\n{optout}"


def render_pitch(target: dict, config: dict, kind: str = 'guest_post') -> dict:
    """Correo de outreach para conseguir el enlace. Identidad + opt-out siempre."""
    brand = config.get('name', 'Nosotros')
    concept = (config.get('concept') or '').lower()
    site = target.get('name') or 'su sitio'
    domain = (config.get('domain') or '').strip('/')
    url = f"https://{domain}/" if domain else ''
    if kind == 'guest_post':
        subject = f"Artículo original para {site} (sin costo)"
        body = (f"Hola, equipo de {site}:\n\n"
                f"Soy de {brand} ({concept}). Me gustaría aportar a su blog un artículo "
                f"original y útil para su audiencia, sin costo, a cambio de una mención/enlace. "
                f"¿Les interesa que les proponga 3 temas?\n\n{url}")
    elif kind == 'directory':
        subject = f"Alta de {brand} en su directorio"
        body = (f"Hola:\n\nQuisiera incluir a {brand} en su directorio de {_niche(config)}. "
                f"Les comparto los datos y logo. ¿Cómo procedemos?\n\n{url}")
    elif kind == 'resource_page':
        subject = f"Recurso útil para su página de {site}"
        body = (f"Hola:\n\nVi su página de recursos. Creo que {brand} ({concept}) encaja y "
                f"puede ser útil para sus lectores. ¿Consideraría añadirlo?\n\n{url}")
    else:  # partner
        subject = f"Posible alianza {brand} × {site}"
        body = (f"Hola, equipo de {site}:\n\nVeo sinergia entre {site} y {brand}. "
                f"¿Exploramos una colaboración con beneficio mutuo (contenido/enlaces cruzados)?\n\n{url}")
    return {'subject': subject, 'body': body.rstrip() + _footer(config)}


def _path(project_id: str, base: Path) -> Path:
    return base / f"{project_id}.json"


def _key(item: dict) -> str:
    w = (item.get('website') or item.get('url') or item.get('domain') or '').lower()
    w = w.replace('https://', '').replace('http://', '').replace('www.', '').strip('/')
    return w.split('/')[0] if w else (item.get('name', '') or '').lower()


def load(project_id: str, base: Path = BACKLINKS_DIR) -> list:
    f = _path(project_id, base)
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding='utf-8'))
    except Exception:
        return []


def _save(project_id: str, rows: list, base: Path) -> None:
    base.mkdir(parents=True, exist_ok=True)
    _path(project_id, base).write_text(
        json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def add_targets(project_id: str, targets: list, base: Path = BACKLINKS_DIR) -> dict:
    rows = load(project_id, base)
    existing = {_key(r) for r in rows}
    added = 0
    for t in targets:
        k = _key(t)
        if not k or k in existing:
            continue
        existing.add(k)
        row = dict(t)
        row.update({'key': k, 'status': 'nuevo',
                    'added_at': datetime.now(timezone.utc).isoformat()})
        rows.append(row)
        added += 1
    _save(project_id, rows, base)
    return {'project': project_id, 'added': added, 'total': len(rows)}


def update_status(project_id: str, key: str, status: str, da: int = None,
                  link_url: str = None, base: Path = BACKLINKS_DIR) -> bool:
    if status not in STATUSES:
        raise ValueError(f"estado inválido: {status}")
    rows = load(project_id, base)
    hit = False
    for r in rows:
        if r.get('key') == key:
            r['status'] = status
            r['status_at'] = datetime.now(timezone.utc).isoformat()
            if da is not None:
                r['domain_authority'] = da
            if link_url:
                r['link_url'] = link_url
            hit = True
    if hit:
        _save(project_id, rows, base)
    return hit


def summary(project_id: str, base: Path = BACKLINKS_DIR) -> dict:
    rows = load(project_id, base)
    counts = {s: 0 for s in STATUSES}
    live = []
    for r in rows:
        counts[r.get('status', 'nuevo')] = counts.get(r.get('status', 'nuevo'), 0) + 1
        if r.get('status') == 'publicado':
            live.append(r)
    avg_da = round(sum(r.get('domain_authority', 0) for r in live) / len(live), 1) if live else 0
    return {'project': project_id, 'total': len(rows), 'counts': counts,
            'live_backlinks': len(live), 'avg_domain_authority': avg_da}


if __name__ == "__main__":
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp(prefix='bl_'))
    try:
        cfg = {'name': 'TuIAlista', 'domain': 'tuialista.com',
               'concept': 'IA local para automatizar tu negocio',
               'prospecting': {'categories': ['despacho contable'],
                               'sender': {'company': 'TuIAlista', 'address': 'México'}}}

        # 1) sugerencias por tipo
        tg = suggest_targets(cfg)
        kinds = [t['kind'] for t in tg]
        print('tipos:', kinds)
        assert set(kinds) == set(OPP_TEMPLATES.keys())
        assert 'despacho contable' in tg[0]['query']

        # 2) pitch guest post incluye identidad + opt-out SIEMPRE
        pitch = render_pitch({'name': 'ContaBlog'}, cfg, 'guest_post')
        print('asunto:', pitch['subject'])
        assert 'ContaBlog' in pitch['subject']
        assert 'BAJA' in pitch['body'] and 'TuIAlista · México' in pitch['body']
        # otros tipos también con footer
        for k in ('directory', 'resource_page', 'partner'):
            assert 'BAJA' in render_pitch({'name': 'X'}, cfg, k)['body']

        # 3) embudo: add + dedup + estado + DA
        r = add_targets('demo', [
            {'name': 'ContaBlog', 'website': 'https://contablog.mx'},
            {'name': 'Directorio SW', 'website': 'https://dirsw.mx'},
        ], base=tmp)
        assert r['added'] == 2
        assert add_targets('demo', [{'name': 'dup', 'website': 'https://contablog.mx'}],
                           base=tmp)['added'] == 0, 'dedup por dominio'
        assert update_status('demo', 'contablog.mx', 'publicado', da=45,
                             link_url='https://contablog.mx/post', base=tmp)

        s = summary('demo', base=tmp)
        print('resumen:', s['counts'], '| live:', s['live_backlinks'], '| DA prom:', s['avg_domain_authority'])
        assert s['live_backlinks'] == 1 and s['avg_domain_authority'] == 45
        assert s['counts']['publicado'] == 1 and s['counts']['nuevo'] == 1
        print('OK: backlinks (targets por nicho + pitch con opt-out + embudo + DA)')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
