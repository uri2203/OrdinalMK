"""
OrdinalMK — Puerta de calidad + verificación de contenido sensible.

Antes de publicar, cada artículo pasa por esta puerta:
  - Se PUNTÚA y se BLOQUEA si no alcanza el umbral (calidad mínima) o si tiene
    problemas duros (muy corto, sin estructura, relleno, marca equivocada).
  - Se marca para REVISIÓN HUMANA si contiene afirmaciones fiscales/legales
    sensibles (CFDI, SAT, IVA, tasas, plazos…) — un dato inventado sobre esto
    puede dañar la marca o meter en problemas a un cliente.

Decisión final:
  - 'publish'      → cumple calidad y no tiene afirmaciones sensibles.
  - 'hold_review'  → cumple calidad pero necesita revisión humana (fiscal/legal).
  - 'blocked'      → no cumple calidad; no se publica.

Es una función pura sobre el dict del artículo → fácil de testear.
"""

import re

DEFAULT_MIN_SCORE = 60
DEFAULT_MIN_WORDS = 600
MAX_BRAND_MENTIONS = 8

# Afirmaciones fiscales/legales que DEBEN ser correctas → revisión humana.
# Ojo: términos genéricos como "factura"/"facturación" NO disparan revisión
# (aparecen en casi todo el contenido); solo los específicos de alto riesgo.
HIGH_RISK_TERMS = [
    r'\bCFDI\b', r'\bSAT\b', r'\bIVA\b', r'\bISR\b', r'\bRFC\b', r'\bIEPS\b',
    r'\bIMSS\b', r'\bINFONAVIT\b', r'\bSUA\b',
    r'\bdeducibl\w*', r'\bretenci\w*', r'\bdeclaraci\w*', r'\bcontribuyent\w*',
    r'\boblig\w*', r'\bmulta\w*', r'\bplazo\w*', r'\bvencimient\w*',
    r'\bcomplement\w+\s+de\s+pago', r'\btimbrad\w*',
]
# Cifras que parecen tasas/porcentajes o montos concretos (afirmación verificable)
NUMERIC_CLAIM = re.compile(r'\b\d{1,3}(?:[.,]\d+)?\s?%|\$\s?\d')

PLACEHOLDER = re.compile(r'lorem ipsum|\bxxx\b|\btbd\b|todo:|placeholder', re.IGNORECASE)

# Marcas conocidas del ecosistema — si aparece una que NO es la del proyecto,
# es contenido con marca equivocada (fallo duro).
KNOWN_BRANDS = ['Yayika', 'TuIAlista', 'LastMile']


def evaluate(article: dict, min_score: int = DEFAULT_MIN_SCORE,
             min_words: int = DEFAULT_MIN_WORDS) -> dict:
    """Evalúa un artículo y devuelve la decisión de publicación."""
    body = (article.get('body') or '')
    brand = (article.get('brand') or '').strip()
    score = int(article.get('seo_score') or 0)
    wc = int(article.get('word_count') or len(body.split()))

    reasons = []  # problemas duros que BLOQUEAN

    if wc < min_words:
        reasons.append(f'muy corto ({wc} palabras; mínimo {min_words})')
    if '##' not in body:
        reasons.append('sin subtítulos (##)')
    if not re.search(r'conclus|fazit|conclusion|fazit', body.lower()):
        reasons.append('sin conclusión')
    if PLACEHOLDER.search(body):
        reasons.append('contiene texto de relleno / placeholder')

    if brand:
        n_brand = len(re.findall(re.escape(brand), body, re.IGNORECASE))
        if n_brand == 0:
            reasons.append('no menciona la marca del proyecto')
        elif n_brand > MAX_BRAND_MENTIONS:
            reasons.append(f'sobre-menciona la marca ({n_brand} veces; spam)')
        # ¿aparece OTRA marca conocida? → marca equivocada
        for other in KNOWN_BRANDS:
            if other.lower() != brand.lower() and re.search(
                    r'\b' + re.escape(other) + r'\b', body, re.IGNORECASE):
                reasons.append(f'menciona marca equivocada: {other}')

    # Afirmaciones sensibles → revisión humana (no bloquea, pero no auto-publica)
    flags = []
    for pat in HIGH_RISK_TERMS:
        m = re.search(pat, body, re.IGNORECASE)
        if m:
            flags.append(m.group(0))
    if NUMERIC_CLAIM.search(body):
        flags.append('cifra/porcentaje/monto concreto')
    # dedup preservando orden
    seen, flags_u = set(), []
    for f in flags:
        k = f.lower()
        if k not in seen:
            seen.add(k)
            flags_u.append(f)

    passed = (score >= min_score) and not reasons
    needs_review = bool(flags_u)

    if not passed:
        decision = 'blocked'
    elif needs_review:
        decision = 'hold_review'
    else:
        decision = 'publish'

    if score < min_score:
        reasons = reasons + [f'SEO score {score} < {min_score}']

    return {
        'decision': decision,
        'passed': passed,
        'needs_review': needs_review,
        'score': score,
        'word_count': wc,
        'reasons': reasons,
        'flags': flags_u,
    }


if __name__ == "__main__":
    # Autotest rápido
    good = {
        'title': 'Cómo automatizar tu negocio con IA en 2026',
        'brand': 'TuIAlista',
        'seo_score': 80,
        'word_count': 1300,
        'body': '# T\n\n## Intro\n' + ('palabra ' * 1300) +
                '\n## Conclusión\nUsa TuIAlista hoy.',
    }
    short = {'title': 'x', 'brand': 'TuIAlista', 'seo_score': 40,
             'word_count': 120, 'body': '## a\nTuIAlista texto corto. conclusion'}
    fiscal = {
        'title': 'Facturación CFDI con IA', 'brand': 'TuIAlista', 'seo_score': 75,
        'word_count': 1200,
        'body': '# T\n## Intro\n' + ('palabra ' * 1200) +
                '\nEl IVA es del 16% y el CFDI se timbra ante el SAT.\n## Conclusión\nTuIAlista.',
    }
    wrong = {
        'title': 'x', 'brand': 'TuIAlista', 'seo_score': 80, 'word_count': 1000,
        'body': '# T\n## Intro\n' + ('palabra ' * 1000) +
                '\nDescubre Yayika.\n## Conclusión\n',
    }
    for name, art in [('bueno', good), ('corto', short), ('fiscal', fiscal), ('marca-mala', wrong)]:
        r = evaluate(art)
        print(f"{name:12} -> {r['decision']:12} score={r['score']} "
              f"flags={r['flags']} reasons={r['reasons']}")
