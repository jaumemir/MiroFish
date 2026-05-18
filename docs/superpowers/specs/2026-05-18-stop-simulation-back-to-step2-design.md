# Disseny: Aturar simulació i tornar al Step 2

**Data:** 2026-05-18  
**Àmbit:** Step 3 (SimulationRunView / Step3Simulation) + backend `start_simulation`

---

## Problema

Quan una simulació no flueix bé (rondes incorrectes, agents mal configurats), l'usuari necessita:
1. Aturar la simulació en curs.
2. Tornar al Step 2 amb tots els agents i paràmetres editables.
3. Relançar una nova simulació neta.

El flux actual no té un botó explícit de retorn al Step 2 des del Step 3, i el graf clonat de simulació no es neteja en relançar.

---

## Decisió de disseny

**Enfocament A** — Botó explícit "← Pas anterior" al Step 3, neteja del graf en relançar.

### Raonament

- Step 2 ja conté tota la UI d'edició d'agents i paràmetres — no cal duplicar-la al Step 3.
- L'usuari controla explícitament l'aturada (prem "Aturar" primer) i després el retorn.
- La neteja del graf es fa al moment de relançar (`force=True`) — simple i consistent.

---

## Canvis

### 1. `frontend/src/components/Step3Simulation.vue`

Afegir botó `← Pas anterior` al `control-bar`:

- **Visible** quan `phase !== 1` (simulació no en curs: no iniciada, aturada o completada).
- **Ocult** quan `phase === 1` (running) — l'usuari ha d'aturar primer amb el botó "Aturar".
- En prémer, emet l'event `go-back` (ja definit al component).
- Posició: a l'esquerra del botó "Aturar" dins `action-controls`.

```vue
<button
  v-if="phase !== 1"
  class="action-btn back"
  @click="$emit('go-back')"
>
  ← {{ $t('step3.backToPrevStep') }}
</button>
```

Nova clau i18n necessària: `step3.backToPrevStep`.

### 2. `frontend/src/views/SimulationRunView.vue`

Funció `handleGoBack`: quan la simulació ja no és en curs (`!isSimulating.value`), navegar directament a Step 2 sense intentar aturar de nou.

```js
const handleGoBack = async () => {
  stopGraphRefresh()
  if (isSimulating.value) {
    // Aturar si encara running (cas de fallback)
    await stopAndCleanup()
  }
  router.push({ name: 'Simulation', params: { simulationId: currentSimulationId.value } })
}
```

### 3. `backend/app/api/simulation.py` — `start_simulation`

Quan `force=True` i `state.graph_id_simulation` existeix, eliminar el graf clonat **abans** de clonar-ne un de nou:

```python
if force and state.graph_id_simulation:
    try:
        graph_backend = get_graph_backend()
        graph_backend.delete_graph(state.graph_id_simulation)
    except Exception:
        pass  # Silenciós: el graf pot ja no existir
    state.graph_id_simulation = None
```

La fallada silenciosa és correcta: si el graf ja no existia (eliminat manualment, error previ), el flux continua sense bloquejar.

---

## Flux complet

```
Step 3 running
  └─ Usuari prem "Aturar"
      └─ phase = 0, canResume = true
          └─ Apareix botó "← Pas anterior"
              └─ Usuari prem "← Pas anterior"
                  └─ Navega a Step 2 (SimulationView)
                      └─ Step 2 carrega agents i config existents (editables)
                          └─ Usuari edita agents/paràmetres
                              └─ Usuari prem "Simular →"
                                  └─ start_simulation(force=True)
                                      ├─ Elimina graf clonat anterior
                                      ├─ Clona nou graf
                                      └─ Navega a Step 3 (nova simulació)
```

---

## Consistència d'agents

Quan l'usuari canvia la postura d'un agent i el regenera al Step 2, el perfil OASIS s'actualitza a la BD. `start_simulation` llegeix sempre els perfils actuals de `SimulationManager` — no hi ha caché. No cal cap lògica addicional.

---

## Fitxers afectats

| Fitxer | Canvi |
|--------|-------|
| `frontend/src/components/Step3Simulation.vue` | Afegir botó `← Pas anterior` (visible si `phase !== 1`) |
| `frontend/src/views/SimulationRunView.vue` | `handleGoBack`: no aturar si ja està aturat |
| `backend/app/api/simulation.py` | `start_simulation`: eliminar `graph_id_simulation` antic si `force=True` |
| `locales/en.json`, `ca.json`, `es.json` | Afegir clau `step3.backToPrevStep` |

---

## Fora d'àmbit

- No es modifica Step 2 (`SimulationView`, `Step2EnvSetup`): ja funciona correctament per al flux de retorn.
- No s'afegeix modal de confirmació en prémer el botó enrere.
- No s'elimina el graf en prémer "Enrere" (es fa en relançar).
