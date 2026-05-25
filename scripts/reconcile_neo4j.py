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


def generate_log_content(
    neo4j_uri: str,
    db_path: str,
    neo4j_gids: set[str],
    sqlite_data: dict[str, Any],
    orphans: list[dict[str, Any]],
    delete_script_path: str,
    log_path: str,
    timestamp: str,
) -> str:
    """Genera el contingut complet del log de reconciliació."""
    lines = []
    lines.append(f"=== RECONCILIACIÓ NEO4J - {timestamp} ===")
    lines.append("")

    # PAS 1
    lines.append(f"[PAS 1] Connexió Neo4j: {neo4j_uri}")
    lines.append(f"[PAS 1] group_ids trobats a Neo4j: {len(neo4j_gids)}")
    for gid in sorted(neo4j_gids):
        lines.append(f"[PAS 1]   - {gid}")
    lines.append("")

    # PAS 2
    lines.append(f"[PAS 2] BBDD: {db_path}")
    lines.append(f"[PAS 2] external_ids (backend=graphiti): {len(sqlite_data['known_external_ids'])}")
    lines.append(f"[PAS 2] sim_ids a simulations: {len(sqlite_data['known_sim_ids'])}")
    lines.append(f"[PAS 2] project_ids a projects: {len(sqlite_data['known_project_ids'])}")
    if sqlite_data["warnings"]:
        lines.append("")
        for w in sqlite_data["warnings"]:
            lines.append(f"[PAS 2] ADVERTÈNCIA: {w}")
    lines.append("")

    # PAS 3
    lines.append("[PAS 3] Creuament i classificació:")
    orphan_gids = {o["group_id"] for o in orphans}
    orphan_map = {o["group_id"]: o for o in orphans}
    for gid in sorted(neo4j_gids):
        if gid in orphan_gids:
            o = orphan_map[gid]
            lines.append(f"[PAS 3] ✗ {o['category'].value:<20} {gid} — {o['reason']}")
        else:
            lines.append(f"[PAS 3] ✓ VALID               {gid}")
    lines.append("")

    # Resum
    counts: dict[Any, int] = {}
    for o in orphans:
        counts[o["category"]] = counts.get(o["category"], 0) + 1

    lines.append("=== RESUM ===")
    total_valid = len(neo4j_gids) - len(orphans)
    lines.append(f"  VÀLIDS:           {total_valid}")
    for cat in OrphanCategory:
        lines.append(f"  {cat.value:<20} {counts.get(cat, 0)}")
    lines.append(f"  TOTAL ORFES:      {len(orphans)}")
    lines.append("")
    lines.append(f"Script d'eliminació generat: {delete_script_path}")
    lines.append(f"Log guardat a:              {log_path}")

    return "\n".join(lines)


def generate_delete_script(
    orphans: list[dict[str, Any]],
    neo4j_uri: str,
    log_path: str,
    timestamp: str,
) -> str:
    """Genera el contingut del script reconcile_delete.py."""
    counts: dict[Any, int] = {}
    for o in orphans:
        counts[o["category"]] = counts.get(o["category"], 0) + 1

    count_lines = "\n".join(
        f"  {cat.value}: {counts.get(cat, 0)}"
        for cat in OrphanCategory
    )

    orphans_repr = "ORPHANS: list = [\n"
    for o in orphans:
        orphans_repr += (
            f"    # {o['category']}: {o['reason']}\n"
            f"    {repr(o['group_id'])},\n"
        )
    orphans_repr += "]"

    return f'''#!/usr/bin/env python3
"""
Script d'eliminació de graphs Neo4j orfes.
Generat per: scripts/reconcile_neo4j.py
Data de generació: {timestamp}
Log de referència: {log_path}

Orfes detectats: {len(orphans)}
{count_lines}

ÚS:
  python3 reconcile_delete.py             # dry-run (no elimina res)
  python3 reconcile_delete.py --execute   # elimina amb confirmació interactiva

CONNEXIÓ:
  Llegeix NEO4J_URI/USER/PASSWORD del fitxer .env o de les variables d'entorn.
  Args CLI --neo4j-uri / --neo4j-user / --neo4j-password sobreescriuen .env.
"""
import argparse
import os
import sys
from pathlib import Path


{orphans_repr}


def _load_config(args: argparse.Namespace) -> dict:
    env_file = Path(__file__).parent.parent / ".env"
    config = {{}}
    if env_file.exists():
        try:
            from dotenv import dotenv_values
            config = dict(dotenv_values(env_file))
        except ImportError:
            pass
    return {{
        "uri":      args.neo4j_uri      or config.get("NEO4J_URI")      or os.environ.get("NEO4J_URI", ""),
        "user":     args.neo4j_user     or config.get("NEO4J_USER")     or os.environ.get("NEO4J_USER", "neo4j"),
        "password": args.neo4j_password or config.get("NEO4J_PASSWORD") or os.environ.get("NEO4J_PASSWORD", ""),
    }}


def main() -> None:
    parser = argparse.ArgumentParser(description="Elimina graphs Neo4j orfes.")
    parser.add_argument("--execute", action="store_true",
                        help="Executa l\'eliminació (per defecte: dry-run)")
    parser.add_argument("--neo4j-uri",      default=None)
    parser.add_argument("--neo4j-user",     default=None)
    parser.add_argument("--neo4j-password", default=None)
    args = parser.parse_args()

    if not ORPHANS:
        print("Cap orfe detectat. Res a eliminar.")
        sys.exit(0)

    cfg = _load_config(args)
    if not cfg["uri"] or not cfg["password"]:
        print("ERROR: NEO4J_URI i NEO4J_PASSWORD són obligatoris.", file=sys.stderr)
        sys.exit(1)

    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"]))

    if not args.execute:
        print(f"DRY-RUN: s\'eliminaria {{len(ORPHANS)}} group_id(s):\\n")
        for gid in ORPHANS:
            result = driver.execute_query(
                "MATCH (n) WHERE n.group_id = $gid RETURN count(n) AS cnt",
                gid=gid,
            )
            cnt = result.records[0]["cnt"] if result.records else 0
            print(f"  {{gid}}  ({{cnt}} nodes)")
        driver.close()
        print("\\nExecuta amb --execute per eliminar.")
        sys.exit(0)

    print(f"S\'eliminaran {{len(ORPHANS)}} group_id(s):")
    for gid in ORPHANS:
        print(f"  {{gid}}")
    answer = input("\\nProcedir? [y/N]: ").strip().lower()
    if answer != "y":
        print("Operació cancel·lada.")
        driver.close()
        sys.exit(0)

    for gid in ORPHANS:
        result = driver.execute_query(
            "MATCH (n) WHERE n.group_id = $gid "
            "WITH n, n.group_id AS gid "
            "DETACH DELETE n "
            "RETURN count(n) AS deleted",
            gid=gid,
        )
        deleted = result.records[0]["deleted"] if result.records else 0
        print(f"  Eliminat: {{gid}} ({{deleted}} nodes)")

    driver.close()
    print("\\nEliminació completada.")


if __name__ == "__main__":
    main()
'''
