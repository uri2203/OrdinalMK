"""
OrdinalMK — Prospección: outreach B2B legal.

Envía correo frío SOLO a prospectos APROBADOS por un humano, con:
  - Personalización por negocio (IA si hay credenciales; si no, plantilla).
  - Identidad del remitente + OPT-OUT en CADA correo (obligatorio, se añade en
    código — no se delega a la IA).
  - Dominio de envío dedicado (sender.from_email) para no quemar tu dominio.
  - Tope de volumen/día (entregabilidad + legal).

Envía vía engine.distribution.email_sender (Resend con fallback a cola). Marca
cada prospecto como 'contactado'. Nunca escribe a prospectos 'nuevo' (puerta
humana): primero se aprueban.
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine.prospecting import icp as icp_mod
from engine.prospecting import store
from engine.distribution.email_sender import send as email_send, QUEUE_DIR

CONTENT_MODEL = os.environ.get("ORDINALMK_CONTENT_MODEL", "claude-opus-4-8")


def _ai_available() -> bool:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get('ANTHROPIC_API_KEY')
               or os.environ.get('ANTHROPIC_AUTH_TOKEN')
               or os.environ.get('ANTHROPIC_PROFILE'))


def _cta_link(config: dict, lang: str) -> str:
    land = (config.get('landing') or {}).get(lang, {})
    return land.get('cta_link') or f"https://{(config.get('domain') or '').strip('/')}/"


def _footer(sender: dict) -> str:
    """Identidad + opt-out — SIEMPRE presente (cumplimiento legal)."""
    company = sender.get('company', '')
    address = sender.get('address', '')
    optout = sender.get('unsubscribe', 'Responde BAJA y no vuelvo a escribirte.')
    return f"\n\n—\n{company} · {address}\n{optout}"


def render_outreach(prospect: dict, config: dict, icp: dict = None) -> dict:
    icp = icp or icp_mod.get_icp(config)
    if _ai_available():
        try:
            msg = _render_ai(prospect, config, icp)
        except Exception:
            msg = _render_template(prospect, config, icp)
    else:
        msg = _render_template(prospect, config, icp)
    # El opt-out/identidad SIEMPRE se añade en código (no se confía a la IA)
    msg['body'] = msg['body'].rstrip() + _footer(icp['sender'])
    return msg


def _render_template(prospect: dict, config: dict, icp: dict) -> dict:
    brand = config.get('name', 'Nosotros')
    concept = config.get('concept', '')
    lang = icp['language']
    name = prospect.get('name', '') or 'tu negocio'
    cta = _cta_link(config, lang)
    subject = f"{name}: automatiza tu operación con IA que respeta tus datos"
    body = (f"Hola, equipo de {name}:\n\n"
            f"En {brand} ayudamos a negocios como el suyo a automatizar tareas "
            f"({concept.lower()}). Lo distinto: nuestra IA corre en su propio "
            f"equipo, así sus datos nunca salen a la nube.\n\n"
            f"¿Le muestro cómo en una prueba gratuita? {cta}")
    return {'subject': subject, 'body': body}


def _render_ai(prospect: dict, config: dict, icp: dict) -> dict:
    import anthropic
    import json as _json
    client = anthropic.Anthropic()
    brand = config.get('name', '')
    lang = icp['language']
    system = (f"Eres un vendedor B2B de {brand}. Escribes en '{lang}' un correo frío "
              f"BREVE (4-6 líneas), personalizado al negocio, tono {config.get('governance',{}).get('brand_voice','profesional y directo')}. "
              f"Nada de spam ni exageraciones. Devuelves SOLO JSON: {{subject, body}}. "
              f"No incluyas despedida ni firma (se añaden aparte).")
    user = (f"Negocio: {prospect.get('name','')} ({prospect.get('query','')}).\n"
            f"Marca: {brand} — {config.get('concept','')}. Foso: IA local, los datos "
            f"del cliente no salen de su equipo.\n"
            f"CTA hacia: {_cta_link(config, lang)}\n"
            f"Escribe el correo frío.")
    resp = client.messages.create(model=CONTENT_MODEL, max_tokens=800,
                                  system=system, messages=[{"role": "user", "content": user}])
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    text = text.strip('`')
    if text.startswith('json'):
        text = text[4:]
    data = _json.loads(text)
    return {'subject': data['subject'], 'body': data['body']}


def send_to_approved(project_id: str, config: dict, base: Path = None,
                     queue_dir: Path = QUEUE_DIR) -> dict:
    """Envía a los prospectos APROBADOS (respeta tope/día). Marca 'contactado'."""
    icp = icp_mod.get_icp(config)
    sender = icp['sender']
    if not sender.get('from_email'):
        return {'error': 'falta sender.from_email (dominio de envío dedicado)'}

    kwargs = {'base': base} if base else {}
    approved = store.by_status(project_id, 'aprobado', **kwargs)
    cap = icp['max_emails_per_day']
    batch = approved[:cap]

    sent = queued = 0
    from_addr = f"{sender['from_name']} <{sender['from_email']}>"
    for p in batch:
        to = (p.get('email') or '').strip()
        if not to:
            continue
        msg = render_outreach(p, config, icp)
        res = email_send(to, msg['subject'], msg['body'], from_addr, queue_dir=queue_dir)
        store.update_status(project_id, p.get('key') or to, 'contactado', **kwargs)
        if res.get('sent'):
            sent += 1
        elif res.get('queued'):
            queued += 1
    return {'project': project_id, 'aprobados': len(approved),
            'enviados': sent, 'encolados': queued, 'tope_dia': cap}


if __name__ == "__main__":
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp(prefix='outreach_'))
    try:
        cfg = {
            'name': 'TuIAlista', 'domain': 'tuialista.com', 'primary_language': 'es',
            'concept': 'agentes de IA locales para tu negocio',
            'landing': {'es': {'cta_link': 'https://tuialista.com/catalogo/'}},
            'prospecting': {'enabled': True, 'max_emails_per_day': 2,
                            'sender': {'from_name': 'TuIAlista', 'from_email': 'hola@mail.tuialista.com',
                                       'company': 'TuIAlista', 'address': 'México',
                                       'unsubscribe': 'Responde BAJA y no te escribo más.'}},
        }
        # 1) render incluye SIEMPRE opt-out + identidad + nombre del negocio
        m = render_outreach({'name': 'Despacho López', 'query': 'despacho contable'}, cfg)
        print('asunto:', m['subject'])
        assert 'Despacho López' in m['subject'] or 'Despacho López' in m['body']
        assert 'BAJA' in m['body'] and 'TuIAlista · México' in m['body'], 'opt-out + identidad obligatorios'

        # 2) send_to_approved: solo aprobados, respeta tope, marca contactado, encola sin key
        base = tmp / 'prospects'
        store.add_prospects('demo', [
            {'name': 'A', 'email': 'contacto@a.mx', 'website': 'https://a.mx'},
            {'name': 'B', 'email': 'info@b.mx', 'website': 'https://b.mx'},
            {'name': 'C', 'email': 'hola@c.mx', 'website': 'https://c.mx'},
        ], base=base)
        for k in ('contacto@a.mx', 'info@b.mx', 'hola@c.mx'):
            store.update_status('demo', k, 'aprobado', base=base)
        out = send_to_approved('demo', cfg, base=base, queue_dir=tmp / 'q')
        print('outreach:', out)
        assert out['encolados'] == 2, 'respeta tope de 2/día'
        contactados = store.by_status('demo', 'contactado', base=base)
        assert len(contactados) == 2
        print('OK: opt-out/identidad siempre + solo aprobados + tope/día + marca contactado')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
