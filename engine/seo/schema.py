"""
OrdinalMK — Datos estructurados (JSON-LD / schema.org).

Le da a Google (y a las IAs) el significado explícito del contenido para ganar
resultados enriquecidos: estrellas, FAQ desplegables, precios, ficha de negocio.
Barato y de alto impacto en CTR.

Genera JSON-LD para: Organization, WebSite, Article, FAQPage, Product,
LocalBusiness y BreadcrumbList. `for_article` combina los relevantes y devuelve
el <script> listo para incrustar en el <head>.

Funciones puras (sin red), testeables.
"""

import json


def _clean_domain(config: dict) -> str:
    return (config.get('domain') or '').replace('https://', '').replace('http://', '').strip('/')


def organization(config: dict) -> dict:
    domain = _clean_domain(config)
    org = {
        "@type": "Organization",
        "name": config.get('name', ''),
        "url": f"https://{domain}/" if domain else "",
    }
    if config.get('og_image'):
        org["logo"] = config['og_image']
    return org


def website(config: dict) -> dict:
    domain = _clean_domain(config)
    return {
        "@type": "WebSite",
        "name": config.get('name', ''),
        "url": f"https://{domain}/" if domain else "",
    }


def article(art: dict, config: dict) -> dict:
    domain = _clean_domain(config)
    obj = {
        "@type": "Article",
        "headline": art.get('title', '')[:110],
        "inLanguage": art.get('language', config.get('primary_language', 'es')),
        "author": {"@type": "Organization", "name": config.get('name', '')},
        "publisher": organization(config),
    }
    if art.get('description') or art.get('meta_description'):
        obj["description"] = art.get('description') or art.get('meta_description')
    if art.get('published_at'):
        obj["datePublished"] = art['published_at']
    if art.get('slug') and domain:
        lang = art.get('language', 'es')
        obj["mainEntityOfPage"] = f"https://{domain}/{lang}/{art['slug']}/"
    if art.get('keywords'):
        obj["keywords"] = ", ".join(art['keywords'])
    return obj


def faq_page(faq: list) -> dict:
    return {
        "@type": "FAQPage",
        "mainEntity": [{
            "@type": "Question",
            "name": f.get('question', ''),
            "acceptedAnswer": {"@type": "Answer", "text": f.get('answer', '')},
        } for f in (faq or []) if f.get('question') and f.get('answer')],
    }


def product(prod: dict, config: dict) -> dict:
    obj = {
        "@type": "Product",
        "name": prod.get('name', ''),
        "brand": {"@type": "Brand", "name": config.get('name', '')},
    }
    price = prod.get('price')
    if price is not None:
        obj["offers"] = {
            "@type": "Offer",
            "price": str(price),
            "priceCurrency": prod.get('currency', 'USD'),
            "availability": "https://schema.org/InStock",
        }
        if prod.get('stripe_link') and prod['stripe_link'] != '#':
            obj["offers"]["url"] = prod['stripe_link']
    return obj


def local_business(config: dict, location: str = None) -> dict:
    domain = _clean_domain(config)
    aud = config.get('audience', {}) or {}
    obj = {
        "@type": "LocalBusiness",
        "name": config.get('name', ''),
        "url": f"https://{domain}/" if domain else "",
        "areaServed": location or aud.get('location', ''),
    }
    if config.get('og_image'):
        obj["image"] = config['og_image']
    return obj


def breadcrumb(items: list) -> dict:
    """items = [{name, url}, ...] en orden."""
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [{
            "@type": "ListItem", "position": i + 1,
            "name": it.get('name', ''), "item": it.get('url', ''),
        } for i, it in enumerate(items or [])],
    }


def render(obj) -> str:
    """Envuelve uno o varios objetos en un <script> JSON-LD con @context."""
    if isinstance(obj, list):
        payload = [{"@context": "https://schema.org", **o} for o in obj]
    else:
        payload = {"@context": "https://schema.org", **obj}
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    return f'<script type="application/ld+json">\n{body}\n</script>'


def for_article(art: dict, config: dict) -> str:
    """Combina Article + FAQPage (si hay) + Breadcrumb en un solo <script>."""
    blocks = [article(art, config)]
    if art.get('faq'):
        blocks.append(faq_page(art['faq']))
    domain = _clean_domain(config)
    if domain and art.get('slug'):
        lang = art.get('language', 'es')
        blocks.append(breadcrumb([
            {'name': config.get('name', ''), 'url': f"https://{domain}/"},
            {'name': art.get('title', '')[:60], 'url': f"https://{domain}/{lang}/{art['slug']}/"},
        ]))
    return render(blocks)


if __name__ == "__main__":
    cfg = {'name': 'TuIAlista', 'domain': 'tuialista.com', 'primary_language': 'es',
           'og_image': 'https://tuialista.com/logo.png', 'audience': {'location': 'México'}}

    # 1) Organization / WebSite
    org = organization(cfg)
    assert org['@type'] == 'Organization' and org['url'] == 'https://tuialista.com/'
    assert org['logo'].endswith('logo.png')

    # 2) Article + keywords + url
    art = {'title': 'Facturación electrónica CFDI: guía', 'language': 'es',
           'slug': 'facturacion-cfdi', 'description': 'Todo sobre CFDI',
           'keywords': ['cfdi', 'sat'], 'published_at': '2026-09-01',
           'faq': [{'question': '¿Qué es el CFDI?', 'answer': 'El comprobante fiscal digital.'}]}
    a = article(art, cfg)
    assert a['@type'] == 'Article' and a['inLanguage'] == 'es'
    assert a['mainEntityOfPage'] == 'https://tuialista.com/es/facturacion-cfdi/'
    assert a['keywords'] == 'cfdi, sat'

    # 3) FAQPage
    fp = faq_page(art['faq'])
    assert fp['@type'] == 'FAQPage' and fp['mainEntity'][0]['@type'] == 'Question'
    assert fp['mainEntity'][0]['acceptedAnswer']['text'].startswith('El comprobante')

    # 4) Product con oferta
    p = product({'name': 'Pro', 'price': 29, 'currency': 'USD',
                 'stripe_link': 'https://buy.stripe.com/x'}, cfg)
    assert p['offers']['price'] == '29' and p['offers']['priceCurrency'] == 'USD'
    assert p['offers']['url'].startswith('https://buy.stripe')

    # 5) LocalBusiness + Breadcrumb
    lb = local_business(cfg, 'Guadalajara')
    assert lb['@type'] == 'LocalBusiness' and lb['areaServed'] == 'Guadalajara'
    bc = breadcrumb([{'name': 'Inicio', 'url': 'https://x/'}, {'name': 'Blog', 'url': 'https://x/b/'}])
    assert bc['itemListElement'][1]['position'] == 2

    # 6) render válido + for_article combina Article+FAQ+Breadcrumb
    script = for_article(art, cfg)
    assert script.startswith('<script type="application/ld+json">')
    parsed = json.loads(script.split('>', 1)[1].rsplit('<', 1)[0])
    types = [b['@type'] for b in parsed]
    print('bloques for_article:', types)
    assert 'Article' in types and 'FAQPage' in types and 'BreadcrumbList' in types
    assert all(b['@context'] == 'https://schema.org' for b in parsed)
    print('OK: schema (Organization/Article/FAQ/Product/LocalBusiness/Breadcrumb + render + for_article)')
