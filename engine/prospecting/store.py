"""
OrdinalMK — Prospección: almacén de prospectos por proyecto.

Guarda los prospectos de CADA proyecto por separado (segmentado), deduplica para
no repetir negocios, y lleva su estado en el embudo:

    nuevo -> aprobado -> contactado -> respondio -> convertido   (y: descartado)

Almacén: reports/prospects/<project>.json (lista). En producción esto puede ser
una tabla en tu base; aquí es un archivo simple, suficiente y auditable.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
PROSPECTS_DIR = REPO_ROOT / "reports" / "prospects"

STATUSES = ['nuevo', 'aprobado', 'contactado', 'respondio', 'convertido', 'descartado']


def _path(project_id: str, base: Path) -> Path:
    return base / f"{project_id}.json"


def _key(prospect: dict) -> str:
    """Clave de dedup: correo si hay; si no, dominio del sitio; si no, nombre."""
    email = (prospect.get('email') or '').strip().lower()
    if email:
        return email
    web = (prospect.get('website') or '').lower()
    web = web.replace('https://', '').replace('http://', '').replace('www.', '').strip('/')
    return web.split('/')[0] if web else (prospect.get('name', '') or '').strip().lower()


def load(project_id: str, base: Path = PROSPECTS_DIR) -> list:
    f = _path(project_id, base)
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding='utf-8'))
    except Exception:
        return []


def _save(project_id: str, rows: list, base: Path) -> None:
    base.mkdir(parents=True, exist_ok=True)
    _path(project_id, base).write_text(
        json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def add_prospects(project_id: str, prospects: list, base: Path = PROSPECTS_DIR) -> dict:
    """Añade prospectos nuevos (dedup por clave). No pisa los existentes."""
    rows = load(project_id, base)
    existing = {_key(r) for r in rows}
    added = 0
    for p in prospects:
        k = _key(p)
        if not k or k in existing:
            continue
        existing.add(k)
        row = dict(p)
        row['key'] = k
        row['status'] = 'nuevo'
        row['added_at'] = datetime.now(timezone.utc).isoformat()
        rows.append(row)
        added += 1
    _save(project_id, rows, base)
    return {'project': project_id, 'added': added, 'total': len(rows)}


def by_status(project_id: str, status: str, base: Path = PROSPECTS_DIR) -> list:
    return [r for r in load(project_id, base) if r.get('status') == status]


def update_status(project_id: str, key: str, status: str, base: Path = PROSPECTS_DIR) -> bool:
    if status not in STATUSES:
        raise ValueError(f"estado inválido: {status}")
    rows = load(project_id, base)
    hit = False
    for r in rows:
        if r.get('key') == key or (r.get('email') or '').lower() == key.lower():
            r['status'] = status
            r['status_at'] = datetime.now(timezone.utc).isoformat()
            hit = True
    if hit:
        _save(project_id, rows, base)
    return hit


def counts(project_id: str, base: Path = PROSPECTS_DIR) -> dict:
    rows = load(project_id, base)
    out = {s: 0 for s in STATUSES}
    for r in rows:
        out[r.get('status', 'nuevo')] = out.get(r.get('status', 'nuevo'), 0) + 1
    out['total'] = len(rows)
    return out


if __name__ == "__main__":
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp(prefix='prospects_'))
    try:
        pid = 'demo'
        p1 = [
            {'name': 'Despacho A', 'website': 'https://despachoa.mx', 'email': 'contacto@despachoa.mx'},
            {'name': 'Despacho B', 'website': 'https://despachob.mx', 'email': 'info@despachob.mx'},
        ]
        r = add_prospects(pid, p1, base=tmp)
        print('agregados:', r)
        assert r['added'] == 2
        # dedup: reintentar A (mismo correo) no lo duplica
        r2 = add_prospects(pid, [{'name': 'Despacho A dup', 'email': 'contacto@despachoa.mx'}], base=tmp)
        assert r2['added'] == 0, 'no debe duplicar por correo'

        assert update_status(pid, 'contacto@despachoa.mx', 'aprobado', base=tmp)
        aprobados = by_status(pid, 'aprobado', base=tmp)
        print('aprobados:', [a['name'] for a in aprobados])
        assert len(aprobados) == 1 and aprobados[0]['name'] == 'Despacho A'
        c = counts(pid, base=tmp)
        print('conteos:', {k: v for k, v in c.items() if v})
        assert c['total'] == 2 and c['aprobado'] == 1 and c['nuevo'] == 1
        print('OK: guarda por proyecto + dedup + estado + conteos')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
