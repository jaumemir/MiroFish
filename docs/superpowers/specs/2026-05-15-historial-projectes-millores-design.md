# Disseny: Millores de les fitxes de projecte a l'historial de simulacions

**Data:** 2026-05-15  
**Àmbit:** `HistoryDatabase.vue`, backend `project.py`, `graph.py`, `simulation.py`

---

## Context

Les fitxes de projecte a l'historial (`HistoryDatabase.vue`) presenten tres mancances:

1. **Nom de projecte**: el camp `name` existeix a la BD però sempre és buit o genèric; no es genera automàticament ni hi ha UI per editar-lo.
2. **Fitxers relacionats**: la secció sempre mostra "Sense fitxers relacionats" perquè l'API retorna `files: []` hardcoded i no hi ha endpoints de descàrrega.
3. **Navegació dels passos de reproducció**: el pas 2 ("Configuració de l'entorn") navega a la mateixa ruta que el pas 1 (graf), en comptes d'anar a `SimulationView` on l'usuari pot editar agents i paràmetres.

---

## Millora 1: Generació automàtica del nom i edició

### Generació
- **On:** Al backend, just després de processar el primer document pujat. El punt d'entrada és `backend/app/api/graph.py` (endpoint de creació/pujada de documents).
- **Com:** Nova funció `generate_project_name(text: str) -> str` a `backend/app/services/project_name_generator.py`. Fa una crida LLM (boost si disponible, principal si no) amb un prompt curt per obtenir un títol de 5-8 paraules.
- **Fallback:** Si la crida falla, assigna `"Simulació {YYYY-MM-DD}"`.
- **Persistència:** El resultat s'assigna via `ProjectManager.save_project()` al camp `name`.

### Edició
- **On:** Modal de detall del projecte a `HistoryDatabase.vue`.
- **Com:** El `<h3>` estàtic del nom passa a ser un `<input>` editable. En `blur` o `Enter`, s'envia `PATCH /api/projects/<id>` amb `{ "name": "..." }`.
- **Backend:** Verificar que `ProjectManager.save_project()` accepta actualitzar el camp `name` (camp ja a la llista `updatable`). Afegir endpoint PATCH si no existeix.

---

## Millora 2: Fitxers relacionats descarregables

### Nous endpoints

| Endpoint | Fitxer servit | Condició |
|----------|--------------|----------|
| `GET /api/projects/<id>/download/source` | Document original pujat | Existeix entrada a `project_files` amb `file_type='upload'` |
| `GET /api/simulation/<id>/download/report` | Informe generat (text/JSON → `.txt` o `.json`) | Existeix `last_report_id` associat |
| `GET /api/simulation/<id>/download/log` | Log de simulació (IPC JSON) | Existeix fitxer de log al directori de simulació |

Tots retornen `Content-Disposition: attachment; filename=<nom>` i el contingut del fitxer des del storage (Azure Blob o local, via `azure_blob.py`).

### Frontend (`HistoryDatabase.vue`)
- La secció `relatedFiles` renderitza una llista de `<a href="..." download>` per a cada recurs disponible.
- Un recurs és disponible si el seu ID/path existeix a les dades del projecte.
- Si cap recurs és disponible, es manté el text "Sense fitxers relacionats".
- Tres possibles entrades: **Document inicial**, **Informe final**, **Log de simulació**.

---

## Millora 3: Navegació correcta dels passos de reproducció

### Canvi a `goToSimulation()` (pas 2)

**Actual:**
```js
router.push({ name: 'Process', params: { projectId: selectedProject.value.project_id } })
```

**Nou:**
```js
router.push({ name: 'Simulation', params: { simulationId: selectedProject.value.last_simulation_id } })
```

La ruta `Simulation` (`/simulation/:simulationId`) apunta a `SimulationView`, on l'usuari pot editar agents i paràmetres abans de llançar la simulació.

### Estat dels botons de reproducció

| Botó | Destí | Habilitat si... |
|------|-------|----------------|
| Pas 1 — Construcció del graf | `/process/:projectId` | `project_id` existeix |
| Pas 2 — Configuració de l'entorn | `/simulation/:simulationId` | `last_simulation_id` existeix |
| Pas 4 — Informe d'anàlisi | `/interaction/:reportId` | `last_report_id` o `last_simulation_id` existeix |

*(Pas 3 no té botó de reproducció per disseny.)*

---

## Fitxers crítics

**Backend:**
- `backend/app/api/graph.py` — afegir crida a `generate_project_name` en crear projecte
- `backend/app/api/simulation.py` — afegir endpoints de descàrrega de report i log
- `backend/app/models/project.py` — afegir endpoint PATCH per nom; verificar `save_project`
- `backend/app/services/project_name_generator.py` — **fitxer nou**

**Frontend:**
- `frontend/src/components/HistoryDatabase.vue` — edició de nom, fitxers relacionats, navegació pas 2

**Localitzacions:**
- `locales/{en,es,ca,zh}.json` — possibles claus noves per als labels dels fitxers

---

## Verificació

1. Crear un nou projecte pujant un document → el nom s'ha de generar automàticament (veure a l'historial).
2. Editar el nom des del modal → el canvi persists en recarregar la pàgina.
3. A la fitxa d'un projecte complet, la secció "Fitxers relacionats" mostra els 3 links → cadascun descarrega el fitxer correcte.
4. Des de l'historial, prémer pas 1 → obre `MainView` (graf). Prémer pas 2 → obre `SimulationView` (edició d'agents).
5. Prémer pas 4 → obre la vista d'interacció amb l'informe.
