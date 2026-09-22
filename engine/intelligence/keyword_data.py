"""
OrdinalMK — Datos reales de keywords (expansión + volumen/dificultad).

La inteligencia base (keywords.py) clasifica intención por heurística pero NO sabe
volumen ni dificultad reales. Este módulo añade señales del mundo real:

  - Expansión GRATIS con Google Autocomplete (suggestqueries): a partir de una
    semilla saca decenas de long-tails que la gente realmente teclea, y variantes
    tipo "People Also Ask" (prefijos qué/cómo/cuánto/mejor...).
  - Volumen y dificultad: con DataForSEO si hay credenciales; si no, un ESTIMADOR
    heurístico (por intención + longitud + modificadores) para no quedar a ciegas.

Sin red / sin credenciales: usa el estimador y no rompe. Las funciones de parseo
y estimación son puras (testeables).

Env: DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD.
"""

import os
import sys

REPO_ROOT_ADDED = False
try:
    from engine.intelligence.keywords import classify_intent, INTENT_PRIORITY
except ImportError:
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from engine.intelligence.keywords import classify_intent, INTENT_PRIORITY

AUTOCOMPLETE_URL = "https://suggestqueries.google.com/complete/search"

# Prefijos "People Also Ask" por idioma para minar preguntas long-tail.
PAA_PREFIXES = {
    'es': ['qué es', 'cómo', 'cuánto cuesta', 'mejor', 'para qué sirve', 'precio de'],
    'en': ['what is', 'how to', 'how much', 'best', 'why use', 'price of'],
    'pt': ['o que é', 'como', 'quanto custa', 'melhor', 'para que serve', 'preço de'],
    'fr': ['qu est-ce que', 'comment', 'combien coûte', 'meilleur', 'à quoi sert', 'prix de'],
    'de': ['was ist', 'wie', 'was kostet', 'beste', 'wofür', 'preis von'],
}


def _parse_autocomplete(data) -> list:
    """El endpoint (client=firefox) devuelve [query, [sugerencias...], ...]."""
    try:
        if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
            return [s for s in data[1] if isinstance(s, str)]
    except Exception:
        pass
    return []


def autocomplete(seed: str, lang: str = 'es', country: str = 'mx') -> list:
    """Sugerencias reales de Google Autocomplete (gratis). Fallback: []."""
    try:
        import requests
        r = requests.get(AUTOCOMPLETE_URL,
                         params={'client': 'firefox', 'q': seed, 'hl': lang, 'gl': country},
                         timeout=10)
        return _parse_autocomplete(r.json())
    except Exception:
        return []


def expand(seeds: list, lang: str = 'es', country: str = 'mx',
           include_paa: bool = True) -> list:
    """Expande semillas con autocomplete + variantes PAA. Devuelve lista única."""
    found = []
    seen = set()

    def _add(items):
        for k in items:
            kl = k.lower().strip()
            if kl and kl not in seen:
                seen.add(kl)
                found.append(kl)

    for s in seeds:
        _add([s])
        _add(autocomplete(s, lang, country))
        if include_paa:
            for pre in PAA_PREFIXES.get(lang, PAA_PREFIXES['es']):
                _add(autocomplete(f"{pre} {s}", lang, country))
    return found


def estimate_metrics(keyword: str) -> dict:
    """Estimador heurístico (puro) cuando no hay API de keywords.
    volume: proxy relativo (más específico = menos volumen).
    difficulty: 0-100 (transaccional/comercial compiten más)."""
    k = (keyword or '').lower().strip()
    words = [w for w in k.split() if w]
    n = len(words)
    intent = classify_intent(k)
    # volumen proxy: cabezas cortas ~ más búsquedas; colas largas ~ menos
    base_vol = {1: 4000, 2: 1800, 3: 700, 4: 300, 5: 140}.get(min(n, 5), 90)
    # dificultad: sube con intención comercial/transaccional y baja con longitud
    intent_diff = {'transactional': 55, 'commercial': 60, 'informational': 35}[intent]
    difficulty = max(5, min(95, intent_diff + (3 - n) * 6))
    # oportunidad = prioridad de intención alta + baja dificultad + algo de volumen
    opportunity = round(INTENT_PRIORITY[intent] * 20 + (100 - difficulty) * 0.5
                        + min(base_vol, 2000) / 100, 1)
    return {'keyword': k, 'intent': intent, 'volume_est': base_vol,
            'difficulty': difficulty, 'opportunity': opportunity, 'source': 'estimate'}


def _dataforseo_metrics(keywords: list, lang: str, country: str) -> dict:
    """Volumen/dificultad reales vía DataForSEO. Devuelve {kw: {...}} o {}."""
    login = os.environ.get('DATAFORSEO_LOGIN')
    pw = os.environ.get('DATAFORSEO_PASSWORD')
    if not login or not pw:
        return {}
    try:
        import requests
        url = "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live"
        payload = [{'keywords': keywords, 'language_code': lang, 'location_name': country}]
        r = requests.post(url, auth=(login, pw), json=payload, timeout=30)
        data = r.json()
        out = {}
        for task in data.get('tasks', []):
            for item in (task.get('result') or []):
                kw = (item.get('keyword') or '').lower()
                out[kw] = {'volume_est': item.get('search_volume') or 0,
                           'difficulty': item.get('competition_index') or 0,
                           'source': 'dataforseo'}
        return out
    except Exception:
        return {}


def metrics(keywords: list, lang: str = 'es', country: str = 'Mexico') -> list:
    """Métricas por keyword: reales (DataForSEO) o estimadas. Ordena por oportunidad."""
    real = _dataforseo_metrics(keywords, lang, country)
    out = []
    for k in keywords:
        kl = k.lower().strip()
        m = estimate_metrics(kl)
        if kl in real:
            m.update(real[kl])
            m.setdefault('opportunity', 0)
        out.append(m)
    out.sort(key=lambda x: x.get('opportunity', 0), reverse=True)
    return out


def research(seeds: list, lang: str = 'es', country: str = 'mx',
             expand_online: bool = True) -> list:
    """Pipeline: expandir semillas (online opcional) + métricas, priorizado."""
    kws = expand(seeds, lang, country) if expand_online else [s.lower() for s in seeds]
    if not kws:
        kws = [s.lower() for s in seeds]
    return metrics(kws, lang)


if __name__ == "__main__":
    # 1) parseo de autocomplete (puro, sin red)
    sample = ["software facturacion", ["software facturacion cfdi",
              "software facturacion gratis", "software facturacion sat"]]
    sug = _parse_autocomplete(sample)
    print('autocomplete parse:', sug)
    assert len(sug) == 3 and 'software facturacion cfdi' in sug
    assert _parse_autocomplete({'bad': 1}) == []

    # 2) estimador heurístico (puro)
    head = estimate_metrics('facturación')
    tail = estimate_metrics('software de facturación cfdi para despachos')
    print('cabeza vol:', head['volume_est'], '| cola vol:', tail['volume_est'])
    assert head['volume_est'] > tail['volume_est'], 'cola larga = menos volumen'
    trans = estimate_metrics('comprar software de facturación')
    info = estimate_metrics('qué es la facturación electrónica')
    assert trans['intent'] == 'transactional' and info['intent'] == 'informational'
    assert 5 <= trans['difficulty'] <= 95

    # 3) metrics ordena por oportunidad y no rompe sin API
    os.environ.pop('DATAFORSEO_LOGIN', None)
    os.environ.pop('DATAFORSEO_PASSWORD', None)
    ranked = metrics(['software de facturación cfdi', 'qué es cfdi', 'ia local'])
    print('ranking oportunidad:', [(m['keyword'][:24], m['opportunity']) for m in ranked])
    assert ranked == sorted(ranked, key=lambda x: x['opportunity'], reverse=True)
    assert all(m['source'] == 'estimate' for m in ranked), 'sin API debe estimar'

    # 4) research offline (expand_online=False no llama a la red)
    r = research(['facturación', 'excel'], expand_online=False)
    assert len(r) == 2
    print('OK: keyword_data (autocomplete parse + estimador + metrics + research offline)')
