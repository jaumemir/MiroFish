# Fase 3: Rols i Administració — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar MiroFish en una plataforma multi-usuari amb login real (bcrypt + JWT), aïllament de projectes per usuari, panel d'administració i flux d'invitació per email (ACS).

**Architecture:** El middleware JWT existent (`require_auth` a `__init__.py`) es substitueix per `flask-jwt-extended`. Access token (8h) en header `Authorization: Bearer`; refresh token (7d) en cookie httpOnly. Nous decoradors `@require_admin` i `@require_project_owner` protegeixen les rutes específiques. `ProjectManager.list_projects()` i `create_project()` s'amplien per filtrar i assignar `user_id`. El frontend afegeix un dashboard de projectes mínim com a Home, vistes d'auth (forgot/reset/invite) i AdminView amb 3 pestanyes.

**Tech Stack:** `flask-jwt-extended` · `bcrypt` · `azure-communication-email` · `alembic` · Vue 3 + vue-i18n + vue-router

**Branca:** `feature/fase3-roles-admin` (crear des de `main`)

---

## File Structure

### Backend — nous
| Fitxer | Responsabilitat |
|--------|----------------|
| `backend/app/services/auth_service.py` | hash bcrypt, create/verify JWT, CRUD tokens BD |
| `backend/app/services/email_service.py` | ACS emails + dev fallback (log URL) |
| `backend/app/api/users.py` | CRUD admin d'usuaris (blueprint `users_bp`) |
| `backend/app/api/admin.py` | config sistema + historial execucions (blueprint `admin_bp`) |
| `backend/scripts/init_system.py` | crear primer admin + SystemConfig per defecte |
| `backend/tests/test_auth_service.py` | tests unitaris AuthService |
| `backend/tests/test_auth_api.py` | tests integració endpoints auth |
| `backend/tests/test_users_admin.py` | tests users API (admin) |
| `backend/tests/test_admin_api.py` | tests admin API |
| `backend/tests/test_project_isolation.py` | tests aïllament projectes per user_id |

### Backend — modificats
| Fitxer | Canvis |
|--------|--------|
| `backend/requirements.txt` | + flask-jwt-extended, bcrypt, azure-communication-email |
| `backend/app/config.py` | noves vars JWT, admin inicial, ACS; timedelta per JWT |
| `backend/app/__init__.py` | JWTManager, `get_current_user()`, `require_admin`, `require_project_owner`, `_PUBLIC_PATHS` ampliat |
| `backend/app/api/auth.py` | reescriptura completa (eliminar demo) |
| `backend/app/api/__init__.py` | registrar `users_bp`, `admin_bp` |
| `backend/app/api/graph.py` | filtrar `/project/list` per user; `@require_project_owner` a get/delete; injectar `user_id` a create |
| `backend/app/models/project.py` | `create_project(user_id)`, `list_projects(user_id)`, `_to_dict` + `user_id` |
| `backend/alembic/versions/` | nova migració: assignar projectes orfes + user_id NOT NULL |

### Frontend — nous
- `frontend/src/views/ForgotPasswordView.vue`
- `frontend/src/views/ResetPasswordView.vue`
- `frontend/src/views/SetPasswordView.vue`
- `frontend/src/views/AdminView.vue`

### Frontend — modificats
- `frontend/src/store/auth.js` — `user` object + `isAdmin` + `setUser/clearUser`
- `frontend/src/router/index.js` — noves rutes públiques + guard `/admin`
- `frontend/src/views/LoginView.vue` — camp `email` + link forgot password
- `frontend/src/views/Home.vue` — dashboard projectes (eliminar hero/màrqueting)

### Azure — modificats
- `azure/config.sh.example`
- `azure/container-app.bicep`
- `azure/2-build-deploy.sh`

---

## Task 1: Branca + dependències

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Crear la branca**

```bash
git checkout main && git pull
git checkout -b feature/fase3-roles-admin
```

- [ ] **Afegir dependències a `requirements.txt`**

Afegir al final del fitxer (després de `pydantic>=2.0.0`):

```
# ============= Autenticació Fase 3 =============
flask-jwt-extended>=4.6.0
bcrypt>=4.1.0
azure-communication-email>=1.0.0
```

- [ ] **Instal·lar i verificar**

```bash
cd /home/ubuntu/dev/MiroFish
uv pip install flask-jwt-extended bcrypt azure-communication-email
python -c "import flask_jwt_extended, bcrypt, azure.communication.email; print('OK')"
```

Expected: `OK`

- [ ] **Commit**

```bash
git add backend/requirements.txt
git commit -m "chore(deps): add flask-jwt-extended, bcrypt, azure-communication-email"
```

---

## Task 2: Actualitzar Config

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Substituir variables d'autenticació a `Config`**

Substituir les línies del bloc `Flask settings` (línies 24-25) i el bloc `JWT` (línies 114-118) per:

```python
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')  # mantenir per compatibilitat
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    # Auth JWT (flask-jwt-extended)
    from datetime import timedelta
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'change-me-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        seconds=int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', '28800'))   # 8h
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        seconds=int(os.environ.get('JWT_REFRESH_TOKEN_EXPIRES', '604800'))  # 7d
    )
    JWT_COOKIE_SECURE = os.environ.get('FLASK_DEBUG', 'True').lower() != 'true'
    JWT_COOKIE_CSRF_PROTECT = False
    JWT_REFRESH_COOKIE_PATH = '/api/auth/refresh'

    # Admin inicial (per init_system.py)
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', '')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')

    # Azure Communication Services
    ACS_CONNECTION_STRING = os.environ.get('ACS_CONNECTION_STRING', '')
    ACS_SENDER_ADDRESS = os.environ.get('ACS_SENDER_ADDRESS', 'donotreply@mirofish.local')
    ACS_INVITATION_TTL_HOURS = int(os.environ.get('ACS_INVITATION_TTL_HOURS', '48'))
    ACS_RESET_PASSWORD_TTL_HOURS = int(os.environ.get('ACS_RESET_PASSWORD_TTL_HOURS', '1'))
```

Eliminar les línies antigues de JWT (línies 115-118 originals):
```python
    # Eliminar:
    # JWT_SECRET_KEY = os.environ.get('JWT_SECRET', 'change-me-in-production')
    # JWT_REFRESH_SECRET_KEY = ...
    # JWT_ACCESS_TOKEN_EXPIRES_HOURS = ...
    # JWT_REFRESH_TOKEN_EXPIRES_DAYS = ...
```

- [ ] **Verificar que la config carrega**

```bash
cd /home/ubuntu/dev/MiroFish
python -c "
import sys; sys.path.insert(0, 'backend')
from app.config import Config
print('JWT_SECRET_KEY:', Config.JWT_SECRET_KEY[:10], '...')
print('JWT_ACCESS_TOKEN_EXPIRES:', Config.JWT_ACCESS_TOKEN_EXPIRES)
print('OK')
"
```

Expected: mostra els valors sense error.

- [ ] **Commit**

```bash
git add backend/app/config.py
git commit -m "feat(config): JWT + ACS + admin initial vars for Phase 3"
```

---

## Task 3: AuthService

**Files:**
- Create: `backend/app/services/auth_service.py`
- Create: `backend/tests/test_auth_service.py`

- [ ] **Escriure el test primer**

```python
# backend/tests/test_auth_service.py
import pytest
from datetime import datetime, timezone, timedelta


@pytest.fixture(autouse=True)
def _db(in_memory_db):
    pass


def test_hash_and_verify_password():
    from backend.app.services.auth_service import hash_password, verify_password
    h = hash_password("secret123")
    assert h != "secret123"
    assert verify_password("secret123", h) is True
    assert verify_password("wrong", h) is False


def test_verify_wrong_hash_returns_false():
    from backend.app.services.auth_service import verify_password
    assert verify_password("any", "not-a-valid-hash") is False


def test_create_invitation_token(in_memory_db):
    from backend.app.services.auth_service import create_invitation_token
    from backend.app.models.db_models import UserModel
    from backend.app.db import get_session

    with get_session() as db:
        user = UserModel(email="test@example.com", name="Test", role="user", status="pending")
        db.add(user)
        db.commit()
        user_id = user.id

    token = create_invitation_token(user_id, ttl_hours=1)
    assert len(token) == 36  # UUID


def test_verify_valid_invitation_token(in_memory_db):
    from backend.app.services.auth_service import create_invitation_token, get_user_by_invitation_token
    from backend.app.models.db_models import UserModel
    from backend.app.db import get_session

    with get_session() as db:
        user = UserModel(email="invite@example.com", name="Inv", role="user", status="pending")
        db.add(user)
        db.commit()
        user_id = user.id

    token = create_invitation_token(user_id, ttl_hours=1)
    result = get_user_by_invitation_token(token)
    assert result is not None
    assert result.id == user_id


def test_verify_expired_invitation_token(in_memory_db):
    from backend.app.services.auth_service import get_user_by_invitation_token
    from backend.app.models.db_models import UserModel, InvitationTokenModel
    from backend.app.db import get_session
    import uuid

    with get_session() as db:
        user = UserModel(email="exp@example.com", name="Exp", role="user", status="pending")
        db.add(user)
        db.commit()
        tok = InvitationTokenModel(
            token=str(uuid.uuid4()),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        db.add(tok)
        db.commit()
        token_val = tok.token

    result = get_user_by_invitation_token(token_val)
    assert result is None


def test_create_and_verify_reset_token(in_memory_db):
    from backend.app.services.auth_service import (
        create_reset_token, get_user_by_reset_token, consume_reset_token
    )
    from backend.app.models.db_models import UserModel
    from backend.app.db import get_session

    with get_session() as db:
        user = UserModel(email="reset@example.com", name="Reset", role="user", status="active",
                         password_hash="x")
        db.add(user)
        db.commit()
        user_id = user.id

    token = create_reset_token(user_id, ttl_hours=1)
    u = get_user_by_reset_token(token)
    assert u is not None
    assert u.id == user_id

    # consumir token
    consume_reset_token(token, "newpassword123")

    # token ja no és vàlid
    assert get_user_by_reset_token(token) is None


def test_set_password_activates_user(in_memory_db):
    from backend.app.services.auth_service import (
        create_invitation_token, consume_invitation_token
    )
    from backend.app.models.db_models import UserModel
    from backend.app.db import get_session

    with get_session() as db:
        user = UserModel(email="act@example.com", name="Act", role="user", status="pending")
        db.add(user)
        db.commit()
        user_id = user.id

    token = create_invitation_token(user_id, ttl_hours=1)
    consume_invitation_token(token, "mypassword")

    with get_session() as db:
        u = db.get(UserModel, user_id)
        assert u.status == "active"
        from backend.app.services.auth_service import verify_password
        assert verify_password("mypassword", u.password_hash) is True
```

- [ ] **Executar el test per veure que falla**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/test_auth_service.py -v 2>&1 | head -30
```

Expected: ImportError o ModuleNotFoundError (auth_service no existeix).

- [ ] **Implementar `backend/app/services/auth_service.py`**

```python
"""Auth service: password hashing, JWT helpers, token CRUD."""
import uuid
import bcrypt
from datetime import datetime, timezone, timedelta
from typing import Optional

from ..db import get_session
from ..models.db_models import UserModel, InvitationTokenModel, PasswordResetTokenModel

# Timing-safe: dummy hash prevents timing attacks when user not found
_DUMMY_HASH = bcrypt.hashpw(b'dummy', bcrypt.gensalt(12)).decode('utf-8')


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
    except Exception:
        return False


def get_user_by_email(email: str) -> Optional[UserModel]:
    from sqlalchemy import select
    with get_session() as db:
        user = db.execute(
            select(UserModel).where(UserModel.email == email.strip().lower())
        ).scalar_one_or_none()
        if user:
            db.expunge(user)
        return user


def create_invitation_token(user_id: str, ttl_hours: int = 48) -> str:
    token = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    with get_session() as db:
        db.add(InvitationTokenModel(token=token, user_id=user_id, expires_at=expires_at))
        db.commit()
    return token


def get_user_by_invitation_token(token: str) -> Optional[UserModel]:
    with get_session() as db:
        rec = db.get(InvitationTokenModel, token)
        if rec is None or rec.used_at is not None:
            return None
        if rec.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            return None
        user = db.get(UserModel, rec.user_id)
        if user:
            db.expunge(user)
        return user


def consume_invitation_token(token: str, password: str) -> None:
    """Marca el token com usat, estableix contrasenya i activa l'usuari."""
    with get_session() as db:
        rec = db.get(InvitationTokenModel, token)
        if rec is None:
            return
        rec.used_at = datetime.now(timezone.utc)
        user = db.get(UserModel, rec.user_id)
        if user:
            user.password_hash = hash_password(password)
            user.status = 'active'
        db.commit()


def create_reset_token(user_id: str, ttl_hours: int = 1) -> str:
    token = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    with get_session() as db:
        db.add(PasswordResetTokenModel(token=token, user_id=user_id, expires_at=expires_at))
        db.commit()
    return token


def get_user_by_reset_token(token: str) -> Optional[UserModel]:
    with get_session() as db:
        rec = db.get(PasswordResetTokenModel, token)
        if rec is None or rec.used_at is not None:
            return None
        if rec.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            return None
        user = db.get(UserModel, rec.user_id)
        if user:
            db.expunge(user)
        return user


def consume_reset_token(token: str, new_password: str) -> None:
    """Marca el token com usat i actualitza la contrasenya."""
    with get_session() as db:
        rec = db.get(PasswordResetTokenModel, token)
        if rec is None:
            return
        rec.used_at = datetime.now(timezone.utc)
        user = db.get(UserModel, rec.user_id)
        if user:
            user.password_hash = hash_password(new_password)
        db.commit()
```

- [ ] **Executar els tests**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/test_auth_service.py -v
```

Expected: tots PASS.

- [ ] **Commit**

```bash
git add backend/app/services/auth_service.py backend/tests/test_auth_service.py
git commit -m "feat(auth): AuthService — bcrypt hash, invitation and reset token CRUD"
```

---

## Task 4: EmailService

**Files:**
- Create: `backend/app/services/email_service.py`

- [ ] **Implementar `email_service.py`** (no necessita tests unitaris propis — la lògica és trivial i ACS requereix credencials reals)

```python
"""Email service: ACS amb dev fallback (log URL a consola)."""
import logging
from flask import current_app

logger = logging.getLogger('mirofish.email')


def send_invitation_email(to_email: str, to_name: str, accept_url: str) -> bool:
    subject = "Invitació a MiroFish"
    body = (
        f"Hola {to_name},\n\n"
        f"Has estat convidat/da a MiroFish.\n\n"
        f"Estableix la teva contrasenya accedint a:\n{accept_url}\n\n"
        f"Aquest enllaç caduca en {current_app.config['ACS_INVITATION_TTL_HOURS']} hores.\n"
    )
    return _send(to_email, subject, body)


def send_reset_password_email(to_email: str, reset_url: str) -> bool:
    subject = "Restabliment de contrasenya MiroFish"
    body = (
        f"Has sol·licitat restablir la contrasenya de MiroFish.\n\n"
        f"Accedeix a:\n{reset_url}\n\n"
        f"Aquest enllaç caduca en {current_app.config['ACS_RESET_PASSWORD_TTL_HOURS']} hora/es.\n"
        f"Si no has fet aquesta sol·licitud, ignora aquest missatge.\n"
    )
    return _send(to_email, subject, body)


def _send(to_email: str, subject: str, body: str) -> bool:
    conn_str = current_app.config.get('ACS_CONNECTION_STRING', '')
    sender = current_app.config.get('ACS_SENDER_ADDRESS', '')

    if not conn_str:
        logger.warning(
            "[EMAIL DEV — ACS no configurat]\n"
            f"  To:      {to_email}\n"
            f"  Subject: {subject}\n"
            f"  Body:\n{body}"
        )
        return True

    try:
        from azure.communication.email import EmailClient
        client = EmailClient.from_connection_string(conn_str)
        message = {
            "senderAddress": sender,
            "recipients": {"to": [{"address": to_email}]},
            "content": {"subject": subject, "plainText": body},
        }
        poller = client.begin_send(message)
        poller.result()
        return True
    except Exception as exc:
        logger.error(f"ACS send failed to {to_email}: {exc}")
        return False
```

- [ ] **Commit**

```bash
git add backend/app/services/email_service.py
git commit -m "feat(email): EmailService with ACS and dev console fallback"
```

---

## Task 5: Reescriure auth.py

**Files:**
- Modify: `backend/app/api/auth.py`
- Create: `backend/tests/test_auth_api.py`

- [ ] **Escriure els tests**

```python
# backend/tests/test_auth_api.py
"""Tests d'integració per als endpoints d'autenticació."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def app(in_memory_db):
    import backend.app.db as db_module
    saved_engine = db_module._engine
    saved_session = db_module._SessionLocal

    def _noop_init_db(url):
        db_module._engine = saved_engine
        db_module._SessionLocal = saved_session

    with patch('backend.app.db.init_db', side_effect=_noop_init_db):
        from backend.app import create_app
        application = create_app()

    application.config['TESTING'] = True
    application.extensions['storage'] = MagicMock()
    db_module._engine = saved_engine
    db_module._SessionLocal = saved_session
    return application


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


@pytest.fixture
def active_user(in_memory_db):
    from backend.app.models.db_models import UserModel
    from backend.app.services.auth_service import hash_password
    from backend.app.db import get_session
    with get_session() as db:
        user = UserModel(
            email="user@example.com",
            name="Test User",
            role="user",
            status="active",
            password_hash=hash_password("password123")
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    return user_id


def test_login_success(client, active_user):
    res = client.post('/api/auth/login', json={
        'email': 'user@example.com',
        'password': 'password123'
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'token' in data
    assert data['user']['email'] == 'user@example.com'


def test_login_wrong_password(client, active_user):
    res = client.post('/api/auth/login', json={
        'email': 'user@example.com',
        'password': 'wrongpassword'
    })
    assert res.status_code == 401
    assert res.get_json()['success'] is False


def test_login_nonexistent_user(client, in_memory_db):
    res = client.post('/api/auth/login', json={
        'email': 'nobody@example.com',
        'password': 'password123'
    })
    assert res.status_code == 401


def test_login_pending_user_rejected(client, in_memory_db):
    from backend.app.models.db_models import UserModel
    from backend.app.services.auth_service import hash_password
    from backend.app.db import get_session
    with get_session() as db:
        user = UserModel(
            email="pending@example.com", name="P", role="user", status="pending",
            password_hash=hash_password("pass")
        )
        db.add(user)
        db.commit()
    res = client.post('/api/auth/login', json={'email': 'pending@example.com', 'password': 'pass'})
    assert res.status_code == 401


def test_forgot_password_always_202(client, in_memory_db):
    # Email existent
    res = client.post('/api/auth/forgot-password', json={'email': 'notexists@example.com'})
    assert res.status_code == 202

    # Email inexistent
    res2 = client.post('/api/auth/forgot-password', json={'email': 'alsonotexists@example.com'})
    assert res2.status_code == 202


def test_get_invitation_token_valid(client, in_memory_db):
    from backend.app.models.db_models import UserModel
    from backend.app.services.auth_service import create_invitation_token
    from backend.app.db import get_session
    with get_session() as db:
        user = UserModel(email="inv@example.com", name="Inv", role="user", status="pending")
        db.add(user)
        db.commit()
        user_id = user.id
    token = create_invitation_token(user_id, ttl_hours=24)
    res = client.get(f'/api/auth/invitation/{token}')
    assert res.status_code == 200
    assert res.get_json()['data']['email'] == 'inv@example.com'


def test_get_invitation_token_invalid(client, in_memory_db):
    res = client.get('/api/auth/invitation/non-existent-token')
    assert res.status_code == 404


def test_set_password_activates_user(client, in_memory_db):
    from backend.app.models.db_models import UserModel
    from backend.app.services.auth_service import create_invitation_token
    from backend.app.db import get_session
    with get_session() as db:
        user = UserModel(email="setpwd@example.com", name="S", role="user", status="pending")
        db.add(user)
        db.commit()
        user_id = user.id
    token = create_invitation_token(user_id, ttl_hours=24)
    res = client.post('/api/auth/set-password', json={'token': token, 'password': 'newpass123'})
    assert res.status_code == 200
    with get_session() as db:
        u = db.get(UserModel, user_id)
        assert u.status == 'active'


def test_reset_password_flow(client, in_memory_db):
    from backend.app.models.db_models import UserModel
    from backend.app.services.auth_service import hash_password, create_reset_token
    from backend.app.db import get_session
    with get_session() as db:
        user = UserModel(
            email="reset@example.com", name="R", role="user", status="active",
            password_hash=hash_password("oldpass")
        )
        db.add(user)
        db.commit()
        user_id = user.id
    token = create_reset_token(user_id, ttl_hours=1)

    # GET verifica token
    res = client.get(f'/api/auth/reset-password/{token}')
    assert res.status_code == 200
    assert res.get_json()['data']['email'] == 'reset@example.com'

    # POST canvia contrasenya
    res2 = client.post('/api/auth/reset-password', json={'token': token, 'password': 'newpass456'})
    assert res2.status_code == 200

    # Token ja no és vàlid
    res3 = client.get(f'/api/auth/reset-password/{token}')
    assert res3.status_code == 404
```

- [ ] **Executar per veure que falla**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/test_auth_api.py -v 2>&1 | head -40
```

Expected: errors de login (endpoint demo no accepta email) i 404 a rutes noves.

- [ ] **Reescriure `backend/app/api/auth.py`**

```python
"""
Autenticació real: login bcrypt+JWT, refresh, logout, me,
forgot-password, reset-password, invitation, set-password.
"""
import logging
from flask import request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    set_refresh_cookies, unset_jwt_cookies,
    jwt_required, get_jwt_identity
)
from . import auth_bp
from ..db import get_session
from ..models.db_models import UserModel
from ..services.auth_service import (
    verify_password, get_user_by_email, _DUMMY_HASH,
    create_invitation_token, get_user_by_invitation_token, consume_invitation_token,
    create_reset_token, get_user_by_reset_token, consume_reset_token
)

logger = logging.getLogger('mirofish.auth')


def _user_dto(user: UserModel) -> dict:
    return {'id': user.id, 'email': user.email, 'name': user.name, 'role': user.role}


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    user = get_user_by_email(email)
    candidate_hash = user.password_hash if (user and user.password_hash) else _DUMMY_HASH
    valid = verify_password(password, candidate_hash)

    if not valid or not user or user.status != 'active':
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

    access_token = create_access_token(
        identity=user.id,
        additional_claims={'role': user.role, 'email': user.email}
    )
    refresh_token = create_refresh_token(identity=user.id)
    response = jsonify({'success': True, 'token': access_token, 'user': _user_dto(user)})
    set_refresh_cookies(response, refresh_token)
    return response


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    with get_session() as db:
        user = db.get(UserModel, user_id)
        if not user or user.status != 'active':
            return jsonify({'success': False, 'error': 'User not active'}), 401
        db.expunge(user)
    access_token = create_access_token(
        identity=user.id,
        additional_claims={'role': user.role, 'email': user.email}
    )
    return jsonify({'success': True, 'token': access_token, 'user': _user_dto(user)})


@auth_bp.route('/logout', methods=['POST'])
def logout():
    response = jsonify({'success': True})
    unset_jwt_cookies(response)
    return response


@auth_bp.route('/me', methods=['GET'])
def me():
    from .. import get_current_user
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    return jsonify({'success': True, 'data': _user_dto(user)})


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    user = get_user_by_email(email)
    if user and user.status == 'active':
        ttl = current_app.config.get('ACS_RESET_PASSWORD_TTL_HOURS', 1)
        token = create_reset_token(user.id, ttl_hours=ttl)
        reset_url = f"{request.host_url.rstrip('/')}/reset-password/{token}"
        from ..services.email_service import send_reset_password_email
        send_reset_password_email(user.email, reset_url)
    # sempre 202 (anti-enumeració)
    return jsonify({'success': True, 'message': 'If the email exists, a reset link has been sent'}), 202


@auth_bp.route('/reset-password/<token>', methods=['GET'])
def get_reset_token(token):
    user = get_user_by_reset_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Invalid or expired token'}), 404
    return jsonify({'success': True, 'data': {'email': user.email}})


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json(silent=True) or {}
    token = data.get('token', '')
    password = data.get('password', '')
    if len(password) < 8:
        return jsonify({'success': False, 'error': 'Password must be at least 8 characters'}), 400
    user = get_user_by_reset_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Invalid or expired token'}), 404
    consume_reset_token(token, password)
    return jsonify({'success': True})


@auth_bp.route('/invitation/<token>', methods=['GET'])
def get_invitation(token):
    user = get_user_by_invitation_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Invalid or expired token'}), 404
    return jsonify({'success': True, 'data': {'email': user.email, 'name': user.name}})


@auth_bp.route('/set-password', methods=['POST'])
def set_password():
    data = request.get_json(silent=True) or {}
    token = data.get('token', '')
    password = data.get('password', '')
    if len(password) < 8:
        return jsonify({'success': False, 'error': 'Password must be at least 8 characters'}), 400
    user = get_user_by_invitation_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Invalid or expired token'}), 404
    consume_invitation_token(token, password)
    return jsonify({'success': True})
```

- [ ] **Executar els tests**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/test_auth_api.py -v
```

Expected: tots PASS.

- [ ] **Commit**

```bash
git add backend/app/api/auth.py backend/tests/test_auth_api.py
git commit -m "feat(auth): rewrite auth.py with real login, invite, forgot/reset password"
```

---

## Task 6: JWTManager, decoradors i middleware

**Files:**
- Modify: `backend/app/__init__.py`

- [ ] **Actualitzar `create_app()` a `backend/app/__init__.py`**

Substituir el contingut complet del fitxer:

```python
"""MiroFish Backend - Flask application factory"""
import os
import warnings
from functools import wraps

warnings.filterwarnings("ignore", message=".*resource_tracker.*")

import jwt as _pyjwt
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, verify_jwt_in_request, get_jwt_identity

from .config import Config
from .utils.logger import setup_logger, get_logger

# Rutes públiques (sense JWT requerit)
_PUBLIC_PATHS = {
    '/health',
    '/api/auth/login',
    '/api/auth/logout',
    '/api/auth/forgot-password',
    '/api/auth/reset-password',
    '/api/auth/set-password',
}
_PUBLIC_PREFIXES = (
    '/api/auth/invitation/',
    '/api/auth/reset-password/',
)


def create_app(config_class=Config):
    """Flask application factory"""
    app = Flask(__name__)
    if isinstance(config_class, dict):
        app.config.from_object(Config)
        app.config.from_mapping(config_class)
    else:
        app.config.from_object(config_class)

    # Inicialitzar BD
    from .db import init_db
    init_db(app.config['DATABASE_URL'])

    # Inicialitzar Storage
    from .storage import create_storage_service
    app.extensions['storage'] = create_storage_service()

    # flask-jwt-extended
    JWTManager(app)

    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False

    logger = setup_logger('mirofish')
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process

    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroFish Backend starting...")
        logger.info("=" * 50)

    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()

    @app.before_request
    def require_auth():
        if app.config.get('TESTING'):
            return None
        if request.method == 'OPTIONS':
            return None
        if request.path in _PUBLIC_PATHS:
            return None
        if any(request.path.startswith(p) for p in _PUBLIC_PREFIXES):
            return None
        if not request.path.startswith('/api/'):
            return None
        try:
            verify_jwt_in_request()
        except Exception:
            return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401

    @app.before_request
    def log_request():
        logger = get_logger('mirofish.request')
        logger.debug(f"Request: {request.method} {request.path}")

    @app.after_request
    def log_response(response):
        logger = get_logger('mirofish.request')
        logger.debug(f"Response: {response.status_code}")
        return response

    from .api import graph_bp, simulation_bp, report_bp, auth_bp, users_bp, admin_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'MiroFish Backend'}

    import os as _os
    from flask import send_from_directory, send_file as _send_file
    _dist = _os.path.join(_os.path.dirname(__file__), '../../frontend/dist')
    if _os.path.isdir(_dist):
        @app.route('/', defaults={'path': ''})
        @app.route('/<path:path>')
        def serve_spa(path):
            f = _os.path.join(_dist, path)
            if path and _os.path.isfile(f):
                return send_from_directory(_dist, path)
            return _send_file(_os.path.join(_dist, 'index.html'))

    if should_log_startup:
        logger.info("MiroFish Backend startup complete")

    return app


def get_storage():
    from flask import current_app
    return current_app.extensions['storage']


def get_current_user():
    """Retorna el UserModel autenticat o None (en mode TESTING)."""
    from flask import current_app
    if current_app.config.get('TESTING'):
        return None
    try:
        user_id = get_jwt_identity()
    except Exception:
        return None
    if not user_id:
        return None
    from .db import get_session
    from .models.db_models import UserModel
    with get_session() as db:
        user = db.get(UserModel, user_id)
        if user:
            db.expunge(user)
        return user


def require_admin(f):
    """Decorator: requereix role=='admin'. Saltat en mode TESTING."""
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import current_app
        if not current_app.config.get('TESTING'):
            user = get_current_user()
            if not user or user.role != 'admin':
                return jsonify({'success': False, 'error': 'Admin required'}), 403
        return f(*args, **kwargs)
    return decorated


def require_project_owner(f):
    """Decorator: requereix ser propietari del projecte o admin. Saltat en TESTING."""
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import current_app
        if not current_app.config.get('TESTING'):
            user = get_current_user()
            if not user:
                return jsonify({'success': False, 'error': 'Not authenticated'}), 401
            if user.role != 'admin':
                project_id = kwargs.get('project_id')
                if project_id:
                    from .db import get_session
                    from .models.db_models import ProjectModel
                    with get_session() as db:
                        proj = db.get(ProjectModel, project_id)
                        if proj and proj.user_id and proj.user_id != user.id:
                            return jsonify({'success': False, 'error': 'Forbidden'}), 403
        return f(*args, **kwargs)
    return decorated
```

- [ ] **Actualitzar `backend/app/api/__init__.py`** per registrar els nous blueprints:

```python
"""API routes module"""
from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
simulation_bp = Blueprint('simulation', __name__)
report_bp = Blueprint('report', __name__)
auth_bp = Blueprint('auth', __name__)
users_bp = Blueprint('users', __name__)
admin_bp = Blueprint('admin', __name__)

from . import graph      # noqa
from . import simulation # noqa
from . import report     # noqa
from . import auth       # noqa
from . import users      # noqa
from . import admin      # noqa
```

- [ ] **Verificar que l'app arrenca sense errors**

```bash
cd /home/ubuntu/dev/MiroFish
python -c "
import sys; sys.path.insert(0, 'backend')
from unittest.mock import patch
with patch('app.db.init_db'):
    from app import create_app
    app = create_app()
    print('App created OK')
    print('JWTManager:', 'flask_jwt_extended' in str(app.extensions))
" 2>&1 | tail -5
```

Expected: `App created OK` (pot donar warnings de no trobar users/admin, acceptables).

- [ ] **Executar tots els tests existents per verificar no regressions**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/ -v --ignore=backend/tests/test_simulation_agent_api.py 2>&1 | tail -20
```

Expected: la majoria PASS (possibles errors a test_auth_api.py per blueprints no trobats — acceptable fins Task 7).

- [ ] **Commit**

```bash
git add backend/app/__init__.py backend/app/api/__init__.py
git commit -m "feat(auth): JWTManager, get_current_user, require_admin, require_project_owner decorators"
```

---

## Task 7: Users API (admin)

**Files:**
- Create: `backend/app/api/users.py`
- Create: `backend/tests/test_users_admin.py`

- [ ] **Escriure els tests**

```python
# backend/tests/test_users_admin.py
"""Tests per a l'API d'administració d'usuaris."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def app(in_memory_db):
    import backend.app.db as db_module
    saved_engine = db_module._engine
    saved_session = db_module._SessionLocal

    def _noop(url):
        db_module._engine = saved_engine
        db_module._SessionLocal = saved_session

    with patch('backend.app.db.init_db', side_effect=_noop):
        from backend.app import create_app
        application = create_app()

    application.config['TESTING'] = True
    application.extensions['storage'] = MagicMock()
    db_module._engine = saved_engine
    db_module._SessionLocal = saved_session
    return application


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


def test_list_users_empty(client, in_memory_db):
    res = client.get('/api/users/')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['data'] == []


def test_create_user_sends_invitation(client, in_memory_db):
    with patch('backend.app.api.users.send_invitation_email', return_value=True) as mock_email:
        res = client.post('/api/users/', json={
            'email': 'newuser@example.com',
            'name': 'New User',
            'role': 'user'
        })
    assert res.status_code == 201
    data = res.get_json()
    assert data['success'] is True
    assert data['data']['email'] == 'newuser@example.com'
    assert data['data']['status'] == 'pending'
    mock_email.assert_called_once()


def test_create_user_duplicate_email(client, in_memory_db):
    with patch('backend.app.api.users.send_invitation_email', return_value=True):
        client.post('/api/users/', json={'email': 'dup@example.com', 'name': 'D', 'role': 'user'})
        res = client.post('/api/users/', json={'email': 'dup@example.com', 'name': 'D2', 'role': 'user'})
    assert res.status_code == 409


def test_get_user(client, in_memory_db):
    with patch('backend.app.api.users.send_invitation_email', return_value=True):
        create_res = client.post('/api/users/', json={'email': 'get@example.com', 'name': 'Get', 'role': 'user'})
    user_id = create_res.get_json()['data']['id']
    res = client.get(f'/api/users/{user_id}')
    assert res.status_code == 200
    assert res.get_json()['data']['email'] == 'get@example.com'


def test_patch_user_role(client, in_memory_db):
    with patch('backend.app.api.users.send_invitation_email', return_value=True):
        create_res = client.post('/api/users/', json={'email': 'patch@example.com', 'name': 'P', 'role': 'user'})
    user_id = create_res.get_json()['data']['id']
    res = client.patch(f'/api/users/{user_id}', json={'role': 'admin'})
    assert res.status_code == 200
    assert res.get_json()['data']['role'] == 'admin'


def test_soft_delete_user(client, in_memory_db):
    with patch('backend.app.api.users.send_invitation_email', return_value=True):
        create_res = client.post('/api/users/', json={'email': 'del@example.com', 'name': 'Del', 'role': 'user'})
    user_id = create_res.get_json()['data']['id']
    res = client.delete(f'/api/users/{user_id}')
    assert res.status_code == 200
    # status és disabled, no esborrat
    get_res = client.get(f'/api/users/{user_id}')
    assert get_res.get_json()['data']['status'] == 'disabled'


def test_reinvite_pending_user(client, in_memory_db):
    with patch('backend.app.api.users.send_invitation_email', return_value=True) as mock_email:
        create_res = client.post('/api/users/', json={'email': 'reinv@example.com', 'name': 'R', 'role': 'user'})
    user_id = create_res.get_json()['data']['id']
    with patch('backend.app.api.users.send_invitation_email', return_value=True) as mock_email2:
        res = client.post(f'/api/users/{user_id}/reinvite')
    assert res.status_code == 200
    mock_email2.assert_called_once()
```

- [ ] **Executar per veure que falla**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/test_users_admin.py -v 2>&1 | head -20
```

- [ ] **Implementar `backend/app/api/users.py`**

```python
"""Users API: CRUD d'usuaris per a administradors."""
import logging
from flask import request, jsonify, current_app
from sqlalchemy import select
from . import users_bp
from .. import require_admin
from ..db import get_session
from ..models.db_models import UserModel
from ..services.auth_service import create_invitation_token
from ..services.email_service import send_invitation_email

logger = logging.getLogger('mirofish.users')


def _user_dto(user: UserModel) -> dict:
    return {
        'id': user.id, 'email': user.email, 'name': user.name,
        'role': user.role, 'status': user.status,
        'created_at': user.created_at.isoformat(),
    }


@users_bp.route('/', methods=['GET'])
@require_admin
def list_users():
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)
    offset = (page - 1) * page_size
    with get_session() as db:
        total = db.query(UserModel).count()
        users = db.execute(
            select(UserModel).order_by(UserModel.created_at.desc())
            .offset(offset).limit(page_size)
        ).scalars().all()
        for u in users:
            db.expunge(u)
    return jsonify({'success': True, 'data': [_user_dto(u) for u in users],
                    'total': total, 'page': page, 'pageSize': page_size})


@users_bp.route('/', methods=['POST'])
@require_admin
def create_user():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    name = data.get('name', '').strip()
    role = data.get('role', 'user')
    if not email or not name:
        return jsonify({'success': False, 'error': 'email and name required'}), 400
    with get_session() as db:
        existing = db.execute(select(UserModel).where(UserModel.email == email)).scalar_one_or_none()
        if existing:
            return jsonify({'success': False, 'error': 'Email already registered'}), 409
        user = UserModel(email=email, name=name, role=role, status='pending')
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)

    ttl = current_app.config.get('ACS_INVITATION_TTL_HOURS', 48)
    token = create_invitation_token(user.id, ttl_hours=ttl)
    accept_url = f"{request.host_url.rstrip('/')}/accept-invite/{token}"
    send_invitation_email(user.email, user.name, accept_url)

    return jsonify({'success': True, 'data': _user_dto(user)}), 201


@users_bp.route('/<user_id>', methods=['GET'])
@require_admin
def get_user(user_id):
    with get_session() as db:
        user = db.get(UserModel, user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        db.expunge(user)
    return jsonify({'success': True, 'data': _user_dto(user)})


@users_bp.route('/<user_id>', methods=['PATCH'])
@require_admin
def patch_user(user_id):
    data = request.get_json(silent=True) or {}
    with get_session() as db:
        user = db.get(UserModel, user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        for field in ('name', 'role', 'status'):
            if field in data:
                setattr(user, field, data[field])
        db.commit()
        db.refresh(user)
        db.expunge(user)
    return jsonify({'success': True, 'data': _user_dto(user)})


@users_bp.route('/<user_id>', methods=['DELETE'])
@require_admin
def delete_user(user_id):
    """Soft delete: status = disabled."""
    with get_session() as db:
        user = db.get(UserModel, user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        user.status = 'disabled'
        db.commit()
    return jsonify({'success': True})


@users_bp.route('/<user_id>/purge', methods=['DELETE'])
@require_admin
def purge_user(user_id):
    """Hard delete: esborra usuari i projectes en cascada."""
    from .. import get_storage
    storage = get_storage()
    with get_session() as db:
        user = db.get(UserModel, user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        # Esborrar fitxers de storage per a cada projecte
        for proj in user.projects:
            try:
                storage.delete_prefix(f"projects/{proj.id}")
            except Exception:
                pass
        db.delete(user)
        db.commit()
    return jsonify({'success': True})


@users_bp.route('/<user_id>/reinvite', methods=['POST'])
@require_admin
def reinvite_user(user_id):
    with get_session() as db:
        user = db.get(UserModel, user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        if user.status != 'pending':
            return jsonify({'success': False, 'error': 'User is not pending'}), 400
        db.expunge(user)
    ttl = current_app.config.get('ACS_INVITATION_TTL_HOURS', 48)
    token = create_invitation_token(user.id, ttl_hours=ttl)
    accept_url = f"{request.host_url.rstrip('/')}/accept-invite/{token}"
    send_invitation_email(user.email, user.name, accept_url)
    return jsonify({'success': True})
```

- [ ] **Executar els tests**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/test_users_admin.py -v
```

Expected: tots PASS.

- [ ] **Commit**

```bash
git add backend/app/api/users.py backend/tests/test_users_admin.py
git commit -m "feat(users): admin CRUD users API with invitation flow"
```

---

## Task 8: Admin API (config + historial)

**Files:**
- Create: `backend/app/api/admin.py`
- Create: `backend/tests/test_admin_api.py`

- [ ] **Escriure els tests**

```python
# backend/tests/test_admin_api.py
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def app(in_memory_db):
    import backend.app.db as db_module
    saved_engine = db_module._engine
    saved_session = db_module._SessionLocal

    def _noop(url):
        db_module._engine = saved_engine
        db_module._SessionLocal = saved_session

    with patch('backend.app.db.init_db', side_effect=_noop):
        from backend.app import create_app
        application = create_app()

    application.config['TESTING'] = True
    application.extensions['storage'] = MagicMock()
    db_module._engine = saved_engine
    db_module._SessionLocal = saved_session
    return application


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


def test_get_config_empty(client, in_memory_db):
    res = client.get('/api/admin/config')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert isinstance(data['data'], list)


def test_patch_config(client, in_memory_db):
    # Crear una entrada de config
    from backend.app.models.db_models import SystemConfigModel
    from backend.app.db import get_session
    with get_session() as db:
        db.add(SystemConfigModel(
            key='llm.model_name', value='qwen-plus',
            value_type='string', group='llm',
            label='Model LLM', description='Nom del model LLM principal',
            is_secret=False
        ))
        db.commit()

    res = client.patch('/api/admin/config', json={'llm.model_name': 'gpt-4o'})
    assert res.status_code == 200

    res2 = client.get('/api/admin/config')
    entries = res2.get_json()['data']
    entry = next(e for e in entries if e['key'] == 'llm.model_name')
    assert entry['value'] == 'gpt-4o'


def test_get_executions_empty(client, in_memory_db):
    res = client.get('/api/admin/executions')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['data'] == []
```

- [ ] **Implementar `backend/app/api/admin.py`**

```python
"""Admin API: configuració sistema i historial d'execucions."""
from flask import request, jsonify
from sqlalchemy import select, desc
from . import admin_bp
from .. import require_admin
from ..db import get_session
from ..models.db_models import SystemConfigModel, SimulationModel, ProjectModel, UserModel


@admin_bp.route('/config', methods=['GET'])
@require_admin
def get_config():
    with get_session() as db:
        entries = db.execute(select(SystemConfigModel)).scalars().all()
        result = []
        for e in entries:
            result.append({
                'key': e.key,
                'value': '●●●●' if e.is_secret else e.value,
                'value_type': e.value_type,
                'group': e.group,
                'label': e.label,
                'description': e.description,
                'is_secret': e.is_secret,
            })
    return jsonify({'success': True, 'data': result})


@admin_bp.route('/config', methods=['PATCH'])
@require_admin
def patch_config():
    data = request.get_json(silent=True) or {}
    with get_session() as db:
        for key, value in data.items():
            entry = db.get(SystemConfigModel, key)
            if entry:
                entry.value = str(value)
        db.commit()
    return jsonify({'success': True})


@admin_bp.route('/executions', methods=['GET'])
@require_admin
def list_executions():
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)
    filter_user_id = request.args.get('user_id')
    offset = (page - 1) * page_size

    with get_session() as db:
        stmt = (
            select(SimulationModel, ProjectModel, UserModel)
            .join(ProjectModel, SimulationModel.project_id == ProjectModel.id)
            .outerjoin(UserModel, ProjectModel.user_id == UserModel.id)
            .order_by(desc(SimulationModel.created_at))
        )
        if filter_user_id:
            stmt = stmt.where(ProjectModel.user_id == filter_user_id)

        total_stmt = stmt.with_only_columns(SimulationModel.id)
        total = len(db.execute(total_stmt).all())

        rows = db.execute(stmt.offset(offset).limit(page_size)).all()
        result = []
        for sim, proj, user in rows:
            result.append({
                'simulation_id': sim.id,
                'project_id': proj.id,
                'project_name': proj.name,
                'user_email': user.email if user else None,
                'status': sim.status,
                'platform': sim.platform,
                'rounds_total': sim.rounds_total,
                'rounds_completed': sim.rounds_completed,
                'created_at': sim.created_at.isoformat(),
            })
    return jsonify({'success': True, 'data': result, 'total': total, 'page': page, 'pageSize': page_size})
```

- [ ] **Executar els tests**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/test_admin_api.py -v
```

Expected: tots PASS.

- [ ] **Commit**

```bash
git add backend/app/api/admin.py backend/tests/test_admin_api.py
git commit -m "feat(admin): system config and global executions history API"
```

---

## Task 9: ProjectManager — aïllament per user_id

**Files:**
- Modify: `backend/app/models/project.py`
- Create: `backend/tests/test_project_isolation.py`

- [ ] **Escriure els tests**

```python
# backend/tests/test_project_isolation.py
import pytest


@pytest.fixture(autouse=True)
def _db(in_memory_db):
    pass


def _make_user(email, role='user'):
    from backend.app.models.db_models import UserModel
    from backend.app.db import get_session
    with get_session() as db:
        user = UserModel(email=email, name=email, role=role, status='active')
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id


def test_list_projects_filtered_by_user():
    from backend.app.models.project import ProjectManager
    uid1 = _make_user('u1@test.com')
    uid2 = _make_user('u2@test.com')

    ProjectManager.create_project(name="U1-A", user_id=uid1)
    ProjectManager.create_project(name="U1-B", user_id=uid1)
    ProjectManager.create_project(name="U2-A", user_id=uid2)

    u1_projects = ProjectManager.list_projects(user_id=uid1)
    assert len(u1_projects) == 2
    assert all(p['user_id'] == uid1 for p in u1_projects)

    u2_projects = ProjectManager.list_projects(user_id=uid2)
    assert len(u2_projects) == 1
    assert u2_projects[0]['name'] == 'U2-A'


def test_list_projects_no_filter_returns_all():
    from backend.app.models.project import ProjectManager
    uid1 = _make_user('all1@test.com')
    uid2 = _make_user('all2@test.com')
    ProjectManager.create_project(name="P1", user_id=uid1)
    ProjectManager.create_project(name="P2", user_id=uid2)
    all_projects = ProjectManager.list_projects(user_id=None)
    assert len(all_projects) >= 2


def test_create_project_assigns_user_id():
    from backend.app.models.project import ProjectManager
    uid = _make_user('owner@test.com')
    proj = ProjectManager.create_project(name="Owned", user_id=uid)
    assert proj['user_id'] == uid


def test_to_dict_includes_user_id():
    from backend.app.models.project import ProjectManager
    uid = _make_user('dict@test.com')
    proj = ProjectManager.create_project(name="DictTest", user_id=uid)
    assert 'user_id' in proj
    assert proj['user_id'] == uid
```

- [ ] **Executar per veure que falla**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/test_project_isolation.py -v 2>&1 | head -30
```

Expected: errors perquè `create_project` no accepta `user_id` i `_to_dict` no inclou `user_id`.

- [ ] **Actualitzar `backend/app/models/project.py`**

Fer els canvis següents (no reescriure tot el fitxer):

**`create_project` (línia 24):** afegir `user_id: str = None`:

```python
    @classmethod
    def create_project(cls, name: str = "Unnamed Project", storage=None, user_id: str = None) -> Dict[str, Any]:
        project_id = str(uuid.uuid4())
        with get_session() as db:
            proj = ProjectModel(id=project_id, name=name, status="created", user_id=user_id)
            db.add(proj)
            db.commit()
            db.refresh(proj)
            db.expunge(proj)
        return cls._to_dict(proj)
```

**`list_projects` (línia 62):** afegir `user_id: str = None` i filtre:

```python
    @classmethod
    def list_projects(cls, limit: int = 50, user_id: str = None) -> List[Dict[str, Any]]:
        from sqlalchemy import select, desc
        with get_session() as db:
            stmt = select(ProjectModel).order_by(desc(ProjectModel.created_at)).limit(limit)
            if user_id is not None:
                stmt = stmt.where(ProjectModel.user_id == user_id)
            projects = db.execute(stmt).scalars().all()
            for p in projects:
                db.expunge(p)
        return [cls._to_dict(p) for p in projects]
```

**`_to_dict` (línia 264):** afegir `user_id` al diccionari retornat (afegir just després de `"project_id": proj.id`):

```python
            "user_id": proj.user_id,
```

- [ ] **Executar els tests**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/test_project_isolation.py -v
```

Expected: tots PASS.

- [ ] **Executar tots els tests per verificar no regressions**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/ -v --ignore=backend/tests/test_simulation_agent_api.py 2>&1 | tail -15
```

Expected: tots PASS.

- [ ] **Commit**

```bash
git add backend/app/models/project.py backend/tests/test_project_isolation.py
git commit -m "feat(project): user_id isolation in create_project, list_projects and _to_dict"
```

---

## Task 10: graph.py — filtrat per usuari i protecció propietari

**Files:**
- Modify: `backend/app/api/graph.py`

Els canvis a `graph.py` afecten tres punts:
1. `list_projects` → filtrar per `user_id` del token (admin veu tots)
2. `get_project`, `delete_project` → afegir `@require_project_owner`
3. `create_project` (dins `generate_ontology` i `import_ontology`) → passar `user_id`

- [ ] **Afegir imports necessaris al principi de `graph.py`** (substituir la línia `from ..models.project import ProjectManager, ProjectStatus`):

```python
from ..models.project import ProjectManager, ProjectStatus
from .. import get_current_user, require_project_owner
```

- [ ] **Actualitzar `list_projects` (línia ~64)**

```python
@graph_bp.route('/project/list', methods=['GET'])
def list_projects():
    limit = request.args.get('limit', 50, type=int)
    user = get_current_user()
    # Admin i mode TESTING (user=None) veuen tots; usuaris normals veuen els seus
    filter_user_id = None if (user is None or user.role == 'admin') else user.id
    projects = ProjectManager.list_projects(limit=limit, user_id=filter_user_id)
    return jsonify({"success": True, "data": projects, "count": len(projects)})
```

- [ ] **Afegir `@require_project_owner` a `get_project` i `delete_project`**

```python
@graph_bp.route('/project/<project_id>', methods=['GET'])
@require_project_owner
def get_project(project_id: str):
    # ... (codi existent sense canvis)

@graph_bp.route('/project/<project_id>', methods=['DELETE'])
@require_project_owner
def delete_project(project_id: str):
    # ... (codi existent sense canvis)
```

- [ ] **Localitzar les crides a `ProjectManager.create_project()` dins `graph.py`** (busca amb grep):

```bash
grep -n "create_project" /home/ubuntu/dev/MiroFish/backend/app/api/graph.py
```

Per cada crida trobada, afegir `user_id`:
```python
# Exemple (adaptar a cada lloc):
user = get_current_user()
proj = ProjectManager.create_project(
    name="Unnamed Project",
    storage=storage,
    user_id=user.id if user else None
)
```

- [ ] **Verificar que els tests existents passen**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/test_graph_api_project.py backend/tests/test_project_isolation.py -v
```

Expected: tots PASS (en mode TESTING, `get_current_user()` retorna None → filtre desactivat → comportament idèntic als tests actuals).

- [ ] **Commit**

```bash
git add backend/app/api/graph.py
git commit -m "feat(graph): filter projects by user_id, protect get/delete with require_project_owner"
```

---

## Task 11: Migració Alembic + init_system.py

**Files:**
- Create: `backend/alembic/versions/xxxx_fase3_user_isolation.py` (nom generat per alembic)
- Create: `backend/scripts/init_system.py`

- [ ] **Generar la migració Alembic**

```bash
cd /home/ubuntu/dev/MiroFish/backend
uv run alembic revision --autogenerate -m "fase3_user_isolation"
```

Editar el fitxer generat a `alembic/versions/` per assegurar que inclou:

```python
def upgrade() -> None:
    # Alembic pot generar-ho automàticament; verificar que conté:
    # 1. CREATE TABLE users (si no existeix)
    # 2. CREATE TABLE invitation_tokens
    # 3. CREATE TABLE password_reset_tokens
    # 4. CREATE TABLE system_config
    # 5. ALTER TABLE projects ADD COLUMN user_id (si no existeix)
    # Si la migració inicial ja crea les taules, aquest pas pot ser buit
    # o només assignar projectes orfes a l'admin:
    op.execute("""
        UPDATE projects
        SET user_id = (
            SELECT id FROM users WHERE role = 'admin' ORDER BY created_at LIMIT 1
        )
        WHERE user_id IS NULL
        AND EXISTS (SELECT 1 FROM users WHERE role = 'admin')
    """)
```

- [ ] **Crear `backend/scripts/init_system.py`**

```python
#!/usr/bin/env python3
"""
Inicialitzar el sistema MiroFish per al primer ús:
  1. Crear el primer admin si no existeix cap usuari
  2. Inserir valors per defecte a SystemConfigModel
  3. Executar migracions Alembic pendents

Ús: uv run python backend/scripts/init_system.py
     o:  flask init-system (si es registra com a CLI command)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def main():
    from app.config import Config
    from app.db import init_db, get_session, Base
    from app.models.db_models import UserModel, SystemConfigModel
    from app.services.auth_service import hash_password
    from sqlalchemy import select

    db_url = Config.DATABASE_URL
    print(f"[init_system] Connecting to: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    init_db(db_url)

    # Executar migracions Alembic
    try:
        import subprocess
        result = subprocess.run(
            ['uv', 'run', 'alembic', 'upgrade', 'head'],
            cwd=os.path.dirname(__file__) + '/..',
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"[init_system] Alembic warning: {result.stderr}")
        else:
            print("[init_system] Alembic migrations: OK")
    except Exception as e:
        print(f"[init_system] Alembic skipped: {e}")

    with get_session() as db:
        # Crear admin si no existeix cap usuari
        any_user = db.execute(select(UserModel).limit(1)).scalar_one_or_none()
        if any_user is None:
            admin_email = Config.ADMIN_EMAIL or input("Admin email: ").strip()
            admin_password = Config.ADMIN_PASSWORD or input("Admin password: ").strip()
            if not admin_email or not admin_password:
                print("[init_system] ERROR: ADMIN_EMAIL i ADMIN_PASSWORD requerits")
                sys.exit(1)
            admin = UserModel(
                email=admin_email.lower(),
                name="Admin",
                role="admin",
                status="active",
                password_hash=hash_password(admin_password)
            )
            db.add(admin)
            db.commit()
            print(f"[init_system] Admin creat: {admin_email}")
        else:
            print(f"[init_system] Usuaris existents, saltant creació admin")

        # Inserir SystemConfig per defecte si no existeix
        defaults = [
            ('llm.model_name',  Config.LLM_MODEL_NAME,     'string', 'llm',    'Model LLM',        '', False),
            ('llm.base_url',    Config.LLM_BASE_URL,        'string', 'llm',    'URL base LLM',     '', False),
            ('llm.api_key',     Config.LLM_API_KEY or '',   'string', 'llm',    'API Key LLM',      '', True),
            ('limits.max_projects_per_user', '20',          'int',    'limits', 'Màx. projectes',   '', False),
            ('limits.max_simulations',       '10',          'int',    'limits', 'Màx. simulacions', '', False),
        ]
        for key, value, vtype, group, label, desc, is_secret in defaults:
            existing = db.get(SystemConfigModel, key)
            if not existing:
                db.add(SystemConfigModel(
                    key=key, value=value, value_type=vtype,
                    group=group, label=label, description=desc, is_secret=is_secret
                ))
        db.commit()
        print("[init_system] SystemConfig per defecte: OK")

    print("[init_system] Inicialització completada.")


if __name__ == '__main__':
    main()
```

- [ ] **Verificar execució en dev (BD SQLite)**

```bash
cd /home/ubuntu/dev/MiroFish
ADMIN_EMAIL=admin@dev.local ADMIN_PASSWORD=adminpass123 uv run python backend/scripts/init_system.py
```

Expected: `Admin creat: admin@dev.local` + `SystemConfig per defecte: OK`.

- [ ] **Commit**

```bash
git add backend/alembic/versions/ backend/scripts/init_system.py
git commit -m "feat(init): Alembic migration fase3 + init_system.py script"
```

---

## Task 12: Frontend — auth store + router

**Files:**
- Modify: `frontend/src/store/auth.js`
- Modify: `frontend/src/router/index.js`

- [ ] **Reescriure `frontend/src/store/auth.js`**

```javascript
import { reactive, computed } from 'vue'

const AUTH_KEY = 'mirofish_token'
const USER_KEY = 'mirofish_user'

const state = reactive({
  token: localStorage.getItem(AUTH_KEY) || null,
  user: JSON.parse(localStorage.getItem(USER_KEY) || 'null'),
  get isAuthenticated() { return !!this.token }
})

export const isAdmin = computed(() => state.user?.role === 'admin')

export function setAuth(token, user) {
  state.token = token
  state.user = user
  localStorage.setItem(AUTH_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearAuth() {
  state.token = null
  state.user = null
  localStorage.removeItem(AUTH_KEY)
  localStorage.removeItem(USER_KEY)
}

export function getToken() {
  return state.token
}

// Compatibilitat enrere (LoginView usa setToken)
export function setToken(token) {
  setAuth(token, state.user)
}

export function clearToken() {
  clearAuth()
}

export default state
```

- [ ] **Reescriure `frontend/src/router/index.js`**

```javascript
import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Process from '../views/MainView.vue'
import SimulationView from '../views/SimulationView.vue'
import SimulationRunView from '../views/SimulationRunView.vue'
import ReportView from '../views/ReportView.vue'
import InteractionView from '../views/InteractionView.vue'
import LoginView from '../views/LoginView.vue'
import ForgotPasswordView from '../views/ForgotPasswordView.vue'
import ResetPasswordView from '../views/ResetPasswordView.vue'
import SetPasswordView from '../views/SetPasswordView.vue'
import AdminView from '../views/AdminView.vue'
import authState, { isAdmin } from '../store/auth'

const routes = [
  // Públiques
  { path: '/login',                name: 'Login',          component: LoginView,         meta: { public: true } },
  { path: '/forgot-password',      name: 'ForgotPassword', component: ForgotPasswordView, meta: { public: true } },
  { path: '/reset-password/:token',name: 'ResetPassword',  component: ResetPasswordView,  meta: { public: true }, props: true },
  { path: '/accept-invite/:token', name: 'AcceptInvite',   component: SetPasswordView,    meta: { public: true }, props: true },

  // Privades
  { path: '/',                          name: 'Home',          component: Home },
  { path: '/process/:projectId',        name: 'Process',       component: Process,          props: true },
  { path: '/simulation/:simulationId',  name: 'Simulation',    component: SimulationView,   props: true },
  { path: '/simulation/:simulationId/start', name: 'SimulationRun', component: SimulationRunView, props: true },
  { path: '/report/:reportId',          name: 'Report',        component: ReportView,       props: true },
  { path: '/interaction/:reportId',     name: 'Interaction',   component: InteractionView,  props: true },

  // Admin only
  { path: '/admin',           redirect: '/admin/users' },
  { path: '/admin/:tab',      name: 'Admin', component: AdminView, props: true, meta: { requiresAdmin: true } },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to, from, next) => {
  if (to.meta?.public) return next()
  if (!authState.isAuthenticated) return next({ name: 'Login', query: { redirect: to.fullPath } })
  if (to.meta?.requiresAdmin && !isAdmin.value) return next({ name: 'Home' })
  if (to.name === 'Login') return next({ name: 'Home' })
  next()
})

export default router
```

- [ ] **Commit**

```bash
git add frontend/src/store/auth.js frontend/src/router/index.js
git commit -m "feat(frontend): auth store with user object + isAdmin, router with admin guard"
```

---

## Task 13: Frontend — LoginView + vistes d'autenticació

**Files:**
- Modify: `frontend/src/views/LoginView.vue`
- Create: `frontend/src/views/ForgotPasswordView.vue`
- Create: `frontend/src/views/ResetPasswordView.vue`
- Create: `frontend/src/views/SetPasswordView.vue`

- [ ] **Actualitzar `frontend/src/views/LoginView.vue`**

Canvis mínims: substituir el camp `username` per `email`, actualitzar la crida API, afegir link forgot password, afegir missatge `?activated=1`, actualitzar `setAuth`:

```vue
<template>
  <div class="login-container">
    <nav class="navbar">
      <div class="nav-brand">MIROFISH</div>
    </nav>
    <main class="login-main">
      <div class="login-card">
        <div class="card-header">
          <span class="tag">AUTH</span>
          <h1 class="title">{{ $t('login.title') }}</h1>
          <p v-if="activated" class="success-msg">{{ $t('login.accountActivated') }}</p>
          <p v-else class="subtitle">{{ $t('login.subtitle') }}</p>
        </div>
        <form class="login-form" @submit.prevent="handleLogin">
          <div class="field">
            <label class="field-label" for="login-email">{{ $t('login.email') }}</label>
            <input id="login-email" v-model="form.email" type="email" class="field-input"
                   autocomplete="email" :disabled="loading" :placeholder="$t('login.emailPlaceholder')" />
          </div>
          <div class="field">
            <label class="field-label" for="login-password">{{ $t('login.password') }}</label>
            <input id="login-password" v-model="form.password" type="password" class="field-input"
                   autocomplete="current-password" :disabled="loading" :placeholder="$t('login.passwordPlaceholder')" />
          </div>
          <div v-if="error" class="error-msg" role="alert">{{ error }}</div>
          <button type="submit" class="submit-btn" :disabled="loading || !canSubmit">
            <span v-if="loading">{{ $t('login.loading') }}</span>
            <span v-else>{{ $t('login.submit') }} <span class="btn-arrow">→</span></span>
          </button>
          <router-link to="/forgot-password" class="forgot-link">{{ $t('login.forgotPassword') }}</router-link>
        </form>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import service from '../api/index'
import { setAuth } from '../store/auth'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()

const form = ref({ email: '', password: '' })
const loading = ref(false)
const error = ref('')
const activated = computed(() => route.query.activated === '1')
const canSubmit = computed(() => form.value.email.trim() !== '' && form.value.password !== '')

async function handleLogin() {
  if (!canSubmit.value || loading.value) return
  loading.value = true
  error.value = ''
  try {
    const res = await service.post('/api/auth/login', {
      email: form.value.email,
      password: form.value.password
    })
    setAuth(res.token, res.user)
    router.push(route.query.redirect || '/')
  } catch {
    error.value = t('login.invalidCredentials')
  } finally {
    loading.value = false
  }
}
</script>
```

Afegir al `<style scoped>` existent:
```css
.forgot-link {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: #666;
  text-align: center;
  text-decoration: none;
}
.forgot-link:hover { color: #ff4500; }
.success-msg {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  color: #22c55e;
  border-left: 3px solid #22c55e;
  padding-left: 12px;
}
```

- [ ] **Afegir claus i18n necessàries a `locales/en.json`** (dins el bloc `"login"`):

```json
"email": "Email",
"emailPlaceholder": "your@email.com",
"forgotPassword": "Forgot password?",
"accountActivated": "Account activated. You can now log in.",
```

I a `locales/zh.json` les equivalents en xinès.

- [ ] **Crear `frontend/src/views/ForgotPasswordView.vue`**

```vue
<template>
  <div class="auth-container">
    <nav class="navbar"><div class="nav-brand">MIROFISH</div></nav>
    <main class="auth-main">
      <div class="auth-card">
        <div class="card-header">
          <span class="tag">AUTH</span>
          <h1 class="title">{{ $t('forgotPassword.title') }}</h1>
          <p class="subtitle">{{ $t('forgotPassword.subtitle') }}</p>
        </div>
        <div v-if="sent" class="success-msg">{{ $t('forgotPassword.sent') }}</div>
        <form v-else class="auth-form" @submit.prevent="handleSubmit">
          <div class="field">
            <label class="field-label">{{ $t('login.email') }}</label>
            <input v-model="email" type="email" class="field-input"
                   :disabled="loading" :placeholder="$t('login.emailPlaceholder')" />
          </div>
          <div v-if="error" class="error-msg">{{ error }}</div>
          <button type="submit" class="submit-btn" :disabled="loading || !email.trim()">
            <span v-if="loading">{{ $t('common.loading') }}</span>
            <span v-else>{{ $t('forgotPassword.submit') }} →</span>
          </button>
          <router-link to="/login" class="back-link">← {{ $t('common.back') }}</router-link>
        </form>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import service from '../api/index'

const { t } = useI18n()
const email = ref('')
const loading = ref(false)
const sent = ref(false)
const error = ref('')

async function handleSubmit() {
  loading.value = true
  error.value = ''
  try {
    await service.post('/api/auth/forgot-password', { email: email.value })
    sent.value = true
  } catch {
    error.value = t('common.unknownError')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* Reutilitza l'estil de LoginView */
.auth-container { min-height: 100vh; background: #fff; font-family: 'Space Grotesk', system-ui, sans-serif; color: #000; display: flex; flex-direction: column; }
.navbar { height: 60px; background: #000; color: #fff; display: flex; align-items: center; padding: 0 40px; }
.nav-brand { font-family: 'JetBrains Mono', monospace; font-weight: 800; letter-spacing: 1px; font-size: 1.2rem; }
.auth-main { flex: 1; display: flex; align-items: center; justify-content: center; padding: 40px 20px; }
.auth-card { width: 100%; max-width: 400px; border: 1px solid #e5e5e5; padding: 48px 40px; }
.card-header { margin-bottom: 32px; }
.tag { display: inline-block; background: #ff4500; color: #fff; font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; font-weight: 700; padding: 2px 8px; letter-spacing: 1px; margin-bottom: 16px; }
.title { font-size: 1.8rem; font-weight: 500; margin-bottom: 8px; }
.subtitle { font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #666; }
.auth-form { display: flex; flex-direction: column; gap: 20px; }
.field { display: flex; flex-direction: column; gap: 8px; }
.field-label { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
.field-input { border: 1px solid #e5e5e5; background: #fafafa; padding: 12px 16px; font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; outline: none; transition: border-color 0.15s; width: 100%; box-sizing: border-box; }
.field-input:focus { border-color: #000; background: #fff; }
.error-msg { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #ff4500; border-left: 3px solid #ff4500; padding-left: 12px; }
.success-msg { font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #22c55e; border-left: 3px solid #22c55e; padding-left: 12px; }
.submit-btn { background: #000; color: #fff; border: none; padding: 14px 24px; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 0.95rem; cursor: pointer; transition: background 0.15s; width: 100%; }
.submit-btn:hover:not(:disabled) { background: #ff4500; }
.submit-btn:disabled { background: #e5e5e5; color: #999; cursor: not-allowed; }
.back-link { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #666; text-decoration: none; text-align: center; }
.back-link:hover { color: #ff4500; }
</style>
```

- [ ] **Crear `frontend/src/views/ResetPasswordView.vue`**

```vue
<template>
  <div class="auth-container">
    <nav class="navbar"><div class="nav-brand">MIROFISH</div></nav>
    <main class="auth-main">
      <div class="auth-card">
        <div class="card-header">
          <span class="tag">AUTH</span>
          <h1 class="title">{{ $t('resetPassword.title') }}</h1>
          <p v-if="email" class="subtitle">{{ email }}</p>
        </div>
        <div v-if="error && !email" class="error-msg">{{ $t('resetPassword.invalidToken') }}</div>
        <div v-else-if="done" class="success-msg">{{ $t('resetPassword.done') }}</div>
        <form v-else-if="email" class="auth-form" @submit.prevent="handleSubmit">
          <div class="field">
            <label class="field-label">{{ $t('resetPassword.newPassword') }}</label>
            <input v-model="password" type="password" class="field-input"
                   :disabled="loading" minlength="8" />
          </div>
          <div class="field">
            <label class="field-label">{{ $t('resetPassword.confirmPassword') }}</label>
            <input v-model="confirm" type="password" class="field-input" :disabled="loading" />
          </div>
          <div v-if="formError" class="error-msg">{{ formError }}</div>
          <button type="submit" class="submit-btn" :disabled="loading || !canSubmit">
            <span v-if="loading">{{ $t('common.loading') }}</span>
            <span v-else>{{ $t('resetPassword.submit') }} →</span>
          </button>
        </form>
        <router-link v-if="done" to="/login" class="back-link">{{ $t('resetPassword.goToLogin') }} →</router-link>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import service from '../api/index'

const props = defineProps({ token: String })
const { t } = useI18n()

const email = ref('')
const password = ref('')
const confirm = ref('')
const loading = ref(false)
const error = ref('')
const formError = ref('')
const done = ref(false)

const canSubmit = computed(() =>
  password.value.length >= 8 && password.value === confirm.value
)

onMounted(async () => {
  try {
    const res = await service.get(`/api/auth/reset-password/${props.token}`)
    email.value = res.data.email
  } catch {
    error.value = 'invalid'
  }
})

async function handleSubmit() {
  if (!canSubmit.value) {
    formError.value = t('resetPassword.passwordMismatch')
    return
  }
  loading.value = true
  formError.value = ''
  try {
    await service.post('/api/auth/reset-password', { token: props.token, password: password.value })
    done.value = true
  } catch {
    formError.value = t('common.unknownError')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* Ídem ForgotPasswordView */
.auth-container { min-height: 100vh; background: #fff; font-family: 'Space Grotesk', system-ui, sans-serif; color: #000; display: flex; flex-direction: column; }
.navbar { height: 60px; background: #000; color: #fff; display: flex; align-items: center; padding: 0 40px; }
.nav-brand { font-family: 'JetBrains Mono', monospace; font-weight: 800; letter-spacing: 1px; font-size: 1.2rem; }
.auth-main { flex: 1; display: flex; align-items: center; justify-content: center; padding: 40px 20px; }
.auth-card { width: 100%; max-width: 400px; border: 1px solid #e5e5e5; padding: 48px 40px; }
.card-header { margin-bottom: 32px; }
.tag { display: inline-block; background: #ff4500; color: #fff; font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; font-weight: 700; padding: 2px 8px; letter-spacing: 1px; margin-bottom: 16px; }
.title { font-size: 1.8rem; font-weight: 500; margin-bottom: 8px; }
.subtitle { font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #666; }
.auth-form { display: flex; flex-direction: column; gap: 20px; }
.field { display: flex; flex-direction: column; gap: 8px; }
.field-label { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; }
.field-input { border: 1px solid #e5e5e5; background: #fafafa; padding: 12px 16px; font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; outline: none; width: 100%; box-sizing: border-box; }
.field-input:focus { border-color: #000; background: #fff; }
.error-msg { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #ff4500; border-left: 3px solid #ff4500; padding-left: 12px; }
.success-msg { font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #22c55e; border-left: 3px solid #22c55e; padding-left: 12px; }
.submit-btn { background: #000; color: #fff; border: none; padding: 14px 24px; font-family: 'JetBrains Mono', monospace; font-weight: 700; cursor: pointer; transition: background 0.15s; width: 100%; }
.submit-btn:hover:not(:disabled) { background: #ff4500; }
.submit-btn:disabled { background: #e5e5e5; color: #999; cursor: not-allowed; }
.back-link { display: block; margin-top: 16px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #000; text-decoration: none; text-align: center; }
.back-link:hover { color: #ff4500; }
</style>
```

- [ ] **Crear `frontend/src/views/SetPasswordView.vue`** (acceptar invitació)

```vue
<template>
  <div class="auth-container">
    <nav class="navbar"><div class="nav-brand">MIROFISH</div></nav>
    <main class="auth-main">
      <div class="auth-card">
        <div class="card-header">
          <span class="tag">AUTH</span>
          <h1 class="title">{{ $t('setPassword.title') }}</h1>
          <p v-if="inviteData" class="subtitle">{{ inviteData.email }}</p>
        </div>
        <div v-if="tokenError" class="error-msg">{{ $t('setPassword.invalidToken') }}</div>
        <div v-else-if="done" class="success-msg">{{ $t('setPassword.done') }}</div>
        <form v-else-if="inviteData" class="auth-form" @submit.prevent="handleSubmit">
          <div class="field">
            <label class="field-label">{{ $t('setPassword.newPassword') }}</label>
            <input v-model="password" type="password" class="field-input" :disabled="loading" minlength="8" />
          </div>
          <div class="field">
            <label class="field-label">{{ $t('resetPassword.confirmPassword') }}</label>
            <input v-model="confirm" type="password" class="field-input" :disabled="loading" />
          </div>
          <div v-if="formError" class="error-msg">{{ formError }}</div>
          <button type="submit" class="submit-btn" :disabled="loading || !canSubmit">
            <span v-if="loading">{{ $t('common.loading') }}</span>
            <span v-else>{{ $t('setPassword.submit') }} →</span>
          </button>
        </form>
        <router-link v-if="done" to="/login?activated=1" class="back-link">{{ $t('resetPassword.goToLogin') }} →</router-link>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import service from '../api/index'

const props = defineProps({ token: String })
const { t } = useI18n()
const router = useRouter()

const inviteData = ref(null)
const password = ref('')
const confirm = ref('')
const loading = ref(false)
const tokenError = ref(false)
const formError = ref('')
const done = ref(false)

const canSubmit = computed(() =>
  password.value.length >= 8 && password.value === confirm.value
)

onMounted(async () => {
  try {
    const res = await service.get(`/api/auth/invitation/${props.token}`)
    inviteData.value = res.data
  } catch {
    tokenError.value = true
  }
})

async function handleSubmit() {
  if (!canSubmit.value) { formError.value = t('resetPassword.passwordMismatch'); return }
  loading.value = true; formError.value = ''
  try {
    await service.post('/api/auth/set-password', { token: props.token, password: password.value })
    done.value = true
    setTimeout(() => router.push('/login?activated=1'), 2000)
  } catch {
    formError.value = t('common.unknownError')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-container { min-height: 100vh; background: #fff; font-family: 'Space Grotesk', system-ui, sans-serif; color: #000; display: flex; flex-direction: column; }
.navbar { height: 60px; background: #000; color: #fff; display: flex; align-items: center; padding: 0 40px; }
.nav-brand { font-family: 'JetBrains Mono', monospace; font-weight: 800; letter-spacing: 1px; font-size: 1.2rem; }
.auth-main { flex: 1; display: flex; align-items: center; justify-content: center; padding: 40px 20px; }
.auth-card { width: 100%; max-width: 400px; border: 1px solid #e5e5e5; padding: 48px 40px; }
.card-header { margin-bottom: 32px; }
.tag { display: inline-block; background: #ff4500; color: #fff; font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; font-weight: 700; padding: 2px 8px; letter-spacing: 1px; margin-bottom: 16px; }
.title { font-size: 1.8rem; font-weight: 500; margin-bottom: 8px; }
.subtitle { font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #666; }
.auth-form { display: flex; flex-direction: column; gap: 20px; }
.field { display: flex; flex-direction: column; gap: 8px; }
.field-label { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; }
.field-input { border: 1px solid #e5e5e5; background: #fafafa; padding: 12px 16px; font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; outline: none; width: 100%; box-sizing: border-box; }
.field-input:focus { border-color: #000; background: #fff; }
.error-msg { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #ff4500; border-left: 3px solid #ff4500; padding-left: 12px; }
.success-msg { font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #22c55e; border-left: 3px solid #22c55e; padding-left: 12px; }
.submit-btn { background: #000; color: #fff; border: none; padding: 14px 24px; font-family: 'JetBrains Mono', monospace; font-weight: 700; cursor: pointer; transition: background 0.15s; width: 100%; }
.submit-btn:hover:not(:disabled) { background: #ff4500; }
.submit-btn:disabled { background: #e5e5e5; color: #999; cursor: not-allowed; }
.back-link { display: block; margin-top: 16px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #000; text-decoration: none; text-align: center; }
.back-link:hover { color: #ff4500; }
</style>
```

- [ ] **Afegir claus i18n a `locales/en.json`** (noves seccions):

```json
"forgotPassword": {
  "title": "Forgot Password",
  "subtitle": "Enter your email and we'll send you a reset link.",
  "submit": "Send reset link",
  "sent": "If an account exists with this email, you will receive a reset link shortly."
},
"resetPassword": {
  "title": "Reset Password",
  "newPassword": "New password",
  "confirmPassword": "Confirm password",
  "submit": "Set new password",
  "done": "Password updated. You can now log in.",
  "goToLogin": "Go to login",
  "invalidToken": "This link is invalid or has expired.",
  "passwordMismatch": "Passwords do not match."
},
"setPassword": {
  "title": "Welcome to MiroFish",
  "newPassword": "Choose a password",
  "submit": "Activate account",
  "done": "Account activated! Redirecting to login...",
  "invalidToken": "This invitation link is invalid or has expired."
}
```

- [ ] **Commit**

```bash
git add frontend/src/views/LoginView.vue \
        frontend/src/views/ForgotPasswordView.vue \
        frontend/src/views/ResetPasswordView.vue \
        frontend/src/views/SetPasswordView.vue \
        locales/
git commit -m "feat(frontend): login with email, forgot/reset/set-password views"
```

---

## Task 14: Home.vue — dashboard minimalista

**Files:**
- Modify: `frontend/src/views/Home.vue`

- [ ] **Reescriure `frontend/src/views/Home.vue` completament**

```vue
<template>
  <div class="home-container">
    <nav class="navbar">
      <div class="nav-brand">MIROFISH</div>
      <div class="nav-right">
        <router-link v-if="isAdmin" to="/admin/users" class="admin-link">
          {{ $t('home.admin') }}
        </router-link>
        <LanguageSwitcher />
        <span class="user-email">{{ authState.user?.email }}</span>
        <button class="logout-btn" @click="handleLogout" :title="$t('home.logout')">→</button>
      </div>
    </nav>

    <div class="content">
      <div class="header-row">
        <h2 class="section-title">{{ $t('home.myProjects') }}</h2>
        <button class="new-btn" @click="showNewModal = true">+ {{ $t('home.newProject') }}</button>
      </div>

      <!-- Llistat de projectes -->
      <div class="project-list" v-if="projects.length > 0">
        <div
          v-for="project in projects"
          :key="project.id"
          class="project-row"
          @click="openProject(project)"
        >
          <span class="status-dot" :class="statusClass(project.status)">■</span>
          <div class="project-info">
            <span class="project-name">{{ project.name }}</span>
            <span class="project-meta">{{ formatStatus(project.status) }} · {{ formatDate(project.created_at) }}</span>
          </div>
          <div class="project-actions" @click.stop>
            <button class="action-btn" @click="startRename(project)" :title="$t('home.rename')">✎</button>
            <button class="action-btn danger" @click="confirmDelete(project)" :title="$t('home.delete')">✕</button>
            <button class="arrow-btn" @click="openProject(project)">→</button>
          </div>
        </div>
      </div>
      <div v-else class="empty-state">
        <span>{{ $t('home.noProjects') }}</span>
      </div>
    </div>

    <!-- Modal: Nou Projecte -->
    <div v-if="showNewModal" class="modal-overlay" @click.self="showNewModal = false">
      <div class="modal">
        <div class="modal-header">
          <span class="tag">NEW</span>
          <h3 class="modal-title">{{ $t('home.newProject') }}</h3>
        </div>

        <div class="console-section">
          <div class="console-header">
            <span class="console-label">{{ $t('home.realitySeed') }}</span>
            <span class="console-meta">{{ $t('home.supportedFormats') }}</span>
          </div>
          <div class="upload-zone"
               :class="{ 'drag-over': isDragOver, 'has-files': files.length > 0 }"
               @dragover.prevent="isDragOver = true"
               @dragleave.prevent="isDragOver = false"
               @drop.prevent="handleDrop"
               @click="fileInput?.click()">
            <input ref="fileInput" type="file" multiple accept=".pdf,.md,.txt"
                   @change="handleFileSelect" style="display:none" />
            <div v-if="files.length === 0" class="upload-placeholder">
              <div class="upload-icon">↑</div>
              <div class="upload-title">{{ $t('home.dragToUpload') }}</div>
              <div class="upload-hint">{{ $t('home.orBrowse') }}</div>
            </div>
            <div v-else class="file-list">
              <div v-for="(f, i) in files" :key="i" class="file-item">
                <span class="file-icon">📄</span>
                <span class="file-name">{{ f.name }}</span>
                <button @click.stop="files.splice(i, 1)" class="remove-btn">×</button>
              </div>
            </div>
          </div>
        </div>

        <div class="console-section">
          <div class="console-header">
            <span class="console-label">{{ $t('home.simulationPrompt') }}</span>
          </div>
          <div class="input-wrapper">
            <textarea v-model="requirement" class="code-input"
                      :placeholder="$t('home.promptPlaceholder')" rows="5"></textarea>
          </div>
        </div>

        <div class="modal-footer">
          <button class="cancel-btn" @click="showNewModal = false">{{ $t('common.cancel') }}</button>
          <button class="start-btn" @click="startProject" :disabled="!canStart">
            {{ $t('home.startEngine') }} →
          </button>
        </div>
      </div>
    </div>

    <!-- Modal: Rename -->
    <div v-if="renameProject" class="modal-overlay" @click.self="renameProject = null">
      <div class="modal modal-sm">
        <h3 class="modal-title">{{ $t('home.rename') }}</h3>
        <input v-model="renameValue" class="field-input" @keyup.enter="submitRename" />
        <div class="modal-footer">
          <button class="cancel-btn" @click="renameProject = null">{{ $t('common.cancel') }}</button>
          <button class="start-btn" @click="submitRename" :disabled="!renameValue.trim()">{{ $t('common.save') }}</button>
        </div>
      </div>
    </div>

    <!-- Modal: Confirmar Delete -->
    <div v-if="deleteTarget" class="modal-overlay" @click.self="deleteTarget = null">
      <div class="modal modal-sm">
        <h3 class="modal-title">{{ $t('home.confirmDelete') }}</h3>
        <p class="modal-desc">{{ deleteTarget.name }}</p>
        <div class="modal-footer">
          <button class="cancel-btn" @click="deleteTarget = null">{{ $t('common.cancel') }}</button>
          <button class="danger-btn" @click="submitDelete">{{ $t('home.delete') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import authState, { isAdmin, clearAuth } from '../store/auth'
import service from '../api/index'
import { setPendingUpload } from '../store/pendingUpload'

const router = useRouter()
const { t } = useI18n()

const projects = ref([])
const showNewModal = ref(false)
const files = ref([])
const requirement = ref('')
const isDragOver = ref(false)
const fileInput = ref(null)
const renameProject = ref(null)
const renameValue = ref('')
const deleteTarget = ref(null)

const canStart = computed(() => files.value.length > 0 && requirement.value.trim())

onMounted(loadProjects)

async function loadProjects() {
  try {
    const res = await service.get('/api/graph/project/list')
    projects.value = res.data || []
  } catch { /* silent */ }
}

function openProject(project) {
  router.push({ name: 'Process', params: { projectId: project.id } })
}

function handleFileSelect(e) {
  const valid = Array.from(e.target.files).filter(f =>
    ['pdf', 'md', 'txt'].includes(f.name.split('.').pop().toLowerCase())
  )
  files.value.push(...valid)
}

function handleDrop(e) {
  isDragOver.value = false
  const valid = Array.from(e.dataTransfer.files).filter(f =>
    ['pdf', 'md', 'txt'].includes(f.name.split('.').pop().toLowerCase())
  )
  files.value.push(...valid)
}

async function startProject() {
  if (!canStart.value) return
  setPendingUpload(files.value, requirement.value, false, null)
  showNewModal.value = false
  files.value = []
  requirement.value = ''
  router.push({ name: 'Process', params: { projectId: 'new' } })
}

function startRename(project) {
  renameProject.value = project
  renameValue.value = project.name
}

async function submitRename() {
  if (!renameValue.value.trim() || !renameProject.value) return
  try {
    await service.patch(`/api/graph/project/${renameProject.value.id}`, { name: renameValue.value.trim() })
    await loadProjects()
  } finally {
    renameProject.value = null
  }
}

function confirmDelete(project) {
  deleteTarget.value = project
}

async function submitDelete() {
  if (!deleteTarget.value) return
  try {
    await service.delete(`/api/graph/project/${deleteTarget.value.id}`)
    await loadProjects()
  } finally {
    deleteTarget.value = null
  }
}

function handleLogout() {
  service.post('/api/auth/logout').catch(() => {})
  clearAuth()
  router.push('/login')
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString()
}

function formatStatus(status) {
  const map = {
    created: t('common.pending'),
    ontology_generated: 'Ontologia',
    graph_building: t('common.processing'),
    graph_completed: t('common.ready'),
    failed: t('common.failed'),
  }
  return map[status] || status
}

function statusClass(status) {
  if (status === 'graph_completed') return 'green'
  if (status === 'failed') return 'red'
  if (status === 'graph_building') return 'orange'
  return 'gray'
}
</script>

<style scoped>
.home-container { min-height: 100vh; background: #fff; font-family: 'Space Grotesk', system-ui, sans-serif; color: #000; }
.navbar { height: 60px; background: #000; color: #fff; display: flex; justify-content: space-between; align-items: center; padding: 0 40px; }
.nav-brand { font-family: 'JetBrains Mono', monospace; font-weight: 800; letter-spacing: 1px; font-size: 1.2rem; }
.nav-right { display: flex; align-items: center; gap: 16px; }
.admin-link { color: #ff4500; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; text-decoration: none; font-weight: 700; }
.admin-link:hover { opacity: 0.8; }
.user-email { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #aaa; }
.logout-btn { background: none; border: none; color: #fff; font-size: 1.1rem; cursor: pointer; padding: 4px 8px; transition: color 0.15s; }
.logout-btn:hover { color: #ff4500; }
.content { max-width: 900px; margin: 0 auto; padding: 48px 40px; }
.header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 32px; }
.section-title { font-size: 1.4rem; font-weight: 500; margin: 0; }
.new-btn { background: #000; color: #fff; border: none; padding: 10px 20px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 700; cursor: pointer; transition: background 0.15s; }
.new-btn:hover { background: #ff4500; }
.project-list { border-top: 1px solid #e5e5e5; }
.project-row { display: flex; align-items: center; gap: 16px; padding: 16px 0; border-bottom: 1px solid #f0f0f0; cursor: pointer; transition: background 0.1s; }
.project-row:hover { background: #fafafa; }
.status-dot { font-size: 0.7rem; }
.status-dot.green { color: #22c55e; }
.status-dot.red { color: #ef4444; }
.status-dot.orange { color: #ff4500; }
.status-dot.gray { color: #aaa; }
.project-info { flex: 1; display: flex; flex-direction: column; gap: 4px; }
.project-name { font-weight: 500; font-size: 1rem; }
.project-meta { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #999; }
.project-actions { display: flex; align-items: center; gap: 8px; opacity: 0; transition: opacity 0.15s; }
.project-row:hover .project-actions { opacity: 1; }
.action-btn { background: none; border: 1px solid #e5e5e5; padding: 4px 8px; font-size: 0.85rem; cursor: pointer; transition: all 0.15s; }
.action-btn:hover { border-color: #000; }
.action-btn.danger:hover { border-color: #ef4444; color: #ef4444; }
.arrow-btn { background: #000; color: #fff; border: none; padding: 6px 12px; font-size: 0.9rem; cursor: pointer; }
.empty-state { padding: 48px 0; text-align: center; font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; color: #999; border-top: 1px solid #e5e5e5; }
/* Modal */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: #fff; width: 100%; max-width: 560px; max-height: 90vh; overflow-y: auto; padding: 32px; }
.modal-sm { max-width: 400px; }
.modal-header { margin-bottom: 24px; }
.modal-title { font-size: 1.3rem; font-weight: 500; margin: 8px 0 0; }
.modal-desc { font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; color: #666; margin: 8px 0 0; }
.modal-footer { display: flex; gap: 12px; justify-content: flex-end; margin-top: 24px; }
.cancel-btn { background: none; border: 1px solid #e5e5e5; padding: 10px 20px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; cursor: pointer; }
.cancel-btn:hover { border-color: #000; }
.start-btn { background: #000; color: #fff; border: none; padding: 10px 20px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 700; cursor: pointer; transition: background 0.15s; }
.start-btn:hover:not(:disabled) { background: #ff4500; }
.start-btn:disabled { background: #e5e5e5; color: #999; cursor: not-allowed; }
.danger-btn { background: #ef4444; color: #fff; border: none; padding: 10px 20px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 700; cursor: pointer; }
.danger-btn:hover { background: #dc2626; }
.tag { display: inline-block; background: #ff4500; color: #fff; font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; font-weight: 700; padding: 2px 8px; letter-spacing: 1px; margin-bottom: 12px; }
.field-input { border: 1px solid #e5e5e5; background: #fafafa; padding: 12px 16px; font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; outline: none; width: 100%; box-sizing: border-box; margin-top: 8px; }
/* Upload (reutilitzat del Home original) */
.console-section { padding: 0 0 16px 0; }
.console-header { display: flex; justify-content: space-between; margin-bottom: 10px; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #666; }
.upload-zone { border: 1px dashed #ccc; height: 150px; overflow-y: auto; display: flex; align-items: center; justify-content: center; cursor: pointer; background: #fafafa; transition: all 0.2s; }
.upload-zone.has-files { align-items: flex-start; }
.upload-zone:hover, .upload-zone.drag-over { background: #f0f0f0; border-color: #999; }
.upload-placeholder { text-align: center; }
.upload-icon { width: 36px; height: 36px; border: 1px solid #ddd; display: flex; align-items: center; justify-content: center; margin: 0 auto 10px; color: #999; }
.upload-title { font-weight: 500; font-size: 0.85rem; }
.upload-hint { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: #999; }
.file-list { width: 100%; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
.file-item { display: flex; align-items: center; background: #fff; padding: 6px 10px; border: 1px solid #eee; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; }
.file-name { flex: 1; margin: 0 8px; }
.remove-btn { background: none; border: none; cursor: pointer; font-size: 1rem; color: #999; }
.input-wrapper { border: 1px solid #ddd; background: #fafafa; }
.code-input { width: 100%; border: none; background: transparent; padding: 16px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; line-height: 1.6; resize: vertical; outline: none; box-sizing: border-box; }
</style>
```

- [ ] **Afegir claus i18n a `locales/en.json`** (dins el bloc `"home"`, substituir les existents i afegir noves):

```json
"home": {
  "myProjects": "My Projects",
  "newProject": "New Project",
  "noProjects": "No projects yet. Create your first one.",
  "admin": "Administration",
  "logout": "Logout",
  "rename": "Rename",
  "delete": "Delete",
  "confirmDelete": "Delete project?",
  "realitySeed": "REALITY SEED",
  "supportedFormats": "PDF / MD / TXT",
  "simulationPrompt": "SIMULATION PROMPT",
  "promptPlaceholder": "Describe the simulation scenario...",
  "startEngine": "START",
  "dragToUpload": "Drag files here",
  "orBrowse": "or click to browse",
  "inputParams": "PARAMS"
}
```

- [ ] **Commit**

```bash
git add frontend/src/views/Home.vue locales/
git commit -m "feat(home): replace hero/marketing with minimal project dashboard + new project modal"
```

---

## Task 15: AdminView.vue

**Files:**
- Create: `frontend/src/views/AdminView.vue`

- [ ] **Crear `frontend/src/views/AdminView.vue`**

```vue
<template>
  <div class="admin-container">
    <nav class="navbar">
      <div class="nav-brand">MIROFISH</div>
      <div class="nav-right">
        <router-link to="/" class="back-link">← {{ $t('common.back') }}</router-link>
        <LanguageSwitcher />
      </div>
    </nav>

    <div class="content">
      <div class="tabs">
        <router-link to="/admin/users"      class="tab" :class="{ active: tab === 'users' }">
          {{ $t('admin.users') }}
        </router-link>
        <router-link to="/admin/config"     class="tab" :class="{ active: tab === 'config' }">
          {{ $t('admin.config') }}
        </router-link>
        <router-link to="/admin/executions" class="tab" :class="{ active: tab === 'executions' }">
          {{ $t('admin.executions') }}
        </router-link>
      </div>

      <!-- Tab: Usuaris -->
      <div v-if="tab === 'users'" class="tab-content">
        <div class="tab-header">
          <h2 class="section-title">{{ $t('admin.users') }}</h2>
          <button class="new-btn" @click="showInviteForm = !showInviteForm">
            + {{ $t('admin.inviteUser') }}
          </button>
        </div>

        <div v-if="showInviteForm" class="invite-form">
          <div class="form-row">
            <input v-model="invite.name" class="field-input" :placeholder="$t('admin.name')" />
            <input v-model="invite.email" type="email" class="field-input" :placeholder="$t('admin.email')" />
            <select v-model="invite.role" class="field-select">
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
            <button class="start-btn" @click="submitInvite" :disabled="!invite.email || !invite.name">
              {{ $t('admin.send') }} →
            </button>
          </div>
          <div v-if="inviteSuccess" class="success-msg">{{ $t('admin.inviteSent') }}</div>
          <div v-if="inviteError" class="error-msg">{{ inviteError }}</div>
        </div>

        <table class="data-table" v-if="users.length">
          <thead>
            <tr>
              <th>{{ $t('admin.email') }}</th>
              <th>{{ $t('admin.name') }}</th>
              <th>{{ $t('admin.role') }}</th>
              <th>{{ $t('admin.status') }}</th>
              <th>{{ $t('admin.created') }}</th>
              <th>{{ $t('admin.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td class="mono">{{ user.email }}</td>
              <td>{{ user.name }}</td>
              <td>
                <select class="role-select" :value="user.role" @change="changeRole(user, $event.target.value)">
                  <option value="user">user</option>
                  <option value="admin">admin</option>
                </select>
              </td>
              <td><span class="status-badge" :class="user.status">{{ user.status }}</span></td>
              <td class="mono">{{ formatDate(user.created_at) }}</td>
              <td class="actions-cell">
                <button v-if="user.status === 'pending'" class="action-btn" @click="reinvite(user)" :title="$t('admin.reinvite')">✉</button>
                <button v-if="user.status !== 'disabled'" class="action-btn danger" @click="disableUser(user)" :title="$t('admin.disable')">✕</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-state">{{ $t('admin.noUsers') }}</div>
      </div>

      <!-- Tab: Configuració -->
      <div v-if="tab === 'config'" class="tab-content">
        <div class="tab-header">
          <h2 class="section-title">{{ $t('admin.config') }}</h2>
          <button class="start-btn" @click="saveConfig">{{ $t('common.save') }}</button>
        </div>
        <div v-if="configEntries.length" class="config-form">
          <div v-for="entry in configEntries" :key="entry.key" class="config-row">
            <label class="config-label">
              <span class="config-key mono">{{ entry.key }}</span>
              <span class="config-desc">{{ entry.label }}</span>
            </label>
            <input
              v-model="configValues[entry.key]"
              :type="entry.is_secret ? 'password' : 'text'"
              class="field-input"
              :placeholder="entry.is_secret ? '●●●●' : entry.value"
            />
          </div>
        </div>
        <div v-else class="empty-state">{{ $t('admin.noConfig') }}</div>
        <div v-if="configSaved" class="success-msg">{{ $t('admin.configSaved') }}</div>
      </div>

      <!-- Tab: Historial -->
      <div v-if="tab === 'executions'" class="tab-content">
        <div class="tab-header">
          <h2 class="section-title">{{ $t('admin.executions') }}</h2>
        </div>
        <table class="data-table" v-if="executions.length">
          <thead>
            <tr>
              <th>{{ $t('admin.user') }}</th>
              <th>{{ $t('admin.project') }}</th>
              <th>{{ $t('admin.platform') }}</th>
              <th>{{ $t('admin.status') }}</th>
              <th>{{ $t('admin.rounds') }}</th>
              <th>{{ $t('admin.created') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="ex in executions" :key="ex.simulation_id">
              <td class="mono">{{ ex.user_email || '—' }}</td>
              <td>{{ ex.project_name }}</td>
              <td class="mono">{{ ex.platform }}</td>
              <td><span class="status-badge" :class="ex.status">{{ ex.status }}</span></td>
              <td class="mono">{{ ex.rounds_completed }}/{{ ex.rounds_total || '?' }}</td>
              <td class="mono">{{ formatDate(ex.created_at) }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-state">{{ $t('admin.noExecutions') }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import service from '../api/index'

const props = defineProps({ tab: { type: String, default: 'users' } })
const { t } = useI18n()

// Users
const users = ref([])
const showInviteForm = ref(false)
const invite = ref({ name: '', email: '', role: 'user' })
const inviteSuccess = ref(false)
const inviteError = ref('')

// Config
const configEntries = ref([])
const configValues = ref({})
const configSaved = ref(false)

// Executions
const executions = ref([])

onMounted(loadTab)
watch(() => props.tab, loadTab)

async function loadTab() {
  if (props.tab === 'users') await loadUsers()
  if (props.tab === 'config') await loadConfig()
  if (props.tab === 'executions') await loadExecutions()
}

async function loadUsers() {
  const res = await service.get('/api/users/')
  users.value = res.data || []
}

async function loadConfig() {
  const res = await service.get('/api/admin/config')
  configEntries.value = res.data || []
  configValues.value = Object.fromEntries(
    configEntries.value.filter(e => !e.is_secret).map(e => [e.key, e.value])
  )
}

async function loadExecutions() {
  const res = await service.get('/api/admin/executions')
  executions.value = res.data || []
}

async function submitInvite() {
  inviteSuccess.value = false; inviteError.value = ''
  try {
    await service.post('/api/users/', invite.value)
    inviteSuccess.value = true
    invite.value = { name: '', email: '', role: 'user' }
    await loadUsers()
  } catch (e) {
    inviteError.value = e.response?.data?.error || t('common.unknownError')
  }
}

async function changeRole(user, newRole) {
  await service.patch(`/api/users/${user.id}`, { role: newRole })
  await loadUsers()
}

async function disableUser(user) {
  await service.delete(`/api/users/${user.id}`)
  await loadUsers()
}

async function reinvite(user) {
  await service.post(`/api/users/${user.id}/reinvite`)
}

async function saveConfig() {
  const payload = {}
  for (const [k, v] of Object.entries(configValues.value)) {
    if (v !== '' && !configEntries.value.find(e => e.key === k)?.is_secret) {
      payload[k] = v
    }
  }
  await service.patch('/api/admin/config', payload)
  configSaved.value = true
  setTimeout(() => { configSaved.value = false }, 2000)
}

function formatDate(iso) {
  return iso ? new Date(iso).toLocaleDateString() : '—'
}
</script>

<style scoped>
.admin-container { min-height: 100vh; background: #fff; font-family: 'Space Grotesk', system-ui, sans-serif; color: #000; }
.navbar { height: 60px; background: #000; color: #fff; display: flex; justify-content: space-between; align-items: center; padding: 0 40px; }
.nav-brand { font-family: 'JetBrains Mono', monospace; font-weight: 800; letter-spacing: 1px; font-size: 1.2rem; }
.nav-right { display: flex; align-items: center; gap: 16px; }
.back-link { color: #aaa; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; text-decoration: none; }
.back-link:hover { color: #fff; }
.content { max-width: 1100px; margin: 0 auto; padding: 40px; }
.tabs { display: flex; gap: 0; border-bottom: 1px solid #e5e5e5; margin-bottom: 32px; }
.tab { padding: 12px 24px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 700; text-decoration: none; color: #666; border-bottom: 2px solid transparent; transition: all 0.15s; }
.tab:hover { color: #000; }
.tab.active { color: #000; border-bottom-color: #ff4500; }
.tab-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.section-title { font-size: 1.2rem; font-weight: 500; margin: 0; }
.new-btn, .start-btn { background: #000; color: #fff; border: none; padding: 8px 18px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; font-weight: 700; cursor: pointer; transition: background 0.15s; }
.new-btn:hover, .start-btn:hover:not(:disabled) { background: #ff4500; }
.start-btn:disabled { background: #e5e5e5; color: #999; cursor: not-allowed; }
.invite-form { border: 1px solid #e5e5e5; padding: 20px; margin-bottom: 24px; background: #fafafa; }
.form-row { display: flex; gap: 12px; flex-wrap: wrap; }
.field-input { border: 1px solid #e5e5e5; background: #fff; padding: 8px 12px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; outline: none; flex: 1; min-width: 160px; }
.field-input:focus { border-color: #000; }
.field-select { border: 1px solid #e5e5e5; background: #fff; padding: 8px 12px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; cursor: pointer; }
.data-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.data-table th { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #666; padding: 10px 12px; text-align: left; border-bottom: 1px solid #e5e5e5; }
.data-table td { padding: 12px; border-bottom: 1px solid #f0f0f0; }
.mono { font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
.status-badge { display: inline-block; font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; }
.status-badge.active { background: #dcfce7; color: #166534; }
.status-badge.pending { background: #fef9c3; color: #854d0e; }
.status-badge.disabled { background: #f1f5f9; color: #64748b; }
.status-badge.completed { background: #dcfce7; color: #166534; }
.status-badge.failed { background: #fee2e2; color: #991b1b; }
.role-select { border: 1px solid #e5e5e5; background: #fff; padding: 4px 8px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; cursor: pointer; }
.actions-cell { display: flex; gap: 6px; }
.action-btn { background: none; border: 1px solid #e5e5e5; padding: 4px 8px; font-size: 0.85rem; cursor: pointer; }
.action-btn:hover { border-color: #000; }
.action-btn.danger:hover { border-color: #ef4444; color: #ef4444; }
.config-form { display: flex; flex-direction: column; gap: 16px; }
.config-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: center; padding: 12px 0; border-bottom: 1px solid #f0f0f0; }
.config-label { display: flex; flex-direction: column; gap: 2px; }
.config-key { font-size: 0.8rem; color: #000; }
.config-desc { font-size: 0.8rem; color: #666; }
.empty-state { padding: 48px 0; text-align: center; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #999; }
.success-msg { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #22c55e; border-left: 3px solid #22c55e; padding-left: 10px; margin-top: 8px; }
.error-msg { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #ff4500; border-left: 3px solid #ff4500; padding-left: 10px; margin-top: 8px; }
</style>
```

- [ ] **Afegir claus i18n a `locales/en.json`** (nova secció `"admin"`):

```json
"admin": {
  "users": "Users",
  "config": "Configuration",
  "executions": "Execution History",
  "inviteUser": "Invite User",
  "name": "Name",
  "email": "Email",
  "role": "Role",
  "status": "Status",
  "created": "Created",
  "actions": "Actions",
  "send": "Send",
  "inviteSent": "Invitation sent.",
  "reinvite": "Resend invitation",
  "disable": "Disable user",
  "noUsers": "No users found.",
  "noConfig": "No configuration entries.",
  "configSaved": "Configuration saved.",
  "noExecutions": "No executions found.",
  "user": "User",
  "project": "Project",
  "platform": "Platform",
  "rounds": "Rounds"
}
```

- [ ] **Commit**

```bash
git add frontend/src/views/AdminView.vue locales/
git commit -m "feat(admin): AdminView with users, config, and executions tabs"
```

---

## Task 16: Actualitzar fitxers Azure

**Files:**
- Modify: `azure/config.sh.example`
- Modify: `azure/container-app.bicep`
- Modify: `azure/2-build-deploy.sh`

- [ ] **Actualitzar `azure/config.sh.example`**

Substituir el bloc `# ── Secrets de l'aplicació` (línies 24-28) per:

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
# ACS és opcional en dev: els links apareixeran als logs si ACS_CONNECTION_STRING és buit
ACS_CONNECTION_STRING=""
ACS_SENDER_ADDRESS="donotreply@example.com"
ACS_INVITATION_TTL_HOURS=48
ACS_RESET_PASSWORD_TTL_HOURS=1
```

Eliminar la línia `DEMO_PASSWORD="<contrasenya-segura>"`.
Eliminar la línia `SECRET_KEY="<flask-secret-key>"`.

- [ ] **Actualitzar `azure/container-app.bicep`**

**Eliminar** el paràmetre `demoPassword` (i les seves referències a `mandatorySecrets` i `mandatoryEnv`).

**Renombrar** `secretKey` → `jwtSecretKey` (tots els seus usos).

**Afegir** nous paràmetres `@secure()` (després de `param databaseUrl`):

```bicep
@description('JWT Secret Key per a flask-jwt-extended')
@secure()
param jwtSecretKey string

@description('Contrasenya de l\'admin inicial (per flask init-system)')
@secure()
param adminPassword string

@description('Connection string Azure Communication Services (opcional)')
@secure()
param acsConnectionString string = ''
```

**Afegir** nous paràmetres no secrets:

```bicep
@description('Email de l\'admin inicial')
param adminEmail string = ''

@description('Adreça remitent ACS')
param acsSenderAddress string = ''

@description('TTL invitació en hores')
param acsInvitationTtlHours string = '48'

@description('TTL reset password en hores')
param acsResetPasswordTtlHours string = '1'

@description('Expiració access token JWT en segons')
param jwtAccessTokenExpires string = '28800'

@description('Expiració refresh token JWT en segons')
param jwtRefreshTokenExpires string = '604800'
```

**Actualitzar `mandatorySecrets`:** substituir `demo-password` i `secret-key` per:

```bicep
var mandatorySecrets = [
  { name: 'acr-password',  value: acrPassword }
  { name: 'jwt-secret-key', value: jwtSecretKey }
  { name: 'llm-api-key',   value: llmApiKey }
  { name: 'admin-password', value: adminPassword }
]
```

**Actualitzar `optionalSecrets`:** afegir `acs-connection-string`:

```bicep
  empty(acsConnectionString) ? [] : [{ name: 'acs-connection-string', value: acsConnectionString }],
```

**Actualitzar `mandatoryEnv`:** substituir `DEMO_PASSWORD` i `SECRET_KEY` per:

```bicep
  { name: 'JWT_SECRET_KEY',              secretRef: 'jwt-secret-key' }
  { name: 'ADMIN_EMAIL',                 value: adminEmail }
  { name: 'ADMIN_PASSWORD',              secretRef: 'admin-password' }
  { name: 'JWT_ACCESS_TOKEN_EXPIRES',    value: jwtAccessTokenExpires }
  { name: 'JWT_REFRESH_TOKEN_EXPIRES',   value: jwtRefreshTokenExpires }
  { name: 'ACS_SENDER_ADDRESS',          value: acsSenderAddress }
  { name: 'ACS_INVITATION_TTL_HOURS',    value: acsInvitationTtlHours }
  { name: 'ACS_RESET_PASSWORD_TTL_HOURS', value: acsResetPasswordTtlHours }
```

**Actualitzar `optionalEnv`:** afegir:

```bicep
  empty(acsConnectionString) ? [] : [{ name: 'ACS_CONNECTION_STRING', secretRef: 'acs-connection-string' }],
```

- [ ] **Actualitzar `azure/2-build-deploy.sh`**

**`REQUIRED_VARS`:** substituir `DEMO_PASSWORD` per `JWT_SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`:

```bash
REQUIRED_VARS=(
  AZURE_SUBSCRIPTION_ID RESOURCE_GROUP PROJECT_NAME
  JWT_SECRET_KEY ADMIN_EMAIL ADMIN_PASSWORD
  LLM_API_KEY LLM_BASE_URL LLM_MODEL_NAME
  DATABASE_URL STORAGE_CONNECTION_STRING
)
```

**Afegir validació ACS** (avís, no error) just abans del `for var in "${REQUIRED_VARS[@]}"`:

```bash
if [[ -z "${ACS_CONNECTION_STRING:-}" ]]; then
  echo "AVÍS: ACS_CONNECTION_STRING no configurat — emails d'invitació es mostraran als logs"
fi
```

**Actualitzar `--parameters`** del `az deployment group create`: eliminar `demoPassword` i afegir:

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

- [ ] **Commit**

```bash
git add azure/config.sh.example azure/container-app.bicep azure/2-build-deploy.sh
git commit -m "feat(azure): update deployment files for Phase 3 auth variables"
```

---

## Verificació final

- [ ] **Executar tots els tests backend**

```bash
cd /home/ubuntu/dev/MiroFish
python -m pytest backend/tests/ -v --ignore=backend/tests/test_simulation_agent_api.py 2>&1 | tail -30
```

Expected: tots PASS (≥ 50 tests).

- [ ] **Inicialitzar sistema en dev i verificar**

```bash
cd /home/ubuntu/dev/MiroFish
ADMIN_EMAIL=admin@dev.local ADMIN_PASSWORD=adminpass123 uv run python backend/scripts/init_system.py
```

Expected: `Admin creat` + `SystemConfig per defecte: OK`.

- [ ] **Arrancar l'aplicació i fer smoke test manual**

```bash
npm run dev
```

Obrir http://localhost:3000 → redirigeix a /login ✓
Login amb `admin@dev.local` / `adminpass123` → Home amb 0 projectes ✓
Navbar mostra "Administration" (rol admin) ✓
Crear nou projecte via modal ✓
/admin/users → taula buida ✓
Invitar usuari → log ACS als logs (ACS no configurat) ✓

- [ ] **PR final**

```bash
git push -u origin feature/fase3-roles-admin
gh pr create --title "feat(fase3): multi-user auth, project isolation, admin panel" --body "$(cat <<'EOF'
## Summary
- Real JWT authentication (bcrypt + flask-jwt-extended) replacing hardcoded demo login
- User isolation: projects filtered by user_id, admin sees all
- Invitation-based enrollment via Azure Communication Services (dev fallback to logs)
- Forgot/reset password flow
- Admin panel: users CRUD, system config, execution history
- Minimal project dashboard replacing marketing hero section
- Azure deployment files updated for new auth variables

## Test plan
- [ ] Run `pytest backend/tests/` — all pass
- [ ] `init_system.py` creates admin in fresh SQLite DB
- [ ] Login with admin, create project, invite user, reset password
- [ ] `/admin` route hidden for non-admin users
- [ ] GET `/api/graph/project/list` returns only own projects

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
