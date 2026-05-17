# Disseny: System Config ampliat amb prevalença BD > env

**Data:** 2026-05-17
**Estat:** Aprovat

---

## Resum

Ampliar la taula `system_config` perquè cobreixi totes les variables de comportament del sistema (LLM principal i secundaris, simulació, informe, email). Afegir una funció helper `get_config(key, default)` que implementi la prevalença BD > env. Millorar la UI de configuració a l'AdminView agrupant per secció i tractant els secrets de manera segura (mai surten del backend).

---

## Motivació

Ara mateix, totes les variables de configuració de comportament resideixen exclusivament a les variables d'entorn / `Config`. Això impedeix canviar-les sense reiniciar el servidor i les fa invisibles a l'admin. La pestanya "Configuració" de l'AdminView existeix però només exposa 5 claus bàsiques.

---

## Claus a `system_config`

### Grup `llm` (LLM principal)

| Clau | Tipus | Secret | Valor per defecte (env fallback) |
|---|---|---|---|
| `llm.api_key` | string | **sí** | `LLM_API_KEY` |
| `llm.base_url` | string | no | `LLM_BASE_URL` |
| `llm.model_name` | string | no | `LLM_MODEL_NAME` |
| `llm.max_tokens` | int | no | `0` (0 = sense límit explícit; `get_config` retorna `None` si el valor és 0) |
| `llm.provider` | string | no | `LLM_PROVIDER` |

### Grup `llm` (LLM boost — OASIS)

| Clau | Tipus | Secret | Valor per defecte (env fallback) |
|---|---|---|---|
| `llm.boost.api_key` | string | **sí** | `LLM_BOOST_API_KEY` |
| `llm.boost.base_url` | string | no | `LLM_BOOST_BASE_URL` |
| `llm.boost.model_name` | string | no | `LLM_BOOST_MODEL_NAME` |

### Grup `llm` (LLM embed — Graphiti)

| Clau | Tipus | Secret | Valor per defecte (env fallback) |
|---|---|---|---|
| `llm.embed.api_key` | string | **sí** | `LLM_EMBED_API_KEY` |
| `llm.embed.base_url` | string | no | `LLM_EMBED_BASE_URL` |
| `llm.embed.model_name` | string | no | `LLM_EMBED_MODEL_NAME` |

### Grup `llm` (LLM small — Graphiti)

| Clau | Tipus | Secret | Valor per defecte (env fallback) |
|---|---|---|---|
| `llm.small.api_key` | string | **sí** | `LLM_SMALL_API_KEY` |
| `llm.small.base_url` | string | no | `LLM_SMALL_BASE_URL` |
| `llm.small.model_name` | string | no | `LLM_SMALL_MODEL_NAME` |

### Grup `simulation`

| Clau | Tipus | Secret | Valor per defecte (env fallback) |
|---|---|---|---|
| `simulation.max_rounds` | int | no | `OASIS_DEFAULT_MAX_ROUNDS` (10) |

### Grup `report`

| Clau | Tipus | Secret | Valor per defecte (env fallback) |
|---|---|---|---|
| `report.max_tool_calls` | int | no | `REPORT_AGENT_MAX_TOOL_CALLS` (5) |
| `report.max_reflection_rounds` | int | no | `REPORT_AGENT_MAX_REFLECTION_ROUNDS` (2) |
| `report.temperature` | float | no | `REPORT_AGENT_TEMPERATURE` (0.5) |

### Grup `email`

| Clau | Tipus | Secret | Valor per defecte (env fallback) |
|---|---|---|---|
| `acs.sender_display_name` | string | no | `ACS_SENDER_DISPLAY_NAME` ("MiroFish") |

### Grup `limits` (ja existent)

| Clau | Tipus | Secret | Valor per defecte |
|---|---|---|---|
| `limits.max_projects_per_user` | int | no | 20 |
| `limits.max_simulations` | int | no | 10 |

---

## Backend: helper `get_config`

**Fitxer nou:** `backend/app/config_db.py`

```python
def get_config(key: str, default=None):
    """Llegeix una clau de system_config; fallback a default si no hi ha valor a BD."""
```

- Obre sessió BD, fa `db.get(SystemConfigModel, key)`
- Si existeix i `value` no és `None` → casteja a `value_type` (`int`, `float`, `bool`, `string`) i retorna
- Si no existeix o `value` és `None` → retorna `default`
- No llança excepcions: si la BD no és accessible, retorna `default`

**Punts de consum a actualitzar:**

| Fitxer | Clau BD | Default (Config.*) |
|---|---|---|
| `services/simulation_runner.py` | `simulation.max_rounds` | `Config.OASIS_DEFAULT_MAX_ROUNDS` |
| `services/report_agent.py` | `report.max_tool_calls` | `Config.REPORT_AGENT_MAX_TOOL_CALLS` |
| `services/report_agent.py` | `report.max_reflection_rounds` | `Config.REPORT_AGENT_MAX_REFLECTION_ROUNDS` |
| `services/report_agent.py` | `report.temperature` | `Config.REPORT_AGENT_TEMPERATURE` |
| Qualsevol lloc que llegeixi `Config.LLM_*` per construir clients LLM | `llm.*` | `Config.LLM_*` |

Els serveis de graf (Graphiti) i el constructor de clients LLM llegiran les claus `llm.embed.*`, `llm.small.*`, `llm.boost.*` via `get_config`.

---

## Backend: API `/api/admin/config`

### GET `/api/admin/config`

Resposta per a claus normals:
```json
{ "key": "simulation.max_rounds", "value": "10", "value_type": "int",
  "group": "simulation", "label": "...", "is_secret": false }
```

Resposta per a claus secretes — **el valor mai surt del backend**:
```json
{ "key": "llm.api_key", "value": null, "has_value": true,
  "value_type": "string", "group": "llm", "label": "...", "is_secret": true }
```

`has_value` és `true` si `entry.value` no és `None` i no és `""`.

### PATCH `/api/admin/config`

```json
{ "llm.model_name": "gpt-4o", "llm.api_key": "sk-..." }
```

Regles:
- Si la clau no existeix a BD → ignorar (no crear claus noves des de la UI)
- Si `is_secret=True` i el valor rebut és `""` o `None` → ignorar (no esborrar secrets)
- Qualsevol altre cas → actualitzar `entry.value`

---

## Frontend: UI de configuració

**Agrupació per `group`** amb capçalera de secció. Ordre de grups: `llm` → `simulation` → `report` → `email` → `limits`.

**Camps normals:** `<input type="text">` amb el valor actual.

**Camps secrets (`is_secret=true`):**
- `<input type="password">` sempre buit inicialment
- Placeholder: `"(ja configurat)"` si `has_value=true`, `"(no configurat)"` si `has_value=false`
- L'usuari escriu per canviar; si no escriu res, no s'inclou al PATCH

**Lògica de PATCH al frontend:**
```js
// Pel PATCH, per a cada clau:
// - No secreta: sempre incloure si ha canviat (o sempre)
// - Secreta: incloure NOMÉS si el camp no és buit
const payload = {}
for (const entry of configEntries) {
  if (entry.is_secret) {
    const v = secretInputs[entry.key]
    if (v && v !== '') payload[entry.key] = v
  } else {
    payload[entry.key] = configValues[entry.key]
  }
}
```

**Subgrups LLM:** Els LLMs boost/embed/small es mostren col·lapsats per defecte sota "LLM secundaris" amb un botó per expandir, per no sobrecarregar la vista.

---

## `init_system.py`: inicialització de les claus noves

S'afegiran totes les claus noves amb els seus valors per defecte llegits de `Config.*`. La lògica actual ja és "inserir si no existeix" (`if not existing: db.add(...)`), cosa que preserva valors ja configurats.

---

## Fora d'abast

- Variables de persistència: `DATABASE_URL`, `STORAGE_TYPE`, `AZURE_STORAGE_*`, `NEO4J_*`, `ZEP_API_KEY` → continuen sent només d'entorn (requereixen reinici)
- Tokens JWT, `ACS_ENDPOINT`, `ACS_ACCESS_KEY`, `ACS_SENDER_ADDRESS` → continuen sent només d'entorn
- `ADMIN_EMAIL`, `ADMIN_PASSWORD` → només per a `init_system.py`
- No es creen claus noves des de la UI (només s'editen les existents)
