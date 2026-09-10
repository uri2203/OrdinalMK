"""
Config Loader — Reads projects.yaml and provides global configuration.
"""

import os
import yaml
from pathlib import Path

CONFIG_DIR = Path(__file__).parent
PROJECT_ROOT = CONFIG_DIR.parent
CONFIG_FILE = CONFIG_DIR / "projects.yaml"


def load_config(path: str = None) -> dict:
    """Load configuration from YAML file."""
    config_path = Path(path) if path else CONFIG_FILE
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Resolve env vars in config (basic substitution)
    _resolve_env_vars(config)
    
    return config


def _resolve_env_vars(obj):
    """Recursively resolve ${ENV_VAR} patterns in config values."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                env_key = value[2:-1]
                obj[key] = os.environ.get(env_key, value)
            elif isinstance(value, (dict, list)):
                _resolve_env_vars(value)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, str) and item.startswith('${') and item.endswith('}'):
                env_key = item[2:-1]
                obj[i] = os.environ.get(env_key, item)
            elif isinstance(item, (dict, list)):
                _resolve_env_vars(item)


def get_project_config(project_id: str) -> dict:
    """Get configuration for a specific project."""
    config = load_config()
    return config.get('projects', {}).get(project_id, {})


def get_engine_config() -> dict:
    """Get engine-level configuration."""
    config = load_config()
    return config.get('engine', {})


def get_all_project_ids() -> list:
    """Get list of all project IDs."""
    config = load_config()
    return list(config.get('projects', {}).keys())


def active_languages(project_config: dict) -> list:
    """Idiomas que el motor debe generar/publicar AHORA para un proyecto.

    Permite el lanzamiento por fases: un proyecto declara todos los idiomas que
    soporta en `languages:` y, opcionalmente, cuáles están activos hoy en
    `active_languages:`. El motor solo trabaja los activos; los demás se integran
    después cambiando esa lista (o quitándola para activar todos).

    Reglas:
      - Sin `active_languages` → todos los `languages` (compatibilidad hacia atrás).
      - Con `active_languages` → intersección con `languages`, respetando el orden
        de `languages`.
      - Si la intersección queda vacía → cae al `primary_language` (o al primero
        de `languages`) para no dejar el proyecto sin idioma.
      - El `primary_language` siempre se considera activo aunque se omita.
    """
    supported = project_config.get('languages') or ['es', 'en']
    primary = project_config.get('primary_language') or (supported[0] if supported else 'es')

    rollout = project_config.get('active_languages')
    if not rollout:
        return list(supported)

    rollout_set = set(rollout)
    rollout_set.add(primary)  # el primario nunca se desactiva
    active = [lang for lang in supported if lang in rollout_set]
    if not active:
        active = [primary] if primary in supported else list(supported[:1])
    return active
