"""
OrdinalMK — Prospección: perfil de cliente ideal (ICP) por proyecto.

Cada proyecto define a QUIÉN quiere prospectar y con qué límites/remitente, en un
bloque `prospecting:` de projects.yaml. Es opt-in por proyecto (enabled: true).

Ejemplo:
    prospecting:
      enabled: true
      categories: ["despacho contable", "asesoría fiscal", "contador público"]
      locations: ["Ciudad de México", "Guadalajara", "Monterrey"]
      language: es
      max_discover_per_run: 20        # cuántos prospectos nuevos por corrida
      max_emails_per_day: 25          # tope de outreach/día (entregabilidad + legal)
      sender:
        from_name: "TuIAlista"
        from_email: "hola@mail.tuialista.com"   # DOMINIO DE ENVÍO DEDICADO
        reply_to: "hola@tuialista.com"
        company: "TuIAlista"
        address: "Ciudad de México, México"      # identidad del remitente (legal)
        unsubscribe: "Responde BAJA y no vuelvo a escribirte."
"""

DEFAULT_MAX_DISCOVER = 20
DEFAULT_MAX_EMAILS = 25


def _p(project_config: dict) -> dict:
    return (project_config or {}).get('prospecting', {}) or {}


def prospecting_enabled(project_config: dict) -> bool:
    return bool(_p(project_config).get('enabled', False))


def categories(project_config: dict) -> list:
    return list(_p(project_config).get('categories', []) or [])


def locations(project_config: dict) -> list:
    return list(_p(project_config).get('locations', []) or [])


def language(project_config: dict) -> str:
    return _p(project_config).get('language') or project_config.get('primary_language', 'es')


def max_discover_per_run(project_config: dict) -> int:
    try:
        return max(0, int(_p(project_config).get('max_discover_per_run', DEFAULT_MAX_DISCOVER)))
    except (TypeError, ValueError):
        return DEFAULT_MAX_DISCOVER


def max_emails_per_day(project_config: dict) -> int:
    try:
        return max(0, int(_p(project_config).get('max_emails_per_day', DEFAULT_MAX_EMAILS)))
    except (TypeError, ValueError):
        return DEFAULT_MAX_EMAILS


def sender(project_config: dict) -> dict:
    """Remitente B2B con defaults sensatos (identidad + opt-out obligatorios)."""
    s = dict(_p(project_config).get('sender', {}) or {})
    brand = project_config.get('name', 'Nosotros')
    domain = (project_config.get('domain') or '').replace('https://', '').replace('http://', '').strip('/')
    s.setdefault('from_name', brand)
    s.setdefault('from_email', f"hola@mail.{domain}" if domain else 'hola@example.com')
    s.setdefault('reply_to', f"hola@{domain}" if domain else '')
    s.setdefault('company', brand)
    s.setdefault('address', project_config.get('audience', {}).get('location', ''))
    s.setdefault('unsubscribe', 'Responde BAJA y no vuelvo a escribirte.')
    return s


def get_icp(project_config: dict) -> dict:
    return {
        'enabled': prospecting_enabled(project_config),
        'categories': categories(project_config),
        'locations': locations(project_config),
        'language': language(project_config),
        'max_discover_per_run': max_discover_per_run(project_config),
        'max_emails_per_day': max_emails_per_day(project_config),
        'sender': sender(project_config),
    }


if __name__ == "__main__":
    cfg = {
        'name': 'TuIAlista', 'domain': 'tuialista.com', 'primary_language': 'es',
        'audience': {'location': 'México'},
        'prospecting': {
            'enabled': True,
            'categories': ['despacho contable', 'asesoría fiscal'],
            'locations': ['Ciudad de México', 'Guadalajara'],
            'max_discover_per_run': 15, 'max_emails_per_day': 20,
            'sender': {'from_email': 'hola@mail.tuialista.com', 'address': 'CDMX, México'},
        },
    }
    icp = get_icp(cfg)
    print('ICP:', icp['categories'], '|', icp['locations'], '| max/día:', icp['max_emails_per_day'])
    print('sender:', icp['sender']['from_email'], '| opt-out:', icp['sender']['unsubscribe'])
    assert icp['enabled'] and len(icp['categories']) == 2
    assert icp['sender']['from_email'] == 'hola@mail.tuialista.com'
    assert icp['sender']['unsubscribe']  # opt-out siempre presente
    # sin bloque -> opt-in apagado
    assert prospecting_enabled({'name': 'X'}) is False
    # defaults de sender cuando faltan
    s = sender({'name': 'Yayika', 'domain': 'yayika.com'})
    assert s['from_email'] == 'hola@mail.yayika.com' and s['company'] == 'Yayika'
    print('OK: ICP por proyecto + sender con opt-out obligatorio + opt-in apagado por defecto')
