"""
OrdinalMK — Sindicación (audiencia prestada).

Si no tienes audiencia propia, la pides prestada: republicas cada artículo en
plataformas con tráfico (Medium, LinkedIn, dev.to, Hashnode, Quora) SIEMPRE con
`canonical` apuntando al original, para ganar alcance sin canibalizar tu SEO.

  - Formatea el post por plataforma (largo/tono/tags/frontmatter).
  - Publica por API si hay token (Medium/dev.to); si no, encola a archivo.
  - El canonical al original es OBLIGATORIO (se añade en código).

Cola: reports/syndication_queue/<project>.jsonl. Builders puros y testeables.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

QUEUE_DIR = REPO_ROOT / "reports" / "syndication_queue"
PLATFORMS = ['medium', 'linkedin', 'devto', 'hashnode', 'quora']


def _canonical(article: dict, config: dict) -> str:
    domain = (config.get('domain') or '').replace('https://', '').replace('http://', '').strip('/')
    lang = article.get('language', 'es')
    slug = article.get('slug', '')
    if article.get('canonical'):
        return article['canonical']
    return f"https://{domain}/{lang}/{slug}/" if domain and slug else (f"https://{domain}/" if domain else '')


def _excerpt(body: str, n: int = 280) -> str:
    import re
    plain = re.sub(r'[#*`>]', '', body or '').strip()
    plain = re.sub(r'\s+', ' ', plain)
    return plain[:n] + ('…' if len(plain) > n else '')


def build(article: dict, config: dict, platform: str) -> dict:
    """Formatea el artículo para una plataforma. Canonical SIEMPRE presente."""
    title = article.get('title', '')
    body = article.get('body') or article.get('content') or ''
    canonical = _canonical(article, config)
    tags = [str(k) for k in (article.get('keywords') or [])][:4]
    brand = config.get('name', '')
    footer = f"\n\n---\n*Publicado originalmente en [{brand}]({canonical}).*"

    if platform == 'linkedin':
        # LinkedIn: gancho corto + CTA al original (no soporta canonical real)
        out_body = f"{_excerpt(body, 600)}\n\nSigue leyendo: {canonical}"
    elif platform == 'quora':
        # Quora: formato respuesta, enlaza como fuente
        out_body = f"{_excerpt(body, 900)}\n\nMás detalle aquí: {canonical}"
    elif platform == 'devto':
        # dev.to: frontmatter con canonical_url y tags
        fm = (f"---\ntitle: {title}\npublished: false\ntags: {', '.join(tags)}\n"
              f"canonical_url: {canonical}\n---\n\n")
        out_body = fm + body + footer
    else:  # medium / hashnode: markdown completo + nota de canonical
        out_body = body + footer

    return {'platform': platform, 'title': title, 'body': out_body,
            'canonical_url': canonical, 'tags': tags,
            'language': article.get('language', 'es')}


def _enqueue(project_id, items, reason, queue_dir):
    queue_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with open(queue_dir / f"{project_id}.jsonl", 'a', encoding='utf-8') as f:
        for it in items:
            f.write(json.dumps({**it, 'ts': ts, 'status': 'queued', 'reason': reason},
                               ensure_ascii=False) + "\n")
    return len(items)


def _post_devto(item: dict) -> bool:
    key = os.environ.get('DEVTO_API_KEY')
    if not key:
        return False
    try:
        import requests
        r = requests.post("https://dev.to/api/articles",
                          headers={'api-key': key, 'Content-Type': 'application/json'},
                          json={'article': {'title': item['title'], 'body_markdown': item['body'],
                                            'published': False, 'canonical_url': item['canonical_url'],
                                            'tags': item['tags']}}, timeout=20)
        return r.status_code in (200, 201)
    except Exception:
        return False


def _post_medium(item: dict) -> bool:
    token = os.environ.get('MEDIUM_TOKEN')
    if not token:
        return False
    try:
        import requests
        me = requests.get("https://api.medium.com/v1/me",
                          headers={'Authorization': f'Bearer {token}'}, timeout=15).json()
        uid = me.get('data', {}).get('id')
        if not uid:
            return False
        r = requests.post(f"https://api.medium.com/v1/users/{uid}/posts",
                          headers={'Authorization': f'Bearer {token}'},
                          json={'title': item['title'], 'contentFormat': 'markdown',
                                'content': item['body'], 'canonicalUrl': item['canonical_url'],
                                'tags': item['tags'], 'publishStatus': 'draft'}, timeout=20)
        return r.status_code in (200, 201)
    except Exception:
        return False


def syndicate(project_id: str, article: dict, config: dict,
              platforms: list = None, queue_dir: Path = QUEUE_DIR) -> dict:
    """Publica el artículo en las plataformas. Lo que no tenga API, se encola."""
    platforms = platforms or PLATFORMS
    published, queued = [], []
    for p in platforms:
        item = build(article, config, p)
        ok = _post_devto(item) if p == 'devto' else (_post_medium(item) if p == 'medium' else False)
        if ok:
            published.append(p)
        else:
            _enqueue(project_id, [item], f'sin API {p}', queue_dir)
            queued.append(p)
    return {'project': project_id, 'article': article.get('slug', ''),
            'published': published, 'queued': queued}


if __name__ == "__main__":
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp(prefix='synd_'))
    try:
        cfg = {'name': 'TuIAlista', 'domain': 'tuialista.com'}
        art = {'title': 'Automatiza tu facturación con IA local', 'slug': 'facturacion-ia',
               'language': 'es', 'keywords': ['facturación', 'ia', 'cfdi'],
               'body': '# Facturación con IA\n\nProcesa tus CFDI en tu equipo, sin nube.\n'}

        # 1) canonical SIEMPRE presente y correcto
        m = build(art, cfg, 'medium')
        print('canonical:', m['canonical_url'])
        assert m['canonical_url'] == 'https://tuialista.com/es/facturacion-ia/'
        assert 'Publicado originalmente' in m['body']

        # 2) dev.to lleva frontmatter con canonical_url y tags
        d = build(art, cfg, 'devto')
        assert 'canonical_url: https://tuialista.com/es/facturacion-ia/' in d['body']
        assert 'tags:' in d['body'] and d['tags'] == ['facturación', 'ia', 'cfdi']

        # 3) linkedin/quora enlazan al original
        li = build(art, cfg, 'linkedin')
        assert 'tuialista.com/es/facturacion-ia' in li['body']

        # 4) sin APIs -> todo a cola, no rompe
        os.environ.pop('DEVTO_API_KEY', None); os.environ.pop('MEDIUM_TOKEN', None)
        res = syndicate('demo', art, cfg, queue_dir=tmp)
        print('publicadas:', res['published'], '| en cola:', res['queued'])
        assert res['published'] == [] and set(res['queued']) == set(PLATFORMS)
        q = (tmp / 'demo.jsonl').read_text(encoding='utf-8').strip().splitlines()
        assert len(q) == len(PLATFORMS)
        # cada línea en cola tiene canonical
        assert all('canonical_url' in json.loads(l) for l in q)
        print('OK: syndication (canonical obligatorio + formato por plataforma + fallback a cola)')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
