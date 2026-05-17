# Fase 3: Rols i Administració — Disseny

**Data:** 2026-05-15
**Branca:** `feature/fase3-roles-admin`
**Estat:** Aprovat per implementació

## Context

MiroFish funciona ara com a aplicació d'un sol usuari amb login demo hardcoded (`username: demo`). La Fase 3 transforma la plataforma en un sistema multi-usuari administrable, requisit per al pilot GenCat. Els models de BD (`UserModel`, `InvitationTokenModel`, `PasswordResetTokenModel`, `SystemConfigModel`) ja existeixen a `backend/app/models/db_models.py`; el treball és implementar els endpoints, la lògica d'autenticació real, l'aïllament de projectes per usuari, i el frontend complet.

L'entrega és un PR únic des de la branca `feature/fase3-roles-admin` cap a `main`.

## Decisions de disseny

- **Enrollment:** Només per invitació d'admin (no registre públic) — adequat per pilot tancat
- **Emails:** Azure Communication Services (ACS), consistent amb l'stack Azure i el roadmap Fase 4
- **Home.vue:** Redissenyat com a dashboard de projectes minimalista (eliminar hero section i textos de màrqueting)
- **Projectes orfes:** Assignar a l'admin inicial via migració Alembic
- **Sessions:** JWT access token (8h) + refresh token cookie httpOnly (7 dies)

---

## 1. Arquitectura general

### Fitxers afectats

```
Backend (nous):
  backend/app/api/users.py              CRUD admin d'usuaris
  backend/app/api/admin.py              Paràmetres sistema + historial global
  backend/app/services/auth_service.py  Lògica auth (login, tokens, invitació, reset)
  backend/app/services/email_service.py Enviament via ACS
  alembic/versions/xxxx_fase3_user_isolation.py

Backend (modificats):
  backend/app/api/auth.py               Reescriptura completa (eliminar demo)
  backend/app/api/graph.py              Filtrar projectes per user_id
  backend/app/__init__.py               Afegir decoradors @require_admin, @require_project_owner

Frontend (nous):
  frontend/src/views/SetPasswordView.vue      Acceptar invitació / establir contrasenya
  frontend/src/views/ForgotPasswordView.vue   Forgot password
  frontend/src/views/ResetPasswordView.vue    Reset password
  frontend/src/views/AdminView.vue            Panel admin (3 pestanyes)

Frontend (modificats):
  frontend/src/views/LoginView.vue       Refactoritzar (ara és stub)
  frontend/src/views/Home.vue            Redisseny complet com a dashboard
  frontend/src/router/index.js           Noves rutes + guard de rol admin
  frontend/src/store/auth.js             Ampliar: guardar user.role, user.id
```

### Sessions i tokens

- `flask-jwt-extended`: access token Bearer (8h) + refresh token cookie httpOnly (7 dies)
- Frontend guarda access token a `localStorage` (consistent amb codi actual)
- `POST /api/auth/refresh` renova sense re-login

---

## 2. Endpoints d'autenticació

### `backend/app/api/auth.py` (reescriptura)

```
POST /api/auth/login
  Body: { email, password }
  → JWT access token (8h) + refresh cookie (7d)
  → Timing-safe: sempre fa bcrypt.compare
  → Rate limit: 10 intents / 15 min per IP

POST /api/auth/refresh
  Cookie: refresh_token
  → Nou access token

POST /api/auth/logout
  → Esborra refresh cookie

GET  /api/auth/me                        [auth required]
  → { id, email, role, status }

POST /api/auth/forgot-password
  Body: { email }
  → Sempre 202 (anti-enumeració)
  → Token UUID (TTL: 1h), envia email ACS

GET  /api/auth/reset-password/<token>
  → Valida token, retorna { email } o 404

POST /api/auth/reset-password
  Body: { token, password }
  → Actualitza hash, marca token usat, invalida sessions

GET  /api/auth/invitation/<token>
  → Valida token, retorna { email, name } o 404

POST /api/auth/set-password
  Body: { token, password }
  → Estableix contrasenya, activa user (pending → active), marca token usat
```

### `backend/app/api/users.py` (nou, només admin)

```
GET    /api/users?page=1&pageSize=20     [@require_admin]
POST   /api/users                        [@require_admin]
  Body: { email, name, role? }
  → Crea user (status=pending), genera invitació, envia email ACS

GET    /api/users/<id>                   [@require_admin]
PATCH  /api/users/<id>                   [@require_admin]
  → Pot canviar: name, role, status

DELETE /api/users/<id>                   [@require_admin]  soft: status=disabled
DELETE /api/users/<id>/purge             [@require_admin]  hard: cascada projectes+fitxers
POST   /api/users/<id>/reinvite          [@require_admin]  reenviar email a pending
```

### `backend/app/api/admin.py` (nou, només admin)

```
GET   /api/admin/config                  [@require_admin]
PATCH /api/admin/config                  [@require_admin]
  → Llegir/escriure SystemConfigModel

GET   /api/admin/executions              [@require_admin]
  Query: ?user_id=&page=&pageSize=
  → Historial global de simulacions
```

### Decoradors nous a `backend/app/__init__.py`

```python
@require_auth          # JWT vàlid (ja existeix)
@require_admin         # role == "admin"
@require_project_owner # project.user_id == current_user.id (o admin)
```

---

## 3. Frontend: vistes i routing

### Rutes noves/modificades a `frontend/src/router/index.js`

```javascript
// Públiques
/login                    → LoginView.vue
/forgot-password          → ForgotPasswordView.vue
/reset-password/:token    → ResetPasswordView.vue
/accept-invite/:token     → SetPasswordView.vue

// Privades (sense canvis de ruta)
/                         → Home.vue  (refactoritzat)
/process/:projectId       → MainView.vue
/simulation/:simId/start  → SimulationRunView.vue
/report/:reportId         → ReportView.vue
/interaction/:reportId    → InteractionView.vue

// Admin only
/admin                    → AdminView.vue (redirect a /admin/users)
/admin/users              → AdminView.vue (pestanya Usuaris)
/admin/config             → AdminView.vue (pestanya Configuració)
/admin/executions         → AdminView.vue (pestanya Historial)
```

Guard del router:
```javascript
router.beforeEach((to, from) => {
  if (to.meta.requiresAuth && !auth.isAuthenticated) return '/login'
  if (to.meta.requiresAdmin && auth.user.role !== 'admin') return '/'
})
```

### `frontend/src/store/auth.js` (ampliar)

```javascript
state = reactive({
  token: localStorage.getItem('mirofish_token'),
  user: JSON.parse(localStorage.getItem('mirofish_user') || 'null'),
  // user: { id, email, role, status }
})
const isAdmin = computed(() => state.user?.role === 'admin')
```

### Vistes noves/modificades

**`LoginView.vue`** — formulari email + password, enllaç forgot-password, missatge contextual si ve de accept-invite

**`ForgotPasswordView.vue`** — camp email, UI anti-enumeració (sempre mostra "comprova el correu")

**`ResetPasswordView.vue`** — verifica token, formulari nova contrasenya (≥8 chars + confirmació), redirigeix a /login en èxit

**`SetPasswordView.vue`** — verifica token invitació, mostra "Benvingut/da {name}", formulari contrasenya, redirigeix a /login?activated=1

**`Home.vue`** — redisseny complet:
- Eliminar: hero section, textos de màrqueting, mètriques, llista de passos, HistoryDatabase, link GitHub, scroll button
- Conservar: navbar negra, paleta (negre/blanc/taronja), fonts JetBrains Mono + Space Grotesk
- Navbar ampliada: afegir email usuari + botó logout + "Administració" (només admin)
- Dashboard de projectes: llistat de files (nom, data, status, →), menú contextual per fila (editar nom, eliminar)
- Botó "Nou projecte": obre modal amb el console-box actual (reutilitza lògica pendingUpload)
- Estat buit: "Cap projecte. Crea'n un de nou."
- Eliminar component HistoryDatabase del Home

**`AdminView.vue`** — 3 pestanyes:
- *Usuaris:* taula (email, nom, rol, status, data), formulari invitació ràpida, accions per fila
- *Configuració:* formulari dinàmic des de SystemConfigModel, camps is_secret emmascats
- *Historial:* taula global simulacions, filtre per usuari, paginació

---

## 4. Migració de dades i inicialització

### Migració Alembic

```python
# alembic/versions/xxxx_fase3_user_isolation.py
# 1. Crear taules Fase 3 si no existeixen
# 2. Assignar projectes orfes a l'admin inicial
UPDATE projects SET user_id = (
  SELECT id FROM users WHERE role = 'admin' ORDER BY created_at LIMIT 1
) WHERE user_id IS NULL
# 3. Fer user_id NOT NULL a projects
```

### Inicialització del sistema

Nou comando `flask init-system` (o `backend/scripts/init_system.py`):
1. Crea primer admin si no existeix cap usuari (llegeix `ADMIN_EMAIL` + `ADMIN_PASSWORD` de .env)
2. Insereix valors per defecte a `SystemConfigModel` des de variables d'entorn
3. Verifica migració Alembic al dia

### Variables d'entorn noves a `.env.example`

```bash
# Auth
JWT_SECRET_KEY=change-me-in-production
JWT_ACCESS_TOKEN_EXPIRES=28800        # 8h
JWT_REFRESH_TOKEN_EXPIRES=604800      # 7d

# Admin inicial
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=change-me

# Azure Communication Services
ACS_CONNECTION_STRING=
ACS_SENDER_ADDRESS=donotreply@example.com
ACS_INVITATION_TTL_HOURS=48
ACS_RESET_PASSWORD_TTL_HOURS=1
```

---

## 5. Verificació i criteris d'acceptació

### Tests pytest

```
tests/test_auth.py
  ✓ login correcte retorna JWT
  ✓ login incorrecte retorna 401 (timing-safe)
  ✓ forgot-password retorna 202 sempre
  ✓ reset-password amb token vàlid actualitza contrasenya
  ✓ reset-password amb token expirat retorna 404
  ✓ invitation flow complet: crear → set-password → login

tests/test_users_admin.py
  ✓ GET /api/users requereix rol admin
  ✓ POST /api/users crea user pending + token invitació
  ✓ PATCH /api/users/:id canvia rol/status
  ✓ DELETE /api/users/:id/purge elimina en cascada

tests/test_project_isolation.py
  ✓ GET /api/graph/projects retorna només projectes propis
  ✓ GET /api/graph/project/:id retorna 403 si no és propietari
  ✓ Admin pot veure projectes de qualsevol usuari
```

### Golden path manual

```
Flux admin:
  □ flask init-system en entorn net
  □ Login admin → Home buit → navbar mostra "Administració"
  □ Crear usuari des de panel → email ACS enviat
  □ Acceptar invitació → establir contrasenya → login
  □ Nou usuari no veu projectes de l'admin
  □ Admin veu tot a /admin/executions

Flux usuari normal:
  □ Login → Home amb els seus projectes
  □ "Nou projecte" → modal → crear → navega a MainView
  □ Editar nom de projecte
  □ Eliminar projecte (demana confirmació)
  □ Forgot-password → email → reset → login

Flux seguretat:
  □ Token expirat → redirigeix a /login
  □ /admin sense rol admin → redirigeix a /
  □ GET /api/graph/project/:id d'un altre usuari → 403
```

### Criteris d'acceptació del PR

- Tots els tests pytest passen
- Login demo (`username: demo`) ja no funciona
- Cap ruta retorna projectes d'altres usuaris (excepte admin)
- `flask init-system` funciona en entorn net
- `.env.example` documentat amb les noves variables

---

## 6. Desplegament Azure

Els tres fitxers de desplegament cal actualitzar-los com a part de la Fase 3.

### `azure/config.sh.example`

- **Eliminar** `DEMO_PASSWORD` (el login demo desapareix)
- **Eliminar** `SECRET_KEY` → substituir pel bloc JWT explícit:

```bash
# ── Auth JWT ──────────────────────────────────────────────────────────────────
# Genera JWT_SECRET_KEY amb: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY="<clau-secreta-jwt>"
JWT_ACCESS_TOKEN_EXPIRES=28800        # 8h en segons
JWT_REFRESH_TOKEN_EXPIRES=604800      # 7d en segons

# ── Admin inicial (per flask init-system) ─────────────────────────────────────
ADMIN_EMAIL="admin@example.com"
ADMIN_PASSWORD="<contrasenya-segura>"

# ── Azure Communication Services (emails d'invitació i reset) ────────────────
# ACS_CONNECTION_STRING és opcional en dev (els links es mostren als logs)
ACS_CONNECTION_STRING="<output-de-1-infra.sh>"
ACS_SENDER_ADDRESS="donotreply@<domini>"
ACS_INVITATION_TTL_HOURS=48
ACS_RESET_PASSWORD_TTL_HOURS=1
```

### `azure/container-app.bicep`

**Paràmetres eliminats:**
- `demoPassword` (i les seves referències a `mandatorySecrets` i `mandatoryEnv`)
- `secretKey` → renombrat a `jwtSecretKey`

**Paràmetres nous `@secure()`:**
- `jwtSecretKey` (obligatori)
- `adminPassword` (obligatori)
- `acsConnectionString` (opcional, default `''`)

**Paràmetres nous no secrets:**
- `adminEmail` (string, obligatori)
- `acsSenderAddress` (string, default `''`)
- `acsInvitationTtlHours` (string, default `'48'`)
- `acsResetPasswordTtlHours` (string, default `'1'`)
- `jwtAccessTokenExpires` (string, default `'28800'`)
- `jwtRefreshTokenExpires` (string, default `'604800'`)

**Canvis a `mandatorySecrets`:** substituir `demo-password` i `secret-key` per `jwt-secret-key` i `admin-password`.

**Canvis a `optionalSecrets`:** afegir `acs-connection-string` si no buit.

**Canvis a `mandatoryEnv`:** substituir `DEMO_PASSWORD` i `SECRET_KEY` per:
```
JWT_SECRET_KEY       → secretRef: 'jwt-secret-key'
ADMIN_EMAIL          → value: adminEmail
ADMIN_PASSWORD       → secretRef: 'admin-password'
JWT_ACCESS_TOKEN_EXPIRES  → value: jwtAccessTokenExpires
JWT_REFRESH_TOKEN_EXPIRES → value: jwtRefreshTokenExpires
```

**Canvis a `optionalEnv`:** afegir:
```
ACS_CONNECTION_STRING     → secretRef: 'acs-connection-string'  (si no buit)
ACS_SENDER_ADDRESS        → value: acsSenderAddress              (si no buit)
ACS_INVITATION_TTL_HOURS  → value: acsInvitationTtlHours        (si no buit)
ACS_RESET_PASSWORD_TTL_HOURS → value: acsResetPasswordTtlHours  (si no buit)
```

### `azure/2-build-deploy.sh`

**`REQUIRED_VARS`:** eliminar `DEMO_PASSWORD`; afegir `JWT_SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`.

**Validació nova** (avís, no error — ACS és opcional en dev):
```bash
if [[ -z "${ACS_CONNECTION_STRING:-}" ]]; then
  echo "AVÍS: ACS_CONNECTION_STRING no configurat — els emails d'invitació es mostraran als logs"
fi
```

**`--parameters` del `az deployment group create`:** eliminar `demoPassword`; afegir:
```bash
jwtSecretKey="$JWT_SECRET_KEY" \
adminEmail="$ADMIN_EMAIL" \
adminPassword="$ADMIN_PASSWORD" \
acsConnectionString="${ACS_CONNECTION_STRING:-}" \
acsSenderAddress="${ACS_SENDER_ADDRESS:-}" \
acsInvitationTtlHours="${ACS_INVITATION_TTL_HOURS:-48}" \
acsResetPasswordTtlHours="${ACS_RESET_PASSWORD_TTL_HOURS:-1}" \
jwtAccessTokenExpires="${JWT_ACCESS_TOKEN_EXPIRES:-28800}" \
jwtRefreshTokenExpires="${JWT_REFRESH_TOKEN_EXPIRES:-604800}" \
```
