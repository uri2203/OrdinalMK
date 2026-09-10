"""
OrdinalMK — Bucle de medición: Google Search Console.

Los "ojos" del motor. Lee impresiones, clics, CTR y posición por página y por
keyword desde Search Console, para que el sistema APRENDA qué funciona y se
corrija (empujar páginas de la página 2, detectar caídas, ver qué keyword pega).

Diseño con fallback elegante:
  - Si hay credenciales (GSC_CREDENTIALS o GOOGLE_APPLICATION_CREDENTIALS) y las
    librerías de Google instaladas → consulta real a la API.
  - Si no → devuelve {'available': False, 'reason': ...} y filas vacías, sin
    romper nada. El resto del motor sigue funcionando.

Para activarlo en producción:
  pip install google-api-python-client google-auth
  export GSC_CREDENTIALS=/ruta/service-account.json   (con acceso a la propiedad)
"""

import os
from datetime import date, timedelta

SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']


def _creds_path():
    return (os.environ.get('GSC_CREDENTIALS')
            or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'))


class SearchConsole:
    """Cliente de Search Console con fallback si no hay credenciales/librerías."""

    def __init__(self, site_url: str):
        self.site_url = site_url
        self._service = None
        self._reason = None

    @classmethod
    def from_config(cls, config: dict) -> "SearchConsole":
        domain = (config.get('domain') or '').replace(
            'https://', '').replace('http://', '').strip('/')
        # Propiedad de dominio en GSC (cubre http/https y subdominios)
        return cls(f"sc-domain:{domain}")

    def is_available(self) -> bool:
        if self._service:
            return True
        if not _creds_path():
            self._reason = 'sin credenciales (define GSC_CREDENTIALS)'
            return False
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError:
            self._reason = 'falta google-api-python-client / google-auth'
            return False
        try:
            creds = service_account.Credentials.from_service_account_file(
                _creds_path(), scopes=SCOPES)
            self._service = build('searchconsole', 'v1',
                                  credentials=creds, cache_discovery=False)
            return True
        except Exception as e:  # credenciales inválidas, sin acceso, etc.
            self._reason = f'error de credenciales: {e}'
            return False

    def query(self, days: int = 28, dimensions=('page', 'query'),
              row_limit: int = 1000) -> dict:
        """Devuelve {'available': bool, 'rows': [...], 'reason'?: str}."""
        if not self.is_available():
            return {'available': False, 'reason': self._reason, 'rows': []}
        end = date.today()
        start = end - timedelta(days=days)
        body = {
            'startDate': start.isoformat(),
            'endDate': end.isoformat(),
            'dimensions': list(dimensions),
            'rowLimit': row_limit,
        }
        try:
            resp = self._service.searchanalytics().query(
                siteUrl=self.site_url, body=body).execute()
        except Exception as e:
            return {'available': False, 'reason': f'error de consulta: {e}', 'rows': []}

        rows = []
        for r in resp.get('rows', []):
            row = dict(zip(dimensions, r.get('keys', [])))
            row.update(
                clicks=r.get('clicks', 0),
                impressions=r.get('impressions', 0),
                ctr=r.get('ctr', 0.0),
                position=r.get('position', 0.0),
            )
            rows.append(row)
        return {'available': True, 'rows': rows}


# ── Helpers puros (analizan filas, testeable sin API) ──────────────────

def pages_on_page_two(rows: list, low: float = 10.5, high: float = 20.5) -> list:
    """Páginas en la página 2 de Google (posición ~11-20): candidatas a empujar
    al top con un refresco. Ordenadas por impresiones (mayor oportunidad primero)."""
    out = [r for r in rows if low <= float(r.get('position', 0) or 0) <= high]
    out.sort(key=lambda r: r.get('impressions', 0), reverse=True)
    return out


def high_impressions_low_ctr(rows: list, min_impressions: int = 100,
                             max_ctr: float = 0.02) -> list:
    """Muchas impresiones pero pocos clics: el título/meta no atrae → reescribir."""
    out = [r for r in rows
           if r.get('impressions', 0) >= min_impressions
           and float(r.get('ctr', 0) or 0) <= max_ctr]
    out.sort(key=lambda r: r.get('impressions', 0), reverse=True)
    return out


if __name__ == "__main__":
    # 1) Fallback sin credenciales
    sc = SearchConsole.from_config({'domain': 'tuialista.com'})
    res = sc.query()
    print('site:', sc.site_url)
    print('disponible:', res['available'], '| motivo:', res.get('reason'))
    assert res['available'] is False and res['rows'] == []

    # 2) Helpers puros con filas de ejemplo
    sample = [
        {'page': '/a', 'query': 'facturación cfdi', 'impressions': 800, 'ctr': 0.005, 'position': 14.2},
        {'page': '/b', 'query': 'excel ia', 'impressions': 300, 'ctr': 0.09, 'position': 3.1},
        {'page': '/c', 'query': 'ia local', 'impressions': 500, 'ctr': 0.01, 'position': 18.9},
    ]
    p2 = pages_on_page_two(sample)
    lowctr = high_impressions_low_ctr(sample)
    print('página 2:', [r['page'] for r in p2])
    print('impresiones altas / ctr bajo:', [r['page'] for r in lowctr])
    assert [r['page'] for r in p2] == ['/a', '/c']  # 14.2 y 18.9, ordenadas por impresiones
    assert '/a' in [r['page'] for r in lowctr] and '/b' not in [r['page'] for r in lowctr]
    print('OK: fallback correcto + helpers de oportunidad (página 2, ctr bajo)')
