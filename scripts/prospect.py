#!/usr/bin/env python
"""
OrdinalMK — Prospección B2B (CLI).

Uso:
    python scripts/prospect.py discover <proyecto>          # busca + enriquece + guarda (cola)
    python scripts/prospect.py list <proyecto> [estado]     # ver prospectos / conteos
    python scripts/prospect.py approve <proyecto> <clave|all># aprobar para outreach
    python scripts/prospect.py send <proyecto>              # enviar a los APROBADOS

Flujo: discover -> (revisas) -> approve -> send. El envío nunca es automático
desde 'nuevo': primero apruebas (puerta humana).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.projects import get_project_config
from engine.prospecting import store, pipeline, outreach


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    action, pid = sys.argv[1], sys.argv[2]
    cfg = get_project_config(pid)

    if action == 'discover':
        print(pipeline.discover_project(pid, cfg))

    elif action == 'list':
        estado = sys.argv[3] if len(sys.argv) > 3 else None
        print("Conteos:", {k: v for k, v in store.counts(pid).items() if v})
        rows = store.by_status(pid, estado) if estado else store.load(pid)
        for r in rows[:50]:
            print(f"  [{r.get('status')}] {r.get('name','')} <{r.get('email','')}>")

    elif action == 'approve' and len(sys.argv) >= 4:
        target = sys.argv[3]
        if target == 'all':
            n = pipeline.approve_all_new(pid)
            print(f"Aprobados {n} prospectos 'nuevo' con correo.")
        else:
            ok = store.update_status(pid, target, 'aprobado')
            print("Aprobado." if ok else "No encontrado.")

    elif action == 'send':
        print(outreach.send_to_approved(pid, cfg))

    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
