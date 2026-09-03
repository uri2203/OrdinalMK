"""
OrdinalMK — Landing Page Generator (multi-proyecto)
Genera landing pages de alta conversión, con SEO completo y SIN datos
específicos de marca hardcodeados: todo (marca, dominio, tema, moneda, copy,
features, testimonios, precio, schema) proviene de la config del proyecto.
Un proyecto nuevo = un bloque en projects.yaml, cero cambios de código.
"""

import json
import re
import hashlib
from pathlib import Path

PUBLISHED_DIR = Path(__file__).parent.parent.parent / "published"

# Copy base por idioma — neutral de marca; el proyecto puede sobrescribir
# cualquiera vía config['copy'] = {...}.
BASE_COPY = {
    'es': {'features': 'Por qué elegirnos', 'testimonials': 'Lo que dicen nuestros clientes',
           'guarantee': 'Garantía de 30 días', 'guarantee_full': 'Si no te convence, te devolvemos tu dinero',
           'final': 'Empieza hoy', 'access': 'Acceso completo', 'cta': 'Empezar ahora'},
    'en': {'features': 'Why choose us', 'testimonials': 'What our customers say',
           'guarantee': '30-day guarantee', 'guarantee_full': "If you're not satisfied, we'll refund you",
           'final': 'Start today', 'access': 'Full access', 'cta': 'Start now'},
    'pt': {'features': 'Por que nos escolher', 'testimonials': 'O que dizem nossos clientes',
           'guarantee': 'Garantia de 30 dias', 'guarantee_full': 'Se não gostar, devolvemos seu dinheiro',
           'final': 'Comece hoje', 'access': 'Acesso completo', 'cta': 'Começar agora'},
    'fr': {'features': 'Pourquoi nous choisir', 'testimonials': 'Ce que disent nos clients',
           'guarantee': 'Garantie de 30 jours', 'guarantee_full': "Si vous n'êtes pas satisfait, nous vous remboursons",
           'final': "Commencez aujourd'hui", 'access': 'Accès complet', 'cta': 'Commencer'},
    'de': {'features': 'Warum wir', 'testimonials': 'Das sagen unsere Kunden',
           'guarantee': '30 Tage Garantie', 'guarantee_full': 'Wenn es dir nicht gefällt, erstatten wir dein Geld',
           'final': 'Starte heute', 'access': 'Voller Zugang', 'cta': 'Jetzt starten'},
    'it': {'features': 'Perché sceglierci', 'testimonials': 'Cosa dicono i nostri clienti',
           'guarantee': 'Garanzia di 30 giorni', 'guarantee_full': 'Se non sei soddisfatto, ti rimborsiamo',
           'final': 'Inizia oggi', 'access': 'Accesso completo', 'cta': 'Inizia ora'},
}
OG_LOCALE = {'es': 'es_ES', 'en': 'en_US', 'pt': 'pt_BR', 'fr': 'fr_FR', 'de': 'de_DE', 'it': 'it_IT'}


class LandingPageGenerator:
    """Genera landing pages para campañas (dirigido por config, multi-proyecto)."""

    def __init__(self, project_id: str):
        self.project_id = project_id

    def create_landing_page(self, config: dict) -> dict:
        """Crea una landing page completa."""
        slug = config.get('slug') or self._slugify(config['title'])
        html = self._generate_html(config)

        output_dir = PUBLISHED_DIR / self.project_id / "landing" / config.get('language', 'es')
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / f"{slug}.html"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)

        return {'status': 'created', 'slug': slug, 'path': str(filepath), 'title': config['title']}

    def _generate_html(self, config: dict) -> str:
        lang = config.get('language', 'es')
        cp = dict(BASE_COPY.get(lang, BASE_COPY['es']))
        cp.update(config.get('copy', {}))   # el proyecto puede sobrescribir cualquier copy

        # ── Identidad / SEO desde config (multi-proyecto, sin marca hardcodeada) ──
        brand = config.get('brand') or self.project_id.title()
        hero = config.get('headline') or config.get('title') or brand
        subtitle = config.get('subtitle') or config.get('concept') or ''
        cta = config.get('cta') or cp['cta']
        final_cta = config.get('final_cta') or cp['final']
        raw_title = config.get('seo_title') or config.get('title') or hero
        # No repetir la marca si ya aparece en el título (evita "X … — X")
        page_title = raw_title if brand.lower() in raw_title.lower() else f"{raw_title} — {brand}"
        page_title = page_title.strip()[:65]
        meta_desc = (config.get('meta_description') or subtitle or brand).strip()[:160]
        base_url = (config.get('base_url') or f"https://{config.get('domain', self.project_id + '.com')}").rstrip('/')
        canonical = config.get('canonical_url') or f"{base_url}/{config.get('path', '').lstrip('/')}"
        og_image = config.get('og_image') or f"{base_url}/og-image.png"
        currency = config.get('currency', 'USD')
        locale = OG_LOCALE.get(lang, 'es_ES')
        price_numeric = str(config.get('price_numeric', '0'))
        # hreflang: config['alternates'] = [{'lang':'en','url':'…'}, …]
        alternates = config.get('alternates') or []
        hreflang = "".join(
            f'\n    <link rel="alternate" hreflang="{a["lang"]}" href="{a["url"]}">' for a in alternates)
        if alternates:
            hreflang += f'\n    <link rel="alternate" hreflang="x-default" href="{canonical}">'

        # ── Tema desde config (colores/tipografía por marca) ──
        th = config.get('theme', {})
        c_primary = th.get('primary', '#6366f1'); c_primary_dark = th.get('primary_dark', '#4f46e5')
        c_accent = th.get('accent', '#8b5cf6'); c_bg = th.get('bg', '#0f1117'); c_surface = th.get('surface', '#1a1d27')
        c_text = th.get('text', '#e4e6f0'); c_muted = th.get('muted', '#8b8fa3'); c_line = th.get('line', '#2d3140')
        c_success = th.get('success', '#22c55e'); font = th.get('font', 'Inter')

        # ── Contenido OPCIONAL: si el proyecto no lo aporta, se omite la sección
        #    (nunca se muestran datos de otra marca) ──
        price = config.get('price', '')
        price_name = config.get('price_name', '')
        stripe_link = config.get('stripe_link') or config.get('cta_url') or '#'
        features = config.get('features') or []
        testimonials = config.get('testimonials') or []
        schema_type = config.get('schema_type') or ('Product' if price_numeric not in ('0', '', 'None') else 'WebSite')

        feat_html = ''.join(
            f'<div class="feature"><div class="feature-icon">{f.get("icon","")}</div>'
            f'<h3>{f.get("title","")}</h3><p>{f.get("desc","")}</p></div>' for f in features)
        features_section = (f'<section class="section"><h2 class="section-title">{cp["features"]}</h2>'
                            f'<div class="features">{feat_html}</div></section>') if features else ''
        test_html = ''.join(
            f'<div class="testimonial"><div class="testimonial-stars">{"★" * int(tm.get("rating", 5))}</div>'
            f'<p class="testimonial-text">&ldquo;{tm.get("text","")}&rdquo;</p>'
            f'<p class="testimonial-name">{tm.get("name","")}</p></div>' for tm in testimonials)
        testimonials_section = (f'<section class="section"><h2 class="section-title">{cp["testimonials"]}</h2>'
                                f'<div class="testimonials">{test_html}</div></section>') if testimonials else ''
        pricing_section = (
            f'<section class="section"><div class="pricing"><h3>{price_name}</h3>'
            f'<div class="price">{price}</div>'
            f'<p style="color:var(--muted);margin-bottom:2rem">{cp["access"]}</p>'
            f'<a href="{stripe_link}" class="cta-btn" style="width:100%;display:block">{cta}</a>'
            f'</div></section>') if price else ''

        ld = {"@context": "https://schema.org", "@type": schema_type, "name": brand,
              "description": meta_desc, "url": canonical, "brand": {"@type": "Brand", "name": brand}}
        if schema_type == 'Product':
            ld["offers"] = {"@type": "Offer", "price": price_numeric, "priceCurrency": currency, "url": canonical}
        ld_json = json.dumps(ld, ensure_ascii=False, indent=2)
        font_q = font.replace(' ', '+')

        return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_title}</title>
    <meta name="description" content="{meta_desc}">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="{canonical}">
    <meta property="og:type" content="website">
    <meta property="og:title" content="{page_title}">
    <meta property="og:description" content="{meta_desc}">
    <meta property="og:url" content="{canonical}">
    <meta property="og:image" content="{og_image}">
    <meta property="og:locale" content="{locale}">
    <meta property="og:site_name" content="{brand}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{page_title}">
    <meta name="twitter:description" content="{meta_desc}">
    <meta name="twitter:image" content="{og_image}">{hreflang}
    <link href="https://fonts.googleapis.com/css2?family={font_q}:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{ --primary: {c_primary}; --primary-dark: {c_primary_dark}; --bg: {c_bg}; --surface: {c_surface}; --text: {c_text}; --muted: {c_muted}; --success: {c_success}; --line: {c_line}; --gradient: linear-gradient(135deg, {c_primary}, {c_accent}); }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: '{font}', system-ui, sans-serif; background: var(--bg); color: var(--text); }}
        .hero {{ min-height: 100vh; display: flex; align-items: center; justify-content: center; text-align: center; padding: 2rem; background: radial-gradient(circle at 50% 0%, rgba(99,102,241,0.15), transparent 50%); }}
        .hero h1 {{ font-size: 3.5rem; font-weight: 800; margin-bottom: 1rem; background: var(--gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; max-width: 800px; }}
        .hero p {{ font-size: 1.3rem; color: var(--muted); margin-bottom: 2rem; max-width: 600px; }}
        .cta-btn {{ display: inline-block; background: var(--gradient); color: white; padding: 16px 40px; border-radius: 12px; font-size: 1.1rem; font-weight: 600; text-decoration: none; transition: transform 0.2s, box-shadow 0.2s; }}
        .cta-btn:hover {{ transform: translateY(-2px); box-shadow: 0 8px 30px rgba(99,102,241,0.4); }}
        .section {{ padding: 5rem 2rem; max-width: 1200px; margin: 0 auto; }}
        .section-title {{ font-size: 2rem; font-weight: 700; text-align: center; margin-bottom: 3rem; }}
        .features {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 2rem; }}
        .feature {{ background: var(--surface); border: 1px solid var(--line); border-radius: 16px; padding: 2rem; text-align: center; transition: transform 0.2s; }}
        .feature:hover {{ transform: translateY(-4px); }}
        .feature-icon {{ font-size: 2.5rem; margin-bottom: 1rem; }}
        .feature h3 {{ font-size: 1.1rem; margin-bottom: 0.5rem; }}
        .feature p {{ color: var(--muted); font-size: 0.9rem; }}
        .testimonials {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 2rem; }}
        .testimonial {{ background: var(--surface); border: 1px solid var(--line); border-radius: 16px; padding: 2rem; }}
        .testimonial-text {{ color: var(--muted); line-height: 1.8; margin-bottom: 1rem; font-style: italic; }}
        .testimonial-name {{ font-weight: 600; }}
        .testimonial-stars {{ color: #f59e0b; margin-bottom: 0.5rem; }}
        .pricing {{ text-align: center; background: var(--surface); border: 2px solid var(--primary); border-radius: 24px; padding: 3rem; max-width: 500px; margin: 0 auto; }}
        .price {{ font-size: 3rem; font-weight: 800; margin: 1rem 0; }}
        .guarantee {{ text-align: center; padding: 2rem; color: var(--muted); }}
        .final-cta {{ text-align: center; padding: 5rem 2rem; background: radial-gradient(circle at 50% 100%, rgba(99,102,241,0.15), transparent 50%); }}
        .final-cta h2 {{ font-size: 2rem; margin-bottom: 2rem; }}
        @media (max-width: 768px) {{ .hero h1 {{ font-size: 2rem; }} }}
    </style>
    <script type="application/ld+json">
{ld_json}
    </script>
</head>
<body>
    <section class="hero">
        <div>
            <h1>{hero}</h1>
            <p>{subtitle}</p>
            <a href="{stripe_link}" class="cta-btn">{cta}</a>
        </div>
    </section>
    {features_section}
    {testimonials_section}
    {pricing_section}
    <div class="guarantee"><p>🛡️ {cp['guarantee']} — {cp['guarantee_full']}</p></div>
    <section class="final-cta">
        <h2>{final_cta}</h2>
        <a href="{stripe_link}" class="cta-btn">{cta}</a>
    </section>
</body>
</html>"""

    def _slugify(self, text: str) -> str:
        slug = text.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        hash_suffix = hashlib.md5(text.encode()).hexdigest()[:6]
        return f"{slug}-{hash_suffix}"


if __name__ == "__main__":
    # Ejemplo multi-proyecto: TODO desde config, nada hardcodeado.
    gen = LandingPageGenerator('demo')
    result = gen.create_landing_page({
        'title': 'Demo — página de ejemplo',
        'brand': 'Demo',
        'headline': 'Un título de héroe',
        'subtitle': 'Una descripción única y persuasiva para SEO.',
        'meta_description': 'Descripción única para buscadores (≤160 caracteres).',
        'language': 'es',
        'base_url': 'https://demo.com',
        'path': 'landing/es/ejemplo',
        'currency': 'USD',
        'price': '$19 USD/mo', 'price_numeric': '19', 'price_name': 'Pro',
        'stripe_link': 'https://buy.stripe.com/xxx',
        'theme': {'primary': '#e8821e', 'accent': '#c46a12'},
        'alternates': [{'lang': 'en', 'url': 'https://demo.com/landing/en/example'}],
        'features': [{'icon': '⚡', 'title': 'Rápido', 'desc': 'Descripción de la feature.'}],
    })
    print(f"Landing creada: {result['slug']} -> {result['path']}")
