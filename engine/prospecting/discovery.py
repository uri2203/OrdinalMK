"""
OrdinalMK — Prospección: descubrimiento de negocios (Google Places).

Busca negocios que encajan con el ICP (giro + zona) usando la Places API (v1) y
devuelve nombre, sitio web, dirección y teléfono. Con estos datos, el paso de
enriquecimiento saca el correo de negocio.

Fallback elegante: sin GOOGLE_PLACES_API_KEY → available=False y lista vacía
(no rompe). Activación: crear API key de Google (Places API) con facturación.
"""

import os

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ("places.displayName,places.websiteUri,places.formattedAddress,"
              "places.nationalPhoneNumber,places.id")


def _key(api_key: str = None) -> str:
    return (api_key or os.environ.get('GOOGLE_PLACES_API_KEY')
            or os.environ.get('GOOGLE_MAPS_API_KEY') or '')


def _parse_places(data: dict, query: str) -> list:
    """Convierte la respuesta de Places en prospectos (función pura, testeable)."""
    out = []
    for p in (data or {}).get('places', []):
        out.append({
            'name': (p.get('displayName') or {}).get('text', ''),
            'website': p.get('websiteUri', ''),
            'address': p.get('formattedAddress', ''),
            'phone': p.get('nationalPhoneNumber', ''),
            'place_id': p.get('id', ''),
            'query': query,
        })
    return out


def discover(categories: list, locations: list, max_results: int = 20,
             language: str = 'es', api_key: str = None) -> dict:
    """Descubre prospectos combinando cada giro con cada zona."""
    key = _key(api_key)
    if not key:
        return {'available': False, 'reason': 'sin GOOGLE_PLACES_API_KEY', 'prospects': []}

    import requests
    seen, out = set(), []
    for loc in locations:
        for cat in categories:
            if len(out) >= max_results:
                break
            query = f"{cat} en {loc}"
            try:
                resp = requests.post(
                    PLACES_URL,
                    headers={'Content-Type': 'application/json',
                             'X-Goog-Api-Key': key, 'X-Goog-FieldMask': FIELD_MASK},
                    json={'textQuery': query, 'languageCode': language,
                          'maxResultCount': min(20, max_results)},
                    timeout=20)
                data = resp.json()
            except Exception:
                continue
            for pr in _parse_places(data, query):
                pid = pr.get('place_id') or pr.get('website') or pr.get('name')
                if pid in seen:
                    continue
                seen.add(pid)
                out.append(pr)
                if len(out) >= max_results:
                    break
    return {'available': True, 'prospects': out[:max_results]}


if __name__ == "__main__":
    # 1) Fallback sin key
    r = discover(['despacho contable'], ['CDMX'], api_key=None)
    print('sin key -> disponible:', r['available'], '| motivo:', r.get('reason'))
    assert r['available'] is False and r['prospects'] == []

    # 2) Parseo de una respuesta de Places (simulada)
    sample = {'places': [
        {'id': 'p1', 'displayName': {'text': 'Despacho López y Asociados'},
         'websiteUri': 'https://despacholopez.mx', 'formattedAddress': 'CDMX',
         'nationalPhoneNumber': '55 1234 5678'},
        {'id': 'p2', 'displayName': {'text': 'Contadores GDL'},
         'websiteUri': 'https://contadoresgdl.com', 'formattedAddress': 'Guadalajara'},
    ]}
    ps = _parse_places(sample, 'despacho contable en CDMX')
    print('parseados:', [(p['name'], p['website']) for p in ps])
    assert len(ps) == 2 and ps[0]['website'] == 'https://despacholopez.mx'
    assert ps[0]['query'] == 'despacho contable en CDMX'
    print('OK: fallback sin key + parseo de resultados de Places')
