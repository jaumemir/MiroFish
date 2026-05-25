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
import sqlite3 as _sqlite3
from enum import Enum
from typing import Any


class OrphanCategory(str, Enum):
    BASE_ORPHAN = "BASE_ORPHAN"
    SIM_ORPHAN = "SIM_ORPHAN"
    DANGLING_PROJECT = "DANGLING_PROJECT"


# Patró de group_id de simulació: mirofish_<sim_id>_sim
# sim_id segueix el format sim_<12 hex digits>
_SIM_GID_RE = re.compile(r"^mirofish_(sim_[a-f0-9]{12})_sim$")


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


def read_sqlite(conn: _sqlite3.Connection) -> dict[str, Any]:
    """Llegeix les taules graphs, simulations i projects de la BBDD SQLite.

    Retorna:
        known_external_ids : set[str] — external_ids de graphs amb backend=graphiti
        known_sim_ids      : set[str] — ids de totes les simulacions
        known_project_ids  : set[str] — ids de tots els projectes
        graph_rows         : list[dict] — files de graphs amb external_id vàlid
        warnings           : list[str] — inconsistències detectades (no generen eliminació)
    """
    _original_factory = conn.row_factory
    conn.row_factory = _sqlite3.Row
    try:
        warnings = []

        # Llegir graphs
        known_external_ids: set[str] = set()
        graph_rows: list[dict[str, Any]] = []

        for row in conn.execute("SELECT id, project_id, backend, external_id FROM graphs").fetchall():
            gid = row["id"]
            backend = row["backend"] or ""
            ext_id = row["external_id"]

            if backend != "graphiti":
                warnings.append(
                    f"GraphModel id='{gid}' backend='{backend}' — ignorat per a reconciliació Neo4j"
                )
                continue

            if not ext_id:
                warnings.append(
                    f"GraphModel id='{gid}' backend='graphiti' external_id=NULL — sense external_id, no reconciliable"
                )
                continue

            known_external_ids.add(ext_id)
            graph_rows.append({
                "graph_id": gid,
                "project_id": row["project_id"],
                "external_id": ext_id,
            })

        # Llegir simulations
        known_sim_ids: set[str] = {
            row["id"]
            for row in conn.execute("SELECT id FROM simulations").fetchall()
        }

        # Llegir projects
        known_project_ids: set[str] = {
            row["id"]
            for row in conn.execute("SELECT id FROM projects").fetchall()
        }

        return {
            "known_external_ids": known_external_ids,
            "known_sim_ids": known_sim_ids,
            "known_project_ids": known_project_ids,
            "graph_rows": graph_rows,
            "warnings": warnings,
        }
    finally:
        conn.row_factory = _original_factory


def read_neo4j_group_ids(driver: Any) -> set[str]:
    """Consulta Neo4j i retorna tots els group_id únics que existeixen.

    Args:
        driver: Neo4j driver sincronitzat (neo4j.GraphDatabase.driver(...))

    Returns:
        Conjunt de strings amb tots els group_id distincts trobats.
    """
    result = driver.execute_query(
        "MATCH (n) WHERE n.group_id IS NOT NULL "
        "RETURN DISTINCT n.group_id AS gid"
    )
    return {record["gid"] for record in result.records if record["gid"]}
