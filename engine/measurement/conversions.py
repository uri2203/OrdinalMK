"""
OrdinalMK — Tracking de conversión (contenido → cliente → ingreso).

Cierra el ciclo hasta el dinero. Un webhook de Stripe o tu portal registran cada
evento (prueba iniciada / pago) con su atribución (fuente, campaña, contenido).
El motor agrega y así SABE qué contenido y qué canal generan ingresos —para
doblar lo que funciona y cortar lo que no.

Almacén simple por proyecto: reports/conversions/<project>.jsonl (una línea por
evento). Fallback: sin archivo → resumen en cero (no rompe).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
CONV_DIR = REPO_ROOT / "reports" / "conversions"


def record_event(project_id: str, event: dict, conv_dir: Path = CONV_DIR) -> dict:
    """Registra un evento de conversión. type: 'trial' | 'paid'.
    Campos sugeridos: amount, currency, source, campaign, content, ts."""
    conv_dir.mkdir(parents=True, exist_ok=True)
    ev = dict(event)
    ev.setdefault('ts', datetime.now(timezone.utc).isoformat())
    ev.setdefault('type', 'trial')
    with open(conv_dir / f"{project_id}.jsonl", 'a', encoding='utf-8') as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return ev


def load_events(project_id: str, conv_dir: Path = CONV_DIR) -> list:
    f = conv_dir / f"{project_id}.jsonl"
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _blank():
    return {'trials': 0, 'paid': 0, 'revenue': 0.0}


def summary(project_id: str, conv_dir: Path = CONV_DIR) -> dict:
    """Agrega conversiones e ingresos totales y por contenido/fuente."""
    events = load_events(project_id, conv_dir)
    totals = _blank()
    by_content = {}
    by_source = {}
    for e in events:
        t = e.get('type')
        amount = float(e.get('amount', 0) or 0)
        content = e.get('content') or e.get('landing') or e.get('slug') or '(desconocido)'
        source = e.get('source') or e.get('utm_source') or '(directo)'
        bc = by_content.setdefault(content, _blank())
        bs = by_source.setdefault(source, _blank())
        if t == 'trial':
            totals['trials'] += 1; bc['trials'] += 1; bs['trials'] += 1
        elif t == 'paid':
            totals['paid'] += 1; bc['paid'] += 1; bs['paid'] += 1
            totals['revenue'] += amount; bc['revenue'] += amount; bs['revenue'] += amount

    conv_rate = (totals['paid'] / totals['trials']) if totals['trials'] else 0.0
    totals['revenue'] = round(totals['revenue'], 2)
    return {
        'project': project_id,
        'totals': totals,
        'trial_to_paid': round(conv_rate, 3),
        'by_content': by_content,
        'by_source': by_source,
        'events': len(events),
    }


def top_content_by_revenue(project_id: str, n: int = 5, conv_dir: Path = CONV_DIR) -> list:
    s = summary(project_id, conv_dir)
    items = [{'content': k, **v} for k, v in s['by_content'].items()]
    items.sort(key=lambda x: x['revenue'], reverse=True)
    return items[:n]


if __name__ == "__main__":
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp(prefix='conv_'))
    try:
        pid = 'demo'
        # 3 pruebas, 2 pagos (uno del artículo 'facturacion', otro de 'excel')
        events = [
            {'type': 'trial', 'content': 'facturacion', 'source': 'google'},
            {'type': 'trial', 'content': 'facturacion', 'source': 'google'},
            {'type': 'trial', 'content': 'excel', 'source': 'meta'},
            {'type': 'paid', 'content': 'facturacion', 'source': 'google', 'amount': 29},
            {'type': 'paid', 'content': 'excel', 'source': 'meta', 'amount': 29},
        ]
        for e in events:
            record_event(pid, e, conv_dir=tmp)

        s = summary(pid, conv_dir=tmp)
        print('totales:', s['totals'], '| trial-a-paid:', s['trial_to_paid'])
        assert s['totals'] == {'trials': 3, 'paid': 2, 'revenue': 58.0}, s['totals']
        assert s['trial_to_paid'] == round(2/3, 3)
        top = top_content_by_revenue(pid, conv_dir=tmp)
        print('top por ingreso:', [(t['content'], t['revenue']) for t in top])
        assert top[0]['revenue'] == 29 and s['by_source']['google']['revenue'] == 29
        # fallback sin archivo
        assert summary('inexistente', conv_dir=tmp)['totals'] == _blank()
        print('OK: registro + atribución (contenido/fuente) + top por ingreso + fallback')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
