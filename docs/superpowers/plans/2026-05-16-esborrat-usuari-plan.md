# Esborrament permanent d'usuaris — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permetre a l'administrador esborrar permanentment un usuari (i tots els seus grafs, fitxers i dades) en un flux de dos passos: primer desactivar, després esborrament definitiu amb modal de confirmació per email.

**Architecture:** El backend corregeix `DELETE /api/users/<id>/purge` per eliminar els grafs externs Zep/Graphiti de tots els projectes de l'usuari abans d'esborrar la BD. El frontend afegeix el botó "Reactiva" i "Esborra" per a usuaris `disabled` i un modal de confirmació que requereix escriure l'email.

**Tech Stack:** Flask + SQLAlchemy 2.x, `GraphBuilderService`, Vue 3 + vue-i18n v11, pytest

---

## Fitxers a modificar

| Fitxer | Canvis |
|--------|--------|
| `backend/app/api/users.py` | Ampliar `purge_user`: iterar grafs i cridar `GraphBuilderService.delete_graph()` |
| `backend/tests/test_users_admin.py` | Afegir 3 tests nous: purge amb grafs, purge amb fallada de graf, reactiva usuari |
| `frontend/src/views/AdminView.vue` | Afegir botó Reactiva + botó Esborra + modal de confirmació |
| `locales/en.json` | Afegir claus `admin.enableUser`, `deleteUser*` |
| `locales/zh.json` | Ídem en xinès |
| `locales/ca.json` | Ídem en català |

---

## Task 1: Tests backend per a purge amb grafs

**Files:**
- Modify: `backend/tests/test_users_admin.py`

- [ ] **Step 1: Afegir imports necessaris als tests**

A `backend/tests/test_users_admin.py`, afegir a la secció d'imports:

```python
from sqlalchemy import select
from backend.app.models.db_models import UserModel, ProjectModel, GraphModel
from backend.app.db import get_session
```

- [ ] **Step 2: Escriure el test `test_purge_user_deletes_external_graphs`**

Afegir al final del fitxer:

```python
def test_purge_user_deletes_external_graphs(client, in_memory_db):
    """purge_user ha de cridar delete_graph per cada graph amb external_id."""
    # Crear usuari
    with patch('backend.app.api.users.send_invitation_email', return_value=True):
        create_res = client.post('/api/users/', json={
            'email': 'purge@example.com', 'name': 'Purge', 'role': 'user'
        })
    user_id = create_res.get_json()['data']['id']

    # Crear projecte i grafs directament a la BD
    with get_session() as db:
        proj = ProjectModel(id='proj-purge-1', name='Test', status='created', user_id=user_id)
        db.add(proj)
        db.flush()
        g1 = GraphModel(project_id='proj-purge-1', external_id='ext-graph-1', status='ready')
        g2 = GraphModel(project_id='proj-purge-1', external_id='ext-graph-2', status='ready')
        g3 = GraphModel(project_id='proj-purge-1', external_id=None, status='ready')  # sense external_id
        db.add_all([g1, g2, g3])
        db.commit()

    with patch('backend.app.api.users.GraphBuilderService') as MockBuilder:
        mock_instance = MockBuilder.return_value
        res = client.delete(f'/api/users/{user_id}/purge')

    assert res.status_code == 200
    assert res.get_json()['success'] is True
    # delete_graph ha de ser cridat exactament 2 vegades (els 2 amb external_id)
    assert mock_instance.delete_graph.call_count == 2
    called_ids = {call.args[0] for call in mock_instance.delete_graph.call_args_list}
    assert called_ids == {'ext-graph-1', 'ext-graph-2'}
```

- [ ] **Step 3: Escriure el test `test_purge_user_continues_if_graph_delete_fails`**

```python
def test_purge_user_continues_if_graph_delete_fails(client, in_memory_db):
    """Si delete_graph falla, l'usuari s'esborra igualment."""
    with patch('backend.app.api.users.send_invitation_email', return_value=True):
        create_res = client.post('/api/users/', json={
            'email': 'failgraph@example.com', 'name': 'FailGraph', 'role': 'user'
        })
    user_id = create_res.get_json()['data']['id']

    with get_session() as db:
        proj = ProjectModel(id='proj-fail-1', name='Fail', status='created', user_id=user_id)
        db.add(proj)
        db.flush()
        g = GraphModel(project_id='proj-fail-1', external_id='ext-fail-1', status='ready')
        db.add(g)
        db.commit()

    with patch('backend.app.api.users.GraphBuilderService') as MockBuilder:
        mock_instance = MockBuilder.return_value
        mock_instance.delete_graph.side_effect = Exception("Zep unavailable")
        res = client.delete(f'/api/users/{user_id}/purge')

    assert res.status_code == 200
    assert res.get_json()['success'] is True
    # Usuari ja no existeix a la BD
    with get_session() as db:
        user = db.execute(
            select(UserModel).where(UserModel.id == user_id)
        ).scalar_one_or_none()
    assert user is None
```

- [ ] **Step 4: Escriure el test `test_enable_disabled_user`**

```python
def test_enable_disabled_user(client, in_memory_db):
    """Un usuari disabled es pot reactivar via PATCH status: active."""
    with patch('backend.app.api.users.send_invitation_email', return_value=True):
        create_res = client.post('/api/users/', json={
            'email': 'enable@example.com', 'name': 'Enable', 'role': 'user'
        })
    user_id = create_res.get_json()['data']['id']

    # Desactivar primer
    client.delete(f'/api/users/{user_id}')
    get_res = client.get(f'/api/users/{user_id}')
    assert get_res.get_json()['data']['status'] == 'disabled'

    # Reactivar
    res = client.patch(f'/api/users/{user_id}', json={'status': 'active'})
    assert res.status_code == 200
    assert res.get_json()['data']['status'] == 'active'
```

- [ ] **Step 5: Executar els tests nous per verificar que fallen**

```bash
cd /home/ubuntu/dev/MiroFish/backend
uv run pytest tests/test_users_admin.py::test_purge_user_deletes_external_graphs tests/test_users_admin.py::test_purge_user_continues_if_graph_delete_fails tests/test_users_admin.py::test_enable_disabled_user -v
```

Resultat esperat: 2 failures (els de purge), 1 pass (`test_enable_disabled_user` ja funciona amb el PATCH actual).

---

## Task 2: Implementar purge_user corregit

**Files:**
- Modify: `backend/app/api/users.py`

- [ ] **Step 1: Afegir import de GraphBuilderService i selectinload**

A la secció d'imports de `backend/app/api/users.py`, afegir:

```python
from sqlalchemy.orm import selectinload
from ..services.graph_builder import GraphBuilderService
```

- [ ] **Step 2: Substituir la funció `purge_user` sencera**

Localitzar la funció `purge_user` (línies ~110-125) i substituir-la completament per:

```python
@users_bp.route('/<user_id>/purge', methods=['DELETE'])
@require_admin
def purge_user(user_id):
    """Hard delete: esborra grafs externs, storage i usuari+cascada BD."""
    from .. import get_storage
    storage = get_storage()
    builder = GraphBuilderService()

    with get_session() as db:
        user = db.execute(
            select(UserModel)
            .where(UserModel.id == user_id)
            .options(
                selectinload(UserModel.projects)
                .selectinload(ProjectModel.graphs)
            )
        ).scalar_one_or_none()
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404

        for proj in user.projects:
            for graph in proj.graphs:
                if graph.external_id:
                    try:
                        builder.delete_graph(graph.external_id)
                    except Exception as exc:
                        logger.warning(
                            'purge_user: delete_graph(%s) failed: %s', graph.external_id, exc
                        )
            try:
                storage.delete_prefix(f"projects/{proj.id}")
            except Exception as exc:
                logger.warning('purge_user: storage.delete_prefix(%s) failed: %s', proj.id, exc)

        db.delete(user)
        db.commit()

    return jsonify({'success': True})
```

- [ ] **Step 3: Afegir import de `ProjectModel` als imports de la funció (ja disponible via db_models)**

Verificar que `ProjectModel` és accessible. Afegir a la secció d'imports del fitxer si no hi és:

```python
from ..models.db_models import UserModel, ProjectModel
```

- [ ] **Step 4: Executar els tests per verificar que passen**

```bash
cd /home/ubuntu/dev/MiroFish/backend
uv run pytest tests/test_users_admin.py -v
```

Resultat esperat: tots els tests passen (inclosos els 3 nous).

- [ ] **Step 5: Executar la suite completa per verificar que no hi ha regressions**

```bash
cd /home/ubuntu/dev/MiroFish/backend
uv run pytest --tb=short -q
```

Resultat esperat: mateixos resultats que abans (≤2 failures pre-existents, cap nova failure).

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/dev/MiroFish
git add backend/app/api/users.py backend/tests/test_users_admin.py
git commit -m "fix(users): purge_user elimina grafs Zep/Graphiti de tots els projectes"
```

---

## Task 3: Claus i18n per a les accions noves

**Files:**
- Modify: `locales/en.json`
- Modify: `locales/zh.json`
- Modify: `locales/ca.json`

- [ ] **Step 1: Afegir claus a `locales/en.json`**

Localitzar la secció `"admin"` (al voltant de la línia 794) i afegir les claus noves **al final** de l'objecte, abans del `}` de tancament:

```json
"enableUser": "Re-enable",
"deleteUser": "Delete",
"deleteUserTitle": "Delete user",
"deleteUserWarning": "This action is irreversible. All projects, simulations, graphs and files belonging to {name} ({email}) will be permanently deleted.",
"deleteUserConfirmPlaceholder": "Type the email to confirm",
"deleteUserConfirm": "Delete permanently",
"deleteUserSuccess": "User deleted."
```

- [ ] **Step 2: Afegir claus a `locales/zh.json`**

Localitzar la secció `"admin"` i afegir al final:

```json
"enableUser": "重新启用",
"deleteUser": "删除",
"deleteUserTitle": "删除用户",
"deleteUserWarning": "此操作不可逆。{name}（{email}）的所有项目、模拟、图谱和文件将被永久删除。",
"deleteUserConfirmPlaceholder": "输入邮箱以确认",
"deleteUserConfirm": "永久删除",
"deleteUserSuccess": "用户已删除。"
```

- [ ] **Step 3: Afegir claus a `locales/ca.json`**

Localitzar la secció `"admin"` i afegir al final:

```json
"enableUser": "Reactiva",
"deleteUser": "Esborra",
"deleteUserTitle": "Esborra usuari",
"deleteUserWarning": "Aquesta acció és irreversible. S'esborraran tots els projectes, simulacions, grafs i fitxers de {name} ({email}).",
"deleteUserConfirmPlaceholder": "Escriu l'email per confirmar",
"deleteUserConfirm": "Esborra definitivament",
"deleteUserSuccess": "Usuari esborrat."
```

- [ ] **Step 4: Verificar que els 3 fitxers JSON són vàlids**

```bash
cd /home/ubuntu/dev/MiroFish
node -e "
['locales/en.json','locales/zh.json','locales/ca.json'].forEach(f => {
  try { JSON.parse(require('fs').readFileSync(f,'utf8')); console.log('OK:', f); }
  catch(e) { console.error('ERR:', f, e.message); }
})"
```

Resultat esperat:
```
OK: locales/en.json
OK: locales/zh.json
OK: locales/ca.json
```

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/dev/MiroFish
git add locales/en.json locales/zh.json locales/ca.json
git commit -m "feat(i18n): afegir claus per a reactivar i esborrar usuari"
```

---

## Task 4: Frontend — botons Reactiva i Esborra + modal

**Files:**
- Modify: `frontend/src/views/AdminView.vue`

- [ ] **Step 1: Localitzar la secció de botons d'acció per fila**

Buscar al fitxer el bloc que conté els botons d'acció (al voltant de `disableUser` i `reinvite`):

```html
<td class="actions-cell">
  <button v-if="user.status === 'pending'" class="action-btn" @click="reinvite(user)" :title="$t('admin.reinvite')">✉</button>
  <button v-if="user.status !== 'disabled'" class="action-btn danger" @click="disableUser(user)" :title="$t('admin.disable')">✕</button>
</td>
```

Substituir per:

```html
<td class="actions-cell">
  <button v-if="user.status === 'pending'" class="action-btn" @click="reinvite(user)" :title="$t('admin.reinvite')">✉</button>
  <button v-if="user.status !== 'disabled'" class="action-btn danger" @click="disableUser(user)" :title="$t('admin.disable')">✕</button>
  <button v-if="user.status === 'disabled'" class="action-btn" @click="enableUser(user)" :title="$t('admin.enableUser')">✓</button>
  <button v-if="user.status === 'disabled'" class="action-btn danger" @click="openDeleteModal(user)" :title="$t('admin.deleteUser')">🗑</button>
</td>
```

- [ ] **Step 2: Afegir el modal de confirmació**

Buscar el tancament `</template>` de l'arrel del component (al final del `<template>`) i afegir el modal just abans:

```html
<!-- Modal d'esborrament d'usuari -->
<div v-if="deleteModal.open" class="modal-overlay" @click.self="closeDeleteModal">
  <div class="modal-box">
    <h3 class="modal-title">{{ $t('admin.deleteUserTitle') }}</h3>
    <p class="modal-warning">
      {{ $t('admin.deleteUserWarning', { name: deleteModal.user?.name, email: deleteModal.user?.email }) }}
    </p>
    <input
      v-model="deleteModal.confirmEmail"
      type="email"
      class="field-input"
      :placeholder="$t('admin.deleteUserConfirmPlaceholder')"
    />
    <div v-if="deleteModal.error" class="error-msg">{{ deleteModal.error }}</div>
    <div class="modal-actions">
      <button class="action-btn" @click="closeDeleteModal">{{ $t('common.cancel') }}</button>
      <button
        class="start-btn danger"
        :disabled="deleteModal.confirmEmail !== deleteModal.user?.email || deleteModal.loading"
        @click="confirmDelete"
      >
        {{ deleteModal.loading ? $t('common.loading') : $t('admin.deleteUserConfirm') }}
      </button>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Afegir l'estat reactiu del modal**

Dins el bloc `<script setup>`, localitzar on estan les altres refs (`invite`, `inviteSuccess`, etc.) i afegir:

```js
const deleteModal = ref({
  open: false,
  user: null,
  confirmEmail: '',
  loading: false,
  error: ''
})
```

- [ ] **Step 4: Afegir les funcions `openDeleteModal`, `closeDeleteModal`, `confirmDelete` i `enableUser`**

Localitzar la funció `disableUser` i afegir just a continuació:

```js
async function enableUser(user) {
  await service.patch(`/api/users/${user.id}`, { status: 'active' })
  await loadUsers()
}

function openDeleteModal(user) {
  deleteModal.value = { open: true, user, confirmEmail: '', loading: false, error: '' }
}

function closeDeleteModal() {
  deleteModal.value.open = false
}

async function confirmDelete() {
  deleteModal.value.loading = true
  deleteModal.value.error = ''
  try {
    await service.delete(`/api/users/${deleteModal.value.user.id}/purge`)
    deleteModal.value.open = false
    await loadUsers()
  } catch (e) {
    deleteModal.value.error = e?.response?.data?.error || t('common.unknownError')
  } finally {
    deleteModal.value.loading = false
  }
}
```

- [ ] **Step 5: Afegir els estils CSS del modal**

Localitzar la secció `<style scoped>` i afegir al final:

```css
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.4);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.modal-box {
  background: #fff; padding: 32px; max-width: 480px; width: 90%;
  border: 1px solid #e5e5e5; display: flex; flex-direction: column; gap: 16px;
}
.modal-title { font-size: 1.1rem; font-weight: 700; margin: 0; }
.modal-warning {
  background: #fee2e2; color: #991b1b; padding: 12px 16px;
  font-size: 0.85rem; line-height: 1.5;
}
.modal-actions { display: flex; gap: 12px; justify-content: flex-end; }
.action-btn.danger { border-color: #fca5a5; color: #dc2626; }
.start-btn.danger { background: #dc2626; }
.start-btn.danger:hover:not(:disabled) { background: #b91c1c; }
```

- [ ] **Step 6: Verificar que `t` està importat a l'script**

Buscar si l'script ja té `const { t } = useI18n()`. Si no hi és, afegir-lo on es fan servir les altres funcions de vue-i18n (al costat de `locale` o `$t`). Si `useI18n` no s'usa directament a l'script (perquè tot és via template `$t`), no cal afegir res.

- [ ] **Step 7: Iniciar el servidor de dev i verificar manualment**

```bash
cd /home/ubuntu/dev/MiroFish
npm run dev
```

Obrir el navegador a `http://localhost:3000`. Iniciar sessió com a admin. Anar a Administració → Usuaris.

Verificar:
1. Usuari `active`: mostra `✕ Desactiva`, no mostra `✓` ni `🗑`
2. Desactivar un usuari: ara mostra `✓ Reactiva` i `🗑 Esborra`
3. Clicar `✓ Reactiva`: l'usuari torna a `active`
4. Tornar a desactivar. Clicar `🗑 Esborra`: s'obre el modal
5. El botó "Esborra definitivament" està desactivat fins escriure l'email exacte
6. Escriure l'email: el botó s'activa
7. Confirmar: l'usuari desapareix de la llista, es mostra missatge d'èxit

- [ ] **Step 8: Commit**

```bash
cd /home/ubuntu/dev/MiroFish
git add frontend/src/views/AdminView.vue
git commit -m "feat(admin): botons reactiva/esborra per a usuaris desactivats amb modal de confirmació"
```

---

## Self-review

**Cobertura de la spec:**
- ✅ §1.1 purge elimina grafs externs → Task 2
- ✅ §1.1 errors de servei extern no bloquegen → Task 1 test + Task 2 impl
- ✅ §1.2 reactivat via PATCH existent → Task 1 `test_enable_disabled_user` + Task 4 `enableUser`
- ✅ §2.1 botons per status → Task 4 Step 1
- ✅ §2.2 modal amb camp email → Task 4 Steps 2-5
- ✅ §2.3 i18n → Task 3
- ✅ §3 tests backend → Task 1

**Placeholders:** cap TBD ni "similar to".

**Consistència de noms:**
- `GraphBuilderService` (importat i instanciat a `users.py`)
- `graph.external_id` (camp a `GraphModel`)
- `deleteModal` (ref Vue)
- `openDeleteModal` / `closeDeleteModal` / `confirmDelete` / `enableUser` (funcions Vue)
- `admin.enableUser` / `admin.deleteUser*` (claus i18n)
