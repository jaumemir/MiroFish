# MiroFish — Pla d'Escalabilitat Corporativa

**Data**: 2026-05-25  
**Context**: Plataforma en producció a Azure Container Apps (1 pod, 1 worker gunicorn, 4 threads).  
**Objectiu**: Suportar 30 usuaris concurrents, 10 simulacions simultànies, coexistint amb generació d'informes, graph builds i ontologies. Convertir l'eina en una plataforma corporativa real.

---

## Situació de partida — Limitacions actuals

### Arquitectura present

```
[Azure Container Apps — 1 pod]
  └── gunicorn (1 worker, 4 threads, gthread)
        ├── Flask API (HTTP)
        ├── SimulationRunner (estat en memòria: _run_states, _processes, _monitor_threads)
        ├── Monitor threads (threading.Thread per simulació)
        ├── OASIS subprocessos (subprocess.Popen)
        └── ZepGraphMemoryUpdater (threading.Thread per simulació)
```

### Problemes bloquejants per escalar

| Problema | Impacte |
|---|---|
| **Estat en memòria** (`SimulationRunner._run_states`) | Impossibilitat de tenir >1 pod: cada pod té el seu propi estat, les peticions de polling van al pod equivocat |
| **1 worker gunicorn** | Màxim 4 peticions concurrents; graph builds i reports bloquegen l'API |
| **Monitor threads** | S'aturen silenciosament (cap watchdog); `run_state.json` queda congelat |
| **OASIS subprocess al mateix pod que l'API** | Una simulació amb 112 agents consumeix 2–4 CPU i 4+ GB RAM, esgotant recursos de l'API |
| **ZepGraphMemoryUpdater** | Thread continu per simulació que satura Neo4j i no s'atura bé en fer stop |
| **Neo4j AuraDB** | `get_all_edges` llegeix tot el graf (>5000 arestes truncades), duplicate_facts errors freqüents, coll d'ampolla amb >100 agents |
| **Azure Files NFS** | Latència alta en operacions de fitxer; `simulation.log` dona OSError intermitent |

---

## Opcions d'escalabilitat

### Opció A — Monòlit robust amb cua de tasques (Celery + Redis)

**Filosofia**: Un sol repositori, un sol Dockerfile base. Es substitueixen els threads actuals per tasques Celery. L'estat de les simulacions va a Redis/PostgreSQL. Múltiples pods idèntics d'API i múltiples pods de worker.

```
                    ┌─────────────────────────────────────────┐
                    │         Azure Container Apps            │
                    │                                         │
[Usuaris] → [Load   │  [Pod API Flask × 2-4]                  │
             Balancer│       │                                 │
                    │       ▼                                 │
                    │  [Redis Cache]  ←──────────────────────│─── estat simulacions
                    │       │                                 │    cua de tasques
                    │       ▼                                 │
                    │  [Pod Celery Worker × 2-5]              │
                    │       │                                 │
                    │  [OASIS subprocess]                     │
                    └─────────────────────────────────────────┘
                              │
                    [PostgreSQL] [Neo4j] [Azure Files]
```

**Components nous**:
- **Redis Azure Cache** (Basic C1, ~15€/mes): cua de tasques + estat simulacions
- **Pods Celery Worker**: substitueixen `SimulationRunner` thread-based; un pod per simulació activa
- **Celery Beat** (opcional): tasques periòdiques (cleanup, watchdog)

**Canvis al codi**:
- `SimulationRunner.start_simulation()` → publica tasca Celery en comptes de llançar thread
- `_run_states` dict → claus Redis (amb TTL)
- `_monitor_threads` → tasca Celery periòdica que llegeix `actions.jsonl` i actualitza Redis
- `ZepGraphMemoryUpdater` → tasca Celery independent (amb rate limiting)
- API `/run-status` → llegeix de Redis en comptes de memòria local

**Consideració tècnica important**: OASIS és asyncio. Celery és sync per defecte. Cal una de:
- `celery[gevent]` amb pool gevent (recomanat)
- Wrapper `asyncio.run()` dins la tasca Celery (funciona però perd paral·lelisme async)
- Migrar a `arq` (async task queue, Redis-based, natiu asyncio) — menys madur però encaixa millor

**Pros**:
- Un sol repositori, CI/CD simple
- Migració incremental des del codi actual
- Celery/arq ben documentats, ecosistema madur
- Redis també resol watchdog (TTL com a heartbeat)
- Pods d'API completament sense estat → escalen sense coordinació
- Monitoring gratuït amb Flower (Celery) o arq-dashboard

**Contres**:
- Quirks Celery + asyncio (resolt amb gevent o arq)
- Redis és un servei addicional a gestionar (però gestionat a Azure, <5 min de setup)
- Tots els pods worker executen el mateix codi: no hi ha especialització per tipus de feina
- En pic de 10 simulacions simultànies, els pods worker necessiten molta RAM (4–8 Gi cadascun)

**Nivell d'esforç**: **Mitjà** — 3–4 setmanes. La majoria del codi de lògica de simulació es conserva; canvia com es crida i com s'emmagatzema l'estat.

**Recomanació d'ús**: Bon punt de partida. Millora dràsticament la robustesa sense canvi d'arquitectura profund.

---

### Opció B — Separació lleugera: pods API + pods Worker especialitzats

**Filosofia**: L'API Flask i els workers pesats (OASIS, Report Agent, Graph Builder) viuen en pods separats. Comunicació via cua de missatges. Cada tipus de worker escala pel seu propi workload.

```
                    ┌─────────────────────────────────────────────────────┐
                    │                 Azure Container Apps                │
                    │                                                     │
[Usuaris] → [Load   │  [Pod API Flask × 2-4]                              │
             Balancer│       │                                             │
                    │       ▼                                             │
                    │  [Azure Service Bus]  ←── cua de tasques            │
                    │       │                                             │
                    │       ├──────────────────────────────────────┐      │
                    │       ▼                                      ▼      │
                    │  [Pod Worker Simulació × 0-5]    [Pod Worker Report/Graph × 0-3] │
                    │       │                                      │      │
                    │  [OASIS subprocess]              [ReportAgent + GraphBuilder]    │
                    └─────────────────────────────────────────────────────┘
                              │                        │
                    [PostgreSQL]    [Neo4j]    [Azure Files]
```

**Components nous**:
- **Azure Service Bus** (Standard, ~10€/mes): cua duradora, dead-letter automàtic
- **Imatge Docker Worker-Sim**: conté OASIS + dependències pesades (~2 GB)
- **Imatge Docker Worker-Report**: conté ReportAgent + eines d'anàlisi
- **Imatge Docker API**: lleugera, sense OASIS (~400 MB)
- **PostgreSQL per a estat**: substitueix `_run_states` en memòria

**Canvis al codi**:
- API publica missatge a Service Bus en comptes de cridar `SimulationRunner` directament
- Workers consumeixen missatges i publiquen actualitzacions d'estat a PostgreSQL
- API llegeix estat de PostgreSQL
- Watchdog com a CronJob de Container Apps (revisa simulacions mortes cada minut)

**Pros**:
- Pods d'API molt lleugers (poca RAM, escalen ràpid)
- Workers de simulació poden tenir 8–16 Gi RAM sense afectar l'API
- Aïllament de fallades complet: crash del worker de simulació no afecta l'API ni els reports
- Escala a zero: si no hi ha simulacions, els pods worker s'apaguen (Azure Container Apps ho suporta)
- Azure Service Bus és completament gestionat, garanties de lliurament, dead-letter

**Contres**:
- Dos o tres Dockerfiles → CI/CD més complex (però manejable amb GitHub Actions matrix)
- Cal re-escriure la lògica de polling d'estat (l'API no té el procés localment)
- Latència addicional de Service Bus (~50ms per missatge, negligible per a tasques llargues)
- El `run_state.json` sobre Azure Files perd sentit: cal migrar a PostgreSQL completament
- Debugging més complex: un error pot estar al worker o a l'API

**Nivell d'esforç**: **Mitjà-Alt** — 5–7 setmanes. Canvi arquitectònic real però sense tocar la lògica de negoci.

**Recomanació d'ús**: Ideal quan el creixement és clar i es vol escalar workers de simulació agressivament (>20 simultànies).

---

### Opció C — Microserveis complets

**Filosofia**: Cada domini del negoci és un servei independent amb la seva pròpia BD, API i cicle de desplegament. Event-driven amb Azure Event Grid o Apache Kafka.

```
[Azure API Management Gateway]
         │
         ├── [Servei Auth]          → [PostgreSQL Auth]
         ├── [Servei Projects]      → [PostgreSQL Projects]
         ├── [Servei Graph]         → [Neo4j] + [Event Grid]
         ├── [Servei Simulation]    → [Redis] + [Azure Files]
         ├── [Servei Report]        → [PostgreSQL Reports]
         └── [Servei Notification]  → [Azure Service Bus]

[Event Grid]
   ├── graph.built       → Servei Simulation (habilita inici)
   ├── simulation.ended  → Servei Report (inicia generació automàtica)
   └── report.ready      → Servei Notification (avisa usuari)
```

**Pros**:
- Escalat independent màxim per servei
- Tecnologies heterogènies possibles (Python per simulació, Go per API lleugera...)
- Ideal per a equips grans amb squads per domini
- Desplegaments independents sense risc de regresió global

**Contres**:
- **Overkill absolut per a 30 usuaris**: la complexitat operacional és desproporcionada
- Observabilitat distribuïda necessita inversió seriosa (Jaeger/Zipkin, OpenTelemetry)
- Migració des del monòlit actual: 3–6 mesos de feina sense afegir funcionalitat
- Debugging d'errors travessa múltiples serveis (distributed tracing obligatori)
- Cost Azure: +API Management (~150€/mes), múltiples bases de dades, Event Grid...
- Equip petit ha de mantenir 5+ serveis, 5+ CI/CD pipelines, 5+ Dockerfiles

**Nivell d'esforç**: **Alt** — 3–6 mesos. No recomanat fins que el volum justifiqui la complexitat.

**Recomanació d'ús**: Considerar únicament si l'equip supera 5 persones i el volum supera els 100 usuaris concurrents.

---

## Recomanació: Opció A amb separació de pods (híbrid A+B)

Per al cas d'ús actual (30 usuaris, 10 simulacions concurrent, equip petit), la millor estratègia és una **Opció A evolució B**: implementar Celery+Redis però des del principi separar les imatges Docker d'API i worker.

### Arquitectura recomanada detallada

```
[Azure Load Balancer]
        │
        ▼
[Container App: mirofish-api]          ← imatge lleugera (~400 MB)
  gunicorn, 2 workers, 4 threads       ← sense OASIS, sense agents LLM
  Escala: 1–4 répliques                ← escala per CPU/peticions HTTP
        │
        ▼
[Azure Cache for Redis]                ← estat simulacions + cua arq/Celery
        │
        ▼
[Container App: mirofish-worker]       ← imatge completa (~2.5 GB amb OASIS)
  arq worker (async, Redis)            ← 1 worker per simulació concurrent
  Escala: 0–10 répliques               ← escala per longitud de cua
        │
        ├── OASIS subprocess (Twitter/Reddit)
        ├── ReportAgent (LLM tool calling)
        └── GraphBuilder (Graphiti + Neo4j)

[PostgreSQL]  ← estat persistent de simulacions (substitueix _run_states)
[Neo4j AuraDB Professional]  ← upgrade necessari per >5 simulacions
[Azure Files NFS]  ← actions.jsonl, simulation.log (sense canvis)
```

### Pla d'implementació en fases

#### Fase 1 — Treure estat de memòria (prerequisit per escalar) [2 setmanes]

**Objectiu**: Que qualsevol pod d'API pugui respondre qualsevol petició sense conèixer l'estat local.

- Migrar `SimulationRunner._run_states` → taula `simulation_run_states` a PostgreSQL
- `_processes` dict → columna `process_pid` + heartbeat (el worker fa ping a PostgreSQL cada 30s)
- API `/run-status` llegeix PostgreSQL en comptes de memòria
- Mantenir `run_state.json` a Azure Files com a backup/compatibilitat

**Resultat**: Es pot arrencar >1 réplica d'API sense problemes de consistència.

#### Fase 2 — Workers fiables amb arq [2 setmanes]

**Objectiu**: Substituir `threading.Thread` per tasques async duradores.

- Instal·lar `arq` (async Redis queue, compatible asyncio natiu)
- `start_simulation()` → publica tasca `run_simulation` a arq
- `start_report()` → publica tasca `generate_report` a arq
- `build_graph()` → publica tasca `build_graph` a arq
- Watchdog: arq healthcheck + Container Apps liveness probe
- Monitor de simulació → tasca arq periòdica (cada 5s llegeix `actions.jsonl` i actualitza PostgreSQL)

**Resultat**: Cap thread que mori silenciosament. Tasques reiniciables. Retry automàtic en fallada.

#### Fase 3 — Separació imatges Docker [1 setmana]

**Objectiu**: API lleugera que escali ràpid; workers grans amb OASIS.

- `Dockerfile.api`: Flask + dependències HTTP (sense OASIS, sense camel-ai)
- `Dockerfile.worker`: tot + OASIS + camel-ai + langchain
- `azure/container-app-api.bicep` + `azure/container-app-worker.bicep`
- Worker escala per longitud de cua Redis (KEDA si Azure Container Apps ho suporta, o scaling rule custom)

**Resultat**: 10 simulacions concurrent → 10 pods worker de 4 CPU / 8 Gi. API sempre lleugera.

#### Fase 4 — Neo4j tuning [1 setmana]

**Objectiu**: Eliminar el coll d'ampolla de Neo4j.

- Upgrade AuraDB Free → AuraDB Professional (o Neo4j self-hosted a Azure VM)
- `ZepGraphMemoryUpdater`: afegir rate limiting (màxim 1 batch/minut per simulació)
- Opció de desactivar graph memory durant la simulació i activar-la en batch al final
- Índexs Neo4j: revisar que `entity_name`, `uuid`, i les arestes més consultades tinguin índexs
- Graphiti: limitar `get_all_edges` (investigar si hi ha paginació disponible)

**Resultat**: Neo4j deixa de ser coll d'ampolla; simulacions de 100+ agents sense degradació.

#### Fase 5 — Robustesa i observabilitat [1 setmana]

**Objectiu**: Detecció i recuperació automàtica de fallades.

- Frontend: reprendre polling si `runner_status` torna a `running` (fix Step3Simulation.vue)
- Watchdog task (arq periodic): detecta simulacions amb `updated_at` >5 min congelat i reinicia el monitor
- Azure Application Insights: traces de les tasques arq (durada, errors, retries)
- Alertes: simulació >4h sense progressar → notificació per email
- Límit de simulacions concurrent per usuari (configurable a SystemConfig)

---

## Comparativa final

| Criteri | Opció A (Celery+Redis) | Opció B (Service Bus + pods especialitzats) | Opció C (Microserveis) | Recomanació (A+B híbrid) |
|---|---|---|---|---|
| Esforç migració | Mitjà (3–4 set.) | Mitjà-Alt (5–7 set.) | Alt (3–6 mesos) | Mitjà (6–7 set. en fases) |
| Complexitat operacional | Baixa-Mitjana | Mitjana | Alta | Baixa-Mitjana |
| Suport 10 sim. concurrent | ✓ | ✓ | ✓ | ✓ |
| Escalat API independent | ✓ (si estat a Redis) | ✓ | ✓ | ✓ |
| Escalat workers independent | Parcial (mateixa imatge) | ✓ | ✓ | ✓ (imatges separades) |
| Robustesa fallades | Alta (Celery retry) | Alta | Alta | Alta (arq retry + watchdog) |
| Cost addicional Azure | +Redis ~15€/mes | +Service Bus ~10€/mes | +++ | +Redis ~15€/mes |
| Debugging | Fàcil | Mitjà | Difícil | Fàcil-Mitjà |
| Asyncio natiu (OASIS) | Problemàtic (workaround) | OK | OK | ✓ (arq és natiu asyncio) |
| Recomanat per a... | Equip petit, volum moderat | Creixement agressiu | Equip gran, 100+ usuaris | **Cas actual: 30 usuaris, 10 sim.** |

---

## Problemes puntuals a resoldre independentment de l'opció escollida

Aquests fixes son necessaris sigui quina sigui l'opció d'escalat triada:

| Problema | Fix | Esforç |
|---|---|---|
| Monitor thread s'atura silenciosament | Watchdog: reiniciar si `updated_at` >5 min congelat | Petit |
| Frontend para polling prematurament | Step3Simulation.vue: tornar a `phase=1` si `runner_status` torna a `running` | Petit |
| Overflow tokens OASIS (observació entorn) | Reduir `semaphore` de 30 a 10–15 | Trivial |
| Neo4j CPU pujant | Rate limiting updater + índexs + upgrade AuraDB | Mitjà |
| `simulation.log` OSError Azure Files | Ja resolt (retry + makedirs) | ✓ Fet |
| `actions.jsonl` no es creava | Ja resolt (action_logger integrat) | ✓ Fet |

---

## Decisió recomanada

**Implementar l'híbrid A+B en 5 fases** (6–7 setmanes), prioritzant:

1. **Fase 1** immediatament (treure estat de memòria) — desbloqueig crític
2. **Fase 2** a continuació (arq workers) — robustesa i fiabilitat
3. **Fixes puntuals** en paral·lel (semaphore, frontend polling, watchdog)
4. **Fases 3–5** quan la base sigui estable

Aquesta seqüència permet tenir millores observables cada 2 setmanes i no requereix un "big bang" de migració.
