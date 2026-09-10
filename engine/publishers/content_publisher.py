"""
OrdinalMK — Content Publisher
Generates SEO-optimized articles and publishes them to project websites.
Supports multilingual content (ES, EN, PT, FR, DE).

Content generation:
  - Si hay credenciales de Anthropic (ANTHROPIC_API_KEY o `ant auth login`) y el
    paquete `anthropic` está instalado, el cuerpo del artículo se redacta con
    Claude usando el perfil del proyecto (marca, dominio, audiencia, pain points,
    tono y keywords desde projects.yaml). Artículos únicos y largos = buen SEO.
  - Si no hay credenciales, se usa un fallback de plantilla que YA respeta la
    marca y el dominio correctos del proyecto (no queda cableado a una sola marca).

Modelo configurable con ORDINALMK_CONTENT_MODEL (por defecto claude-opus-4-8).
"""

import json
import os
import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent.parent
# Todo lo publicable vive en <repo>/published (igual que el generador de landings),
# para que el paso de deploy lo encuentre. NO en engine/published.
PUBLISHED_ROOT = REPO_ROOT / "published"
CONTENT_ROOT = REPO_ROOT / "content"
CALENDAR_DIR = Path(__file__).parent / "calendar"
CALENDAR_DIR.mkdir(exist_ok=True)

CONTENT_MODEL = os.environ.get("ORDINALMK_CONTENT_MODEL", "claude-opus-4-8")

SUPPORTED_LANGS = ['es', 'en', 'pt', 'fr', 'de']
LANG_LOCALES = {
    'es': 'es-MX', 'en': 'en-US', 'pt': 'pt-BR', 'fr': 'fr-FR', 'de': 'de-DE'
}
LANG_NAMES = {
    'es': 'español', 'en': 'English', 'pt': 'português',
    'fr': 'français', 'de': 'Deutsch'
}
CTA_LABELS = {
    'es': 'Descubre {brand}', 'en': 'Discover {brand}', 'pt': 'Descubra {brand}',
    'fr': 'Découvrir {brand}', 'de': 'Entdecke {brand}'
}


class ContentPublisher:
    """Generates and publishes SEO-optimized articles for a specific project."""

    def __init__(self, project_id: str, config: dict = None):
        self.project_id = project_id
        self.config = config or {}

        # Identidad de marca (multi-proyecto, ya no cableada a Yayika)
        self.brand = self.config.get('name') or project_id.title()
        self.domain = (self.config.get('domain') or f"{project_id}.com").replace(
            "https://", "").replace("http://", "").strip("/")
        # Los artículos se despliegan bajo /lp/<lang>/<slug> (ver _deploy en el
        # orquestador). Usamos esa misma base para canonical/hreflang.
        self.lp_path = (self.config.get('deploy', {}).get('lp_path', 'lp')).strip('/')

        # Temas por idioma (desde projects.yaml -> content.topics)
        self.topics = self.config.get('content', {}).get('topics', {})

        # Perfil para la IA
        self.tone = self.config.get('content', {}).get('tone', 'profesional y claro')
        self.style = self.config.get('content', {}).get('style', 'práctico con ejemplos')
        self.audience = self.config.get('audience', {})
        self.keywords_by_lang = self.config.get('seo', {}).get('target_keywords', {})

    # ──────────────────────────────────────────────
    # GENERATE
    # ──────────────────────────────────────────────
    def generate_article(self, topic: str, language: str = 'es') -> dict:
        """Generate a full SEO-optimized article."""
        slug = self._slugify(topic)
        body = self._generate_body(topic, language)

        article = {
            'title': topic,
            'slug': slug,
            'language': language,
            'brand': self.brand,
            'domain': self.domain,
            'meta_description': self._generate_meta(topic, language, body),
            'keywords': self._extract_keywords(topic, language),
            'body': body,
            'word_count': len(body.split()),
            'reading_time_min': max(1, len(body.split()) // 200),
            'seo_score': 0,
            'ai_generated': self._ai_available(),
            'status': 'draft',
            'generated_at': datetime.now().isoformat(),
            'published_at': None,
        }
        article['seo_score'] = self._calculate_seo_score(article)
        return article

    def publish_article(self, article: dict) -> dict:
        """Publish article to the project website."""
        article['status'] = 'published'
        article['published_at'] = datetime.now().isoformat()

        # JSON (fuente de datos) en <repo>/content/<project>/
        content_dir = CONTENT_ROOT / self.project_id
        content_dir.mkdir(parents=True, exist_ok=True)
        with open(content_dir / f"{article['slug']}.json", 'w', encoding='utf-8') as f:
            json.dump(article, f, indent=2, ensure_ascii=False)

        # HTML en <repo>/published/<project>/<lang>/ (lo recoge el deploy)
        html_dir = PUBLISHED_ROOT / self.project_id / article['language']
        html_dir.mkdir(parents=True, exist_ok=True)
        html_path = html_dir / f"{article['slug']}.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(self._generate_html(article))

        return {
            'status': 'published',
            'slug': article['slug'],
            'language': article['language'],
            'word_count': article['word_count'],
            'seo_score': article['seo_score'],
            'ai_generated': article['ai_generated'],
            'html_path': str(html_path),
        }

    def get_content_calendar(self, days: int = 30) -> list:
        """Generate a content calendar for the next N days.

        Solo agenda los idiomas ACTIVOS del proyecto (lanzamiento por fases):
        los idiomas soportados pero aún no activos no se producen todavía.
        """
        try:
            import sys as _sys
            _sys.path.insert(0, str(REPO_ROOT))
            from config.projects import active_languages as _active
            active = set(_active(self.config))
        except Exception:
            active = set(self.topics.keys())  # fallback: todos

        all_topics = []
        for lang, lang_topics in self.topics.items():
            if lang not in active:
                continue
            for topic in lang_topics:
                all_topics.append({'topic': topic, 'language': lang})

        calendar = []
        for i in range(min(days, len(all_topics))):
            date = (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')
            item = all_topics[i % len(all_topics)]
            calendar.append({
                'date': date,
                'topic': item['topic'],
                'language': item['language'],
                'status': 'scheduled',
                'project': self.project_id,
            })

        with open(CALENDAR_DIR / f"{self.project_id}_calendar.json", 'w', encoding='utf-8') as f:
            json.dump(calendar, f, indent=2, ensure_ascii=False)
        return calendar

    # ──────────────────────────────────────────────
    # BODY (IA con fallback)
    # ──────────────────────────────────────────────
    def _ai_available(self) -> bool:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        # Con credenciales por env o perfil de `ant auth login`, el cliente
        # zero-arg funciona. Basta con que exista alguna de estas señales.
        return bool(
            os.environ.get('ANTHROPIC_API_KEY')
            or os.environ.get('ANTHROPIC_AUTH_TOKEN')
            or os.environ.get('ANTHROPIC_PROFILE')
        )

    def _generate_body(self, topic: str, language: str) -> str:
        """Genera el cuerpo del artículo. IA si hay credenciales; si no, plantilla."""
        if self._ai_available():
            try:
                return self._generate_body_ai(topic, language)
            except Exception as e:  # nunca romper el pipeline por un fallo de red/API
                print(f"    [IA no disponible, uso plantilla] {e}")
        return self._generate_body_template(topic, language)

    def _generate_body_ai(self, topic: str, language: str) -> str:
        import anthropic

        client = anthropic.Anthropic()
        lang_name = LANG_NAMES.get(language, language)
        keywords = ", ".join(self.keywords_by_lang.get(language, [])) or "—"
        pains = self.audience.get('pain_points', [])
        pains_txt = "\n".join(f"- {p}" for p in pains) if pains else "—"
        demo = self.audience.get('demographic', '')

        system = (
            f"Eres un redactor SEO experto que escribe para la marca {self.brand} "
            f"({self.domain}). Escribes en {lang_name}, con tono {self.tone} y estilo "
            f"{self.style}. NUNCA menciones otras marcas. Mencionas {self.brand} de forma "
            f"natural 2-3 veces (no spam). Devuelves SOLO el artículo en Markdown, sin "
            f"comentarios ni notas fuera del artículo."
        )
        user = f"""Escribe un artículo SEO en {lang_name} sobre: "{topic}"

Contexto de la marca:
- Marca: {self.brand} — {self.config.get('concept', '')}
- Público objetivo: {demo}
- Puntos de dolor del lector:
{pains_txt}
- Keywords a cubrir de forma natural: {keywords}

Requisitos:
- 1200-1600 palabras, único y con valor real (no relleno genérico).
- Empieza con un H1 (# ) que sea el título.
- Usa subtítulos (## y ###), listas y ejemplos accionables.
- Incluye una sección de conclusión con una llamada a la acción sutil hacia {self.brand}.
- Incluye una mini sección de preguntas frecuentes (FAQ) con 3 preguntas y respuestas.
- Escribe para humanos primero; el SEO es consecuencia de la calidad.
"""
        resp = client.messages.create(
            model=CONTENT_MODEL,
            max_tokens=8000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if not text:
            raise RuntimeError("respuesta vacía de la IA")
        return text

    def _generate_body_template(self, topic: str, language: str) -> str:
        """Fallback sin IA — plantilla que respeta marca y dominio del proyecto."""
        b = self.brand
        concept = self.config.get('concept', '')
        headings = {
            'es': ("Introducción", "Por qué importa", "Cómo aplicarlo", "Conclusión"),
            'en': ("Introduction", "Why it matters", "How to apply it", "Conclusion"),
            'pt': ("Introdução", "Por que importa", "Como aplicar", "Conclusão"),
            'fr': ("Introduction", "Pourquoi c'est important", "Comment l'appliquer", "Conclusion"),
            'de': ("Einleitung", "Warum es wichtig ist", "Wie du es anwendest", "Fazit"),
        }
        h = headings.get(language, headings['es'])
        return f"""# {topic}

## {h[0]}

{topic} es un tema clave para quienes buscan resultados reales. En {b} ({concept}) lo abordamos de forma práctica para que puedas aplicarlo hoy mismo.

## {h[1]}

Entender {topic.lower()} te permite tomar mejores decisiones, ahorrar tiempo y obtener mejores resultados de forma sostenible.

## {h[2]}

1. Define un objetivo concreto y medible.
2. Empieza pequeño y mide lo que funciona.
3. Ajusta con base en datos, no en suposiciones.
4. Apóyate en herramientas que te quiten trabajo repetitivo.

## {h[3]}

{topic} no es una moda: es una ventaja competitiva. Da el primer paso con {b}.
"""

    # ──────────────────────────────────────────────
    # SEO helpers
    # ──────────────────────────────────────────────
    def _generate_meta(self, topic: str, language: str, body: str = "") -> str:
        base = {
            'es': f"{topic}: guía práctica de {self.brand} con tips accionables y herramientas para lograrlo.",
            'en': f"{topic}: a practical {self.brand} guide with actionable tips and tools to get it done.",
            'pt': f"{topic}: guia prático da {self.brand} com dicas acionáveis e ferramentas.",
            'fr': f"{topic} : guide pratique {self.brand} avec des conseils concrets et des outils.",
            'de': f"{topic}: praktischer {self.brand}-Leitfaden mit umsetzbaren Tipps und Tools.",
        }
        meta = base.get(language, base['es'])
        return meta[:157] + ("…" if len(meta) > 157 else "")

    def _extract_keywords(self, topic: str, language: str) -> list:
        stop_words = {
            'es': {'el', 'la', 'los', 'las', 'un', 'una', 'de', 'del', 'en', 'para', 'con', 'por', 'que', 'como', 'y', 'a', 'tu', 'lo'},
            'en': {'the', 'a', 'an', 'of', 'in', 'for', 'to', 'with', 'on', 'at', 'by', 'your', 'how', 'and', 'is', 'what'},
            'pt': {'o', 'a', 'os', 'as', 'um', 'uma', 'de', 'do', 'da', 'em', 'para', 'com', 'por', 'que', 'como', 'e'},
            'fr': {'le', 'la', 'les', 'un', 'une', 'de', 'du', 'des', 'en', 'pour', 'avec', 'par', 'que', 'comment', 'et'},
            'de': {'der', 'die', 'das', 'ein', 'eine', 'von', 'in', 'für', 'mit', 'auf', 'wie', 'und', 'ist', 'was'},
        }
        words = re.findall(r'\w+', topic.lower())
        stops = stop_words.get(language, stop_words['en'])
        # Prioriza keywords de la config si las hay
        cfg_kw = [k for k in self.keywords_by_lang.get(language, [])]
        kws = cfg_kw + [w for w in words if w not in stops and len(w) > 3]
        # dedup preservando orden
        seen, out = set(), []
        for k in kws:
            if k.lower() not in seen:
                seen.add(k.lower())
                out.append(k)
        return out[:6]

    def _calculate_seo_score(self, article: dict) -> int:
        score = 0
        title_len = len(article['title'])
        if 50 <= title_len <= 60:
            score += 20
        elif 40 <= title_len <= 70:
            score += 10
        meta_len = len(article['meta_description'])
        if 150 <= meta_len <= 160:
            score += 20
        elif 120 <= meta_len <= 180:
            score += 10
        if article['word_count'] >= 1500:
            score += 20
        elif article['word_count'] >= 1000:
            score += 10
        if article['keywords']:
            score += 10
        if '##' in article['body']:
            score += 10
        if '- ' in article['body'] or '1.' in article['body']:
            score += 10
        if re.search(r'conclus|fazit|conclusion', article['body'].lower()):
            score += 10
        return min(100, score)

    def _slugify(self, text: str) -> str:
        slug = re.sub(r'[^\w\s-]', '', text.lower())
        slug = re.sub(r'[\s_]+', '-', slug).strip('-')
        return f"{slug}-{hashlib.md5(text.encode()).hexdigest()[:6]}"

    # ──────────────────────────────────────────────
    # HTML
    # ──────────────────────────────────────────────
    def _article_url(self, lang: str, slug: str) -> str:
        return f"https://{self.domain}/{self.lp_path}/{lang}/{slug}"

    def _generate_html(self, article: dict) -> str:
        lang = article['language']
        slug = article['slug']
        canonical = self._article_url(lang, slug)
        cta_link = self.config.get('landing', {}).get(lang, {}).get(
            'cta_link', f"https://{self.domain}/")
        cta_label = CTA_LABELS.get(lang, CTA_LABELS['es']).format(brand=self.brand)

        # hreflang para los idiomas realmente publicados del proyecto
        langs = self.config.get('languages', [lang])
        hreflang_links = [
            f'    <link rel="alternate" hreflang="{LANG_LOCALES.get(l, l)}" href="{self._article_url(l, slug)}">'
            for l in langs
        ]
        hreflang_links.append(
            f'    <link rel="alternate" hreflang="x-default" href="{self._article_url(langs[0] if langs else lang, slug)}">')

        theme = self.config.get('theme', {})
        primary = theme.get('primary', '#6366f1')
        primary_dark = theme.get('primary_dark', primary)
        bg = theme.get('bg', '#0f1117')
        surface = theme.get('surface', '#1a1d27')
        text = theme.get('text', '#e4e6f0')
        muted = theme.get('muted', '#8b8fa3')
        line = theme.get('line', '#2d3140')
        og_locale = LANG_LOCALES.get(lang, lang)
        og_image = self.config.get('og_image', f"https://{self.domain}/og-image.png")

        return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{article['title']} — {self.brand}</title>
    <meta name="description" content="{article['meta_description']}">
    <meta name="keywords" content="{', '.join(article['keywords'])}">
    <meta name="robots" content="index, follow">
    <meta property="og:title" content="{article['title']}">
    <meta property="og:description" content="{article['meta_description']}">
    <meta property="og:type" content="article">
    <meta property="og:site_name" content="{self.brand}">
    <meta property="og:locale" content="{og_locale}">
    <meta property="og:image" content="{og_image}">
    <meta property="og:url" content="{canonical}">
    <link rel="canonical" href="{canonical}">
{chr(10).join(hreflang_links)}
    <style>
        :root {{ --primary: {primary}; --primary-dark: {primary_dark}; --bg: {bg}; --surface: {surface}; --text: {text}; --muted: {muted}; --line: {line}; }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); line-height: 1.8; }}
        .container {{ max-width: 800px; margin: 0 auto; padding: 2rem; }}
        h1 {{ font-size: 2.4rem; margin-bottom: 1rem; color: var(--primary); }}
        h2 {{ font-size: 1.5rem; margin: 2rem 0 1rem; color: var(--primary); }}
        h3 {{ font-size: 1.15rem; margin: 1.5rem 0 0.5rem; }}
        p {{ margin-bottom: 1rem; color: var(--muted); }}
        ul, ol {{ margin: 1rem 0 1rem 2rem; color: var(--muted); }}
        li {{ margin-bottom: 0.5rem; }}
        strong {{ color: var(--text); }}
        hr {{ border: none; border-top: 1px solid var(--line); margin: 2rem 0; }}
        .meta {{ color: var(--muted); font-size: 0.9rem; margin-bottom: 2rem; }}
        .cta {{ display:inline-block; background: var(--primary); color: white; padding: 1rem 2rem; border: none; border-radius: 8px; font-size: 1rem; cursor: pointer; margin: 2rem 0; text-decoration:none; }}
        .cta:hover {{ background: var(--primary-dark); }}
    </style>
</head>
<body>
    <article class="container">
        <div class="meta">
            <span>{lang.upper()}</span> · <span>{article['reading_time_min']} min</span> · <span>{article['word_count']} palabras</span>
        </div>
        {self._markdown_to_html(article['body'])}
        <a class="cta" href="{cta_link}">{cta_label}</a>
    </article>
    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": {json.dumps(article['title'])},
        "description": {json.dumps(article['meta_description'])},
        "author": {{ "@type": "Organization", "name": {json.dumps(self.brand)} }},
        "publisher": {{ "@type": "Organization", "name": {json.dumps(self.brand)} }},
        "datePublished": {json.dumps(article.get('published_at') or datetime.now().isoformat())},
        "inLanguage": {json.dumps(og_locale)},
        "mainEntityOfPage": {json.dumps(canonical)}
    }}
    </script>
</body>
</html>"""

    def _markdown_to_html(self, md: str) -> str:
        html = md
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'^\s*[-*] (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'^\s*\d+\.\s+(.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'(<li>.*?</li>\s*)+', lambda m: f'<ul>{m.group()}</ul>', html, flags=re.DOTALL)
        html = re.sub(r'\n\n', '</p><p>', html)
        html = f'<p>{html}</p>'
        html = html.replace('<p>---</p>', '<hr>')
        # limpia párrafos que envuelven headings/listas
        html = re.sub(r'<p>\s*(<h[1-3]>)', r'\1', html)
        html = re.sub(r'(</h[1-3]>)\s*</p>', r'\1', html)
        html = re.sub(r'<p>\s*(<ul>)', r'\1', html)
        html = re.sub(r'(</ul>)\s*</p>', r'\1', html)
        return html


if __name__ == "__main__":
    import yaml
    cfg_path = REPO_ROOT / "config" / "projects.yaml"
    cfg = yaml.safe_load(open(cfg_path, encoding='utf-8'))
    project = os.environ.get("ORDINALMK_PROJECT", "tuialista")
    pub = ContentPublisher(project, cfg['projects'][project])
    cal = pub.get_content_calendar(30)
    print(f"Calendar: {len(cal)} artículos")
    art = pub.generate_article(cal[0]['topic'], cal[0]['language'])
    res = pub.publish_article(art)
    print(f"Publicado: {res['slug']} ({res['word_count']} palabras, SEO {res['seo_score']}, IA={res['ai_generated']})")
