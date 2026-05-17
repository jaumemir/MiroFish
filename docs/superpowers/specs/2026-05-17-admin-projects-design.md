# Disseny: Secció "Projectes" al panell d'administració

**Data:** 2026-05-17  
**Estat:** Aprovat

## Context

L'administrador veia tots els projectes com si fossin propis a la vista "Els meus projectes". Això és incorrecte: l'admin ha de veure els seus propis projectes a la vista normal, i gestionar tots els projectes del sistema des d'una secció específica dins l'àrea d'administració. L'admin no accedeix al flux normal (graf, simulació, informe) dels projectes d'altri — només pot veure informació tècnica i eliminar-ne.

## Canvis al backend

### Nous endpoints a `backend/app/api/admin.py`

**`GET /api/admin/projects`**
- Requereix `@require_admin`
- Retorna llista de tots els projectes amb: `project_id`, `name`, `owner_email`, `owner_name`, `simulation_count`, `status`, `created_at`
- Consulta: JOIN ProjectModel + UserModel + COUNT(SimulationModel)

**`GET /api/admin/projects/<project_id>`**
- Requereix `@require_admin`
- Retorna detall complet:
  - `project_id`, `name`, `status`, `created_at`
  - `owner_email`, `owner_name`
  - `graphs`: llista de `{ graph_id, external_id, backend, status, node_count, edge_count, created_at }`
  - `simulations`: llista de `{ simulation_id, graph_id, status, platform, rounds_total, rounds_completed, created_at }`

**`DELETE /api/admin/projects/<project_id>`**
- Requereix `@require_admin`
- Elimina en cascada: grafs externs (via GraphBuilderService), fitxers de storage, i el projecte a la BD (la cascada SQLAlchemy s'encarrega de simulacions, grafs, etc.)
- Reutilitza el patró existent de `purge_user`

**`DELETE /api/admin/simulations/<simulation_id>`**
- Requereix `@require_admin`
- Elimina la simulació de la BD (cascada: reports associats)
- No elimina grafs ni storage del projecte pare

## Canvis al frontend

### Router (`frontend/src/router/index.js`)
Sense canvis: la ruta `/admin/:tab` ja accepta qualsevol valor de pestanya.

### `AdminView.vue`

**Ordre de pestanyes:**
1. Usuaris (`/admin/users`)
2. **Projectes** (`/admin/projects`) ← nou
3. Configuració (`/admin/config`)
4. Historial (`/admin/executions`)

**Tab "Projectes" — taula principal:**

| Columna | Contingut |
|---|---|
| Nom projecte | Nom del projecte |
| Propietari | email del propietari |
| Simulacions | Recompte numèric |
| Estat | Badge (created / graph_completed / etc.) |
| Creat | Data |
| Accions | Botó "Detall" |

**Modal de detall del projecte:**
- S'obre en clicar "Detall" a qualsevol fila
- **No es tanca en clicar fora** — només amb el botó × (tancar) explícit
- Contingut:
  - Capçalera: nom del projecte + propietari
  - Bloc "Identificadors": ID Projecte en mono
  - Bloc "Graf(s)": taula amb ID intern, ID extern, backend, estat, nodes/arestes
  - Bloc "Simulacions": taula amb ID Simulació, ID Graf sim, Estat (badge), Plataforma, Rondes, Data + botó "Eliminar" per fila
  - Peu: botó "Eliminar projecte" (color vermell)
- Les eliminacions mostren confirmació inline dins el modal (text de confirmació + botó confirmar/cancel·lar), sense obrir un segon modal per sobre

**Flux d'eliminació de simulació (inline al modal):**
1. Clic "Eliminar" a la fila → la fila mostra "Confirmar eliminació? [Sí] [No]"
2. Clic "Sí" → crida `DELETE /api/admin/simulations/<id>` → refresca la llista de simulacions del modal

**Flux d'eliminació de projecte (inline al modal):**
1. Clic "Eliminar projecte" → apareix zona de confirmació al peu: "Escriu el nom del projecte per confirmar" + input + botó "Eliminar definitivamente"
2. Validació: el text ha de coincidir exactament amb el nom del projecte
3. Clic confirmar → crida `DELETE /api/admin/projects/<id>` → tanca modal → refresca taula

## Canvis d'i18n

Noves claus a `locales/{ca,es,en}.json` sota el namespace `admin`:

```
admin.projects          → "Projectes" / "Proyectos" / "Projects"
admin.projectDetail     → "Detall del projecte" / ...
admin.owner             → "Propietari" / "Propietario" / "Owner"
admin.simulations       → "Simulacions" / "Simulaciones" / "Simulations"
admin.graphs            → "Grafs" / "Grafos" / "Graphs"
admin.noProjects        → "Cap projecte" / ...
admin.deleteProject     → "Eliminar projecte" / ...
admin.deleteProjectConfirmLabel → "Escriu el nom per confirmar" / ...
admin.deleteProjectSuccess → "Projecte eliminat" / ...
admin.deleteSimulation  → "Eliminar simulació" / ...
admin.deleteSimulationSuccess → "Simulació eliminada" / ...
admin.confirmYes        → "Sí, eliminar" / ...
admin.externalId        → "ID extern" / ...
admin.graphId           → "ID graf" / ...
admin.simulationId      → "ID simulació" / ...
admin.projectId         → "ID projecte" / ...
admin.nodeCount         → "Nodes" / ...
admin.edgeCount         → "Arestes" / "Aristas" / "Edges"
```

## Restriccions importants

- L'admin NO pot accedir a `ProjectDetailView` ni a cap ruta del flux normal per a projectes d'altri.
- El fix del `list_projects` al backend: `filter_user_id` ha de ser `user.id` per a l'admin (no `None`), de manera que la vista "Els meus projectes" mostri únicament els projectes propis de l'admin.
- Tots els modals nous: **mai** `@click.self="close"` a l'overlay.
