"""
OrdinalMK — Analítica real de tráfico (Plausible / GA4) con fallback.

Cierra el bucle contenido -> visita -> cliente con NÚMEROS REALES (hoy el
dashboard usa datos de ejemplo). Fuentes:

  - Plausible (privacy-first, API simple): visitantes, vistas, top páginas, fuentes.
  - GA4 (Data API) si se configura (opcional).
  - Sin credenciales: devuelve ceros con source='none' (no rompe; el panel lo
    marca como "sin conectar").

Parsers puros y testeables. Env: PLAUSIBLE_API_KEY, PLAUSIBLE_SITE_ID (o domain),
PLAUSIBLE_HOST (para self-host; por defecto plausible.io).
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _blank(source='none', reason=''):
    return {'source': source, 'visitors': 0, 'pageviews': 0,
            'top_pages': [], 'sources': [], 'reason': reason}


def _domain(config: dict) -> str:
    return (config.get('domain') or '').replace('https://', '').replace('http://', '').strip('/')


def parse_aggregate(data: dict) -> dict:
    """De /stats/aggregate: {results:{visitors:{value},pageviews:{value}}}."""
    res = (data or {}).get('results', {}) or {}
    return {
        'visitors': int((res.get('visitors') or {}).get('value', 0) or 0),
        'pageviews': int((res.get('pageviews') or {}).get('value', 0) or 0),
    }


def parse_breakdown(data: dict, label_key: str, value_key: str = 'visitors') -> list:
    """De /stats/breakdown: {results:[{<label_key>:.., visitors:..}, ...]}."""
    out = []
    for row in (data or {}).get('results', []) or []:
        out.append({'label': row.get(label_key, ''), 'value': int(row.get(value_key, 0) or 0)})
    return out


def plausible(config: dict, period: str = '30d') -> dict:
    key = os.environ.get('PLAUSIBLE_API_KEY')
    site = os.environ.get('PLAUSIBLE_SITE_ID') or _domain(config)
    host = os.environ.get('PLAUSIBLE_HOST', 'https://plausible.io').rstrip('/')
    if not key or not site:
        return _blank('none', 'falta PLAUSIBLE_API_KEY o site')
    try:
        import requests
        h = {'Authorization': f'Bearer {key}'}
        agg = requests.get(f"{host}/api/v1/stats/aggregate",
                           params={'site_id': site, 'period': period,
                                   'metrics': 'visitors,pageviews'}, headers=h, timeout=15).json()
        pages = requests.get(f"{host}/api/v1/stats/breakdown",
                             params={'site_id': site, 'period': period,
                                     'property': 'event:page', 'limit': 8}, headers=h, timeout=15).json()
        srcs = requests.get(f"{host}/api/v1/stats/breakdown",
                            params={'site_id': site, 'period': period,
                                    'property': 'visit:source', 'limit': 8}, headers=h, timeout=15).json()
        base = parse_aggregate(agg)
        return {'source': 'plausible', **base,
                'top_pages': parse_breakdown(pages, 'page'),
                'sources': parse_breakdown(srcs, 'source')}
    except Exception as e:
        return _blank('none', f'error {type(e).__name__}')


def summary(config: dict, period: str = '30d') -> dict:
    """Analítica unificada: intenta Plausible; si no, ceros marcados."""
    if os.environ.get('PLAUSIBLE_API_KEY'):
        return plausible(config, period)
    # hook GA4 futuro: if os.environ.get('GA4_PROPERTY_ID'): return ga4(...)
    return _blank('none', 'sin analítica conectada')


if __name__ == "__main__":
    # 1) parse_aggregate puro
    agg = {'results': {'visitors': {'value': 1250}, 'pageviews': {'value': 3800}}}
    b = parse_aggregate(agg)
    print('aggregate:', b)
    assert b['visitors'] == 1250 and b['pageviews'] == 3800
    assert parse_aggregate({}) == {'visitors': 0, 'pageviews': 0}

    # 2) parse_breakdown puro
    bd = {'results': [{'page': '/', 'visitors': 500}, {'page': '/precios', 'visitors': 200}]}
    rows = parse_breakdown(bd, 'page')
    print('breakdown:', rows)
    assert rows[0] == {'label': '/', 'value': 500} and len(rows) == 2
    src = parse_breakdown({'results': [{'source': 'Google', 'visitors': 320}]}, 'source')
    assert src[0]['label'] == 'Google' and src[0]['value'] == 320

    # 3) sin credenciales -> ceros marcados, no rompe
    os.environ.pop('PLAUSIBLE_API_KEY', None)
    s = summary({'domain': 'tuialista.com'})
    print('sin conectar:', s['source'], '|', s['reason'])
    assert s['source'] == 'none' and s['visitors'] == 0 and s['top_pages'] == []
    print('OK: analytics (parse aggregate/breakdown + summary con fallback marcado)')
