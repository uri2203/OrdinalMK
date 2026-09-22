"""
OrdinalMK — SEO local (directorios + Google Business Profile).

Visibilidad local sin esperar meses: consistencia NAP (nombre/dirección/teléfono),
alta en directorios y posts periódicos en Google Business Profile.

  - build_nap(): datos NAP consistentes (clave para SEO local; deben ser idénticos
    en todos lados).
  - directory_targets(): directorios a los que dar de alta (globales + por país).
  - gbp_post(): arma un post de Google Business Profile desde un artículo/oferta.
  - submit(): encola altas/posts (la API de GBP requiere OAuth; sin credenciales
    encola a archivo, listo para ejecutar).

Cola: reports/local_queue/<project>.jsonl. Funciones de armado puras y testeables.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

QUEUE_DIR = REPO_ROOT / "reports" / "local_queue"

# Directorios generales + por país (se filtran por el país de la audiencia).
DIRECTORIES = {
    'global': ['Google Business Profile', 'Bing Places', 'Apple Business Connect',
               'Trustpilot', 'Clutch', 'Crunchbase'],
    'MX': ['Sección Amarilla', 'Cylex México', 'Doplim', 'Vulka'],
    'ES': ['Páginas Amarillas', 'QDQ', 'Cylex España'],
    'US': ['Yelp', 'Yellow Pages', 'Angi', 'BBB'],
}


def _country_code(config: dict) -> str:
    loc = ((config.get('audience', {}) or {}).get('location') or '').lower()
    if 'méxico' in loc or 'mexico' in loc or 'latinoam' in loc:
        return 'MX'
    if 'españa' in loc or 'espana' in loc or 'spain' in loc:
        return 'ES'
    if 'usa' in loc or 'estados unidos' in loc or 'united states' in loc:
        return 'US'
    return 'MX'


def build_nap(config: dict) -> dict:
    """NAP consistente. Debe usarse IDÉNTICO en cada directorio."""
    sender = (config.get('prospecting') or {}).get('sender', {}) or {}
    domain = (config.get('domain') or '').strip('/')
    return {
        'name': config.get('name', ''),
        'address': sender.get('address') or (config.get('audience', {}) or {}).get('location', ''),
        'phone': sender.get('phone', config.get('phone', '')),
        'website': f"https://{domain}/" if domain else '',
        'email': sender.get('reply_to') or sender.get('from_email', ''),
        'description': config.get('concept', ''),
    }


def directory_targets(config: dict) -> list:
    cc = _country_code(config)
    return DIRECTORIES['global'] + DIRECTORIES.get(cc, [])


def gbp_post(config: dict, source: dict) -> dict:
    """Arma un post de Google Business Profile desde un artículo u oferta."""
    domain = (config.get('domain') or '').strip('/')
    title = source.get('title') or config.get('tagline', '') or config.get('name', '')
    body = source.get('summary') or source.get('description') \
        or (source.get('body') or '')[:280] or config.get('concept', '')
    cta_link = source.get('cta_link') or ((config.get('landing') or {}).get('es', {}) or {}).get(
        'cta_link') or (f"https://{domain}/" if domain else '')
    return {'type': 'gbp_post', 'summary': title, 'body': body,
            'cta_type': 'LEARN_MORE', 'cta_link': cta_link}


def submit(project_id: str, config: dict, posts: list = None,
           queue_dir: Path = QUEUE_DIR) -> dict:
    """Encola altas en directorios + posts GBP (API GBP requiere OAuth)."""
    queue_dir.mkdir(parents=True, exist_ok=True)
    nap = build_nap(config)
    dirs = directory_targets(config)
    ts = datetime.now(timezone.utc).isoformat()
    items = [{'type': 'directory', 'directory': d, 'nap': nap, 'ts': ts, 'status': 'queued'}
             for d in dirs]
    for p in (posts or []):
        items.append({**gbp_post(config, p), 'ts': ts, 'status': 'queued'})
    with open(queue_dir / f"{project_id}.jsonl", 'a', encoding='utf-8') as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    return {'project': project_id, 'directories': len(dirs),
            'gbp_posts': len(posts or []), 'queued': len(items)}


if __name__ == "__main__":
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp(prefix='local_'))
    try:
        cfg = {'name': 'TuIAlista', 'domain': 'tuialista.com', 'concept': 'IA local para negocios',
               'tagline': 'Tu asistente IA', 'audience': {'location': 'México'},
               'landing': {'es': {'cta_link': 'https://tuialista.com/catalogo/'}},
               'prospecting': {'sender': {'address': 'CDMX, México', 'reply_to': 'hola@tuialista.com'}}}

        # 1) NAP consistente
        nap = build_nap(cfg)
        print('NAP:', nap['name'], '|', nap['address'], '|', nap['website'])
        assert nap['name'] == 'TuIAlista' and nap['website'] == 'https://tuialista.com/'
        assert nap['address'] == 'CDMX, México' and nap['email'] == 'hola@tuialista.com'

        # 2) directorios según país (MX)
        dirs = directory_targets(cfg)
        print('directorios:', dirs)
        assert 'Google Business Profile' in dirs and 'Sección Amarilla' in dirs
        # país distinto -> otro set
        us = directory_targets({'audience': {'location': 'USA'}})
        assert 'Yelp' in us and 'Sección Amarilla' not in us

        # 3) gbp_post desde artículo
        post = gbp_post(cfg, {'title': 'Nuevo agente de facturación',
                              'summary': 'Automatiza tus CFDI en local.'})
        assert post['type'] == 'gbp_post' and post['cta_link'].endswith('/catalogo/')
        assert 'CFDI' in post['body']

        # 4) submit encola directorios + posts
        res = submit('demo', cfg, posts=[{'title': 'Oferta', 'summary': 'Prueba gratis'}], queue_dir=tmp)
        print('encolados:', res['queued'], '(dirs', res['directories'], '+ posts', res['gbp_posts'], ')')
        assert res['queued'] == res['directories'] + 1
        lines = (tmp / 'demo.jsonl').read_text(encoding='utf-8').strip().splitlines()
        types = {json.loads(l)['type'] for l in lines}
        assert 'directory' in types and 'gbp_post' in types
        print('OK: local (NAP + directorios por país + gbp_post + submit a cola)')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
