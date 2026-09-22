"""
OrdinalMK — SERP tracker (posiciones reales en el tiempo).

Guarda un histórico de posiciones por keyword para SABER si subes o bajas, y
detecta caídas (para alertar y disparar refresco). Fuentes de posición:

  - SerpAPI (SERPAPI_KEY) o DataForSEO si hay credenciales.
  - Si no, usa las filas de Google Search Console (engine.measurement.search_console),
    que ya tiene su propio fallback.

Histórico: reports/serp/<project>.jsonl (una línea por medición). Las funciones
de agregación (latest/movers) son puras y testeables sobre filas inyectadas.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

SERP_DIR = REPO_ROOT / "reports" / "serp"


def _today() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def record(project_id: str, rows: list, serp_dir: Path = SERP_DIR, date: str = None) -> dict:
    """Guarda una medición: rows = [{keyword, position, url, language?}]."""
    serp_dir.mkdir(parents=True, exist_ok=True)
    date = date or _today()
    n = 0
    with open(serp_dir / f"{project_id}.jsonl", 'a', encoding='utf-8') as f:
        for r in rows:
            kw = (r.get('keyword') or r.get('query') or '').strip()
            if not kw:
                continue
            f.write(json.dumps({
                'date': date, 'keyword': kw,
                'position': round(float(r.get('position', 0) or 0), 1),
                'url': r.get('url') or r.get('page') or '',
                'language': r.get('language', ''),
            }, ensure_ascii=False) + "\n")
            n += 1
    return {'project': project_id, 'recorded': n, 'date': date}


def load(project_id: str, serp_dir: Path = SERP_DIR) -> list:
    f = serp_dir / f"{project_id}.jsonl"
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def history(project_id: str, keyword: str, serp_dir: Path = SERP_DIR) -> list:
    kw = keyword.lower().strip()
    rows = [r for r in load(project_id, serp_dir) if r['keyword'].lower() == kw]
    rows.sort(key=lambda x: x['date'])
    return [{'date': r['date'], 'position': r['position']} for r in rows]


def _dates(rows: list) -> list:
    return sorted({r['date'] for r in rows})


def latest(project_id: str, serp_dir: Path = SERP_DIR) -> dict:
    """Última posición conocida por keyword."""
    rows = load(project_id, serp_dir)
    out = {}
    for r in sorted(rows, key=lambda x: x['date']):
        out[r['keyword']] = r  # el último por fecha gana
    return out


def movers(project_id: str, serp_dir: Path = SERP_DIR, threshold: float = 3.0) -> dict:
    """Compara las dos ULTIMAS fechas: keywords que suben/bajan >= threshold.
    Posición menor = mejor, así que delta positivo = mejoró."""
    rows = load(project_id, serp_dir)
    dates = _dates(rows)
    if len(dates) < 2:
        return {'up': [], 'down': [], 'reason': 'se necesitan 2 mediciones'}
    prev_d, cur_d = dates[-2], dates[-1]
    prev = {r['keyword']: r['position'] for r in rows if r['date'] == prev_d}
    cur = {r['keyword']: r['position'] for r in rows if r['date'] == cur_d}
    up, down = [], []
    for kw, pos in cur.items():
        if kw in prev:
            delta = prev[kw] - pos  # bajó de posición número = subió en ranking
            if delta >= threshold:
                up.append({'keyword': kw, 'from': prev[kw], 'to': pos, 'delta': round(delta, 1)})
            elif delta <= -threshold:
                down.append({'keyword': kw, 'from': prev[kw], 'to': pos, 'delta': round(delta, 1)})
    up.sort(key=lambda x: -x['delta'])
    down.sort(key=lambda x: x['delta'])
    return {'up': up, 'down': down, 'prev_date': prev_d, 'cur_date': cur_d}


def _fetch_serpapi(keywords: list, domain: str, lang: str, country: str) -> list:
    key = os.environ.get('SERPAPI_KEY')
    if not key:
        return []
    try:
        import requests
        rows = []
        for kw in keywords:
            r = requests.get("https://serpapi.com/search", params={
                'q': kw, 'hl': lang, 'gl': country, 'api_key': key, 'num': 20}, timeout=20)
            data = r.json()
            for res in data.get('organic_results', []):
                if domain and domain in (res.get('link') or ''):
                    rows.append({'keyword': kw, 'position': res.get('position', 0),
                                 'url': res.get('link'), 'language': lang})
                    break
        return rows
    except Exception:
        return []


def track(project_id: str, config: dict, keywords: list = None,
          rows: list = None, serp_dir: Path = SERP_DIR) -> dict:
    """Obtiene posiciones y las registra. `rows` inyectable para test.
    Orden de fuentes: rows dados -> SerpAPI -> GSC (con su fallback)."""
    domain = (config.get('domain') or '').replace('https://', '').replace('http://', '').strip('/')
    lang = config.get('primary_language', 'es')
    if rows is None:
        kws = keywords or []
        rows = _fetch_serpapi(kws, domain, lang, 'mx') if kws else []
        if not rows:
            try:
                from engine.measurement.search_console import SearchConsole
                res = SearchConsole.from_config(config).query()
                rows = [{'keyword': r.get('query'), 'position': r.get('position'),
                         'url': r.get('page')} for r in res.get('rows', [])]
            except Exception:
                rows = []
    return record(project_id, rows, serp_dir)


if __name__ == "__main__":
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp(prefix='serp_'))
    try:
        pid = 'demo'
        # dia 1
        record(pid, [
            {'keyword': 'software facturación cfdi', 'position': 14, 'url': 'https://x.com/a'},
            {'keyword': 'ia local para empresas', 'position': 8, 'url': 'https://x.com/b'},
            {'keyword': 'automatizar excel', 'position': 5, 'url': 'https://x.com/c'},
        ], serp_dir=tmp, date='2026-09-01')
        # dia 2: cfdi mejora mucho (14->6), excel cae (5->11), ia igual
        record(pid, [
            {'keyword': 'software facturación cfdi', 'position': 6, 'url': 'https://x.com/a'},
            {'keyword': 'ia local para empresas', 'position': 8, 'url': 'https://x.com/b'},
            {'keyword': 'automatizar excel', 'position': 11, 'url': 'https://x.com/c'},
        ], serp_dir=tmp, date='2026-09-02')

        h = history(pid, 'software facturación cfdi', serp_dir=tmp)
        print('histórico cfdi:', h)
        assert [x['position'] for x in h] == [14, 6]

        lt = latest(pid, serp_dir=tmp)
        assert lt['automatizar excel']['position'] == 11

        m = movers(pid, serp_dir=tmp, threshold=3)
        print('subieron:', [(x['keyword'][:20], x['delta']) for x in m['up']])
        print('bajaron:', [(x['keyword'][:20], x['delta']) for x in m['down']])
        assert any(x['keyword'].startswith('software') for x in m['up']), 'cfdi debe subir'
        assert any(x['keyword'] == 'automatizar excel' for x in m['down']), 'excel debe caer'
        assert not any(x['keyword'] == 'ia local para empresas' for x in m['up'] + m['down'])

        # una sola medición -> sin movers
        one = movers('nuevo', serp_dir=tmp)
        assert one['up'] == [] and 'reason' in one

        # track con rows inyectadas
        track('demo2', {'domain': 'x.com'}, rows=[{'keyword': 'k', 'position': 3}], serp_dir=tmp)
        assert latest('demo2', serp_dir=tmp)['k']['position'] == 3
        print('OK: serp_tracker (record + history + latest + movers up/down + track inyectado)')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
