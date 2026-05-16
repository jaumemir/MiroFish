# Project Detail View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear `ProjectDetailView` com a hub de treball per a projectes existents, amb gestió de graph base, llistat de simulacions i accions per entrar al flux de MiroFish.

**Architecture:** Nova vista `ProjectDetailView` amb layout de dues columnes (info projecte + simulacions). Es reutilitza `Process.vue` en mode `adjust` per editar simulacions existents. La navegació de retorn s'implementa via `history.state.backTo` a les vistes existents. Nous endpoints backend per servir dades agregades.

**Tech Stack:** Vue 3 (Composition API, `<script setup>`), Vue Router 4, Axios, Flask + SQLAlchemy, pytest

---

## Mapa de fitxers

| Acció | Fitxer | Responsabilitat |
| --- | --- | --- |
| Crear | `frontend/src/views/ProjectDetailView.vue` | Vista hub: columna esquerra + dreta |
| Modificar | `frontend/src/router/index.js` | Afegir ruta `/project/:projectId` |
| Modificar | `frontend/src/views/Home.vue` | `openProject()` redirigeix a ProjectDetail |
| Modificar | `frontend/src/views/SimulationRunView.vue` | Respectar `history.state.backTo` |
| Modificar | `frontend/src/views/ReportView.vue` | Respectar `history.state.backTo` |
| Modificar | `frontend/src/views/InteractionView.vue` | Respectar `history.state.backTo` |
| Modificar | `frontend/src/views/Process.vue` | Mode `adjust`: read-only + regles consistència |
| Modificar | `frontend/src/components/LanguageSwitcher.vue` | Fix color text sobre navbar negra |
| Modificar | `backend/app/api/graph.py` | Nou endpoint `GET /project/:id/detail` |
| Modificar | `backend/app/api/simulation.py` | Nous endpoints: detail, DELETE, log download |
| Modificar | `backend/app/api/report.py` | Endpoint download MD si no existeix |
| Crear | `frontend/src/api/project.js` | Funcions API per a ProjectDetailView |
| Crear | `backend/tests/test_project_detail.py` | Tests dels nous endpoints |

---

## Task 1: Fix LanguageSwitcher + Ruta ProjectDetail + Home redirect

**Files:**
- Modify: `frontend/src/components/LanguageSwitcher.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/views/Home.vue`

- [ ] **Step 1: Llegir els fitxers actuals**

```bash
cat -n frontend/src/components/LanguageSwitcher.vue
cat -n frontend/src/router/index.js
grep -n "openProject\|router.push\|Process" frontend/src/views/Home.vue
```

- [ ] **Step 2: Verificar fix del LanguageSwitcher**

El fix ja ha estat aplicat manualment. Verificar que `.switcher-trigger` té `color: white` o equivalent visible sobre fons negre. Si el fix no és visible, afegir al bloc `<style scoped>`:

```css
.switcher-trigger {
  color: #ffffff;
}
```

- [ ] **Step 3: Afegir la ruta ProjectDetail al router**

A `frontend/src/router/index.js`, importar la nova vista i afegir la ruta just després de la ruta `Home`:

```js
import ProjectDetailView from '@/views/ProjectDetailView.vue'

// A l'array de rutes, afegir:
{ path: '/project/:projectId', name: 'ProjectDetail', component: ProjectDetailView, props: true },
```

- [ ] **Step 4: Modificar Home.vue per redirigir a ProjectDetail**

Localitzar `openProject` a `frontend/src/views/Home.vue` (~línia 162) i canviar:

```js
// ABANS:
function openProject(project) {
  router.push({ name: 'Process', params: { projectId: project.id } })
}

// DESPRÉS:
function openProject(project) {
  router.push({ name: 'ProjectDetail', params: { projectId: project.id } })
}
```

- [ ] **Step 5: Crear ProjectDetailView.vue buit per validar la ruta**

Crear `frontend/src/views/ProjectDetailView.vue` amb contingut mínim:

```vue
<template>
  <div class="project-detail">
    <p>ProjectDetailView — projectId: {{ projectId }}</p>
  </div>
</template>

<script setup>
defineProps({ projectId: String })
</script>
```

- [ ] **Step 6: Verificar al navegador**

```bash
npm run dev
```

Obrir Home, clicar un projecte existent → ha d'anar a `/project/:id` i mostrar el text del placeholder. Crear un projecte nou → ha de seguir el flux normal (Process Step 1).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/LanguageSwitcher.vue frontend/src/router/index.js frontend/src/views/Home.vue frontend/src/views/ProjectDetailView.vue
git commit -m "feat(project-detail): ruta /project/:id i redirect des de Home"
```

---

## Task 2: Backend — GET /api/graph/project/:id/detail

**Files:**
- Modify: `backend/app/api/graph.py`
- Create: `backend/tests/test_project_detail.py`

- [ ] **Step 1: Examinar l'endpoint GET /project/:id existent**

```bash
sed -n '40,75p' backend/app/api/graph.py
```

Prendre nota de com s'obté el projecte, com es fan les queries de relacions i com es construeix la resposta JSON.

- [ ] **Step 2: Examinar els models per entendre les relacions**

```bash
grep -n "class.*Model\|files\|ontologies\|graphs\|simulations\|reports" backend/app/models/db_models.py | head -60
```

- [ ] **Step 3: Escriure el test que ha de fallar**

Crear `backend/tests/test_project_detail.py`:

```python
import pytest
from app import create_app
from app.db import db as _db
from app.models.db_models import ProjectModel, GraphModel, SimulationModel, OntologyModel, ProjectFileModel
import uuid

@pytest.fixture
def app():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def project(app):
    with app.app_context():
        p = ProjectModel(
            id=str(uuid.uuid4()),
            name='Test Project',
            simulation_requirement='Test question',
            status='graph_completed'
        )
        _db.session.add(p)
        _db.session.commit()
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
```

- [ ] **Step 4: Executar el test per verificar que falla**

```bash
cd backend && uv run pytest tests/test_project_detail.py -v
```

Esperat: FAIL — `404` o `AssertionError` perquè l'endpoint no existeix.

- [ ] **Step 5: Implementar l'endpoint a graph.py**

Afegir just després de l'endpoint `GET /project/<project_id>` existent (~línia 58):

```python
@graph_bp.route('/project/<project_id>/detail', methods=['GET'])
@jwt_required()
def get_project_detail(project_id):
    from app.models.db_models import ProjectModel, GraphModel, SimulationModel, OntologyModel, ProjectFileModel, ReportModel
    from app.db import db
    current_user_id = get_jwt_identity()

    project = db.session.get(ProjectModel, project_id)
    if not project or (project.user_id and project.user_id != current_user_id):
        return jsonify({'error': 'Not found'}), 404

    # Fitxer font (primer upload)
    source_file = next(
        (f for f in project.files if f.file_type == 'upload'),
        None
    )

    # Ontologia activa (la més recent)
    ontology = project.ontologies[-1] if project.ontologies else None

    # Graph base actiu (el més recent)
    graph = project.graphs[-1] if project.graphs else None

    # Simulacions ordenades per data de creació desc
    simulations = []
    for i, sim in enumerate(sorted(project.simulations, key=lambda s: s.created_at, reverse=True), 1):
        report = next((r for r in sim.reports), None)
        simulations.append({
            'id': sim.id,
            'ordinal': len(project.simulations) - i + 1,
            'status': sim.status,
            'platform': sim.platform,
            'rounds_total': sim.rounds_total,
            'rounds_completed': sim.rounds_completed,
            'graph_id': sim.graph_id,
            'created_at': sim.created_at.isoformat() if sim.created_at else None,
            'report_id': report.id if report else None,
            'report_status': report.status if report else None,
        })

    return jsonify({
        'project': {
            'id': project.id,
            'name': project.name,
            'status': project.status,
            'simulation_requirement': project.simulation_requirement,
            'created_at': project.created_at.isoformat() if project.created_at else None,
        },
        'files': [{
            'id': f.id,
            'original_name': f.original_name,
            'size': f.size,
            'mime_type': f.mime_type,
        } for f in project.files if f.file_type == 'upload'],
        'ontology': {
            'id': ontology.id,
            'version': ontology.version,
            'created_at': ontology.created_at.isoformat() if ontology.created_at else None,
        } if ontology else None,
        'graph': {
            'id': graph.id,
            'status': graph.status,
            'node_count': graph.node_count,
            'edge_count': graph.edge_count,
            'backend': graph.backend,
        } if graph else None,
        'simulations': simulations,
    }), 200
```

- [ ] **Step 6: Executar els tests per verificar que passen**

```bash
cd backend && uv run pytest tests/test_project_detail.py -v
```

Esperat: PASS per tots els tests.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/graph.py backend/tests/test_project_detail.py
git commit -m "feat(api): endpoint GET /project/:id/detail agregat"
```

---

## Task 3: Backend — Endpoints de descàrrega i DELETE simulació

**Files:**
- Modify: `backend/app/api/graph.py`
- Modify: `backend/app/api/simulation.py`
- Modify: `backend/app/api/report.py`

- [ ] **Step 1: Verificar quins endpoints de descàrrega ja existeixen**

```bash
grep -n "download\|DELETE\|log" backend/app/api/graph.py backend/app/api/simulation.py backend/app/api/report.py
```

- [ ] **Step 2: Verificar endpoint de descàrrega de fitxer font**

```bash
sed -n '748,800p' backend/app/api/graph.py
```

Si retorna el fitxer com a `send_file`, l'endpoint existeix i és correcte. Si no, afegir:

```python
@graph_bp.route('/project/<project_id>/download/source', methods=['GET'])
@jwt_required()
def download_project_source(project_id):
    from app.models.db_models import ProjectModel, ProjectFileModel
    from app.db import db
    from flask import send_file
    import os
    current_user_id = get_jwt_identity()
    project = db.session.get(ProjectModel, project_id)
    if not project or (project.user_id and project.user_id != current_user_id):
        return jsonify({'error': 'Not found'}), 404
    source_file = next((f for f in project.files if f.file_type == 'upload'), None)
    if not source_file or not os.path.exists(source_file.storage_path):
        return jsonify({'error': 'File not found'}), 404
    return send_file(source_file.storage_path, as_attachment=True, download_name=source_file.original_name)
```

- [ ] **Step 3: Afegir endpoint de descàrrega d'ontologia**

Afegir a `backend/app/api/graph.py` (després del download source):

```python
@graph_bp.route('/project/<project_id>/ontology/download', methods=['GET'])
@jwt_required()
def download_project_ontology(project_id):
    from app.models.db_models import ProjectModel
    from app.db import db
    import json
    current_user_id = get_jwt_identity()
    project = db.session.get(ProjectModel, project_id)
    if not project or (project.user_id and project.user_id != current_user_id):
        return jsonify({'error': 'Not found'}), 404
    ontology = project.ontologies[-1] if project.ontologies else None
    if not ontology:
        return jsonify({'error': 'No ontology found'}), 404
    data = {
        'entity_types': ontology.entity_types or {},
        'edge_types': ontology.edge_types or {},
    }
    from flask import Response
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename="ontology_v{ontology.version}.json"'}
    )
```

- [ ] **Step 4: Afegir endpoint DELETE simulació**

Verificar si existeix a `simulation.py`:

```bash
grep -n "DELETE\|delete" backend/app/api/simulation.py | head -20
```

Si no existeix, afegir a `backend/app/api/simulation.py`:

```python
@simulation_bp.route('/<simulation_id>', methods=['DELETE'])
@jwt_required()
def delete_simulation(simulation_id):
    from app.models.db_models import SimulationModel
    from app.db import db
    sim = db.session.get(SimulationModel, simulation_id)
    if not sim:
        return jsonify({'error': 'Not found'}), 404
    db.session.delete(sim)
    db.session.commit()
    return jsonify({'success': True}), 200
```

- [ ] **Step 5: Afegir endpoint de descàrrega d'informe MD**

Verificar si existeix a `report.py`:

```bash
grep -n "download\|\.md\|markdown" backend/app/api/report.py
```

Si no existeix endpoint per MD, afegir a `backend/app/api/report.py`:

```python
@report_bp.route('/<report_id>/download/md', methods=['GET'])
@jwt_required()
def download_report_md(report_id):
    from app.models.db_models import ReportModel
    from app.db import db
    from app.storage.azure_blob import get_storage
    report = db.session.get(ReportModel, report_id)
    if not report or report.status != 'completed':
        return jsonify({'error': 'Report not available'}), 404
    storage = get_storage()
    md_path = f"{report.storage_prefix}/report.md" if report.storage_prefix else None
    if not md_path:
        return jsonify({'error': 'Report file not found'}), 404
    content = storage.read_text(md_path)
    from flask import Response
    return Response(
        content,
        mimetype='text/markdown',
        headers={'Content-Disposition': f'attachment; filename="report_{report_id}.md"'}
    )
```

- [ ] **Step 6: Afegir endpoint de descàrrega de log de simulació**

```python
@simulation_bp.route('/<simulation_id>/log/download', methods=['GET'])
@jwt_required()
def download_simulation_log(simulation_id):
    from app.models.db_models import SimulationModel
    from app.db import db
    from flask import Response
    import os, json
    sim = db.session.get(SimulationModel, simulation_id)
    if not sim:
        return jsonify({'error': 'Not found'}), 404
    log_path = f'/tmp/mirofish_sim_{simulation_id}_log.json'
    if sim.actions_path and os.path.exists(sim.actions_path):
        log_path = sim.actions_path
    if not os.path.exists(log_path):
        return jsonify({'error': 'Log not available'}), 404
    with open(log_path, 'r') as f:
        content = f.read()
    return Response(
        content,
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename="simulation_{simulation_id}_log.json"'}
    )
```

- [ ] **Step 7: Executar tests existents per verificar que no s'ha trencat res**

```bash
cd backend && uv run pytest -v --tb=short 2>&1 | tail -30
```

Esperat: els tests existents passen.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/graph.py backend/app/api/simulation.py backend/app/api/report.py
git commit -m "feat(api): endpoints descàrrega ontologia/informe MD/log i DELETE simulació"
```

---

## Task 4: Backend — GET /api/simulation/:id/detail (mode adjust)

**Files:**
- Modify: `backend/app/api/simulation.py`
- Modify: `backend/tests/test_project_detail.py`

- [ ] **Step 1: Examinar l'endpoint GET /simulation/:id i GET /profiles existents**

```bash
sed -n '836,900p' backend/app/api/simulation.py
sed -n '1072,1130p' backend/app/api/simulation.py
sed -n '1340,1400p' backend/app/api/simulation.py
```

- [ ] **Step 2: Afegir test per al nou endpoint**

Afegir a `backend/tests/test_project_detail.py`:

```python
def test_simulation_detail_returns_profiles_and_config(client, project, app):
    with app.app_context():
        # Crear simulació de prova
        sim = SimulationModel(
            id=str(uuid.uuid4()),
            project_id=project,
            status='completed',
            platform='twitter',
            config={'max_rounds': 50},
            rounds_total=50,
            rounds_completed=50,
        )
        _db.session.add(sim)
        _db.session.commit()
        sim_id = sim.id

    resp = client.get(f'/api/simulation/{sim_id}/detail')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'simulation' in data
    assert 'profiles' in data
    assert 'config' in data
    assert 'graph_id' in data['simulation']
```

- [ ] **Step 3: Executar el test per verificar que falla**

```bash
cd backend && uv run pytest tests/test_project_detail.py::test_simulation_detail_returns_profiles_and_config -v
```

Esperat: FAIL.

- [ ] **Step 4: Implementar l'endpoint**

Afegir a `backend/app/api/simulation.py` (després de `GET /<simulation_id>`):

```python
@simulation_bp.route('/<simulation_id>/detail', methods=['GET'])
@jwt_required()
def get_simulation_detail(simulation_id):
    from app.models.db_models import SimulationModel
    from app.db import db
    import json, os

    sim = db.session.get(SimulationModel, simulation_id)
    if not sim:
        return jsonify({'error': 'Not found'}), 404

    # Carregar perfils d'agents des del fitxer de perfils
    profiles = []
    if sim.profiles_path and os.path.exists(sim.profiles_path):
        try:
            with open(sim.profiles_path, 'r') as f:
                profiles = json.load(f)
        except Exception:
            profiles = []

    return jsonify({
        'simulation': {
            'id': sim.id,
            'project_id': sim.project_id,
            'graph_id': sim.graph_id,
            'status': sim.status,
            'platform': sim.platform,
            'rounds_total': sim.rounds_total,
            'rounds_completed': sim.rounds_completed,
            'created_at': sim.created_at.isoformat() if sim.created_at else None,
        },
        'profiles': profiles,
        'config': sim.config or {},
    }), 200
```

- [ ] **Step 5: Executar els tests**

```bash
cd backend && uv run pytest tests/test_project_detail.py -v
```

Esperat: tots PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/simulation.py backend/tests/test_project_detail.py
git commit -m "feat(api): endpoint GET /simulation/:id/detail per mode adjust"
```

---

## Task 5: Frontend API — funcions per a ProjectDetailView

**Files:**
- Create: `frontend/src/api/project.js`

- [ ] **Step 1: Examinar l'estructura dels fitxers api existents**

```bash
cat -n frontend/src/api/graph.js | head -30
```

Prendre nota del patró: `import service from './index.js'` + funcions exportades.

- [ ] **Step 2: Crear frontend/src/api/project.js**

```js
import service from './index.js'

export async function getProjectDetail(projectId) {
  const res = await service.get(`/api/graph/project/${projectId}/detail`)
  return res.data
}

export async function downloadProjectSource(projectId, filename) {
  const res = await service.get(`/api/graph/project/${projectId}/download/source`, {
    responseType: 'blob',
  })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || 'source'
  a.click()
  URL.revokeObjectURL(url)
}

export async function downloadProjectOntology(projectId, version) {
  const res = await service.get(`/api/graph/project/${projectId}/ontology/download`, {
    responseType: 'blob',
  })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = `ontology_v${version || 1}.json`
  a.click()
  URL.revokeObjectURL(url)
}

export async function uploadOntology(projectId, file) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('project_id', projectId)
  const res = await service.post('/api/graph/ontology/import', formData)
  return res.data
}

export async function forceRebuildGraph(projectId) {
  const res = await service.post('/api/graph/build', { project_id: projectId, force: true })
  return res.data
}

export async function deleteSimulation(simulationId) {
  const res = await service.delete(`/api/simulation/${simulationId}`)
  return res.data
}

export async function downloadReportMd(reportId) {
  const res = await service.get(`/api/report/${reportId}/download/md`, {
    responseType: 'blob',
  })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = `report_${reportId}.md`
  a.click()
  URL.revokeObjectURL(url)
}

export async function downloadReportPdf(reportId) {
  const res = await service.get(`/api/report/${reportId}/download`, {
    responseType: 'blob',
  })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = `report_${reportId}.pdf`
  a.click()
  URL.revokeObjectURL(url)
}

export async function downloadSimulationLog(simulationId) {
  const res = await service.get(`/api/simulation/${simulationId}/log/download`, {
    responseType: 'blob',
  })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = `simulation_${simulationId}_log.json`
  a.click()
  URL.revokeObjectURL(url)
}

export async function generateReport(simulationId) {
  const res = await service.post('/api/report/generate', { simulation_id: simulationId })
  return res.data
}
```

- [ ] **Step 3: Verificar que no hi ha errors de sintaxi**

```bash
cd frontend && npx eslint src/api/project.js --no-eslintrc --rule '{"no-undef": "error"}' 2>&1 || true
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/project.js
git commit -m "feat(api): funcions frontend per a ProjectDetailView"
```

---

## Task 6: ProjectDetailView — Columna esquerra (info projecte + graph)

**Files:**
- Modify: `frontend/src/views/ProjectDetailView.vue`

- [ ] **Step 1: Examinar GraphPanel per entendre com s'usa**

```bash
grep -n "GraphPanel\|graph-panel\|props\|graphId" frontend/src/components/GraphPanel.vue | head -30
```

- [ ] **Step 2: Examinar un component Step existent per veure patrons d'estil**

```bash
sed -n '1,80p' frontend/src/components/Step1GraphBuild.vue
```

- [ ] **Step 3: Implementar la columna esquerra de ProjectDetailView**

Substituir el contingut de `frontend/src/views/ProjectDetailView.vue`:

```vue
<template>
  <div class="project-detail-layout">
    <!-- NAV -->
    <div class="pd-navbar">
      <span class="pd-logo">🐟 MiroFish</span>
      <button class="pd-back-btn" @click="router.push({ name: 'Home' })">
        ← {{ t('projectDetail.backToHome') }}
      </button>
      <div class="pd-nav-right">
        <LanguageSwitcher />
      </div>
    </div>

    <div class="pd-body" v-if="detail">
      <!-- COLUMNA ESQUERRA -->
      <aside class="pd-sidebar">
        <!-- Nom projecte -->
        <div class="pd-card">
          <div class="pd-card-label">{{ t('projectDetail.project') }}</div>
          <div class="pd-project-name">{{ detail.project.name }}</div>
          <div class="pd-meta">{{ formatDate(detail.project.created_at) }}</div>
        </div>

        <!-- Pregunta simulació -->
        <div class="pd-card" v-if="detail.project.simulation_requirement">
          <div class="pd-card-label">{{ t('projectDetail.simulationQuestion') }}</div>
          <div class="pd-question">{{ detail.project.simulation_requirement }}</div>
        </div>

        <!-- Fitxer inicial -->
        <div class="pd-card" v-if="detail.files.length">
          <div class="pd-card-label">{{ t('projectDetail.sourceFile') }}</div>
          <div class="pd-file-row" v-for="file in detail.files" :key="file.id">
            <span class="pd-filename">📄 {{ file.original_name }}</span>
            <button class="pd-btn-sm" @click="handleDownloadSource(file)">↓</button>
          </div>
        </div>

        <!-- Ontologia -->
        <div class="pd-card">
          <div class="pd-card-label">{{ t('projectDetail.ontology') }}</div>
          <div v-if="detail.ontology" class="pd-file-row">
            <span class="pd-filename">📋 ontology_v{{ detail.ontology.version }}.json</span>
            <button class="pd-btn-sm" @click="handleDownloadOntology">↓</button>
          </div>
          <div v-else class="pd-empty">{{ t('projectDetail.noOntology') }}</div>
          <label class="pd-btn pd-btn-upload">
            ⬆ {{ t('projectDetail.uploadNewOntology') }}
            <input type="file" accept=".json" style="display:none" @change="handleUploadOntology" />
          </label>
        </div>

        <!-- Graph base -->
        <div class="pd-card">
          <div class="pd-card-header">
            <div class="pd-card-label">{{ t('projectDetail.graphBase') }}</div>
            <span v-if="detail.graph" :class="['pd-badge', `pd-badge--${detail.graph.status}`]">
              {{ t(`projectDetail.graphStatus.${detail.graph.status}`) }}
            </span>
          </div>
          <template v-if="detail.graph">
            <div class="pd-meta">
              ID: {{ detail.graph.id.slice(0, 8) }}… · {{ detail.graph.node_count ?? '?' }} {{ t('projectDetail.entities') }}
            </div>
            <div class="pd-graph-actions">
              <button class="pd-btn" @click="handleViewGraph">👁 {{ t('projectDetail.viewGraph') }}</button>
              <button
                v-if="detail.graph.status === 'ready'"
                class="pd-btn pd-btn-danger"
                @click="handleForceRebuild"
              >↺ {{ t('projectDetail.forceRebuild') }}</button>
              <button
                v-if="detail.graph.status === 'failed'"
                class="pd-btn"
                @click="handleForceRebuild"
              >↺ {{ t('projectDetail.retry') }}</button>
            </div>
            <div v-if="detail.graph.status === 'building'" class="pd-progress">
              ⟳ {{ t('projectDetail.graphBuilding') }}
            </div>
          </template>
          <div v-else class="pd-empty">{{ t('projectDetail.noGraph') }}</div>
        </div>

        <!-- Mini-preview graph -->
        <div class="pd-graph-preview" v-if="detail.graph && detail.graph.status === 'ready'">
          <GraphPanel
            :graphId="detail.graph.id"
            :compact="true"
          />
        </div>
      </aside>

      <!-- COLUMNA DRETA (task 7) -->
      <main class="pd-main">
        <div class="pd-simulations-placeholder">
          <!-- implementat a Task 7 -->
        </div>
      </main>
    </div>

    <!-- Loading -->
    <div v-else-if="loading" class="pd-loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="pd-error">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'
import GraphPanel from '@/components/GraphPanel.vue'
import {
  getProjectDetail,
  downloadProjectSource,
  downloadProjectOntology,
  uploadOntology,
  forceRebuildGraph,
} from '@/api/project.js'

const props = defineProps({ projectId: String })
const router = useRouter()
const { t } = useI18n()

const detail = ref(null)
const loading = ref(true)
const error = ref(null)

async function loadDetail() {
  loading.value = true
  error.value = null
  try {
    detail.value = await getProjectDetail(props.projectId)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString()
}

async function handleDownloadSource(file) {
  await downloadProjectSource(props.projectId, file.original_name)
}

async function handleDownloadOntology() {
  await downloadProjectOntology(props.projectId, detail.value.ontology?.version)
}

async function handleUploadOntology(event) {
  const file = event.target.files[0]
  if (!file) return
  await uploadOntology(props.projectId, file)
  await loadDetail()
}

function handleViewGraph() {
  // Obre el graph en modal (a implementar amb el component existent)
  router.push({ name: 'Process', params: { projectId: props.projectId }, query: { step: '1', view: 'graph' } })
}

async function handleForceRebuild() {
  if (!confirm(t('projectDetail.confirmForceRebuild'))) return
  await forceRebuildGraph(props.projectId)
  await loadDetail()
}

onMounted(loadDetail)
</script>

<style scoped>
.project-detail-layout { display: flex; flex-direction: column; height: 100vh; background: #0f0f1e; color: #e0e0ff; font-family: 'JetBrains Mono', monospace; }
.pd-navbar { display: flex; align-items: center; justify-content: space-between; padding: 0.5rem 1rem; background: #1a1a2e; border-bottom: 1px solid #2a2a4a; flex-shrink: 0; }
.pd-logo { font-weight: bold; }
.pd-back-btn { background: transparent; border: none; color: #8080c0; cursor: pointer; font-size: 0.85rem; }
.pd-back-btn:hover { color: #c0c0ff; }
.pd-nav-right { display: flex; align-items: center; gap: 0.75rem; }
.pd-body { display: flex; flex: 1; overflow: hidden; }
.pd-sidebar { width: 340px; min-width: 280px; border-right: 1px solid #2a2a4a; overflow-y: auto; padding: 1rem; display: flex; flex-direction: column; gap: 0.75rem; }
.pd-main { flex: 1; overflow-y: auto; padding: 1rem; }
.pd-card { background: #1e1e30; border: 1px solid #2a2a4a; border-radius: 6px; padding: 0.75rem; }
.pd-card-label { font-size: 0.68rem; text-transform: uppercase; opacity: 0.5; margin-bottom: 0.35rem; letter-spacing: 0.05em; }
.pd-card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem; }
.pd-project-name { font-size: 1.05rem; font-weight: bold; }
.pd-question { font-size: 0.82rem; color: #b0b0d0; font-style: italic; }
.pd-meta { font-size: 0.72rem; opacity: 0.45; margin-top: 0.2rem; }
.pd-file-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem; }
.pd-filename { font-size: 0.8rem; color: #80c0ff; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 220px; }
.pd-empty { font-size: 0.75rem; opacity: 0.4; font-style: italic; margin-bottom: 0.35rem; }
.pd-btn { background: #1e2e3e; border: 1px solid #3a5a7a; color: #80c0ff; border-radius: 4px; padding: 0.3rem 0.7rem; cursor: pointer; font-size: 0.78rem; font-family: inherit; margin-top: 0.35rem; }
.pd-btn:hover { background: #2a3e50; }
.pd-btn-sm { background: #1e2e3e; border: 1px solid #3a5a7a; color: #80c0ff; border-radius: 4px; padding: 0.15rem 0.4rem; cursor: pointer; font-size: 0.75rem; font-family: inherit; }
.pd-btn-upload { display: block; width: 100%; text-align: center; box-sizing: border-box; cursor: pointer; }
.pd-btn-danger { background: #2a1a1a; border-color: #7a3a3a; color: #ff8080; }
.pd-btn-danger:hover { background: #3a1a1a; }
.pd-graph-actions { display: flex; gap: 0.4rem; flex-wrap: wrap; margin-top: 0.4rem; }
.pd-progress { font-size: 0.75rem; color: #ffd080; margin-top: 0.4rem; }
.pd-badge { font-size: 0.68rem; padding: 0.1rem 0.4rem; border-radius: 10px; }
.pd-badge--ready { background: #1a3a1a; color: #80ff80; }
.pd-badge--building { background: #3a3a00; color: #ffd080; }
.pd-badge--failed { background: #3a1a1a; color: #ff8080; }
.pd-graph-preview { flex: 1; min-height: 150px; border: 1px solid #2a2a4a; border-radius: 6px; overflow: hidden; }
.pd-loading, .pd-error { padding: 2rem; text-align: center; opacity: 0.6; }
</style>
```

- [ ] **Step 4: Afegir claus i18n a locales**

Afegir a `locales/ca.json` (i equivalent en `en.json` i `es.json`):

```json
"projectDetail": {
  "backToHome": "Tornar als meus projectes",
  "project": "Projecte",
  "simulationQuestion": "Pregunta de simulació",
  "sourceFile": "Fitxer inicial",
  "ontology": "Ontologia",
  "noOntology": "Sense ontologia",
  "uploadNewOntology": "Pujar nova ontologia",
  "graphBase": "Graph base",
  "entities": "entitats",
  "viewGraph": "Veure graph",
  "forceRebuild": "Forçar regeneració",
  "retry": "Reintentar",
  "graphBuilding": "Construint...",
  "noGraph": "Sense graph generat",
  "confirmForceRebuild": "Esborrarà el graph actual i el reconstruirà des de zero. Continuar?",
  "graphStatus": {
    "ready": "Completat",
    "building": "En curs",
    "failed": "Error"
  },
  "simulations": "Simulacions",
  "newSimulation": "Nova simulació",
  "simulation": "Simulació",
  "platform": "Plataforma",
  "rounds": "rondes",
  "graphUsed": "Graph",
  "adjust": "Ajustar",
  "regenerateReport": "Re-generar informe",
  "interaction": "Interacció",
  "downloadMd": "↓ MD",
  "downloadPdf": "↓ PDF",
  "downloadLog": "↓ Log",
  "delete": "Esborrar",
  "confirmDelete": "Esborrar aquesta simulació? Aquesta acció no es pot desfer.",
  "statusCompleted": "Completada",
  "statusRunning": "En curs",
  "statusFailed": "Fallida",
  "statusPrepared": "Preparada",
  "statusError": "Error"
}
```

- [ ] **Step 5: Verificar al navegador**

```bash
npm run dev
```

Obrir un projecte des de Home → columna esquerra ha de mostrar info del projecte, fitxers, ontologia i graph base.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/ProjectDetailView.vue locales/
git commit -m "feat(project-detail): columna esquerra amb info projecte i graph base"
```

---

## Task 7: ProjectDetailView — Columna dreta (simulacions)

**Files:**
- Modify: `frontend/src/views/ProjectDetailView.vue`

- [ ] **Step 1: Implementar la columna dreta amb targetes de simulació**

Substituir el bloc `<main class="pd-main">` de `ProjectDetailView.vue` pel contingut complet:

```vue
<!-- COLUMNA DRETA -->
<main class="pd-main">
  <div class="pd-sim-header">
    <h2 class="pd-sim-title">
      {{ t('projectDetail.simulations') }}
      <span class="pd-sim-count">({{ detail.simulations.length }})</span>
    </h2>
    <button class="pd-btn pd-btn-primary" @click="handleNewSimulation">
      + {{ t('projectDetail.newSimulation') }}
    </button>
  </div>

  <div v-if="detail.simulations.length === 0" class="pd-sim-empty">
    {{ t('projectDetail.noSimulations') }}
  </div>

  <div
    v-for="sim in detail.simulations"
    :key="sim.id"
    :class="['pd-sim-card', `pd-sim-card--${sim.status}`]"
  >
    <div class="pd-sim-card-header">
      <div>
        <div class="pd-sim-card-title">
          {{ t('projectDetail.simulation') }} #{{ sim.ordinal }}
          <span :class="['pd-badge', statusBadgeClass(sim.status)]">
            {{ t(`projectDetail.status${capitalize(sim.status)}`) }}
          </span>
        </div>
        <div class="pd-sim-card-meta">
          {{ formatDate(sim.created_at) }} ·
          {{ sim.platform }} ·
          {{ sim.rounds_completed }}/{{ sim.rounds_total ?? '?' }} {{ t('projectDetail.rounds') }} ·
          Graph: {{ sim.graph_id ? sim.graph_id.slice(0, 8) + '…' : '—' }}
        </div>
      </div>
    </div>

    <div class="pd-sim-card-actions">
      <!-- Completada -->
      <template v-if="sim.status === 'completed' || sim.status === 'profiles_ready' || sim.status === 'config_ready'">
        <button class="pd-btn-sm" @click="handleAdjust(sim)">✏️ {{ t('projectDetail.adjust') }}</button>
        <button class="pd-btn-sm" @click="handleRegenerateReport(sim)">↺ {{ t('projectDetail.regenerateReport') }}</button>
        <button v-if="sim.report_id" class="pd-btn-sm pd-btn-interaction" @click="handleInteraction(sim)">
          💬 {{ t('projectDetail.interaction') }}
        </button>
        <button v-if="sim.report_id" class="pd-btn-sm" @click="handleDownloadMd(sim)">{{ t('projectDetail.downloadMd') }}</button>
        <button v-if="sim.report_id" class="pd-btn-sm" @click="handleDownloadPdf(sim)">{{ t('projectDetail.downloadPdf') }}</button>
        <button class="pd-btn-sm" @click="handleDownloadLog(sim)">{{ t('projectDetail.downloadLog') }}</button>
      </template>

      <!-- En curs / running -->
      <template v-else-if="sim.status === 'running'">
        <span class="pd-running-indicator">⟳ {{ sim.rounds_completed }}/{{ sim.rounds_total }}</span>
      </template>

      <!-- Fallida / error -->
      <template v-else-if="sim.status === 'error' || sim.status === 'failed'">
        <button class="pd-btn-sm" @click="handleAdjust(sim)">✏️ {{ t('projectDetail.adjust') }}</button>
      </template>

      <!-- Preparada -->
      <template v-else-if="sim.status === 'prepared'">
        <button class="pd-btn-sm" @click="handleAdjust(sim)">✏️ {{ t('projectDetail.adjust') }}</button>
      </template>

      <button class="pd-btn-sm pd-btn-danger" @click="handleDeleteSimulation(sim)">
        🗑 {{ t('projectDetail.delete') }}
      </button>
    </div>
  </div>
</main>
```

- [ ] **Step 2: Afegir les funcions de navegació i accions al `<script setup>`**

Afegir les importacions i funcions que falten al bloc `<script setup>` de `ProjectDetailView.vue`:

```js
import {
  getProjectDetail,
  downloadProjectSource,
  downloadProjectOntology,
  uploadOntology,
  forceRebuildGraph,
  deleteSimulation,
  downloadReportMd,
  downloadReportPdf,
  downloadSimulationLog,
  generateReport,
} from '@/api/project.js'

// Funcions de navegació
function handleNewSimulation() {
  router.push({
    name: 'Process',
    params: { projectId: props.projectId },
    query: { step: '2' },
    state: { backTo: `/project/${props.projectId}` },
  })
}

function handleAdjust(sim) {
  router.push({
    name: 'Process',
    params: { projectId: props.projectId },
    query: { mode: 'adjust', simulationId: sim.id },
    state: { backTo: `/project/${props.projectId}` },
  })
}

function handleRegenerateReport(sim) {
  // Navega a ReportView passant simulationId — ReportView ja gestiona generar o re-generar
  router.push({
    name: 'Report',
    params: { reportId: sim.report_id || sim.id },
    query: { simulationId: sim.id },
    state: { backTo: `/project/${props.projectId}` },
  })
}

function handleInteraction(sim) {
  router.push({
    name: 'Interaction',
    params: { reportId: sim.report_id },
    state: { backTo: `/project/${props.projectId}` },
  })
}

async function handleDeleteSimulation(sim) {
  if (!confirm(t('projectDetail.confirmDelete'))) return
  await deleteSimulation(sim.id)
  await loadDetail()
}

async function handleDownloadMd(sim) {
  await downloadReportMd(sim.report_id)
}

async function handleDownloadPdf(sim) {
  await downloadReportPdf(sim.report_id)
}

async function handleDownloadLog(sim) {
  await downloadSimulationLog(sim.id)
}

// Helpers de presentació
function statusBadgeClass(status) {
  const map = {
    completed: 'pd-badge--ready',
    profiles_ready: 'pd-badge--ready',
    config_ready: 'pd-badge--ready',
    running: 'pd-badge--building',
    error: 'pd-badge--failed',
    failed: 'pd-badge--failed',
    prepared: 'pd-badge--prepared',
  }
  return map[status] || ''
}

function capitalize(str) {
  return str ? str.charAt(0).toUpperCase() + str.slice(1) : ''
}
```

- [ ] **Step 3: Afegir CSS per a la columna dreta**

Afegir al bloc `<style scoped>`:

```css
.pd-sim-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; }
.pd-sim-title { margin: 0; font-size: 1rem; color: #e0e0ff; }
.pd-sim-count { opacity: 0.4; font-weight: normal; font-size: 0.85rem; }
.pd-btn-primary { background: #1a3a6a; border-color: #4080c0; color: #80c0ff; }
.pd-btn-primary:hover { background: #2a4a7a; }
.pd-sim-empty { color: #6060a0; font-size: 0.85rem; text-align: center; padding: 2rem; }
.pd-sim-card { border: 1px solid #2a2a4a; border-radius: 8px; padding: 0.9rem; margin-bottom: 0.75rem; background: #111120; }
.pd-sim-card--completed, .pd-sim-card--profiles_ready, .pd-sim-card--config_ready { border-color: #2a5a2a; background: #0f1a0f; }
.pd-sim-card--running { border-color: #5a4a00; background: #1a1500; }
.pd-sim-card--error, .pd-sim-card--failed { border-color: #5a1a1a; background: #1a0f0f; }
.pd-sim-card-header { margin-bottom: 0.6rem; }
.pd-sim-card-title { font-size: 0.88rem; font-weight: bold; display: flex; align-items: center; gap: 0.5rem; }
.pd-sim-card-meta { font-size: 0.72rem; opacity: 0.45; margin-top: 0.2rem; }
.pd-sim-card-actions { display: flex; gap: 0.35rem; flex-wrap: wrap; align-items: center; }
.pd-badge--prepared { background: #2a2a4a; color: #a0a0ff; }
.pd-btn-interaction { color: #ff80ff; border-color: #7a3a7a; }
.pd-running-indicator { font-size: 0.75rem; color: #ffd080; }
```

- [ ] **Step 4: Afegir claus i18n que falten**

Afegir a `locales/ca.json` dins `projectDetail`:

```json
"noSimulations": "Sense simulacions. Crea'n una nova per començar.",
"rounds": "rondes",
"statusCompleted": "Completada",
"statusProfiles_ready": "Perfils llestos",
"statusConfig_ready": "Config llesta",
"statusRunning": "En curs",
"statusError": "Error",
"statusFailed": "Fallida",
"statusPrepared": "Preparada"
```

- [ ] **Step 5: Verificar al navegador**

```bash
npm run dev
```

Obrir ProjectDetailView → columna dreta mostra simulacions amb targetes, badges de color i botons correctes per cada estat.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/ProjectDetailView.vue locales/
git commit -m "feat(project-detail): columna dreta amb targetes de simulació i accions"
```

---

## Task 8: Navegació backTo a SimulationRunView, ReportView i InteractionView

**Files:**
- Modify: `frontend/src/views/SimulationRunView.vue`
- Modify: `frontend/src/views/ReportView.vue`
- Modify: `frontend/src/views/InteractionView.vue`
- Modify: `frontend/src/components/Step4Report.vue`
- Modify: `frontend/src/components/Step5Interaction.vue`

- [ ] **Step 1: Examinar com Step4Report i Step5Interaction gestionen la navegació**

```bash
grep -n "router\|push\|back\|Home\|emit" frontend/src/components/Step4Report.vue | head -30
grep -n "router\|push\|back\|Home\|emit" frontend/src/components/Step5Interaction.vue | head -30
```

- [ ] **Step 2: Examinar SimulationRunView per trobar tots els punts de navigació**

```bash
grep -n "router\.push\|router\.replace\|name.*Home\|name.*Simulation" frontend/src/views/SimulationRunView.vue
```

- [ ] **Step 3: Crear un composable useBackTo**

Crear `frontend/src/composables/useBackTo.js`:

```js
import { useRouter } from 'vue-router'

export function useBackTo(defaultRouteName = 'Home') {
  const router = useRouter()

  function navigateBack(defaultParams = {}) {
    const backTo = history.state?.backTo
    if (backTo) {
      router.push(backTo)
    } else {
      router.push({ name: defaultRouteName, ...defaultParams })
    }
  }

  function pushWithBackTo(route) {
    const backTo = history.state?.backTo
    router.push({
      ...route,
      state: { ...route.state, backTo: backTo || undefined },
    })
  }

  return { navigateBack, pushWithBackTo }
}
```

- [ ] **Step 4: Modificar SimulationRunView per usar useBackTo**

Localitzar a `SimulationRunView.vue` la línia on `handleGoBack` fa `router.push({ name: 'Simulation', ... })` i afegir al final (o substituir) la navegació de retorn al finalitzar la simulació:

```js
import { useBackTo } from '@/composables/useBackTo.js'
const { navigateBack } = useBackTo('Home')

// On ara hi ha router.push({ name: 'Home' }) o similar al finalitzar:
// Substituir per:
navigateBack()
```

- [ ] **Step 5: Examinar i modificar Step4Report**

```bash
grep -n "router\|push\|Home\|back\|emit" frontend/src/components/Step4Report.vue
```

Localitzar on navega al finalitzar l'informe. Substituir `router.push({ name: 'Home' })` (o equivalent) per:

```js
import { useBackTo } from '@/composables/useBackTo.js'
const { navigateBack } = useBackTo('Home')

// Al finalitzar l'informe:
navigateBack()
```

- [ ] **Step 6: Examinar i modificar Step5Interaction**

```bash
grep -n "router\|push\|Home\|back\|emit" frontend/src/components/Step5Interaction.vue
```

Aplicar el mateix patró que Step4Report:

```js
import { useBackTo } from '@/composables/useBackTo.js'
const { navigateBack } = useBackTo('Home')
// On ara navega a Home: substituir per navigateBack()
```

- [ ] **Step 7: Verificar al navegador**

Flux complet: Home → ProjectDetail → Nova simulació → SimulationRun → (acabar) → ha de tornar a ProjectDetail. Flux de nou projecte: Home → Nou projecte → Process → SimulationRun → (acabar) → ha d'anar a Home.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/composables/useBackTo.js frontend/src/views/SimulationRunView.vue frontend/src/views/ReportView.vue frontend/src/views/InteractionView.vue frontend/src/components/Step4Report.vue frontend/src/components/Step5Interaction.vue
git commit -m "feat(navigation): composable useBackTo per retorn a ProjectDetail"
```

---

## Task 9: Process.vue — Mode adjust (carregar dades + UI read-only)

**Files:**
- Modify: `frontend/src/views/Process.vue`
- Modify: `frontend/src/components/Step2EnvSetup.vue`
- Modify: `frontend/src/components/Step3Simulation.vue`

- [ ] **Step 1: Examinar com Process.vue rep i usa projectId i el step inicial**

```bash
sed -n '90,130p' frontend/src/views/Process.vue
grep -n "currentStep\|route\.query\|route\.params\|step" frontend/src/views/Process.vue | head -30
```

- [ ] **Step 2: Examinar l'inici de Step2EnvSetup per entendre props i events**

```bash
sed -n '1,60p' frontend/src/components/Step2EnvSetup.vue
grep -n "defineProps\|defineEmits\|agents\|profiles" frontend/src/components/Step2EnvSetup.vue | head -30
```

- [ ] **Step 3: Examinar l'inici de Step3Simulation per entendre props i events**

```bash
sed -n '1,60p' frontend/src/components/Step3Simulation.vue
grep -n "defineProps\|defineEmits\|config\|params" frontend/src/components/Step3Simulation.vue | head -30
```

- [ ] **Step 4: Afegir suport a query params mode i simulationId a Process.vue**

Al bloc `<script setup>` de `Process.vue`, afegir lectura dels query params i càrrega de dades:

```js
import { getSimulationDetail } from '@/api/project.js' // afegir a api/project.js si cal
// Ja existents:
// const route = useRoute()
// const currentStep = ref(1)

const isAdjustMode = computed(() => route.query.mode === 'adjust')
const adjustSimulationId = computed(() => route.query.simulationId)
const adjustData = ref(null) // { simulation, profiles, config }

// Modificar onMounted o l'init existent per carregar dades en mode adjust:
onMounted(async () => {
  // ... codi existent ...
  if (isAdjustMode.value && adjustSimulationId.value) {
    adjustData.value = await getSimulationDetail(adjustSimulationId.value)
    currentStep.value = 2 // Entrar directament al step 2
  } else if (route.query.step) {
    currentStep.value = parseInt(route.query.step) || 1
  }
})
```

Afegir `getSimulationDetail` a `frontend/src/api/project.js`:

```js
export async function getSimulationDetail(simulationId) {
  const res = await service.get(`/api/simulation/${simulationId}/detail`)
  return res.data
}
```

- [ ] **Step 5: Passar adjustData i isAdjustMode als components Step2 i Step3**

Al template de `Process.vue`, modificar les línies que renderitzen Step2 i Step3:

```vue
<Step2EnvSetup
  v-else-if="currentStep === 2"
  :projectId="currentProjectId"
  :adjustMode="isAdjustMode"
  :adjustProfiles="adjustData?.profiles"
  @go-back="handleGoBack"
  @next-step="handleNextStep"
/>
<Step3Simulation
  v-else-if="currentStep === 3"
  :projectId="currentProjectId"
  :adjustMode="isAdjustMode"
  :adjustConfig="adjustData?.config"
  @go-back="handleGoBack"
  @next-step="handleNextStep"
/>
```

- [ ] **Step 6: Afegir prop adjustMode a Step2EnvSetup i mostrar banner read-only**

A `Step2EnvSetup.vue`, afegir les props:

```js
const props = defineProps({
  // ... props existents ...
  adjustMode: { type: Boolean, default: false },
  adjustProfiles: { type: Array, default: null },
})
```

Afegir al template, just a l'inici del contingut del step, el banner read-only:

```vue
<div v-if="props.adjustMode && !editingSection" class="adjust-banner">
  📋 Mode consulta —
  <button class="adjust-edit-btn" @click="editingSection = true">
    ✏️ {{ t('adjust.editSection') }}
  </button>
</div>
```

Afegir al `<script setup>`:

```js
const editingSection = ref(false)

// Quan es carreguen les dades en mode adjust, pre-emplenar els agents:
watch(() => props.adjustProfiles, (profiles) => {
  if (profiles && props.adjustMode) {
    // Pre-emplenar la llista d'agents amb les dades de la simulació existent
    // (la variable concreta depèn de l'estructura interna de Step2EnvSetup)
    agentProfiles.value = profiles // Ajustar al nom de variable real
  }
}, { immediate: true })
```

- [ ] **Step 7: Afegir prop adjustMode a Step3Simulation i mostrar banner read-only**

Aplicar el mateix patró que Step 6 però a `Step3Simulation.vue`:

```js
const props = defineProps({
  // ... props existents ...
  adjustMode: { type: Boolean, default: false },
  adjustConfig: { type: Object, default: null },
})
const editingSection = ref(false)

watch(() => props.adjustConfig, (config) => {
  if (config && props.adjustMode) {
    // Pre-emplenar la config amb les dades existents
    // Ajustar als noms de variables reals del component
  }
}, { immediate: true })
```

- [ ] **Step 8: Modificar el botó principal de llançament en mode adjust**

A `Step3Simulation.vue`, localitzar el botó "Generar" o "Iniciar simulació" i adaptar:

```vue
<button @click="handleLaunch" class="launch-btn">
  {{ isAdjustMode ? t('adjust.launchSimulation') : t('step3.startSimulation') }}
</button>
```

- [ ] **Step 9: Afegir claus i18n**

```json
"adjust": {
  "editSection": "Editar aquesta secció",
  "launchSimulation": "▶ Llançar simulació",
  "readOnlyMode": "Mode consulta"
}
```

- [ ] **Step 10: Verificar al navegador**

Flux: ProjectDetail → Ajustar (sim completada) → Process Step 2 mostra agents de la simulació en read-only amb banner. Clicar "Editar" activa l'edició.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/views/Process.vue frontend/src/components/Step2EnvSetup.vue frontend/src/components/Step3Simulation.vue frontend/src/api/project.js locales/
git commit -m "feat(adjust-mode): Process.vue mode adjust amb dades pre-carregades i read-only"
```

---

## Task 10: Process.vue — Regles de consistència (mode adjust)

**Files:**
- Modify: `frontend/src/components/Step2EnvSetup.vue`
- Modify: `frontend/src/components/Step3Simulation.vue`

- [ ] **Step 1: Examinar com Step2 i Step3 es comuniquen via events**

```bash
grep -n "emit\|@next-step\|profiles\|config" frontend/src/components/Step2EnvSetup.vue | head -20
grep -n "emit\|@next-step\|profiles\|config" frontend/src/components/Step3Simulation.vue | head -20
```

- [ ] **Step 2: Afegir un store reactiu local de consistència entre Step2 i Step3**

A `Process.vue`, afegir un ref compartit que es passa als dos steps:

```js
const simulationAgents = ref([]) // Llista d'agents actualitzada en temps real

// handleNextStep ja porta dades del step 2 al step 3:
const handleNextStep = (params = {}) => {
  if (currentStep.value === 2 && params.profiles) {
    simulationAgents.value = params.profiles
  }
  // ... codi existent ...
}
```

Passar als components:

```vue
<Step3Simulation
  ...
  :agents="simulationAgents"
/>
```

- [ ] **Step 3: Implementar la regla "eliminar agent → eliminar de config"**

A `Step2EnvSetup.vue`, quan s'elimina un agent en mode adjust, emetre l'event amb el canvi:

```js
function removeAgent(agentId) {
  agentProfiles.value = agentProfiles.value.filter(a => a.id !== agentId || a.user_id !== agentId)
  emit('agent-removed', agentId)
}
```

A `Step3Simulation.vue`, escoltar el canvi via prop `agents` i eliminar l'entrada corresponent de la config:

```js
watch(() => props.agents, (newAgents) => {
  if (!props.adjustMode) return
  // Eliminar de la config els agents que ja no existeixen
  const agentIds = new Set(newAgents.map(a => a.user_id ?? a.id))
  // Ajustar als camps reals de la config de simulació
  if (simConfig.value?.agent_configs) {
    simConfig.value.agent_configs = simConfig.value.agent_configs.filter(
      ac => agentIds.has(ac.user_id ?? ac.agent_id)
    )
  }
}, { deep: true })
```

- [ ] **Step 4: Implementar la regla "canviar plataforma d'agent → actualitzar config"**

A `Step2EnvSetup.vue`, quan es canvia la plataforma d'un agent:

```js
function updateAgentPlatform(agentId, newPlatform) {
  const agent = agentProfiles.value.find(a => (a.user_id ?? a.id) === agentId)
  if (agent) agent.platform = newPlatform
  emit('agent-platform-changed', { agentId, platform: newPlatform })
}
```

A `Step3Simulation.vue`, escoltar i actualitzar la config:

```js
// Via watch de props.agents — la plataforma ja ve actualitzada dins l'objecte agent
// Sincronitzar la plataforma a la config:
watch(() => props.agents, (newAgents) => {
  if (!props.adjustMode || !simConfig.value?.agent_configs) return
  newAgents.forEach(agent => {
    const configEntry = simConfig.value.agent_configs.find(
      ac => (ac.user_id ?? ac.agent_id) === (agent.user_id ?? agent.id)
    )
    if (configEntry) configEntry.platform = agent.platform
  })
}, { deep: true })
```

- [ ] **Step 5: Mostrar avisos inline quan hi ha canvis de consistència**

A `Step3Simulation.vue`, afegir un ref per als avisos:

```js
const consistencyWarnings = ref([])

// Actualitzar els avisos quan canvien els agents:
watch(() => props.agents, (newAgents) => {
  consistencyWarnings.value = []
  if (!props.adjustMode) return
  const agentIds = new Set(newAgents.map(a => a.user_id ?? a.id))
  const removedCount = (simConfig.value?.agent_configs || []).filter(
    ac => !agentIds.has(ac.user_id ?? ac.agent_id)
  ).length
  if (removedCount > 0) {
    consistencyWarnings.value.push(t('adjust.agentsRemovedWarning', { count: removedCount }))
  }
}, { deep: true })
```

Afegir al template de `Step3Simulation.vue`:

```vue
<div v-if="consistencyWarnings.length" class="consistency-warnings">
  <div v-for="(w, i) in consistencyWarnings" :key="i" class="consistency-warning">
    ⚠️ {{ w }}
  </div>
</div>
```

- [ ] **Step 6: Afegir claus i18n**

```json
"adjust": {
  "agentsRemovedWarning": "S'han eliminat {count} agent(s) de la configuració de simulació."
}
```

- [ ] **Step 7: Verificar al navegador**

Flux: Ajustar simulació → Step 2 → eliminar un agent → anar a Step 3 → l'entrada d'aquell agent ha desaparegut de la config. L'avís és visible.

- [ ] **Step 8: Commit final de la feature**

```bash
git add frontend/src/views/Process.vue frontend/src/components/Step2EnvSetup.vue frontend/src/components/Step3Simulation.vue locales/
git commit -m "feat(adjust-mode): regles de consistència agents↔config en mode adjust"
```
