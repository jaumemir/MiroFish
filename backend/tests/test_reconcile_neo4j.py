"""Tests unitaris per a la lògica de reconciliació Neo4j."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'scripts'))

from reconcile_neo4j import classify_group_ids, OrphanCategory


def test_valid_group_id_not_classified_as_orphan():
    neo4j_gids = {"mirofish_abc123"}
    known_external_ids = {"mirofish_abc123"}
    known_sim_ids = set()
    known_project_ids = {"proj1"}
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
        "mirofish_sim_deadbeef1234_sim",
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


import sqlite3


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
