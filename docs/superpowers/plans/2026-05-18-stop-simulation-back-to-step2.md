# Stop Simulation & Back to Step 2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permetre a l'usuari aturar la simulació al Step 3, tornar al Step 2 per editar agents i paràmetres, i relançar una simulació neta (eliminant el graf clonat anterior).

**Architecture:** Botó "← Pas anterior" al `Step3Simulation.vue` (visible només quan `phase !== 1`); `handleGoBack` simplificat a `SimulationRunView.vue`; neteja del `graph_id_simulation` antic al backend `start_simulation` quan `force=True`; claus i18n noves als tres idiomes.

**Tech Stack:** Vue 3 (Composition API), Flask (Python), vue-i18n v11, fitxers JSON de localització a `/locales/`.

---

## Fitxers afectats

| Fitxer | Acció |
|--------|-------|
| `frontend/src/components/Step3Simulation.vue` | Modificar: afegir botó `← Pas anterior` al `control-bar` |
| `frontend/src/views/SimulationRunView.vue` | Modificar: simplificar `handleGoBack` |
| `backend/app/api/simulation.py` | Modificar: eliminar graf clonat antic si `force=True` |
| `locales/en.json` | Modificar: afegir `step3.backToPrevStep` |
| `locales/ca.json` | Modificar: afegir `step3.backToPrevStep` |
| `locales/es.json` | Modificar: afegir `step3.backToPrevStep` |

---

## Task 1: Afegir clau i18n `step3.backToPrevStep` als tres idiomes

**Files:**
- Modify: `locales/en.json`
- Modify: `locales/ca.json`
- Modify: `locales/es.json`

- [ ] **Step 1: Afegir clau a `locales/en.json`**

Localitza el bloc `"step3"` (línia ~233). Afegir després de `"resumeException"`:

```json
"backToPrevStep": "← Previous step"
```

El bloc queda:
```json
"step3": {
  "startGenerateReport": "Generate Report",
  "generatingReport": "Starting...",
  "stoppingSim": "Stopping simulation...",
  "startGenerateReportBtn": "Generate Report",
  "generatingReportBtn": "Starting...",
  "stopSimBtn": "Stop simulation",
  "stoppingSimBtn": "Stopping...",
  "resumeSimBtn": "Resume simulation",
  "resumingSim": "Resuming simulation...",
  "simResumed": "Simulation resumed",
  "resumeFailed": "Resume failed: {error}",
  "resumeException": "Resume error: {error}",
  "backToPrevStep": "← Previous step"
},
```

- [ ] **Step 2: Afegir clau a `locales/ca.json`**

Localitza el bloc `"step3"` (línia ~233). Afegir després de `"resumeException"`:

```json
"backToPrevStep": "← Pas anterior"
```

- [ ] **Step 3: Afegir clau a `locales/es.json`**

Localitza el bloc `"step3"` (línia ~233). Afegir després de `"resumeException"`:

```json
"backToPrevStep": "← Paso anterior"
```

- [ ] **Step 4: Verificar que els JSON són vàlids**

```bash
python3 -c "import json; json.load(open('locales/en.json')); json.load(open('locales/ca.json')); json.load(open('locales/es.json')); print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add locales/en.json locales/ca.json locales/es.json
git commit -m "feat(i18n): afegir clau step3.backToPrevStep als tres idiomes"
```

---

## Task 2: Afegir botó "← Pas anterior" a `Step3Simulation.vue`

**Files:**
- Modify: `frontend/src/components/Step3Simulation.vue`

El botó ha d'aparèixer al `action-controls` div (línia ~100), **a l'esquerra del botó "Aturar"**, i ha de ser visible només quan `phase !== 1` (no running).

- [ ] **Step 1: Localitzar el punt d'inserció**

Obre `frontend/src/components/Step3Simulation.vue`. Busca el div `action-controls` (línia ~100). L'estructura actual és:

```html
<div class="action-controls">
  <fieldset ...>
    ...
  </fieldset>
  <!-- Botó atura (quan s'executa) -->
  <button v-if="phase === 1" class="action-btn stop" ...>
  <!-- Botó reprèn (quan pausada) -->
  <button v-if="phase === 0 && canResume" class="action-btn resume" ...>
  <!-- Botó genera informe -->
  <button class="action-btn primary" ...>
</div>
```

- [ ] **Step 2: Inserir el botó "← Pas anterior" just abans del botó "Aturar"**

Afegir el bloc següent **immediatament abans** del comentari `<!-- Botó atura (quan s'executa) -->`:

```html
<!-- Botó tornar al pas anterior (quan no running) -->
<button
  v-if="phase !== 1"
  class="action-btn back"
  @click="$emit('go-back')"
>
  {{ $t('step3.backToPrevStep') }}
</button>
```

- [ ] **Step 3: Afegir estil `.action-btn.back`**

A la secció `<style scoped>`, localitza `.action-btn.stop` (línia ~1116). Afegir **just abans**:

```css
.action-btn.back {
  background: #fff;
  color: #555;
  border: 1px solid #e0e0e0;
}

.action-btn.back:hover:not(:disabled) {
  background: #f5f5f5;
  border-color: #bbb;
}
```

- [ ] **Step 4: Verificar visualment al navegador**

Si el servidor de dev ja corre (`npm run dev`), obre el Step 3 d'una simulació aturada (`phase === 0`). El botó "← Pas anterior" ha d'aparèixer a l'esquerra del botó "Reprendre".

Si la simulació no està aturada, verificar que el botó **no apareix** quan `phase === 1`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Step3Simulation.vue
git commit -m "feat(step3): afegir botó 'Pas anterior' visible quan simulació no running"
```

---

## Task 3: Simplificar `handleGoBack` a `SimulationRunView.vue`

**Files:**
- Modify: `frontend/src/views/SimulationRunView.vue`

La funció `handleGoBack` actual (línia ~135) intenta aturar la simulació incondicionalment. Com que el botó "← Pas anterior" només apareix quan `phase !== 1`, la simulació ja no pot estar en curs quan es prem. Simplificar per evitar lògica redundant.

- [ ] **Step 1: Localitzar `handleGoBack` a `SimulationRunView.vue`**

Busca la funció `handleGoBack` (línia ~135). L'estructura actual:

```js
const handleGoBack = async () => {
  addLog(t('log.preparingGoBack'))
  stopGraphRefresh()
  try {
    const envStatusRes = await getEnvStatus(...)
    // ... lògica complexa d'aturada ...
  } catch (err) { ... }
  router.push({ name: 'Simulation', params: { simulationId: currentSimulationId.value } })
}
```

- [ ] **Step 2: Substituir `handleGoBack` per la versió simplificada**

Substituir **tota** la funció `handleGoBack` per:

```js
const handleGoBack = () => {
  stopGraphRefresh()
  router.push({ name: 'Simulation', params: { simulationId: currentSimulationId.value } })
}
```

La lògica d'aturada s'ha eliminat perquè:
- El botó "← Pas anterior" al Step 3 ja és invisible quan `phase === 1` (running).
- `SimulationView.onMounted` ja crida `checkAndStopRunningSimulation` si cal.

- [ ] **Step 3: Verificar que la importació `getEnvStatus` i `closeSimulationEnv` segueix sent usada**

```bash
grep -n "getEnvStatus\|closeSimulationEnv" frontend/src/views/SimulationRunView.vue
```

Si no apareixen en cap altre lloc, eliminar-les de la línia d'imports (línia ~57):

```js
import { getSimulation, getSimulationConfig, stopSimulation } from '../api/simulation'
```

(Eliminar `closeSimulationEnv` i `getEnvStatus` de la llista d'imports si no s'usen.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/SimulationRunView.vue
git commit -m "refactor(step3): simplificar handleGoBack, navegació directa sense aturada redundant"
```

---

## Task 4: Neteja del graf clonat al backend quan `force=True`

**Files:**
- Modify: `backend/app/api/simulation.py`

Quan `force=True` a `start_simulation` i existeix `state.graph_id_simulation`, eliminar el graf clonat antic **abans** del nou clon.

- [ ] **Step 1: Localitzar el punt d'inserció a `simulation.py`**

Busca la línia:
```python
# Clone graph for per-simulation isolation
graph_id_simulation = None
if enable_graph_memory_update and graph_id:
```
(línia ~1829)

Just **abans** d'aquesta línia s'inserirà el codi de neteja.

- [ ] **Step 2: Inserir el bloc de neteja del graf antic**

Inserir el bloc següent just **abans** del comentari `# Clone graph for per-simulation isolation`:

```python
        # Delete previous simulation graph if force-restarting
        if force and state.graph_id_simulation:
            try:
                from ..graph import get_graph_backend
                _old_graph_backend = get_graph_backend()
                _old_graph_backend.delete_graph(state.graph_id_simulation)
                logger.info(f"Deleted old simulation graph: {state.graph_id_simulation}")
            except Exception as _del_err:
                logger.warning(f"Could not delete old simulation graph {state.graph_id_simulation}: {_del_err}")
            state.graph_id_simulation = None
            manager._save_simulation_state(state)
```

Notes:
- `from ..graph import get_graph_backend` ja s'importa al bloc de clonació que ve just després — l'import duplicat no fa res de dolent però per neteja es pot usar el mateix nom de variable.
- La fallada és silenciosa (`logger.warning`) i no bloqueja el relanç.
- `state.graph_id_simulation = None` + `_save_simulation_state` assegura que no queda referència morta.

- [ ] **Step 3: Verificar que `get_graph_backend` no s'importa dues vegades en el mateix scope**

Revisar les línies ~1829-1845. Si el bloc de clonació existent ja té `from ..graph import get_graph_backend` a la mateixa funció, extreure'l al principi del bloc nou per evitar duplicació:

```python
        # Delete previous simulation graph if force-restarting
        if force and state.graph_id_simulation:
            try:
                from ..graph import get_graph_backend as _get_gb
                _get_gb().delete_graph(state.graph_id_simulation)
                logger.info(f"Deleted old simulation graph: {state.graph_id_simulation}")
            except Exception as _del_err:
                logger.warning(f"Could not delete old simulation graph {state.graph_id_simulation}: {_del_err}")
            state.graph_id_simulation = None
            manager._save_simulation_state(state)
```

(L'alias `_get_gb` evita qualsevol conflicte de nom amb l'import del bloc de clonació.)

- [ ] **Step 4: Arrancar el backend i verificar que no hi ha errors de sintaxi**

```bash
cd /home/ubuntu/dev/MiroFish && uv run python -c "from backend.app.api.simulation import start_simulation; print('OK')"
```

Expected: `OK` (o error d'imports externs com Neo4j — acceptable si no estan configurats, però no `SyntaxError`).

Alternativament:
```bash
uv run python -m py_compile backend/app/api/simulation.py && echo "Syntax OK"
```

Expected: `Syntax OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/simulation.py
git commit -m "feat(backend): eliminar graf clonat antic en relancar simulació (force=True)"
```

---

## Task 5: Test manual del flux complet

**Files:** Cap canvi de codi — verificació funcional.

- [ ] **Step 1: Arrancar l'entorn de dev**

```bash
npm run dev
```

Obrir `http://localhost:3000`.

- [ ] **Step 2: Verificar botó invisible quan running**

Navegar a un projecte → Step 3. Quan la simulació arranca (`phase === 1`), verificar que el botó "← Pas anterior" **no apareix** al `action-controls`.

- [ ] **Step 3: Aturar la simulació i verificar botó visible**

Prémer "Aturar simulació". Quan `phase === 0` i `canResume === true`, verificar que apareix el botó "← Pas anterior".

- [ ] **Step 4: Prémer "← Pas anterior" i verificar navegació**

Prémer el botó. Verificar que:
1. Es navega a Step 2 (`/simulation/:id`).
2. Step 2 mostra els agents i la configuració correctament.
3. No apareixen errors a la consola del navegador.

- [ ] **Step 5: Relançar simulació des de Step 2**

Prémer "Simular →" al Step 2 (amb `force: true`). Verificar als logs del backend:
```
Deleted old simulation graph: mirofish_<sim_id>_sim
Graph cloned for simulation isolation: mirofish_<sim_id>_sim
```

- [ ] **Step 6: Commit final si tot és correcte**

```bash
git log --oneline -5
```

Verificar que els 4 commits de les tasks anteriors hi són.
