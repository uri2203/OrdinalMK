"""
OrdinalMK — Content Publisher
Generates SEO-optimized articles and publishes them to project websites.
Supports multilingual content (ES, EN, PT, FR, DE).
"""

import json
import os
import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path

# ──────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────
PROJECTS_DIR = Path(__file__).parent.parent.parent
DATA_DIR = Path(__file__).parent.parent / "docs" / "data"
CALENDAR_DIR = Path(__file__).parent / "calendar"
CALENDAR_DIR.mkdir(exist_ok=True)

# Content topics per project
CONTENT_TOPICS = {
    'yayika': {
        'es': [
            'Como trackear tu ciclo menstrual para mejorar tu productividad',
            '5 estrategias para mujeres emprendedoras en 2026',
            'Guia completa: planificador digital para mujeres',
            'Beneficios de una comunidad de mujeres emprendedoras',
            'Como organizar tu vida con un planner digital',
            'Menstruacion y trabajo: tips para productividad',
            'Productos digitales que toda mujer necesita',
            'Como empezar tu negocio siendo mujer en Latinoamerica',
            'Salud menstrual: lo que nadie te cuenta',
            'Networking para mujeres: como crear tu circulo de apoyo'
        ],
        'en': [
            'How to track your menstrual cycle for better productivity',
            '5 strategies for women entrepreneurs in 2026',
            'Complete guide: digital planner for women',
            'Benefits of a women entrepreneur community',
            'How to organize your life with a digital planner',
            'Menstruation and work: productivity tips',
            'Digital products every woman needs',
            'How to start your business as a woman in Latin America',
            'Menstrual health: what nobody tells you',
            'Networking for women: how to build your support circle'
        ],
        'pt': [
            'Como rastrear seu ciclo menstrual para melhor produtividade',
            '5 estrategias para mulheres empreendedoras em 2026',
            'Guia completo: planejador digital para mulheres'
        ],
        'fr': [
            'Comment suivre votre cycle menstruel pour une meilleure productivité',
            '5 stratégies pour les femmes entrepreneures en 2026',
            'Guide complet: planificateur numérique pour femmes'
        ],
        'de': [
            'Wie du deinen Menstruationszyklus für mehr Produktivität trackst',
            '5 Strategien für Unternehmerinnen 2026',
            'Komplettleitfaden: digitaler Planer für Frauen'
        ]
    }
}


class ContentPublisher:
    """Generates and publishes SEO-optimized articles."""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.topics = CONTENT_TOPICS.get(project_id, {})
    
    def generate_article(self, topic: str, language: str = 'es') -> dict:
        """Generate a full SEO-optimized article."""
        # Generate slug
        slug = self._slugify(topic)
        
        # Generate article structure
        article = {
            'title': topic,
            'slug': slug,
            'language': language,
            'meta_description': self._generate_meta(topic, language),
            'keywords': self._extract_keywords(topic, language),
            'body': self._generate_body(topic, language),
            'word_count': 0,
            'reading_time_min': 0,
            'seo_score': 0,
            'status': 'draft',
            'generated_at': datetime.now().isoformat(),
            'published_at': None
        }
        
        # Calculate stats
        article['word_count'] = len(article['body'].split())
        article['reading_time_min'] = max(1, article['word_count'] // 200)
        article['seo_score'] = self._calculate_seo_score(article)
        
        return article
    
    def publish_article(self, article: dict) -> dict:
        """Publish article to the project website."""
        article['status'] = 'published'
        article['published_at'] = datetime.now().isoformat()
        
        # Save to content directory
        content_dir = Path(__file__).parent.parent / "content" / self.project_id
        content_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = content_dir / f"{article['slug']}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(article, f, indent=2, ensure_ascii=False)
        
        # Generate HTML page
        html = self._generate_html(article)
        html_dir = Path(__file__).parent.parent / "published" / self.project_id / article['language']
        html_dir.mkdir(parents=True, exist_ok=True)
        
        html_path = html_dir / f"{article['slug']}.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return {
            'status': 'published',
            'slug': article['slug'],
            'language': article['language'],
            'word_count': article['word_count'],
            'seo_score': article['seo_score'],
            'html_path': str(html_path)
        }
    
    def get_content_calendar(self, days: int = 30) -> list:
        """Generate a content calendar for the next N days."""
        calendar = []
        topics = self.topics
        
        all_topics = []
        for lang, lang_topics in topics.items():
            for topic in lang_topics:
                all_topics.append({'topic': topic, 'language': lang})
        
        # Schedule topics across days
        for i in range(min(days, len(all_topics))):
            date = (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')
            item = all_topics[i % len(all_topics)]
            
            calendar.append({
                'date': date,
                'topic': item['topic'],
                'language': item['language'],
                'status': 'scheduled',
                'project': self.project_id
            })
        
        # Save calendar
        calendar_path = CALENDAR_DIR / f"{self.project_id}_calendar.json"
        with open(calendar_path, 'w', encoding='utf-8') as f:
            json.dump(calendar, f, indent=2, ensure_ascii=False)
        
        return calendar
    
    def _generate_meta(self, topic: str, language: str) -> str:
        """Generate meta description."""
        metas = {
            'es': f"Descubre todo sobre {topic.lower()}. Guia practica con tips, herramientas y recomendaciones para mujeres emprendedoras.",
            'en': f"Learn everything about {topic.lower()}. Practical guide with tips, tools and recommendations for women entrepreneurs.",
            'pt': f"Descubra tudo sobre {topic.lower()}. Guia pratica com dicas, ferramentas e recomendacoes.",
            'fr': f"Decouvrez tout sur {topic.lower()}. Guide pratique avec conseils et recommandations.",
            'de': f"Erfahre alles über {topic.lower()}. Praktischer Leitfaden mit Tipps und Empfehlungen."
        }
        return metas.get(language, metas['es'])
    
    def _extract_keywords(self, topic: str, language: str) -> list:
        """Extract keywords from topic."""
        # Simple keyword extraction
        stop_words = {
            'es': ['el', 'la', 'los', 'las', 'un', 'una', 'de', 'del', 'en', 'para', 'con', 'por', 'que', 'como', 'y', 'a', 'tu', 'tu', 'lo'],
            'en': ['the', 'a', 'an', 'of', 'in', 'for', 'to', 'with', 'on', 'at', 'by', 'your', 'how', 'and', 'is', 'what'],
            'pt': ['o', 'a', 'os', 'as', 'um', 'uma', 'de', 'do', 'da', 'em', 'para', 'com', 'por', 'que', 'como', 'e'],
            'fr': ['le', 'la', 'les', 'un', 'une', 'de', 'du', 'des', 'en', 'pour', 'avec', 'par', 'que', 'comment', 'et'],
            'de': ['der', 'die', 'das', 'ein', 'eine', 'von', 'in', 'für', 'mit', 'auf', 'wie', 'und', 'ist', 'was']
        }
        
        words = re.findall(r'\w+', topic.lower())
        stops = stop_words.get(language, stop_words['en'])
        keywords = [w for w in words if w not in stops and len(w) > 3]
        
        return keywords[:5]
    
    def _generate_body(self, topic: str, language: str) -> str:
        """Generate article body content."""
        templates = {
            'es': f"""# {topic}

## Introduccion

En el mundo actual, las mujeres tienen la oportunidad de crear, innovar y liderar como nunca antes. {topic} es una habilidad essential para toda mujer que quiere tener exito en sus proyectos.

## Por que es importante

Entender {topic.lower()} te permite:
- Tomar mejores decisiones
- Optimizar tu tiempo y recursos
- Conectar con otras mujeres emprendedoras
- Crecer tanto personal como profesionalmente

## Tips practicos

### 1. Educate yourself
La informacion es poder. Dedica tiempo a aprender sobre este tema cada semana.

### 2. Connect with others
Una comunidad de apoyo es fundamental. Rodeate de mujeres que compartan tus metas.

### 3. Take action
El conocimiento sin accion no sirve. Implementa lo que aprendas de inmediato.

### 4. Track your progress
Mide tus resultados y ajusta tu estrategia segun sea necesario.

## Herramientas recomendadas

- **Yayika**: Tu plataforma integral para productos digitales
- **Planificador digital**: Organiza tu vida y tus proyectos
- **Comunidad de mujeres**: Conecta con otras emprendedoras

## Conclusion

{topic} no es solo una tendencia, es una necesidad. Empieza hoy y transforma tu vida.

---
*Articulo generado por OrdinalMK para Yayika*""",

            'en': f"""# {topic}

## Introduction

In today's world, women have the opportunity to create, innovate and lead like never before. {topic} is an essential skill for every woman who wants to succeed in her projects.

## Why it matters

Understanding {topic.lower()} allows you to:
- Make better decisions
- Optimize your time and resources
- Connect with other women entrepreneurs
- Grow both personally and professionally

## Practical tips

### 1. Educate yourself
Information is power. Dedicate time to learn about this topic every week.

### 2. Connect with others
A support community is fundamental. Surround yourself with women who share your goals.

### 3. Take action
Knowledge without action is useless. Implement what you learn immediately.

### 4. Track your progress
Measure your results and adjust your strategy as needed.

## Recommended tools

- **Yayika**: Your comprehensive platform for digital products
- **Digital planner**: Organize your life and projects
- **Women's community**: Connect with other entrepreneurs

## Conclusion

{topic} is not just a trend, it's a necessity. Start today and transform your life.

---
*Article generated by OrdinalMK for Yayika*""",

            'pt': f"""# {topic}

## Introducao

No mundo atual, as mulheres tem a oportunidade de criar, inovar e liderar como nunca antes. {topic} e uma habilidade essencial para toda mulher que quer ter sucesso em seus projetos.

## Por que e importante

Entender {topic.lower()} permite voce:
- Tomar melhores decisoes
- Otimizar seu tempo e recursos
- Conectar com outras mulheres empreendedoras
- Crescer pessoal e profissionalmente

## Dicas praticas

### 1. Se eduque
A informacao e poder. Dedique tempo a aprender sobre este tema toda semana.

### 2. Conecte-se com outros
Uma comunidade de apoio e fundamental. Cerque-se de mulheres que compartilhem seus objetivos.

### 3. Aja
O conhecimento sem acao nao serve. Implemente o que aprender imediatamente.

## Ferramentas recomendadas

- **Yayika**: Sua plataforma integral para produtos digitais
- **Planejador digital**: Organize sua vida e seus projetos

## Conclusao

{topic} nao e apenas uma tendencia, e uma necessidade. Comece hoje e transforme sua vida.

---
*Artigo gerado por OrdinalMK para Yayika*""",

            'fr': f"""# {topic}

## Introduction

Dans le monde d'aujourd'hui, les femmes ont l'opportunité de créer, innover et leader comme jamais auparavant. {topic} est une compétence essentielle pour chaque femme qui veut réussir.

## Pourquoi c'est important

Comprendre {topic.lower()} vous permet de:
- Prendre de meilleures décisions
- Optimiser votre temps et vos ressources
- Vous connecter avec d'autres femmes entrepreneures
- Grandir personnellement et professionnellement

## Conseils pratiques

### 1. Éduquez-vous
L'information est le pouvoir. Consacrez du temps à apprendre chaque semaine.

### 2. Connectez-vous avec d'autres
Une communauté de soutien est fondamentale. Entourez-vous de femmes qui partagent vos objectifs.

### 3. Agissez
Le savoir sans action ne sert à rien. Mettez en pratique immédiatement.

## Outils recommandés

- **Yayika**: Votre plateforme complète pour produits numériques
- **Planificateur numérique**: Organisez votre vie et vos projets

## Conclusion

{topic} n'est pas seulement une tendance, c'est une nécessité. Commencez aujourd'hui et transformez votre vie.

---
*Article généré par OrdinalMK pour Yayika*""",

            'de': f"""# {topic}

## Einleitung

In der heutigen Welt haben Frauen die Möglichkeit, wie noch nie zuvor zu schaffen, zu innovieren und zu führen. {topic} ist eine essentielle Fähigkeit für jede Frau, die Erfolg haben möchte.

## Warum es wichtig ist

{topic.lower()} zu verstehen erlaubt dir:
- Bessere Entscheidungen zu treffen
- Deine Zeit und Ressourcen zu optimieren
- Dich mit anderen Unternehmerinnen zu verbinden
- Persönlich und beruflich zu wachsen

## Praktische Tipps

### 1. Bilde dich weiter
Information ist Macht. Widme jede Woche Zeit, um über dieses Thema zu lernen.

### 2. Verbinde dich mit anderen
Eine Unterstützungscommunity ist grundlegend. Umringe dich von Frauen, die deine Ziele teilen.

### 3. Handele
Wissen ohne Handeln ist nutzlos. Setze um, was du lernst, sofort um.

## Empfohlene Tools

- **Yayika**: Deine Plattform für digitale Produkte
- **Digitaler Planer**: Organisiere dein Leben und deine Projekte

## Fazit

{topic} ist nicht nur ein Trend, es ist eine Notwendigkeit. Fang heute an und verändere dein Leben.

---
*Artikel generiert von OrdinalMK für Yayika*"""
        }
        
        return templates.get(language, templates['es'])
    
    def _calculate_seo_score(self, article: dict) -> int:
        """Calculate SEO score (0-100)."""
        score = 0
        
        # Title length (50-60 chars ideal)
        title_len = len(article['title'])
        if 50 <= title_len <= 60:
            score += 20
        elif 40 <= title_len <= 70:
            score += 10
        
        # Meta description (150-160 chars ideal)
        meta_len = len(article['meta_description'])
        if 150 <= meta_len <= 160:
            score += 20
        elif 120 <= meta_len <= 180:
            score += 10
        
        # Word count (1500+ ideal)
        if article['word_count'] >= 1500:
            score += 20
        elif article['word_count'] >= 1000:
            score += 10
        
        # Keywords present
        if article['keywords']:
            score += 10
        
        # Has headings
        if '##' in article['body']:
            score += 10
        
        # Has lists
        if '- ' in article['body'] or '1.' in article['body']:
            score += 10
        
        # Has conclusion
        if 'conclusion' in article['body'].lower() or 'conclusion' in article['body'].lower():
            score += 10
        
        return min(100, score)
    
    def _slugify(self, text: str) -> str:
        """Create URL-friendly slug."""
        slug = text.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = slug.strip('-')
        hash_suffix = hashlib.md5(text.encode()).hexdigest()[:6]
        return f"{slug}-{hash_suffix}"
    
    def _generate_html(self, article: dict) -> str:
        """Generate complete HTML page for article."""
        return f"""<!DOCTYPE html>
<html lang="{article['language']}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{article['title']} — Yayika</title>
    <meta name="description" content="{article['meta_description']}">
    <meta name="keywords" content="{', '.join(article['keywords'])}">
    <meta property="og:title" content="{article['title']}">
    <meta property="og:description" content="{article['meta_description']}">
    <meta property="og:type" content="article">
    <meta property="og:locale" content="{article['language']}_MX">
    <link rel="canonical" href="https://yayika.com/blog/{article['slug']}">
    <style>
        :root {{ --primary: #6366f1; --bg: #0f1117; --surface: #1a1d27; --text: #e4e6f0; --muted: #8b8fa3; }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); line-height: 1.8; }}
        .container {{ max-width: 800px; margin: 0 auto; padding: 2rem; }}
        h1 {{ font-size: 2.5rem; margin-bottom: 1rem; background: linear-gradient(135deg, var(--primary), #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        h2 {{ font-size: 1.5rem; margin: 2rem 0 1rem; color: var(--primary); }}
        h3 {{ font-size: 1.2rem; margin: 1.5rem 0 0.5rem; }}
        p {{ margin-bottom: 1rem; color: var(--muted); }}
        ul, ol {{ margin: 1rem 0 1rem 2rem; color: var(--muted); }}
        li {{ margin-bottom: 0.5rem; }}
        strong {{ color: var(--text); }}
        hr {{ border: none; border-top: 1px solid #2d3140; margin: 2rem 0; }}
        .meta {{ color: var(--muted); font-size: 0.9rem; margin-bottom: 2rem; }}
        .cta {{ background: var(--primary); color: white; padding: 1rem 2rem; border: none; border-radius: 8px; font-size: 1rem; cursor: pointer; margin: 2rem 0; }}
        .cta:hover {{ opacity: 0.9; }}
    </style>
</head>
<body>
    <article class="container">
        <div class="meta">
            <span>{article['language'].upper()}</span> · 
            <span>{article['reading_time_min']} min read</span> · 
            <span>{article['word_count']} words</span>
        </div>
        {self._markdown_to_html(article['body'])}
        <button class="cta" onclick="window.location='https://yayika.com'">
            {'Descubre Yayika' if article['language'] == 'es' else 'Discover Yayika' if article['language'] == 'en' else 'Decouvrir Yayika' if article['language'] == 'fr' else 'Entdecke Yayika' if article['language'] == 'de' else 'Descubra Yayika'}
        </button>
    </article>
    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "{article['title']}",
        "description": "{article['meta_description']}",
        "author": {{ "@type": "Organization", "name": "Yayika" }},
        "publisher": {{ "@type": "Organization", "name": "Yayika" }},
        "datePublished": "{article.get('published_at', datetime.now().isoformat())}",
        "inLanguage": "{article['language']}"
    }}
    </script>
</body>
</html>"""
    
    def _markdown_to_html(self, md: str) -> str:
        """Simple markdown to HTML converter."""
        html = md
        # Headers
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        # Bold
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        # Lists
        html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'(<li>.*</li>\n?)+', lambda m: f'<ul>{m.group()}</ul>', html, flags=re.MULTILINE)
        # Paragraphs
        html = re.sub(r'\n\n', '</p><p>', html)
        html = f'<p>{html}</p>'
        # HR
        html = html.replace('<p>---</p>', '<hr>')
        return html


if __name__ == "__main__":
    publisher = ContentPublisher('yayika')
    
    # Generate calendar
    calendar = publisher.get_content_calendar(30)
    print(f"Content Calendar: {len(calendar)} articles scheduled")
    
    # Generate first article
    article = publisher.generate_article(calendar[0]['topic'], calendar[0]['language'])
    result = publisher.publish_article(article)
    print(f"Published: {result['slug']} ({result['word_count']} words, SEO: {result['seo_score']}/100)")
