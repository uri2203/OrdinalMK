"""
OrdinalMK — Email Automation
Sends email campaigns via Resend API.
Supports sequences: welcome, nurture, upsell.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "docs" / "data"

# Lazy import urllib (fails on Python 3.14 on Windows)
_urllib = None
def _get_urllib():
    global _urllib
    if _urllib is None:
        import urllib.request as _req
        import urllib.error as _err
        _urllib = {'request': _req, 'error': _err}
    return _urllib

DATA_DIR = Path(__file__).parent.parent.parent / "docs" / "data"

# Load env
def load_env():
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip()

load_env()

RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
FROM_EMAIL = os.environ.get('FROM_EMAIL', 'marketing@yayika.com')


# ──────────────────────────────────────────────────
# EMAIL TEMPLATES
# ──────────────────────────────────────────────────
EMAIL_TEMPLATES = {
    'welcome': {
        'es': {
            'subject': 'Bienvenida a Yayika - Tu journey empieza aqui',
            'html': """
            <div style="font-family:Inter,sans-serif;max-width:600px;margin:0 auto;padding:2rem;background:#0f1117;color:#e4e6f0;border-radius:12px">
                <h1 style="color:#6366f1;font-size:1.8rem">Bienvenida a Yayika</h1>
                <p style="color:#8b8fa3;line-height:1.8">Hola {name},</p>
                <p style="color:#8b8fa3;line-height:1.8">Nos emociona que te hayas unido a la comunidad de mujeres que estan transformando sus vidas.</p>
                <p style="color:#8b8fa3;line-height:1.8">Aqui esta lo que te espera:</p>
                <ul style="color:#8b8fa3;line-height:2">
                    <li>Productos digitales exclusivos para mujeres</li>
                    <li>Comunidad de apoyo y networking</li>
                    <li>Tools para trackear tu ciclo menstrual</li>
                    <li>Contenido de valor semanal</li>
                </ul>
                <a href="https://yayika.com" style="display:inline-block;background:#6366f1;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;margin:1rem 0">Explorar Yayika</a>
                <p style="color:#8b8fa3;font-size:0.8rem;margin-top:2rem">Este email fue enviado por Yayika. Si no quisiste suscribirte, puedes <a href="{unsubscribe_url}" style="color:#6366f1">cancelar aqui</a>.</p>
            </div>"""
        },
        'en': {
            'subject': 'Welcome to Yayika - Your journey starts here',
            'html': """
            <div style="font-family:Inter,sans-serif;max-width:600px;margin:0 auto;padding:2rem;background:#0f1117;color:#e4e6f0;border-radius:12px">
                <h1 style="color:#6366f1;font-size:1.8rem">Welcome to Yayika</h1>
                <p style="color:#8b8fa3;line-height:1.8">Hi {name},</p>
                <p style="color:#8b8fa3;line-height:1.8">We're excited to have you join the community of women transforming their lives.</p>
                <p style="color:#8b8fa3;line-height:1.8">Here's what awaits you:</p>
                <ul style="color:#8b8fa3;line-height:2">
                    <li>Exclusive digital products for women</li>
                    <li>Support community and networking</li>
                    <li>Tools to track your menstrual cycle</li>
                    <li>Weekly valuable content</li>
                </ul>
                <a href="https://yayika.com" style="display:inline-block;background:#6366f1;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;margin:1rem 0">Explore Yayika</a>
                <p style="color:#8b8fa3;font-size:0.8rem;margin-top:2rem">This email was sent by Yayika. If you didn't subscribe, you can <a href="{unsubscribe_url}" style="color:#6366f1">unsubscribe here</a>.</p>
            </div>"""
        }
    },
    'nurture': {
        'es': {
            'subject': '5 tips que toda mujer emprendedora deberia saber',
            'html': """
            <div style="font-family:Inter,sans-serif;max-width:600px;margin:0 auto;padding:2rem;background:#0f1117;color:#e4e6f0;border-radius:12px">
                <h1 style="color:#6366f1;font-size:1.5rem">5 tips para mujeres emprendedoras</h1>
                <p style="color:#8b8fa3;line-height:1.8">Hola {name},</p>
                <p style="color:#8b8fa3;line-height:1.8">Aquí van 5 tips que te ayudaran a crecer:</p>
                <ol style="color:#8b8fa3;line-height:2">
                    <li><strong>Define tu niche:</strong> enfocate en lo que mejor haces</li>
                    <li><strong>Construye comunidad:</strong> no crees sola</li>
                    <li><strong>Trackea tu ciclo:</strong> tu productividad varia</li>
                    <li><strong>Invierte en ti:</strong> cursos, herramientas, salud</li>
                    <li><strong>Mide resultados:</strong> lo que no se mide, no se mejora</li>
                </ol>
                <a href="https://yayika.com/tienda" style="display:inline-block;background:#22c55e;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;margin:1rem 0">Ver productos</a>
            </div>"""
        },
        'en': {
            'subject': '5 tips every woman entrepreneur should know',
            'html': """
            <div style="font-family:Inter,sans-serif;max-width:600px;margin:0 auto;padding:2rem;background:#0f1117;color:#e4e6f0;border-radius:12px">
                <h1 style="color:#6366f1;font-size:1.5rem">5 tips for women entrepreneurs</h1>
                <p style="color:#8b8fa3;line-height:1.8">Hi {name},</p>
                <p style="color:#8b8fa3;line-height:1.8">Here are 5 tips to help you grow:</p>
                <ol style="color:#8b8fa3;line-height:2">
                    <li><strong>Define your niche:</strong> focus on what you do best</li>
                    <li><strong>Build community:</strong> don't create alone</li>
                    <li><strong>Track your cycle:</strong> your productivity varies</li>
                    <li><strong>Invest in yourself:</strong> courses, tools, health</li>
                    <li><strong>Measure results:</strong> what isn't measured isn't improved</li>
                </ol>
                <a href="https://yayika.com/store" style="display:inline-block;background:#22c55e;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;margin:1rem 0">View products</a>
            </div>"""
        }
    },
    'upsell': {
        'es': {
            'subject': 'Desbloquea tu potencial con Yayika',
            'html': """
            <div style="font-family:Inter,sans-serif;max-width:600px;margin:0 auto;padding:2rem;background:#0f1117;color:#e4e6f0;border-radius:12px">
                <h1 style="color:#6366f1;font-size:1.5rem">Tu potencial es infinito</h1>
                <p style="color:#8b8fa3;line-height:1.8">Hola {name},</p>
                <p style="color:#8b8fa3;line-height:1.8">Has estado en Yayika por un tiempo y queremos ayudarte a dar el siguiente paso.</p>
                <div style="background:#1a1d27;padding:1.5rem;border-radius:8px;margin:1rem 0;border-left:4px solid #6366f1">
                    <h3 style="color:#6366f1;margin-bottom:0.5rem">Plan Guerrera - $349/mes</h3>
                    <ul style="color:#8b8fa3;line-height:1.8">
                        <li>Acceso ilimitado a productos</li>
                        <li>Comunidad premium</li>
                        <li>Mentoring mensual</li>
                        <li>Sin comisiones por ventas</li>
                    </ul>
                </div>
                <a href="https://buy.stripe.com/14A4gzeXk0xY4cg3mtgA80g" style="display:inline-block;background:#6366f1;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;margin:1rem 0">Upgrade ahora</a>
            </div>"""
        },
        'en': {
            'subject': 'Unlock your potential with Yayika',
            'html': """
            <div style="font-family:Inter,sans-serif;max-width:600px;margin:0 auto;padding:2rem;background:#0f1117;color:#e4e6f0;border-radius:12px">
                <h1 style="color:#6366f1;font-size:1.5rem">Your potential is infinite</h1>
                <p style="color:#8b8fa3;line-height:1.8">Hi {name},</p>
                <p style="color:#8b8fa3;line-height:1.8">You've been on Yayika for a while and we want to help you take the next step.</p>
                <div style="background:#1a1d27;padding:1.5rem;border-radius:8px;margin:1rem 0;border-left:4px solid #6366f1">
                    <h3 style="color:#6366f1;margin-bottom:0.5rem">Guerrera Plan - $349/mo</h3>
                    <ul style="color:#8b8fa3;line-height:1.8">
                        <li>Unlimited product access</li>
                        <li>Premium community</li>
                        <li>Monthly mentoring</li>
                        <li>No sales commissions</li>
                    </ul>
                </div>
                <a href="https://buy.stripe.com/14A4gzeXk0xY4cg3mtgA80g" style="display:inline-block;background:#6366f1;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;margin:1rem 0">Upgrade now</a>
            </div>"""
        }
    }
}


class EmailAutomation:
    """Manages email campaigns and sequences."""
    
    def __init__(self):
        self.api_key = RESEND_API_KEY
        self.from_email = FROM_EMAIL
    
    def send_email(self, to: str, subject: str, html: str) -> dict:
        """Send a single email via Resend."""
        if not self.api_key:
            return {'error': 'No RESEND_API_KEY configured'}
        
        try:
            urllib = _get_urllib()
        except Exception:
            return {'error': 'urllib not available (Python 3.14 Windows issue)'}
        
        payload = json.dumps({
            'from': f'Yayika <{self.from_email}>',
            'to': [to],
            'subject': subject,
            'html': html
        }).encode()
        
        req = urllib['request'].Request(
            'https://api.resend.com/emails',
            data=payload,
            method='POST'
        )
        req.add_header('Authorization', f'Bearer {self.api_key}')
        req.add_header('Content-Type', 'application/json')
        
        try:
            resp = urllib['request'].urlopen(req, timeout=30)
            return {'status': 'sent', 'id': json.loads(resp.read()).get('id')}
        except urllib['error'].HTTPError as e:
            return {'error': f'HTTP {e.code}: {e.read().decode()[:200]}'}
        except Exception as e:
            return {'error': str(e)}
    
    def send_sequence(self, email: str, name: str, sequence: str, language: str = 'es') -> dict:
        """Send an email sequence."""
        template = EMAIL_TEMPLATES.get(sequence, {}).get(language)
        if not template:
            return {'error': f'Sequence "{sequence}" not found for language "{language}"'}
        
        html = template['html'].replace('{name}', name).replace('{unsubscribe_url}', f'https://yayika.com/unsubscribe?email={email}')
        subject = template['subject']
        
        return self.send_email(email, subject, html)
    
    def send_welcome(self, email: str, name: str, language: str = 'es') -> dict:
        """Send welcome email."""
        return self.send_sequence(email, name, 'welcome', language)
    
    def send_nurture(self, email: str, name: str, language: str = 'es') -> dict:
        """Send nurture email."""
        return self.send_sequence(email, name, 'nurture', language)
    
    def send_upsell(self, email: str, name: str, language: str = 'es') -> dict:
        """Send upsell email."""
        return self.send_sequence(email, name, 'upsell', language)
    
    def get_sequences(self) -> list:
        """List available sequences."""
        return [
            {'name': 'welcome', 'description': 'Email de bienvenida automatico', 'trigger': 'Suscripcion'},
            {'name': 'nurture', 'description': 'Serie de nutricion y educacion', 'trigger': '48h despues de welcome'},
            {'name': 'upsell', 'description': 'Conversion a plan de pago', 'trigger': '7 dias despues de nurture'}
        ]


if __name__ == "__main__":
    automation = EmailAutomation()
    
    print("Available sequences:")
    for seq in automation.get_sequences():
        print(f"  - {seq['name']}: {seq['description']}")
    
    # Test send (uncomment to test)
    # result = automation.send_welcome('test@example.com', 'Test User', 'es')
    # print(f"Send result: {result}")
