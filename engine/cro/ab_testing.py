"""
OrdinalMK — A/B testing de títulos/meta (CRO con Search Console).

Cierra el bucle de medición: para páginas con MUCHAS impresiones pero POCOS
clics (título/meta que no atrae), genera variantes de título y, cuando hay
datos, elige la ganadora por CTR. Sube clics sin ganar más ranking.

- Generación de variantes: fallback de plantillas (año, beneficio, pregunta,
  urgencia); hook para IA si se conecta.
- Selección: gana la variante con mayor CTR que supere una muestra mínima.

Todo offline/testeable. Consume los helpers de engine.measurement.search_console.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine.measurement.search_console import high_impressions_low_ctr

TITLE_MAX = 60
MIN_IMPRESSIONS = 50  # muestra mínima por variante para decidir


def _clip(s: str, n: int = TITLE_MAX) -> str:
    s = s.strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def title_variants(current_title: str, keyword: str = "", year: int = None) -> list:
    """Genera variantes de título orientadas a mejorar el CTR."""
    year = year or datetime.now().year
    base = current_title.strip()
    kw = (keyword or base).strip()
    cands = [
        base,                                              # control
        _clip(f"{base} ({year})"),                         # año/frescura
        _clip(f"Guía: {kw}"),                              # formato guía
        _clip(f"¿{kw[0].upper() + kw[1:]}?") if kw else base,  # pregunta
        _clip(f"{base} — paso a paso"),                    # accionable
    ]
    # dedup preservando orden, quitar vacíos
    seen, out = set(), []
    for c in cands:
        c = c.strip()
        if c and c.lower() not in seen:
            seen.add(c.lower())
            out.append(c)
    return out[:4]


def pick_winner(variants: list, min_impressions: int = MIN_IMPRESSIONS) -> dict:
    """Elige la variante con mayor CTR que tenga muestra suficiente.
    variants: [{'id','title','impressions','clicks'}]. Devuelve la ganadora o
    None si aún no hay datos suficientes (seguir probando)."""
    eligible = [v for v in variants if v.get('impressions', 0) >= min_impressions]
    if not eligible:
        return None
    for v in eligible:
        v['ctr'] = (v['clicks'] / v['impressions']) if v.get('impressions') else 0.0
    winner = max(eligible, key=lambda v: v['ctr'])
    return winner


def propose_experiments(project_id: str, config: dict, gsc_rows: list) -> list:
    """Crea experimentos de título para las páginas con impresiones altas y CTR
    bajo (las que más ganarían con mejor título/meta)."""
    experiments = []
    for r in high_impressions_low_ctr(gsc_rows):
        page = r.get('page', '')
        kw = r.get('query', '')
        current = r.get('title') or kw or page
        experiments.append({
            'project': project_id,
            'page': page,
            'reason': f"{r.get('impressions',0)} impresiones, CTR "
                      f"{round(float(r.get('ctr',0))*100,1)}%",
            'variants': title_variants(current, kw),
            'created_at': datetime.now(timezone.utc).isoformat(),
        })
    return experiments


if __name__ == "__main__":
    # 1) Variantes
    vs = title_variants("Automatizar facturación con IA", "software de facturación")
    print('variantes:', vs)
    assert vs[0] == "Automatizar facturación con IA"  # control primero
    assert len(vs) >= 2 and all(len(v) <= 60 for v in vs)

    # 2) Ganadora por CTR con muestra suficiente
    experiment = [
        {'id': 'A', 'title': 'control', 'impressions': 400, 'clicks': 8},   # 2%
        {'id': 'B', 'title': 'variante', 'impressions': 380, 'clicks': 30},  # ~7.9%
        {'id': 'C', 'title': 'poca data', 'impressions': 10, 'clicks': 5},   # 50% pero sin muestra
    ]
    w = pick_winner(experiment)
    print('ganadora:', w['id'], 'ctr', round(w['ctr'] * 100, 1), '%')
    assert w['id'] == 'B', 'gana B (mejor CTR con muestra suficiente)'
    assert pick_winner([{'id': 'X', 'impressions': 5, 'clicks': 3}]) is None  # sin muestra

    # 3) Propuestas desde GSC (solo impresiones altas + CTR bajo)
    rows = [
        {'page': '/lp/es/fact', 'query': 'facturación cfdi', 'impressions': 900, 'ctr': 0.007, 'position': 6.2},
        {'page': '/lp/es/ok', 'query': 'x', 'impressions': 300, 'ctr': 0.08, 'position': 3.0},  # buen CTR, no
    ]
    exps = propose_experiments('tuialista', {}, rows)
    print('experimentos propuestos:', [e['page'] for e in exps])
    assert [e['page'] for e in exps] == ['/lp/es/fact']
    print('OK: variantes + selección por CTR con muestra + propuestas desde GSC')
