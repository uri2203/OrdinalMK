"""
OrdinalMK — GEO (Generative Engine Optimization).

En 2026 mucha gente "busca" preguntándole a ChatGPT/Claude/Google AI Overviews.
Para que TE citen, el contenido debe ser fácil de EXTRAER: respuesta directa al
inicio, datos concretos, listas, y una sección de preguntas frecuentes.

Este módulo:
  - Calcula un `geo_score` (0-100) de qué tan "citable por IA" es un artículo.
  - Genera un bloque TL;DR / respuesta directa (IA si hay credenciales; si no,
    extractivo de las primeras frases).
  - Extrae/crea preguntas frecuentes (FAQ) a partir de los encabezados.
  - Devuelve el artículo enriquecido, listo para que schema.py emita FAQPage.

Todo con fallback y funciones puras (score, extracción) testeables sin red.
"""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

CONTENT_MODEL = os.environ.get("ORDINALMK_CONTENT_MODEL", "claude-opus-4-8")

_SENT_SPLIT = re.compile(r'(?<=[.!?])\s+')


def _body(article: dict) -> str:
    return (article.get('body') or article.get('content') or '').strip()


def _headings(body: str) -> list:
    return [h.strip() for h in re.findall(r'^\s*#{2,3}\s+(.+?)\s*$', body, flags=re.MULTILINE)]


def _first_sentences(text: str, n: int = 2) -> str:
    plain = re.sub(r'[#*`>\-]', '', text).strip()
    plain = re.sub(r'\s+', ' ', plain)
    parts = [s for s in _SENT_SPLIT.split(plain) if s.strip()]
    return ' '.join(parts[:n]).strip()


def geo_score(article: dict) -> dict:
    """Heurística 0-100 de citabilidad por IA. Puro."""
    body = _body(article)
    reasons = []
    score = 0
    # respuesta directa arriba (TL;DR ya presente)
    if article.get('tldr'):
        score += 20; reasons.append('tiene TL;DR')
    else:
        reasons.append('falta respuesta directa arriba')
    # datos/números concretos
    nums = len(re.findall(r'\b\d+([.,]\d+)?\s?(%|mxn|usd|€|\$|años?|días?|horas?)?', body))
    if nums >= 3:
        score += 20; reasons.append('incluye datos/números')
    else:
        reasons.append('pocos datos concretos')
    # listas (fáciles de extraer)
    if re.search(r'^\s*[-*]\s+', body, flags=re.MULTILINE):
        score += 15; reasons.append('tiene listas')
    else:
        reasons.append('sin listas')
    # encabezados claros
    hs = _headings(body)
    if len(hs) >= 2:
        score += 15; reasons.append('encabezados claros')
    else:
        reasons.append('estructura pobre')
    # FAQ
    if article.get('faq'):
        score += 20; reasons.append('tiene FAQ')
    else:
        reasons.append('sin FAQ')
    # preguntas en encabezados (buena señal PAA)
    if any('?' in h or re.match(r'^(qué|cómo|cuánto|por qué|what|how|why)', h.lower()) for h in hs):
        score += 10; reasons.append('encabezados tipo pregunta')
    return {'geo_score': min(100, score), 'reasons': reasons,
            'grade': 'A' if score >= 80 else 'B' if score >= 60 else 'C' if score >= 40 else 'D'}


def make_tldr(article: dict, config: dict = None) -> str:
    """Respuesta directa breve. IA si hay credenciales; si no, extractiva."""
    body = _body(article)
    if _ai_available():
        try:
            return _ai_tldr(article, config or {})
        except Exception:
            pass
    return _first_sentences(body, 2) or (article.get('title', '') or '')


def extract_faq(article: dict, max_q: int = 5) -> list:
    """FAQ desde encabezados: los que ya son preguntas, o convierte H2/H3 en Q&A."""
    body = _body(article)
    hs = _headings(body)
    faq = []
    # separa el cuerpo por encabezados para tomar el texto de cada sección
    sections = re.split(r'^\s*#{2,3}\s+.+?\s*$', body, flags=re.MULTILINE)
    # sections[0] es el intro; a partir de 1 corresponde a cada heading en orden
    for i, h in enumerate(hs):
        ans_src = sections[i + 1] if i + 1 < len(sections) else ''
        answer = _first_sentences(ans_src, 2) or _first_sentences(body, 1)
        q = h if '?' in h else _to_question(h)
        if answer:
            faq.append({'question': q, 'answer': answer})
        if len(faq) >= max_q:
            break
    return faq


def _to_question(heading: str) -> str:
    h = heading.strip().rstrip('.')
    low = h.lower()
    if re.match(r'^(qué|cómo|cuánto|por qué|para qué|what|how|why|when)', low):
        return h + '?'
    return f"¿Qué es {h.lower()}?" if len(h.split()) <= 4 else f"{h}?"


def optimize(article: dict, config: dict = None) -> dict:
    """Enriquece el artículo con tldr + faq y calcula el geo_score final."""
    out = dict(article)
    if not out.get('tldr'):
        out['tldr'] = make_tldr(out, config)
    if not out.get('faq'):
        out['faq'] = extract_faq(out)
    out['geo'] = geo_score(out)
    return out


def _ai_available() -> bool:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_AUTH_TOKEN'))


def _ai_tldr(article, config):
    import anthropic
    client = anthropic.Anthropic()
    lang = article.get('language', 'es')
    sysp = (f"Resume en '{lang}' en UNA respuesta directa (2 frases máx) la idea central "
            f"del artículo, como la citaría una IA. Sin preámbulo. Solo el texto.")
    resp = client.messages.create(model=CONTENT_MODEL, max_tokens=180, system=sysp,
                                  messages=[{"role": "user", "content": _body(article)[:2000]}])
    return "".join(b.text for b in resp.content if b.type == "text").strip()


if __name__ == "__main__":
    thin = {'title': 'Facturación', 'language': 'es', 'body': 'La facturación es útil.'}
    rich = {'title': 'Facturación electrónica CFDI', 'language': 'es', 'body': (
        "La facturación electrónica es obligatoria en México desde 2014.\n\n"
        "## Qué es el CFDI\nEl CFDI es el comprobante fiscal digital. Lo exige el SAT.\n\n"
        "## Cuánto cuesta automatizarla\nDesde $0 con herramientas locales. Ahorra 10 horas al mes.\n\n"
        "## Ventajas\n- Menos errores\n- Cumples con el SAT\n- Ahorras tiempo\n")}

    # 1) score: rico debe superar a pobre
    sr = geo_score(rich); st = geo_score(thin)
    print('score rico:', sr['geo_score'], sr['grade'], '| pobre:', st['geo_score'], st['grade'])
    assert sr['geo_score'] > st['geo_score']

    # 2) TL;DR extractivo (sin IA) toma las primeras frases
    os.environ.pop('ANTHROPIC_API_KEY', None); os.environ.pop('ANTHROPIC_AUTH_TOKEN', None)
    tl = make_tldr(rich)
    print('tldr:', tl[:70])
    assert 'facturación electrónica' in tl.lower()

    # 3) FAQ desde encabezados (incluye preguntas y respuestas)
    faq = extract_faq(rich)
    print('faq:', [(f['question'][:28]) for f in faq])
    assert len(faq) >= 2
    assert any('CFDI' in f['question'] or 'cuánto' in f['question'].lower() for f in faq)
    assert all(f['answer'] for f in faq), 'toda FAQ debe tener respuesta'

    # 4) optimize enriquece y sube el score
    opt = optimize(rich)
    assert opt['tldr'] and opt['faq'] and opt['geo']['geo_score'] >= sr['geo_score']
    assert opt['geo']['geo_score'] >= 80, opt['geo']['geo_score']
    print('score optimizado:', opt['geo']['geo_score'], opt['geo']['grade'])
    print('OK: geo (score citabilidad + tldr extractivo + faq desde headings + optimize)')
