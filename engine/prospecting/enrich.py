"""
OrdinalMK — Prospección: enriquecimiento de correo de negocio.

Dado el sitio del negocio, extrae el correo de contacto PÚBLICO de su propia web
(home + página de contacto), prioriza correos de la empresa y descarta basura
(noreply, correos de plantillas/imágenes, dominios de terceros). Es B2B: se usa
el correo de negocio que la empresa publica, no correos personales.

Fallback: sin web o si falla la descarga → email None (el prospecto queda sin
correo, no se le contacta).
"""

import re
from urllib.parse import urlparse

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')

# Dominios/patrones basura que NO son correos de negocio reales
JUNK_DOMAINS = ('example.com', 'sentry.io', 'wixpress.com', 'wix.com', 'godaddy.com',
                'squarespace.com', 'schema.org', 'w3.org', 'googleapis.com')
JUNK_LOCAL = ('noreply', 'no-reply', 'no_reply', 'donotreply')
IMG_EXT = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg')
# Prioridad de buzones de negocio
ROLE_PRIORITY = ['contacto', 'contact', 'info', 'hola', 'hello', 'ventas', 'sales',
                 'admin', 'administracion', 'atencion']


def extract_emails(html: str) -> list:
    """Extrae correos válidos de un HTML, filtrando basura. (puro)"""
    found = []
    for m in EMAIL_RE.findall(html or ''):
        e = m.strip().lower()
        if any(e.endswith(ext) for ext in IMG_EXT):
            continue
        dom = e.split('@')[-1]
        if any(dom == j or dom.endswith('.' + j) for j in JUNK_DOMAINS):
            continue
        if e not in found:
            found.append(e)
    return found


def _domain_of(website: str) -> str:
    host = urlparse(website if '://' in (website or '') else 'http://' + (website or '')).netloc.lower()
    return host[4:] if host.startswith('www.') else host


def pick_business_email(emails: list, website: str = '') -> str:
    """Elige el mejor correo de negocio: prioriza el del dominio de la empresa y
    los buzones de contacto; descarta noreply. (puro)"""
    cands = [e for e in emails if not any(j in e.split('@')[0] for j in JUNK_LOCAL)]
    if not cands:
        return ''
    site_dom = _domain_of(website)
    same = [e for e in cands if site_dom and e.split('@')[-1] == site_dom]
    pool = same or cands

    def rank(e):
        local = e.split('@')[0]
        for i, role in enumerate(ROLE_PRIORITY):
            if local.startswith(role):
                return i
        return len(ROLE_PRIORITY)
    pool.sort(key=rank)
    return pool[0]


def enrich(prospect: dict, timeout: int = 15) -> dict:
    """Descarga la web del prospecto y le añade 'email' + 'email_status'."""
    website = prospect.get('website', '')
    result = dict(prospect)
    if not website:
        result['email'] = ''
        result['email_status'] = 'sin_web'
        return result
    try:
        import requests
        emails = []
        for path in ('', '/contacto', '/contact', '/contacto/'):
            url = website.rstrip('/') + path
            try:
                r = requests.get(url, timeout=timeout,
                                 headers={'User-Agent': 'Mozilla/5.0 OrdinalMK-bot'})
                if r.status_code == 200:
                    emails += extract_emails(r.text)
            except Exception:
                continue
            if emails:
                break
        email = pick_business_email(list(dict.fromkeys(emails)), website)
        result['email'] = email
        result['email_status'] = 'ok' if email else 'no_encontrado'
    except Exception as e:
        result['email'] = ''
        result['email_status'] = f'error: {e}'
    return result


if __name__ == "__main__":
    html = """
    <html><body>
      Escríbenos a <a href="mailto:contacto@despacholopez.mx">contacto@despacholopez.mx</a>
      o a ventas@despacholopez.mx. Soporte: noreply@despacholopez.mx.
      Hecho con amor por hola@wixpress.com — logo.png@2x
    </body></html>"""
    emails = extract_emails(html)
    print('extraídos:', emails)
    assert 'contacto@despacholopez.mx' in emails
    assert 'hola@wixpress.com' not in emails  # dominio basura filtrado

    best = pick_business_email(emails, 'https://despacholopez.mx')
    print('elegido:', best)
    assert best == 'contacto@despacholopez.mx'  # buzón de contacto del dominio propio
    # noreply descartado aunque sea del dominio
    assert pick_business_email(['noreply@x.com', 'info@x.com'], 'https://x.com') == 'info@x.com'
    # sin web -> sin correo
    e = enrich({'name': 'N', 'website': ''})
    assert e['email'] == '' and e['email_status'] == 'sin_web'
    print('OK: extracción filtra basura + elige buzón de negocio + descarta noreply')
