# Technical Design — MiroFish

## Graph Backend

MiroFish suporta dos backends de knowledge graph, seleccionable via `GRAPH_BACKEND` al `.env`:

| Valor | Backend | Requisits |
|-------|---------|-----------|
| `zep` (per defecte) | Zep Cloud (gestionat) | `ZEP_API_KEY` |
| `graphiti` | Graphiti + Neo4j (self-hosted) | `NEO4J_PASSWORD` + variables LLM |

La selecció es fa via la factoria `backend/app/graph/factory.py` — un singleton que instancia `ZepBackend` o `GraphitiBackend` en funció de `GRAPH_BACKEND`. La validació de configuració és condicionada: si `GRAPH_BACKEND=graphiti`, `ZEP_API_KEY` no és necessari i viceversa.

### Commutació entre backends

Només cal canviar al `.env`:

```env
# Per usar Zep Cloud:
GRAPH_BACKEND=zep
ZEP_API_KEY=z_...

# Per usar Graphiti + Neo4j:
GRAPH_BACKEND=graphiti
NEO4J_URI=bolt://<host>:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<contrasenya>
```

---

## Models LLM

El projecte usa fins a quatre grups de variables LLM, cadascun per a un ús diferent. Totes les variables `LLM_SMALL_*` i `LLM_EMBED_*` fan **fallback** als valors `LLM_*` si no s'estableixen.

### Variables de configuració

```env
# ── Model principal (generatiu, potent) ──────────────────────────────────────
LLM_API_KEY=...
LLM_BASE_URL=https://...
LLM_MODEL_NAME=gpt-4o

# ── Proveïdor Gemini (opcional) ──────────────────────────────────────────────
# LLM_PROVIDER=gemini  → configura automàticament l'endpoint de Google AI Studio

# ── Model petit/ràpid (lightweight, econòmic) ────────────────────────────────
# Fallback a LLM_* si no definit
LLM_SMALL_API_KEY=...
LLM_SMALL_BASE_URL=...
LLM_SMALL_MODEL_NAME=gpt-4o-mini

# ── Model d'embedding (vectorització) ────────────────────────────────────────
# Fallback a LLM_* si no definit. Requerit per Graphiti.
LLM_EMBED_API_KEY=...
LLM_EMBED_BASE_URL=...
LLM_EMBED_MODEL_NAME=text-embedding-3-large

# ── Model boost (simulació OASIS, opcional) ──────────────────────────────────
# Fallback a LLM_* si no definit
LLM_BOOST_API_KEY=...
LLM_BOOST_BASE_URL=...
LLM_BOOST_MODEL_NAME=...
```

### Mapa d'usos per operació

| Grup de variables | Component | Operació |
|---|---|---|
| `LLM_*` | `OntologyGenerator` | Pas 1 — Anàlisi del document i generació d'ontologia |
| `LLM_*` | `GraphBuilderService` (mode Zep) | Pas 1 — Extracció d'entitats i relacions via Zep SDK |
| `LLM_*` | Graphiti `OpenAIGenericClient` (mode graphiti) | Pas 1 — Extracció d'entitats via graphiti-core |
| `LLM_*` | `OasisProfileGenerator` | Pas 2 — Generació de perfils d'agents OASIS |
| `LLM_*` | `ReportAgent` | Pas 4 — Generació de l'informe analític (multi-turn, tool use) |
| `LLM_SMALL_*` | Graphiti `OpenAIRerankerClient` | Pas 1 — Reranking de resultats de cerca (mode graphiti) |
| `LLM_SMALL_*` | Graphiti `ModelSize.small` | Pas 1 — Tasques lleugeres internes de graphiti |
| `LLM_EMBED_*` | Graphiti `OpenAIEmbedder` | Pas 1 — Vectors d'embedding per a Neo4j (mode graphiti) |
| `LLM_BOOST_*` | `SimulationRunner` / `run_parallel_simulation.py` | Pas 3 — Decisions d'acció de cada agent durant la simulació |

### API endpoint usada per cada component

| Component | API endpoint | Nota |
|---|---|---|
| `LLMClient` (wrapper projecte) | `chat.completions.create` | Síncrona (`OpenAI`) |
| `OntologyGenerator` | `chat.completions.create` | Via `LLMClient` |
| `OasisProfileGenerator` | `chat.completions.create` | Client intern |
| `SimulationConfigGenerator` | `chat.completions.create` | Client intern |
| `ReportAgent` | `chat.completions.create` | Via `LLMClient` |
| Graphiti `OpenAIGenericClient` | `chat.completions.create` | AsyncOpenAI, injectable |
| Graphiti `OpenAIRerankerClient` | `chat.completions.create` | Amb `logprobs=True` per scoring |
| Graphiti `OpenAIEmbedder` | `embeddings.create` | AsyncOpenAI, injectable |
| OASIS/CAMEL-AI | `chat.completions.create` | Via `ModelFactory` (CAMEL abstraction) |

> **Nota:** graphiti-core inclou també un `OpenAIClient` que usa `responses.parse` (API beta d'OpenAI). MiroFish **no l'usa** — configura `OpenAIGenericClient` que sempre usa `chat.completions`, compatible amb Azure i qualsevol API OpenAI-compatible.

### Notes sobre Azure OpenAI

- `LLM_BASE_URL` accepta la URL completa d'Azure (`/chat/completions?api-version=...`). El codi la processa automàticament: extreu el `api-version` com a `default_query` i retalla el sufix per al SDK.
- El mateix tractament s'aplica a `LLM_EMBED_BASE_URL` (sufix `/embeddings?api-version=...`).
- `LLM_SMALL_BASE_URL` accepta directament la URL base d'Azure AI Foundry sense sufix ni `api-version`.

---

## Pipeline de 5 passos

```
Pas 1 — Graph Build (ontologia + construcció)
  ├─ OntologyGenerator           →  LLM_*
  ├─ mode zep:   GraphBuilderService + Zep SDK  →  LLM_*
  └─ mode graphiti: GraphitiBackend
       ├─ extracció:   OpenAIGenericClient   →  LLM_*
       ├─ reranking:   OpenAIRerankerClient  →  LLM_SMALL_*
       └─ embedding:   OpenAIEmbedder        →  LLM_EMBED_*

Pas 2 — Environment Setup (agents)
  ├─ OasisProfileGenerator       →  LLM_*  (perfils individuals del graf)
  └─ SimulationConfigGenerator   →  LLM_*  (comportament per batch de 15)

Pas 3 — Simulació OASIS
  └─ SimulationRunner / run_parallel_simulation.py  →  LLM_BOOST_* (o LLM_*)

Pas 4 — Informe
  └─ ReportAgent (multi-turn + tool use)  →  LLM_*

Pas 5 — Interacció live
  └─ Chat amb agents simulats  →  LLM_*
```

---

## Generació d'agents (Pas 2)

Els agents reben un `stance` (actitud) que determina el seu posicionament respecte al tema de la simulació:

| Valor | Significat |
|-------|-----------|
| `supportive` | A favor del tema principal |
| `opposing` | En contra del tema principal |
| `neutral` | Sense posició definida |
| `observer` | Observador passiu (típic per a media) |

**No hi ha balanceig per percentatge.** El LLM decideix el stance de cada agent en funció del context de l'entitat (tipus, resum, atributs). Els guidelines del prompt estableixen `neutral` per defecte per a institucions, individus i experts; `observer` per a outlets de media. Si el LLM falla, un fallback rule-based assigna `neutral` o `observer` per tipus d'entitat.

---

## Autenticació i Autorització

- **Framework**: `flask-jwt-extended`
- **Tokens**: Access (8h) + Refresh (7d), transmesos com `Authorization: Bearer <token>`
- **Rols**: `admin` (accés total) i `user` (accés als seus propis projectes)
- **Estatus d'usuari**: `pending` → `active` → `disabled`
- **Decoradors**: `@require_admin` (admin only), `@require_project_owner` (propietari o admin)
- **Rutes públiques**: `/health`, `/api/auth/login`, `/api/auth/forgot-password`, `/api/auth/reset-password`, `/api/auth/set-password`, `/api/auth/invitation/*`

### Flux d'invitació

```
Admin crea usuari (POST /api/users/)
  → es genera InvitationToken (TTL: 48h per defecte)
  → s'envia email amb link via Azure Communication Services
  → usuari fa clic → GET /api/auth/invitation/<token>
  → usuari estableix contrasenya → POST /api/auth/set-password
  → estatus canvia pending → active
```

---

## Models de dades (SQLAlchemy)

| Model | Taula | Camps clau |
|-------|-------|-----------|
| `UserModel` | users | id, email, name, password_hash, role, status |
| `ProjectModel` | projects | id, user_id, name, status, active_task_id |
| `ProjectFileModel` | project_files | id, project_id, original_name, storage_path |
| `OntologyModel` | ontologies | id, project_id, version, entity_types, edge_types |
| `GraphModel` | graphs | id, project_id, ontology_id, backend, external_id, status |
| `SimulationModel` | simulations | id, project_id, graph_id, status, platform, config, rounds_total |
| `ReportModel` | reports | id, project_id, simulation_id, status, outline, storage_prefix |
| `TaskModel` | tasks | id, task_type, entity_id, status, progress, message, result |
| `SystemConfigModel` | system_config | key, value, value_type, group, label, is_secret |
| `InvitationTokenModel` | invitation_tokens | token, user_id, expires_at, used_at |
| `PasswordResetTokenModel` | password_reset_tokens | token, user_id, expires_at, used_at |

**Base de dades**: SQLite per defecte (`sqlite:///mirofish_dev.db`). Configurable via `DATABASE_URL`. Migracions gestionades amb Alembic.

---

## Storage

| Tipus | Descripció | Variables |
|-------|-----------|-----------|
| `local` (per defecte) | Sistema de fitxers local | `STORAGE_LOCAL_PATH` (default: `backend/uploads`) |
| `azure` | Azure Blob Storage | `AZURE_STORAGE_CONNECTION_STRING`, `AZURE_STORAGE_CONTAINER` |

---

## Internacionalització (i18n)

- Fitxers de traducció: `/locales/{ca,en,es}.json` — compartits per frontend i backend.
- Instruccions de llengua per al LLM: `/locales/languages.json` (clau `llmInstruction`).
- El frontend injecta el locale actual via header `Accept-Language` a cada petició API.
- El backend detecta el locale a `backend/app/utils/locale.py:get_locale()` i l'usa per:
  - Traduccions de missatges d'error (`t()`)
  - Instruccions d'idioma als prompts LLM (`get_language_instruction()`)
- L'ontologia generada sortirà en l'idioma de la UI. Els **noms** de tipus d'entitat i relació seguiran PascalCase/UPPER\_SNAKE\_CASE (p.ex. `AgenciaGovern`, `TREBALLA_PER` en català).

---

## Inicialització del sistema

El primer cop que s'instal·la el sistema cal executar:

```bash
ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=secret \
  uv run python backend/scripts/init_system.py
```

Aquest script:
1. Connecta a la BD (`DATABASE_URL`)
2. Executa les migracions Alembic (`alembic upgrade head`)
3. Crea l'usuari admin inicial si no existeix

En producció, `ADMIN_EMAIL` i `ADMIN_PASSWORD` s'estableixen al `.env`.
