"""
OrdinalMK — Publicador/programador de redes sociales.

Toma los snippets ya generados (published/<p>/<lang>/_social/<slug>.json del
repurposing) y los publica en cada red:
  - Con credenciales de la red (env por plataforma) → publica vía su API.
  - Sin credenciales → fallback: encola a archivo (para revisar/programar).

Deduplica con un registro de publicados (slug:plataforma), así una corrida
diaria no re-publica lo mismo. Conectar las APIs reales es rellenar _post_api().
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
PUBLISHED_ROOT = REPO_ROOT / "published"
QUEUE_DIR = REPO_ROOT / "reports" / "social_queue"

# Canales a publicar y la env var de credencial que los activaría
CHANNELS = {
    'x': ('x', 'X_ACCESS_TOKEN'),
    'linkedin': ('linkedin', 'LINKEDIN_ACCESS_TOKEN'),
    'facebook_instagram': ('meta', 'META_ACCESS_TOKEN'),
}


def _load_posted(queue_dir: Path) -> set:
    f = queue_dir / 'posted.json'
    if f.exists():
        try:
            return set(json.loads(f.read_text(encoding='utf-8')))
        except Exception:
            return set()
    return set()


def _save_posted(queue_dir: Path, posted: set) -> None:
    queue_dir.mkdir(parents=True, exist_ok=True)
    (queue_dir / 'posted.json').write_text(
        json.dumps(sorted(posted), ensure_ascii=False), encoding='utf-8')


def _post_api(channel: str, content: str, token: str) -> dict:
    """Publicación real por API (a completar por plataforma)."""
    # Estructura lista; cada red se conecta aquí con su endpoint oficial.
    return {'posted': False, 'reason': f'API de {channel} no implementada aún'}


def _post_or_queue(channel: str, env_var: str, content: str, meta: dict,
                   queue_dir: Path) -> dict:
    token = os.environ.get(env_var, '')
    if token:
        res = _post_api(channel, content, token)
        if res.get('posted'):
            return {'posted': True}
        # si la API falla, cae a cola para no perder el post
    queue_dir.mkdir(parents=True, exist_ok=True)
    rec = {'channel': channel, 'content': content,
           'queued_at': datetime.now(timezone.utc).isoformat(), **meta}
    with open(queue_dir / 'queue.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {'posted': False, 'queued': True}


def publish_all(project_id: str, config: dict = None,
                published_root: Path = PUBLISHED_ROOT,
                queue_dir: Path = QUEUE_DIR) -> dict:
    """Publica/encola los snippets de redes no publicados aún de un proyecto."""
    base = published_root / project_id
    posted = _load_posted(queue_dir)
    n_posted = n_queued = 0

    for social_json in sorted(base.glob('*/_social/*.json')):
        try:
            data = json.loads(social_json.read_text(encoding='utf-8'))
        except Exception:
            continue
        lang = social_json.parent.parent.name
        slug = social_json.stem
        url = data.get('url', '')
        for key, (channel, env_var) in CHANNELS.items():
            content = data.get(key)
            if not content:
                continue
            marker = f"{project_id}:{lang}:{slug}:{channel}"
            if marker in posted:
                continue
            res = _post_or_queue(channel, env_var, content,
                                 {'project': project_id, 'lang': lang, 'slug': slug, 'url': url},
                                 queue_dir)
            posted.add(marker)
            if res.get('posted'):
                n_posted += 1
            elif res.get('queued'):
                n_queued += 1

    _save_posted(queue_dir, posted)
    return {'project': project_id, 'posted': n_posted, 'queued': n_queued}


if __name__ == "__main__":
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp(prefix='social_'))
    try:
        pr = tmp / "published"
        qd = tmp / "queue"
        d = pr / 'demo' / 'es' / '_social'
        d.mkdir(parents=True)
        (d / 'art-abc.json').write_text(json.dumps({
            'x': 'Post para X con enlace https://demo.com/lp/es/art-abc',
            'linkedin': 'Post para LinkedIn ...',
            'facebook_instagram': 'Post para FB/IG ...',
            'email': {'subject': 's', 'body': 'b'},
            'url': 'https://demo.com/lp/es/art-abc',
        }, ensure_ascii=False), encoding='utf-8')

        r1 = publish_all('demo', {}, published_root=pr, queue_dir=qd)
        print('run1:', r1)
        assert r1['queued'] == 3, 'x + linkedin + meta encolados'
        assert (qd / 'queue.jsonl').exists()
        # dedup: segunda corrida no re-encola
        r2 = publish_all('demo', {}, published_root=pr, queue_dir=qd)
        print('run2:', r2)
        assert r2['queued'] == 0 and r2['posted'] == 0, 'no debe re-publicar'
        print('OK: publica/encola 3 canales + deduplica en la 2a corrida')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
