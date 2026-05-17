# System Config Expanded Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ampliar `system_config` amb totes les variables de comportament del sistema (LLM principal i secundaris, simulació, informe, email), afegir una funció `get_config(key, default)` amb prevalença BD > env, i millorar la UI de configuració de l'AdminView tractant els secrets de forma segura (mai surten del backend).

**Architecture:** Nou fitxer `backend/app/config_db.py` exposa `get_config(key, default)` que llegeix la BD i fa fallback al default. L'API GET no retorna valors de claus secretes (retorna `value: null, has_value: bool`). El PATCH ignora claus secretes amb valor buit. `init_system.py` s'amplia amb totes les claus noves. El frontend agrupa les claus per `group` i gestiona els camps secrets amb inputs buits.

**Tech Stack:** Python / Flask / SQLAlchemy (backend); Vue 3 + vue-i18n (frontend); pytest (tests)

---

## Fitxers afectats

| Fitxer | Acció |
|---|---|
| `backend/app/config_db.py` | Crear — helper `get_config` |
| `backend/tests/test_config_db.py` | Crear — tests del helper |
| `backend/app/api/admin.py` | Modificar — GET retorna `has_value` per secrets; PATCH ignora secrets buits |
| `backend/tests/test_admin_api.py` | Modificar — tests nous per a comportament de secrets |
| `backend/scripts/init_system.py` | Modificar — afegir totes les claus noves |
| `backend/app/services/report_agent.py` | Modificar — llegir MAX_TOOL_CALLS, MAX_REFLECTION_ROUNDS des de BD |
| `backend/app/api/simulation.py` | Modificar — max_rounds per defecte des de BD |
| `backend/app/utils/llm_client.py` | Modificar — llegir api_key, base_url, model, provider des de BD |
| `backend/app/graph/graphiti_backend.py` | Modificar — llegir claus llm.embed.* i llm.small.* des de BD |
| `backend/scripts/run_parallel_simulation.py` | Modificar — llegir claus llm.boost.* des de BD |
| `frontend/src/views/AdminView.vue` | Modificar — agrupació per grup, gestió de secrets |

---

## Task 1: Helper `get_config` amb tests

**Files:**
- Create: `backend/app/config_db.py`
- Create: `backend/tests/test_config_db.py`

- [ ] **Step 1: Escriure el test que fallarà**

```python
# backend/tests/test_config_db.py
"""Tests per a get_config (prevalença BD > env)."""
import pytest


@pytest.fixture
def app_ctx(in_memory_db):
    """Context Flask amb BD en memòria."""
    from unittest.mock import MagicMock, patch
    import backend.app.db as db_module
    saved_engine = db_module._engine
    saved_session = db_module._SessionLocal

    def _noop(url):
        db_module._engine = saved_engine
        db_module._SessionLocal = saved_session

    with patch('backend.app.db.init_db', side_effect=_noop):
        from backend.app import create_app
        app = create_app()
    app.config['TESTING'] = True
    app.extensions['storage'] = MagicMock()
    db_module._engine = saved_engine
    db_module._SessionLocal = saved_session
    with app.app_context():
        yield app


def _insert_config(key, value, value_type='string', is_secret=False):
    from backend.app.models.db_models import SystemConfigModel
    from backend.app.db import get_session
    with get_session() as db:
        db.merge(SystemConfigModel(
            key=key, value=value, value_type=value_type,
            group='test', label='', description='', is_secret=is_secret
        ))
        db.commit()


def test_returns_default_when_key_missing(app_ctx):
    from backend.app.config_db import get_config
    result = get_config('nonexistent.key', default='fallback')
    assert result == 'fallback'


def test_returns_string_value_from_db(app_ctx):
    from backend.app.config_db import get_config
    _insert_config('llm.model_name', 'gpt-4o', 'string')
    assert get_config('llm.model_name', 'default-model') == 'gpt-4o'


def test_casts_int_value(app_ctx):
    from backend.app.config_db import get_config
    _insert_config('simulation.max_rounds', '15', 'int')
    result = get_config('simulation.max_rounds', 10)
    assert result == 15
    assert isinstance(result, int)


def test_casts_float_value(app_ctx):
    from backend.app.config_db import get_config
    _insert_config('report.temperature', '0.7', 'float')
    result = get_config('report.temperature', 0.5)
    assert abs(result - 0.7) < 1e-9
    assert isinstance(result, float)


def test_returns_default_when_value_is_none(app_ctx):
    from backend.app.config_db import get_config
    _insert_config('llm.model_name', None, 'string')
    assert get_config('llm.model_name', 'fallback') == 'fallback'


def test_max_tokens_zero_returns_none(app_ctx):
    from backend.app.config_db import get_config
    _insert_config('llm.max_tokens', '0', 'int')
    assert get_config('llm.max_tokens', None) is None


def test_returns_default_on_db_error(app_ctx):
    """Si la BD no és accessible, retorna el default sense llançar excepció."""
    import backend.app.db as db_module
    from backend.app.config_db import get_config
    saved = db_module._SessionLocal
    db_module._SessionLocal = None
    try:
        result = get_config('llm.model_name', 'safe-default')
        assert result == 'safe-default'
    finally:
        db_module._SessionLocal = saved
```

- [ ] **Step 2: Executar per verificar que falla**

```bash
cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/test_config_db.py -v 2>&1 | head -30
```

Expected: `ImportError` o `ModuleNotFoundError` — `config_db` no existeix encara.

- [ ] **Step 3: Crear `backend/app/config_db.py`**

```python
# backend/app/config_db.py
"""Helper get_config: prevalença BD > env."""
from __future__ import annotations
from typing import Any


def get_config(key: str, default: Any = None) -> Any:
    """Llegeix una clau de system_config; fallback a default si no hi ha valor.

    Llei especial: si value_type=='int' i el valor és '0', retorna None
    (0 = sense límit explícit per a max_tokens).
    """
    try:
        from .db import get_session
        from .models.db_models import SystemConfigModel
        with get_session() as db:
            entry = db.get(SystemConfigModel, key)
            if entry is None or entry.value is None or entry.value == '':
                return default
            return _cast(entry.value, entry.value_type, default)
    except Exception:
        return default


def _cast(value: str, value_type: str, default: Any) -> Any:
    try:
        if value_type == 'int':
            cast = int(value)
            return None if cast == 0 else cast
        if value_type == 'float':
            return float(value)
        if value_type == 'bool':
            return value.lower() in ('true', '1', 'yes')
        return value
    except (ValueError, TypeError):
        return default
```

- [ ] **Step 4: Executar tests i verificar que passen**

```bash
cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/test_config_db.py -v
```

Expected: tots els tests en verd.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/dev/MiroFish && git add backend/app/config_db.py backend/tests/test_config_db.py && git commit -m "feat(config): add get_config helper with DB > env precedence"
```

---

## Task 2: Ampliar `init_system.py` amb totes les claus

**Files:**
- Modify: `backend/scripts/init_system.py`

- [ ] **Step 1: Substituir el bloc `defaults` a `init_system.py`**

Localitza el bloc (línies ~62–76):
```python
        defaults = [
            ('llm.model_name',  Config.LLM_MODEL_NAME,     'string', 'llm',    'Model LLM',        '', False),
            ('llm.base_url',    Config.LLM_BASE_URL,        'string', 'llm',    'URL base LLM',     '', False),
            ('llm.api_key',     Config.LLM_API_KEY or '',   'string', 'llm',    'API Key LLM',      '', True),
            ('limits.max_projects_per_user', '20',          'int',    'limits', 'Màx. projectes',   '', False),
            ('limits.max_simulations',       '10',          'int',    'limits', 'Màx. simulacions', '', False),
        ]
```

Substitueix-lo per:
```python
        defaults = [
            # ── LLM principal ────────────────────────────────────────────
            ('llm.api_key',        Config.LLM_API_KEY or '',    'string', 'llm', 'API Key LLM',             'Clau API del LLM principal',                      True),
            ('llm.base_url',       Config.LLM_BASE_URL,         'string', 'llm', 'URL base LLM',            'URL base OpenAI-compatible del LLM principal',    False),
            ('llm.model_name',     Config.LLM_MODEL_NAME,       'string', 'llm', 'Model LLM',               'Nom del model del LLM principal',                 False),
            ('llm.max_tokens',     '0',                         'int',    'llm', 'Max tokens LLM',          'Límit de tokens de sortida (0 = sense límit)',     False),
            ('llm.provider',       Config.LLM_PROVIDER or '',   'string', 'llm', 'Proveïdor LLM',           'Deixa buit per OpenAI-compatible; "gemini" per Google AI Studio', False),
            # ── LLM Boost (OASIS) ────────────────────────────────────────
            ('llm.boost.api_key',    os.environ.get('LLM_BOOST_API_KEY', ''),    'string', 'llm', 'API Key LLM Boost',    'Clau API del LLM ràpid per a OASIS (opcional)',                   True),
            ('llm.boost.base_url',   os.environ.get('LLM_BOOST_BASE_URL', ''),   'string', 'llm', 'URL base LLM Boost',   'URL base del LLM ràpid per a OASIS',                              False),
            ('llm.boost.model_name', os.environ.get('LLM_BOOST_MODEL_NAME', ''), 'string', 'llm', 'Model LLM Boost',      'Model del LLM ràpid per a OASIS',                                 False),
            # ── LLM Embed (Graphiti) ─────────────────────────────────────
            ('llm.embed.api_key',    os.environ.get('LLM_EMBED_API_KEY', '') or Config.LLM_API_KEY or '',    'string', 'llm', 'API Key LLM Embed',    'Clau API del LLM d\'embeddings (Graphiti)',   True),
            ('llm.embed.base_url',   os.environ.get('LLM_EMBED_BASE_URL', '') or Config.LLM_BASE_URL,        'string', 'llm', 'URL base LLM Embed',   'URL base del LLM d\'embeddings',              False),
            ('llm.embed.model_name', os.environ.get('LLM_EMBED_MODEL_NAME', 'text-embedding-3-small'),       'string', 'llm', 'Model LLM Embed',      'Model d\'embeddings',                         False),
            # ── LLM Small (Graphiti) ─────────────────────────────────────
            ('llm.small.api_key',    os.environ.get('LLM_SMALL_API_KEY', '') or Config.LLM_API_KEY or '',    'string', 'llm', 'API Key LLM Small',    'Clau API del LLM lleuger (Graphiti)',          True),
            ('llm.small.base_url',   os.environ.get('LLM_SMALL_BASE_URL', '') or Config.LLM_BASE_URL,        'string', 'llm', 'URL base LLM Small',   'URL base del LLM lleuger',                    False),
            ('llm.small.model_name', Config.LLM_SMALL_MODEL_NAME,                                            'string', 'llm', 'Model LLM Small',      'Model lleuger per a tasques Graphiti',         False),
            # ── Simulació ────────────────────────────────────────────────
            ('simulation.max_rounds', str(Config.OASIS_DEFAULT_MAX_ROUNDS), 'int', 'simulation', 'Rondes màximes simulació', 'Nombre màxim de rondes OASIS per defecte', False),
            # ── Informe ──────────────────────────────────────────────────
            ('report.max_tool_calls',       str(Config.REPORT_AGENT_MAX_TOOL_CALLS),       'int',   'report', 'Max tool calls informe',       'Màx. crides a eines per secció al ReportAgent',  False),
            ('report.max_reflection_rounds', str(Config.REPORT_AGENT_MAX_REFLECTION_ROUNDS), 'int', 'report', 'Rondes de reflexió informe',   'Rondes de reflexió del ReportAgent',              False),
            ('report.temperature',          str(Config.REPORT_AGENT_TEMPERATURE),          'float', 'report', 'Temperatura informe',          'Temperatura del LLM al ReportAgent',              False),
            # ── Email ─────────────────────────────────────────────────────
            ('acs.sender_display_name', Config.ACS_SENDER_DISPLAY_NAME, 'string', 'email', 'Nom del remitent email', 'Nom visible al camp "De:" dels emails enviats', False),
            # ── Límits ───────────────────────────────────────────────────
            ('limits.max_projects_per_user', '20', 'int', 'limits', 'Màx. projectes per usuari', '', False),
            ('limits.max_simulations',       '10', 'int', 'limits', 'Màx. simulacions',          '', False),
        ]
```

- [ ] **Step 2: Verificar que `init_system.py` s'executa sense errors**

```bash
cd /home/ubuntu/dev/MiroFish && DATABASE_URL=sqlite:///test_init.db uv run python backend/scripts/init_system.py 2>&1; rm -f backend/test_init.db
```

Expected: `[init_system] SystemConfig per defecte: OK` i `[init_system] Inicialització completada.`

- [ ] **Step 3: Commit**

```bash
cd /home/ubuntu/dev/MiroFish && git add backend/scripts/init_system.py && git commit -m "feat(config): expand init_system defaults with all behavior keys"
```

---

## Task 3: API GET/PATCH segura per a secrets

**Files:**
- Modify: `backend/app/api/admin.py` (funció `get_config` i `patch_config`)
- Modify: `backend/tests/test_admin_api.py`

- [ ] **Step 1: Afegir tests nous a `test_admin_api.py`**

Afegeix al final del fitxer:

```python
def test_get_config_secret_hides_value(client, in_memory_db):
    """GET no retorna el valor de claus secretes; retorna has_value=True."""
    from backend.app.models.db_models import SystemConfigModel
    from backend.app.db import get_session
    with get_session() as db:
        db.add(SystemConfigModel(
            key='llm.api_key', value='sk-secret-key',
            value_type='string', group='llm',
            label='API Key LLM', description='',
            is_secret=True
        ))
        db.commit()

    res = client.get('/api/admin/config')
    assert res.status_code == 200
    entries = res.get_json()['data']
    entry = next(e for e in entries if e['key'] == 'llm.api_key')
    assert entry['value'] is None
    assert entry['has_value'] is True


def test_get_config_secret_no_value(client, in_memory_db):
    """has_value=False quan la clau secreta no té valor."""
    from backend.app.models.db_models import SystemConfigModel
    from backend.app.db import get_session
    with get_session() as db:
        db.add(SystemConfigModel(
            key='llm.api_key', value='',
            value_type='string', group='llm',
            label='API Key LLM', description='',
            is_secret=True
        ))
        db.commit()

    res = client.get('/api/admin/config')
    entry = next(e for e in res.get_json()['data'] if e['key'] == 'llm.api_key')
    assert entry['value'] is None
    assert entry['has_value'] is False


def test_patch_config_secret_empty_does_not_update(client, in_memory_db):
    """PATCH amb valor buit en clau secreta no modifica el valor actual."""
    from backend.app.models.db_models import SystemConfigModel
    from backend.app.db import get_session
    with get_session() as db:
        db.add(SystemConfigModel(
            key='llm.api_key', value='sk-original',
            value_type='string', group='llm',
            label='API Key LLM', description='',
            is_secret=True
        ))
        db.commit()

    res = client.patch('/api/admin/config', json={'llm.api_key': ''})
    assert res.status_code == 200

    with get_session() as db:
        entry = db.get(SystemConfigModel, 'llm.api_key')
        assert entry.value == 'sk-original'


def test_patch_config_secret_with_value_updates(client, in_memory_db):
    """PATCH amb valor no buit en clau secreta sí que actualitza."""
    from backend.app.models.db_models import SystemConfigModel
    from backend.app.db import get_session
    with get_session() as db:
        db.add(SystemConfigModel(
            key='llm.api_key', value='sk-original',
            value_type='string', group='llm',
            label='API Key LLM', description='',
            is_secret=True
        ))
        db.commit()

    res = client.patch('/api/admin/config', json={'llm.api_key': 'sk-new-key'})
    assert res.status_code == 200

    with get_session() as db:
        entry = db.get(SystemConfigModel, 'llm.api_key')
        assert entry.value == 'sk-new-key'
```

- [ ] **Step 2: Executar per verificar que fallen**

```bash
cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/test_admin_api.py -v 2>&1 | tail -20
```

Expected: els 4 tests nous fallen (`AssertionError` perquè l'API encara retorna `'●●●●'` i no comprova secrets al PATCH).

- [ ] **Step 3: Modificar `get_config` a `backend/app/api/admin.py`**

Substitueix la funció `get_config` (línies 10–26):

```python
@admin_bp.route('/config', methods=['GET'])
@require_admin
def get_config():
    with get_session() as db:
        entries = db.execute(select(SystemConfigModel)).scalars().all()
        result = []
        for e in entries:
            entry = {
                'key': e.key,
                'value_type': e.value_type,
                'group': e.group,
                'label': e.label,
                'description': e.description,
                'is_secret': e.is_secret,
            }
            if e.is_secret:
                entry['value'] = None
                entry['has_value'] = bool(e.value)
            else:
                entry['value'] = e.value
                entry['has_value'] = bool(e.value)
            result.append(entry)
    return jsonify({'success': True, 'data': result})
```

- [ ] **Step 4: Modificar `patch_config` a `backend/app/api/admin.py`**

Substitueix la funció `patch_config` (línies 29–39):

```python
@admin_bp.route('/config', methods=['PATCH'])
@require_admin
def patch_config():
    data = request.get_json(silent=True) or {}
    with get_session() as db:
        for key, value in data.items():
            entry = db.get(SystemConfigModel, key)
            if entry is None:
                continue
            if entry.is_secret and not value:
                continue
            entry.value = str(value)
        db.commit()
    return jsonify({'success': True})
```

- [ ] **Step 5: Executar tots els tests de l'API d'admin**

```bash
cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/test_admin_api.py -v
```

Expected: tots els tests en verd (inclosos els tests anteriors).

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/dev/MiroFish && git add backend/app/api/admin.py backend/tests/test_admin_api.py && git commit -m "feat(admin): secure secrets in config API — GET hides values, PATCH ignores empty secrets"
```

---

## Task 4: Consumir `get_config` a `report_agent.py`

**Files:**
- Modify: `backend/app/services/report_agent.py` (classe `ReportAgent`, constants de classe)

Les constants actuals `MAX_TOOL_CALLS_PER_SECTION = 5` i `MAX_REFLECTION_ROUNDS = 3` s'han de llegir de BD en cada instanciació.

- [ ] **Step 1: Localitzar les constants a `report_agent.py`**

```bash
grep -n "MAX_TOOL_CALLS_PER_SECTION\|MAX_REFLECTION_ROUNDS\|MAX_TOOL_CALLS_PER_CHAT" /home/ubuntu/dev/MiroFish/backend/app/services/report_agent.py | head -10
```

- [ ] **Step 2: Modificar la classe `ReportAgent` per llegir de BD**

Al mètode `__init__` de `ReportAgent` (a `backend/app/services/report_agent.py`), just DESPRÉS de les línies de constants de classe (línies ~884–891), afegeix l'import i sobreescriu els valors a l'`__init__`:

Primer, afegeix l'import al bloc d'imports del fitxer (cerca `from ..config import Config`):

```python
from ..config_db import get_config
```

Després, al mètode `__init__` de `ReportAgent`, afegeix al principi del cos (just després de `self` assignacions inicials):

```python
        # Llegeix de BD amb fallback a les constants de classe
        self.max_tool_calls_per_section = get_config(
            'report.max_tool_calls', Config.REPORT_AGENT_MAX_TOOL_CALLS
        ) or self.MAX_TOOL_CALLS_PER_SECTION
        self.max_reflection_rounds = get_config(
            'report.max_reflection_rounds', Config.REPORT_AGENT_MAX_REFLECTION_ROUNDS
        ) or self.MAX_REFLECTION_ROUNDS
        self.report_temperature = get_config(
            'report.temperature', Config.REPORT_AGENT_TEMPERATURE
        )
```

- [ ] **Step 3: Substituir usos de `self.MAX_TOOL_CALLS_PER_SECTION` i `self.MAX_REFLECTION_ROUNDS` per les instàncies**

Busca tots els usos dins la classe:

```bash
grep -n "self\.MAX_TOOL_CALLS_PER_SECTION\|self\.MAX_REFLECTION_ROUNDS" /home/ubuntu/dev/MiroFish/backend/app/services/report_agent.py
```

Per a cada línia trobada, canvia:
- `self.MAX_TOOL_CALLS_PER_SECTION` → `self.max_tool_calls_per_section`
- `self.MAX_REFLECTION_ROUNDS` → `self.max_reflection_rounds`

Les constants de classe (`MAX_TOOL_CALLS_PER_SECTION`, `MAX_REFLECTION_ROUNDS`) queden com a valors per defecte — no les eliminis.

- [ ] **Step 4: Verificar que els tests existents segueixen passant**

```bash
cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/ -v -k "not simulation_runner" 2>&1 | tail -20
```

Expected: tots els tests en verd.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/dev/MiroFish && git add backend/app/services/report_agent.py && git commit -m "feat(report): read max_tool_calls and max_reflection_rounds from system_config"
```

---

## Task 5: Consumir `get_config` a `api/simulation.py` (max_rounds)

**Files:**
- Modify: `backend/app/api/simulation.py`

Quan l'API de simulació no rep `max_rounds` en el request, ha d'usar el valor de BD.

- [ ] **Step 1: Localitzar on es llegeix `max_rounds` del request**

```bash
grep -n "max_rounds\|OASIS_DEFAULT_MAX_ROUNDS" /home/ubuntu/dev/MiroFish/backend/app/api/simulation.py | head -15
```

- [ ] **Step 2: Afegir import i ús de `get_config`**

Al bloc d'imports de `backend/app/api/simulation.py`, afegeix:
```python
from ..config_db import get_config
```

Localitza el codi on s'obté `max_rounds` del request (al voltant de la línia `max_rounds = data.get('max_rounds')`). Canvia la lògica perquè si no ve del request, usi el valor de BD:

```python
        max_rounds = data.get('max_rounds')
        if max_rounds is not None:
            try:
                max_rounds = int(max_rounds)
                if max_rounds <= 0:
                    max_rounds = None
            except (ValueError, TypeError):
                max_rounds = None
        
        # Si no ve del request, usar valor de BD (prevalença BD > env)
        if max_rounds is None:
            max_rounds = get_config('simulation.max_rounds', Config.OASIS_DEFAULT_MAX_ROUNDS)
```

- [ ] **Step 3: Verificar tests existents**

```bash
cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/ -v 2>&1 | tail -20
```

Expected: tots els tests en verd.

- [ ] **Step 4: Commit**

```bash
cd /home/ubuntu/dev/MiroFish && git add backend/app/api/simulation.py && git commit -m "feat(simulation): read default max_rounds from system_config"
```

---

## Task 6: Consumir `get_config` a `llm_client.py`

**Files:**
- Modify: `backend/app/utils/llm_client.py`

El constructor de `LLMClient` llegeix `Config.LLM_*` directament. Cal que llegeixi de BD amb fallback a `Config.*`.

- [ ] **Step 1: Modificar `__init__` de `LLMClient`**

Al fitxer `backend/app/utils/llm_client.py`, afegeix l'import:
```python
from ..config_db import get_config
```

Substitueix les línies (al `__init__`):
```python
        self.api_key = api_key or Config.LLM_API_KEY
        raw_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME
```

Per:
```python
        self.api_key = api_key or get_config('llm.api_key', Config.LLM_API_KEY)
        raw_url = base_url or get_config('llm.base_url', Config.LLM_BASE_URL)
        self.model = model or get_config('llm.model_name', Config.LLM_MODEL_NAME)
```

I la línia que comprova el proveïdor:
```python
        if (Config.LLM_PROVIDER or "").lower() == "gemini" and not base_url:
```

Canvia per:
```python
        provider = get_config('llm.provider', Config.LLM_PROVIDER or '')
        if provider.lower() == "gemini" and not base_url:
```

- [ ] **Step 2: Verificar tests existents de llm_client**

```bash
cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/test_llm_client.py -v
```

Expected: tots els tests en verd.

- [ ] **Step 3: Commit**

```bash
cd /home/ubuntu/dev/MiroFish && git add backend/app/utils/llm_client.py && git commit -m "feat(llm): read LLM config from system_config with env fallback"
```

---

## Task 7: Consumir `get_config` a `graphiti_backend.py`

**Files:**
- Modify: `backend/app/graph/graphiti_backend.py`

Localitza el bloc on s'inicialitzen els tres clients LLM (principal, small, embed) a `graphiti_backend.py`.

- [ ] **Step 1: Veure el bloc d'inicialització de Graphiti**

```bash
grep -n "LLM_API_KEY\|LLM_BASE_URL\|LLM_MODEL\|LLM_SMALL\|LLM_EMBED\|Config\." /home/ubuntu/dev/MiroFish/backend/app/graph/graphiti_backend.py | head -30
```

- [ ] **Step 2: Afegir import i substituir les lectures de Config**

Al fitxer `backend/app/graph/graphiti_backend.py`, afegeix l'import:
```python
from ..config_db import get_config
```

Substitueix totes les referències a `Config.LLM_API_KEY`, `Config.LLM_BASE_URL`, `Config.LLM_MODEL_NAME`, `Config.LLM_SMALL_*`, `Config.LLM_EMBED_*` per les cridades a `get_config` corresponents:

```python
# Al bloc d'inicialització dels clients LLM (al voltant de les línies 149–181):
llm_base_url, llm_query = parse_azure_url(get_config('llm.base_url', Config.LLM_BASE_URL))
small_base_url, small_query = parse_azure_url(get_config('llm.small.base_url', Config.LLM_SMALL_BASE_URL))
embed_base_url, embed_query = parse_azure_url(get_config('llm.embed.base_url', Config.LLM_EMBED_BASE_URL))

# I per api_keys i model names:
# Config.LLM_API_KEY     → get_config('llm.api_key', Config.LLM_API_KEY)
# Config.LLM_SMALL_API_KEY → get_config('llm.small.api_key', Config.LLM_SMALL_API_KEY)
# Config.LLM_EMBED_API_KEY → get_config('llm.embed.api_key', Config.LLM_EMBED_API_KEY)
# Config.LLM_MODEL_NAME    → get_config('llm.model_name', Config.LLM_MODEL_NAME)
# Config.LLM_SMALL_MODEL_NAME → get_config('llm.small.model_name', Config.LLM_SMALL_MODEL_NAME)
# Config.LLM_EMBED_MODEL_NAME → get_config('llm.embed.model_name', Config.LLM_EMBED_MODEL_NAME)
```

- [ ] **Step 3: Verificar tests existents**

```bash
cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/test_graph_factory.py -v
```

Expected: tots els tests en verd.

- [ ] **Step 4: Commit**

```bash
cd /home/ubuntu/dev/MiroFish && git add backend/app/graph/graphiti_backend.py && git commit -m "feat(graphiti): read LLM embed/small config from system_config"
```

---

## Task 8: Consumir `get_config` a `run_parallel_simulation.py` (boost LLM)

**Files:**
- Modify: `backend/scripts/run_parallel_simulation.py`

`run_parallel_simulation.py` és un script que llegeix directament de `os.environ`. Com que no és una app Flask, ha de carregar la BD manualment.

- [ ] **Step 1: Localitzar el bloc de boost LLM**

```bash
grep -n "LLM_BOOST\|boost_api_key\|boost_base_url\|boost_model" /home/ubuntu/dev/MiroFish/backend/scripts/run_parallel_simulation.py | head -15
```

- [ ] **Step 2: Modificar la funció que llegeix el boost LLM**

Localitza la funció que conté les línies `boost_api_key = os.environ.get("LLM_BOOST_API_KEY", "")` (al voltant de la línia 1042).

Afegeix al principi de la funció (just abans de les línies `boost_api_key = ...`):

```python
    # Intentar llegir de BD (prevalença BD > env)
    try:
        import sys
        import os as _os
        _scripts_dir = _os.path.dirname(_os.path.abspath(__file__))
        _backend_dir = _os.path.join(_scripts_dir, '..')
        if _backend_dir not in sys.path:
            sys.path.insert(0, _backend_dir)
        from app.config import Config as _Config
        from app.db import init_db as _init_db
        from app.config_db import get_config as _get_config
        _init_db(_Config.DATABASE_URL)
        _boost_api_key_bd = _get_config('llm.boost.api_key', '')
        _boost_base_url_bd = _get_config('llm.boost.base_url', '')
        _boost_model_bd = _get_config('llm.boost.model_name', '')
    except Exception:
        _boost_api_key_bd = ''
        _boost_base_url_bd = ''
        _boost_model_bd = ''

    boost_api_key = _boost_api_key_bd or os.environ.get("LLM_BOOST_API_KEY", "")
    boost_base_url = _boost_base_url_bd or os.environ.get("LLM_BOOST_BASE_URL", "")
    boost_model = _boost_model_bd or os.environ.get("LLM_BOOST_MODEL_NAME", "")
```

I elimina (o comenta) les línies originals:
```python
    boost_api_key = os.environ.get("LLM_BOOST_API_KEY", "")
    boost_base_url = os.environ.get("LLM_BOOST_BASE_URL", "")
    boost_model = os.environ.get("LLM_BOOST_MODEL_NAME", "")
```

- [ ] **Step 3: Verificar que el script no dona errors de sintaxi**

```bash
cd /home/ubuntu/dev/MiroFish && uv run python -c "import backend.scripts.run_parallel_simulation" 2>&1 | head -10
```

Expected: cap error de sintaxi.

- [ ] **Step 4: Commit**

```bash
cd /home/ubuntu/dev/MiroFish && git add backend/scripts/run_parallel_simulation.py && git commit -m "feat(simulation): read boost LLM config from system_config with env fallback"
```

---

## Task 9: Frontend — UI de configuració millorada

**Files:**
- Modify: `frontend/src/views/AdminView.vue`

La UI actual mostra totes les claus en una llista plana. Cal agrupar per `group`, gestionar secrets amb `has_value`, i agrupar els LLMs secundaris en un subpanel col·lapsable.

- [ ] **Step 1: Localitzar el template de configuració i el codi JS**

```bash
grep -n "config\|Config\|configEntries\|configValues\|saveConfig\|loadConfig" /home/ubuntu/dev/MiroFish/frontend/src/views/AdminView.vue | head -30
```

- [ ] **Step 2: Modificar `loadConfig` per inicialitzar `secretInputs`**

Localitza la funció `loadConfig` (al voltant de la línia 387). Modifica-la:

```javascript
const secretInputs = ref({})

async function loadConfig() {
  const res = await service.get('/api/admin/config')
  configEntries.value = res.data || []
  configValues.value = Object.fromEntries(
    configEntries.value.filter(e => !e.is_secret).map(e => [e.key, e.value ?? ''])
  )
  secretInputs.value = Object.fromEntries(
    configEntries.value.filter(e => e.is_secret).map(e => [e.key, ''])
  )
}
```

Assegura't que `secretInputs` es declara al costat de `configEntries` i `configValues` (al bloc `ref`):

```javascript
const configEntries = ref([])
const configValues = ref({})
const configSaved = ref(false)
const secretInputs = ref({})
```

- [ ] **Step 3: Modificar `saveConfig` per incloure secrets no buits**

Localitza `saveConfig` (al voltant de la línia 513). Substitueix:

```javascript
async function saveConfig() {
  const payload = {}
  for (const entry of configEntries.value) {
    if (entry.is_secret) {
      const v = secretInputs.value[entry.key]
      if (v && v !== '') payload[entry.key] = v
    } else {
      payload[entry.key] = configValues.value[entry.key]
    }
  }
  await service.patch('/api/admin/config', payload)
  // Netejar camps secrets després de guardar
  for (const key of Object.keys(secretInputs.value)) {
    secretInputs.value[key] = ''
  }
  configSaved.value = true
  setTimeout(() => { configSaved.value = false }, 2000)
}
```

- [ ] **Step 4: Afegir computed `groupedConfig` per agrupar per `group`**

Afegeix just sota les declaracions `ref`:

```javascript
const GROUP_ORDER = ['llm', 'simulation', 'report', 'email', 'limits']
const GROUP_LABELS = {
  llm: 'LLM',
  simulation: $t('admin.configGroupSimulation'),
  report: $t('admin.configGroupReport'),
  email: 'Email',
  limits: $t('admin.configGroupLimits'),
}
const showSecondaryLlm = ref(false)

const SECONDARY_LLM_PREFIXES = ['llm.boost.', 'llm.embed.', 'llm.small.']

const groupedConfig = computed(() => {
  const groups = {}
  for (const entry of configEntries.value) {
    const g = entry.group || 'other'
    if (!groups[g]) groups[g] = []
    groups[g].push(entry)
  }
  return GROUP_ORDER.filter(g => groups[g]).map(g => ({
    key: g,
    label: GROUP_LABELS[g] || g,
    entries: groups[g],
  }))
})
```

Nota: `$t` no és accessible fora del template en Options API, però `AdminView.vue` usa Composition API amb `useI18n`. Afegeix `const { t } = useI18n()` si no existeix ja, i usa `t(...)` en comptes de `$t(...)`.

- [ ] **Step 5: Substituir el template del tab de configuració**

Localitza el bloc `<!-- Tab: Configuració -->` i substitueix-lo:

```html
<!-- Tab: Configuració -->
<div v-if="tab === 'config'" class="tab-content">
  <div class="tab-header">
    <h2 class="section-title">{{ $t('admin.config') }}</h2>
    <button class="start-btn" @click="saveConfig">{{ $t('common.save') }}</button>
  </div>
  <div v-if="groupedConfig.length" class="config-form">
    <div v-for="group in groupedConfig" :key="group.key" class="config-group">
      <div class="config-group-header">{{ group.label }}</div>

      <!-- Subgrup LLMs secundaris (col·lapsable) dins del grup llm -->
      <template v-if="group.key === 'llm'">
        <template v-for="entry in group.entries" :key="entry.key">
          <template v-if="!SECONDARY_LLM_PREFIXES.some(p => entry.key.startsWith(p))">
            <div class="config-row">
              <label class="config-label">
                <span class="config-key mono">{{ entry.key }}</span>
                <span class="config-desc">{{ entry.label }}</span>
              </label>
              <input
                v-if="entry.is_secret"
                type="password"
                class="field-input"
                v-model="secretInputs[entry.key]"
                :placeholder="entry.has_value ? $t('admin.configSecretSet') : $t('admin.configSecretUnset')"
              />
              <input v-else type="text" class="field-input" v-model="configValues[entry.key]" />
            </div>
          </template>
        </template>
        <div class="config-secondary-toggle">
          <button class="action-btn" @click="showSecondaryLlm = !showSecondaryLlm">
            {{ showSecondaryLlm ? '▲' : '▼' }} {{ $t('admin.configSecondaryLlm') }}
          </button>
        </div>
        <template v-if="showSecondaryLlm">
          <template v-for="entry in group.entries" :key="entry.key + '-sec'">
            <template v-if="SECONDARY_LLM_PREFIXES.some(p => entry.key.startsWith(p))">
              <div class="config-row">
                <label class="config-label">
                  <span class="config-key mono">{{ entry.key }}</span>
                  <span class="config-desc">{{ entry.label }}</span>
                </label>
                <input
                  v-if="entry.is_secret"
                  type="password"
                  class="field-input"
                  v-model="secretInputs[entry.key]"
                  :placeholder="entry.has_value ? $t('admin.configSecretSet') : $t('admin.configSecretUnset')"
                />
                <input v-else type="text" class="field-input" v-model="configValues[entry.key]" />
              </div>
            </template>
          </template>
        </template>
      </template>

      <!-- Resta de grups (simulació, report, email, limits) -->
      <template v-else>
        <div v-for="entry in group.entries" :key="entry.key" class="config-row">
          <label class="config-label">
            <span class="config-key mono">{{ entry.key }}</span>
            <span class="config-desc">{{ entry.label }}</span>
          </label>
          <input
            v-if="entry.is_secret"
            type="password"
            class="field-input"
            v-model="secretInputs[entry.key]"
            :placeholder="entry.has_value ? $t('admin.configSecretSet') : $t('admin.configSecretUnset')"
          />
          <input v-else type="text" class="field-input" v-model="configValues[entry.key]" />
        </div>
      </template>
    </div>
  </div>
  <div v-else class="empty-state">{{ $t('admin.noConfig') }}</div>
  <div v-if="configSaved" class="success-msg">{{ $t('admin.configSaved') }}</div>
</div>
```

- [ ] **Step 6: Afegir estils CSS per als nous elements**

Al bloc `<style>` del component, afegeix:

```css
.config-group { margin-bottom: 24px; }
.config-group-header { font-weight: 600; font-size: 0.85rem; text-transform: uppercase;
  letter-spacing: 0.05em; color: #555; padding: 8px 0 4px; border-bottom: 2px solid #e8e8e8;
  margin-bottom: 8px; }
.config-secondary-toggle { padding: 8px 0; }
```

- [ ] **Step 7: Afegir traduccions als fitxers de localització**

Al fitxer `locales/ca.json`, afegeix dins el bloc `"admin"`:
```json
"configGroupSimulation": "Simulació",
"configGroupReport": "Informe",
"configGroupLimits": "Límits",
"configSecondaryLlm": "LLMs secundaris (Boost / Embed / Small)",
"configSecretSet": "(ja configurat)",
"configSecretUnset": "(no configurat)"
```

Afegeix les mateixes claus als fitxers `locales/en.json` i `locales/es.json` amb les traduccions corresponents:

`en.json`:
```json
"configGroupSimulation": "Simulation",
"configGroupReport": "Report",
"configGroupLimits": "Limits",
"configSecondaryLlm": "Secondary LLMs (Boost / Embed / Small)",
"configSecretSet": "(already configured)",
"configSecretUnset": "(not configured)"
```

`es.json`:
```json
"configGroupSimulation": "Simulación",
"configGroupReport": "Informe",
"configGroupLimits": "Límites",
"configSecondaryLlm": "LLMs secundarios (Boost / Embed / Small)",
"configSecretSet": "(ya configurado)",
"configSecretUnset": "(no configurado)"
```

- [ ] **Step 8: Verificar que el frontend compila sense errors**

```bash
cd /home/ubuntu/dev/MiroFish && npm run build 2>&1 | tail -20
```

Expected: build correcte sense errors.

- [ ] **Step 9: Commit**

```bash
cd /home/ubuntu/dev/MiroFish && git add frontend/src/views/AdminView.vue locales/ca.json locales/en.json locales/es.json && git commit -m "feat(admin): group config by section, secure secret fields in UI"
```

---

## Task 10: Test de suite complet i verificació final

- [ ] **Step 1: Executar tots els tests**

```bash
cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/ -v 2>&1 | tail -30
```

Expected: tots els tests en verd, sense regressions.

- [ ] **Step 2: Verificar que el build del frontend és net**

```bash
cd /home/ubuntu/dev/MiroFish && npm run build 2>&1 | tail -10
```

Expected: `✓ built in Xs` sense warnings ni errors.

- [ ] **Step 3: Commit final si hi ha alguna cosa pendent**

```bash
cd /home/ubuntu/dev/MiroFish && git status
```

Si hi ha canvis sense committejar, crear el commit corresponent.
