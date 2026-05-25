#!/usr/bin/env python3
"""
reconcile_neo4j.py — Reconciliació entre graphs Neo4j i BBDD SQLite de MiroFish.

Detecta group_ids orfes a Neo4j i genera:
  - reconcile_YYYYMMDD_HHMMSS.log  : log detallat del procés
  - reconcile_delete.py            : script d'eliminació executable

Ús:
  python3 scripts/reconcile_neo4j.py [--env-file PATH] [--db-path PATH]
          [--neo4j-uri URI] [--neo4j-user USER] [--neo4j-password PASS]
          [--output-dir DIR] [--log-level LEVEL]
"""
import re
from enum import Enum
from typing import Any


class OrphanCategory(str, Enum):
    BASE_ORPHAN = "BASE_ORPHAN"
    SIM_ORPHAN = "SIM_ORPHAN"
    DANGLING_PROJECT = "DANGLING_PROJECT"


# Patró de group_id de simulació: mirofish_<sim_id>_sim
# sim_id segueix el format sim_<anything>
_SIM_GID_RE = re.compile(r"^mirofish_(sim_[\w]+)_sim$")


def classify_group_ids(
    neo4j_gids: set[str],
    known_external_ids: set[str],
    known_sim_ids: set[str],
    known_project_ids: set[str],
    graph_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Classifica els group_ids de Neo4j en orfes o vàlids.

    Retorna llista de dicts amb claus: group_id, category, reason.
    Només inclou els orfes (els vàlids no apareixen).
    """
    # Mapa external_id -> graph_row per a DANGLING_PROJECT
    ext_to_row = {r["external_id"]: r for r in graph_rows if r.get("external_id")}

    orphans = []
    for gid in sorted(neo4j_gids):
        sim_match = _SIM_GID_RE.match(gid)

        if sim_match:
            # Pot ser SIM_ORPHAN o vàlid
            sim_id = sim_match.group(1)
            if sim_id not in known_sim_ids:
                orphans.append({
                    "group_id": gid,
                    "category": OrphanCategory.SIM_ORPHAN,
                    "reason": (
                        f"Cap SimulationModel amb id='{sim_id}' "
                        f"corresponent al group_id '{gid}'"
                    ),
                })
        elif gid in known_external_ids:
            # Pot ser DANGLING_PROJECT o vàlid
            row = ext_to_row.get(gid)
            if row and row.get("project_id") not in known_project_ids:
                orphans.append({
                    "group_id": gid,
                    "category": OrphanCategory.DANGLING_PROJECT,
                    "reason": (
                        f"GraphModel id='{row['graph_id']}' té "
                        f"external_id='{gid}' però el "
                        f"project_id='{row['project_id']}' "
                        f"no existeix a projects"
                    ),
                })
            # else: vàlid, no s'afegeix
        else:
            # BASE_ORPHAN: no és _sim i no té GraphModel
            orphans.append({
                "group_id": gid,
                "category": OrphanCategory.BASE_ORPHAN,
                "reason": f"Cap GraphModel amb external_id='{gid}' a la BBDD",
            })

    return orphans
