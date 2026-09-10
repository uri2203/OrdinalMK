"""
OrdinalMK — Guardia anti-canibalización de keywords.

Cuando dos páginas del MISMO proyecto e idioma apuntan a la misma keyword,
compiten entre sí en Google y se hunden mutuamente (keyword cannibalization).
Esta pieza audita la biblioteca y reporta colisiones para consolidar o
diferenciar el contenido.

Señales de colisión (mismo proyecto + mismo idioma):
  - Mismo keyword primario (el primero de la lista de keywords).
  - Solapamiento muy alto del conjunto de keywords (Jaccard >= umbral).

Función pura sobre los JSON de artículos (acepta ruta override) → testeable.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
CONTENT_ROOT = REPO_ROOT / "content"

DEFAULT_JACCARD = 0.6


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
        if a.get('status') == 'published' and a.get('slug') and a.get('language'):
            arts.append(a)
    return arts


def _primary(a: dict) -> str:
    kws = a.get('keywords') or []
    if kws:
        return str(kws[0]).lower().strip()
    # sin keywords: primeras 3 palabras del título
    return ' '.join((a.get('title') or '').lower().split()[:3])


def _jaccard(a: dict, b: dict) -> float:
    ka = {k.lower() for k in (a.get('keywords') or [])}
    kb = {k.lower() for k in (b.get('keywords') or [])}
    if not ka or not kb:
        return 0.0
    return len(ka & kb) / len(ka | kb)


def detect(project_id: str, config: dict = None, jaccard_threshold: float = DEFAULT_JACCARD,
           content_root: Path = CONTENT_ROOT) -> list:
    """Devuelve la lista de colisiones de canibalización detectadas."""
    arts = _load_published(project_id, content_root)
    by_lang = {}
    for a in arts:
        by_lang.setdefault(a['language'], []).append(a)

    collisions = []
    for lang, group in by_lang.items():
        # 1) mismo keyword primario
        by_primary = {}
        for a in group:
            by_primary.setdefault(_primary(a), []).append(a['slug'])
        for kw, slugs in by_primary.items():
            if kw and len(slugs) > 1:
                collisions.append({
                    'language': lang, 'reason': 'mismo keyword primario',
                    'keyword': kw, 'slugs': sorted(slugs),
                })

        # 2) solapamiento muy alto (aunque el primario difiera)
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                if _primary(a) == _primary(b):
                    continue  # ya cubierto arriba
                sim = _jaccard(a, b)
                if sim >= jaccard_threshold:
                    collisions.append({
                        'language': lang, 'reason': 'solapamiento alto de keywords',
                        'similarity': round(sim, 2),
                        'slugs': sorted([a['slug'], b['slug']]),
                    })
    return collisions


if __name__ == "__main__":
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp(prefix='cannib_'))
    try:
        cr = tmp / "content"
        pid = "demo"
        (cr / pid).mkdir(parents=True)
        arts = [
            # A y B: mismo keyword primario 'facturación' -> colisión
            {'slug': 'a', 'title': 'Facturar rápido', 'language': 'es', 'status': 'published',
             'keywords': ['facturación', 'ia']},
            {'slug': 'b', 'title': 'Facturación fácil', 'language': 'es', 'status': 'published',
             'keywords': ['facturación', 'cfdi']},
            # C: distinto -> sin colisión
            {'slug': 'c', 'title': 'Excel con IA', 'language': 'es', 'status': 'published',
             'keywords': ['excel', 'reportes']},
            # D (inglés): no colisiona con los es
            {'slug': 'd', 'title': 'Invoice with AI', 'language': 'en', 'status': 'published',
             'keywords': ['invoicing', 'ai']},
        ]
        for a in arts:
            (cr / pid / f"{a['slug']}.json").write_text(json.dumps(a, ensure_ascii=False), encoding='utf-8')

        cols = detect(pid, content_root=cr)
        print('colisiones:', cols)
        assert any(c['reason'] == 'mismo keyword primario' and set(c['slugs']) == {'a', 'b'} for c in cols), \
            'debería detectar A/B mismo primario'
        assert not any('c' in c['slugs'] for c in cols), 'C no debe colisionar'
        assert not any('d' in c['slugs'] for c in cols), 'D (en) no colisiona con es'
        print('OK: detecta canibalización es (A/B), ignora C y el idioma en')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
