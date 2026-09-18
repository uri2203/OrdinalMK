"""
OrdinalMK — Gobierno multi-proyecto.

Reglas para que el motor opere SOLO sobre todos los proyectos sin pisarse:
  - `enabled`: si el proyecto está activo en la operación diaria.
  - `priority`: orden de atención (mayor = primero). Reparte el esfuerzo.
  - `articles_per_day`: cuota de artículos por corrida (evita sobre-producir /
    controla costo de IA). Cae a engine.limits.articles_per_day si no se define.
  - `brand_voice`: nota de voz de marca (se inyecta al redactar).

Config (opcional) por proyecto en projects.yaml:
    governance:
      enabled: true
      priority: 90
      articles_per_day: 2
      brand_voice: "cercano, claro, sin tecnicismos"
"""

DEFAULT_PRIORITY = 50
DEFAULT_ARTICLES_PER_DAY = 2


def _gov(project_config: dict) -> dict:
    return (project_config or {}).get('governance', {}) or {}


def project_enabled(project_config: dict) -> bool:
    return bool(_gov(project_config).get('enabled', True))


def project_priority(project_config: dict) -> int:
    try:
        return int(_gov(project_config).get('priority', DEFAULT_PRIORITY))
    except (TypeError, ValueError):
        return DEFAULT_PRIORITY


def articles_per_day(project_config: dict, engine_config: dict = None) -> int:
    g = _gov(project_config).get('articles_per_day')
    if g is not None:
        try:
            return max(0, int(g))
        except (TypeError, ValueError):
            pass
    limits = (engine_config or {}).get('limits', {}) or {}
    try:
        return max(0, int(limits.get('articles_per_day', DEFAULT_ARTICLES_PER_DAY)))
    except (TypeError, ValueError):
        return DEFAULT_ARTICLES_PER_DAY


def brand_voice(project_config: dict) -> str:
    return _gov(project_config).get('brand_voice', '') or ''


def active_projects_ordered(projects: dict) -> list:
    """Devuelve [(project_id, config), ...] solo de los habilitados, ordenados
    por prioridad descendente (y por id para desempatar de forma estable)."""
    items = [(pid, cfg) for pid, cfg in (projects or {}).items()
             if project_enabled(cfg)]
    items.sort(key=lambda x: (-project_priority(x[1]), x[0]))
    return items


if __name__ == "__main__":
    projects = {
        'yayika': {'governance': {'enabled': True, 'priority': 30}},
        'tuialista': {'governance': {'enabled': True, 'priority': 90, 'articles_per_day': 4}},
        'lastmile': {'governance': {'enabled': False}},
        'sinconfig': {},  # sin bloque governance -> habilitado, prioridad 50
    }
    engine_cfg = {'limits': {'articles_per_day': 2}}

    order = [pid for pid, _ in active_projects_ordered(projects)]
    print('orden activos:', order)
    assert order == ['tuialista', 'sinconfig', 'yayika'], order
    assert 'lastmile' not in order, 'lastmile está deshabilitado'

    assert articles_per_day(projects['tuialista'], engine_cfg) == 4  # override
    assert articles_per_day(projects['sinconfig'], engine_cfg) == 2  # cae al engine
    assert project_priority(projects['sinconfig']) == 50
    assert project_enabled(projects['sinconfig']) is True
    print('cuota tuialista:', articles_per_day(projects['tuialista'], engine_cfg))
    print('OK: gobierno (orden por prioridad, deshabilitados fuera, cuotas)')
