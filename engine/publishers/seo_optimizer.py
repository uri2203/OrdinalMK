"""
OrdinalMK — SEO Auto-Optimizer
Generates meta tags, sitemaps, and structured data for all content.
"""

import json
import os
from datetime import datetime
from pathlib import Path

PUBLISHED_DIR = Path(__file__).parent.parent.parent / "published"


class SEOOptimizer:
    """Auto-generates SEO elements for content."""
    
    def __init__(self, project_id: str, domain: str):
        self.project_id = project_id
        self.domain = domain
    
    def generate_sitemap(self, pages: list) -> str:
        """Generate XML sitemap for all pages."""
        urls = []
        for page in pages:
            url = page.get('url', f"https://{self.domain}/{page.get('slug', '')}")
            lastmod = page.get('published_at', datetime.now().isoformat()[:10])
            changefreq = page.get('changefreq', 'weekly')
            priority = page.get('priority', '0.8')
            
            urls.append(f"""  <url>
    <loc>{url}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>{changefreq}</changefreq>
    <priority>{priority}</priority>
  </url>""")
        
        sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{''.join(urls)}
</urlset>"""
        
        # Save
        output_dir = PUBLISHED_DIR / self.project_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = output_dir / "sitemap.xml"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(sitemap)
        
        return str(filepath)
    
    def generate_robots_txt(self) -> str:
        """Generate robots.txt."""
        content = f"""User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/

Sitemap: https://{self.domain}/sitemap.xml
"""
        output_dir = PUBLISHED_DIR / self.project_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = output_dir / "robots.txt"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(filepath)
    
    def generate_meta_tags(self, page: dict) -> str:
        """Generate meta tags HTML for a page."""
        title = page.get('title', self.project_id.title())
        description = page.get('description', '')
        url = page.get('url', f"https://{self.domain}/{page.get('slug', '')}")
        image = page.get('image', f"https://{self.domain}/og-image.png")
        language = page.get('language', 'es')
        
        return f"""<title>{title} — {self.project_id.title()}</title>
<meta name="description" content="{description}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{url}">

<!-- Open Graph -->
<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{image}">
<meta property="og:locale" content="{language}_MX">
<meta property="og:site_name" content="{self.project_id.title()}">

<!-- Twitter -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="{image}">"""
    
    def generate_structured_data(self, page: dict) -> dict:
        """Generate JSON-LD structured data."""
        schema_type = page.get('schema_type', 'WebPage')
        
        base = {
            "@context": "https://schema.org",
            "@type": schema_type,
            "name": page.get('title', ''),
            "description": page.get('description', ''),
            "url": page.get('url', f"https://{self.domain}/{page.get('slug', '')}"),
            "publisher": {
                "@type": "Organization",
                "name": self.project_id.title(),
                "url": f"https://{self.domain}"
            }
        }
        
        if schema_type == 'Article':
            base['datePublished'] = page.get('published_at', datetime.now().isoformat())
            base['author'] = {"@type": "Organization", "name": self.project_id.title()}
        
        if schema_type == 'Product':
            base['offers'] = {
                "@type": "Offer",
                "price": page.get('price', '0'),
                "priceCurrency": "MXN"
            }
        
        return base
    
    def analyze_page(self, html: str) -> dict:
        """Analyze a page for SEO issues."""
        issues = []
        score = 100
        
        # Check title
        if '<title>' not in html:
            issues.append({'severity': 'high', 'issue': 'Missing <title> tag'})
            score -= 20
        elif len(html.split('<title>')[1].split('</title>')[0]) > 60:
            issues.append({'severity': 'medium', 'issue': 'Title too long (>60 chars)'})
            score -= 5
        
        # Check meta description
        if 'meta name="description"' not in html:
            issues.append({'severity': 'high', 'issue': 'Missing meta description'})
            score -= 20
        
        # Check canonical
        if 'rel="canonical"' not in html:
            issues.append({'severity': 'medium', 'issue': 'Missing canonical tag'})
            score -= 10
        
        # Check Open Graph
        if 'og:title' not in html:
            issues.append({'severity': 'medium', 'issue': 'Missing Open Graph tags'})
            score -= 10
        
        # Check structured data
        if 'application/ld+json' not in html:
            issues.append({'severity': 'low', 'issue': 'Missing structured data (JSON-LD)'})
            score -= 5
        
        # Check images alt text
        import re
        imgs = re.findall(r'<img[^>]+>', html)
        imgs_without_alt = [img for img in imgs if 'alt=' not in img]
        if imgs_without_alt:
            issues.append({'severity': 'medium', 'issue': f'{len(imgs_without_alt)} images without alt text'})
            score -= 5
        
        return {
            'score': max(0, score),
            'issues': issues,
            'passed': len([i for i in issues if i['severity'] == 'high']) == 0
        }


if __name__ == "__main__":
    optimizer = SEOOptimizer('yayika', 'yayika.com')
    
    # Generate sitemap
    pages = [
        {'slug': '', 'url': 'https://yayika.com/', 'priority': '1.0', 'changefreq': 'daily'},
        {'slug': 'tienda', 'url': 'https://yayika.com/tienda', 'priority': '0.9', 'changefreq': 'weekly'},
        {'slug': 'comunidad', 'url': 'https://yayika.com/comunidad', 'priority': '0.8', 'changefreq': 'weekly'},
    ]
    
    sitemap_path = optimizer.generate_sitemap(pages)
    print(f"Sitemap: {sitemap_path}")
    
    robots_path = optimizer.generate_robots_txt()
    print(f"Robots: {robots_path}")
    
    # Analyze a page
    sample_html = '<html><head><title>Test Page</title></head><body></body></html>'
    analysis = optimizer.analyze_page(sample_html)
    print(f"SEO Score: {analysis['score']}/100")
    print(f"Issues: {len(analysis['issues'])}")
