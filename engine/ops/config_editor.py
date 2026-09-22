"""
OrdinalMK — Edición de configuración (overrides no destructivos).

Permite cambiar ajustes por proyecto (activar/pausar, prioridad, cuota, voz de
marca, prospección) DESDE EL PANEL, sin tocar el projects.yaml documentado.

Los cambios se guardan en config/overrides.json y el loader los fusiona sobre la
config base. Solo se permiten claves de una lista blanca (seguridad). Deep-merge
puro y testeable.
"""

import json
from pathlib import Path

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
OVERRIDES_FILE = CONFIG_DIR / "overrides.json"

# Lista blanca: solo estas rutas se pueden editar desde el panel.
ALLOWED = {
    'governance.enabled': bool,
    'governance.priority': int,
    'governance.articles_per_day': int,
    'governance.brand_voice': str,
    'prospecting.enabled': bool,
    'prospecting.max_emails_per_day': int,
    'prospecting.max_discover_per_run': int,
}


def load_overrides(path: Path = OVERRIDES_FILE) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _coerce(dotted: str, value):
    typ = ALLOWED[dotted]
    if typ is bool:
        if isinstance(value, str):
            return value.strip().lower() in ('1', 'true', 'on', 'sí', 'si', 'yes')
        return bool(value)
    if typ is int:
        return int(value)
    return str(value)


def set_override(project_id: str, dotted_key: str, value, path: Path = OVERRIDES_FILE) -> dict:
    """Fija un override validado. dotted_key ej: 'governance.priority'."""
    if dotted_key not in ALLOWED:
        raise ValueError(f"clave no permitida: {dotted_key}")
    val = _coerce(dotted_key, value)
    data = load_overrides(path)
    proj = data.setdefault(project_id, {})
    section, key = dotted_key.split('.', 1)
    proj.setdefault(section, {})[key] = val
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'project': project_id, 'set': dotted_key, 'value': val}


def deep_merge(base: dict, override: dict) -> dict:
    """Fusiona override sobre base (recursivo). No muta base."""
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def apply_overrides(projects: dict, path: Path = OVERRIDES_FILE) -> dict:
    """Devuelve los proyectos con overrides fusionados."""
    ov = load_overrides(path)
    if not ov:
        return projects
    out = {}
    for pid, cfg in (projects or {}).items():
        out[pid] = deep_merge(cfg, ov.get(pid, {}))
    return out


if __name__ == "__main__":
    import tempfile, shutil, os
    tmp = Path(tempfile.mkdtemp(prefix='cfg_'))
    p = tmp / 'overrides.json'
    try:
        # 1) deep_merge no muta base y fusiona anidado
        base = {'governance': {'enabled': True, 'priority': 90}, 'name': 'X'}
        merged = deep_merge(base, {'governance': {'priority': 40}})
        assert merged['governance'] == {'enabled': True, 'priority': 40}
        assert base['governance']['priority'] == 90, 'no debe mutar base'

        # 2) set_override valida lista blanca + coerciona tipos
        set_override('tuialista', 'governance.priority', '30', path=p)
        set_override('tuialista', 'prospecting.enabled', 'false', path=p)
        set_override('tuialista', 'governance.brand_voice', 'directo', path=p)
        ov = load_overrides(p)
        print('overrides:', ov['tuialista'])
        assert ov['tuialista']['governance']['priority'] == 30  # int
        assert ov['tuialista']['prospecting']['enabled'] is False  # bool desde 'false'
        assert ov['tuialista']['governance']['brand_voice'] == 'directo'

        # 3) clave no permitida -> error
        try:
            set_override('x', 'deploy.repo', 'hack', path=p); assert False
        except ValueError:
            pass

        # 4) apply_overrides fusiona sobre la config base
        projects = {'tuialista': {'name': 'TuIAlista',
                                  'governance': {'enabled': True, 'priority': 90},
                                  'prospecting': {'enabled': True, 'max_emails_per_day': 25}},
                    'yayika': {'name': 'Yayika'}}
        applied = apply_overrides(projects, path=p)
        print('tuialista prioridad:', applied['tuialista']['governance']['priority'])
        assert applied['tuialista']['governance']['priority'] == 30
        assert applied['tuialista']['prospecting']['enabled'] is False
        assert applied['tuialista']['prospecting']['max_emails_per_day'] == 25  # intacto
        assert applied['yayika'] == {'name': 'Yayika'}  # sin override, igual
        print('OK: config_editor (deep_merge inmutable + whitelist + coerción + apply)')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
