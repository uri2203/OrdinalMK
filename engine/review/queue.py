"""
OrdinalMK — Flujo de revisión humana del contenido apartado (_held).

La puerta de calidad aparta el contenido fiscal/legal sensible para que un humano
lo verifique antes de publicarlo. Esta pieza es la bandeja de aprobación:
  - list_held(): qué hay pendiente, con motivos/flags.
  - approve(): un humano lo verificó → se publica (marca revisado) y sale de _held.
  - reject(): no pasa → se archiva en _rejected/ (queda el registro).

Funciones sobre archivos (rutas override) → testeable.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine.publishers.content_publisher import ContentPublisher, CONTENT_ROOT


def _held_dir(project_id: str, content_root: Path) -> Path:
    return content_root / project_id / "_held"


def list_held(project_id: str, content_root: Path = CONTENT_ROOT) -> list:
    d = _held_dir(project_id, content_root)
    items = []
    if not d.exists():
        return items
    for f in sorted(d.glob('*.json')):
        try:
            a = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        gate = a.get('gate', {})
        items.append({
            'slug': a.get('slug', f.stem),
            'language': a.get('language', '?'),
            'title': a.get('title', ''),
            'decision': gate.get('decision', '?'),
            'flags': gate.get('flags', []),
            'reasons': gate.get('reasons', []),
        })
    return items


def approve(project_id: str, slug: str, config: dict,
            content_root: Path = CONTENT_ROOT, reviewer: str = 'humano') -> dict:
    """Un humano verificó el contenido → publicarlo y sacarlo de _held."""
    f = _held_dir(project_id, content_root) / f"{slug}.json"
    if not f.exists():
        return {'error': f'no encontrado en _held: {slug}'}
    article = json.loads(f.read_text(encoding='utf-8'))
    article.pop('gate', None)
    article['reviewed_by'] = reviewer
    article['reviewed_at'] = datetime.now(timezone.utc).isoformat()
    article['status'] = 'draft'

    publisher = ContentPublisher(project_id, config)
    res = publisher.publish_article(article)
    f.unlink()
    return {'approved': slug, 'published': res.get('slug'), 'html': res.get('html_path')}


def reject(project_id: str, slug: str, content_root: Path = CONTENT_ROOT,
           reason: str = '') -> dict:
    """No pasa la revisión → archivar en _rejected/ (queda registro)."""
    f = _held_dir(project_id, content_root) / f"{slug}.json"
    if not f.exists():
        return {'error': f'no encontrado en _held: {slug}'}
    rej_dir = content_root / project_id / "_rejected"
    rej_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(f.read_text(encoding='utf-8'))
    data['rejected_at'] = datetime.now(timezone.utc).isoformat()
    data['reject_reason'] = reason
    (rej_dir / f"{slug}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    f.unlink()
    return {'rejected': slug}


if __name__ == "__main__":
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp(prefix='review_'))
    try:
        cr = tmp / "content"
        pid = 'demo'
        held = cr / pid / '_held'
        held.mkdir(parents=True)
        for slug, flags in [('fiscal-cfdi-1', ['CFDI', 'SAT']), ('fiscal-iva-2', ['IVA'])]:
            (held / f"{slug}.json").write_text(json.dumps({
                'slug': slug, 'language': 'es', 'title': slug.replace('-', ' '),
                'body': '# t\n## a\n texto\n## Conclusión', 'keywords': ['x'],
                'gate': {'decision': 'hold_review', 'flags': flags, 'reasons': []},
            }, ensure_ascii=False), encoding='utf-8')

        items = list_held(pid, content_root=cr)
        print('en revisión:', [(i['slug'], i['flags']) for i in items])
        assert len(items) == 2 and items[0]['decision'] == 'hold_review'

        r = reject(pid, 'fiscal-iva-2', content_root=cr, reason='dato de IVA incorrecto')
        print('rechazado:', r)
        assert r.get('rejected') == 'fiscal-iva-2'
        assert not (held / 'fiscal-iva-2.json').exists()
        assert (cr / pid / '_rejected' / 'fiscal-iva-2.json').exists()
        assert len(list_held(pid, content_root=cr)) == 1
        print('OK: listar + rechazar (archiva en _rejected, sale de _held)')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
