"""
OrdinalMK — Capa de recomendaciones del director.

El Hulk no solo informa: RECOMIENDA y prioriza acciones. Combina tres fuentes:
  - Medición (Search Console): páginas en la página 2 → empujar; muchas
    impresiones y CTR bajo → reescribir título/meta.
  - Inteligencia de keywords: huecos de alta intención → qué escribir a continuación.
  - Canibalización: páginas que compiten entre sí → consolidar/diferenciar.

Ordena por impacto (quick wins de ranking primero) y guarda un reporte por
proyecto. Funciona offline (sin GSC solo usa huecos + canibalización).
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))  # permite ejecutar el módulo suelto

from engine.measurement.search_console import (
    SearchConsole, pages_on_page_two, high_impressions_low_ctr)
from engine.intelligence.keywords import suggest_next
from engine.authority.cannibalization import detect as detect_cannibalization

CONTENT_ROOT = REPO_ROOT / "content"
REPORT_DIR = REPO_ROOT / "docs" / "data"


def generate(project_id: str, config: dict, gsc_rows: list = None,
             content_root: Path = CONTENT_ROOT) -> dict:
    """Genera recomendaciones accionables priorizadas para un proyecto."""
    config = config or {}
    recs = []

    # ── Medición (GSC) ── quick wins de ranking ──
    if gsc_rows is None:
        res = SearchConsole.from_config(config).query()
        gsc_available = res.get('available', False)
        gsc_rows = res.get('rows', [])
    else:
        gsc_available = True

    for r in pages_on_page_two(gsc_rows)[:10]:
        recs.append({
            'type': 'refresh_push', 'priority': 90, 'page': r.get('page'),
            'impressions': r.get('impressions', 0),
            'action': f"Página 2 (pos {round(float(r.get('position', 0)), 1)}): "
                      f"refresca y amplía para subir al top.",
        })
    for r in high_impressions_low_ctr(gsc_rows)[:10]:
        recs.append({
            'type': 'rewrite_meta', 'priority': 80, 'page': r.get('page'),
            'impressions': r.get('impressions', 0),
            'action': f"Muchas impresiones, CTR {round(float(r.get('ctr', 0)) * 100, 1)}%: "
                      f"reescribe título/meta para ganar clics.",
        })

    # ── Canibalización ──
    for c in detect_cannibalization(project_id, config, content_root=content_root):
        recs.append({
            'type': 'consolidate', 'priority': 70, 'language': c['language'],
            'slugs': c['slugs'],
            'action': f"Canibalización ({c['reason']}): consolida o diferencia estas páginas.",
        })

    # ── Huecos de contenido (qué escribir) ──
    for g in suggest_next(config, project_id, n=8, content_root=content_root):
        recs.append({
            'type': 'write', 'priority': 50 + g['priority'] * 5,
            'language': g['language'], 'keyword': g['keyword'], 'intent': g['intent'],
            'action': f"Escribe sobre '{g['keyword']}' (intención {g['intent']}).",
        })

    recs.sort(key=lambda x: x['priority'], reverse=True)
    return {'project': project_id, 'gsc_available': gsc_available,
            'count': len(recs), 'recommendations': recs}


def generate_and_save(project_id: str, config: dict,
                      report_dir: Path = REPORT_DIR, **kwargs) -> dict:
    out = generate(project_id, config, **kwargs)
    report_dir.mkdir(parents=True, exist_ok=True)
    with open(report_dir / f"recommendations_{project_id}.json", 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)
    return out


if __name__ == "__main__":
    import tempfile, shutil

    tmp = Path(tempfile.mkdtemp(prefix='recs_'))
    try:
        cr = tmp / "content"
        (cr / 'demo').mkdir(parents=True)
        # Un artículo publicado + dos que canibalizan
        arts = [
            {'slug': 'excel-x', 'title': 'Automatiza Excel', 'language': 'es',
             'status': 'published', 'keywords': ['excel', 'reportes']},
            {'slug': 'fact-a', 'title': 'Facturar', 'language': 'es',
             'status': 'published', 'keywords': ['facturación', 'ia']},
            {'slug': 'fact-b', 'title': 'Facturación fácil', 'language': 'es',
             'status': 'published', 'keywords': ['facturación', 'cfdi']},
        ]
        for a in arts:
            (cr / 'demo' / f"{a['slug']}.json").write_text(
                json.dumps(a, ensure_ascii=False), encoding='utf-8')

        cfg = {'domain': 'demo.com', 'seo': {'target_keywords': {'es': [
            'software de facturación cfdi',    # transaccional, hueco
            'qué es la facturación electrónica',  # informacional, hueco
            'automatizar excel',               # cubierto
        ]}}}
        gsc = [
            {'page': '/lp/es/fact-a', 'query': 'facturación', 'impressions': 900,
             'ctr': 0.006, 'position': 13.4},  # página 2 + ctr bajo
        ]
        out = generate('demo', cfg, gsc_rows=gsc, content_root=cr)
        types = [r['type'] for r in out['recommendations']]
        print('recomendaciones (por prioridad):')
        for r in out['recommendations']:
            print('  ', r['priority'], r['type'], '-', r['action'][:60])
        assert types[0] == 'refresh_push', 'el quick win de ranking debe ir primero'
        assert 'consolidate' in types, 'debe detectar canibalización fact-a/fact-b'
        assert any(r['type'] == 'write' and 'cfdi' in r.get('keyword', '') for r in out['recommendations'])
        # el hueco transaccional debe rankear por encima del informacional
        writes = [r for r in out['recommendations'] if r['type'] == 'write']
        assert writes[0]['intent'] == 'transactional'
        print('OK: recomendaciones combinadas y priorizadas (medición > canibalización > huecos)')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
