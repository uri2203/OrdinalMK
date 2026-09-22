"""
OrdinalMK — Motor de refresco de contenido.

No basta con recomendar "actualiza esto": este módulo lo EJECUTA. Detecta
contenido que decae y lo reescribe/amplía para recuperar ranking.

Señales de decaimiento:
  - Cayó en el ranking (engine.measurement.serp_tracker.movers -> 'down').
  - Antigüedad: publicado hace más de N días (por defecto 180).

Refresco: con IA reescribe/expande manteniendo el tema; sin IA (fallback) marca
`needs_ai`, actualiza `updated_at`, sube `version` y añade una nota de frescura,
sin romper. Funciones de detección puras y testeables.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

CONTENT_ROOT = REPO_ROOT / "content"
CONTENT_MODEL = os.environ.get("ORDINALMK_CONTENT_MODEL", "claude-opus-4-8")


def _age_days(published_at: str, now: datetime = None) -> int:
    if not published_at:
        return 10**6  # sin fecha -> tratar como muy viejo
    now = now or datetime.now(timezone.utc)
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S.%f'):
        try:
            d = datetime.strptime(published_at[:len(fmt) + 6 if '%f' in fmt else len(fmt)].rstrip('Z'), fmt)
            return (now.replace(tzinfo=None) - d).days
        except ValueError:
            continue
    try:
        d = datetime.fromisoformat(published_at.replace('Z', ''))
        return (now.replace(tzinfo=None) - d.replace(tzinfo=None)).days
    except Exception:
        return 10**6


def detect_stale(articles: list, dropped_keywords: list = None,
                 max_age_days: int = 180, now: datetime = None) -> list:
    """Devuelve [{slug, reasons[]}] de artículos que conviene refrescar. Puro."""
    dropped = {k.lower() for k in (dropped_keywords or [])}
    out = []
    for a in articles:
        reasons = []
        age = _age_days(a.get('published_at') or a.get('created_at') or '', now)
        if age >= max_age_days:
            reasons.append(f'antiguo ({age}d)')
        kws = {str(k).lower() for k in (a.get('keywords') or [])}
        title = (a.get('title') or '').lower()
        if dropped and (kws & dropped or any(dk in title for dk in dropped)):
            reasons.append('cayó en ranking')
        if reasons:
            out.append({'slug': a.get('slug', ''), 'title': a.get('title', ''),
                        'reasons': reasons, 'age_days': age})
    # primero los que cayeron en ranking, luego por antigüedad
    out.sort(key=lambda x: ('cayó en ranking' not in x['reasons'], -x['age_days']))
    return out


def _ai_available() -> bool:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_AUTH_TOKEN'))


def refresh_article(article: dict, config: dict = None) -> dict:
    """Refresca un artículo. IA si hay; si no, marca needs_ai + nota de frescura."""
    out = dict(article)
    now = datetime.now(timezone.utc).isoformat()
    out['version'] = int(out.get('version', 1)) + 1
    out['updated_at'] = now
    if _ai_available():
        try:
            out['body'] = _ai_rewrite(article, config or {})
            out['refresh_mode'] = 'ai'
            out.pop('needs_ai', None)
            return out
        except Exception:
            pass
    body = (out.get('body') or out.get('content') or '').rstrip()
    year = datetime.now().year
    note = f"\n\n> Actualizado en {year}: revisado y vigente."
    if 'Actualizado en' not in body:
        out['body'] = body + note
    out['refresh_mode'] = 'fallback'
    out['needs_ai'] = True
    return out


def _ai_rewrite(article, config):
    import anthropic
    client = anthropic.Anthropic()
    lang = article.get('language', 'es')
    voice = (config.get('governance', {}) or {}).get('brand_voice', 'claro y directo')
    sysp = (f"Reescribe y AMPLÍA en '{lang}' este artículo manteniendo el tema y el título. "
            f"Tono {voice}. Añade datos concretos, ejemplos y una sección de preguntas "
            f"frecuentes. Devuelve solo el cuerpo en Markdown.")
    resp = client.messages.create(model=CONTENT_MODEL, max_tokens=2500, system=sysp,
                                  messages=[{"role": "user",
                                             "content": f"Título: {article.get('title','')}\n\n"
                                                        f"{article.get('body','')[:3000]}"}])
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def _load_articles(project_id: str, content_root: Path) -> list:
    d = content_root / project_id
    arts = []
    if not d.exists():
        return arts
    for f in sorted(d.glob('*.json')):
        try:
            arts.append(json.loads(f.read_text(encoding='utf-8')))
        except Exception:
            continue
    return arts


def run(project_id: str, config: dict, content_root: Path = CONTENT_ROOT,
        dropped_keywords: list = None, max_age_days: int = 180,
        execute: bool = True) -> dict:
    """Detecta y (si execute) refresca, guardando el artículo actualizado."""
    articles = _load_articles(project_id, content_root)
    stale = detect_stale(articles, dropped_keywords, max_age_days)
    refreshed = []
    if execute:
        by_slug = {a.get('slug'): a for a in articles}
        for s in stale:
            a = by_slug.get(s['slug'])
            if not a:
                continue
            upd = refresh_article(a, config)
            (content_root / project_id / f"{s['slug']}.json").write_text(
                json.dumps(upd, ensure_ascii=False, indent=2), encoding='utf-8')
            refreshed.append({'slug': s['slug'], 'mode': upd.get('refresh_mode'),
                              'version': upd['version']})
    return {'project': project_id, 'stale': len(stale), 'detail': stale,
            'refreshed': refreshed}


if __name__ == "__main__":
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp(prefix='refresh_'))
    try:
        old_date = (datetime.now(timezone.utc) - timedelta(days=400)).strftime('%Y-%m-%d')
        new_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        arts = [
            {'slug': 'viejo', 'title': 'Guía facturación', 'language': 'es',
             'published_at': old_date, 'keywords': ['facturación'],
             'body': '# Guía\nContenido de la guía.'},
            {'slug': 'reciente-cae', 'title': 'IA local', 'language': 'es',
             'published_at': new_date, 'keywords': ['ia local'],
             'body': '# IA local\nTexto.'},
            {'slug': 'reciente-ok', 'title': 'Excel', 'language': 'es',
             'published_at': new_date, 'keywords': ['excel'], 'body': '# Excel\nTexto.'},
        ]

        # 1) detección: viejo (antigüedad) + reciente-cae (ranking) ; reciente-ok NO
        stale = detect_stale(arts, dropped_keywords=['ia local'])
        slugs = [s['slug'] for s in stale]
        print('a refrescar:', slugs)
        assert 'viejo' in slugs and 'reciente-cae' in slugs and 'reciente-ok' not in slugs
        # el que cayó en ranking va primero
        assert stale[0]['slug'] == 'reciente-cae', 'ranking primero'

        # 2) refresh fallback (sin IA): sube versión, updated_at, nota, needs_ai
        os.environ.pop('ANTHROPIC_API_KEY', None); os.environ.pop('ANTHROPIC_AUTH_TOKEN', None)
        upd = refresh_article(arts[0])
        assert upd['version'] == 2 and upd['updated_at'] and upd['needs_ai'] is True
        assert 'Actualizado en' in upd['body']

        # 3) run ejecuta y guarda solo los stale
        cr = tmp / 'content'
        (cr / 'demo').mkdir(parents=True)
        for a in arts:
            (cr / 'demo' / f"{a['slug']}.json").write_text(json.dumps(a, ensure_ascii=False), encoding='utf-8')
        res = run('demo', {}, content_root=cr, dropped_keywords=['ia local'])
        print('refrescados:', [(r['slug'], r['mode'], r['version']) for r in res['refreshed']])
        assert res['stale'] == 2 and len(res['refreshed']) == 2
        saved = json.loads((cr / 'demo' / 'viejo.json').read_text(encoding='utf-8'))
        assert saved['version'] == 2, 'debe persistir la versión'
        # el ok no se tocó
        ok = json.loads((cr / 'demo' / 'reciente-ok.json').read_text(encoding='utf-8'))
        assert 'version' not in ok
        print('OK: refresh (detección antigüedad+ranking + refresh fallback + run persiste)')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
