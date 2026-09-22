"""
OrdinalMK — Indexación automática (Google Indexing API + IndexNow).

Publicar no basta: Google puede tardar SEMANAS en encontrar una página. Este
módulo empuja las URLs nuevas/actualizadas a los buscadores en minutos:

  - IndexNow (Bing, Yandex, Seznam, Naver): POST simple con una clave. Requiere
    subir un archivo <key>.txt a la raíz del dominio (se documenta en el manifest).
  - Google Indexing API: notifica URL_UPDATED (requiere service account con el
    permiso "Owner" en Search Console del dominio).

Todo con fallback: sin credenciales, encola las URLs a archivo (dry-run) y no
rompe. Las funciones que construyen payloads son puras (testeables sin red).

Cola: reports/index_queue/<project>.jsonl
Env: INDEXNOW_KEY, GOOGLE_INDEXING_CREDENTIALS (o GSC_CREDENTIALS).
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

QUEUE_DIR = REPO_ROOT / "reports" / "index_queue"
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
GOOGLE_ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"


def _host(url_or_domain: str) -> str:
    h = (url_or_domain or '').replace('https://', '').replace('http://', '').strip('/')
    return h.split('/')[0]


def indexnow_payload(host: str, key: str, urls: list, key_location: str = None) -> dict:
    """Construye el cuerpo JSON de IndexNow (función pura)."""
    body = {'host': host, 'key': key, 'urlList': list(urls)}
    body['keyLocation'] = key_location or f"https://{host}/{key}.txt"
    return body


def _enqueue(project_id: str, urls: list, engine: str, reason: str,
             queue_dir: Path = QUEUE_DIR) -> dict:
    queue_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with open(queue_dir / f"{project_id}.jsonl", 'a', encoding='utf-8') as f:
        for u in urls:
            f.write(json.dumps({'url': u, 'engine': engine, 'ts': ts,
                                'status': 'queued', 'reason': reason},
                               ensure_ascii=False) + "\n")
    return {'engine': engine, 'queued': len(urls), 'reason': reason}


def submit_indexnow(project_id: str, urls: list, config: dict,
                    queue_dir: Path = QUEUE_DIR) -> dict:
    key = os.environ.get('INDEXNOW_KEY')
    host = _host(config.get('domain', ''))
    if not urls:
        return {'engine': 'indexnow', 'sent': 0, 'reason': 'sin urls'}
    if not key or not host:
        return _enqueue(project_id, urls, 'indexnow',
                        'falta INDEXNOW_KEY o domain', queue_dir)
    try:
        import requests
        body = indexnow_payload(host, key, urls)
        r = requests.post(INDEXNOW_ENDPOINT, json=body, timeout=15)
        ok = r.status_code in (200, 202)
        if not ok:
            return _enqueue(project_id, urls, 'indexnow', f'http {r.status_code}', queue_dir)
        return {'engine': 'indexnow', 'sent': len(urls), 'status': r.status_code}
    except Exception as e:
        return _enqueue(project_id, urls, 'indexnow', f'error {type(e).__name__}', queue_dir)


def submit_google(project_id: str, urls: list, config: dict,
                  queue_dir: Path = QUEUE_DIR) -> dict:
    creds_path = os.environ.get('GOOGLE_INDEXING_CREDENTIALS') or os.environ.get('GSC_CREDENTIALS')
    if not urls:
        return {'engine': 'google', 'sent': 0, 'reason': 'sin urls'}
    if not creds_path or not Path(creds_path).exists():
        return _enqueue(project_id, urls, 'google',
                        'falta GOOGLE_INDEXING_CREDENTIALS', queue_dir)
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
        scopes = ['https://www.googleapis.com/auth/indexing']
        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=scopes)
        session = AuthorizedSession(creds)
        sent = 0
        for u in urls:
            resp = session.post(GOOGLE_ENDPOINT, json={'url': u, 'type': 'URL_UPDATED'}, timeout=15)
            if resp.status_code == 200:
                sent += 1
        return {'engine': 'google', 'sent': sent, 'total': len(urls)}
    except Exception as e:
        return _enqueue(project_id, urls, 'google', f'error {type(e).__name__}', queue_dir)


def submit(project_id: str, urls: list, config: dict,
           queue_dir: Path = QUEUE_DIR) -> dict:
    """Empuja a IndexNow + Google. Lo que falle se encola. Nunca rompe."""
    urls = [u for u in (urls or []) if u]
    return {
        'project': project_id,
        'urls': len(urls),
        'indexnow': submit_indexnow(project_id, urls, config, queue_dir),
        'google': submit_google(project_id, urls, config, queue_dir),
    }


def pending(project_id: str, queue_dir: Path = QUEUE_DIR) -> int:
    f = queue_dir / f"{project_id}.jsonl"
    if not f.exists():
        return 0
    return sum(1 for line in f.read_text(encoding='utf-8').splitlines() if line.strip())


if __name__ == "__main__":
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp(prefix='idx_'))
    try:
        cfg = {'domain': 'tuialista.com'}
        urls = ['https://tuialista.com/es/lp/despacho-contable-guadalajara/',
                'https://tuialista.com/es/lp/asesoria-fiscal-monterrey/']

        # 1) payload de IndexNow (puro)
        body = indexnow_payload('tuialista.com', 'ABC123', urls)
        print('payload keys:', sorted(body.keys()))
        assert body['host'] == 'tuialista.com' and body['key'] == 'ABC123'
        assert body['keyLocation'] == 'https://tuialista.com/ABC123.txt'
        assert body['urlList'] == urls

        # 2) sin credenciales -> encola ambos motores, no rompe
        os.environ.pop('INDEXNOW_KEY', None)
        os.environ.pop('GOOGLE_INDEXING_CREDENTIALS', None)
        os.environ.pop('GSC_CREDENTIALS', None)
        res = submit('demo', urls, cfg, queue_dir=tmp)
        print('resultado:', res['indexnow']['reason'], '|', res['google']['reason'])
        assert res['indexnow'].get('queued') == 2
        assert res['google'].get('queued') == 2
        assert pending('demo', queue_dir=tmp) == 4, 'debe haber 4 urls en cola'

        # 3) host limpio desde url completa
        assert _host('https://www.tuialista.com/algo') == 'www.tuialista.com'

        # 4) sin urls -> no encola
        empty = submit('demo', [], cfg, queue_dir=tmp)
        assert empty['indexnow']['sent'] == 0
        print('en cola:', pending('demo', queue_dir=tmp))
        print('OK: indexacion (payload IndexNow + fallback a cola Google/IndexNow + host)')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
