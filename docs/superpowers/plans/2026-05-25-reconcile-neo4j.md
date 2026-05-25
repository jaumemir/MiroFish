# Reconciliació Neo4j Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear `scripts/reconcile_neo4j.py` que detecta `group_id` orfes a Neo4j comparant-los amb la BBDD SQLite de MiroFish, genera un log detallat i un `reconcile_delete.py` executable.

**Architecture:** Script Python autònom (sense dependències del backend de MiroFish) amb tres passos: (1) recollir `group_id` de Neo4j, (2) recollir IDs coneguts de SQLite, (3) creuament i classificació en `BASE_ORPHAN` / `SIM_ORPHAN` / `DANGLING_PROJECT`. Genera dos fitxers de sortida: log detallat i script d'eliminació amb dry-run per defecte.

**Tech Stack:** Python 3.11+, `neo4j` (driver ja al venv), `python-dotenv` (ja al venv), `sqlite3` (stdlib), `argparse` (stdlib).

---

## Mapa de fitxers

| Fitxer | Acció | Responsabilitat |
|--------|-------|-----------------|
| `scripts/reconcile_neo4j.py` | Crear | Script principal: CLI, connexions, 3 passos, generació d'outputs |
| `scripts/reconcile_delete.py` | Generat en execució | Script d'eliminació amb dry-run/execute |
| `scripts/reconcile_YYYYMMDD_HHMMSS.log` | Generat en execució | Log detallat del procés |
| `backend/tests/test_reconcile_neo4j.py` | Crear | Tests unitaris de la lògica de reconciliació |

---

## Task 1: Lògica de reconciliació pura (sense I/O)

La lògica de creuament és fàcil de testejar si s'aïlla de les connexions. Comencem amb les funcions pures de classificació.

**Files:**
- Create: `scripts/reconcile_neo4j.py` (esquelet inicial amb funcions pures)
- Create: `backend/tests/test_reconcile_neo4j.py`

- [ ] **Step 1: Crear el fitxer de test**

```python
# backend/tests/test_reconcile_neo4j.py
"""Tests unitaris per a la lògica de reconciliació Neo4j."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'scripts'))

from reconcile_neo4j import classify_group_ids, OrphanCategory


def test_valid_group_id_not_classified_as_orphan():
    neo4j_gids = {"mirofish_abc123"}
    known_external_ids = {"mirofish_abc123"}
    known_sim_ids = set()
    known_project_ids = set()
    graph_rows = [{"external_id": "mirofish_abc123", "project_id": "proj1", "graph_id": "g1"}]

    result = classify_group_ids(neo4j_gids, known_external_ids, known_sim_ids, known_project_ids, graph_rows)
    assert result == []


def test_base_orphan_not_in_sqlite():
    neo4j_gids = {"mirofish_deadbeef"}
    known_external_ids = set()
    known_sim_ids = set()
    known_project_ids = set()
    graph_rows = []

    result = classify_group_ids(neo4j_gids, known_external_ids, known_sim_ids, known_project_ids, graph_rows)
    assert len(result) == 1
    assert result[0]["group_id"] == "mirofish_deadbeef"
    assert result[0]["category"] == OrphanCategory.BASE_ORPHAN
    assert "mirofish_deadbeef" in result[0]["reason"]


def test_sim_orphan_no_simulation_in_sqlite():
    neo4j_gids = {"mirofish_sim_aabbcc112233_sim"}
    known_external_ids = set()
    known_sim_ids = set()  # sim_aabbcc112233 no existeix
    known_project_ids = set()
    graph_rows = []

    result = classify_group_ids(neo4j_gids, known_external_ids, known_sim_ids, known_project_ids, graph_rows)
    assert len(result) == 1
    assert result[0]["category"] == OrphanCategory.SIM_ORPHAN
    assert "sim_aabbcc112233" in result[0]["reason"]


def test_sim_valid_simulation_exists():
    neo4j_gids = {"mirofish_sim_aabbcc112233_sim"}
    known_external_ids = set()
    known_sim_ids = {"sim_aabbcc112233"}
    known_project_ids = set()
    graph_rows = []

    result = classify_group_ids(neo4j_gids, known_external_ids, known_sim_ids, known_project_ids, graph_rows)
    assert result == []


def test_dangling_project_graph_exists_but_project_deleted():
    neo4j_gids = {"mirofish_99887766"}
    known_external_ids = {"mirofish_99887766"}
    known_sim_ids = set()
    known_project_ids = set()  # project_id no existeix
    graph_rows = [{"external_id": "mirofish_99887766", "project_id": "proj_deleted", "graph_id": "g99"}]

    result = classify_group_ids(neo4j_gids, known_external_ids, known_sim_ids, known_project_ids, graph_rows)
    assert len(result) == 1
    assert result[0]["category"] == OrphanCategory.DANGLING_PROJECT
    assert "proj_deleted" in result[0]["reason"]


def test_multiple_group_ids_mixed():
    neo4j_gids = {
        "mirofish_valid1",
        "mirofish_orphan1",
        "mirofish_sim_deadbeef123456_sim",
        "mirofish_dangling",
    }
    known_external_ids = {"mirofish_valid1", "mirofish_dangling"}
    known_sim_ids = set()
    known_project_ids = {"proj_valid"}
    graph_rows = [
        {"external_id": "mirofish_valid1",   "project_id": "proj_valid",   "graph_id": "g1"},
        {"external_id": "mirofish_dangling",  "project_id": "proj_missing", "graph_id": "g2"},
    ]

    result = classify_group_ids(neo4j_gids, known_external_ids, known_sim_ids, known_project_ids, graph_rows)
    categories = {r["category"] for r in result}
    assert OrphanCategory.BASE_ORPHAN in categories
    assert OrphanCategory.SIM_ORPHAN in categories
    assert OrphanCategory.DANGLING_PROJECT in categories
    assert len(result) == 3
```

- [ ] **Step 2: Executar tests per verificar que fallen**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/test_reconcile_neo4j.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'reconcile_neo4j'`

- [ ] **Step 3: Crear l'esquelet de `reconcile_neo4j.py` amb les funcions pures**

```python
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
# sim_id segueix el format sim_[a-f0-9]{12}
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
```

- [ ] **Step 4: Executar tests per verificar que passen**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/test_reconcile_neo4j.py -v
```

Expected: tots els tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add scripts/reconcile_neo4j.py backend/tests/test_reconcile_neo4j.py
git commit -m "feat(reconcile): lògica pura de classificació d'orfes Neo4j"
```

---

## Task 2: Lectura de la BBDD SQLite

Funció que llegeix les tres taules necessàries de SQLite i retorna les estructures que necessita `classify_group_ids`. Inclou detecció d'inconsistències (GraphModel sense external_id, backend!=graphiti).

**Files:**
- Modify: `scripts/reconcile_neo4j.py` (afegir `read_sqlite`)
- Modify: `backend/tests/test_reconcile_neo4j.py` (afegir tests de `read_sqlite`)

- [ ] **Step 1: Afegir tests de `read_sqlite`**

Afegir al final de `backend/tests/test_reconcile_neo4j.py`:

```python
import sqlite3
import tempfile
import os


def _make_test_db(graphs=None, simulations=None, projects=None):
    """Crea una BBDD SQLite en memòria amb les taules necessàries."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE graphs (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            backend TEXT,
            external_id TEXT,
            status TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE simulations (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            graph_id TEXT,
            status TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            name TEXT
        )
    """)
    for row in (graphs or []):
        conn.execute(
            "INSERT INTO graphs VALUES (?,?,?,?,?)",
            (row["id"], row["project_id"], row["backend"], row.get("external_id"), row.get("status", "ready"))
        )
    for row in (simulations or []):
        conn.execute(
            "INSERT INTO simulations VALUES (?,?,?,?)",
            (row["id"], row.get("project_id"), row.get("graph_id"), row.get("status", "completed"))
        )
    for row in (projects or []):
        conn.execute("INSERT INTO projects VALUES (?,?)", (row["id"], row.get("name", "")))
    conn.commit()
    return conn


def test_read_sqlite_basic():
    from reconcile_neo4j import read_sqlite
    conn = _make_test_db(
        graphs=[{"id": "g1", "project_id": "p1", "backend": "graphiti", "external_id": "mirofish_abc"}],
        simulations=[{"id": "sim_aabbcc112233", "project_id": "p1"}],
        projects=[{"id": "p1"}],
    )
    result = read_sqlite(conn)
    assert "mirofish_abc" in result["known_external_ids"]
    assert "sim_aabbcc112233" in result["known_sim_ids"]
    assert "p1" in result["known_project_ids"]
    assert len(result["graph_rows"]) == 1
    assert result["graph_rows"][0]["graph_id"] == "g1"
    assert result["warnings"] == []


def test_read_sqlite_warns_graphiti_null_external_id():
    from reconcile_neo4j import read_sqlite
    conn = _make_test_db(
        graphs=[{"id": "g1", "project_id": "p1", "backend": "graphiti", "external_id": None}],
        projects=[{"id": "p1"}],
    )
    result = read_sqlite(conn)
    assert result["known_external_ids"] == set()
    assert any("external_id=NULL" in w for w in result["warnings"])


def test_read_sqlite_warns_zep_backend():
    from reconcile_neo4j import read_sqlite
    conn = _make_test_db(
        graphs=[{"id": "g2", "project_id": "p1", "backend": "zep", "external_id": "zep_xyz"}],
        projects=[{"id": "p1"}],
    )
    result = read_sqlite(conn)
    assert "zep_xyz" not in result["known_external_ids"]
    assert any("backend='zep'" in w for w in result["warnings"])


def test_read_sqlite_empty_tables():
    from reconcile_neo4j import read_sqlite
    conn = _make_test_db()
    result = read_sqlite(conn)
    assert result["known_external_ids"] == set()
    assert result["known_sim_ids"] == set()
    assert result["known_project_ids"] == set()
    assert result["graph_rows"] == []
    assert result["warnings"] == []
```

- [ ] **Step 2: Executar tests nous per verificar que fallen**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/test_reconcile_neo4j.py::test_read_sqlite_basic -v
```

Expected: `ImportError` o `AttributeError: module 'reconcile_neo4j' has no attribute 'read_sqlite'`

- [ ] **Step 3: Implementar `read_sqlite` a `reconcile_neo4j.py`**

Afegir després de `classify_group_ids`:

```python
import sqlite3 as _sqlite3


def read_sqlite(conn: _sqlite3.Connection) -> dict[str, Any]:
    """Llegeix les taules graphs, simulations i projects de la BBDD SQLite.

    Retorna:
        known_external_ids : set[str] — external_ids de graphs amb backend=graphiti
        known_sim_ids      : set[str] — ids de totes les simulacions
        known_project_ids  : set[str] — ids de tots els projectes
        graph_rows         : list[dict] — files de graphs amb external_id vàlid
        warnings           : list[str] — inconsistències detectades (no generen eliminació)
    """
    conn.row_factory = _sqlite3.Row
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
```

- [ ] **Step 4: Executar tots els tests**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/test_reconcile_neo4j.py -v
```

Expected: tots els tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add scripts/reconcile_neo4j.py backend/tests/test_reconcile_neo4j.py
git commit -m "feat(reconcile): lectura BBDD SQLite amb detecció d'inconsistències"
```

---

## Task 3: Connexió Neo4j i lectura de `group_id`s

Funció que connecta a Neo4j i retorna tots els `group_id` únics. S'usa el driver oficial `neo4j`.

**Files:**
- Modify: `scripts/reconcile_neo4j.py` (afegir `read_neo4j_group_ids`)
- Modify: `backend/tests/test_reconcile_neo4j.py` (afegir test amb mock del driver)

- [ ] **Step 1: Afegir test amb mock de Neo4j**

Afegir al final de `backend/tests/test_reconcile_neo4j.py`:

```python
from unittest.mock import MagicMock, patch


def test_read_neo4j_group_ids_returns_set():
    from reconcile_neo4j import read_neo4j_group_ids

    mock_record1 = MagicMock()
    mock_record1.__getitem__ = lambda self, k: "mirofish_abc" if k == "gid" else None
    mock_record2 = MagicMock()
    mock_record2.__getitem__ = lambda self, k: "mirofish_xyz" if k == "gid" else None

    mock_result = MagicMock()
    mock_result.records = [mock_record1, mock_record2]

    mock_driver = MagicMock()
    mock_driver.execute_query.return_value = mock_result

    result = read_neo4j_group_ids(mock_driver)
    assert result == {"mirofish_abc", "mirofish_xyz"}
    mock_driver.execute_query.assert_called_once()
    call_args = mock_driver.execute_query.call_args[0][0]
    assert "group_id" in call_args
    assert "DISTINCT" in call_args


def test_read_neo4j_group_ids_empty():
    from reconcile_neo4j import read_neo4j_group_ids

    mock_result = MagicMock()
    mock_result.records = []
    mock_driver = MagicMock()
    mock_driver.execute_query.return_value = mock_result

    result = read_neo4j_group_ids(mock_driver)
    assert result == set()
```

- [ ] **Step 2: Executar tests nous per verificar que fallen**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/test_reconcile_neo4j.py::test_read_neo4j_group_ids_returns_set -v
```

Expected: `AttributeError: module 'reconcile_neo4j' has no attribute 'read_neo4j_group_ids'`

- [ ] **Step 3: Implementar `read_neo4j_group_ids`**

Afegir a `scripts/reconcile_neo4j.py` (després de `read_sqlite`):

```python
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
```

- [ ] **Step 4: Executar tots els tests**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/test_reconcile_neo4j.py -v
```

Expected: tots els tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add scripts/reconcile_neo4j.py backend/tests/test_reconcile_neo4j.py
git commit -m "feat(reconcile): lectura group_ids de Neo4j"
```

---

## Task 4: Generació del log i del `reconcile_delete.py`

Funcions que produeixen els dos fitxers de sortida a partir dels orfes classificats.

**Files:**
- Modify: `scripts/reconcile_neo4j.py` (afegir `generate_log_content` i `generate_delete_script`)
- Modify: `backend/tests/test_reconcile_neo4j.py` (afegir tests de generació)

- [ ] **Step 1: Afegir tests de generació**

Afegir al final de `backend/tests/test_reconcile_neo4j.py`:

```python
def test_generate_log_content_includes_all_sections():
    from reconcile_neo4j import generate_log_content, OrphanCategory

    neo4j_gids = {"mirofish_orphan", "mirofish_valid"}
    sqlite_data = {
        "known_external_ids": {"mirofish_valid"},
        "known_sim_ids": set(),
        "known_project_ids": {"p1"},
        "graph_rows": [{"external_id": "mirofish_valid", "project_id": "p1", "graph_id": "g1"}],
        "warnings": ["GraphModel id='gx' backend='zep' — ignorat"],
    }
    orphans = [
        {"group_id": "mirofish_orphan", "category": OrphanCategory.BASE_ORPHAN,
         "reason": "Cap GraphModel amb external_id='mirofish_orphan' a la BBDD"},
    ]
    log = generate_log_content(
        neo4j_uri="neo4j+s://test",
        db_path="/tmp/test.db",
        neo4j_gids=neo4j_gids,
        sqlite_data=sqlite_data,
        orphans=orphans,
        delete_script_path="scripts/reconcile_delete.py",
        log_path="scripts/reconcile_test.log",
        timestamp="2026-05-25 14:30:00",
    )
    assert "[PAS 1]" in log
    assert "[PAS 2]" in log
    assert "[PAS 3]" in log
    assert "RESUM" in log
    assert "BASE_ORPHAN" in log
    assert "mirofish_orphan" in log
    assert "ADVERTÈNCIA" in log
    assert "✓ VALID" in log
    assert "reconcile_delete.py" in log


def test_generate_delete_script_contains_orphans():
    from reconcile_neo4j import generate_delete_script, OrphanCategory

    orphans = [
        {"group_id": "mirofish_orphan1", "category": OrphanCategory.BASE_ORPHAN,
         "reason": "Cap GraphModel"},
        {"group_id": "mirofish_sim_aabbcc112233_sim", "category": OrphanCategory.SIM_ORPHAN,
         "reason": "Cap SimulationModel"},
    ]
    script = generate_delete_script(
        orphans=orphans,
        neo4j_uri="neo4j+s://test",
        log_path="scripts/reconcile_test.log",
        timestamp="2026-05-25 14:30:00",
    )
    assert "mirofish_orphan1" in script
    assert "BASE_ORPHAN" in script
    assert "mirofish_sim_aabbcc112233_sim" in script
    assert "SIM_ORPHAN" in script
    assert "--execute" in script
    assert "dry-run" in script.lower() or "dry_run" in script.lower()
    assert "DETACH DELETE" in script


def test_generate_delete_script_no_orphans():
    from reconcile_neo4j import generate_delete_script

    script = generate_delete_script(
        orphans=[],
        neo4j_uri="neo4j+s://test",
        log_path="scripts/reconcile_test.log",
        timestamp="2026-05-25 14:30:00",
    )
    assert "ORPHANS = []" in script or "ORPHANS: list = []" in script
```

- [ ] **Step 2: Executar tests nous per verificar que fallen**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/test_reconcile_neo4j.py::test_generate_log_content_includes_all_sections -v
```

Expected: `AttributeError: module 'reconcile_neo4j' has no attribute 'generate_log_content'`

- [ ] **Step 3: Implementar `generate_log_content`**

Afegir a `scripts/reconcile_neo4j.py`:

```python
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
    lines.append(f"[PAS 2] BBDD SQLite: {db_path}")
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
            lines.append(f"[PAS 3] ✗ {o['category']:<20} {gid} — {o['reason']}")
        else:
            lines.append(f"[PAS 3] ✓ VALID               {gid}")
    lines.append("")

    # Resum
    counts = {}
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
```

- [ ] **Step 4: Implementar `generate_delete_script`**

Afegir a `scripts/reconcile_neo4j.py`:

```python
def generate_delete_script(
    orphans: list[dict[str, Any]],
    neo4j_uri: str,
    log_path: str,
    timestamp: str,
) -> str:
    """Genera el contingut del script reconcile_delete.py."""
    counts = {}
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
                        help="Executa l'eliminació (per defecte: dry-run)")
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
        print(f"DRY-RUN: s'eliminaria {{len(ORPHANS)}} group_id(s):\\n")
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

    print(f"S'eliminaran {{len(ORPHANS)}} group_id(s):")
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
```

- [ ] **Step 5: Executar tots els tests**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/test_reconcile_neo4j.py -v
```

Expected: tots els tests `PASSED`.

- [ ] **Step 6: Commit**

```bash
git add scripts/reconcile_neo4j.py backend/tests/test_reconcile_neo4j.py
git commit -m "feat(reconcile): generació de log i reconcile_delete.py"
```

---

## Task 5: CLI principal i integració de tot el flux

El `main()` del script: parseig d'args, lectura de `.env`, connexions, crida als 3 passos, escriptura dels fitxers de sortida.

**Files:**
- Modify: `scripts/reconcile_neo4j.py` (afegir `load_config`, `open_sqlite`, `main`)

- [ ] **Step 1: Implementar `load_config` i `open_sqlite`**

Afegir a `scripts/reconcile_neo4j.py`:

```python
import argparse as _argparse
import os as _os
import sys as _sys
from datetime import datetime as _datetime
from pathlib import Path as _Path


def load_config(args: _argparse.Namespace) -> dict[str, str]:
    """Carrega la configuració des de .env i args CLI.

    Prioritat: args CLI > .env > error si manquen valors obligatoris.
    """
    # Determinar ruta del .env
    env_file = _Path(args.env_file) if args.env_file else _Path(__file__).parent.parent / ".env"

    env_values: dict[str, str] = {}
    if env_file.exists():
        try:
            from dotenv import dotenv_values
            env_values = dict(dotenv_values(env_file))
        except ImportError:
            pass  # python-dotenv no disponible, continuem sense .env

    def _get(cli_val, env_key, default=None):
        if cli_val is not None:
            return cli_val
        if env_key in env_values:
            return env_values[env_key]
        if default is not None:
            return default
        return _os.environ.get(env_key, "")

    # DATABASE_URL pot ser sqlite:///path o ruta directa
    db_url = _get(args.db_path, "DATABASE_URL", "")
    if db_url.startswith("sqlite:///"):
        db_path = db_url[len("sqlite:///"):]
        # Ruta relativa → absoluta respecte al directori del .env
        if not _os.path.isabs(db_path):
            db_path = str(env_file.parent / db_path)
    else:
        db_path = db_url

    return {
        "db_path":       db_path,
        "neo4j_uri":     _get(args.neo4j_uri,      "NEO4J_URI",      ""),
        "neo4j_user":    _get(args.neo4j_user,     "NEO4J_USER",     "neo4j"),
        "neo4j_password": _get(args.neo4j_password, "NEO4J_PASSWORD", ""),
        "output_dir":    args.output_dir or str(_Path(__file__).parent),
    }


def open_sqlite(db_path: str) -> "_sqlite3.Connection":
    """Obre la connexió SQLite en mode lectura. Falla amb missatge clar si no existeix."""
    if not _os.path.exists(db_path):
        print(f"ERROR: BBDD SQLite no trobada: {db_path}", file=_sys.stderr)
        _sys.exit(1)
    conn = _sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = _sqlite3.Row
    return conn
```

- [ ] **Step 2: Implementar `main()`**

Afegir al final de `scripts/reconcile_neo4j.py`:

```python
def _parse_args() -> _argparse.Namespace:
    parser = _argparse.ArgumentParser(
        description="Reconcilia group_ids Neo4j amb la BBDD SQLite de MiroFish."
    )
    parser.add_argument("--env-file",        default=None, help="Camí al fitxer .env")
    parser.add_argument("--db-path",         default=None, help="Camí a la BBDD SQLite (sobreescriu DATABASE_URL del .env)")
    parser.add_argument("--neo4j-uri",       default=None, help="URI de Neo4j")
    parser.add_argument("--neo4j-user",      default=None, help="Usuari Neo4j")
    parser.add_argument("--neo4j-password",  default=None, help="Contrasenya Neo4j")
    parser.add_argument("--output-dir",      default=None, help="Directori de sortida (defecte: scripts/)")
    parser.add_argument("--log-level",       default="INFO", choices=["DEBUG", "INFO", "WARNING"])
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    cfg = load_config(args)

    # Validar configuració obligatòria
    missing = [k for k in ("neo4j_uri", "neo4j_password", "db_path") if not cfg.get(k)]
    if missing:
        print(f"ERROR: Falten valors de configuració: {', '.join(missing)}", file=_sys.stderr)
        print("Comprova el fitxer .env o passa els arguments --neo4j-uri/--neo4j-password/--db-path",
              file=_sys.stderr)
        _sys.exit(1)

    timestamp = _datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ts_file   = _datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = _Path(cfg["output_dir"])
    log_path    = output_dir / f"reconcile_{ts_file}.log"
    delete_path = output_dir / "reconcile_delete.py"

    if delete_path.exists():
        print(f"AVÍS: {delete_path} ja existeix i serà sobreescrit.")

    # Connectar Neo4j
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            cfg["neo4j_uri"],
            auth=(cfg["neo4j_user"], cfg["neo4j_password"]),
        )
    except Exception as exc:
        print(f"ERROR: No s'ha pogut connectar a Neo4j ({cfg['neo4j_uri']}): {exc}", file=_sys.stderr)
        _sys.exit(1)

    # PAS 1: Llegir group_ids de Neo4j
    print(f"[PAS 1] Llegint group_ids de Neo4j ({cfg['neo4j_uri']})...")
    try:
        neo4j_gids = read_neo4j_group_ids(driver)
    except Exception as exc:
        print(f"ERROR: Consulta Neo4j fallida: {exc}", file=_sys.stderr)
        driver.close()
        _sys.exit(1)
    print(f"[PAS 1] group_ids trobats: {len(neo4j_gids)}")

    # PAS 2: Llegir BBDD SQLite
    print(f"[PAS 2] Llegint BBDD SQLite ({cfg['db_path']})...")
    conn = open_sqlite(cfg["db_path"])
    sqlite_data = read_sqlite(conn)
    conn.close()
    print(f"[PAS 2] external_ids (graphiti): {len(sqlite_data['known_external_ids'])}, "
          f"sim_ids: {len(sqlite_data['known_sim_ids'])}, "
          f"project_ids: {len(sqlite_data['known_project_ids'])}")
    for w in sqlite_data["warnings"]:
        print(f"[PAS 2] ADVERTÈNCIA: {w}")

    # PAS 3: Classificar
    print("[PAS 3] Classificant orfes...")
    orphans = classify_group_ids(
        neo4j_gids=neo4j_gids,
        known_external_ids=sqlite_data["known_external_ids"],
        known_sim_ids=sqlite_data["known_sim_ids"],
        known_project_ids=sqlite_data["known_project_ids"],
        graph_rows=sqlite_data["graph_rows"],
    )
    driver.close()

    # Generar log
    log_content = generate_log_content(
        neo4j_uri=cfg["neo4j_uri"],
        db_path=cfg["db_path"],
        neo4j_gids=neo4j_gids,
        sqlite_data=sqlite_data,
        orphans=orphans,
        delete_script_path=str(delete_path),
        log_path=str(log_path),
        timestamp=timestamp,
    )
    log_path.write_text(log_content, encoding="utf-8")
    print(f"\n{log_content}")

    # Generar script d'eliminació
    delete_content = generate_delete_script(
        orphans=orphans,
        neo4j_uri=cfg["neo4j_uri"],
        log_path=str(log_path),
        timestamp=timestamp,
    )
    delete_path.write_text(delete_content, encoding="utf-8")
    delete_path.chmod(0o755)

    print(f"\nLog guardat a: {log_path}")
    print(f"Script d'eliminació generat: {delete_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Fer executable el script principal**

```bash
chmod +x /home/ubuntu/dev/MiroFish/scripts/reconcile_neo4j.py
```

- [ ] **Step 4: Executar tots els tests per verificar que segueixen passant**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/test_reconcile_neo4j.py -v
```

Expected: tots els tests `PASSED`.

- [ ] **Step 5: Verificar que el CLI funciona amb --help**

```bash
cd /home/ubuntu/dev/MiroFish
python3 scripts/reconcile_neo4j.py --help
```

Expected: sortida d'ajuda amb tots els arguments documentats (sense errors d'importació).

- [ ] **Step 6: Commit**

```bash
git add scripts/reconcile_neo4j.py backend/tests/test_reconcile_neo4j.py
git commit -m "feat(reconcile): CLI principal i integració del flux complet"
```

---

## Self-Review

**Cobertura de la spec:**

| Requisit spec | Task |
|---------------|------|
| Script autònom sense deps del backend | Task 1 (imports purs) |
| Args CLI + .env amb prioritat correcta | Task 5 (`load_config`) |
| PAS 1: query Neo4j `DISTINCT group_id` | Task 3 |
| PAS 2: lectura SQLite (graphs, simulations, projects) | Task 2 |
| PAS 2: advertències per graphiti-NULL, backend!=graphiti | Task 2 |
| PAS 3: classificació BASE_ORPHAN / SIM_ORPHAN / DANGLING_PROJECT | Task 1 |
| Log detallat amb els 3 passos i resum | Task 4 |
| `reconcile_delete.py` generat amb dry-run per defecte | Task 4 |
| `reconcile_delete.py` --execute amb confirmació interactiva | Task 4 |
| Sobreescriptura de `reconcile_delete.py` amb avís | Task 5 (`main`) |
| Error clar si Neo4j no accessible | Task 5 |
| Error clar si SQLite no accessible | Task 5 (`open_sqlite`) |
| Patró `sim_id` = `sim_[a-f0-9]{12}` | Task 1 (`_SIM_GID_RE`) |

**Tipus consistents entre tasks:** `classify_group_ids` rep `set[str]` i `list[dict]` definits a Task 1; `read_sqlite` retorna el dict amb les mateixes claus que consumeix Task 5; `generate_log_content` i `generate_delete_script` reben `list[dict]` amb `group_id`/`category`/`reason` tal com produeix `classify_group_ids`. ✓

**Placeholders:** Cap TBD ni "similar a task N". ✓
