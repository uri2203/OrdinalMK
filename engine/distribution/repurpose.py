"""
OrdinalMK — Repurposing multi-canal.

Un artículo → varios canales. De cada artículo publicado genera snippets nativos
para X/Twitter, LinkedIn, Facebook/Instagram y un email. Amplifica el mismo
contenido sin trabajo extra.

- Con credenciales de Anthropic + `anthropic` instalado: genera versiones
  adaptadas por plataforma con Claude.
- Sin credenciales: fallback de plantilla (título + resumen + enlace). Útil,
  aunque menos afinado.

La PUBLICACIÓN real en cada red necesita conectar cuentas (APIs oficiales); por
ahora los snippets se guardan a archivo para revisar/programar.
"""

import json
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
PUBLISHED_ROOT = REPO_ROOT / "published"

CONTENT_MODEL = os.environ.get("ORDINALMK_CONTENT_MODEL", "claude-opus-4-8")

CTA = {
    'es': 'Pruébalo gratis', 'en': 'Try it free', 'pt': 'Teste grátis',
    'fr': 'Essai gratuit', 'de': 'Kostenlos testen',
}


def _ai_available() -> bool:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get('ANTHROPIC_API_KEY')
               or os.environ.get('ANTHROPIC_AUTH_TOKEN')
               or os.environ.get('ANTHROPIC_PROFILE'))


def _brand_tag(brand: str) -> str:
    return '#' + re.sub(r'[^A-Za-z0-9]', '', brand or 'Marca')


def _url(article: dict, config: dict) -> str:
    domain = (config.get('domain') or f"{article.get('brand','').lower()}.com").replace(
        'https://', '').replace('http://', '').strip('/')
    lp = (config.get('deploy', {}).get('lp_path', 'lp')).strip('/')
    return f"https://{domain}/{lp}/{article['language']}/{article['slug']}"


def repurpose_article(article: dict, config: dict = None) -> dict:
    config = config or {}
    if _ai_available():
        try:
            return _repurpose_ai(article, config)
        except Exception as e:
            print(f"      [repurpose IA no disponible, uso plantilla] {e}")
    return _repurpose_template(article, config)


def _repurpose_template(article: dict, config: dict) -> dict:
    title = article.get('title', '')
    meta = article.get('meta_description', '') or title
    brand = article.get('brand', '')
    lang = article.get('language', 'es')
    url = _url(article, config)
    cta = CTA.get(lang, CTA['es'])
    tag = _brand_tag(brand)

    # X/Twitter: <= 280 chars
    x = f"{title} — {cta}. {url} {tag}"
    if len(x) > 280:
        room = 280 - len(f" — {cta}. {url} {tag}")
        x = f"{title[:max(0, room)].rstrip()} — {cta}. {url} {tag}"

    linkedin = (f"{title}\n\n{meta}\n\nCon {brand}: {cta}.\n{url}" if brand
                else f"{title}\n\n{meta}\n{url}")
    social = f"{title}\n{meta}\n{cta} → {url} {tag}"
    email = {
        'subject': title,
        'body': f"{meta}\n\n{cta}: {url}",
    }
    return {'ai_generated': False, 'x': x, 'linkedin': linkedin,
            'facebook_instagram': social, 'email': email, 'url': url}


def _repurpose_ai(article: dict, config: dict) -> dict:
    import anthropic
    client = anthropic.Anthropic()
    brand = article.get('brand', '')
    lang = article.get('language', 'es')
    url = _url(article, config)

    system = (f"Eres community manager de {brand}. Escribes en el idioma '{lang}'. "
              "Devuelves SOLO un JSON válido con las claves exactas: x, linkedin, "
              "facebook_instagram, email (objeto con subject y body). Nada más.")
    user = (f"Artículo: \"{article.get('title','')}\"\n"
            f"Resumen: {article.get('meta_description','')}\n"
            f"Enlace: {url}\n\n"
            "Crea posts nativos por plataforma que inviten a leer/probar:\n"
            "- x: <=280 caracteres, con el enlace y 1-2 hashtags.\n"
            "- linkedin: profesional, 3-5 líneas, con el enlace.\n"
            "- facebook_instagram: cercano, con gancho y el enlace.\n"
            "- email: subject (asunto corto) y body (2-3 líneas + CTA con el enlace).")
    resp = client.messages.create(
        model=CONTENT_MODEL, max_tokens=1500,
        system=system, messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    text = re.sub(r'^```(?:json)?|```$', '', text, flags=re.MULTILINE).strip()
    data = json.loads(text)
    data['ai_generated'] = True
    data['url'] = url
    return data


def repurpose_and_save(article: dict, config: dict = None,
                       published_root: Path = PUBLISHED_ROOT) -> dict:
    """Genera los snippets y los guarda en published/<p>/<lang>/_social/<slug>.json."""
    data = repurpose_article(article, config)
    project = (config or {}).get('_project_id') or article.get('project') or \
        (article.get('brand', 'proyecto').lower())
    out = published_root / project / article['language'] / "_social"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"{article['slug']}.json", 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data


if __name__ == "__main__":
    art = {
        'title': 'Automatiza tu facturación con IA local',
        'meta_description': 'Genera tus facturas CFDI en tu propia computadora, sin subir datos a la nube.',
        'brand': 'TuIAlista', 'language': 'es', 'slug': 'facturacion-ia-abc123',
    }
    cfg = {'domain': 'tuialista.com', 'deploy': {'lp_path': 'lp'}}
    r = _repurpose_template(art, cfg)
    print('X (', len(r['x']), 'chars):', r['x'])
    print('LinkedIn:', r['linkedin'][:60], '...')
    print('Email subject:', r['email']['subject'])
    assert len(r['x']) <= 280, 'X debe caber en 280'
    assert r['url'] in r['x'] and r['url'] in r['email']['body']
    assert all(k in r for k in ('x', 'linkedin', 'facebook_instagram', 'email'))
    print('OK: snippets multi-canal generados (fallback), X dentro de 280')
