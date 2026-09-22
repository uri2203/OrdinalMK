"""
OrdinalMK — Alertas operativas.

Te avisa cuando algo necesita tu atención, sin que tengas que entrar a mirar:
  - Cae un ranking (serp_tracker -> movers 'down').
  - Hay contenido fiscal esperando revisión (_held).
  - Respondió un prospecto (embudo -> 'respondio').

Canales: Telegram (instantáneo) o email (Resend). Sin credenciales: registra la
alerta en archivo (para que el panel la muestre) y no rompe.

Registro: reports/alerts/<project>.jsonl. `format_alert` es pura y testeable.
Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, RESEND_API_KEY, ALERT_EMAIL.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

ALERTS_DIR = REPO_ROOT / "reports" / "alerts"

SEVERITY = {'rank_drop': 'alta', 'held_review': 'media', 'prospect_reply': 'alta',
            'info': 'baja'}


def format_alert(kind: str, payload: dict, project_name: str = '') -> dict:
    """Construye {title, body} legible por canal. Puro."""
    pn = project_name or payload.get('project', '')
    if kind == 'rank_drop':
        items = payload.get('down', [])
        lines = [f"- {d['keyword']}: {d['from']} -> {d['to']} ({d['delta']})" for d in items[:5]]
        title = f"[{pn}] Caída de ranking ({len(items)})"
        body = "Keywords que bajaron:\n" + "\n".join(lines)
    elif kind == 'held_review':
        n = payload.get('count', 0)
        title = f"[{pn}] {n} en revisión"
        body = f"Hay {n} artículo(s) fiscal(es) esperando tu aprobación en el panel."
    elif kind == 'prospect_reply':
        n = payload.get('count', 0)
        who = ", ".join(payload.get('names', [])[:5])
        title = f"[{pn}] {n} prospecto(s) respondieron"
        body = f"Respondieron: {who}. Dales seguimiento en Prospectos."
    else:
        title = f"[{pn}] {payload.get('title', 'Aviso')}"
        body = payload.get('message', '')
    return {'title': title, 'body': body, 'severity': SEVERITY.get(kind, 'baja'), 'kind': kind}


def _log(project_id, alert, alerts_dir):
    alerts_dir.mkdir(parents=True, exist_ok=True)
    rec = {**alert, 'ts': datetime.now(timezone.utc).isoformat(), 'channel': 'log'}
    with open(alerts_dir / f"{project_id}.jsonl", 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _send_telegram(alert) -> bool:
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat:
        return False
    try:
        import requests
        text = f"*{alert['title']}*\n{alert['body']}"
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={'chat_id': chat, 'text': text, 'parse_mode': 'Markdown'}, timeout=15)
        return r.status_code == 200
    except Exception:
        return False


def _send_email(alert) -> bool:
    to = os.environ.get('ALERT_EMAIL')
    if not to or not os.environ.get('RESEND_API_KEY'):
        return False
    try:
        from engine.distribution.email_sender import send as email_send
        res = email_send(to, alert['title'], alert['body'], os.environ.get('ALERT_FROM', 'alerts@ordinalmk'))
        return bool(res.get('sent'))
    except Exception:
        return False


def notify(project_id: str, kind: str, payload: dict, config: dict = None,
           alerts_dir: Path = ALERTS_DIR) -> dict:
    """Dispara una alerta: Telegram -> email -> log. Siempre registra."""
    alert = format_alert(kind, payload, (config or {}).get('name', ''))
    channel = 'log'
    if _send_telegram(alert):
        channel = 'telegram'
    elif _send_email(alert):
        channel = 'email'
    _log(project_id, alert, alerts_dir)  # siempre queda registro para el panel
    return {'project': project_id, 'kind': kind, 'channel': channel,
            'severity': alert['severity'], 'title': alert['title']}


def run(project_id: str, config: dict, movers: dict = None, held: int = 0,
        replies: list = None, alerts_dir: Path = ALERTS_DIR) -> dict:
    """Evalúa señales y dispara las alertas que apliquen."""
    fired = []
    if movers and movers.get('down'):
        fired.append(notify(project_id, 'rank_drop', movers, config, alerts_dir))
    if held:
        fired.append(notify(project_id, 'held_review', {'count': held}, config, alerts_dir))
    if replies:
        fired.append(notify(project_id, 'prospect_reply',
                            {'count': len(replies), 'names': replies}, config, alerts_dir))
    return {'project': project_id, 'fired': len(fired), 'alerts': fired}


def recent(project_id: str, n: int = 20, alerts_dir: Path = ALERTS_DIR) -> list:
    f = alerts_dir / f"{project_id}.jsonl"
    if not f.exists():
        return []
    rows = [json.loads(l) for l in f.read_text(encoding='utf-8').splitlines() if l.strip()]
    return rows[-n:][::-1]


if __name__ == "__main__":
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp(prefix='alerts_'))
    try:
        cfg = {'name': 'TuIAlista'}

        # 1) format_alert por tipo (puro)
        a = format_alert('rank_drop', {'down': [{'keyword': 'cfdi', 'from': 6, 'to': 14, 'delta': -8}]}, 'TuIAlista')
        print('titulo:', a['title'], '| sev:', a['severity'])
        assert 'Caída de ranking' in a['title'] and a['severity'] == 'alta'
        assert 'cfdi' in a['body']
        h = format_alert('held_review', {'count': 3}, 'TuIAlista')
        assert '3 en revisión' in h['title']
        pr = format_alert('prospect_reply', {'count': 2, 'names': ['Despacho A', 'Despacho B']}, 'TuIAlista')
        assert 'respondieron' in pr['title'] and 'Despacho A' in pr['body']

        # 2) sin canales -> log, no rompe, y queda registro
        for k in ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'RESEND_API_KEY', 'ALERT_EMAIL'):
            os.environ.pop(k, None)
        res = notify('demo', 'held_review', {'count': 2}, cfg, alerts_dir=tmp)
        print('canal:', res['channel'])
        assert res['channel'] == 'log'

        # 3) run evalúa varias señales
        r = run('demo', cfg,
                movers={'down': [{'keyword': 'k', 'from': 5, 'to': 12, 'delta': -7}]},
                held=2, replies=['Despacho A'], alerts_dir=tmp)
        print('disparadas:', r['fired'], [x['kind'] for x in r['alerts']])
        assert r['fired'] == 3
        rec = recent('demo', alerts_dir=tmp)
        assert len(rec) >= 3 and rec[0]['kind']  # más reciente primero
        print('OK: alerts (format por tipo + fallback a log + run multi-señal + recent)')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
