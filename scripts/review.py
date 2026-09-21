#!/usr/bin/env python
"""
OrdinalMK — Bandeja de revisión humana (CLI).

Uso:
    python scripts/review.py list [proyecto]           # ver pendientes
    python scripts/review.py approve <proyecto> <slug> # verificado -> publicar
    python scripts/review.py reject  <proyecto> <slug> ["motivo"]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.projects import load_config, get_project_config
from engine.review.queue import list_held, approve, reject


def _all_projects():
    return list(load_config().get('projects', {}).keys())


def cmd_list(project=None):
    projects = [project] if project else _all_projects()
    total = 0
    for pid in projects:
        items = list_held(pid)
        if not items:
            continue
        print(f"\n[{pid}] {len(items)} en revisión:")
        for it in items:
            print(f"  - {it['slug']} [{it['language']}] "
                  f"flags={it['flags']} reasons={it['reasons']}")
        total += len(items)
    if total == 0:
        print("Nada en revisión. Todo limpio.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    action = sys.argv[1]
    if action == 'list':
        cmd_list(sys.argv[2] if len(sys.argv) > 2 else None)
    elif action == 'approve' and len(sys.argv) >= 4:
        pid, slug = sys.argv[2], sys.argv[3]
        print(approve(pid, slug, get_project_config(pid)))
    elif action == 'reject' and len(sys.argv) >= 4:
        pid, slug = sys.argv[2], sys.argv[3]
        reason = sys.argv[4] if len(sys.argv) > 4 else ''
        print(reject(pid, slug, reason=reason))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
