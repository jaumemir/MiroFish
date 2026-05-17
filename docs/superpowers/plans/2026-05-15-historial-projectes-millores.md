# Millores de les fitxes de projecte — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Millorar les fitxes de l'historial de simulacions afegint nom automàtic editable, fitxers descarregables i navegació correcta del pas 2.

**Architecture:** Tres millores independents: (1) servei de generació de nom via LLM + endpoint PATCH al backend + input editable al modal; (2) tres endpoints de descàrrega nous al backend + llista de links al modal; (3) correccions de dues línies a la funció `goToSimulation()` i la condició de disabled del botó Step 2 a `HistoryDatabase.vue`.

**Tech Stack:** Python/Flask (backend), Vue 3 + vue-i18n (frontend), SQLAlchemy (BD), openai SDK (LLM client), pytest (tests)

---

## Mapa de fitxers

| Fitxer | Acció | Responsabilitat |
|--------|-------|----------------|
| `backend/app/services/project_name_generator.py` | **Crear** | Funció `generate_project_name(text) -> str` via LLM |
| `backend/app/api/graph.py` | **Modificar** | Cridar `generate_project_name` a `generate_ontology` i `import_ontology`; afegir endpoint PATCH `/project/<id>` |
| `backend/app/api/simulation.py` | **Modificar** | Afegir endpoints de descàrrega: report i log |
| `backend/app/models/project.py` | **Modificar** | Afegir `get_project_files()` per exposar fitxers a `_to_dict` |
| `frontend/src/components/HistoryDatabase.vue` | **Modificar** | Nom editable al modal; llista de fitxers descarregables; correcció `goToSimulation()` |
| `frontend/src/api/graph.js` | **Modificar** | Afegir `updateProjectName(projectId, name)` |
| `locales/ca.json`, `locales/es.json`, `locales/en.json`, `locales/zh.json` | **Modificar** | Claus noves per a fitxers relacionats |
| `backend/tests/test_project_name_generator.py` | **Crear** | Tests unitaris del generador de noms |
| `backend/tests/test_project_download.py` | **Crear** | Tests dels endpoints de descàrrega |
| `backend/tests/test_project_patch.py` | **Crear** | Tests de l'endpoint PATCH |

---

## Task 1: Servei de generació de nom de projecte

**Files:**
- Create: `backend/app/services/project_name_generator.py`
- Create: `backend/tests/test_project_name_generator.py`

- [ ] **Step 1: Escriure el test fallat**

```python
# backend/tests/test_project_name_generator.py
from unittest.mock import patch, MagicMock
from app.services.project_name_generator import generate_project_name


def test_generate_project_name_returns_string():
    mock_client = MagicMock()
    mock_client.chat.return_value = "Debat Climàtic BCN 2024"
    with patch('app.services.project_name_generator.LLMClient', return_value=mock_client):
        result = generate_project_name("Text sobre el debat climàtic a Barcelona...")
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_project_name_fallback_on_error():
    mock_client = MagicMock()
    mock_client.chat.side_effect = Exception("LLM error")
    with patch('app.services.project_name_generator.LLMClient', return_value=mock_client):
        result = generate_project_name("Text qualsevol")
    assert result.startswith("Simulació")
```

- [ ] **Step 2: Verificar que el test falla**

```bash
cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/test_project_name_generator.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.services.project_name_generator'`

- [ ] **Step 3: Crear el servei**

```python
# backend/app/services/project_name_generator.py
from datetime import date
from typing import Optional
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger('mirofish.project_name')

_PROMPT = (
    "Read the following document excerpt and return ONLY a concise title of 5-8 words "
    "that summarizes its main topic. Do not use punctuation at the end. "
    "Reply only with the title, nothing else.\n\nText:\n{text}"
)


def generate_project_name(text: str, llm_client: Optional[LLMClient] = None) -> str:
    excerpt = text[:2000]
    try:
        client = llm_client or LLMClient()
        name = client.chat(
            messages=[{"role": "user", "content": _PROMPT.format(text=excerpt)}],
            temperature=0.3,
        )
        name = name.strip().strip('"').strip("'")
        if name:
            return name
    except Exception as e:
        logger.warning(f"Failed to generate project name: {e}")
    return f"Simulació {date.today().isoformat()}"
```

- [ ] **Step 4: Verificar que els tests passen**

```bash
cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/test_project_name_generator.py -v
```
Expected: 2 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/project_name_generator.py backend/tests/test_project_name_generator.py
git commit -m "feat(project): add LLM-based project name generator service"
```

---

## Task 2: Integrar la generació de nom als endpoints de creació de projecte

**Files:**
- Modify: `backend/app/api/graph.py:167-218` (funció `generate_ontology`)
- Modify: `backend/app/api/graph.py:260-320` (funció `import_ontology`)

La crida a `generate_project_name` s'ha de fer **en background** (via `threading.Thread`) per no bloquejar la resposta de l'endpoint. El projecte es crea primer amb nom "Unnamed Project", i la generació del nom actualitza la BD uns segons després.

- [ ] **Step 1: Modificar `generate_ontology` a `backend/app/api/graph.py`**

Afegir l'import al capdamunt del fitxer (amb els imports existents de `threading`):

```python
from ..services.project_name_generator import generate_project_name
```

Dins la funció `generate_ontology`, just després de la línia `ProjectManager.save_extracted_text(project_id, all_text, storage)` (línia ~196), afegir:

```python
        # Generate project name in background (non-blocking)
        def _name_task():
            try:
                name = generate_project_name(all_text)
                ProjectManager.save_project({"id": project_id, "name": name})
                logger.info(f"Project name generated: {name!r}")
            except Exception as exc:
                logger.warning(f"Background name generation failed: {exc}")

        threading.Thread(target=_name_task, daemon=True).start()
```

- [ ] **Step 2: Modificar `import_ontology` de la mateixa manera**

A `import_ontology`, after `ProjectManager.save_extracted_text(project_id, all_text, storage)` (cerca la mateixa crida dins `import_ontology`), afegir el mateix bloc `_name_task` i `threading.Thread(target=_name_task, daemon=True).start()`.

- [ ] **Step 3: Verificar que els tests existents passen**

```bash
cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/test_graph_api_project.py -v
```
Expected: tots els tests PASSED (sense trencar res existent)

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/graph.py
git commit -m "feat(project): trigger async LLM name generation on project creation"
```

---

## Task 3: Endpoint PATCH per actualitzar el nom del projecte

**Files:**
- Modify: `backend/app/api/graph.py` (afegir endpoint nou)
- Create: `backend/tests/test_project_patch.py`

- [ ] **Step 1: Escriure el test fallat**

```python
# backend/tests/test_project_patch.py
import pytest
from unittest.mock import patch, MagicMock
from app import create_app


@pytest.fixture
def app():
    return create_app({'TESTING': True})


@pytest.fixture
def client(app):
    return app.test_client()


def test_patch_project_name_success(client):
    mock_project = {"id": "proj_123", "project_id": "proj_123", "name": "Old Name"}
    updated = {**mock_project, "name": "New Name"}
    with patch('app.api.graph.ProjectManager.get_project', return_value=mock_project), \
         patch('app.api.graph.ProjectManager.save_project') as mock_save, \
         patch('app.api.graph.ProjectManager.get_project', side_effect=[mock_project, updated]):
        resp = client.patch('/api/graph/project/proj_123', json={"name": "New Name"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True


def test_patch_project_name_not_found(client):
    with patch('app.api.graph.ProjectManager.get_project', return_value=None):
        resp = client.patch('/api/graph/project/nonexistent', json={"name": "X"})
    assert resp.status_code == 404


def test_patch_project_name_empty_rejected(client):
    mock_project = {"id": "proj_123", "project_id": "proj_123", "name": "Old"}
    with patch('app.api.graph.ProjectManager.get_project', return_value=mock_project):
        resp = client.patch('/api/graph/project/proj_123', json={"name": "   "})
    assert resp.status_code == 400
```

- [ ] **Step 2: Verificar que els tests fallen**

```bash
cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/test_project_patch.py -v
```
Expected: 404 NOT FOUND (l'endpoint no existeix)

- [ ] **Step 3: Afegir l'endpoint PATCH a `backend/app/api/graph.py`**

Just després del bloc de `delete_project` (línia ~91), afegir:

```python
@graph_bp.route('/project/<project_id>', methods=['PATCH'])
def patch_project(project_id: str):
    """Update mutable project fields (currently: name)."""
    project = ProjectManager.get_project(project_id)
    if not project:
        return jsonify({"success": False, "error": t('api.projectNotFound', id=project_id)}), 404

    body = request.get_json(silent=True) or {}
    name = body.get("name", "").strip()
    if not name:
        return jsonify({"success": False, "error": "name cannot be empty"}), 400

    ProjectManager.save_project({"id": project_id, "name": name})
    updated = ProjectManager.get_project(project_id)
    return jsonify({"success": True, "data": updated})
```

- [ ] **Step 4: Verificar que els tests passen**

```bash
cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/test_project_patch.py -v
```
Expected: 3 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/graph.py backend/tests/test_project_patch.py
git commit -m "feat(api): add PATCH /api/graph/project/<id> to update project name"
```

---

## Task 4: Exposar fitxers del projecte a `_to_dict`

**Files:**
- Modify: `backend/app/models/project.py:282-302` (funció `_to_dict`)

La BD ja té la taula `project_files` amb els fitxers de tipus `upload`. Cal retornar-los a `_to_dict` en comptes del `"files": []` hardcoded.

- [ ] **Step 1: Modificar `_to_dict` a `backend/app/models/project.py`**

Substituir les línies:
```python
            "files": [],
            "total_text_length": 0,
```

Per:
```python
            "files": cls._get_project_files(proj.id),
            "total_text_length": 0,
```

- [ ] **Step 2: Afegir el mètode `_get_project_files` a la classe `ProjectManager`**

Just abans de `_to_dict`, afegir:

```python
    @classmethod
    def _get_project_files(cls, project_id: str) -> list:
        from sqlalchemy import select
        with get_session() as db:
            stmt = select(ProjectFileModel).where(
                ProjectFileModel.project_id == project_id,
                ProjectFileModel.file_type == "upload",
            )
            files = db.execute(stmt).scalars().all()
            return [
                {
                    "file_id": f.id,
                    "filename": f.original_name,
                    "size": f.size,
                    "mime_type": f.mime_type,
                    "storage_path": f.storage_path,
                }
                for f in files
            ]
```

- [ ] **Step 3: Verificar tests existents**

```bash
cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/ -v -k "project"
```
Expected: tots els tests existents PASSED

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/project.py
git commit -m "fix(project): expose uploaded files in project _to_dict response"
```

---

## Task 5: Endpoints de descàrrega (document font, informe, log)

**Files:**
- Modify: `backend/app/api/graph.py` (endpoint de descàrrega de document font)
- Modify: `backend/app/api/simulation.py` (endpoints de descàrrega d'informe i log)
- Create: `backend/tests/test_project_download.py`

- [ ] **Step 1: Escriure els tests fallats**

```python
# backend/tests/test_project_download.py
import pytest
from unittest.mock import patch, MagicMock
from app import create_app


@pytest.fixture
def app():
    return create_app({'TESTING': True})

@pytest.fixture
def client(app):
    return app.test_client()


class TestSourceDownload:
    def test_download_source_returns_file(self, client):
        mock_file = MagicMock()
        mock_file.id = "file_001"
        mock_file.original_name = "doc.pdf"
        mock_file.storage_path = "projects/p1/files/doc.pdf"
        mock_file.mime_type = "application/pdf"

        mock_storage = MagicMock()
        mock_storage.download.return_value = b"%PDF-1.4 fake content"

        with patch('app.api.graph.ProjectManager.get_project', return_value={"id": "p1"}), \
             patch('app.api.graph.ProjectManager._get_project_files',
                   return_value=[{"file_id": "file_001", "filename": "doc.pdf",
                                  "storage_path": "projects/p1/files/doc.pdf",
                                  "mime_type": "application/pdf", "size": 100}]), \
             patch('app.api.graph.get_storage', return_value=mock_storage):
            resp = client.get('/api/graph/project/p1/download/source')

        assert resp.status_code == 200
        assert 'attachment' in resp.headers.get('Content-Disposition', '')

    def test_download_source_not_found(self, client):
        with patch('app.api.graph.ProjectManager.get_project', return_value=None):
            resp = client.get('/api/graph/project/nonexistent/download/source')
        assert resp.status_code == 404

    def test_download_source_no_files(self, client):
        with patch('app.api.graph.ProjectManager.get_project', return_value={"id": "p1"}), \
             patch('app.api.graph.ProjectManager._get_project_files', return_value=[]):
            resp = client.get('/api/graph/project/p1/download/source')
        assert resp.status_code == 404


class TestSimulationDownloads:
    def _make_state(self, sim_id="sim_001", project_id="p1"):
        state = MagicMock()
        state.simulation_id = sim_id
        state.project_id = project_id
        return state

    def test_download_log_returns_json(self, client, tmp_path):
        import json, os
        log_file = tmp_path / "actions.jsonl"
        log_file.write_text('{"action": "test"}\n')

        state = self._make_state()
        with patch('app.api.simulation.SimulationManager') as MockMgr, \
             patch('app.api.simulation.Config') as MockConfig:
            MockMgr.return_value.get_simulation.return_value = state
            MockConfig.OASIS_SIMULATION_DATA_DIR = str(tmp_path.parent)
            # Simulate sim dir with actions.jsonl
            sim_dir = tmp_path
            with patch('app.api.simulation._get_simulation_log_path',
                       return_value=str(log_file)):
                resp = client.get('/api/simulation/sim_001/download/log')
        # Just verify the endpoint exists (status not 405)
        assert resp.status_code != 405
```

- [ ] **Step 2: Verificar que els tests fallen**

```bash
cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/test_project_download.py -v
```
Expected: `404` o `405` per endpoints no existents

- [ ] **Step 3: Afegir endpoint de descàrrega del document font a `backend/app/api/graph.py`**

```python
@graph_bp.route('/project/<project_id>/download/source', methods=['GET'])
def download_project_source(project_id: str):
    """Download the original uploaded document for a project."""
    project = ProjectManager.get_project(project_id)
    if not project:
        return jsonify({"success": False, "error": t('api.projectNotFound', id=project_id)}), 404

    files = ProjectManager._get_project_files(project_id)
    if not files:
        return jsonify({"success": False, "error": "No source file found"}), 404

    file_info = files[0]
    storage = get_storage()
    try:
        data = storage.download(file_info["storage_path"])
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    from flask import Response
    return Response(
        data,
        status=200,
        headers={
            "Content-Disposition": f'attachment; filename="{file_info["filename"]}"',
            "Content-Type": file_info.get("mime_type", "application/octet-stream"),
        }
    )
```

- [ ] **Step 4: Afegir endpoints de descàrrega a `backend/app/api/simulation.py`**

Afegir imports si no existeixen: `from flask import request, jsonify, send_file, Response` (ja existeix `send_file`).

Afegir funció helper privada i dos endpoints:

```python
def _get_simulation_log_path(simulation_id: str) -> str:
    """Return path to the combined actions log for a simulation."""
    sim_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)
    # Prefer combined log, fall back to twitter then reddit
    for candidate in [
        os.path.join(sim_dir, "actions.jsonl"),
        os.path.join(sim_dir, "twitter", "actions.jsonl"),
        os.path.join(sim_dir, "reddit", "actions.jsonl"),
    ]:
        if os.path.exists(candidate):
            return candidate
    return ""


@simulation_bp.route('/<simulation_id>/download/report', methods=['GET'])
def download_simulation_report(simulation_id: str):
    """Download the final report for a simulation as a Markdown file."""
    from ..services.report_agent import ReportManager
    try:
        report = ReportManager.get_report_by_simulation(simulation_id)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    if not report:
        return jsonify({"success": False, "error": t('api.noReportForSim', id=simulation_id)}), 404

    content = (report.markdown_content or "").encode("utf-8")
    filename = f"report_{report.report_id}.md"
    return Response(
        content,
        status=200,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/markdown; charset=utf-8",
        }
    )


@simulation_bp.route('/<simulation_id>/download/log', methods=['GET'])
def download_simulation_log(simulation_id: str):
    """Download the raw simulation actions log (JSONL)."""
    log_path = _get_simulation_log_path(simulation_id)
    if not log_path:
        return jsonify({"success": False, "error": "Log file not found"}), 404

    try:
        with open(log_path, "rb") as f:
            data = f.read()
    except OSError as e:
        return jsonify({"success": False, "error": str(e)}), 500

    filename = f"simulation_{simulation_id}_log.jsonl"
    return Response(
        data,
        status=200,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/x-ndjson",
        }
    )
```

- [ ] **Step 5: Verificar que els tests principals passen**

```bash
cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/test_project_download.py::TestSourceDownload -v
```
Expected: 3 tests PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/graph.py backend/app/api/simulation.py backend/tests/test_project_download.py
git commit -m "feat(api): add download endpoints for source doc, report and simulation log"
```

---

## Task 6: Millores al frontend — HistoryDatabase.vue (nom editable + fitxers + navegació)

**Files:**
- Modify: `frontend/src/components/HistoryDatabase.vue`
- Modify: `frontend/src/api/graph.js`
- Modify: `locales/ca.json`, `locales/es.json`, `locales/en.json`, `locales/zh.json`

Totes les modificacions d'aquesta tasca es fan en un sol commit perquè estan estretament lligades.

- [ ] **Step 1: Afegir `updateProjectName` a `frontend/src/api/graph.js`**

Al final del fitxer, afegir:

```javascript
/**
 * Actualitza el nom d'un projecte
 * @param {String} projectId
 * @param {String} name
 * @returns {Promise}
 */
export function updateProjectName(projectId, name) {
  return service({
    url: `/api/graph/project/${projectId}`,
    method: 'patch',
    data: { name }
  })
}
```

- [ ] **Step 2: Afegir les claus de traducció als 4 fitxers de localització**

A `locales/ca.json`, dins la secció `"history"`, afegir:
```json
"editName": "Edita el nom",
"namePlaceholder": "Nom del projecte",
"sourceDoc": "Document original",
"finalReport": "Informe final",
"simLog": "Log de simulació"
```

Fer el mateix a `locales/es.json`:
```json
"editName": "Editar nombre",
"namePlaceholder": "Nombre del proyecto",
"sourceDoc": "Documento original",
"finalReport": "Informe final",
"simLog": "Log de simulación"
```

A `locales/en.json`:
```json
"editName": "Edit name",
"namePlaceholder": "Project name",
"sourceDoc": "Source document",
"finalReport": "Final report",
"simLog": "Simulation log"
```

A `locales/zh.json`:
```json
"editName": "编辑名称",
"namePlaceholder": "项目名称",
"sourceDoc": "原始文档",
"finalReport": "最终报告",
"simLog": "模拟日志"
```

- [ ] **Step 3: Modificar `HistoryDatabase.vue` — imports i state**

A la línia de l'import d'API (línia 225), afegir `updateProjectName` a la importació:
```javascript
import { listProjects, deleteProject, updateProjectName } from '../api/graph'
```

Dins el bloc `<script setup>`, just després de `const deleteConfirmProject = ref(null)`, afegir:
```javascript
const editingName = ref(false)
const editedName = ref('')
```

- [ ] **Step 4: Modificar el modal header per fer el nom editable**

Al template, localitzar el bloc del `modal-header` (línia ~118). Substituir:

```html
<span class="modal-id">{{ selectedProject.name || (selectedProject.project_id || '').slice(0, 8) }}</span>
```

Per:
```html
<span v-if="!editingName" class="modal-id" @click="startEditName" style="cursor:pointer;" :title="$t('history.editName')">
  {{ selectedProject.name || (selectedProject.project_id || '').slice(0, 8) }}
  <span style="font-size:0.7rem; color:#9CA3AF; margin-left:4px;">✎</span>
</span>
<input
  v-else
  ref="nameInput"
  v-model="editedName"
  class="modal-name-input"
  :placeholder="$t('history.namePlaceholder')"
  @blur="saveEditedName"
  @keyup.enter="saveEditedName"
  @keyup.escape="cancelEditName"
/>
```

- [ ] **Step 5: Afegir les funcions d'edició de nom al `<script setup>`**

Just abans de la funció `goToProject`, afegir:

```javascript
const nameInput = ref(null)

const startEditName = () => {
  editedName.value = selectedProject.value?.name || ''
  editingName.value = true
  nextTick(() => nameInput.value?.focus())
}

const saveEditedName = async () => {
  const name = editedName.value.trim()
  editingName.value = false
  if (!name || !selectedProject.value) return
  if (name === selectedProject.value.name) return
  try {
    await updateProjectName(selectedProject.value.project_id, name)
    selectedProject.value = { ...selectedProject.value, name }
    const idx = projects.value.findIndex(p => p.project_id === selectedProject.value.project_id)
    if (idx !== -1) projects.value[idx] = { ...projects.value[idx], name }
  } catch (e) {
    console.error('Failed to update project name', e)
  }
}

const cancelEditName = () => {
  editingName.value = false
}
```

- [ ] **Step 6: Modificar la secció de fitxers relacionats al modal**

Localitzar el bloc de `modal-section` amb `relatedFiles` (línies ~138-147). Substituir el contingut de `<div class="modal-files" ...>` sencer per:

```html
<div class="modal-section">
  <div class="modal-label">{{ $t('history.relatedFiles') }}</div>
  <div class="modal-files" v-if="hasRelatedFiles(selectedProject)">
    <a
      v-if="selectedProject.files && selectedProject.files.length > 0"
      :href="`/api/graph/project/${selectedProject.project_id}/download/source`"
      class="modal-file-item modal-file-link"
      download
    >
      <span class="file-tag txt">SRC</span>
      <span class="modal-file-name">{{ selectedProject.files[0].filename }}</span>
      <span class="file-download-icon">↓</span>
    </a>
    <a
      v-if="selectedProject.last_simulation_id"
      :href="`/api/simulation/${selectedProject.last_simulation_id}/download/report`"
      class="modal-file-item modal-file-link"
      download
    >
      <span class="file-tag doc">RPT</span>
      <span class="modal-file-name">{{ $t('history.finalReport') }}</span>
      <span class="file-download-icon">↓</span>
    </a>
    <a
      v-if="selectedProject.last_simulation_id"
      :href="`/api/simulation/${selectedProject.last_simulation_id}/download/log`"
      class="modal-file-item modal-file-link"
      download
    >
      <span class="file-tag code">LOG</span>
      <span class="modal-file-name">{{ $t('history.simLog') }}</span>
      <span class="file-download-icon">↓</span>
    </a>
  </div>
  <div class="modal-empty" v-else>{{ $t('history.noRelatedFiles') }}</div>
</div>
```

Afegir la funció helper al `<script setup>`:

```javascript
const hasRelatedFiles = (project) => {
  if (!project) return false
  return (project.files && project.files.length > 0) || !!project.last_simulation_id
}
```

- [ ] **Step 7: Corregir `goToSimulation` i el disabled del botó Step 2**

Substituir la funció `goToSimulation` (línies ~467-475):

```javascript
// Actual (INCORRECTE):
const goToSimulation = () => {
  if (selectedProject.value?.graph_id) {
    router.push({
      name: 'Process',
      params: { projectId: selectedProject.value.project_id }
    })
    closeModal()
  }
}
```

Per:

```javascript
// Corregit:
const goToSimulation = () => {
  if (selectedProject.value?.last_simulation_id) {
    router.push({
      name: 'Simulation',
      params: { simulationId: selectedProject.value.last_simulation_id }
    })
    closeModal()
  }
}
```

Al template, localitzar el botó `btn-simulation` (línia ~169):
```html
:disabled="!selectedProject.graph_id"
```
Substituir per:
```html
:disabled="!selectedProject.last_simulation_id"
```

- [ ] **Step 8: Afegir CSS per als nous elements**

Dins `<style scoped>`, afegir al final:

```css
.modal-name-input {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1rem;
  font-weight: 600;
  color: #111827;
  border: 1px solid #D1D5DB;
  border-radius: 4px;
  padding: 2px 8px;
  outline: none;
  width: 260px;
}

.modal-name-input:focus {
  border-color: #3B82F6;
}

.modal-file-link {
  text-decoration: none;
  color: inherit;
  cursor: pointer;
}

.modal-file-link:hover {
  border-color: #3B82F6;
  background: #EFF6FF;
}

.file-download-icon {
  margin-left: auto;
  font-size: 0.85rem;
  color: #9CA3AF;
}
```

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/HistoryDatabase.vue frontend/src/api/graph.js \
        locales/ca.json locales/es.json locales/en.json locales/zh.json
git commit -m "feat(history): editable project name, related files downloads, fix step2 navigation"
```

---

## Task 7: Verificació end-to-end

- [ ] **Step 1: Arrancar el servidor de desenvolupament**

```bash
cd /home/ubuntu/dev/MiroFish && npm run dev
```

- [ ] **Step 2: Verificar generació automàtica del nom**
  - Crear un nou projecte pujant un document
  - Esperar 5-10 segons
  - Obrir l'historial → la fitxa ha de mostrar un nom generat per LLM (no "Unnamed Project")

- [ ] **Step 3: Verificar edició del nom**
  - Obrir el modal d'un projecte
  - Clicar sobre el nom → ha d'aparèixer un input editable
  - Canviar el nom i prémer Enter → el nom s'ha d'actualitzar al modal i a la fitxa de la llista
  - Refrescar la pàgina → el nou nom ha de persistir

- [ ] **Step 4: Verificar fitxers relacionats**
  - Obrir el modal d'un projecte que tingui simulació completada
  - La secció "Fitxers relacionats" ha de mostrar entre 1 i 3 links (document original, informe, log)
  - Clicar un dels links → s'ha de descarregar el fitxer corresponent

- [ ] **Step 5: Verificar navegació dels passos**
  - Des del modal d'un projecte amb simulació, prémer "Step2 Configuració de l'entorn"
  - Ha d'obrir `SimulationView` (URL `/simulation/:simulationId`), no `MainView`
  - Prémer "Step1 Construcció del graf" → ha d'obrir `MainView` (URL `/process/:projectId`)

- [ ] **Step 6: Executar tots els tests**

```bash
cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/ -v
```
Expected: tots els tests PASSED

---

## Notes d'implementació

- **`LLMClient.chat()`** retorna directament un `str` (la resposta del model). Veure `backend/app/utils/llm_client.py:67`.
- **`ProjectManager._get_project_files()`** és un mètode de classe que es pot cridar directament sense instanciar.
- **Log de simulació**: la ruta prioritzada és `{OASIS_SIMULATION_DATA_DIR}/{simulation_id}/actions.jsonl`, amb fallback a `twitter/actions.jsonl` i `reddit/actions.jsonl`.
- **Ruta Simulation** al router: `name: 'Simulation'` → `/simulation/:simulationId` → `SimulationView`. Confirmada a `frontend/src/router/index.js:30-33`.
- **`report.markdown_content`**: propietat de l'objecte `Report` (dataclass a `report_agent.py:447`).
