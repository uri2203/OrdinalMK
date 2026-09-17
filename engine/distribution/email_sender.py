"""
OrdinalMK — Envío de secuencias de email (Resend) con fallback.

Motor de secuencias por tiempo (welcome → nurture → conversión, definidas en
projects.yaml → email.sequences con delay_hours). Para cada suscriptor calcula
qué etapas ya vencieron y las envía:
  - Con RESEND_API_KEY → envía por Resend.
  - Sin credenciales → fallback: encola a archivo (dry-run), sin romper.

Multi-idioma (usa el idioma del suscriptor). El estado de "ya enviado" lo lleva
el suscriptor (lista `sent`); en producción lo persistes en tu base.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
QUEUE_DIR = REPO_ROOT / "reports" / "email_queue"

STAGE_TEMPLATES = {
    'welcome': {
        'es': ("Bienvenido a {brand}", "Gracias por unirte a {brand}. Empieza por el agente que más tiempo te ahorra: {cta}"),
        'en': ("Welcome to {brand}", "Thanks for joining {brand}. Start with the agent that saves you the most time: {cta}"),
        'pt': ("Bem-vindo à {brand}", "Obrigado por se juntar à {brand}. Comece pelo agente que mais poupa tempo: {cta}"),
        'fr': ("Bienvenue chez {brand}", "Merci d'avoir rejoint {brand}. Commencez par l'agent qui vous fait gagner le plus de temps : {cta}"),
        'de': ("Willkommen bei {brand}", "Danke, dass du bei {brand} bist. Starte mit dem Agenten, der dir am meisten Zeit spart: {cta}"),
    },
    'nurture': {
        'es': ("Por qué tu IA debe correr en tu equipo", "Tus datos no deberían vivir en la nube. Con {brand} la IA trabaja en tu computadora. {cta}"),
        'en': ("Why your AI should run on your computer", "Your data shouldn't live in the cloud. With {brand}, AI runs on your machine. {cta}"),
        'pt': ("Por que sua IA deve rodar no seu computador", "Seus dados não deveriam viver na nuvem. Com {brand}, a IA roda no seu computador. {cta}"),
        'fr': ("Pourquoi votre IA doit tourner sur votre ordinateur", "Vos données ne devraient pas vivre dans le cloud. Avec {brand}, l'IA tourne chez vous. {cta}"),
        'de': ("Warum deine KI auf deinem Rechner laufen sollte", "Deine Daten gehören nicht in die Cloud. Mit {brand} läuft die KI auf deinem Rechner. {cta}"),
    },
    'conversion': {
        'es': ("Tu prueba está por terminar", "No pierdas lo que {brand} automatiza por ti. Actívalo hoy y cancela cuando quieras: {cta}"),
        'en': ("Your trial is ending", "Don't lose what {brand} automates for you. Activate today, cancel anytime: {cta}"),
        'pt': ("Seu teste está terminando", "Não perca o que a {brand} automatiza para você. Ative hoje, cancele quando quiser: {cta}"),
        'fr': ("Votre essai se termine", "Ne perdez pas ce que {brand} automatise pour vous. Activez aujourd'hui, annulez quand vous voulez : {cta}"),
        'de': ("Deine Testphase endet bald", "Verliere nicht, was {brand} für dich automatisiert. Aktiviere heute, jederzeit kündbar: {cta}"),
    },
}


def _resend_key():
    return os.environ.get('RESEND_API_KEY', '')


def _cta_link(config: dict, lang: str) -> str:
    land = (config.get('landing') or {}).get(lang, {})
    return land.get('cta_link') or f"https://{(config.get('domain') or '').strip('/')}/"


def render(config: dict, stage: str, lang: str) -> dict:
    brand = config.get('name', 'nuestra marca')
    tmpl = STAGE_TEMPLATES.get(stage, {})
    subject, body = tmpl.get(lang, tmpl.get('es', (stage, '{cta}')))
    cta = _cta_link(config, lang)
    return {'subject': subject.format(brand=brand),
            'body': body.format(brand=brand, cta=cta)}


def send(to: str, subject: str, body: str, from_addr: str,
         queue_dir: Path = QUEUE_DIR) -> dict:
    """Envía por Resend si hay key; si no, encola a archivo (dry-run)."""
    key = _resend_key()
    if not key:
        queue_dir.mkdir(parents=True, exist_ok=True)
        rec = {'to': to, 'from': from_addr, 'subject': subject, 'body': body,
               'queued_at': datetime.now(timezone.utc).isoformat()}
        with open(queue_dir / 'queue.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return {'sent': False, 'queued': True, 'reason': 'sin RESEND_API_KEY'}
    try:
        import requests
        resp = requests.post(
            'https://api.resend.com/emails',
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            json={'from': from_addr, 'to': [to], 'subject': subject,
                  'html': f"<p>{body}</p>"},
            timeout=20)
        ok = resp.status_code in (200, 201)
        return {'sent': ok, 'queued': False,
                'status': resp.status_code} if ok else {
                'sent': False, 'queued': False, 'status': resp.status_code}
    except Exception as e:
        return {'sent': False, 'queued': False, 'error': str(e)}


def due_stages(subscribed_at: datetime, sequences: dict, sent: list,
               now: datetime = None) -> list:
    """Etapas cuyo delay_hours ya venció y aún no se enviaron, en orden temporal."""
    now = now or datetime.now(timezone.utc)
    elapsed_h = (now - subscribed_at).total_seconds() / 3600.0
    due = []
    for stage, spec in (sequences or {}).items():
        if stage in (sent or []):
            continue
        delay = float((spec or {}).get('delay_hours', 0))
        if elapsed_h >= delay:
            due.append((delay, stage))
    due.sort()
    return [stage for _, stage in due]


def run_sequences(project_id: str, config: dict, subscribers: list,
                  now: datetime = None, queue_dir: Path = QUEUE_DIR) -> dict:
    """Procesa la secuencia de email para una lista de suscriptores."""
    sequences = (config.get('email') or {}).get('sequences', {}) or {}
    from_addr = (config.get('email') or {}).get('from') or f"no-reply@{config.get('domain','')}"
    sent_count = queued_count = 0
    for sub in subscribers:
        lang = sub.get('language', 'es')
        sa = sub['subscribed_at']
        if isinstance(sa, str):
            sa = datetime.fromisoformat(sa)
        for stage in due_stages(sa, sequences, sub.get('sent', []), now=now):
            msg = render(config, stage, lang)
            res = send(sub['email'], msg['subject'], msg['body'], from_addr, queue_dir=queue_dir)
            sub.setdefault('sent', []).append(stage)
            if res.get('sent'):
                sent_count += 1
            elif res.get('queued'):
                queued_count += 1
    return {'project': project_id, 'sent': sent_count, 'queued': queued_count,
            'subscribers': len(subscribers)}


if __name__ == "__main__":
    import tempfile, shutil
    from datetime import timedelta

    tmp = Path(tempfile.mkdtemp(prefix='email_'))
    try:
        cfg = {
            'name': 'TuIAlista', 'domain': 'tuialista.com',
            'landing': {'es': {'cta_link': 'https://tuialista.com/catalogo/'}},
            'email': {'from': 'TuIAlista <hola@tuialista.com>', 'sequences': {
                'welcome': {'delay_hours': 0}, 'nurture': {'delay_hours': 48},
                'conversion': {'delay_hours': 168},
            }},
        }
        now = datetime.now(timezone.utc)
        subs = [
            # se suscribió hace 50h → welcome (0h) y nurture (48h) vencidas, conversion no
            {'email': 'a@x.com', 'language': 'es', 'subscribed_at': now - timedelta(hours=50), 'sent': []},
        ]
        r = render(cfg, 'welcome', 'es')
        print('welcome:', r['subject'], '|', r['body'][:50])
        assert 'TuIAlista' in r['subject'] and 'tuialista.com' in r['body']

        due = due_stages(subs[0]['subscribed_at'], cfg['email']['sequences'], [], now=now)
        print('etapas vencidas:', due)
        assert due == ['welcome', 'nurture'], due

        out = run_sequences('tuialista', cfg, subs, now=now, queue_dir=tmp)
        print('resultado:', out)
        assert out['queued'] == 2 and out['sent'] == 0  # sin key → encola
        assert subs[0]['sent'] == ['welcome', 'nurture']
        assert (tmp / 'queue.jsonl').exists()
        # segunda corrida no reenvía (ya enviadas)
        out2 = run_sequences('tuialista', cfg, subs, now=now, queue_dir=tmp)
        assert out2['queued'] == 0, 'no debe reenviar etapas ya enviadas'
        print('OK: secuencias por tiempo + fallback a cola + no reenvía')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
