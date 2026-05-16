# Spec: Esborrament permanent d'usuaris

**Data:** 2026-05-16
**Branca:** feature/fase3-roles-admin

## Resum

Els administradors poden esborrar permanentment un usuari del sistema. L'esborrament elimina sense rastre l'usuari i tots els seus recursos: grafs externs (Zep/Graphiti), fitxers de storage, i tots els registres de BD (projectes, simulacions, informes, tokens). Es preserven, si n'hi ha, taules d'auditoria.

L'esborrat segueix un flux de dos passos obligatori: primer desactivar (`disabled`), després esborrar. Un usuari `disabled` també pot ser reactivat (`active`).

---

## 1. Backend

### 1.1 Endpoint existent a corregir: `DELETE /api/users/<id>/purge`

L'endpoint ja existeix però **omet l'esborrat dels grafs externs** (Zep/Graphiti). Cal ampliar-lo.

**Flux complet de purga:**

```
per cada project de user.projects:
    per cada graph de project.graphs:
        si graph.external_id no és null:
            graph_builder.delete_graph(graph.external_id)
            # si falla: log warning, continua (no bloqueja)
    storage.delete_prefix(f"projects/{project.id}")

db.delete(user)   # cascade BD: projectes, simulacions, informes, tokens
db.commit()
```

**Estructura de grafs:**
- Cada projecte té N grafs: 1 original + 1 clonat per simulació
- Tots es troben a `project.graphs` (relació `ProjectModel.graphs`)
- `GraphModel.external_id` conté l'ID al servei extern; si és `None`, s'omet silenciosament

**Gestió d'errors del servei extern:**
- Si `graph_builder.delete_graph()` llança excepció → `logger.warning(...)` + continua
- El purge no es pot bloquejar per indisponibilitat de Zep/Graphiti
- Si storage falla → `logger.warning(...)` + continua (el registre de BD s'esborra igualment)

**Prerequisit:** carregar `user.projects` amb eager loading (o accedir-hi dins la sessió) per evitar `DetachedInstanceError`.

### 1.2 Nou endpoint: `PATCH /api/users/<id>` (ja existent)

El reactivat (`status: active`) ja funciona via l'endpoint PATCH existent. No cal cap canvi.

---

## 2. Frontend (`AdminView.vue`)

### 2.1 Botons per fila

| Status de l'usuari | Botons |
|--------------------|--------|
| `pending` | ✉ Reenvia invitació |
| `active` | ✕ Desactiva |
| `disabled` | ✓ Reactiva · 🗑 Esborra |

- El botó **Esborra** (`🗑`) apareix *únicament* per a usuaris `disabled`
- El botó **Reactiva** (`✓`) crida `PATCH /api/users/<id>` amb `{ status: 'active' }`

### 2.2 Modal d'esborrament

S'obre en clicar **Esborra**. Conté:

1. **Capçalera:** "Esborra usuari"
2. **Advertència** (fons vermell clar): "Aquesta acció és irreversible. S'esborraran tots els projectes, simulacions, grafs i fitxers de **{user.name}** ({user.email})."
3. **Camp de confirmació:** `<input>` amb placeholder "Escriu l'email per confirmar"
4. **Botons:**
   - `Cancel·la` — tanca el modal
   - `Esborra definitivament` — desactivat fins que el valor del camp coincideix exactament amb `user.email`; en clicar crida `DELETE /api/users/<id>/purge`

**Estat del modal:**
- Mentre s'executa la crida: botó en estat `loading`, desactivat
- En cas d'error: mostra missatge d'error dins el modal
- En èxit: tanca el modal, refresca la llista d'usuaris, mostra missatge breu d'èxit

### 2.3 i18n

Claus noves a afegir a `locales/{en,zh,ca}.json` sota la secció `admin`:

```json
"enableUser": "Reactiva",
"deleteUser": "Esborra",
"deleteUserTitle": "Esborra usuari",
"deleteUserWarning": "Aquesta acció és irreversible. S'esborraran tots els projectes, simulacions, grafs i fitxers de {name} ({email}).",
"deleteUserConfirmPlaceholder": "Escriu l'email per confirmar",
"deleteUserConfirm": "Esborra definitivament",
"deleteUserSuccess": "Usuari esborrat."
```

---

## 3. Testing

- **Test backend:** `test_purge_user_deletes_graphs` — mock de `graph_builder.delete_graph`, verificar que es crida una vegada per cada `GraphModel` amb `external_id` no null
- **Test backend:** `test_purge_user_continues_if_graph_delete_fails` — mock llança excepció, verificar que l'usuari s'esborra igualment
- **Test backend:** `test_enable_user` — PATCH `status: active` sobre usuari `disabled`
- **Test frontend:** no requerits per al modal (testing manual suficient)

---

## 4. Fora d'abast

- No es crea taula d'auditoria nova (no n'hi ha al sistema actual)
- No s'implementa esborrat en background asíncron (la purga és síncrona; els grafs externs es poden eliminar en <1s cadascun en condicions normals)
- No es modifica el comportament del soft delete (`disable`) existent
