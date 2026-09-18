#!/usr/bin/env python
"""
OrdinalMK — Corrida diaria autónoma.

Punto de entrada para el cron/GitHub Action: ejecuta el marketing de TODOS los
proyectos habilitados, en orden de prioridad (gobierno). Pensado para correr sin
supervisión.

Uso:
    python scripts/daily_run.py
    ORDINALMK_DRY_RUN=1 python scripts/daily_run.py   # prueba sin publicar
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.multi_orchestrator import MultiProjectOrchestrator


def main():
    orchestrator = MultiProjectOrchestrator()
    results = orchestrator.run_all_active()
    errores = sum(1 for r in results.values() if r.get('status') == 'error')
    # Código de salida != 0 si algún proyecto falló (útil para CI/alertas)
    sys.exit(1 if errores else 0)


if __name__ == "__main__":
    main()
