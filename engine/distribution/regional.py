"""
OrdinalMK — Regional Distribution Engine
Handles multi-language SEO, email segmentation, and region detection.
"""

import json
import hashlib
import re
from datetime import datetime
from pathlib import Path

PUBLISHED_DIR = Path(__file__).parent.parent.parent / "published"


# ──────────────────────────────────────────────────
# REGION CONFIG
# ──────────────────────────────────────────────────
REGIONS = {
    'es': {
        'name': 'Espanol',
        'locales': ['es-MX', 'es-CO', 'es-AR', 'es-ES', 'es-CL', 'es-PE'],
        'countries': ['MX', 'CO', 'AR', 'ES', 'CL', 'PE', 'VE', 'EC', 'GT', 'CU', 'BO', 'DO', 'HN', 'PY', 'NI', 'SV', 'CR', 'PA', 'UY', 'GQ'],
        'google_domain': 'google.com',
        'currency': 'MXN',
        'email_tone': 'calido',
        'social_platforms': ['facebook', 'instagram', 'whatsapp'],
        'ad_platforms': ['meta_ads', 'google_ads'],
        'payment_methods': ['oxxo', 'spei', 'mercadopago'],
        'timezone': 'America/Mexico_City'
    },
    'en': {
        'name': 'English',
        'locales': ['en-US', 'en-GB', 'en-CA', 'en-AU'],
        'countries': ['US', 'GB', 'CA', 'AU', 'NZ', 'IE', 'ZA', 'SG', 'IN'],
        'google_domain': 'google.com',
        'currency': 'USD',
        'email_tone': 'professional',
        'social_platforms': ['instagram', 'twitter', 'linkedin'],
        'ad_platforms': ['meta_ads', 'google_ads', 'linkedin_ads'],
        'payment_methods': ['stripe', 'paypal'],
        'timezone': 'America/New_York'
    },
    'pt': {
        'name': 'Portugues',
        'locales': ['pt-BR', 'pt-PT'],
        'countries': ['BR', 'PT', 'AO', 'MZ', 'CV', 'GW', 'ST', 'TL'],
        'google_domain': 'google.com.br',
        'currency': 'BRL',
        'email_tone': 'calido',
        'social_platforms': ['instagram', 'facebook', 'whatsapp'],
        'ad_platforms': ['meta_ads', 'google_ads'],
        'payment_methods': ['pix', 'boleto', 'mercadopago'],
        'timezone': 'America/Sao_Paulo'
    },
    'fr': {
        'name': 'Francais',
        'locales': ['fr-FR', 'fr-CA', 'fr-BE', 'fr-CH'],
        'countries': ['FR', 'CA', 'BE', 'CH', 'LU', 'MC', 'SN', 'CI', 'ML', 'BF', 'NE', 'TD', 'MG', 'CM', 'GA', 'CD', 'CG', 'BJ', 'TG', 'BF'],
        'google_domain': 'google.fr',
        'currency': 'EUR',
        'email_tone': 'formel',
        'social_platforms': ['instagram', 'facebook', 'linkedin'],
        'ad_platforms': ['meta_ads', 'google_ads'],
        'payment_methods': ['stripe', 'cb', 'paypal'],
        'timezone': 'Europe/Paris'
    },
    'de': {
        'name': 'Deutsch',
        'locales': ['de-DE', 'de-AT', 'de-CH'],
        'countries': ['DE', 'AT', 'CH', 'LI', 'LU'],
        'google_domain': 'google.de',
        'currency': 'EUR',
        'email_tone': 'professionell',
        'social_platforms': ['instagram', 'facebook', 'linkedin'],
        'ad_platforms': ['meta_ads', 'google_ads'],
        'payment_methods': ['stripe', 'paypal', 'klarna'],
        'timezone': 'Europe/Berlin'
    }
}


class RegionalDistributor:
    """Handles multi-language content distribution."""
    
    def __init__(self, project_id: str, languages: list, domain: str = None):
        self.project_id = project_id
        self.languages = languages
        # El dominio SIEMPRE debe venir de la config del proyecto (multi-proyecto).
        # Fallback a "{project_id}.com" solo por compatibilidad; NO asumir para
        # dominios como lastmile-platform.com.
        self.domain = (domain or f"{project_id}.com").replace("https://", "").replace("http://", "").strip("/")
        self.base_url = f"https://{self.domain}"
        self.published_dir = PUBLISHED_DIR / project_id

    @staticmethod
    def _hreflang(locale: str) -> str:
        """Código hreflang válido para Google: guion, no guion bajo (es-ES, no es_ES)."""
        return locale.replace("_", "-")
    
    # ──────────────────────────────────────────────
    # SEO: HREFLANG + SITEMAPS
    # ──────────────────────────────────────────────
    
    def generate_hreflang_tags(self, slug: str, title: str, description: str) -> str:
        """Generate hreflang tags for a multi-language page."""
        tags = []
        base_url = self.base_url

        for lang in self.languages:
            region = REGIONS.get(lang, {})
            locale = region.get('locales', [f'{lang}'])[0]
            # hreflang usa el CÓDIGO DE IDIOMA (o idioma-región con guion), no el locale con "_".
            tags.append(f'<link rel="alternate" hreflang="{lang}" href="{base_url}/{lang}/{slug}" />')

        # x-default (fallback)
        tags.append(f'<link rel="alternate" hreflang="x-default" href="{base_url}/{self.languages[0]}/{slug}" />')

        return '\n'.join(tags)
    
    def generate_sitemap_per_language(self) -> dict:
        """Generate separate sitemaps for each language."""
        sitemaps = {}
        
        for lang in self.languages:
            urls = []
            pages_dir = self.published_dir / lang
            
            if pages_dir.exists():
                for page_file in pages_dir.rglob('*.html'):
                    slug = page_file.stem
                    priority = '1.0' if slug in ('index', '') else '0.8'
                    urls.append(f"""  <url>
    <loc>{self.base_url}/{lang}/{slug}</loc>
    <changefreq>weekly</changefreq>
    <priority>{priority}</priority>
  </url>""")
            
            sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">
{''.join(urls)}
</urlset>"""
            
            sitemaps[lang] = sitemap
            
            # Save
            output_dir = self.published_dir
            output_dir.mkdir(parents=True, exist_ok=True)
            filepath = output_dir / f"sitemap_{lang}.xml"
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(sitemap)
        
        # Generate sitemap index
        index = f"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{''.join(f'<sitemap><loc>{self.base_url}/sitemap_{lang}.xml</loc></sitemap>' for lang in self.languages)}
</sitemapindex>"""
        
        index_path = self.published_dir / "sitemap_index.xml"
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(index)
        
        return sitemaps
    
    def add_hreflang_to_html(self, html: str, slug: str, title: str, description: str) -> str:
        """Add hreflang tags to existing HTML."""
        hreflang = self.generate_hreflang_tags(slug, title, description)
        
        # Insert before </head>
        if '</head>' in html:
            html = html.replace('</head>', f'{hreflang}\n</head>')
        
        return html
    
    # ──────────────────────────────────────────────
    # EMAIL: SEGMENTATION
    # ──────────────────────────────────────────────
    
    def get_email_segment(self, subscriber_email: str, subscriber_country: str = None) -> dict:
        """Determine email segment for a subscriber."""
        # Detect language from country
        detected_lang = 'es'  # default
        
        if subscriber_country:
            for lang, region in REGIONS.items():
                if subscriber_country in region['countries']:
                    detected_lang = lang
                    break
        
        region = REGIONS.get(detected_lang, REGIONS['es'])
        
        return {
            'language': detected_lang,
            'country': subscriber_country,
            'locale': region['locales'][0],
            'currency': region['currency'],
            'email_tone': region['email_tone'],
            'google_domain': region['google_domain'],
            'payment_methods': region['payment_methods'],
            'tags': [f'lang:{detected_lang}', f'country:{subscriber_country}'] if subscriber_country else [f'lang:{detected_lang}']
        }
    
    def get_localized_email_template(self, template_name: str, language: str) -> dict:
        """Get email template localized for a language."""
        templates = {
            'welcome': {
                'es': {'subject': 'Bienvenida a Yayika', 'greeting': 'Hola {name},', 'body': 'Nos emociona que te hayas unido.'},
                'en': {'subject': 'Welcome to Yayika', 'greeting': 'Hi {name},', 'body': "We're excited to have you."},
                'pt': {'subject': 'Bem-vinda ao Yayika', 'greeting': 'Ola {name},', 'body': 'Estamos felizes que voce se juntou a nos.'},
                'fr': {'subject': 'Bienvenue sur Yayika', 'greeting': 'Bonjour {name},', 'body': 'Nous sommes ravis de vous accueillir.'},
                'de': {'subject': 'Willkommen bei Yayika', 'greeting': 'Hallo {name},', 'body': 'Wir freuen uns, Sie begrusen zu durfen.'}
            },
            'nurture': {
                'es': {'subject': '5 tips para tu exito', 'body': 'Aquí van 5 tips que te ayudaran.'},
                'en': {'subject': '5 tips for your success', 'body': 'Here are 5 tips to help you grow.'},
                'pt': {'subject': '5 dicas para seu sucesso', 'body': 'Aqui van 5 dicas para te ajudar.'},
                'fr': {'subject': '5 conseils pour reussir', 'body': 'Voici 5 conseils pour vous aider.'},
                'de': {'subject': '5 Tipps fur Ihren Erfolg', 'body': 'Hier sind 5 Tipps fur Sie.'}
            },
            'upsell': {
                'es': {'subject': 'Desbloquea tu potencial', 'body': 'Dale el siguiente paso con Yayika.'},
                'en': {'subject': 'Unlock your potential', 'body': 'Take the next step with Yayika.'},
                'pt': {'subject': 'Desbloqueie seu potencial', 'body': 'De o proximo passo com Yayika.'},
                'fr': {'subject': 'Realisez votre potentiel', 'body': "Faites le prochain pas avec Yayika."},
                'de': {'subject': 'Entfalten Sie Ihr Potenzial', 'body': 'Machen Sie den nachsten Schritt mit Yayika.'}
            }
        }
        
        return templates.get(template_name, {}).get(language, templates[template_name]['es'])
    
    # ──────────────────────────────────────────────
    # LANDING PAGES: REGION REDIRECT
    # ──────────────────────────────────────────────
    
    def generate_region_detector(self) -> str:
        """Generate JavaScript for region detection and redirect."""
        return f"""
<script>
// OrdinalMK — Region Detector
// Detects user's country and redirects to correct language
(function() {{
    const SUPPORTED = {json.dumps({lang: REGIONS[lang]['locales'][0] for lang in self.languages})};
    const DEFAULT = '{self.languages[0]}';
    
    // Check if already on correct language
    const path = window.location.pathname;
    const currentLang = path.split('/')[1];
    if(SUPPORTED[currentLang]) return; // Already on correct lang
    
    // Check localStorage for saved preference
    const saved = localStorage.getItem('ordinalmk_lang');
    if(saved && SUPPORTED[saved]) {{
        // Don't auto-redirect if user manually selected
        return;
    }}
    
    // Detect from browser
    const browserLang = navigator.language.split('-')[0];
    if(SUPPORTED[browserLang]) {{
        // Don't auto-redirect, just show suggestion
        showLangBanner(browserLang);
        return;
    }}
    
    // Default: show language selector
    showLangBanner(DEFAULT);
    
    function showLangBanner(suggested) {{
        const banner = document.createElement('div');
        banner.id = 'lang-banner';
        banner.style.cssText = 'position:fixed;bottom:0;left:0;right:0;background:#1a1d27;border-top:1px solid #2d3140;padding:1rem 2rem;display:flex;align-items:center;justify-content:space-between;z-index:9999;';
        
        const langNames = {json.dumps({lang: REGIONS[lang]['name'] for lang in self.languages})};
        
        banner.innerHTML = `
            <span style="color:#8b8fa3;font-size:0.9rem">
                detected: <strong style="color:#e4e6f0">${{langNames[suggested] || suggested}}</strong>
            </span>
            <div style="display:flex;gap:0.5rem">
                ${{Object.entries(SUPPORTED).map(([lang, locale]) => 
                    `<a href="/${{lang}}/${{path}}" style="padding:0.4rem 0.8rem;border-radius:6px;background:${{lang === suggested ? '#6366f1' : '#232733'}};color:${{lang === suggested ? 'white' : '#8b8fa3'}};text-decoration:none;font-size:0.8rem;font-weight:500">${{langNames[lang] || lang}}</a>`
                ).join('')}}
                <button onclick="this.parentElement.parentElement.remove()" style="background:none;border:none;color:#8b8fa3;cursor:pointer;padding:0.4rem">x</button>
            </div>
        `;
        document.body.appendChild(banner);
    }}
}})();
</script>"""
    
    # ──────────────────────────────────────────────
    # MULTI-LANGUAGE PAGE GENERATOR
    # ──────────────────────────────────────────────
    
    def generate_multilang_page(self, slug: str, content: dict) -> dict:
        """Generate a page in all supported languages with hreflang."""
        results = {}
        
        for lang in self.languages:
            lang_content = content.get(lang, content.get(self.languages[0], {}))
            
            html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{lang_content.get('title', '')} — {self.project_id.title()}</title>
    <meta name="description" content="{lang_content.get('description', '')}">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="{self.base_url}/{lang}/{slug}">
    {self.generate_hreflang_tags(slug, lang_content.get('title', ''), lang_content.get('description', ''))}
</head>
<body>
    <h1>{lang_content.get('title', '')}</h1>
    <p>{lang_content.get('body', '')}</p>
    {self.generate_region_detector()}
</body>
</html>"""
            
            # Save
            output_dir = self.published_dir / lang
            output_dir.mkdir(parents=True, exist_ok=True)
            filepath = output_dir / f"{slug}.html"
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html)
            
            results[lang] = str(filepath)
        
        return results
    
    # ──────────────────────────────────────────────
    # ANALYTICS: REGION REPORT
    # ──────────────────────────────────────────────
    
    def get_region_report(self) -> dict:
        """Generate a report of regional distribution status."""
        report = {
            'project': self.project_id,
            'languages': self.languages,
            'regions': {},
            'generated_at': datetime.now().isoformat()
        }
        
        for lang in self.languages:
            region = REGIONS.get(lang, {})
            pages_dir = self.published_dir / lang
            
            page_count = 0
            if pages_dir.exists():
                page_count = len(list(pages_dir.rglob('*.html')))
            
            report['regions'][lang] = {
                'name': region.get('name', lang),
                'locales': region.get('locales', []),
                'countries': region.get('countries', []),
                'google_domain': region.get('google_domain', 'google.com'),
                'currency': region.get('currency', 'USD'),
                'social_platforms': region.get('social_platforms', []),
                'payment_methods': region.get('payment_methods', []),
                'pages_published': page_count,
                'sitemap_exists': (self.published_dir / f'sitemap_{lang}.xml').exists()
            }
        
        return report


if __name__ == "__main__":
    distributor = RegionalDistributor('yayika', ['es', 'en', 'pt', 'fr', 'de'])
    
    # Generate sitemaps per language
    sitemaps = distributor.generate_sitemap_per_language()
    print(f"Generated {len(sitemaps)} language sitemaps")
    
    # Generate region report
    report = distributor.get_region_report()
    print(f"\nRegion Report for {report['project']}:")
    for lang, data in report['regions'].items():
        print(f"  {data['name']}: {data['pages_published']} pages, sitemap: {data['sitemap_exists']}")
