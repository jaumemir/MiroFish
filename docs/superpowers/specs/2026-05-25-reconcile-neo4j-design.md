# Disseny: Script de reconciliació Neo4j

**Data:** 2026-05-25  
**Estat:** Aprovat  

## Visió general

Script de reconciliació que detecta `group_id` orfes a Neo4j (Graphiti backend) comparant-los amb les taules `graphs`, `simulations` i `projects` de la BBDD SQLite de MiroFish. Genera un script d'eliminació executable i un log detallat.

## Fitxers

| Fitxer | Tipus | Descripció |
|--------|-------|------------|
| `scripts/reconcile_neo4j.py` | Script principal | Reconciliador: llegeix fonts, detecta orfes, genera outputs |
| `scripts/reconcile_delete.py` | Generat | Script d'eliminació dels orfes detectats |
| `scripts/reconcile_YYYYMMDD_HHMMSS.log` | Generat | Log detallat del procés de reconciliació |

## Dependències

Cap dependència del backend de MiroFish. Usa:
- `neo4j` — driver Neo4j (ja present al venv)
- `python-dotenv` — lectura de `.env` (ja present al venv)
- `sqlite3` — mòdul de la stdlib de Python

## Arguments de línia de comandes (`reconcile_neo4j.py`)

```
python3 scripts/reconcile_neo4j.py [opcions]

Opcions:
  --env-file PATH         Camí al fitxer .env (defecte: .env al directori del projecte)
  --db-path PATH          Camí a la BBDD SQLite (sobreescriu DATABASE_URL del .env)
  --neo4j-uri URI         URI de Neo4j (sobreescriu NEO4J_URI del .env)
  --neo4j-user USER       Usuari Neo4j (sobreescriu NEO4J_USER del .env)
  --neo4j-password PASS   Contrasenya Neo4j (sobreescriu NEO4J_PASSWORD del .env)
  --output-dir DIR        Directori on generar els fitxers de sortida (defecte: scripts/)
  --log-level LEVEL       Nivell de log: DEBUG, INFO, WARNING (defecte: INFO)
```

Prioritat de configuració: **args CLI > .env > error**.

## Lògica de reconciliació (3 passos)

### Pas 1 — Recollir `group_id` de Neo4j

Query Cypher:
```cypher
MATCH (n) WHERE n.group_id IS NOT NULL RETURN DISTINCT n.group_id AS gid
```

Retorna tots els `group_id` únics que existeixen a Neo4j, independentment del tipus de node.

### Pas 2 — Recollir IDs coneguts de SQLite

De la taula `graphs`:
- Tots els `external_id` on `backend = 'graphiti'` i `external_id IS NOT NULL` → IDs de graphs base vàlids

De la taula `simulations`:
- Tots els `id` → permet construir els `group_id` de simulació esperats: `mirofish_{sim_id}_sim`

De la taula `projects`:
- Tots els `id` → per detectar `GraphModel` amb `project_id` inexistent

**Inconsistències de BBDD reportades però que no generen proposta d'eliminació:**
- `GraphModel` amb `backend = 'graphiti'` però `external_id IS NULL`
- `GraphModel` amb `backend != 'graphiti'` (ex: `zep`) — s'ignoren per a Neo4j, però es reporta al log
- `GraphModel` amb `external_id` vàlid però `project_id` no trobat a `projects` (DANGLING_PROJECT — sí genera proposta)

### Pas 3 — Creuament i classificació

Per cada `group_id` de Neo4j es comprova:

| Categoria | Condició | Raó reportada al log |
|-----------|----------|----------------------|
| `BASE_ORPHAN` | `group_id` no coincideix amb cap `external_id` de la taula `graphs` (i no és format `*_sim`) | "Cap GraphModel amb external_id='{gid}' a la BBDD" |
| `SIM_ORPHAN` | `group_id` segueix el patró `*_sim` i la part `sim_id` no existeix a la taula `simulations` | "Cap SimulationModel amb id='{sim_id}' corresponent al group_id '{gid}'" |
| `DANGLING_PROJECT` | `group_id` té `GraphModel` corresponent, però el `project_id` d'aquest `GraphModel` no existeix a `projects` | "GraphModel id='{graph_id}' té external_id='{gid}' però el project_id='{project_id}' no existeix a projects" |

`group_id` que no entren en cap categoria anterior es consideren **vàlids** i no es proposa eliminació.

## Format del log (`reconcile_YYYYMMDD_HHMMSS.log`)

```
=== RECONCILIACIÓ NEO4J - 2026-05-25 14:30:00 ===

[PAS 1] Connexió Neo4j: neo4j+s://044d917e.databases.neo4j.io
[PAS 1] group_ids trobats a Neo4j: 12
[PAS 1]   - mirofish_48d9a9ffc6cf4c6b
[PAS 1]   - mirofish_sim_b4252122e125_sim
  ...

[PAS 2] BBDD SQLite: /path/to/mirofish_dev.db
[PAS 2] external_ids (backend=graphiti): 1
[PAS 2] sim_ids a simulations: 6
[PAS 2] project_ids a projects: 2

[PAS 2] ADVERTÈNCIA: GraphModel id='6d4e...' backend='graphiti' external_id=NULL — sense external_id, no reconciliable
[PAS 2] ADVERTÈNCIA: GraphModel id='xxxx...' backend='zep' — ignorat per a reconciliació Neo4j

[PAS 3] Creuament i classificació:
[PAS 3] ✓ VALID          mirofish_48d9a9ffc6cf4c6b
[PAS 3] ✗ BASE_ORPHAN    mirofish_aabbccdd1122 — Cap GraphModel amb external_id='mirofish_aabbccdd1122' a la BBDD
[PAS 3] ✗ SIM_ORPHAN     mirofish_sim_deadbeef_sim — Cap SimulationModel amb id='sim_deadbeef'
[PAS 3] ✗ DANGLING_PROJECT mirofish_99887766 — GraphModel id='abc123...' té external_id='mirofish_99887766' però project_id='xyz...' no existeix a projects

=== RESUM ===
  VÀLIDS:           1
  BASE_ORPHAN:      1
  SIM_ORPHAN:       1
  DANGLING_PROJECT: 1
  TOTAL ORFES:      3

Script d'eliminació generat: scripts/reconcile_delete.py
Log guardat a:              scripts/reconcile_20260525_143000.log
```

## Format del `reconcile_delete.py` generat

```python
#!/usr/bin/env python3
"""
Script d'eliminació de graphs Neo4j orfes.
Generat per: scripts/reconcile_neo4j.py
Data de generació: 2026-05-25 14:30:00
Log de referència: scripts/reconcile_20260525_143000.log

Orfes detectats: 3
  BASE_ORPHAN:      1
  SIM_ORPHAN:       1
  DANGLING_PROJECT: 1

ÚS:
  python3 reconcile_delete.py             # dry-run (no elimina res)
  python3 reconcile_delete.py --execute   # elimina amb confirmació interactiva

CONNEXIÓ:
  Llegeix NEO4J_URI/USER/PASSWORD del fitxer .env o variables d'entorn.
  Args CLI --neo4j-uri / --neo4j-user / --neo4j-password sobreescriuen .env.
"""

ORPHANS = [
    # (group_id, categoria, raó)
    ("mirofish_aabbccdd1122", "BASE_ORPHAN",      "Cap GraphModel amb external_id='mirofish_aabbccdd1122' a la BBDD"),
    ("mirofish_sim_deadbeef_sim", "SIM_ORPHAN",   "Cap SimulationModel amb id='sim_deadbeef'"),
    ("mirofish_99887766", "DANGLING_PROJECT",      "GraphModel id='abc123...' té external_id='mirofish_99887766' però project_id='xyz...' no existeix a projects"),
]

# ... lògica de connexió, dry-run/execute, confirmació interactiva
```

## Comportament del `reconcile_delete.py`

- **Dry-run (per defecte):** Imprimeix les queries `MATCH (n) WHERE n.group_id = $gid DETACH DELETE n` que s'executarien, amb el recompte de nodes afectats (query `MATCH (n) WHERE n.group_id = $gid RETURN count(n)`), sense modificar res.
- **`--execute`:** Mostra el resum dels orfes, demana confirmació interactiva (`Eliminar 3 group_ids? [y/N]:`), i executa les eliminacions. Reporta nodes eliminats per `group_id`.
- **Connexió:** Mateixa lògica que el reconciliador (`.env` + args CLI).

## Consideracions

- El script principal és idempotent: es pot executar múltiples vegades sense efectes secundaris.
- El `reconcile_delete.py` generat sobreescriu l'anterior si ja existeix (amb avís al log).
- Si Neo4j no és accessible, el script falla amb missatge d'error clar i codi de sortida != 0.
- Si la BBDD SQLite no existeix o no és accessible, idem.
- El patró de `group_id` de simulació és `mirofish_{simulation_id}_sim` on `simulation_id` segueix el format `sim_[a-f0-9]{12}`.
