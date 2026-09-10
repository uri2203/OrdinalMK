"""
OrdinalMK — Autoridad temática: enlazado interno + pillar/cluster.

El ranking moderno no lo ganan artículos sueltos, lo gana la ARQUITECTURA:
artículos del mismo tema enlazados entre sí, con una página pilar que concentra
la autoridad. Esta pieza, tras publicar, recorre TODA la biblioteca del proyecto
(por idioma), agrupa por similitud de keywords e inyecta un bloque "Artículos
relacionados" con enlaces internos en cada artículo. Marca el artículo pilar
(el más conectado del cluster).

Idempotente: re-ejecutar reemplaza el bloque anterior, no lo duplica.
Función pura sobre archivos (acepta rutas override) → fácil de testear.
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
PUBLISHED_ROOT = REPO_ROOT / "published"
CONTENT_ROOT = REPO_ROOT / "content"

RELATED_BLOCK_RE = re.compile(
    r'<nav class="related-articles".*?</nav>', re.DOTALL)

RELATED_LABELS = {
    'es': 'Artículos relacionados', 'en': 'Related articles',
    'pt': 'Artigos relacionados', 'fr': 'Articles liés',
    'de': 'Ähnliche Artikel',
}


def _load_published(project_id: str, content_root: Path) -> list:
    """Carga los JSON de artículos PUBLICADOS de un proyecto."""
    arts = []
    d = content_root / project_id
    if not d.exists():
        return arts
    for f in sorted(d.glob('*.json')):
        try:
            a = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        if a.get('status') == 'published' and a.get('slug') and a.get('language'):
            arts.append(a)
    return arts


def _overlap(a: dict, b: dict) -> int:
    ka = {k.lower() for k in (a.get('keywords') or [])}
    kb = {k.lower() for k in (b.get('keywords') or [])}
    return len(ka & kb)


def _article_url(domain: str, lp: str, lang: str, slug: str) -> str:
    return f"https://{domain}/{lp}/{lang}/{slug}"


def build_internal_links(project_id: str, config: dict = None, max_links: int = 4,
                         published_root: Path = PUBLISHED_ROOT,
                         content_root: Path = CONTENT_ROOT) -> dict:
    """Agrupa por tema e inyecta enlaces internos en cada artículo publicado.

    Devuelve resumen: artículos, enlaces inyectados y el pilar por idioma.
    """
    config = config or {}
    domain = (config.get('domain') or f'{project_id}.com').replace(
        'https://', '').replace('http://', '').strip('/')
    lp = (config.get('deploy', {}).get('lp_path', 'lp')).strip('/')

    arts = _load_published(project_id, content_root)
    by_lang = {}
    for a in arts:
        by_lang.setdefault(a['language'], []).append(a)

    injected = 0
    pillars = {}
    for lang, group in by_lang.items():
        if len(group) < 2:
            # nada que enlazar todavía; el pilar (si hay 1) es él mismo
            pillars[lang] = group[0]['slug'] if group else None
            continue

        # Pilar = el artículo más conectado (mayor solapamiento total de keywords)
        totals = {a['slug']: sum(_overlap(a, b) for b in group if b is not a)
                  for a in group}
        pillar = max(group, key=lambda a: totals[a['slug']])['slug']
        pillars[lang] = pillar

        for a in group:
            related = [b for b in group if b['slug'] != a['slug'] and _overlap(a, b) > 0]
            related.sort(key=lambda b: _overlap(a, b), reverse=True)
            related = related[:max_links]
            if not related:
                continue

            label = RELATED_LABELS.get(lang, RELATED_LABELS['es'])
            items = ''.join(
                f'<li><a href="{_article_url(domain, lp, lang, b["slug"])}">{b["title"]}</a></li>'
                for b in related)
            is_pillar = (a['slug'] == pillar)
            nav = (f'<nav class="related-articles"{" data-pillar=\"1\"" if is_pillar else ""} '
                   f'aria-label="{label}"><h2>{label}</h2><ul>{items}</ul></nav>')

            html_path = published_root / project_id / lang / f"{a['slug']}.html"
            if not html_path.exists():
                continue
            html = html_path.read_text(encoding='utf-8')
            html = RELATED_BLOCK_RE.sub('', html)  # idempotencia
            if '</article>' in html:
                html = html.replace('</article>', nav + '</article>', 1)
            elif '</body>' in html:
                html = html.replace('</body>', nav + '</body>', 1)
            else:
                html = html + nav
            html_path.write_text(html, encoding='utf-8')
            injected += 1

    return {'project': project_id, 'articles': len(arts),
            'injected': injected, 'pillars': pillars}


if __name__ == "__main__":
    import tempfile, shutil

    tmp = Path(tempfile.mkdtemp(prefix='topical_test_'))
    try:
        cr = tmp / "content"
        pr = tmp / "published"
        pid = "demo"
        (cr / pid).mkdir(parents=True)
        # 3 artículos: A y B comparten keywords (mismo cluster), C aparte
        arts = [
            {'slug': 'a-facturacion', 'title': 'Automatizar facturación', 'language': 'es',
             'status': 'published', 'keywords': ['facturación', 'ia', 'automatizar']},
            {'slug': 'b-cfdi', 'title': 'IA para CFDI', 'language': 'es',
             'status': 'published', 'keywords': ['facturación', 'cfdi', 'ia']},
            {'slug': 'c-excel', 'title': 'Excel con IA', 'language': 'es',
             'status': 'published', 'keywords': ['excel', 'reportes']},
        ]
        for a in arts:
            (cr / pid / f"{a['slug']}.json").write_text(
                json.dumps(a, ensure_ascii=False), encoding='utf-8')
            d = pr / pid / a['language']
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{a['slug']}.html").write_text(
                f"<html><body><article><h1>{a['title']}</h1></article></body></html>",
                encoding='utf-8')

        cfg = {'domain': 'demo.com', 'deploy': {'lp_path': 'lp'}}
        r1 = build_internal_links(pid, cfg, published_root=pr, content_root=cr)
        print('run1:', r1)

        a_html = (pr / pid / 'es' / 'a-facturacion.html').read_text(encoding='utf-8')
        c_html = (pr / pid / 'es' / 'c-excel.html').read_text(encoding='utf-8')
        assert 'related-articles' in a_html, 'A debería tener bloque de relacionados'
        assert 'b-cfdi' in a_html, 'A debería enlazar a B (comparten keywords)'
        assert 'related-articles' not in c_html, 'C no comparte keywords → sin bloque'
        assert r1['pillars']['es'] in ('a-facturacion', 'b-cfdi')

        # Idempotencia: segunda corrida no duplica
        build_internal_links(pid, cfg, published_root=pr, content_root=cr)
        a_html2 = (pr / pid / 'es' / 'a-facturacion.html').read_text(encoding='utf-8')
        assert a_html2.count('related-articles') == 1, 'no debe duplicar el bloque'

        print('OK: enlazado interno correcto, pilar detectado, idempotente')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
