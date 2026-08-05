"""
OrdinalMK — Landing Page Generator
Creates high-converting landing pages for marketing campaigns.
"""

import json
import re
import hashlib
from datetime import datetime
from pathlib import Path

PUBLISHED_DIR = Path(__file__).parent.parent.parent / "published"


class LandingPageGenerator:
    """Generates landing pages for campaigns."""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
    
    def create_landing_page(self, config: dict) -> dict:
        """Create a complete landing page."""
        slug = self._slugify(config['title'])
        
        html = self._generate_html(config)
        
        # Save
        output_dir = PUBLISHED_DIR / self.project_id / "landing" / config.get('language', 'es')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = output_dir / f"{slug}.html"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return {
            'status': 'created',
            'slug': slug,
            'path': str(filepath),
            'title': config['title']
        }
    
    def _generate_html(self, config: dict) -> str:
        lang = config.get('language', 'es')
        
        headlines = {
            'es': {
                'hero': config.get('headline', 'Transforma tu vida con Yayika'),
                'subtitle': config.get('subtitle', 'La plataforma #1 para mujeres emprendedoras'),
                'cta': config.get('cta', 'Empezar ahora'),
                'features_title': 'Por que elegir Yayika',
                'testimonials_title': 'Lo que dicen nuestras usuarios',
                'guarantee': '30 dias de garantia',
                'final_cta': 'Unete a miles de mujeres que ya transformaron su vida'
            },
            'en': {
                'hero': config.get('headline', 'Transform your life with Yayika'),
                'subtitle': config.get('subtitle', '#1 platform for women entrepreneurs'),
                'cta': config.get('cta', 'Start now'),
                'features_title': 'Why choose Yayika',
                'testimonials_title': 'What our users say',
                'guarantee': '30-day guarantee',
                'final_cta': 'Join thousands of women who already transformed their lives'
            }
        }
        
        t = headlines.get(lang, headlines['es'])
        features = config.get('features', [
            {'icon': ' Cycle Tracking', 'title': 'Track your cycle', 'desc': 'Understand your body and optimize your productivity'},
            {'icon': ' Digital Products', 'title': 'Digital products', 'desc': 'Access exclusive tools for your growth'},
            {'icon': ' Community', 'title': 'Community', 'desc': 'Connect with other women entrepreneurs'},
            {'icon': ' Mentoring', 'title': 'Mentoring', 'desc': 'Guidance from successful women'}
        ])
        
        testimonials = config.get('testimonials', [
            {'name': 'Maria G.', 'text': 'Yayika changed my life. I finally understand my cycle and my productivity doubled.', 'rating': 5},
            {'name': 'Laura P.', 'text': 'The community is amazing. I found support and clients here.', 'rating': 5},
            {'name': 'Ana R.', 'text': 'Best investment I made for my business this year.', 'rating': 5}
        ])
        
        price = config.get('price', '$179 MXN/mes')
        price_name = config.get('price_name', 'Plan Semilla')
        stripe_link = config.get('stripe_link', 'https://buy.stripe.com/00wcN502q0xY2481elgA80f')
        
        return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{config['title']} — Yayika</title>
    <meta name="description" content="{config.get('meta_description', t['subtitle'])}">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{ --primary: #6366f1; --primary-dark: #4f46e5; --bg: #0f1117; --surface: #1a1d27; --text: #e4e6f0; --muted: #8b8fa3; --success: #22c55e; --gradient: linear-gradient(135deg, #6366f1, #8b5cf6); }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); }}
        .hero {{ min-height: 100vh; display: flex; align-items: center; justify-content: center; text-align: center; padding: 2rem; background: radial-gradient(circle at 50% 0%, rgba(99,102,241,0.15), transparent 50%); }}
        .hero h1 {{ font-size: 3.5rem; font-weight: 800; margin-bottom: 1rem; background: var(--gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; max-width: 800px; }}
        .hero p {{ font-size: 1.3rem; color: var(--muted); margin-bottom: 2rem; max-width: 600px; }}
        .cta-btn {{ display: inline-block; background: var(--gradient); color: white; padding: 16px 40px; border-radius: 12px; font-size: 1.1rem; font-weight: 600; text-decoration: none; transition: transform 0.2s, box-shadow 0.2s; }}
        .cta-btn:hover {{ transform: translateY(-2px); box-shadow: 0 8px 30px rgba(99,102,241,0.4); }}
        .section {{ padding: 5rem 2rem; max-width: 1200px; margin: 0 auto; }}
        .section-title {{ font-size: 2rem; font-weight: 700; text-align: center; margin-bottom: 3rem; }}
        .features {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 2rem; }}
        .feature {{ background: var(--surface); border: 1px solid #2d3140; border-radius: 16px; padding: 2rem; text-align: center; transition: transform 0.2s; }}
        .feature:hover {{ transform: translateY(-4px); }}
        .feature-icon {{ font-size: 2.5rem; margin-bottom: 1rem; }}
        .feature h3 {{ font-size: 1.1rem; margin-bottom: 0.5rem; }}
        .feature p {{ color: var(--muted); font-size: 0.9rem; }}
        .testimonials {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 2rem; }}
        .testimonial {{ background: var(--surface); border: 1px solid #2d3140; border-radius: 16px; padding: 2rem; }}
        .testimonial-text {{ color: var(--muted); line-height: 1.8; margin-bottom: 1rem; font-style: italic; }}
        .testimonial-name {{ font-weight: 600; }}
        .testimonial-stars {{ color: #f59e0b; margin-bottom: 0.5rem; }}
        .pricing {{ text-align: center; background: var(--surface); border: 2px solid var(--primary); border-radius: 24px; padding: 3rem; max-width: 500px; margin: 0 auto; }}
        .price {{ font-size: 3rem; font-weight: 800; margin: 1rem 0; }}
        .price-period {{ color: var(--muted); font-size: 1rem; }}
        .guarantee {{ text-align: center; padding: 2rem; color: var(--muted); }}
        .guarantee span {{ color: var(--success); font-weight: 600; }}
        .final-cta {{ text-align: center; padding: 5rem 2rem; background: radial-gradient(circle at 50% 100%, rgba(99,102,241,0.15), transparent 50%); }}
        .final-cta h2 {{ font-size: 2rem; margin-bottom: 2rem; }}
        @media (max-width: 768px) {{ .hero h1 {{ font-size: 2rem; }} }}
    </style>
</head>
<body>
    <section class="hero">
        <div>
            <h1>{t['hero']}</h1>
            <p>{t['subtitle']}</p>
            <a href="{stripe_link}" class="cta-btn">{t['cta']}</a>
        </div>
    </section>
    
    <section class="section">
        <h2 class="section-title">{t['features_title']}</h2>
        <div class="features">
            {''.join(f'<div class="feature"><div class="feature-icon">{f["icon"]}</div><h3>{f["title"]}</h3><p>{f["desc"]}</p></div>' for f in features)}
        </div>
    </section>
    
    <section class="section">
        <h2 class="section-title">{t['testimonials_title']}</h2>
        <div class="testimonials">
            {''.join(f'<div class="testimonial"><div class="testimonial-stars">{"★" * t2["rating"]}</div><p class="testimonial-text">"{t2["text"]}"</p><p class="testimonial-name">{t2["name"]}</p></div>' for t2 in testimonials)}
        </div>
    </section>
    
    <section class="section">
        <div class="pricing">
            <h3>{price_name}</h3>
            <div class="price">{price}</div>
            <p style="color:var(--muted);margin-bottom:2rem">Acceso completo a todo</p>
            <a href="{stripe_link}" class="cta-btn" style="width:100%;display:block">{t['cta']}</a>
        </div>
    </section>
    
    <div class="guarantee">
        <p>🛡️ {t['guarantee']} — Si no te gusta, te devolvemos tu dinero</p>
    </div>
    
    <section class="final-cta">
        <h2>{t['final_cta']}</h2>
        <a href="{stripe_link}" class="cta-btn">{t['cta']}</a>
    </section>
    
    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Yayika",
        "description": "{config.get('meta_description', t['subtitle'])}",
        "brand": {{ "@type": "Brand", "name": "Yayika" }},
        "offers": {{
            "@type": "Offer",
            "price": "{config.get('price_numeric', '179')}",
            "priceCurrency": "MXN"
        }}
    }}
    </script>
</body>
</html>"""
    
    def _slugify(self, text: str) -> str:
        slug = text.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        hash_suffix = hashlib.md5(text.encode()).hexdigest()[:6]
        return f"{slug}-{hash_suffix}"


if __name__ == "__main__":
    gen = LandingPageGenerator('yayika')
    
    result = gen.create_landing_page({
        'title': 'Yayika - Plataforma para Mujeres Emprendedoras',
        'headline': 'Transforma tu vida con Yayika',
        'subtitle': 'La plataforma #1 para mujeres emprendedoras en Latinoamerica',
        'language': 'es',
        'price': '$179 MXN/mes',
        'price_name': 'Plan Semilla',
        'stripe_link': 'https://buy.stripe.com/00wcN502q0xY2481elgA80f',
        'meta_description': 'Yayika es la plataforma #1 para mujeres emprendedoras. Productos digitales, comunidad, mentoring y herramientas para tu crecimiento.'
    })
    
    print(f"Landing page created: {result['slug']}")
    print(f"Path: {result['path']}")
