"""
OrdinalMK — Inteligencia de keywords y competencia.

El "cerebro" que decide SOBRE QUÉ escribir. En vez de una lista fija de temas,
clasifica keywords por intención (transaccional > comercial > informacional),
las prioriza (más cerca de la compra = más valiosas) y detecta HUECOS: keywords
objetivo del proyecto que aún no están cubiertas por ningún artículo.

Funciona sin APIs de pago (heurísticas de intención + huecos). Deja un hook para
enriquecer con volumen/dificultad si algún día se conecta una API de keywords.
Todas las funciones son puras/testables.
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
CONTENT_ROOT = REPO_ROOT / "content"

# Señales de intención (es + en). Orden de prueba: transaccional → comercial →
# informacional (la más específica gana).
TRANSACTIONAL = [
    'comprar', 'precio', 'precios', 'cuanto cuesta', 'cuánto cuesta', 'contratar',
    'software', 'programa', 'app', 'aplicacion', 'aplicación', 'herramienta',
    'plan', 'planes', 'suscripcion', 'suscripción', 'descargar', 'gratis',
    'buy', 'price', 'pricing', 'cost', 'tool', 'download', 'subscription', 'free trial',
]
COMMERCIAL = [
    'mejor', 'mejores', 'alternativa', 'alternativas', 'vs', 'comparativa',
    'comparacion', 'comparación', 'reseña', 'review', 'top',
    'best', 'alternative', 'comparison', 'vs.',
]
INFORMATIONAL = [
    'como', 'cómo', 'que es', 'qué es', 'guia', 'guía', 'tutorial', 'por que',
    'por qué', 'ejemplos', 'beneficios', 'ventajas',
    'how', 'what is', 'guide', 'why', 'examples', 'benefits',
]

INTENT_PRIORITY = {'transactional': 3, 'commercial': 2, 'informational': 1}


def classify_intent(keyword: str) -> str:
    k = (keyword or '').lower()
    if any(t in k for t in TRANSACTIONAL):
        return 'transactional'
    if any(t in k for t in COMMERCIAL):
        return 'commercial'
    if any(t in k for t in INFORMATIONAL):
        return 'informational'
    return 'informational'  # por defecto


def priority_score(keyword: str) -> int:
    return INTENT_PRIORITY[classify_intent(keyword)]


def _load_published(project_id: str, content_root: Path) -> list:
    arts = []
    d = content_root / project_id
    if not d.exists():
        return arts
    for f in sorted(d.glob('*.json')):
        try:
            a = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        if a.get('status') == 'published':
            arts.append(a)
    return arts


def _stem(word: str) -> str:
    """Stemming crudo (primeras 5 letras) para casar variantes: automatizar ~
    automatiza, facturación ~ facturas, etc. Suficiente para detectar cobertura."""
    return word.lower()[:5]


def covered_keywords(project_id: str, content_root: Path = CONTENT_ROOT) -> dict:
    """Cobertura por idioma: frases exactas + stems de palabras (keywords + título)."""
    out = {}
    for a in _load_published(project_id, content_root):
        lang = a.get('language', 'es')
        cov = out.setdefault(lang, {'phrases': set(), 'stems': set()})
        for k in (a.get('keywords') or []):
            phrase = str(k).lower().strip()
            cov['phrases'].add(phrase)
            for w in re.findall(r'\w+', phrase):
                if len(w) > 3:
                    cov['stems'].add(_stem(w))
        for w in re.findall(r'\w+', (a.get('title') or '').lower()):
            if len(w) > 3:
                cov['stems'].add(_stem(w))
    return out


def find_gaps(config: dict, project_id: str, content_root: Path = CONTENT_ROOT) -> dict:
    """Huecos por idioma: keywords objetivo (seo.target_keywords) aún no cubiertas,
    ordenadas por prioridad de intención (transaccional primero)."""
    targets = (config.get('seo') or {}).get('target_keywords') or {}
    covered = covered_keywords(project_id, content_root)
    gaps = {}
    for lang, kws in targets.items():
        cov = covered.get(lang, {'phrases': set(), 'stems': set()})
        missing = []
        for kw in kws:
            k = str(kw).lower().strip()
            # cubierta si la frase exacta ya está, o si todas sus palabras (por stem) lo están
            words = [w for w in re.findall(r'\w+', k) if len(w) > 3]
            stems = [_stem(w) for w in words]
            is_covered = (k in cov['phrases']) or (stems and all(s in cov['stems'] for s in stems))
            if not is_covered:
                missing.append({
                    'keyword': kw,
                    'intent': classify_intent(kw),
                    'priority': priority_score(kw),
                })
        missing.sort(key=lambda x: x['priority'], reverse=True)
        gaps[lang] = missing
    return gaps


def suggest_next(config: dict, project_id: str, n: int = 5,
                 content_root: Path = CONTENT_ROOT) -> list:
    """Lista priorizada de próximas keywords a escribir (mezcla de idiomas),
    huecos de mayor intención primero. Alimenta el calendario del content engine."""
    gaps = find_gaps(config, project_id, content_root)
    flat = []
    for lang, items in gaps.items():
        for it in items:
            flat.append({**it, 'language': lang})
    flat.sort(key=lambda x: x['priority'], reverse=True)
    return flat[:n]


if __name__ == "__main__":
    import tempfile, shutil

    # 1) Clasificación de intención
    cases = {
        'software de facturación cfdi': 'transactional',
        'mejor alternativa a chatgpt': 'commercial',
        'qué es un agente de ia': 'informational',
        'automatizar excel': 'informational',
    }
    for kw, expected in cases.items():
        got = classify_intent(kw)
        print(f"{kw:35} -> {got}")
        assert got == expected, f"{kw}: esperaba {expected}, obtuve {got}"

    # 2) Huecos: sin nada cubierto, todos los targets son huecos, priorizados
    tmp = Path(tempfile.mkdtemp(prefix='kw_'))
    try:
        cr = tmp / "content"
        (cr / 'demo').mkdir(parents=True)
        # 1 artículo publicado que cubre "excel"
        (cr / 'demo' / 'x.json').write_text(json.dumps({
            'status': 'published', 'language': 'es', 'title': 'Automatiza Excel',
            'keywords': ['excel', 'reportes'],
        }, ensure_ascii=False), encoding='utf-8')
        cfg = {'seo': {'target_keywords': {'es': [
            'software de facturación cfdi',   # transaccional, hueco
            'mejor software de facturación',  # comercial, hueco
            'automatizar excel',              # informacional, YA cubierto
        ]}}}
        gaps = find_gaps(cfg, 'demo', content_root=cr)
        print('huecos es:', [(g['keyword'], g['intent']) for g in gaps['es']])
        kws = [g['keyword'] for g in gaps['es']]
        assert 'automatizar excel' not in kws, 'excel ya cubierto, no es hueco'
        assert kws[0] == 'software de facturación cfdi', 'transaccional debe ir primero'
        nxt = suggest_next(cfg, 'demo', n=2, content_root=cr)
        assert len(nxt) == 2 and nxt[0]['intent'] == 'transactional'
        print('siguiente a escribir:', [(x['keyword'], x['intent']) for x in nxt])
        print('OK: intención clasificada + huecos priorizados + sugerencia')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
