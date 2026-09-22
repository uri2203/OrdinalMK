"""
OrdinalMK — SEO programático (páginas a escala).

Genera cientos de landings automáticas por combinación GIRO x CIUDAD x IDIOMA,
para capturar búsquedas long-tail muy específicas ("software de facturación cfdi
para despachos en Guadalajara"). Es el multiplicador de tráfico para B2B local.

- Toma los `categories` y `locations` del bloque `prospecting` (o de un bloque
  `programmatic` si se define) + los idiomas activos del proyecto.
- Construye una página por combinación: título, H1, meta description, cuerpo con
  intención local, CTA e hreflang. Idempotente (mismo slug -> mismo archivo).
- Copy con IA si hay credenciales; si no, plantilla por idioma (no rompe).
- Devuelve un manifiesto de las URLs generadas (para sitemap + indexación).

Salida: published/<project>/<lang>/lp/<slug>.html
"""

import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

PUBLISHED_ROOT = REPO_ROOT / "published"
CONTENT_MODEL = os.environ.get("ORDINALMK_CONTENT_MODEL", "claude-opus-4-8")

# Esqueleto de copy por idioma. {cat}=giro, {loc}=ciudad, {brand}, {concept}.
TEMPLATES = {
    'es': {
        'title': "{cat_cap} en {loc}: automatiza con {brand}",
        'h1': "Software para {cat} en {loc}",
        'desc': "{brand} ayuda a {cat} en {loc} a automatizar su operación con IA local. "
                "Tus datos no salen de tu equipo. Prueba gratis.",
        'intro': "¿Eres {cat} en {loc}? {brand} automatiza tus tareas repetitivas "
                 "({concept}) directamente en tu computadora, sin subir datos a la nube.",
        'why': "Por qué {brand} para {cat} en {loc}",
        'cta': "Ver cómo funciona",
        'bullets': ["100% local y privado — tus archivos no salen de tu equipo",
                    "Pensado para el día a día de {cat}",
                    "Empieza hoy, cancela cuando quieras"],
    },
    'en': {
        'title': "{cat_cap} in {loc}: automate with {brand}",
        'h1': "Software for {cat} in {loc}",
        'desc': "{brand} helps {cat} in {loc} automate their work with local AI. "
                "Your data never leaves your device. Free trial.",
        'intro': "Are you a {cat} in {loc}? {brand} automates your repetitive tasks "
                 "({concept}) right on your computer, with no data sent to the cloud.",
        'why': "Why {brand} for {cat} in {loc}",
        'cta': "See how it works",
        'bullets': ["100% local and private — files stay on your device",
                    "Built for the daily work of {cat}",
                    "Start today, cancel anytime"],
    },
    'pt': {
        'title': "{cat_cap} em {loc}: automatize com {brand}",
        'h1': "Software para {cat} em {loc}",
        'desc': "{brand} ajuda {cat} em {loc} a automatizar a operação com IA local. "
                "Seus dados não saem do seu equipamento. Teste grátis.",
        'intro': "Você é {cat} em {loc}? {brand} automatiza suas tarefas repetitivas "
                 "({concept}) no seu computador, sem enviar dados para a nuvem.",
        'why': "Por que {brand} para {cat} em {loc}",
        'cta': "Ver como funciona",
        'bullets': ["100% local e privado — os arquivos ficam no seu equipamento",
                    "Feito para o dia a dia de {cat}",
                    "Comece hoje, cancele quando quiser"],
    },
    'fr': {
        'title': "{cat_cap} à {loc} : automatisez avec {brand}",
        'h1': "Logiciel pour {cat} à {loc}",
        'desc': "{brand} aide les {cat} à {loc} à automatiser leur activité avec une IA locale. "
                "Vos données ne quittent jamais votre appareil. Essai gratuit.",
        'intro': "Vous êtes {cat} à {loc} ? {brand} automatise vos tâches répétitives "
                 "({concept}) sur votre ordinateur, sans envoyer de données dans le cloud.",
        'why': "Pourquoi {brand} pour les {cat} à {loc}",
        'cta': "Voir comment ça marche",
        'bullets': ["100% local et privé — vos fichiers restent sur votre appareil",
                    "Conçu pour le quotidien des {cat}",
                    "Commencez aujourd'hui, annulez quand vous voulez"],
    },
    'de': {
        'title': "{cat_cap} in {loc}: automatisieren mit {brand}",
        'h1': "Software für {cat} in {loc}",
        'desc': "{brand} hilft {cat} in {loc}, ihre Arbeit mit lokaler KI zu automatisieren. "
                "Deine Daten verlassen nie dein Gerät. Kostenlos testen.",
        'intro': "Bist du {cat} in {loc}? {brand} automatisiert deine wiederkehrenden Aufgaben "
                 "({concept}) direkt auf deinem Rechner, ohne Daten in die Cloud zu senden.",
        'why': "Warum {brand} für {cat} in {loc}",
        'cta': "So funktioniert es",
        'bullets': ["100% lokal und privat — Dateien bleiben auf deinem Gerät",
                    "Für den Alltag von {cat} gemacht",
                    "Heute starten, jederzeit kündbar"],
    },
}


def slugify(text: str) -> str:
    text = (text or '').lower().strip()
    repl = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n', 'ü': 'u',
            'ç': 'c', 'à': 'a', 'è': 'e', 'ê': 'e', 'â': 'a', 'ô': 'o', 'ö': 'o', 'ä': 'a', 'ß': 'ss'}
    for a, b in repl.items():
        text = text.replace(a, b)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')


def _lang_conf(config: dict) -> dict:
    """Fuente de combinaciones: bloque `programmatic` o, si no, `prospecting`."""
    prog = (config or {}).get('programmatic') or {}
    prosp = (config or {}).get('prospecting') or {}
    return {
        'categories': prog.get('categories') or prosp.get('categories') or [],
        'locations': prog.get('locations') or prosp.get('locations') or [],
        'max_pages': prog.get('max_pages'),
    }


def combos(categories: list, locations: list) -> list:
    out = []
    for c in categories:
        for l in locations:
            out.append((c, l))
    return out


def _ai_available() -> bool:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_AUTH_TOKEN'))


def build_page(config: dict, category: str, location: str, lang: str) -> dict:
    """Construye el contenido de una página programática (sin escribir a disco)."""
    t = TEMPLATES.get(lang, TEMPLATES['es'])
    brand = config.get('name', 'Nosotros')
    concept = (config.get('concept') or '').lower()
    domain = (config.get('domain') or '').replace('https://', '').replace('http://', '').strip('/')
    cta_link = ((config.get('landing') or {}).get(lang, {}) or {}).get('cta_link') \
        or (f"https://{domain}/" if domain else "#")
    ctx = {'cat': category, 'cat_cap': category.capitalize(), 'loc': location,
           'brand': brand, 'concept': concept or 'tu operación'}

    def fmt(s):
        try:
            return s.format(**ctx)
        except (KeyError, IndexError):
            return s

    slug = slugify(f"{category}-{location}")
    title = fmt(t['title'])
    desc = fmt(t['desc'])
    h1 = fmt(t['h1'])
    intro = fmt(t['intro'])
    if _ai_available():
        try:
            intro = _ai_intro(config, category, location, lang) or intro
        except Exception:
            pass
    bullets = [fmt(b) for b in t['bullets']]
    keywords = [f"{category} {location}".lower(),
                fmt("software para {cat}").lower(), f"{concept} {location}".strip().lower()]
    canonical = f"https://{domain}/{lang}/lp/{slug}/" if domain else f"/{lang}/lp/{slug}/"
    return {
        'slug': slug, 'language': lang, 'title': title, 'description': desc,
        'h1': h1, 'intro': intro, 'why': fmt(t['why']), 'cta_text': t['cta'],
        'cta_link': cta_link, 'bullets': bullets, 'keywords': keywords,
        'canonical': canonical, 'category': category, 'location': location,
    }


def _ai_intro(config, category, location, lang) -> str:
    import anthropic
    client = anthropic.Anthropic()
    brand = config.get('name', '')
    voice = (config.get('governance', {}) or {}).get('brand_voice', 'claro y directo')
    sysp = (f"Escribe en '{lang}' un párrafo introductorio (2-3 frases) para una landing "
            f"local de {brand}, dirigido a '{category}' en '{location}'. Tono {voice}. "
            f"Sin exageraciones, natural, orientado a la intención de búsqueda local. "
            f"Devuelve solo el texto.")
    resp = client.messages.create(model=CONTENT_MODEL, max_tokens=250, system=sysp,
                                  messages=[{"role": "user", "content": f"{category} en {location}"}])
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def render_html(config: dict, page: dict) -> str:
    theme = config.get('theme', {}) or {}
    primary = theme.get('primary', '#6d5efc')
    bg = theme.get('bg', '#ffffff')
    text = theme.get('text', '#0f1922')
    brand = config.get('name', '')
    footer = ((config.get('landing') or {}).get(page['language'], {}) or {}).get(
        'footer_text', f"© {brand}")
    bullets = "".join(f"<li>{b}</li>" for b in page['bullets'])
    return f"""<!doctype html><html lang="{page['language']}"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{page['title']}</title>
<meta name="description" content="{page['description']}">
<link rel="canonical" href="{page['canonical']}">
<meta property="og:title" content="{page['title']}">
<meta property="og:description" content="{page['description']}">
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:{bg};color:{text};
  line-height:1.6;margin:0}}
 .wrap{{max-width:760px;margin:0 auto;padding:3rem 1.4rem}}
 h1{{font-size:2rem;line-height:1.2;margin-bottom:1rem}}
 .lead{{font-size:1.15rem;color:#444;margin-bottom:1.6rem}}
 h2{{font-size:1.3rem;margin:2rem 0 .8rem}}
 ul{{padding-left:1.1rem}} li{{margin-bottom:.5rem}}
 .cta{{display:inline-block;background:{primary};color:#fff;text-decoration:none;
  padding:.9rem 1.6rem;border-radius:10px;font-weight:700;margin-top:1.5rem}}
 footer{{margin-top:3rem;color:#888;font-size:.85rem;border-top:1px solid #eee;padding-top:1rem}}
</style></head><body><div class="wrap">
<h1>{page['h1']}</h1>
<p class="lead">{page['intro']}</p>
<h2>{page['why']}</h2>
<ul>{bullets}</ul>
<a class="cta" href="{page['cta_link']}">{page['cta_text']}</a>
<footer>{footer} · {page['location']}</footer>
</div></body></html>"""


def generate(project_id: str, config: dict, langs: list = None,
             out_root: Path = PUBLISHED_ROOT, max_pages: int = None,
             write: bool = True) -> dict:
    """Genera todas las páginas programáticas de un proyecto. Devuelve manifiesto."""
    lc = _lang_conf(config)
    cats, locs = lc['categories'], lc['locations']
    if not cats or not locs:
        return {'project': project_id, 'generated': 0, 'reason': 'sin categories/locations',
                'pages': []}
    if langs is None:
        langs = config.get('languages', ['es'])
    cap = max_pages if max_pages is not None else lc['max_pages']

    manifest = []
    for lang in langs:
        for cat, loc in combos(cats, locs):
            page = build_page(config, cat, loc, lang)
            if write:
                d = out_root / project_id / lang / "lp"
                d.mkdir(parents=True, exist_ok=True)
                (d / f"{page['slug']}.html").write_text(render_html(config, page), encoding='utf-8')
            manifest.append({'language': lang, 'slug': page['slug'],
                             'url': page['canonical'], 'title': page['title'],
                             'keywords': page['keywords']})
            if cap and len(manifest) >= cap:
                return {'project': project_id, 'generated': len(manifest),
                        'capped': True, 'pages': manifest}
    return {'project': project_id, 'generated': len(manifest), 'pages': manifest}


if __name__ == "__main__":
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp(prefix='prog_'))
    try:
        cfg = {
            'name': 'TuIAlista', 'domain': 'tuialista.com',
            'concept': 'automatizar documentos, Excel y facturas',
            'languages': ['es', 'en'],
            'theme': {'primary': '#e8821e'},
            'landing': {'es': {'cta_link': 'https://tuialista.com/catalogo/'}},
            'prospecting': {'categories': ['despacho contable', 'asesoría fiscal'],
                            'locations': ['Guadalajara', 'Monterrey']},
        }
        # 1) combinaciones = 2 giros x 2 ciudades x 2 idiomas = 8
        out = generate('demo', cfg, out_root=tmp)
        print('generadas:', out['generated'])
        assert out['generated'] == 8, out['generated']

        # 2) slug e idempotencia
        p = build_page(cfg, 'despacho contable', 'Guadalajara', 'es')
        print('slug es:', p['slug'], '| canonical:', p['canonical'])
        assert p['slug'] == 'despacho-contable-guadalajara'
        assert 'Guadalajara' in p['title'] and p['language'] == 'es'
        f = tmp / 'demo' / 'es' / 'lp' / 'despacho-contable-guadalajara.html'
        assert f.exists(), 'debe escribir el HTML'
        html = f.read_text(encoding='utf-8')
        assert 'canonical' in html and 'Guadalajara' in html and 'tuialista.com/catalogo' in html

        # 3) idioma en (plantilla en inglés)
        pe = build_page(cfg, 'asesoría fiscal', 'Monterrey', 'en')
        assert pe['cta_text'] == 'See how it works' and 'Monterrey' in pe['h1']

        # 4) tope (cap) respeta el máximo
        capped = generate('demo2', cfg, out_root=tmp, max_pages=3)
        assert capped['generated'] == 3 and capped.get('capped')

        # 5) sin categories -> no genera, no rompe
        empty = generate('x', {'languages': ['es']}, out_root=tmp)
        assert empty['generated'] == 0 and 'reason' in empty
        print('manifiesto (muestra):', [m['slug'] for m in out['pages'][:3]])
        print('OK: SEO programatico (combinaciones, slug, idempotente, cap, multi-idioma, fallback)')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
