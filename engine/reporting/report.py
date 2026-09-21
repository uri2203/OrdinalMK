"""
OrdinalMK — Reporte periódico por proyecto (para el director).

Reúne el estado de marketing de un proyecto en un reporte legible: contenido
publicado / en revisión / bloqueado, canibalización, medición (si hay GSC) y las
recomendaciones priorizadas. Guarda JSON + HTML en reports/ (fuera de Pages
público, porque contiene datos internos).

Funciones puras sobre archivos (rutas override) → testeable offline.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine.authority.cannibalization import detect as detect_cannibalization
from engine.intelligence.recommendations import generate as gen_recommendations
from engine.measurement.conversions import summary as conversions_summary

CONTENT_ROOT = REPO_ROOT / "content"
REPORTS_DIR = REPO_ROOT / "reports" / "generated"


def _content_stats(project_id: str, content_root: Path) -> dict:
    published_by_lang = {}
    held = 0
    d = content_root / project_id
    if d.exists():
        for f in d.glob('*.json'):
            try:
                a = json.loads(f.read_text(encoding='utf-8'))
            except Exception:
                continue
            if a.get('status') == 'published':
                lang = a.get('language', '?')
                published_by_lang[lang] = published_by_lang.get(lang, 0) + 1
        held_dir = d / '_held'
        if held_dir.exists():
            held = len(list(held_dir.glob('*.json')))
    return {
        'published_by_lang': published_by_lang,
        'published_total': sum(published_by_lang.values()),
        'held_or_blocked': held,
    }


def generate(project_id: str, config: dict, content_root: Path = CONTENT_ROOT,
             reports_dir: Path = REPORTS_DIR) -> dict:
    config = config or {}
    stats = _content_stats(project_id, content_root)
    cannibalization = detect_cannibalization(project_id, config, content_root=content_root)
    recs = gen_recommendations(project_id, config, content_root=content_root)
    conv = conversions_summary(project_id)

    report = {
        'project': project_id,
        'name': config.get('name', project_id),
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'content': stats,
        'cannibalization': len(cannibalization),
        'gsc_available': recs.get('gsc_available', False),
        'conversions': conv['totals'],
        'trial_to_paid': conv['trial_to_paid'],
        'recommendations': recs.get('recommendations', [])[:10],
    }

    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / f"{project_id}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    (reports_dir / f"{project_id}.html").write_text(
        _render_html(report), encoding='utf-8')
    return report


def _render_html(r: dict) -> str:
    langs = ''.join(
        f'<li>{lang}: {n}</li>' for lang, n in r['content']['published_by_lang'].items()
    ) or '<li>—</li>'
    recs = ''.join(
        f'<li><strong>[{x.get("type")}]</strong> {x.get("action","")}</li>'
        for x in r['recommendations']
    ) or '<li>Sin recomendaciones aún.</li>'
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<meta name="robots" content="noindex, nofollow">
<title>Reporte — {r['name']}</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#0f1117;color:#e4e6f0;max-width:760px;margin:0 auto;padding:2rem;line-height:1.6}}
 h1{{color:#6366f1}} h2{{color:#8b8fa3;font-size:1rem;margin-top:1.5rem}}
 .cards{{display:flex;gap:12px;flex-wrap:wrap;margin:1rem 0}}
 .card{{background:#1a1d27;border:1px solid #2d3140;border-radius:12px;padding:1rem 1.2rem;min-width:130px}}
 .num{{font-size:1.8rem;font-weight:700}} .lbl{{color:#8b8fa3;font-size:.8rem}}
 ul{{margin:.5rem 0 .5rem 1.2rem}} li{{margin-bottom:.3rem}}
</style></head><body>
 <h1>{r['name']} — reporte de marketing</h1>
 <p style="color:#8b8fa3">Generado: {r['generated_at']}</p>
 <div class="cards">
   <div class="card"><div class="num">{r['content']['published_total']}</div><div class="lbl">artículos publicados</div></div>
   <div class="card"><div class="num">{r['content']['held_or_blocked']}</div><div class="lbl">en revisión / bloqueados</div></div>
   <div class="card"><div class="num">{r['cannibalization']}</div><div class="lbl">canibalización</div></div>
   <div class="card"><div class="num">{'Sí' if r['gsc_available'] else 'No'}</div><div class="lbl">medición GSC</div></div>
   <div class="card"><div class="num">${r['conversions']['revenue']}</div><div class="lbl">ingreso ({r['conversions']['paid']} pagos)</div></div>
   <div class="card"><div class="num">{round(r['trial_to_paid']*100)}%</div><div class="lbl">prueba → pago</div></div>
 </div>
 <h2>Publicados por idioma</h2><ul>{langs}</ul>
 <h2>Recomendaciones del director</h2><ul>{recs}</ul>
</body></html>"""


if __name__ == "__main__":
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp(prefix='report_'))
    try:
        cr = tmp / "content"
        rd = tmp / "reports"
        (cr / 'demo').mkdir(parents=True)
        (cr / 'demo' / '_held').mkdir()
        for a in [
            {'slug': 'a', 'title': 'Facturar', 'language': 'es', 'status': 'published', 'keywords': ['facturación']},
            {'slug': 'b', 'title': 'Excel IA', 'language': 'es', 'status': 'published', 'keywords': ['excel']},
        ]:
            (cr / 'demo' / f"{a['slug']}.json").write_text(json.dumps(a, ensure_ascii=False), encoding='utf-8')
        (cr / 'demo' / '_held' / 'h.json').write_text('{}', encoding='utf-8')

        cfg = {'name': 'Demo', 'domain': 'demo.com',
               'seo': {'target_keywords': {'es': ['software de facturación cfdi']}}}
        rep = generate('demo', cfg, content_root=cr, reports_dir=rd)
        print('reporte:', {k: rep[k] for k in ('content', 'cannibalization', 'gsc_available')})
        assert rep['content']['published_total'] == 2
        assert rep['content']['held_or_blocked'] == 1
        assert (rd / 'demo.json').exists() and (rd / 'demo.html').exists()
        assert any(x['type'] == 'write' for x in rep['recommendations'])
        print('OK: reporte generado (JSON + HTML), conteos y recomendaciones')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
