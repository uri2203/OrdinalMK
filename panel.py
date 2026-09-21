"""
OrdinalMK — Panel de control (backend Flask).

Un solo lugar para EVALUAR y CONTROLAR el marketing de todos los proyectos:
  - Resumen por proyecto (gobierno, prospección, contenido, ingresos).
  - Revisión de contenido fiscal (_held): aprobar / rechazar.
  - Prospectos por proyecto: ver, aprobar y enviar outreach.
  - Lanzar la corrida del motor (en segundo plano).
  - Reportes y datos por proyecto.

Login server-side REAL (sesión + contraseña por env), a diferencia del gate JS
del dashboard estático. Corre en un servidor (no en GitHub Pages).

    ORDINALMK_PANEL_PASSWORD=tu-clave  python panel.py     # http://localhost:5001
"""

import hashlib
import os
import subprocess
import sys
from functools import wraps
from pathlib import Path

from flask import (Flask, session, request, redirect, url_for,
                   render_template_string, flash, Response, abort)

REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))

from config.projects import load_config
from engine import governance
from engine.prospecting import icp as icp_mod, store as pstore, pipeline as ppipeline, outreach
from engine.review import queue as review_queue
from engine.reporting.report import generate as gen_report
from engine.measurement.conversions import summary as conv_summary

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ordinalmk-panel-dev')

PANEL_PASSWORD = os.environ.get('ORDINALMK_PANEL_PASSWORD', 'ordinalmk')
REPORTS_DIR = REPO_ROOT / "reports" / "generated"
LAST_RUN_LOG = REPO_ROOT / "reports" / "panel_last_run.log"


def _cfg():
    return load_config().get('projects', {})


def login_required(f):
    @wraps(f)
    def wrapper(*a, **k):
        if not session.get('auth'):
            return redirect(url_for('login', next=request.path))
        return f(*a, **k)
    return wrapper


# ────────────────────────── plantillas ──────────────────────────
LAYOUT = """
<!doctype html><html lang=es><head><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>OrdinalMK — Panel</title>
<style>
 :root{--bg:#0f1117;--surface:#1a1d27;--line:#2d3140;--text:#e4e6f0;--muted:#8b8fa3;--accent:#6366f1;--ok:#22c55e;--warn:#f59e0b;--danger:#ef4444}
 *{box-sizing:border-box;margin:0;padding:0} body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--text);line-height:1.5}
 .nav{background:var(--surface);border-bottom:1px solid var(--line);padding:.8rem 1.2rem;display:flex;gap:1rem;align-items:center;flex-wrap:wrap}
 .nav a{color:var(--muted);text-decoration:none;font-size:.9rem} .nav a:hover{color:var(--text)}
 .nav .brand{color:var(--accent);font-weight:700;margin-right:auto}
 .wrap{max-width:960px;margin:0 auto;padding:1.5rem 1.2rem}
 h1{font-size:1.4rem;margin-bottom:1rem} h2{font-size:1.05rem;margin:1.5rem 0 .6rem;color:var(--accent)}
 table{width:100%;border-collapse:collapse;font-size:.88rem} th,td{text-align:left;padding:.5rem;border-bottom:1px solid var(--line)}
 th{color:var(--muted);font-weight:500}
 .card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:1rem 1.2rem;margin-bottom:1rem}
 .pill{display:inline-block;font-size:.72rem;padding:2px 9px;border-radius:100px}
 .on{background:rgba(34,197,94,.15);color:var(--ok)} .off{background:rgba(139,143,163,.15);color:var(--muted)}
 .warn{background:rgba(245,158,11,.15);color:var(--warn)}
 button,.btn{background:var(--accent);color:#fff;border:none;border-radius:8px;padding:.4rem .9rem;font-size:.85rem;cursor:pointer;text-decoration:none;display:inline-block}
 button.sec{background:transparent;border:1px solid var(--line);color:var(--text)}
 button.dng{background:var(--danger)} .flash{background:rgba(99,102,241,.15);border:1px solid var(--accent);border-radius:8px;padding:.6rem 1rem;margin-bottom:1rem;font-size:.9rem}
 input{background:var(--bg);border:1px solid var(--line);color:var(--text);border-radius:8px;padding:.6rem;font-size:1rem;width:100%}
 a.proj{color:var(--text)} .muted{color:var(--muted);font-size:.85rem}
</style></head><body>
{% if session.get('auth') %}
<div class=nav>
  <a class=brand href="{{url_for('home')}}">● OrdinalMK</a>
  <a href="{{url_for('home')}}">Resumen</a>
  <a href="{{url_for('review')}}">Revisión</a>
  <a href="{{url_for('home')}}#proyectos">Proyectos</a>
  <form method=post action="{{url_for('run')}}" style="display:inline"><button class=sec>▶ Lanzar corrida</button></form>
  <a href="{{url_for('logout')}}">Salir</a>
</div>
{% endif %}
<div class=wrap>
 {% with msgs = get_flashed_messages() %}{% for m in msgs %}<div class=flash>{{m}}</div>{% endfor %}{% endwith %}
 {{ body|safe }}
</div></body></html>
"""


def render(body_html, **ctx):
    return render_template_string(LAYOUT, body=render_template_string(body_html, **ctx))


# ────────────────────────── auth ──────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password', '') == PANEL_PASSWORD:
            session['auth'] = True
            return redirect(request.args.get('next') or url_for('home'))
        flash('Contraseña incorrecta.')
    body = """<h1>OrdinalMK — Panel</h1>
    <div class=card style="max-width:340px">
      <form method=post>
        <p class=muted style="margin-bottom:.6rem">Acceso restringido</p>
        <input type=password name=password placeholder=Contraseña autofocus>
        <button style="margin-top:.8rem;width:100%">Entrar</button>
      </form>
    </div>"""
    return render(body)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ────────────────────────── home / resumen ──────────────────────────
@app.route('/')
@login_required
def home():
    rows = []
    for pid, cfg in _cfg().items():
        pc = pstore.counts(pid)
        held = len(review_queue.list_held(pid))
        conv = conv_summary(pid)['totals']
        rows.append({
            'id': pid, 'name': cfg.get('name', pid),
            'enabled': governance.project_enabled(cfg),
            'priority': governance.project_priority(cfg),
            'prospecting': icp_mod.prospecting_enabled(cfg),
            'prospects': pc.get('total', 0), 'aprobados': pc.get('aprobado', 0),
            'held': held, 'revenue': conv.get('revenue', 0), 'paid': conv.get('paid', 0),
        })
    body = """
    <h1 id=proyectos>Resumen de proyectos</h1>
    <div class=card>
    <table>
      <tr><th>Proyecto</th><th>Estado</th><th>Prosp.</th><th>Aprob.</th><th>Revisión</th><th>Ingreso</th><th></th></tr>
      {% for r in rows %}
      <tr>
        <td><strong>{{r.name}}</strong><div class=muted>prioridad {{r.priority}}</div></td>
        <td>
          <span class="pill {{'on' if r.enabled else 'off'}}">{{'activo' if r.enabled else 'pausado'}}</span>
          <span class="pill {{'on' if r.prospecting else 'off'}}">prospección {{'on' if r.prospecting else 'off'}}</span>
        </td>
        <td>{{r.prospects}}</td><td>{{r.aprobados}}</td>
        <td>{% if r.held %}<span class="pill warn">{{r.held}} pend.</span>{% else %}0{% endif %}</td>
        <td>${{r.revenue}} <span class=muted>({{r.paid}})</span></td>
        <td><a class=btn href="{{url_for('prospects', project=r.id)}}">Prospectos</a>
            <a class="btn sec" href="{{url_for('report', project=r.id)}}">Reporte</a></td>
      </tr>
      {% endfor %}
    </table>
    </div>
    <p class=muted>Revisión = contenido fiscal esperando aprobación humana. La corrida (botón arriba) genera contenido, publica, prospecta y mide para los proyectos activos.</p>
    """
    return render(body, rows=rows)


# ────────────────────────── revisión de contenido (_held) ──────────────────────────
@app.route('/review')
@login_required
def review():
    blocks = []
    for pid, cfg in _cfg().items():
        items = review_queue.list_held(pid)
        if items:
            blocks.append({'id': pid, 'name': cfg.get('name', pid), 'items': items})
    body = """
    <h1>Revisión de contenido fiscal</h1>
    {% if not blocks %}<div class=card>Nada pendiente. Todo limpio. ✅</div>{% endif %}
    {% for b in blocks %}
    <div class=card><h2>{{b.name}}</h2>
    <table><tr><th>Artículo</th><th>Idioma</th><th>Motivo</th><th></th></tr>
    {% for it in b['items'] %}
      <tr><td>{{it.title or it.slug}}</td><td>{{it.language}}</td>
      <td class=muted>{{it.flags|join(', ') or it.reasons|join('; ')}}</td>
      <td>
        <form method=post action="{{url_for('review_action', project=b.id, slug=it.slug, action='approve')}}" style="display:inline"><button>Aprobar</button></form>
        <form method=post action="{{url_for('review_action', project=b.id, slug=it.slug, action='reject')}}" style="display:inline"><button class=dng>Rechazar</button></form>
      </td></tr>
    {% endfor %}
    </table></div>
    {% endfor %}
    """
    return render(body, blocks=blocks)


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


# ────────────────────────── prospectos ──────────────────────────
@app.route('/prospects/<project>')
@login_required
def prospects(project):
    cfg = _cfg().get(project)
    if cfg is None:
        abort(404)
    counts = pstore.counts(project)
    rows = pstore.load(project)
    body = """
    <h1>Prospectos — {{name}}</h1>
    <div class=card>
      <p>{{counts.get('total',0)}} prospectos · nuevos {{counts.get('nuevo',0)}} · aprobados {{counts.get('aprobado',0)}} · contactados {{counts.get('contactado',0)}}</p>
      <form method=post action="{{url_for('prospects_action', project=project, action='discover')}}" style="display:inline"><button class=sec>🔍 Descubrir</button></form>
      <form method=post action="{{url_for('prospects_action', project=project, action='approve_all')}}" style="display:inline"><button>Aprobar nuevos</button></form>
      <form method=post action="{{url_for('prospects_action', project=project, action='send')}}" style="display:inline"><button>✉ Enviar a aprobados</button></form>
    </div>
    <div class=card><table>
      <tr><th>Negocio</th><th>Correo</th><th>Estado</th></tr>
      {% for r in rows[:100] %}
      <tr><td>{{r.get('name','')}}</td><td class=muted>{{r.get('email','')}}</td>
      <td><span class="pill {{'on' if r.get('status')=='convertido' else 'off'}}">{{r.get('status')}}</span></td></tr>
      {% endfor %}
    </table>{% if not rows %}<p class=muted>Sin prospectos aún. Usa "Descubrir" (requiere GOOGLE_PLACES_API_KEY).</p>{% endif %}</div>
    <a href="{{url_for('home')}}" class="btn sec">← Volver</a>
    """
    return render(body, name=cfg.get('name', project), project=project, counts=counts, rows=rows)


@app.route('/prospects/<project>/<action>', methods=['POST'])
@login_required
def prospects_action(project, action):
    cfg = _cfg().get(project, {})
    if action == 'discover':
        r = ppipeline.discover_project(project, cfg)
        flash(f"Descubrir: {r.get('nuevos_guardados', r.get('reason','—'))} nuevos" if r.get('available') else f"Descubrir: {r.get('reason','no disponible')}")
    elif action == 'approve_all':
        n = ppipeline.approve_all_new(project)
        flash(f"Aprobados {n} prospectos nuevos.")
    elif action == 'send':
        r = outreach.send_to_approved(project, cfg)
        flash(f"Outreach: {r.get('enviados',0)} enviados, {r.get('encolados',0)} en cola (tope {r.get('tope_dia','?')}/día)" if not r.get('error') else r['error'])
    return redirect(url_for('prospects', project=project))


# ────────────────────────── lanzar corrida ──────────────────────────
@app.route('/run', methods=['POST'])
@login_required
def run():
    LAST_RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    with open(LAST_RUN_LOG, 'w', encoding='utf-8') as log:
        subprocess.Popen([sys.executable, str(REPO_ROOT / 'scripts' / 'daily_run.py')],
                         stdout=log, stderr=subprocess.STDOUT, env=env, cwd=str(REPO_ROOT))
    flash("Corrida iniciada en segundo plano. Revisa los reportes en un par de minutos.")
    return redirect(url_for('home'))


# ────────────────────────── reporte ──────────────────────────
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
    return render("<h1>Sin reporte aún</h1><a class='btn sec' href='{{url_for(\"home\")}}'>← Volver</a>")


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f"\nOrdinalMK Panel en http://localhost:{port}  (contrasena: env ORDINALMK_PANEL_PASSWORD)\n")
    app.run(host='0.0.0.0', port=port, debug=False)
