"""
OrdinalMK — Generador de campañas de anuncios + creativos.

Deja las campañas LISTAS para lanzar (el gasto lo aprueba y carga el dueño; el
motor no gasta solo):
  - Google Search: grupos de anuncios a partir de las keywords objetivo de mayor
    intención (transaccional/comercial), con títulos y descripciones.
  - Meta (FB/IG): público a partir de `audience` + copy del anuncio.
  - Presupuesto sugerido, repartido Google/Meta.
  - Creativo: banner SVG con la marca (fallback); hook para generar imagen por
    API si se conecta una.

Guarda specs JSON + banner SVG en reports/campaigns/<proyecto>/. Testeable offline.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine.intelligence.keywords import classify_intent

CAMPAIGNS_DIR = REPO_ROOT / "reports" / "campaigns"


def _clip(s: str, n: int) -> str:
    s = s.strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def _google_campaign(config: dict, lang: str, budget: float) -> dict:
    brand = config.get('name', 'Marca')
    land = (config.get('landing') or {}).get(lang, {})
    cta = land.get('cta_text', 'Prueba gratis')
    targets = (config.get('seo') or {}).get('target_keywords', {}).get(lang, [])
    # Solo keywords de intención de compra para búsqueda pagada
    buy_kws = [k for k in targets if classify_intent(k) in ('transactional', 'commercial')]

    ad_groups = []
    for kw in buy_kws[:5]:
        ad_groups.append({
            'ad_group': kw,
            'keywords': [f'"{kw}"', f'[{kw}]'],  # frase y exacta
            'headlines': [
                _clip(brand, 30),
                _clip(kw.capitalize(), 30),
                _clip(cta, 30),
            ],
            'descriptions': [
                _clip(f"{land.get('subtitle', brand)}", 90),
                _clip(f"{cta}. Cancela cuando quieras.", 90),
            ],
            'final_url': land.get('cta_link', f"https://{config.get('domain','')}/"),
        })
    return {'platform': 'google_search', 'language': lang,
            'daily_budget': round(budget, 2), 'ad_groups': ad_groups}


def _meta_campaign(config: dict, lang: str, budget: float) -> dict:
    brand = config.get('name', 'Marca')
    land = (config.get('landing') or {}).get(lang, {})
    aud = config.get('audience', {})
    return {
        'platform': 'meta', 'language': lang, 'daily_budget': round(budget, 2),
        'targeting': {
            'locations': aud.get('location', ''),
            'demographic': aud.get('demographic', ''),
            'interests': aud.get('interests', []),
        },
        'ad': {
            'primary_text': _clip(land.get('description', land.get('subtitle', brand)), 300),
            'headline': _clip(land.get('title', brand), 40),
            'cta_button': land.get('cta_text', 'Más información'),
            'link': land.get('cta_link', f"https://{config.get('domain','')}/"),
            'creative': f"{lang}_banner.svg",
        },
    }


def _banner_svg(config: dict, lang: str) -> str:
    theme = config.get('theme', {})
    primary = theme.get('primary', '#6366f1')
    bg = theme.get('bg', '#0f1117')
    text = theme.get('text', '#ffffff')
    land = (config.get('landing') or {}).get(lang, {})
    brand = config.get('name', 'Marca')
    headline = _clip(land.get('subtitle', land.get('title', brand)), 80)
    cta = land.get('cta_text', 'Prueba gratis')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 628">
  <rect width="1200" height="628" fill="{bg}"/>
  <rect x="0" y="0" width="14" height="628" fill="{primary}"/>
  <text x="80" y="150" fill="{primary}" font-family="Arial, sans-serif" font-size="52" font-weight="bold">{brand}</text>
  <text x="80" y="300" fill="{text}" font-family="Arial, sans-serif" font-size="40" font-weight="bold">
    <tspan x="80" dy="0">{headline[:40]}</tspan>
    <tspan x="80" dy="56">{headline[40:80]}</tspan>
  </text>
  <rect x="80" y="430" width="360" height="80" rx="12" fill="{primary}"/>
  <text x="260" y="482" fill="#ffffff" font-family="Arial, sans-serif" font-size="30" font-weight="bold" text-anchor="middle">{cta}</text>
</svg>"""


def generate(project_id: str, config: dict, daily_budget: float = 15.0,
             lang: str = None, campaigns_dir: Path = CAMPAIGNS_DIR) -> dict:
    """Genera specs de Google + Meta y el creativo, listos para lanzar."""
    config = config or {}
    lang = lang or config.get('primary_language', 'es')
    google_budget = round(daily_budget * 0.6, 2)
    meta_budget = round(daily_budget * 0.4, 2)

    google = _google_campaign(config, lang, google_budget)
    meta = _meta_campaign(config, lang, meta_budget)
    banner = _banner_svg(config, lang)

    out_dir = campaigns_dir / project_id
    out_dir.mkdir(parents=True, exist_ok=True)
    spec = {
        'project': project_id, 'language': lang,
        'daily_budget_total': daily_budget,
        'note': 'Listo para lanzar. El gasto lo aprueba y carga el dueño.',
        'google': google, 'meta': meta,
    }
    (out_dir / f"{lang}_campaign.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False), encoding='utf-8')
    (out_dir / f"{lang}_banner.svg").write_text(banner, encoding='utf-8')
    return spec


if __name__ == "__main__":
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp(prefix='ads_'))
    try:
        cfg = {
            'name': 'TuIAlista', 'domain': 'tuialista.com', 'primary_language': 'es',
            'theme': {'primary': '#e8821e', 'bg': '#0f1922', 'text': '#ffffff'},
            'landing': {'es': {'title': 'TuIAlista — IA local',
                               'subtitle': 'Automatiza facturas y Excel sin subir tus datos',
                               'description': 'Agentes de IA que corren en tu equipo.',
                               'cta_text': 'Ver catálogo', 'cta_link': 'https://tuialista.com/catalogo/'}},
            'audience': {'location': 'México', 'demographic': 'PYMEs y contadores',
                         'interests': ['facturación', 'contabilidad']},
            'seo': {'target_keywords': {'es': [
                'software de facturación con ia',      # transaccional
                'mejor software de facturación 2026',  # comercial
                'qué es la facturación electrónica',   # informacional -> excluida
            ]}},
        }
        spec = generate('tuialista', cfg, daily_budget=15, campaigns_dir=tmp)
        print('presupuesto:', spec['daily_budget_total'],
              '| google grupos:', len(spec['google']['ad_groups']),
              '| meta headline:', spec['meta']['ad']['headline'])
        # Solo keywords de compra en Google
        ags = [g['ad_group'] for g in spec['google']['ad_groups']]
        assert 'qué es la facturación electrónica' not in ags, 'informacional no va a ads'
        assert 'software de facturación con ia' in ags
        # Límites de caracteres
        for g in spec['google']['ad_groups']:
            assert all(len(h) <= 30 for h in g['headlines']), 'títulos <=30'
            assert all(len(d) <= 90 for d in g['descriptions']), 'descripciones <=90'
        assert len(spec['meta']['ad']['headline']) <= 40
        assert (tmp / 'tuialista' / 'es_campaign.json').exists()
        assert (tmp / 'tuialista' / 'es_banner.svg').exists()
        print('OK: campañas Google+Meta + banner, solo keywords de compra, límites de caracteres')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
