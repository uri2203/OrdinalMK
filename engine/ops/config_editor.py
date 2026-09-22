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
CUSTOM_FILE = CONFIG_DIR / "custom_projects.json"

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


# ───────────────── gestor de proyectos (alta/edición/borrado) ─────────────────
def _slug(text: str) -> str:
    import re
    t = (text or '').lower().strip()
    for a, b in {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n'}.items():
        t = t.replace(a, b)
    return re.sub(r'[^a-z0-9]+', '-', t).strip('-')


def _csv(val) -> list:
    if isinstance(val, list):
        return [str(v).strip() for v in val if str(v).strip()]
    return [s.strip() for s in str(val or '').split(',') if s.strip()]


def build_project(form: dict) -> dict:
    """Normaliza los campos del formulario en un dict de proyecto con defaults.
    Requiere id, name, domain. Puro y testeable."""
    pid = _slug(form.get('id') or form.get('name') or '')
    if not pid:
        raise ValueError('falta id/nombre del proyecto')
    name = (form.get('name') or '').strip()
    domain = (form.get('domain') or '').replace('https://', '').replace('http://', '').strip('/')
    if not name or not domain:
        raise ValueError('nombre y dominio son obligatorios')
    primary = (form.get('primary_language') or 'es').strip()
    langs = _csv(form.get('languages')) or [primary]
    if primary not in langs:
        langs.insert(0, primary)
    proj = {
        'name': name,
        'domain': domain,
        'github_repo': (form.get('github_repo') or '').strip(),
        'concept': (form.get('concept') or '').strip(),
        'primary_language': primary,
        'languages': langs,
        'theme': {'primary': (form.get('theme_primary') or '#6d5efc').strip()},
        'audience': {'location': (form.get('audience_location') or '').strip()},
        'governance': {
            'enabled': str(form.get('enabled', 'true')).lower() in ('1', 'true', 'on', 'sí', 'si', 'yes'),
            'priority': int(form.get('priority') or 50),
            'articles_per_day': int(form.get('articles_per_day') or 2),
            'brand_voice': (form.get('brand_voice') or '').strip(),
        },
    }
    cats = _csv(form.get('prospecting_categories'))
    locs = _csv(form.get('prospecting_locations'))
    prosp_on = str(form.get('prospecting_enabled', '')).lower() in ('1', 'true', 'on', 'sí', 'si', 'yes')
    if prosp_on or cats or locs:
        proj['prospecting'] = {
            'enabled': prosp_on,
            'categories': cats,
            'locations': locs,
            'max_discover_per_run': int(form.get('max_discover_per_run') or 20),
            'max_emails_per_day': int(form.get('max_emails_per_day') or 25),
            'sender': {'from_email': f"hola@mail.{domain}", 'company': name,
                       'address': (form.get('audience_location') or '').strip(),
                       'unsubscribe': 'Responde BAJA y no vuelvo a escribirte.'},
        }
    return {'id': pid, 'config': proj}


def load_custom(path: Path = CUSTOM_FILE) -> dict:
    if not path.exists():
        return {'projects': {}, 'hidden': []}
    try:
        d = json.loads(path.read_text(encoding='utf-8'))
        d.setdefault('projects', {})
        d.setdefault('hidden', [])
        return d
    except Exception:
        return {'projects': {}, 'hidden': []}


def _save_custom(data: dict, path: Path = CUSTOM_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def save_project(pid: str, config: dict, path: Path = CUSTOM_FILE) -> dict:
    """Alta o edición: guarda el proyecto en el store custom (add/replace)."""
    data = load_custom(path)
    data['projects'][pid] = config
    if pid in data.get('hidden', []):
        data['hidden'].remove(pid)  # re-activar si estaba oculto
    _save_custom(data, path)
    return {'saved': pid}


def delete_project(pid: str, base_projects: dict = None, path: Path = CUSTOM_FILE) -> dict:
    """Elimina un proyecto: si es custom lo borra; si viene del yaml, lo oculta."""
    data = load_custom(path)
    if pid in data['projects']:
        data['projects'].pop(pid)
        _save_custom(data, path)
        return {'deleted': pid, 'mode': 'custom'}
    if pid not in data['hidden']:
        data['hidden'].append(pid)
    _save_custom(data, path)
    return {'deleted': pid, 'mode': 'hidden'}


def apply_all(base_projects: dict, ov_path: Path = OVERRIDES_FILE,
              custom_path: Path = CUSTOM_FILE) -> dict:
    """Fusión final: base(yaml) + custom(add/edit) - hidden + overrides(campos)."""
    result = dict(base_projects or {})
    cust = load_custom(custom_path)
    for pid, cfg in cust.get('projects', {}).items():
        result[pid] = deep_merge(result.get(pid, {}), cfg) if pid in result else cfg
    for pid in cust.get('hidden', []):
        result.pop(pid, None)
    return apply_overrides(result, ov_path)


if __name__ == "__main__":
    import tempfile, shutil, os
    tmp = Path(tempfile.mkdtemp(prefix='cfg_'))
    p = tmp / 'overrides.json'
    cp = tmp / 'custom_projects.json'
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

        # 5) build_project normaliza + defaults
        built = build_project({'name': 'Mi Tienda', 'domain': 'https://mitienda.com/',
                               'primary_language': 'es', 'languages': 'es, en',
                               'concept': 'venta online', 'priority': '70',
                               'prospecting_enabled': 'true',
                               'prospecting_categories': 'boutique, ropa',
                               'prospecting_locations': 'CDMX'})
        print('nuevo proyecto id:', built['id'])
        assert built['id'] == 'mi-tienda'
        assert built['config']['domain'] == 'mitienda.com'  # limpia http
        assert built['config']['languages'] == ['es', 'en']
        assert built['config']['governance']['priority'] == 70
        assert built['config']['prospecting']['categories'] == ['boutique', 'ropa']
        assert built['config']['prospecting']['sender']['from_email'] == 'hola@mail.mitienda.com'
        # falta dominio -> error
        try:
            build_project({'name': 'X'}); assert False
        except ValueError:
            pass

        # 6) save + apply_all agrega el proyecto custom
        save_project(built['id'], built['config'], path=cp)
        base = {'tuialista': {'name': 'TuIAlista', 'governance': {'priority': 90}}}
        merged = apply_all(base, ov_path=tmp / 'none.json', custom_path=cp)
        assert 'mi-tienda' in merged and merged['mi-tienda']['name'] == 'Mi Tienda'
        assert 'tuialista' in merged

        # 7) delete: custom se borra; yaml se oculta
        d1 = delete_project('mi-tienda', path=cp)
        assert d1['mode'] == 'custom'
        assert 'mi-tienda' not in apply_all(base, ov_path=tmp / 'none.json', custom_path=cp)
        d2 = delete_project('tuialista', path=cp)
        assert d2['mode'] == 'hidden'
        assert 'tuialista' not in apply_all(base, ov_path=tmp / 'none.json', custom_path=cp)
        print('gestor: alta/edición (custom) + borrado (custom/oculto) OK')
        print('OK: config_editor (deep_merge + whitelist + coerción + apply + gestor proyectos)')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
