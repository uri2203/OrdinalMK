"""
OrdinalMK — Multi-Language Landing Page Generator
Creates landing pages with region detection and localization.
"""

import json
from datetime import datetime
from pathlib import Path
from .regional import RegionalDistributor, REGIONS


PUBLISHED_DIR = Path(__file__).parent.parent.parent.parent / "published"


class MultilangLandingPageGenerator:
    """Generate landing pages with multi-language support and region detection."""
    
    def __init__(self, project_id: str, languages: list):
        self.project_id = project_id
        self.languages = languages
        self.distributor = RegionalDistributor(project_id, languages)
    
    def generate_multilang_landing(self, slug: str, content: dict, 
                                    pricing: dict = None, 
                                    testimonials: list = None) -> dict:
        """Generate landing pages in all supported languages with region detection."""
        results = {}
        
        for lang in self.languages:
            region = REGIONS.get(lang, {})
            lang_content = content.get(lang, content.get(self.languages[0], {}))
            
            # Localized pricing
            local_pricing = {}
            if pricing:
                for plan, details in pricing.items():
                    local_pricing[plan] = {
                        'name': details.get('name', plan),
                        'price': details.get('prices', {}).get(lang, details.get('prices', {}).get(self.languages[0], '$0')),
                        'features': details.get('features', {}).get(lang, details.get('features', {}).get(self.languages[0], [])),
                        'cta': details.get('cta', {}).get(lang, details.get('cta', {}).get(self.languages[0], 'Get Started'))
                    }
            
            # Localized testimonials
            local_testimonials = []
            if testimonials:
                for t in testimonials:
                    if lang in t.get('languages', [self.languages[0]]):
                        local_testimonials.append({
                            'name': t.get('name', ''),
                            'role': t.get('roles', {}).get(lang, t.get('role', '')),
                            'quote': t.get('quotes', {}).get(lang, t.get('quote', ''))
                        })
            
            html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{lang_content.get('title', self.project_id.title())}</title>
    <meta name="description" content="{lang_content.get('description', '')}">
    <meta name="keywords" content="{lang_content.get('keywords', '')}">
    
    <!-- hreflang for multi-language SEO -->
    {self.distributor.generate_hreflang_tags(slug, lang_content.get('title', ''), lang_content.get('description', ''))}
    
    <!-- Open Graph -->
    <meta property="og:title" content="{lang_content.get('title', '')}">
    <meta property="og:description" content="{lang_content.get('description', '')}">
    <meta property="og:locale" content="{region.get('locales', [lang])[0]}">
    <meta property="og:locale:alternate" content="en_US">
    
    <!-- Schema.org -->
    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": "{lang_content.get('title', '')}",
        "description": "{lang_content.get('description', '')}",
        "inLanguage": "{lang}",
        "publisher": {{
            "@type": "Organization",
            "name": "{self.project_id.title()}"
        }}
    }}
    </script>
    
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f1117; color: #e4e6f0; line-height: 1.6;
        }}
        .hero {{
            background: linear-gradient(135deg, #1a1d27, #232733);
            padding: 80px 20px; text-align: center;
            border-bottom: 1px solid #2d3140;
        }}
        .hero h1 {{ font-size: 3rem; margin-bottom: 16px; color: #6366f1; }}
        .hero p {{ font-size: 1.2rem; color: #8b8fa3; max-width: 600px; margin: 0 auto; }}
        .hero .cta {{
            display: inline-block; margin-top: 24px; padding: 16px 32px;
            background: #6366f1; color: white; text-decoration: none;
            border-radius: 8px; font-weight: 600; font-size: 1.1rem;
            transition: background 0.3s;
        }}
        .hero .cta:hover {{ background: #5558e6; }}
        
        .features {{
            max-width: 1000px; margin: 60px auto; padding: 0 20px;
        }}
        .features h2 {{ text-align: center; font-size: 2rem; margin-bottom: 40px; }}
        .feature-grid {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 24px;
        }}
        .feature-card {{
            background: #1a1d27; padding: 24px; border-radius: 12px;
            border: 1px solid #2d3140;
        }}
        .feature-card h3 {{ color: #6366f1; margin-bottom: 8px; }}
        .feature-card p {{ color: #8b8fa3; }}
        
        .pricing {{
            max-width: 1000px; margin: 60px auto; padding: 0 20px;
        }}
        .pricing h2 {{ text-align: center; font-size: 2rem; margin-bottom: 40px; }}
        .pricing-grid {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 24px;
        }}
        .pricing-card {{
            background: #1a1d27; padding: 32px; border-radius: 12px;
            border: 1px solid #2d3140; text-align: center;
        }}
        .pricing-card h3 {{ color: #6366f1; margin-bottom: 8px; }}
        .pricing-card .price {{ font-size: 2.5rem; font-weight: 700; margin: 16px 0; }}
        .pricing-card .cta {{
            display: block; padding: 12px; background: #6366f1; color: white;
            text-decoration: none; border-radius: 8px; margin-top: 16px;
        }}
        
        .testimonials {{
            max-width: 800px; margin: 60px auto; padding: 0 20px;
        }}
        .testimonials h2 {{ text-align: center; font-size: 2rem; margin-bottom: 40px; }}
        .testimonial {{
            background: #1a1d27; padding: 24px; border-radius: 12px;
            border: 1px solid #2d3140; margin-bottom: 16px;
        }}
        .testimonial .quote {{ color: #8b8fa3; font-style: italic; }}
        .testimonial .author {{ color: #6366f1; margin-top: 12px; }}
        
        footer {{
            text-align: center; padding: 40px 20px;
            border-top: 1px solid #2d3140; color: #4a4e5c;
        }}
    </style>
</head>
<body>
    <!-- Hero -->
    <section class="hero">
        <h1>{lang_content.get('title', self.project_id.title())}</h1>
        <p>{lang_content.get('subtitle', '')}</p>
        <a href="{lang_content.get('cta_link', '#')}" class="cta">{lang_content.get('cta_text', 'Get Started')}</a>
    </section>
    
    <!-- Features -->
    <section class="features">
        <h2>{lang_content.get('features_title', 'Features')}</h2>
        <div class="feature-grid">
            {''.join(f'''
            <div class="feature-card">
                <h3>{f.get('title', '')}</h3>
                <p>{f.get('description', '')}</p>
            </div>''' for f in lang_content.get('features', []))}
        </div>
    </section>
    
    <!-- Pricing -->
    {f'''
    <section class="pricing">
        <h2>{lang_content.get('pricing_title', 'Pricing')}</h2>
        <div class="pricing-grid">
            {''.join(f'''
            <div class="pricing-card">
                <h3>{plan['name']}</h3>
                <div class="price">{plan['price']}</div>
                <ul style="list-style: none; margin: 16px 0; text-align: left;">
                    {''.join(f'<li style="padding: 8px 0; color: #8b8fa3;">✓ {feat}</li>' for feat in plan.get('features', []))}
                </ul>
                <a href="#" class="cta">{plan.get('cta', 'Get Started')}</a>
            </div>''' for plan in local_pricing.values())}
        </div>
    </section>''' if local_pricing else ''}
    
    <!-- Testimonials -->
    {f'''
    <section class="testimonials">
        <h2>{lang_content.get('testimonials_title', 'Testimonials')}</h2>
        {''.join(f'''
        <div class="testimonial">
            <p class="quote">"{t['quote']}"</p>
            <p class="author">— {t['name']}, {t['role']}</p>
        </div>''' for t in local_testimonials)}
    </section>''' if local_testimonials else ''}
    
    <!-- Footer -->
    <footer>
        <p>{lang_content.get('footer_text', f'© 2024 {self.project_id.title()}. All rights reserved.')}</p>
        <div style="margin-top: 16px;">
            {''.join(f'<a href="/{l}/{slug}" style="margin: 0 8px; color: #6366f1;">{REGIONS.get(l, {{}}).get("name", l)}</a>' for l in self.languages)}
        </div>
    </footer>
    
    <!-- Region Detector -->
    {self.distributor.generate_region_detector()}
</body>
</html>"""
            
            # Save
            output_dir = PUBLISHED_DIR / self.project_id / lang
            output_dir.mkdir(parents=True, exist_ok=True)
            filepath = output_dir / f"{slug}.html"
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html)
            
            results[lang] = str(filepath)
        
        return results
    
    # ──────────────────────────────────────────────
    # BULK GENERATE ALL LANDING PAGES
    # ──────────────────────────────────────────────
    
    def generate_all_landings(self, project_config: dict) -> dict:
        """Generate all landing pages for a project."""
        results = {}
        
        # Main landing
        if 'concept' in project_config:
            results['main'] = self.generate_multilang_landing(
                slug='index',
                content=project_config['concept'],
                pricing=project_config.get('pricing'),
                testimonials=project_config.get('testimonials', [])
            )
        
        # Pricing page
        if 'pricing' in project_config:
            results['pricing'] = self.generate_multilang_landing(
                slug='pricing',
                content={'title': 'Pricing', 'subtitle': 'Choose your plan'},
                pricing=project_config.get('pricing')
            )
        
        return results


if __name__ == "__main__":
    generator = MultilangLandingPageGenerator('yayika', ['es', 'en', 'pt', 'fr', 'de'])
    
    # Test content
    test_content = {
        'es': {
            'title': 'Yayika - Tu negocio, tu forma',
            'subtitle': 'Emprende en la economia del conocimiento',
            'description': 'Plataforma para mujeres emprendedoras',
            'cta_text': 'Comienza Gratis',
            'features': [
                {'title': 'Tienda Online', 'description': 'Vende tus servicios'},
                {'title': 'Comunidad', 'description': 'Conecta con otras mujeres'}
            ]
        },
        'en': {
            'title': 'Yayika - Your business, your way',
            'subtitle': 'Thrive in the knowledge economy',
            'description': 'Platform for women entrepreneurs',
            'cta_text': 'Start Free',
            'features': [
                {'title': 'Online Store', 'description': 'Sell your services'},
                {'title': 'Community', 'description': 'Connect with other women'}
            ]
        }
    }
    
    results = generator.generate_multilang_landing('index', test_content)
    print(f"Generated landing pages in {len(results)} languages")
    for lang, path in results.items():
        print(f"  {lang}: {path}")
