# Spec: Pantalla de Detall de Projecte

**Data:** 2026-05-16
**Branca:** feature/fase3-roles-admin (o branca pròpia)
**Estat:** Aprovada pel disseny

---

## Resum

Afegir una nova vista `ProjectDetailView` que actua com a **hub de treball** per a projectes ja creats. Des de Home, clicar un projecte existent obre aquesta pantalla en lloc d'anar directament al flux de 5 steps. Des d'aquí l'usuari pot gestionar el graph base, veure i gestionar les simulacions, i entrar a qualsevol punt del flux de MiroFish.

El flux de **nou projecte** no canvia.

---

## Arquitectura

### Noves vistes

- `frontend/src/views/ProjectDetailView.vue` — nova vista hub

### Vistes existents modificades

- `frontend/src/views/Home.vue` — redirigir projectes existents a `/project/:projectId`
- `frontend/src/components/Process.vue` — suport a `?mode=adjust&simulationId=xxx`
- `frontend/src/views/ReportView.vue` — respectar `router.state.backTo`
- `frontend/src/views/InteractionView.vue` — respectar `router.state.backTo`
- `frontend/src/views/SimulationRunView.vue` — respectar `router.state.backTo`
- `frontend/src/components/LanguageSwitcher.vue` — fix color text visible sobre fons negre

### Noves rutes (router/index.js)

```text
/project/:projectId  →  ProjectDetailView
```

La ruta `/simulation/:simulationId/edit` **no es crea** — s'usa Process.vue en mode adjust.

---

## Layout de ProjectDetailView

Dues columnes amb `height: 100vh`:

**Columna esquerra (~340px, fixa, overflow-y: auto):**

1. Nom del projecte + data de creació
2. Pregunta de simulació (read-only)
3. Fitxer inicial: nom + botó descarregar
4. Ontologia: nom + botó descarregar + botó "Pujar nova ontologia"
5. Graph base: status + ID + num entitats + botons d'acció
6. Mini-preview del graf (GraphPanel en mode compacte) si hi ha espai visual disponible

**Columna dreta (flex: 1, overflow-y: auto):**

- Header "Simulacions (N)" + botó "+ Nova simulació"
- Llista de targetes de simulació (densitat mitjana)

---

## Targetes de Simulació

Cada targeta mostra: número ordinal, status (badge de color), plataforma, rondes completades/total, data creació, ID del graph usat.

Botons per estat:

| Estat | Botons disponibles |
| --- | --- |
| **Completada** | Ajustar · Re-generar informe · Interacció · ↓ MD · ↓ PDF · ↓ Log · Esborrar |
| **En curs** | Esborrar |
| **Fallida** | Ajustar i re-llançar · Esborrar |
| **Preparada** | Ajustar · Esborrar |

- "Interacció" només apareix si hi ha informe generat.
- "Esborrar" mostra confirmació abans d'executar.

---

## Graph Base — Estats i Accions

| Estat | Accions |
| --- | --- |
| En curs | Cap (polling, mostra progrés) |
| Completat | "Veure graph" (modal) · "Forçar regeneració" |
| Fallat | "Reintentar" |
| Nova ontologia pujada | Avís prominent · "Regenerar graph" (forçat automàtic) |

**"Forçar regeneració"** = esborra el graph actual i reconstrueix des de l'ontologia existent. Equivalent a tornar a Step 1 sense tocar el document ni l'ontologia.

**Pujar nova ontologia** → marca l'estat com "nova ontologia pujada" i força regeneració del graph. L'ontologia anterior queda substituïda (no s'historifica).

El graph base no s'historifica. Cada simulació guarda l'`graph_id` que es va usar en el moment de llançar-la (camp `graph_id` a `SimulationModel`).

---

## Flux de Nova Simulació

Des de ProjectDetailView, "+ Nova simulació":

1. Navega a `Process.vue` en **mode normal** al Step 2 (generació d'agents des del graph actual)
2. Continua Step 3 (paràmetres de simulació)
3. SimulationRunView → ReportView → InteractionView
4. "Tornar" des de qualsevol punt retorna a `ProjectDetailView`

---

## Flux d'"Ajustar" Simulació

Des de la targeta de simulació, botó "Ajustar":

1. Navega a `Process.vue` amb `?mode=adjust&simulationId=xxx`
2. Process.vue carrega les dades de la simulació existent (agents + paràmetres)
3. Totes les seccions es mostren en **mode read-only** amb banner "✏️ Editar aquesta secció"
4. L'usuari edita secció a secció; les altres continuen read-only
5. Botó principal: "▶ Llançar simulació" (en lloc de "Generar agents")
6. En llançar: **clona el graph base actual** i crea una **nova simulació** (la original no es modifica mai)
7. Continua SimulationRunView → ReportView → InteractionView
8. "Tornar" retorna a `ProjectDetailView`

### Regles de consistència (mode adjust)

- Eliminar agent → elimina la seva entrada a la config de simulació (Step 3)
- Canviar plataforma d'agent → actualitza automàticament la seva entrada a la config
- Afegir agent nou → crea entrada buida a la config de simulació per omplir
- Avisos inline en temps real quan una acció afecta la consistència

---

## Navegació i Retorn (router.state.backTo)

Quan es navega des de `ProjectDetailView` cap a qualsevol vista del flux:

```js
router.push({ name: 'SimulationRun', params: {...}, state: { backTo: `/project/${projectId}` } })
```

Les vistes `SimulationRunView`, `ReportView`, `InteractionView` llegeixen `history.state.backTo` al botó "Tornar" / "Finalitzar". Si existeix, usen aquesta ruta. Si no (flux normal de nou projecte), usen el comportament actual (Home).

---

## API Backend — Canvis

### Nous endpoints

**`GET /api/graph/project/:id/detail`**
Retorna en una sola crida: info projecte + fitxer font + ontologia activa + graph base (id, status, num entitats) + llista de simulacions amb status i camps bàsics.

**`GET /api/simulation/:id/detail`**
Detall complet d'una simulació per al mode adjust: agents (profiles), config paràmetres, `graph_id` usat.

### Endpoints a verificar / completar

- `GET /api/graph/project/:id/download/source` — descàrrega fitxer original (verificar si existeix)
- `GET /api/ontology/:id/download` — descàrrega ontologia (verificar o crear)
- `GET /api/report/:id/download` — PDF (ja existeix)
- `GET /api/report/:id/download/md` — format MD (verificar o crear)
- `GET /api/simulation/:id/log/download` — log de simulació (verificar o crear)
- `DELETE /api/simulation/:id` — esborrar simulació (verificar si existeix)

---

## Fix Inclòs: LanguageSwitcher

`frontend/src/components/LanguageSwitcher.vue`: el text del llenguatge seleccionat no era visible sobre la navbar de fons negre. Fix ja aplicat manualment per l'usuari — s'inclou al commit de la feature.

---

## Fora d'Abast

- Historificació del graph base (no cal)
- Edició del nom del projecte o de la pregunta de simulació des d'aquesta pantalla (ja es pot fer des de Home)
- Paginació de simulacions (màxim ~5 per projecte)
- Mode mòbil / responsive (no és un requisit actual)
