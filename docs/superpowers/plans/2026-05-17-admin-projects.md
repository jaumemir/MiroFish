# Admin Projects Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Afegir una pestanya "Projectes" al panell d'administració que llisti tots els projectes del sistema amb propietari i simulacions, permeti veure'n el detall tècnic (IDs, grafs, simulacions) en un modal, i permeti eliminar simulacions individuals i projectes sencers. A més, corregir que l'admin veia tots els projectes a "Els meus projectes".

**Architecture:** Quatre nous endpoints a `backend/app/api/admin.py` (llistat, detall, eliminar projecte, eliminar simulació). Nova pestanya `projects` a `AdminView.vue` amb taula i modal de detall. El modal no es tanca en clicar fora. Confirmació inline (sense segon modal) per a totes les eliminacions. Fix del `list_projects` per filtrar per `user_id` quan l'usuari és admin.

**Tech Stack:** Flask + SQLAlchemy (backend), Vue 3 + vue-i18n (frontend), SQLite (BD per defecte)

---

## Mapa de fitxers

| Fitxer | Acció | Responsabilitat |
|---|---|---|
| `backend/app/api/admin.py` | Modificar | 4 nous endpoints d'administració de projectes |
| `backend/app/api/graph.py` | Modificar | Fix: `list_projects` filtra per `user_id` fins i tot per a admins |
| `backend/app/services/graph_builder.py` | Llegir (no modificar) | Reutilitzar `delete_graph` per a l'eliminació de grafs externs |
| `frontend/src/views/AdminView.vue` | Modificar | Nova pestanya + taula + modal de detall |
| `locales/ca.json` | Modificar | Noves claus admin |
| `locales/es.json` | Modificar | Noves claus admin |
| `locales/en.json` | Modificar | Noves claus admin |

---

## Task 1: Fix — l'admin veu els seus projectes propis a "Els meus projectes"

**Files:**
- Modify: `backend/app/api/graph.py:172-182`

El problema: `list_projects` passa `filter_user_id = None` per a admins, retornant tots els projectes. Ha de passar `user.id` per a admins igual que per a usuaris normals.

- [ ] **Step 1: Obrir `backend/app/api/graph.py` i localitzar la funció `list_projects` (línia ~172)**

- [ ] **Step 2: Substituir el filtre per user_id**

Canviar:
```python
filter_user_id = None if (user is None or user.role == 'admin') else user.id
```
Per:
```python
# None only in TESTING (user is None); both admin and regular users see only their own projects here
filter_user_id = user.id if user is not None else None
```

- [ ] **Step 3: Verificar manualment**

Arrencar el backend (`npm run backend`) i comprovar que l'admin veient `/api/graph/project/list` retorna únicament els seus projectes propis.

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/graph.py
git commit -m "fix: admin veu només els seus projectes a la vista normal"
```

---

## Task 2: Backend — endpoint GET /api/admin/projects (llistat)

**Files:**
- Modify: `backend/app/api/admin.py`

- [ ] **Step 1: Escriure el test**

Crear `tests/test_admin_projects.py`:
```python
import pytest
from backend.app import create_app

@pytest.fixture
def app():
    return create_app({'TESTING': True, 'DATABASE_URL': 'sqlite:///:memory:'})

@pytest.fixture
def client(app):
    return app.test_client()

def test_list_admin_projects_empty(client):
    res = client.get('/api/admin/projects')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['data'] == []
    assert data['total'] == 0
```

- [ ] **Step 2: Executar el test per veure que falla**

```bash
cd /home/ubuntu/dev/MiroFish && uv run pytest tests/test_admin_projects.py::test_list_admin_projects_empty -v
```
Resultat esperat: FAIL amb `404` o similar (endpoint no existeix).

- [ ] **Step 3: Afegir l'endpoint a `backend/app/api/admin.py`**

Afegir al final del fitxer, actualitzant primer l'import existent:
```python
# Actualitzar la línia d'imports dels models:
from ..models.db_models import SystemConfigModel, SimulationModel, ProjectModel, UserModel, GraphModel
```

Afegir la nova funció:
```python
@admin_bp.route('/projects', methods=['GET'])
@require_admin
def list_admin_projects():
    with get_session() as db:
        from sqlalchemy import func as sql_func
        stmt = (
            select(
                ProjectModel,
                UserModel,
                sql_func.count(SimulationModel.id).label('simulation_count'),
            )
            .outerjoin(UserModel, ProjectModel.user_id == UserModel.id)
            .outerjoin(SimulationModel, SimulationModel.project_id == ProjectModel.id)
            .group_by(ProjectModel.id, UserModel.id)
            .order_by(desc(ProjectModel.created_at))
        )
        rows = db.execute(stmt).all()
        result = []
        for proj, user, sim_count in rows:
            result.append({
                'project_id': proj.id,
                'name': proj.name,
                'status': proj.status,
                'owner_email': user.email if user else None,
                'owner_name': user.name if user else None,
                'simulation_count': sim_count,
                'created_at': proj.created_at.isoformat(),
            })
    return jsonify({'success': True, 'data': result, 'total': len(result)})
```

- [ ] **Step 4: Executar el test per veure que passa**

```bash
uv run pytest tests/test_admin_projects.py::test_list_admin_projects_empty -v
```
Resultat esperat: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/admin.py tests/test_admin_projects.py
git commit -m "feat(admin): endpoint GET /api/admin/projects"
```

---

## Task 3: Backend — endpoint GET /api/admin/projects/<project_id> (detall)

**Files:**
- Modify: `backend/app/api/admin.py`
- Modify: `tests/test_admin_projects.py`

- [ ] **Step 1: Afegir test del detall**

Afegir a `tests/test_admin_projects.py`:
```python
from backend.app.db import get_session
from backend.app.models.db_models import ProjectModel, UserModel, GraphModel, SimulationModel
from backend.app.services.auth_service import hash_password

def _seed(app):
    """Crea un usuari, projecte, graf i simulació de prova."""
    with app.app_context():
        with get_session() as db:
            u = UserModel(id='u1', email='a@b.com', name='A', role='user', status='active',
                          password_hash=hash_password('x'))
            p = ProjectModel(id='p1', name='Test', status='created', user_id='u1')
            g = GraphModel(id='g1', project_id='p1', backend='zep', status='ready')
            s = SimulationModel(id='s1', project_id='p1', graph_id='g1', status='completed',
                                platform='twitter')
            db.add_all([u, p, g, s])
            db.commit()

def test_get_admin_project_detail(app, client):
    _seed(app)
    res = client.get('/api/admin/projects/p1')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    d = data['data']
    assert d['project_id'] == 'p1'
    assert d['owner_email'] == 'a@b.com'
    assert len(d['graphs']) == 1
    assert d['graphs'][0]['graph_id'] == 'g1'
    assert len(d['simulations']) == 1
    assert d['simulations'][0]['simulation_id'] == 's1'

def test_get_admin_project_not_found(client):
    res = client.get('/api/admin/projects/nonexistent')
    assert res.status_code == 404
```

- [ ] **Step 2: Executar els tests per veure que fallen**

```bash
uv run pytest tests/test_admin_projects.py::test_get_admin_project_detail tests/test_admin_projects.py::test_get_admin_project_not_found -v
```
Resultat esperat: FAIL (endpoint no existeix).

- [ ] **Step 3: Afegir l'endpoint a `backend/app/api/admin.py`**

```python
@admin_bp.route('/projects/<project_id>', methods=['GET'])
@require_admin
def get_admin_project(project_id):
    with get_session() as db:
        proj = db.get(ProjectModel, project_id)
        if not proj:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        user = db.get(UserModel, proj.user_id) if proj.user_id else None
        graphs = db.execute(
            select(GraphModel).where(GraphModel.project_id == project_id)
            .order_by(GraphModel.created_at)
        ).scalars().all()
        simulations = db.execute(
            select(SimulationModel).where(SimulationModel.project_id == project_id)
            .order_by(SimulationModel.created_at)
        ).scalars().all()
        data = {
            'project_id': proj.id,
            'name': proj.name,
            'status': proj.status,
            'created_at': proj.created_at.isoformat(),
            'owner_email': user.email if user else None,
            'owner_name': user.name if user else None,
            'graphs': [
                {
                    'graph_id': g.id,
                    'external_id': g.external_id,
                    'backend': g.backend,
                    'status': g.status,
                    'node_count': g.node_count,
                    'edge_count': g.edge_count,
                    'created_at': g.created_at.isoformat(),
                }
                for g in graphs
            ],
            'simulations': [
                {
                    'simulation_id': s.id,
                    'graph_id': s.graph_id,
                    'status': s.status,
                    'platform': s.platform,
                    'rounds_total': s.rounds_total,
                    'rounds_completed': s.rounds_completed,
                    'created_at': s.created_at.isoformat(),
                }
                for s in simulations
            ],
        }
    return jsonify({'success': True, 'data': data})
```

- [ ] **Step 4: Executar els tests per veure que passen**

```bash
uv run pytest tests/test_admin_projects.py -v
```
Resultat esperat: tots PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/admin.py tests/test_admin_projects.py
git commit -m "feat(admin): endpoint GET /api/admin/projects/<project_id>"
```

---

## Task 4: Backend — endpoint DELETE /api/admin/projects/<project_id>

**Files:**
- Modify: `backend/app/api/admin.py`
- Modify: `tests/test_admin_projects.py`

- [ ] **Step 1: Afegir test d'eliminació de projecte**

Afegir a `tests/test_admin_projects.py`:
```python
def test_delete_admin_project(app, client):
    _seed(app)
    res = client.delete('/api/admin/projects/p1')
    assert res.status_code == 200
    assert res.get_json()['success'] is True
    # Verificar que ha desaparegut
    res2 = client.get('/api/admin/projects/p1')
    assert res2.status_code == 404

def test_delete_admin_project_not_found(client):
    res = client.delete('/api/admin/projects/ghost')
    assert res.status_code == 404
```

- [ ] **Step 2: Executar els tests per veure que fallen**

```bash
uv run pytest tests/test_admin_projects.py::test_delete_admin_project tests/test_admin_projects.py::test_delete_admin_project_not_found -v
```

- [ ] **Step 3: Afegir l'endpoint a `backend/app/api/admin.py`**

```python
@admin_bp.route('/projects/<project_id>', methods=['DELETE'])
@require_admin
def delete_admin_project(project_id):
    import logging
    logger = logging.getLogger('mirofish.admin')
    from .. import get_storage
    from ..services.graph_builder import GraphBuilderService

    storage = get_storage()
    with get_session() as db:
        from sqlalchemy.orm import selectinload
        proj = db.execute(
            select(ProjectModel)
            .where(ProjectModel.id == project_id)
            .options(selectinload(ProjectModel.graphs))
        ).scalar_one_or_none()
        if not proj:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        for graph in proj.graphs:
            if graph.external_id:
                try:
                    GraphBuilderService().delete_graph(graph.external_id)
                except Exception as exc:
                    logger.warning('delete_admin_project: delete_graph(%s) failed: %s',
                                   graph.external_id, exc)
        try:
            storage.delete_prefix(f'projects/{project_id}')
        except Exception as exc:
            logger.warning('delete_admin_project: storage.delete_prefix(%s) failed: %s',
                           project_id, exc)

        db.delete(proj)
        db.commit()

    return jsonify({'success': True})
```

- [ ] **Step 4: Executar els tests per veure que passen**

```bash
uv run pytest tests/test_admin_projects.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/admin.py tests/test_admin_projects.py
git commit -m "feat(admin): endpoint DELETE /api/admin/projects/<project_id>"
```

---

## Task 5: Backend — endpoint DELETE /api/admin/simulations/<simulation_id>

**Files:**
- Modify: `backend/app/api/admin.py`
- Modify: `tests/test_admin_projects.py`

- [ ] **Step 1: Afegir test d'eliminació de simulació**

Afegir a `tests/test_admin_projects.py`:
```python
def test_delete_admin_simulation(app, client):
    _seed(app)
    res = client.delete('/api/admin/simulations/s1')
    assert res.status_code == 200
    assert res.get_json()['success'] is True
    # El projecte continua existint
    res2 = client.get('/api/admin/projects/p1')
    assert res2.status_code == 200
    assert res2.get_json()['data']['simulations'] == []

def test_delete_admin_simulation_not_found(client):
    res = client.delete('/api/admin/simulations/ghost')
    assert res.status_code == 404
```

- [ ] **Step 2: Executar els tests per veure que fallen**

```bash
uv run pytest tests/test_admin_projects.py::test_delete_admin_simulation tests/test_admin_projects.py::test_delete_admin_simulation_not_found -v
```

- [ ] **Step 3: Afegir l'endpoint a `backend/app/api/admin.py`**

```python
@admin_bp.route('/simulations/<simulation_id>', methods=['DELETE'])
@require_admin
def delete_admin_simulation(simulation_id):
    with get_session() as db:
        sim = db.get(SimulationModel, simulation_id)
        if not sim:
            return jsonify({'success': False, 'error': 'Simulation not found'}), 404
        db.delete(sim)
        db.commit()
    return jsonify({'success': True})
```

- [ ] **Step 4: Executar tots els tests per veure que passen**

```bash
uv run pytest tests/test_admin_projects.py -v
```
Resultat esperat: tots PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/admin.py tests/test_admin_projects.py
git commit -m "feat(admin): endpoint DELETE /api/admin/simulations/<simulation_id>"
```

---

## Task 6: i18n — afegir claus de traducció als tres idiomes

**Files:**
- Modify: `locales/ca.json`
- Modify: `locales/es.json`
- Modify: `locales/en.json`

- [ ] **Step 1: Afegir claus a `locales/ca.json`**

Dins el bloc `"admin"`, afegir:
```json
"projects": "Projectes",
"projectDetail": "Detall del projecte",
"owner": "Propietari",
"simulations": "Simulacions",
"graphs": "Grafs",
"noProjects": "Cap projecte trobat.",
"deleteProject": "Eliminar projecte",
"deleteProjectConfirmLabel": "Escriu el nom del projecte per confirmar",
"deleteProjectSuccess": "Projecte eliminat.",
"deleteSimulation": "Eliminar",
"deleteSimulationConfirm": "Confirmar eliminació?",
"deleteSimulationSuccess": "Simulació eliminada.",
"confirmYes": "Sí, eliminar",
"confirmNo": "No",
"externalId": "ID extern",
"graphId": "ID graf",
"simulationId": "ID simulació",
"projectId": "ID projecte",
"nodeCount": "Nodes",
"edgeCount": "Arestes",
"detail": "Detall",
"backend": "Backend"
```

- [ ] **Step 2: Afegir claus a `locales/es.json`**

Dins el bloc `"admin"`, afegir:
```json
"projects": "Proyectos",
"projectDetail": "Detalle del proyecto",
"owner": "Propietario",
"simulations": "Simulaciones",
"graphs": "Grafos",
"noProjects": "No se han encontrado proyectos.",
"deleteProject": "Eliminar proyecto",
"deleteProjectConfirmLabel": "Escribe el nombre del proyecto para confirmar",
"deleteProjectSuccess": "Proyecto eliminado.",
"deleteSimulation": "Eliminar",
"deleteSimulationConfirm": "¿Confirmar eliminación?",
"deleteSimulationSuccess": "Simulación eliminada.",
"confirmYes": "Sí, eliminar",
"confirmNo": "No",
"externalId": "ID externo",
"graphId": "ID grafo",
"simulationId": "ID simulación",
"projectId": "ID proyecto",
"nodeCount": "Nodos",
"edgeCount": "Aristas",
"detail": "Detalle",
"backend": "Backend"
```

- [ ] **Step 3: Afegir claus a `locales/en.json`**

Dins el bloc `"admin"`, afegir:
```json
"projects": "Projects",
"projectDetail": "Project detail",
"owner": "Owner",
"simulations": "Simulations",
"graphs": "Graphs",
"noProjects": "No projects found.",
"deleteProject": "Delete project",
"deleteProjectConfirmLabel": "Type the project name to confirm",
"deleteProjectSuccess": "Project deleted.",
"deleteSimulation": "Delete",
"deleteSimulationConfirm": "Confirm deletion?",
"deleteSimulationSuccess": "Simulation deleted.",
"confirmYes": "Yes, delete",
"confirmNo": "No",
"externalId": "External ID",
"graphId": "Graph ID",
"simulationId": "Simulation ID",
"projectId": "Project ID",
"nodeCount": "Nodes",
"edgeCount": "Edges",
"detail": "Detail",
"backend": "Backend"
```

- [ ] **Step 4: Commit**

```bash
git add locales/ca.json locales/es.json locales/en.json
git commit -m "feat(i18n): afegir claus admin.projects als tres idiomes"
```

---

## Task 7: Frontend — nova pestanya Projectes + taula + lògica de dades

**Files:**
- Modify: `frontend/src/views/AdminView.vue`

Aquesta tasca afegeix la pestanya i la taula. El modal es fa a la Task 8.

- [ ] **Step 1: Afegir la pestanya al `<nav>` de tabs**

Localitzar el bloc de tabs (línia ~13). Inserir la nova pestanya entre `users` i `config`:
```html
<router-link to="/admin/projects" class="tab" :class="{ active: tab === 'projects' }">
  {{ $t('admin.projects') }}
</router-link>
```

- [ ] **Step 2: Afegir les variables reactives al `<script setup>`**

Al bloc `<script setup>`, afegir després de `const executions = ref([])`:
```js
const projects = ref([])
const projectDetail = ref(null)
const projectDetailLoading = ref(false)
const projectDetailError = ref('')
```

- [ ] **Step 3: Afegir la càrrega de dades a `loadTab`**

Afegir dins la funció `loadTab`:
```js
if (props.tab === 'projects') await loadProjects()
```

Afegir la nova funció just després de `loadExecutions`:
```js
async function loadProjects() {
  try {
    const res = await service.get('/api/admin/projects')
    projects.value = res.data?.data || []
  } catch { /* silent */ }
}
```

- [ ] **Step 4: Afegir la funció per carregar el detall d'un projecte**

```js
async function openProjectDetail(projectId) {
  projectDetail.value = null
  projectDetailError.value = ''
  projectDetailLoading.value = true
  showProjectModal.value = true
  try {
    const res = await service.get(`/api/admin/projects/${projectId}`)
    projectDetail.value = res.data?.data || null
  } catch {
    projectDetailError.value = t('common.unknownError')
  } finally {
    projectDetailLoading.value = false
  }
}
```

Afegir també la variable del modal que mancarà:
```js
const showProjectModal = ref(false)
```

- [ ] **Step 5: Afegir el bloc HTML del tab "projects"**

Inserir just abans del tab `config` (comentari `<!-- Tab: Configuració -->`):
```html
<!-- Tab: Projectes -->
<div v-if="tab === 'projects'" class="tab-content">
  <div class="tab-header">
    <h2 class="section-title">{{ $t('admin.projects') }}</h2>
  </div>
  <table class="data-table" v-if="projects.length">
    <thead>
      <tr>
        <th>{{ $t('admin.project') }}</th>
        <th>{{ $t('admin.owner') }}</th>
        <th>{{ $t('admin.simulations') }}</th>
        <th>{{ $t('admin.status') }}</th>
        <th>{{ $t('admin.created') }}</th>
        <th>{{ $t('admin.actions') }}</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="proj in projects" :key="proj.project_id">
        <td>{{ proj.name }}</td>
        <td class="mono">{{ proj.owner_email || '—' }}</td>
        <td class="mono">{{ proj.simulation_count }}</td>
        <td><span class="status-badge" :class="proj.status">{{ proj.status }}</span></td>
        <td class="mono">{{ formatDate(proj.created_at) }}</td>
        <td>
          <button class="action-btn" @click="openProjectDetail(proj.project_id)">
            {{ $t('admin.detail') }}
          </button>
        </td>
      </tr>
    </tbody>
  </table>
  <div v-else class="empty-state">{{ $t('admin.noProjects') }}</div>
</div>
```

- [ ] **Step 6: Verificar visualment**

Arrencar `npm run dev`, iniciar sessió com a admin, anar a `/admin/projects`. La taula s'ha de veure buida o amb projectes. El botó "Detall" no fa res visible encara (el modal és a la Task 8).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/AdminView.vue
git commit -m "feat(admin): pestanya Projectes amb taula de llistat"
```

---

## Task 8: Frontend — modal de detall amb eliminació inline

**Files:**
- Modify: `frontend/src/views/AdminView.vue`

- [ ] **Step 1: Afegir variables per als estats d'eliminació**

Al `<script setup>`, afegir:
```js
const simDeleteConfirm = ref(null)   // simulation_id que espera confirmació
const simDeleteSuccess = ref('')
const projectDeleteConfirmInput = ref('')
const projectDeleteSuccess = ref(false)
const projectDeleteError = ref('')
const projectDeleteLoading = ref(false)
```

- [ ] **Step 2: Afegir funció per eliminar simulació**

```js
async function deleteSimulation(simulationId) {
  try {
    await service.delete(`/api/admin/simulations/${simulationId}`)
    simDeleteConfirm.value = null
    simDeleteSuccess.value = simulationId
    setTimeout(() => { simDeleteSuccess.value = '' }, 2000)
    // Refrescar detall del projecte
    const res = await service.get(`/api/admin/projects/${projectDetail.value.project_id}`)
    projectDetail.value = res.data?.data || projectDetail.value
  } catch { /* silent */ }
}
```

- [ ] **Step 3: Afegir funció per eliminar projecte**

```js
async function deleteAdminProject() {
  if (projectDeleteConfirmInput.value !== projectDetail.value?.name) return
  projectDeleteLoading.value = true
  projectDeleteError.value = ''
  try {
    await service.delete(`/api/admin/projects/${projectDetail.value.project_id}`)
    showProjectModal.value = false
    projectDetail.value = null
    projectDeleteConfirmInput.value = ''
    projectDeleteSuccess.value = true
    setTimeout(() => { projectDeleteSuccess.value = false }, 3000)
    await loadProjects()
  } catch (e) {
    projectDeleteError.value = e.response?.data?.error || t('common.unknownError')
  } finally {
    projectDeleteLoading.value = false
  }
}
```

- [ ] **Step 4: Afegir el modal al template**

Afegir just abans del tancament de `</template>` (després del modal d'esborrat d'usuari):
```html
<!-- Modal de detall de projecte (admin) -->
<div v-if="showProjectModal" class="modal-overlay">
  <div class="modal-box project-detail-modal">
    <div class="modal-header">
      <h3 class="modal-title">{{ $t('admin.projectDetail') }}</h3>
      <button class="modal-close-btn" @click="showProjectModal = false">×</button>
    </div>

    <div v-if="projectDetailLoading" class="empty-state">{{ $t('common.loading') }}</div>
    <div v-else-if="projectDetailError" class="error-msg">{{ projectDetailError }}</div>
    <template v-else-if="projectDetail">
      <!-- Capçalera projecte -->
      <div class="detail-section">
        <div class="detail-row">
          <span class="detail-label">{{ $t('admin.projectId') }}</span>
          <span class="mono detail-value">{{ projectDetail.project_id }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">{{ $t('admin.owner') }}</span>
          <span class="mono detail-value">{{ projectDetail.owner_email || '—' }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">{{ $t('admin.status') }}</span>
          <span class="status-badge" :class="projectDetail.status">{{ projectDetail.status }}</span>
        </div>
      </div>

      <!-- Grafs -->
      <div class="detail-section">
        <h4 class="detail-section-title">{{ $t('admin.graphs') }}</h4>
        <table class="data-table" v-if="projectDetail.graphs.length">
          <thead>
            <tr>
              <th>{{ $t('admin.graphId') }}</th>
              <th>{{ $t('admin.externalId') }}</th>
              <th>{{ $t('admin.backend') }}</th>
              <th>{{ $t('admin.status') }}</th>
              <th>{{ $t('admin.nodeCount') }}</th>
              <th>{{ $t('admin.edgeCount') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="g in projectDetail.graphs" :key="g.graph_id">
              <td class="mono">{{ g.graph_id }}</td>
              <td class="mono">{{ g.external_id || '—' }}</td>
              <td class="mono">{{ g.backend }}</td>
              <td><span class="status-badge" :class="g.status">{{ g.status }}</span></td>
              <td class="mono">{{ g.node_count ?? '—' }}</td>
              <td class="mono">{{ g.edge_count ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-state-sm">—</div>
      </div>

      <!-- Simulacions -->
      <div class="detail-section">
        <h4 class="detail-section-title">{{ $t('admin.simulations') }}</h4>
        <div v-if="simDeleteSuccess" class="success-msg">{{ $t('admin.deleteSimulationSuccess') }}</div>
        <table class="data-table" v-if="projectDetail.simulations.length">
          <thead>
            <tr>
              <th>{{ $t('admin.simulationId') }}</th>
              <th>{{ $t('admin.graphId') }}</th>
              <th>{{ $t('admin.status') }}</th>
              <th>{{ $t('admin.platform') }}</th>
              <th>{{ $t('admin.rounds') }}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in projectDetail.simulations" :key="s.simulation_id">
              <td class="mono">{{ s.simulation_id }}</td>
              <td class="mono">{{ s.graph_id || '—' }}</td>
              <td><span class="status-badge" :class="s.status">{{ s.status }}</span></td>
              <td class="mono">{{ s.platform }}</td>
              <td class="mono">{{ s.rounds_completed }}/{{ s.rounds_total || '?' }}</td>
              <td>
                <template v-if="simDeleteConfirm === s.simulation_id">
                  <span class="confirm-inline">
                    {{ $t('admin.deleteSimulationConfirm') }}
                    <button class="action-btn danger" @click="deleteSimulation(s.simulation_id)">
                      {{ $t('admin.confirmYes') }}
                    </button>
                    <button class="action-btn" @click="simDeleteConfirm = null">
                      {{ $t('admin.confirmNo') }}
                    </button>
                  </span>
                </template>
                <button v-else class="action-btn danger"
                        @click="simDeleteConfirm = s.simulation_id">
                  {{ $t('admin.deleteSimulation') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-state-sm">—</div>
      </div>

      <!-- Eliminar projecte -->
      <div class="detail-section danger-zone">
        <h4 class="detail-section-title danger-title">{{ $t('admin.deleteProject') }}</h4>
        <p class="danger-hint">{{ $t('admin.deleteProjectConfirmLabel') }}: <strong>{{ projectDetail.name }}</strong></p>
        <div class="form-row">
          <input v-model="projectDeleteConfirmInput" class="field-input"
                 :placeholder="projectDetail.name" />
          <button class="start-btn danger"
                  :disabled="projectDeleteConfirmInput !== projectDetail.name || projectDeleteLoading"
                  @click="deleteAdminProject">
            {{ projectDeleteLoading ? $t('common.loading') : $t('admin.deleteProject') }}
          </button>
        </div>
        <div v-if="projectDeleteError" class="error-msg">{{ projectDeleteError }}</div>
      </div>
    </template>
  </div>
</div>

<div v-if="projectDeleteSuccess" class="toast-success">{{ $t('admin.deleteProjectSuccess') }}</div>
```

- [ ] **Step 5: Afegir estils CSS al `<style scoped>`**

Afegir al final del bloc `<style scoped>`:
```css
.project-detail-modal { max-width: 860px; width: 95%; max-height: 90vh; overflow-y: auto; gap: 0; padding: 0; }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 24px 32px 16px; border-bottom: 1px solid #e5e5e5; }
.modal-close-btn { background: none; border: none; font-size: 1.4rem; cursor: pointer; color: #666; padding: 0 4px; line-height: 1; }
.modal-close-btn:hover { color: #000; }
.detail-section { padding: 20px 32px; border-bottom: 1px solid #f0f0f0; }
.detail-section:last-child { border-bottom: none; }
.detail-section-title { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #666; margin: 0 0 12px; }
.detail-row { display: flex; gap: 16px; align-items: center; margin-bottom: 8px; }
.detail-label { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #666; min-width: 110px; }
.detail-value { font-size: 0.85rem; }
.empty-state-sm { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #bbb; padding: 8px 0; }
.danger-zone { background: #fafafa; }
.danger-title { color: #dc2626; }
.danger-hint { font-size: 0.85rem; color: #666; margin: 0 0 12px; }
.confirm-inline { display: flex; align-items: center; gap: 6px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; }
.toast-success { position: fixed; bottom: 24px; right: 24px; background: #22c55e; color: #fff; padding: 10px 20px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; z-index: 200; }
```

- [ ] **Step 6: Verificar el modal**

Arrencar `npm run dev`. Anar a `/admin/projects`, clicar "Detall" en un projecte. Verificar:
- El modal s'obre i mostra IDs, grafs i simulacions
- Clicar fora del modal **no** el tanca
- El botó × tanca el modal
- Eliminar una simulació mostra confirmació inline i refresca la llista
- Eliminar un projecte requereix escriure el nom exacte

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/AdminView.vue
git commit -m "feat(admin): modal de detall de projecte amb eliminació inline"
```

---

## Task 9: Fix — eliminar `@click.self="close"` del modal existent d'usuaris

**Files:**
- Modify: `frontend/src/views/AdminView.vue`

El modal d'esborrat d'usuari actual té `@click.self="closeDeleteModal"` a l'overlay, cosa que tanca el modal en clicar fora.

- [ ] **Step 1: Localitzar i corregir l'overlay del modal d'usuari**

A `AdminView.vue`, trobar (línia ~142):
```html
<div v-if="deleteModal.open" class="modal-overlay" @click.self="closeDeleteModal" @keydown.esc.window="closeDeleteModal">
```

Substituir per (eliminar `@click.self`, mantenir el `@keydown.esc` és opcional però acceptable):
```html
<div v-if="deleteModal.open" class="modal-overlay">
```

- [ ] **Step 2: Verificar**

Arrencar `npm run dev`. Anar a `/admin/users`, deshabilitar un usuari, obrir el modal d'esborrat. Clicar fora del modal: **no s'ha de tancar**. El botó "Cancel·lar" sí que el tanca.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/AdminView.vue
git commit -m "fix(admin): modal d'esborrat d'usuari no es tanca en clicar fora"
```
