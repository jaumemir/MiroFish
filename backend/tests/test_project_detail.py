"""Tests d'integració per a l'endpoint GET /api/graph/project/:id/detail."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def app(in_memory_db):
    import backend.app.db as db_module
    saved_engine = db_module._engine
    saved_session = db_module._SessionLocal

    def _noop_init_db(url):
        db_module._engine = saved_engine
        db_module._SessionLocal = saved_session

    with patch('backend.app.db.init_db', side_effect=_noop_init_db):
        from backend.app import create_app
        application = create_app()

    application.config['TESTING'] = True
    application.extensions['storage'] = MagicMock()
    db_module._engine = saved_engine
    db_module._SessionLocal = saved_session
    return application


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


@pytest.fixture
def project(in_memory_db):
    from backend.app.models.db_models import ProjectModel
    from backend.app.db import get_session
    with get_session() as db:
        p = ProjectModel(
            name='Test Project',
            simulation_requirement='Test question',
            status='graph_completed',
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        return p.id


def test_project_detail_returns_aggregated_data(client, project):
    resp = client.get(f'/api/graph/project/{project}/detail')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'project' in data
    assert 'files' in data
    assert 'ontology' in data
    assert 'graph' in data
    assert 'simulations' in data


def test_project_detail_not_found(client):
    resp = client.get('/api/graph/project/nonexistent-id/detail')
    assert resp.status_code == 404


def test_project_detail_with_relations(client, app):
    from backend.app.models.db_models import ProjectModel, OntologyModel, GraphModel, SimulationModel
    from backend.app.db import get_session

    with get_session() as db:
        p = ProjectModel(
            name='Project With Relations',
            simulation_requirement='Test req',
            status='graph_completed',
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        project_id = p.id

        ontology = OntologyModel(
            project_id=project_id,
            version=1,
            entity_types={'Person': {}},
            edge_types={},
        )
        db.add(ontology)
        db.commit()
        db.refresh(ontology)

        graph = GraphModel(
            project_id=project_id,
            ontology_id=ontology.id,
            status='ready',
            node_count=10,
            edge_count=5,
            backend='zep',
        )
        db.add(graph)
        db.commit()
        db.refresh(graph)

        sim = SimulationModel(
            project_id=project_id,
            graph_id=graph.id,
            status='completed',
            platform='twitter',
            rounds_total=50,
            rounds_completed=50,
        )
        db.add(sim)
        db.commit()

    resp = client.get(f'/api/graph/project/{project_id}/detail')
    assert resp.status_code == 200
    data = resp.get_json()

    assert data['project']['name'] == 'Project With Relations'
    assert data['ontology'] is not None
    assert data['ontology']['version'] == 1
    assert data['graph'] is not None
    assert data['graph']['node_count'] == 10
    assert data['graph']['status'] == 'ready'
    assert len(data['simulations']) == 1
    assert data['simulations'][0]['status'] == 'completed'
    assert data['simulations'][0]['platform'] == 'twitter'


def test_simulation_detail_returns_profiles_and_config(client, app, tmp_path, monkeypatch, in_memory_db):
    import json
    from backend.app.services import simulation_manager as sm_module

    monkeypatch.setattr(sm_module.SimulationManager, 'SIMULATION_DATA_DIR', str(tmp_path))

    sim_id = "sim_detail_test001"
    sim_dir = tmp_path / sim_id
    sim_dir.mkdir()

    # Insert a SimulationModel DB record so rounds_total/rounds_completed are populated
    from backend.app.models.db_models import ProjectModel, SimulationModel
    from backend.app.db import get_session
    with get_session() as db:
        proj = ProjectModel(name='Detail Test Project', simulation_requirement='q')
        db.add(proj)
        db.flush()
        sim_record = SimulationModel(
            id=sim_id,
            project_id=proj.id,
            status='completed',
            platform='twitter',
            rounds_total=30,
            rounds_completed=30,
        )
        db.add(sim_record)
        db.commit()

    state = {
        "simulation_id": sim_id,
        "project_id": "proj_detail_test",
        "graph_id": "g_detail_test",
        "status": "completed",
        "entities_count": 2,
        "profiles_count": 2,
        "entity_types": [],
        "config_generated": True,
        "config_reasoning": "",
        "current_round": 10,
        "twitter_status": "completed",
        "reddit_status": "not_started",
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T12:00:00",
        "error": None,
        "parent_simulation_id": None,
        "graph_id_simulation": None,
        "enable_twitter": True,
        "enable_reddit": False,
    }
    (sim_dir / "state.json").write_text(json.dumps(state))

    profiles = [
        {"user_id": 0, "user_name": "alice", "name": "Alice", "bio": "Bio A", "persona": "Curious", "manually_edited": False},
        {"user_id": 1, "user_name": "bob", "name": "Bob", "bio": "Bio B", "persona": "Bold", "manually_edited": False},
    ]
    (sim_dir / "twitter_profiles.json").write_text(json.dumps(profiles))

    sim_config = {"max_rounds": 50, "platform": "twitter"}
    (sim_dir / "simulation_config.json").write_text(json.dumps(sim_config))

    resp = client.get(f'/api/simulation/{sim_id}/detail')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'simulation' in data
    assert 'profiles' in data
    assert 'config' in data
    assert data['simulation']['graph_id'] == 'g_detail_test'
    assert data['simulation']['status'] == 'completed'
    assert len(data['profiles']) == 2
    assert data['profiles'][0]['user_name'] == 'alice'
    assert data['config']['max_rounds'] == 50
    assert 'rounds_total' in data['simulation']
    assert 'rounds_completed' in data['simulation']
    assert data['simulation']['rounds_total'] == 30
    assert data['simulation']['rounds_completed'] == 30
