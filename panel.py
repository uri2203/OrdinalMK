"""
OrdinalMK — Panel de control (backend Flask).

Centro de mando PROFESIONAL para operar el marketing de todos los proyectos:

  - Centro de control: KPIs globales + tarjeta por proyecto con embudo real.
  - Vista de proyecto: gobierno, idiomas, SEO/huecos, contenido, prospección
    (ICP + embudo), conversiones e ingresos, y las RECOMENDACIONES del director.
  - Revisión: contenido fiscal apartado (_held) con vista previa, aprobar/rechazar.
  - Prospectos: descubrir / aprobar / enviar outreach + cambiar estado individual.
  - Estado del sistema: qué integraciones están VIVAS vs. en fallback (honesto),
    última corrida y calendario.
  - Lanzar corrida del motor en segundo plano.

Login server-side REAL (sesión + contraseña por env). Corre en un servidor
(no en GitHub Pages, que es estático).

    ORDINALMK_PANEL_PASSWORD=tu-clave  python panel.py     # http://localhost:5001
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import (Flask, session, request, redirect, url_for,
                   render_template_string, flash, Response, abort)

REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))

from config.projects import load_config, active_languages
from engine import governance
from engine.prospecting import (icp as icp_mod, store as pstore,
                                pipeline as ppipeline, outreach)
from engine.review import queue as review_queue
from engine.reporting.report import generate as gen_report
from engine.measurement.conversions import summary as conv_summary
from engine.intelligence import keywords as kw
from engine.intelligence import recommendations as recs_mod
from engine.publishers.content_publisher import CONTENT_ROOT

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ordinalmk-panel-dev')

PANEL_PASSWORD = os.environ.get('ORDINALMK_PANEL_PASSWORD', 'ordinalmk')
REPORTS_DIR = REPO_ROOT / "reports" / "generated"
PUBLISHED_DIR = REPO_ROOT / "published"
DATA_DIR = REPO_ROOT / "docs" / "data"
LAST_RUN_LOG = REPO_ROOT / "reports" / "panel_last_run.log"

FUNNEL = ['nuevo', 'aprobado', 'contactado', 'respondio', 'convertido']
FUNNEL_LABEL = {'nuevo': 'Nuevos', 'aprobado': 'Aprobados', 'contactado': 'Contactados',
                'respondio': 'Respondieron', 'convertido': 'Convertidos',
                'descartado': 'Descartados'}


def _cfg():
    return load_config().get('projects', {})


def _engine_cfg():
    return load_config().get('engine', {})


def login_required(f):
    @wraps(f)
    def wrapper(*a, **k):
        if not session.get('auth'):
            return redirect(url_for('login', next=request.path))
        return f(*a, **k)
    return wrapper


# ─────────────────────────── helpers de datos ───────────────────────────
def _count_published_pages(pid: str, langs: list) -> dict:
    """Cuenta páginas HTML publicadas por idioma en /published/<pid>/<lang>/."""
    out = {}
    base = PUBLISHED_DIR / pid
    for lang in langs:
        d = base / lang
        out[lang] = len(list(d.glob('*.html'))) if d.exists() else 0
    return out


def _load_data(name: str, default=None):
    """Lee un JSON de docs/data/ (dashboard SEO). Tolerante a BOM/errores."""
    f = DATA_DIR / name
    if not f.exists():
        return default
    try:
        return json.loads(f.read_text(encoding='utf-8-sig'))
    except Exception:
        return default


def _held_preview(pid: str, slug: str, chars: int = 480) -> str:
    f = CONTENT_ROOT / pid / "_held" / f"{slug}.json"
    if not f.exists():
        return ''
    try:
        a = json.loads(f.read_text(encoding='utf-8'))
    except Exception:
        return ''
    body = (a.get('body') or a.get('content') or '').strip()
    return body[:chars] + ('…' if len(body) > chars else '')


def project_summary(pid: str, cfg: dict) -> dict:
    """Resumen rico de un proyecto para tarjetas y agregados."""
    langs = cfg.get('languages', []) or []
    try:
        active = active_languages(cfg)
    except Exception:
        active = langs
    counts = pstore.counts(pid)
    conv = conv_summary(pid)
    held = review_queue.list_held(pid)
    pub = _count_published_pages(pid, langs)
    return {
        'id': pid,
        'name': cfg.get('name', pid),
        'domain': cfg.get('domain', ''),
        'concept': cfg.get('concept', ''),
        'enabled': governance.project_enabled(cfg),
        'priority': governance.project_priority(cfg),
        'articles_per_day': governance.articles_per_day(cfg, _engine_cfg()),
        'prospecting': icp_mod.prospecting_enabled(cfg),
        'languages': langs,
        'active_languages': active,
        'published': pub,
        'published_total': sum(pub.values()),
        'counts': counts,
        'prospects_total': counts.get('total', 0),
        'held': held,
        'held_n': len(held),
        'revenue': conv['totals'].get('revenue', 0),
        'trials': conv['totals'].get('trials', 0),
        'paid': conv['totals'].get('paid', 0),
        'trial_to_paid': conv.get('trial_to_paid', 0),
    }


def integrations_status() -> list:
    """Salud honesta: integración -> viva (llave puesta) o fallback."""
    def has(*keys):
        return any(os.environ.get(k) for k in keys)
    return [
        {'name': 'IA de contenido y outreach', 'vendor': 'Anthropic (Claude)',
         'on': has('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN'),
         'env': 'ANTHROPIC_API_KEY',
         'live': 'Redacta artículos y correos con IA de marca.',
         'fallback': 'Usa plantillas (sin IA). No gasta, pero genérico.'},
        {'name': 'Descubrir prospectos', 'vendor': 'Google Places',
         'on': has('GOOGLE_PLACES_API_KEY'),
         'env': 'GOOGLE_PLACES_API_KEY',
         'live': 'Encuentra negocios reales por giro y zona.',
         'fallback': 'No descubre; solo prospectos cargados a mano.'},
        {'name': 'Envío de email / outreach', 'vendor': 'Resend',
         'on': has('RESEND_API_KEY'),
         'env': 'RESEND_API_KEY',
         'live': 'Envía correos de verdad (secuencias + outreach).',
         'fallback': 'Encola a archivo (dry-run). Nada sale.'},
        {'name': 'Medición de ranking', 'vendor': 'Google Search Console',
         'on': has('GSC_CREDENTIALS', 'GSC_SERVICE_ACCOUNT'),
         'env': 'GSC_CREDENTIALS',
         'live': 'Detecta quick wins (página 2, CTR bajo).',
         'fallback': 'Recomienda solo con huecos + canibalización.'},
        {'name': 'Publicar en repos de marca', 'vendor': 'GitHub',
         'on': has('GH_TOKEN', 'GH_PAT'),
         'env': 'GH_TOKEN',
         'live': 'Sube landings/artículos a los sitios.',
         'fallback': 'Genera en /published pero no hace push.'},
    ]


def last_run_info() -> dict:
    if not LAST_RUN_LOG.exists():
        return {'exists': False}
    try:
        mtime = datetime.fromtimestamp(LAST_RUN_LOG.stat().st_mtime, tz=timezone.utc)
        text = LAST_RUN_LOG.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return {'exists': False}
    tail = "\n".join(text.strip().splitlines()[-40:])
    return {'exists': True, 'when': mtime.strftime('%Y-%m-%d %H:%M UTC'), 'tail': tail}


# ───────────────────────────── layout / estilo ─────────────────────────────
LAYOUT = """
<!doctype html><html lang=es><head><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>OrdinalMK — {{ title or 'Panel' }}</title>
<style>
 :root{
   --bg:#0b0d13;--bg2:#0f1218;--surface:#161a24;--surface2:#1b2030;--line:#252b3b;
   --text:#e6e8f0;--muted:#8a90a6;--faint:#5b6178;
   --accent:#6d5efc;--accent2:#8b7bff;--ok:#25c281;--warn:#f5a524;--danger:#f4436c;--info:#38bdf8;
 }
 *{box-sizing:border-box;margin:0;padding:0}
 body{font-family:'Segoe UI',-apple-system,Roboto,sans-serif;background:
   radial-gradient(1200px 600px at 100% -10%,rgba(109,94,252,.10),transparent 60%),
   var(--bg);color:var(--text);line-height:1.5;min-height:100vh}
 a{color:inherit;text-decoration:none}
 /* layout */
 .app{display:flex;min-height:100vh}
 .side{width:230px;flex-shrink:0;background:linear-gradient(180deg,var(--bg2),var(--bg));
   border-right:1px solid var(--line);padding:1.1rem .8rem;position:sticky;top:0;height:100vh;overflow:auto}
 .brand{display:flex;align-items:center;gap:.55rem;font-weight:800;font-size:1.05rem;
   padding:.3rem .5rem 1rem;letter-spacing:.2px}
 .brand .dot{width:26px;height:26px;border-radius:8px;background:linear-gradient(135deg,var(--accent),var(--info));
   display:grid;place-items:center;font-size:.8rem;color:#fff;box-shadow:0 4px 14px rgba(109,94,252,.5)}
 .side .grp{color:var(--faint);font-size:.68rem;text-transform:uppercase;letter-spacing:.12em;margin:1rem .6rem .35rem}
 .side a.item{display:flex;align-items:center;gap:.6rem;padding:.55rem .65rem;border-radius:9px;
   color:var(--muted);font-size:.9rem;margin-bottom:2px;transition:.15s}
 .side a.item:hover{background:var(--surface);color:var(--text)}
 .side a.item.on{background:linear-gradient(90deg,rgba(109,94,252,.18),transparent);color:var(--text);
   box-shadow:inset 2px 0 0 var(--accent)}
 .side a.item .ic{width:18px;text-align:center;opacity:.9}
 .side a.item .cnt{margin-left:auto;background:var(--warn);color:#1a1200;font-size:.7rem;font-weight:700;
   border-radius:100px;padding:0 .45rem}
 .side .runbtn{width:100%;margin-top:.5rem;background:linear-gradient(135deg,var(--accent),var(--accent2));
   color:#fff;border:none;border-radius:10px;padding:.6rem;font-weight:600;cursor:pointer;font-size:.88rem}
 .main{flex:1;min-width:0;padding:1.6rem 2rem 3rem;max-width:1180px}
 .top{display:flex;align-items:center;gap:.8rem;margin-bottom:1.4rem;flex-wrap:wrap}
 .top h1{font-size:1.5rem;font-weight:700}
 .top .sub{color:var(--muted);font-size:.9rem}
 .top .spacer{margin-left:auto}
 /* KPIs */
 .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.9rem;margin-bottom:1.4rem}
 .kpi{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:1rem 1.1rem}
 .kpi .lbl{color:var(--muted);font-size:.78rem;margin-bottom:.35rem;display:flex;align-items:center;gap:.4rem}
 .kpi .val{font-size:1.7rem;font-weight:750;letter-spacing:-.5px}
 .kpi .val small{font-size:.9rem;color:var(--muted);font-weight:500}
 .kpi.accent{background:linear-gradient(135deg,rgba(109,94,252,.22),rgba(56,189,248,.10));border-color:rgba(109,94,252,.4)}
 /* cards */
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:1rem}
 .card{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:1.15rem 1.25rem;margin-bottom:1rem}
 .card h2{font-size:1rem;margin-bottom:.9rem;display:flex;align-items:center;gap:.5rem}
 .card h2 .k{color:var(--faint);font-weight:500;font-size:.8rem;margin-left:auto}
 .pcard .head{display:flex;align-items:flex-start;gap:.7rem;margin-bottom:.9rem}
 .pcard .logo{width:40px;height:40px;border-radius:11px;display:grid;place-items:center;font-weight:800;color:#fff;flex-shrink:0}
 .pcard .nm{font-weight:700;font-size:1.05rem;line-height:1.2}
 .pcard .dm{color:var(--muted);font-size:.8rem}
 .stat-row{display:flex;gap:1.3rem;margin:.4rem 0 .9rem;flex-wrap:wrap}
 .stat-row .s .n{font-size:1.15rem;font-weight:700}
 .stat-row .s .l{color:var(--muted);font-size:.72rem}
 /* funnel */
 .funnel{display:flex;gap:4px;margin:.5rem 0}
 .funnel .seg{flex:1;text-align:center}
 .funnel .bar{height:34px;border-radius:6px;display:grid;place-items:center;font-weight:700;font-size:.85rem;color:#fff}
 .funnel .cap{font-size:.63rem;color:var(--muted);margin-top:.25rem;display:block}
 /* pills + badges */
 .pill{display:inline-flex;align-items:center;gap:.3rem;font-size:.72rem;padding:2px 9px;border-radius:100px;font-weight:600}
 .pill.on{background:rgba(37,194,129,.16);color:var(--ok)}
 .pill.off{background:rgba(139,144,166,.14);color:var(--muted)}
 .pill.warn{background:rgba(245,165,36,.16);color:var(--warn)}
 .pill.info{background:rgba(56,189,248,.16);color:var(--info)}
 .pill.pri{background:rgba(109,94,252,.18);color:var(--accent2)}
 .pill.dng{background:rgba(244,67,108,.16);color:var(--danger)}
 .dot-s{width:8px;height:8px;border-radius:50%;display:inline-block}
 /* tables */
 table{width:100%;border-collapse:collapse;font-size:.87rem}
 th,td{text-align:left;padding:.6rem .5rem;border-bottom:1px solid var(--line);vertical-align:top}
 th{color:var(--muted);font-weight:600;font-size:.76rem;text-transform:uppercase;letter-spacing:.05em}
 tr:last-child td{border-bottom:none}
 /* buttons */
 button,.btn{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff;border:none;border-radius:9px;
   padding:.45rem .9rem;font-size:.84rem;cursor:pointer;display:inline-block;font-weight:600}
 button:hover,.btn:hover{filter:brightness(1.08)}
 .btn.sec,button.sec{background:var(--surface2);border:1px solid var(--line);color:var(--text)}
 .btn.dng,button.dng{background:linear-gradient(135deg,var(--danger),#ff6b8f)}
 .btn.ok,button.ok{background:linear-gradient(135deg,var(--ok),#4fd8a0)}
 .btn.sm{padding:.3rem .6rem;font-size:.78rem}
 .flash{background:linear-gradient(90deg,rgba(109,94,252,.18),transparent);border:1px solid rgba(109,94,252,.4);
   border-radius:10px;padding:.7rem 1rem;margin-bottom:1rem;font-size:.9rem}
 .muted{color:var(--muted)}.faint{color:var(--faint)}
 .bar-track{height:8px;background:var(--surface2);border-radius:100px;overflow:hidden}
 .bar-fill{height:100%;border-radius:100px;background:linear-gradient(90deg,var(--accent),var(--info))}
 .rec{border-left:3px solid var(--accent);background:var(--surface2);border-radius:0 10px 10px 0;
   padding:.6rem .85rem;margin-bottom:.55rem;font-size:.87rem}
 .rec .t{font-size:.68rem;text-transform:uppercase;letter-spacing:.06em;color:var(--accent2);font-weight:700}
 .chips{display:flex;flex-wrap:wrap;gap:.4rem}
 .chip{background:var(--surface2);border:1px solid var(--line);border-radius:100px;padding:.25rem .7rem;font-size:.78rem}
 .chip.gap{border-color:rgba(245,165,36,.5);color:var(--warn)}
 code{background:var(--bg);border:1px solid var(--line);border-radius:5px;padding:.05rem .4rem;font-size:.82rem}
 pre{background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:.9rem;overflow:auto;
   font-size:.78rem;color:var(--muted);max-height:340px}
 .back{display:inline-flex;align-items:center;gap:.35rem;color:var(--muted);font-size:.85rem;margin-bottom:1rem}
 @media(max-width:820px){.side{position:fixed;z-index:20;transform:translateX(-100%)}.main{padding:1.2rem}}
</style></head><body>
{% if session.get('auth') %}
<div class=app>
 <aside class=side>
   <a class=brand href="{{url_for('home')}}"><span class=dot>◆</span> OrdinalMK</a>
   <div class=grp>Operación</div>
   <a class="item {{'on' if nav=='home' else ''}}" href="{{url_for('home')}}"><span class=ic>▦</span> Centro de control</a>
   <a class="item {{'on' if nav=='review' else ''}}" href="{{url_for('review')}}"><span class=ic>✓</span> Revisión {% if held_total %}<span class=cnt>{{held_total}}</span>{% endif %}</a>
   <a class="item {{'on' if nav=='seo' else ''}}" href="{{url_for('seo')}}"><span class=ic>📈</span> Analítica / SEO</a>
   <a class="item {{'on' if nav=='system' else ''}}" href="{{url_for('system')}}"><span class=ic>◈</span> Estado del sistema</a>
   <div class=grp>Proyectos</div>
   {% for p in projects_nav %}
   <a class="item {{'on' if nav=='project' and current_pid==p.id else ''}}" href="{{url_for('project', pid=p.id)}}">
     <span class=ic style="color:{{p.color}}">●</span> {{p.name}}</a>
   {% endfor %}
   <form method=post action="{{url_for('run')}}"><button class=runbtn>▶ Lanzar corrida</button></form>
   <div class=grp>Cuenta</div>
   <a class=item href="{{url_for('logout')}}"><span class=ic>⏻</span> Salir</a>
 </aside>
 <main class=main>
   {% with msgs = get_flashed_messages() %}{% for m in msgs %}<div class=flash>{{m}}</div>{% endfor %}{% endwith %}
   {{ body|safe }}
 </main>
</div>
{% else %}
 <div style="max-width:380px;margin:12vh auto;padding:1.5rem">{{ body|safe }}</div>
{% endif %}
</body></html>
"""

# paleta por proyecto (para logos/acentos)
PALETTE = ['#e8821e', '#6d5efc', '#25c281', '#38bdf8', '#f4436c', '#f5a524']


def _color(pid: str, cfg: dict) -> str:
    th = (cfg or {}).get('theme', {}) or {}
    if th.get('primary'):
        return th['primary']
    return PALETTE[sum(ord(c) for c in pid) % len(PALETTE)]


def render(body_html, nav='', title='', current_pid='', **ctx):
    cfg = _cfg()
    projects_nav = [{'id': pid, 'name': c.get('name', pid), 'color': _color(pid, c)}
                    for pid, c in cfg.items()]
    held_total = sum(len(review_queue.list_held(pid)) for pid in cfg) if session.get('auth') else 0
    inner = render_template_string(body_html, **ctx)
    return render_template_string(
        LAYOUT, body=inner, nav=nav, title=title, current_pid=current_pid,
        projects_nav=projects_nav, held_total=held_total)


# ─────────────────────────────── auth ───────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password', '') == PANEL_PASSWORD:
            session['auth'] = True
            return redirect(request.args.get('next') or url_for('home'))
        flash('Contraseña incorrecta.')
    body = """
    <div style="text-align:center;margin-bottom:1.4rem">
      <div style="width:52px;height:52px;border-radius:14px;margin:0 auto .8rem;
        background:linear-gradient(135deg,#6d5efc,#38bdf8);display:grid;place-items:center;
        font-size:1.4rem;color:#fff;box-shadow:0 8px 24px rgba(109,94,252,.5)">◆</div>
      <h1 style="font-size:1.4rem">OrdinalMK</h1>
      <p class=muted style="font-size:.88rem">Centro de mando de marketing</p>
    </div>
    <div class=card>
      <form method=post>
        <p class=muted style="margin-bottom:.5rem;font-size:.85rem">Acceso restringido</p>
        <input type=password name=password placeholder="Contraseña" autofocus
          style="width:100%;background:var(--bg);border:1px solid var(--line);color:var(--text);
          border-radius:9px;padding:.7rem;font-size:1rem">
        <button style="margin-top:.9rem;width:100%;padding:.7rem">Entrar</button>
      </form>
    </div>"""
    return render(body, title='Entrar')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ───────────────────────── centro de control ─────────────────────────
@app.route('/')
@login_required
def home():
    cfg = _cfg()
    summaries = []
    for pid, c in governance.active_projects_ordered(cfg) + \
            [(pid, c) for pid, c in cfg.items() if not governance.project_enabled(c)]:
        s = project_summary(pid, c)
        s['color'] = _color(pid, c)
        summaries.append(s)

    agg = {
        'active': sum(1 for s in summaries if s['enabled']),
        'total': len(summaries),
        'published': sum(s['published_total'] for s in summaries),
        'prospects': sum(s['prospects_total'] for s in summaries),
        'contacted': sum(s['counts'].get('contactado', 0) for s in summaries),
        'held': sum(s['held_n'] for s in summaries),
        'revenue': round(sum(s['revenue'] for s in summaries), 2),
        'paid': sum(s['paid'] for s in summaries),
    }
    body = """
    <div class=top>
      <div><h1>Centro de control</h1>
      <div class=sub>Marketing de {{agg.total}} proyectos, operados desde un solo lugar.</div></div>
    </div>

    <div class=kpis>
      <div class="kpi accent"><div class=lbl>Proyectos activos</div>
        <div class=val>{{agg.active}}<small>/{{agg.total}}</small></div></div>
      <div class=kpi><div class=lbl>Páginas publicadas</div><div class=val>{{agg.published}}</div></div>
      <div class=kpi><div class=lbl>Prospectos</div><div class=val>{{agg.prospects}}</div></div>
      <div class=kpi><div class=lbl>Contactados</div><div class=val>{{agg.contacted}}</div></div>
      <div class=kpi><div class=lbl>En revisión</div>
        <div class=val>{{agg.held}}{% if agg.held %} <span class="pill warn">acción</span>{% endif %}</div></div>
      <div class=kpi><div class=lbl>Ingresos</div><div class=val>${{agg.revenue}} <small>({{agg.paid}})</small></div></div>
    </div>

    <div class=grid>
    {% for s in summaries %}
      <div class="card pcard">
        <div class=head>
          <div class=logo style="background:linear-gradient(135deg,{{s.color}},{{s.color}}bb)">{{s.name[0]}}</div>
          <div style="flex:1">
            <a href="{{url_for('project', pid=s.id)}}"><div class=nm>{{s.name}}</div></a>
            <div class=dm>{{s.domain}}</div>
          </div>
          <span class="pill {{'on' if s.enabled else 'off'}}">{{'activo' if s.enabled else 'pausado'}}</span>
        </div>

        <div style="display:flex;gap:.4rem;flex-wrap:wrap;margin-bottom:.6rem">
          <span class="pill pri">prioridad {{s.priority}}</span>
          <span class="pill {{'on' if s.prospecting else 'off'}}">prospección {{'on' if s.prospecting else 'off'}}</span>
          <span class="pill info">{{s.active_languages|length}}/{{s.languages|length}} idiomas</span>
          {% if s.held_n %}<span class="pill warn">{{s.held_n}} en revisión</span>{% endif %}
        </div>

        <div class=stat-row>
          <div class=s><div class=n>{{s.published_total}}</div><div class=l>páginas</div></div>
          <div class=s><div class=n>{{s.prospects_total}}</div><div class=l>prospectos</div></div>
          <div class=s><div class=n>${{s.revenue}}</div><div class=l>ingresos</div></div>
        </div>

        {% set c = s.counts %}
        {% if s.prospects_total %}
        <div class=funnel>
          {% for st in funnel %}
          {% set v = c.get(st,0) %}
          <div class=seg>
            <div class=bar style="background:linear-gradient(135deg,{{s.color}},{{s.color}}99);opacity:{{ 0.35 + 0.65*(1 if v else 0) }}">{{v}}</div>
            <span class=cap>{{ funnel_label[st] }}</span>
          </div>
          {% endfor %}
        </div>
        {% else %}
        <div class=muted style="font-size:.82rem;margin:.3rem 0 .6rem">Sin prospectos aún.
          {% if s.prospecting %}Usa “Descubrir”.{% else %}Prospección desactivada.{% endif %}</div>
        {% endif %}

        <div style="display:flex;gap:.4rem;margin-top:.8rem;flex-wrap:wrap">
          <a class="btn sm" href="{{url_for('project', pid=s.id)}}">Ver proyecto</a>
          <a class="btn sm sec" href="{{url_for('prospects', project=s.id)}}">Prospectos</a>
          <a class="btn sm sec" href="{{url_for('report', project=s.id)}}">Reporte</a>
        </div>
      </div>
    {% endfor %}
    </div>
    """
    return render(body, nav='home', title='Centro de control',
                  summaries=summaries, agg=agg, funnel=FUNNEL, funnel_label=FUNNEL_LABEL)


# ───────────────────────── vista de proyecto ─────────────────────────
@app.route('/project/<pid>')
@login_required
def project(pid):
    cfg = _cfg().get(pid)
    if cfg is None:
        abort(404)
    s = project_summary(pid, cfg)
    s['color'] = _color(pid, cfg)
    icp = icp_mod.get_icp(cfg)
    conv = conv_summary(pid)
    gaps = kw.find_gaps(cfg, pid)
    try:
        recs = recs_mod.generate(pid, cfg)['recommendations'][:8]
    except Exception:
        recs = []
    # top contenido por ingreso
    by_content = sorted(
        ([{'k': k, **v} for k, v in conv['by_content'].items()]),
        key=lambda x: x['revenue'], reverse=True)[:5]

    body = """
    <a class=back href="{{url_for('home')}}">← Centro de control</a>
    <div class=top>
      <div class=logo style="width:46px;height:46px;border-radius:12px;display:grid;place-items:center;
        font-weight:800;color:#fff;background:linear-gradient(135deg,{{s.color}},{{s.color}}bb)">{{s.name[0]}}</div>
      <div><h1>{{s.name}}</h1><div class=sub>{{s.concept or s.domain}}</div></div>
      <div class=spacer></div>
      <span class="pill {{'on' if s.enabled else 'off'}}">{{'activo' if s.enabled else 'pausado'}}</span>
      <a class="btn sec" href="{{url_for('report', project=s.id)}}">Reporte completo</a>
    </div>

    <div class=kpis>
      <div class=kpi><div class=lbl>Prioridad</div><div class=val>{{s.priority}}</div></div>
      <div class=kpi><div class=lbl>Artículos/día</div><div class=val>{{s.articles_per_day}}</div></div>
      <div class=kpi><div class=lbl>Páginas publicadas</div><div class=val>{{s.published_total}}</div></div>
      <div class=kpi><div class=lbl>Prospectos</div><div class=val>{{s.prospects_total}}</div></div>
      <div class=kpi><div class=lbl>Ingresos</div><div class=val>${{s.revenue}}</div></div>
      <div class=kpi><div class=lbl>Prueba→pago</div><div class=val>{{ (s.trial_to_paid*100)|round(1) }}<small>%</small></div></div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem" class=cols>
      <!-- Gobierno + idiomas -->
      <div class=card>
        <h2>⚙ Gobierno</h2>
        <table>
          <tr><td class=muted>Estado</td><td><span class="pill {{'on' if s.enabled else 'off'}}">{{'activo' if s.enabled else 'pausado'}}</span></td></tr>
          <tr><td class=muted>Prioridad</td><td>{{s.priority}} <span class=faint>(mayor = primero)</span></td></tr>
          <tr><td class=muted>Cuota IA</td><td>{{s.articles_per_day}} artículos/día</td></tr>
          <tr><td class=muted>Voz de marca</td><td>{{ brand_voice or '—' }}</td></tr>
        </table>
        <h2 style="margin-top:1rem">🌐 Idiomas ({{s.active_languages|length}}/{{s.languages|length}} activos)</h2>
        <div class=chips>
          {% for l in s.languages %}
          <span class="chip {{'' if l in s.active_languages else 'gap'}}">{{l}}
            {% if l in s.active_languages %}<span class=faint>· {{ s.published.get(l,0) }} pág.</span>{% endif %}
          </span>
          {% endfor %}
        </div>
      </div>

      <!-- Prospección / ICP -->
      <div class=card>
        <h2>🎯 Prospección <span class="pill {{'on' if s.prospecting else 'off'}} k">{{'activa' if s.prospecting else 'off'}}</span></h2>
        {% if s.prospecting %}
        <table>
          <tr><td class=muted>Giros</td><td>{{ icp.categories|join(', ') or '—' }}</td></tr>
          <tr><td class=muted>Zonas</td><td>{{ icp.locations|join(', ') or '—' }}</td></tr>
          <tr><td class=muted>Descubre/corrida</td><td>{{ icp.max_discover_per_run }}</td></tr>
          <tr><td class=muted>Tope correos/día</td><td>{{ icp.max_emails_per_day }}</td></tr>
          <tr><td class=muted>Remitente</td><td>{{ icp.sender.from_email }}</td></tr>
          <tr><td class=muted>Opt-out</td><td class=faint>{{ icp.sender.unsubscribe }}</td></tr>
        </table>
        {% set c = s.counts %}
        <div class=funnel style="margin-top:.9rem">
          {% for st in funnel %}
          <div class=seg><div class=bar style="background:linear-gradient(135deg,{{s.color}},{{s.color}}99)">{{ c.get(st,0) }}</div>
          <span class=cap>{{ funnel_label[st] }}</span></div>
          {% endfor %}
        </div>
        <a class="btn sm" style="margin-top:.9rem" href="{{url_for('prospects', project=s.id)}}">Gestionar prospectos</a>
        {% else %}
        <p class=muted>Prospección desactivada para este proyecto (opt-in en <code>projects.yaml</code>).</p>
        {% endif %}
      </div>

      <!-- Recomendaciones del director -->
      <div class=card>
        <h2>🧠 Recomendaciones del director <span class=k>{{recs|length}}</span></h2>
        {% if not recs %}<p class=muted>Sin recomendaciones ahora (necesita contenido/medición).</p>{% endif %}
        {% for r in recs %}
        <div class=rec><div class=t>{{r.type}} · prioridad {{r.priority}}</div>{{ r.action }}</div>
        {% endfor %}
      </div>

      <!-- SEO / huecos + ingresos por contenido -->
      <div class=card>
        <h2>🔎 SEO — huecos por cubrir</h2>
        {% set anygap = false %}
        {% for lang, items in gaps.items() %}
          {% if items %}{% set anygap = true %}
          <div style="margin-bottom:.5rem"><span class=faint style="font-size:.75rem">{{lang}}</span>
          <div class=chips style="margin-top:.25rem">
            {% for g in items[:6] %}<span class="chip gap">{{g.keyword}}</span>{% endfor %}
          </div></div>
          {% endif %}
        {% endfor %}
        {% if not anygap %}<p class=muted>Sin huecos: keywords objetivo cubiertas. ✅</p>{% endif %}

        <h2 style="margin-top:1.1rem">💰 Ingresos por contenido</h2>
        {% if by_content %}
        <table><tr><th>Contenido</th><th>Pruebas</th><th>Pagos</th><th>Ingreso</th></tr>
        {% for b in by_content %}
        <tr><td>{{b.k}}</td><td>{{b.trials}}</td><td>{{b.paid}}</td><td>${{b.revenue}}</td></tr>
        {% endfor %}</table>
        {% else %}<p class=muted>Aún no hay conversiones registradas.</p>{% endif %}
      </div>
    </div>
    <style>@media(max-width:760px){.cols{grid-template-columns:1fr!important}}</style>
    """
    return render(body, nav='project', current_pid=pid, title=s['name'],
                  s=s, icp=icp, gaps=gaps, recs=recs, by_content=by_content,
                  brand_voice=governance.brand_voice(cfg),
                  funnel=FUNNEL, funnel_label=FUNNEL_LABEL)


# ─────────────────────── revisión de contenido (_held) ───────────────────────
@app.route('/review')
@login_required
def review():
    blocks = []
    for pid, cfg in _cfg().items():
        items = review_queue.list_held(pid)
        if items:
            for it in items:
                it['preview'] = _held_preview(pid, it['slug'])
            blocks.append({'id': pid, 'name': cfg.get('name', pid),
                           'color': _color(pid, cfg), 'items': items})
    body = """
    <div class=top><div><h1>Revisión de contenido</h1>
      <div class=sub>Contenido fiscal/sensible apartado por la puerta de calidad. Un humano aprueba antes de publicar.</div></div></div>
    {% if not blocks %}<div class=card>Nada pendiente. Todo limpio. ✅</div>{% endif %}
    {% for b in blocks %}
    <div class=card><h2><span class=dot-s style="background:{{b.color}}"></span> {{b.name}}
      <span class=k>{{ b['items']|length }} pendientes</span></h2>
    {% for it in b['items'] %}
      <div style="border:1px solid var(--line);border-radius:12px;padding:.9rem;margin-bottom:.7rem">
        <div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;margin-bottom:.4rem">
          <strong>{{ it.title or it.slug }}</strong>
          <span class="pill info">{{it.language}}</span>
          {% for fl in it.flags %}<span class="pill warn">{{fl}}</span>{% endfor %}
        </div>
        {% if it.reasons %}<div class=faint style="font-size:.8rem;margin-bottom:.4rem">{{ it.reasons|join('; ') }}</div>{% endif %}
        {% if it.preview %}<div class=muted style="font-size:.83rem;margin-bottom:.6rem;white-space:pre-wrap">{{ it.preview }}</div>{% endif %}
        <div style="display:flex;gap:.4rem">
          <form method=post action="{{url_for('review_action', project=b.id, slug=it.slug, action='approve')}}"><button class="ok sm">✓ Aprobar y publicar</button></form>
          <form method=post action="{{url_for('review_action', project=b.id, slug=it.slug, action='reject')}}"><button class="dng sm">✕ Rechazar</button></form>
        </div>
      </div>
    {% endfor %}
    </div>
    {% endfor %}
    """
    return render(body, nav='review', title='Revisión', blocks=blocks)


@app.route('/review/<project>/<slug>/<action>', methods=['POST'])
@login_required
def review_action(project, slug, action):
    cfg = _cfg().get(project, {})
    if action == 'approve':
        r = review_queue.approve(project, slug, cfg, reviewer='panel')
        flash(f"Aprobado y publicado: {slug}" if not r.get('error') else r['error'])
    elif action == 'reject':
        review_queue.reject(project, slug, reason='rechazado desde panel')
        flash(f"Rechazado: {slug}")
    return redirect(url_for('review'))


# ─────────────────────────────── prospectos ───────────────────────────────
@app.route('/prospects/<project>')
@login_required
def prospects(project):
    cfg = _cfg().get(project)
    if cfg is None:
        abort(404)
    counts = pstore.counts(project)
    rows = pstore.load(project)
    icp = icp_mod.get_icp(cfg)
    color = _color(project, cfg)
    status_filter = request.args.get('status', '')
    if status_filter:
        rows = [r for r in rows if r.get('status') == status_filter]
    body = """
    <a class=back href="{{url_for('project', pid=project)}}">← {{name}}</a>
    <div class=top><div><h1>Prospectos — {{name}}</h1>
      <div class=sub>{{ icp.categories|join(', ') }} · {{ icp.locations|join(', ') }}</div></div></div>

    <div class=funnel style="margin-bottom:1rem">
      {% for st in funnel %}
      <div class=seg><div class=bar style="background:linear-gradient(135deg,{{color}},{{color}}99)">{{ counts.get(st,0) }}</div>
      <span class=cap>{{ funnel_label[st] }}</span></div>
      {% endfor %}
    </div>

    <div class=card>
      <div style="display:flex;gap:.5rem;flex-wrap:wrap;align-items:center">
        <form method=post action="{{url_for('prospects_action', project=project, action='discover')}}"><button class=sec>🔍 Descubrir</button></form>
        <form method=post action="{{url_for('prospects_action', project=project, action='approve_all')}}"><button>Aprobar nuevos</button></form>
        <form method=post action="{{url_for('prospects_action', project=project, action='send')}}"><button class=ok>✉ Enviar a aprobados</button></form>
        <span class=spacer style="margin-left:auto"></span>
        <span class="pill info">tope {{ icp.max_emails_per_day }}/día</span>
        <span class="pill pri">{{ icp.sender.from_email }}</span>
      </div>
    </div>

    <div class=card>
      <div style="margin-bottom:.6rem;display:flex;gap:.4rem;flex-wrap:wrap">
        <a class="chip {{'gap' if not status_filter else ''}}" href="{{url_for('prospects', project=project)}}">Todos ({{counts.get('total',0)}})</a>
        {% for st in all_status %}
        <a class="chip {{'gap' if status_filter==st else ''}}" href="{{url_for('prospects', project=project, status=st)}}">{{ funnel_label.get(st,st) }} ({{counts.get(st,0)}})</a>
        {% endfor %}
      </div>
      <table>
        <tr><th>Negocio</th><th>Correo</th><th>Estado</th><th>Mover a</th></tr>
        {% for r in rows[:150] %}
        <tr>
          <td><strong>{{ r.get('name','') }}</strong>{% if r.get('query') %}<div class=faint style="font-size:.75rem">{{r.get('query')}}</div>{% endif %}</td>
          <td class=muted>{{ r.get('email','—') }}</td>
          <td><span class="pill {{'on' if r.get('status')=='convertido' else ('dng' if r.get('status')=='descartado' else 'info')}}">{{ funnel_label.get(r.get('status'), r.get('status')) }}</span></td>
          <td>
            {% set k = r.get('key') or r.get('email') %}
            {% for st in move_targets %}
            {% if st != r.get('status') %}
            <form method=post action="{{url_for('prospect_set', project=project, key=k, status=st)}}" style="display:inline">
              <button class="sec sm" style="padding:.15rem .5rem;font-size:.72rem">{{ funnel_label.get(st,st) }}</button></form>
            {% endif %}
            {% endfor %}
          </td>
        </tr>
        {% endfor %}
      </table>
      {% if not rows %}<p class=muted>Sin prospectos en este filtro. Usa “Descubrir” (requiere GOOGLE_PLACES_API_KEY).</p>{% endif %}
    </div>
    """
    return render(body, nav='project', current_pid=project, title=f'Prospectos — {cfg.get("name",project)}',
                  name=cfg.get('name', project), project=project, counts=counts, rows=rows,
                  icp=icp, color=color, funnel=FUNNEL, funnel_label=FUNNEL_LABEL,
                  all_status=pstore.STATUSES, status_filter=status_filter,
                  move_targets=['aprobado', 'contactado', 'respondio', 'convertido', 'descartado'])


@app.route('/prospects/<project>/<action>', methods=['POST'])
@login_required
def prospects_action(project, action):
    cfg = _cfg().get(project, {})
    if action == 'discover':
        r = ppipeline.discover_project(project, cfg)
        if r.get('available'):
            flash(f"Descubrir: {r.get('nuevos_guardados', 0)} nuevos (de {r.get('descubiertos', 0)} con {r.get('con_correo', 0)} correos).")
        else:
            flash(f"Descubrir: {r.get('reason') or r.get('skipped') or 'no disponible (falta GOOGLE_PLACES_API_KEY)'}")
    elif action == 'approve_all':
        n = ppipeline.approve_all_new(project)
        flash(f"Aprobados {n} prospectos nuevos.")
    elif action == 'send':
        r = outreach.send_to_approved(project, cfg)
        if r.get('error'):
            flash(r['error'])
        else:
            flash(f"Outreach: {r.get('enviados',0)} enviados, {r.get('encolados',0)} en cola (tope {r.get('tope_dia','?')}/día).")
    return redirect(url_for('prospects', project=project))


@app.route('/prospects/<project>/set/<path:key>/<status>', methods=['POST'])
@login_required
def prospect_set(project, key, status):
    try:
        ok = pstore.update_status(project, key, status)
        flash(f"Prospecto → {FUNNEL_LABEL.get(status, status)}." if ok else "No se encontró el prospecto.")
    except ValueError as e:
        flash(str(e))
    return redirect(url_for('prospects', project=project))


# ─────────────────────────── analítica / SEO ───────────────────────────
@app.route('/seo')
@login_required
def seo():
    report = _load_data('marketing_report.json', {}) or {}
    seo_data = _load_data('seo.json', {}) or {}
    content = _load_data('content.json', {}) or {}
    # normaliza la última corrida (dato REAL) a filas por proyecto
    run_rows = []
    for pid, p in (report.get('projects') or {}).items():
        t = p.get('tasks', {})
        run_rows.append({
            'name': p.get('name', pid),
            'color': _color(pid, _cfg().get(pid, {})),
            'content': t.get('content', {}),
            'landing': t.get('landing', {}),
            'recs': t.get('recommendations', {}),
            'deploy': t.get('deploy', {}),
            'status': p.get('status', ''),
        })
    health = seo_data.get('seo_health', {})
    body = """
    <div class=top><div><h1>Analítica / SEO</h1>
      <div class=sub>Todo en un solo lugar, detrás del login real. Arriba lo REAL del motor; abajo, analítica de ejemplo hasta conectar Search Console.</div></div></div>

    <h2 style="color:var(--accent);font-size:1rem;margin:.2rem 0 .8rem">✅ Última corrida del motor <span class=faint style="font-weight:400;font-size:.8rem">· dato real{% if report.generated_at %} · {{ report.generated_at[:16].replace('T',' ') }}{% endif %}</span></h2>
    {% if not run_rows %}<div class=card><p class=muted>Aún no hay reporte de corrida. Pulsa “▶ Lanzar corrida”.</p></div>{% endif %}
    <div class=grid>
    {% for r in run_rows %}
      <div class=card>
        <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.7rem">
          <span class=dot-s style="background:{{r.color}}"></span><strong>{{r.name}}</strong>
          <span class="pill {{'on' if r.status=='completed' else 'warn'}}" style="margin-left:auto">{{r.status or '—'}}</span>
        </div>
        <table>
          <tr><td class=muted>Contenido</td><td>{{r.content.get('count',0)}} nuevos · <span class=faint>{{r.content.get('blocked',0)}} apartados</span></td></tr>
          <tr><td class=muted>Landings</td><td>{{r.landing.get('count',0)}} ({{ r.landing.get('languages',[])|join(', ') }})</td></tr>
          <tr><td class=muted>Recomendaciones</td><td>{{r.recs.get('count',0)}} <span class=faint>{{'· con GSC' if r.recs.get('gsc') else '· sin GSC'}}</span></td></tr>
          <tr><td class=muted>Deploy</td><td><span class="pill {{'on' if r.deploy.get('status')=='dry-run' else ('dng' if r.deploy.get('status')=='error' else 'info')}}">{{r.deploy.get('status','—')}}</span>{% if r.deploy.get('landings') %} {{r.deploy.get('landings')}} pág.{% endif %}</td></tr>
        </table>
      </div>
    {% endfor %}
    </div>

    <div style="display:flex;align-items:center;gap:.6rem;margin:1.4rem 0 .8rem">
      <h2 style="color:var(--accent);font-size:1rem;margin:0">📊 Analítica SEO</h2>
      <span class="pill warn">datos de ejemplo</span>
      <span class=faint style="font-size:.8rem">se llenan solos al conectar Google Search Console</span>
    </div>

    <div class=kpis>
      <div class="kpi accent"><div class=lbl>Score SEO</div><div class=val>{{ health.get('total_score','—') }} <small>{{ health.get('grade','') }}</small></div></div>
      <div class=kpi><div class=lbl>Keywords rankeando</div><div class=val>{{ health.get('rankings_count','—') }}</div></div>
      <div class=kpi><div class=lbl>En top 10</div><div class=val>{{ health.get('top_10_count','—') }}</div></div>
      <div class=kpi><div class=lbl>Backlinks</div><div class=val>{{ health.get('backlinks_total','—') }}</div></div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem" class=cols>
      <div class=card><h2>Tráfico por idioma</h2><div style="height:220px"><canvas id=chLang></canvas></div></div>
      <div class=card><h2>Tráfico por país</h2><div style="height:220px"><canvas id=chCountry></canvas></div></div>
    </div>

    <div class=card>
      <h2>Rankings de keywords</h2>
      <table><tr><th>Keyword</th><th>Idioma</th><th>Posición</th><th>URL</th></tr>
      {% for k in seo_data.get('seo_rankings', [])[:12] %}
        <tr><td>{{k.keyword}}</td><td><span class="pill info">{{k.language}}</span></td>
        <td><span class="pill {{'on' if k.position<=10 else 'off'}}">#{{k.position}}</span></td>
        <td class=faint style="font-size:.78rem">{{k.url}}</td></tr>
      {% endfor %}</table>
    </div>

    <p class=faint style="font-size:.8rem">Fuente: <code>docs/data/*.json</code>. La analítica SEO reemplaza al dashboard estático de GitHub Pages — ahora vive aquí, con login real y junto al resto.</p>

    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
    <script>
    (function(){
      var lang = {{ (seo_data.get('traffic_by_language', {}))|tojson }};
      var country = {{ (seo_data.get('traffic_by_country', {}))|tojson }};
      var palette = ['#6d5efc','#38bdf8','#25c281','#f5a524','#f4436c','#8b7bff','#5b6178'];
      var txt = '#8a90a6';
      if (window.Chart){
        new Chart(document.getElementById('chLang'), {type:'doughnut',
          data:{labels:Object.keys(lang), datasets:[{data:Object.values(lang), backgroundColor:palette, borderColor:'#161a24', borderWidth:2}]},
          options:{plugins:{legend:{labels:{color:txt}}}, cutout:'62%'}});
        new Chart(document.getElementById('chCountry'), {type:'bar',
          data:{labels:Object.keys(country), datasets:[{data:Object.values(country), backgroundColor:'#6d5efc', borderRadius:6}]},
          options:{plugins:{legend:{display:false}}, scales:{x:{ticks:{color:txt},grid:{display:false}}, y:{ticks:{color:txt},grid:{color:'#252b3b'}}}}});
      }
    })();
    </script>
    <style>@media(max-width:760px){.cols{grid-template-columns:1fr!important}}</style>
    """
    return render(body, nav='seo', title='Analítica / SEO',
                  report=report, run_rows=run_rows, seo_data=seo_data,
                  content=content, health=health)


# ─────────────────────────── estado del sistema ───────────────────────────
@app.route('/system')
@login_required
def system():
    ints = integrations_status()
    live = sum(1 for i in ints if i['on'])
    lr = last_run_info()
    sched = _engine_cfg().get('schedule', {})
    body = """
    <div class=top><div><h1>Estado del sistema</h1>
      <div class=sub>Qué está VIVO vs. en modo fallback. Sin llave, el motor no se rompe: usa un plan B y no gasta.</div></div></div>

    <div class=kpis>
      <div class="kpi accent"><div class=lbl>Integraciones vivas</div><div class=val>{{live}}<small>/{{ints|length}}</small></div></div>
      <div class=kpi><div class=lbl>Última corrida</div><div class=val style="font-size:1rem">{{ lr.when if lr.exists else '—' }}</div></div>
      <div class=kpi><div class=lbl>Contraseña panel</div><div class=val style="font-size:1rem">env ✔</div></div>
    </div>

    <div class=card>
      <h2>🔌 Integraciones</h2>
      <table>
        <tr><th>Servicio</th><th>Estado</th><th>Qué hace / plan B</th><th>Variable</th></tr>
        {% for i in ints %}
        <tr>
          <td><strong>{{i.name}}</strong><div class=faint style="font-size:.76rem">{{i.vendor}}</div></td>
          <td><span class="pill {{'on' if i.on else 'warn'}}"><span class=dot-s style="background:{{'var(--ok)' if i.on else 'var(--warn)'}}"></span>{{ 'VIVO' if i.on else 'fallback' }}</span></td>
          <td style="font-size:.82rem">{{ i.live if i.on else i.fallback }}</td>
          <td><code>{{i.env}}</code></td>
        </tr>
        {% endfor %}
      </table>
      <p class=faint style="font-size:.8rem;margin-top:.7rem">Las llaves se ponen como variables de entorno (local) o en Environment (Render). Nunca en el código.</p>
    </div>

    <div class=card>
      <h2>🗓 Calendario del motor (UTC)</h2>
      <table>
        <tr><td class=muted>Generar contenido</td><td><code>{{ sched.get('content_generation','—') }}</code></td></tr>
        <tr><td class=muted>Campañas email</td><td><code>{{ sched.get('email_campaigns','—') }}</code></td></tr>
        <tr><td class=muted>Auditoría SEO</td><td><code>{{ sched.get('seo_audit','—') }}</code></td></tr>
        <tr><td class=muted>Reporte mensual</td><td><code>{{ sched.get('monthly_report','—') }}</code></td></tr>
      </table>
    </div>

    <div class=card>
      <h2>📜 Última corrida</h2>
      {% if lr.exists %}<div class=faint style="margin-bottom:.5rem">{{lr.when}}</div><pre>{{ lr.tail }}</pre>
      {% else %}<p class=muted>Aún no se ha lanzado ninguna corrida desde el panel. Usa “▶ Lanzar corrida”.</p>{% endif %}
    </div>
    """
    return render(body, nav='system', title='Estado del sistema',
                  ints=ints, live=live, lr=lr, sched=sched)


# ─────────────────────────── lanzar corrida ───────────────────────────
@app.route('/run', methods=['POST'])
@login_required
def run():
    LAST_RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    with open(LAST_RUN_LOG, 'w', encoding='utf-8') as log:
        subprocess.Popen([sys.executable, str(REPO_ROOT / 'scripts' / 'daily_run.py')],
                         stdout=log, stderr=subprocess.STDOUT, env=env, cwd=str(REPO_ROOT))
    flash("Corrida iniciada en segundo plano. Revisa “Estado del sistema” en un par de minutos.")
    return redirect(url_for('system'))


# ─────────────────────────────── reporte ───────────────────────────────
@app.route('/report/<project>')
@login_required
def report(project):
    cfg = _cfg().get(project)
    if cfg is None:
        abort(404)
    try:
        gen_report(project, cfg)
    except Exception:
        pass
    f = REPORTS_DIR / f"{project}.html"
    if f.exists():
        return Response(f.read_text(encoding='utf-8'), mimetype='text/html')
    flash("Aún no hay reporte generado para este proyecto.")
    return redirect(url_for('project', pid=project))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f"\nOrdinalMK Panel en http://localhost:{port}  (contrasena: env ORDINALMK_PANEL_PASSWORD)\n")
    app.run(host='0.0.0.0', port=port, debug=False)
