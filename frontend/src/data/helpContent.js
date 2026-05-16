// frontend/src/data/helpContent.js

export const helpContent = {

  // ─── ENGLISH ────────────────────────────────────────────────────────────────
  en: {
    overview: {
      title: 'MiroFish — How it works',
      body: [
        { type: 'p', text: 'MiroFish is an AI-powered multi-agent social simulation platform. You provide seed documents (research papers, news articles, reports) and describe a scenario; MiroFish extracts the key actors, builds a knowledge graph, spawns realistic agent personas, and runs a social-media simulation across two platforms.' },
        { type: 'h3', text: 'The 5-step workflow' },
        { type: 'list', items: [
          'Step 1 — Graph Build: Upload documents → extract entities & relationships → build knowledge graph (Zep Cloud).',
          'Step 2 — Environment Setup: Generate agent personas from graph entities, configure simulation parameters.',
          'Step 3 — Simulation: Launch the OASIS multi-agent simulation on Info Plaza (Twitter-like) and Topic Community (Reddit-like).',
          'Step 4 — Report: An AI analyst agent queries the knowledge graph and generates a structured report.',
          'Step 5 — Interaction: Chat live with the simulated agents using their full persona and memory.',
        ]},
        { type: 'p', text: 'Use the sidebar to jump to help for any specific step.' },
      ],
    },

    step1: {
      title: 'Step 1 — Graph Build',
      body: [
        { type: 'p', text: 'Upload one or more documents (PDF, Markdown, or plain text). The system analyses them with an LLM to extract entities (people, organisations, concepts) and relationships, then stores them in a Zep Cloud knowledge graph.' },
        { type: 'h3', text: 'Options' },
        { type: 'table',
          headers: ['Option', 'Description'],
          rows: [
            ['Generate ontology', 'Default. The LLM infers entity types and relationship types from your documents.'],
            ['Import ontology (JSON)', 'Upload a previously exported ontology to reuse a known schema. Useful when running multiple simulations on the same domain.'],
          ]
        },
        { type: 'h3', text: 'After ontology generation' },
        { type: 'p', text: 'Review the inferred entity types in the panel. Click "Proceed to GraphRAG" to build the full graph. The graph panel on the left shows nodes and edges as they are created.' },
        { type: 'p', text: 'Minimum recommended: at least 15 distinct entity nodes to get meaningful simulations.' },
      ],
    },

    step2: {
      title: 'Step 2 — Environment Setup',
      body: [
        { type: 'p', text: 'The system generates an OASIS agent persona for each entity extracted from the graph, then creates the simulation configuration.' },

        { type: 'h3', text: 'Agent profile fields' },
        { type: 'p', text: 'Click any agent card to view or edit its profile. These fields shape how the LLM generates the agent\'s posts, comments, and reactions.' },
        { type: 'table',
          headers: ['Field', 'Values', 'Effect on simulation'],
          rows: [
            ['name', 'text', 'The @username displayed on posts.'],
            ['bio', 'text', 'Short public description. Used by the LLM as context when writing posts.'],
            ['persona', 'text (long)', 'Internal personality description. The most influential field — the LLM reads the full persona before every decision.'],
            ['age', 'integer', 'Adjusts linguistic register and topic interests.'],
            ['gender', 'male / female / other', 'Used to inform persona consistency.'],
            ['country', 'text', 'Provides cultural and timezone context.'],
            ['mbti', '16 codes (see below)', 'Communication style, proactivity, and reaction patterns.'],
            ['profession', 'text', 'Determines credibility level and content type generated.'],
            ['stance', 'supportive / opposing / neutral / observer', 'How the agent positions itself on the simulation topic.'],
            ['interested_topics', 'list of tags', 'Which posts the agent notices and reacts to.'],
          ]
        },

        { type: 'h3', text: 'MBTI personality types' },
        { type: 'p', text: 'The Myers-Briggs Type Indicator describes personality across 4 binary dimensions. MiroFish passes the MBTI code to the LLM inside the persona, influencing tone, initiative, and reasoning style.' },
        { type: 'table',
          headers: ['Dimension', 'Values', 'Simulation effect'],
          rows: [
            ['E / I  Extraversion / Introversion', 'E or I', 'E agents post proactively and start conversations. I agents respond more than they initiate.'],
            ['S / N  Sensing / Intuition', 'S or N', 'S agents cite concrete facts and data. N agents make abstract connections and conceptual arguments.'],
            ['T / F  Thinking / Feeling', 'T or F', 'T agents use analytical, reasoned tone. F agents use emotional, empathetic tone.'],
            ['J / P  Judging / Perceiving', 'J or P', 'J agents take clear positions and are decisive. P agents write open-ended, exploratory messages.'],
          ]
        },
        { type: 'p', text: 'Valid MBTI codes: ISTJ, ISFJ, INFJ, INTJ, ISTP, ISFP, INFP, INTP, ESTP, ESFP, ENFP, ENTP, ESTJ, ESFJ, ENFJ, ENTJ.' },

        { type: 'h3', text: 'Stance values' },
        { type: 'table',
          headers: ['Value', 'Meaning'],
          rows: [
            ['supportive', 'The agent actively promotes the simulation topic/position.'],
            ['opposing', 'The agent challenges or criticises the topic/position.'],
            ['neutral', 'The agent discusses the topic without a fixed position.'],
            ['observer', 'The agent mostly watches and rarely engages directly.'],
          ]
        },

        { type: 'h3', text: 'Activity parameters (per agent)' },
        { type: 'table',
          headers: ['Parameter', 'Range', 'Effect'],
          rows: [
            ['activity_level', '0.0 – 1.0', 'Overall probability of taking any action in a given round.'],
            ['posts_per_hour', '0.0 – N', 'How many original posts the agent creates per simulated hour.'],
            ['comments_per_hour', '0.0 – N', 'How many comments/replies per simulated hour.'],
            ['response_delay_min / max', 'minutes', 'Simulated latency before responding. Models real availability.'],
            ['sentiment_bias', '-1.0 – +1.0', 'Emotional tone: −1 = very negative, 0 = neutral, +1 = very positive.'],
            ['influence_weight', '0.0 – N', 'Multiplier: higher weight → more agents see and react to this agent\'s posts.'],
            ['active_hours', 'list 0–23', 'Hours of the simulated day when the agent is active.'],
          ]
        },

        { type: 'h3', text: 'Global simulation parameters' },
        { type: 'table',
          headers: ['Parameter', 'Range', 'Effect'],
          rows: [
            ['total_simulation_hours', '1 – 720 h', 'Total duration of the simulated world.'],
            ['minutes_per_round', '1 – 1440 min', 'Time granularity: each processing round = N minutes of fictional time.'],
            ['agents_per_hour_min / max', 'integer', 'How many agents activate per simulated hour.'],
            ['following_probability', '0.0 – 1.0', 'Probability that an agent follows another after an interaction.'],
            ['recsys_type', 'random / interest / twhin', 'Content recommendation algorithm (see below).'],
          ]
        },

        { type: 'h3', text: 'Recommendation algorithm (recsys_type)' },
        { type: 'table',
          headers: ['Value', 'Description'],
          rows: [
            ['random', 'Agents see random posts. Maximum diversity, minimal echo chambers.'],
            ['interest', 'Agents see posts matching their interested_topics. Moderate polarisation.'],
            ['twhin', 'Graph-based recommendation (social graph topology). High polarisation potential.'],
          ]
        },

        { type: 'h3', text: 'Activity multipliers by time of day' },
        { type: 'p', text: 'Peak, work, morning, and off-peak multipliers (range 0.1 – 5.0) scale agent activity during specific hour ranges. A multiplier of 2.0 means twice as many agents activate during that period.' },

        { type: 'h3', text: 'Platform parameters (Info Plaza & Topic Community)' },
        { type: 'table',
          headers: ['Parameter', 'Range', 'Effect'],
          rows: [
            ['recency_weight', '0.0 – 1.0', 'How much recent posts are boosted in the feed.'],
            ['popularity_weight', '0.0 – 1.0', 'How much high-interaction posts are boosted.'],
            ['relevance_weight', '0.0 – 1.0', 'How much topically relevant posts are boosted.'],
            ['viral_threshold', '0.0 – 1.0', 'Interaction ratio required to trigger viral amplification.'],
            ['echo_chamber_strength', '0.0 – 1.0', '0 = fully diverse feed; 1 = fully homophilic (only similar opinions).'],
          ]
        },

        { type: 'learnMore', links: [
          { label: 'Myers-Briggs Type Indicator (Wikipedia)', url: 'https://en.wikipedia.org/wiki/Myers%E2%80%93Briggs_Type_Indicator' },
          { label: 'OASIS documentation', url: 'https://docs.oasis.camel-ai.org/introduction' },
        ]},
      ],
    },

    step3: {
      title: 'Step 3 — Simulation',
      body: [
        { type: 'p', text: 'The simulation runs OASIS agents across two simultaneous platforms. Each round, a set of agents activates and decides what action to take based on their persona, the visible content, and the recommendation algorithm.' },
        { type: 'h3', text: 'Platforms' },
        { type: 'table',
          headers: ['Platform', 'Model', 'Available actions'],
          rows: [
            ['Info Plaza', 'Twitter/X-like public feed', 'POST, LIKE, REPOST, QUOTE, FOLLOW, IDLE'],
            ['Topic Community', 'Reddit-like threaded discussion', 'POST, COMMENT, LIKE, IDLE'],
          ]
        },
        { type: 'h3', text: 'Reading the progress panel' },
        { type: 'list', items: [
          'ROUND: current round / total rounds.',
          'TIME: elapsed wall-clock time.',
          'ACTS: number of actions taken so far.',
        ]},
        { type: 'h3', text: 'Stopping the simulation' },
        { type: 'p', text: 'Click "Stop simulation" to interrupt at any point. Partial results are saved and you can still generate a report. You cannot resume a stopped simulation.' },
        { type: 'h3', text: 'Max rounds override' },
        { type: 'p', text: 'The number of rounds is calculated from total_simulation_hours ÷ minutes_per_round configured in Step 2. You can override it with a custom value before launching.' },
      ],
    },

    step4: {
      title: 'Step 4 — Report',
      body: [
        { type: 'p', text: 'An AI analyst agent reads the simulation output and the knowledge graph to produce a structured report. It can make up to 5 Zep graph queries and 2 reflection rounds before writing the final text.' },
        { type: 'h3', text: 'What the report contains' },
        { type: 'list', items: [
          'Overview of information propagation patterns.',
          'Most influential agents and their impact.',
          'Stance distribution and opinion polarisation.',
          'Key topics and narrative arcs that emerged.',
          'Anomalies or unexpected behaviours.',
        ]},
        { type: 'h3', text: 'Regenerating the report' },
        { type: 'p', text: 'You can regenerate the report at any time. Each regeneration runs a fresh analysis — results may differ slightly due to LLM non-determinism.' },
      ],
    },

    step5: {
      title: 'Step 5 — Interaction',
      body: [
        { type: 'p', text: 'Chat in real time with the agents that participated in the simulation. Each agent responds using its persona, its memory of the simulation events, and the knowledge graph.' },
        { type: 'h3', text: 'How to use it' },
        { type: 'list', items: [
          'Select an agent from the list on the left.',
          'Type your message and press Enter or click Send.',
          'The agent replies in character, drawing on its persona and simulation history.',
          'Switch agents at any time — each agent has independent memory.',
        ]},
        { type: 'h3', text: 'Tips' },
        { type: 'list', items: [
          'Ask the agent about specific events that happened during the simulation.',
          'Ask for its opinion on other agents or topics.',
          'Agents with high influence_weight tend to be more opinionated and articulate.',
        ]},
      ],
    },
  },

  // ─── CATALÀ ─────────────────────────────────────────────────────────────────
  ca: {
    overview: {
      title: 'MiroFish — Com funciona',
      body: [
        { type: 'p', text: 'MiroFish és una plataforma de simulació social multi-agent amb IA. Proporciones documents de partida (articles, informes, notícies) i describes un escenari; MiroFish extreu els actors principals, construeix un graf de coneixement, genera perfils d\'agent realistes i executa una simulació de xarxes socials en dues plataformes.' },
        { type: 'h3', text: 'El flux de 5 passos' },
        { type: 'list', items: [
          'Pas 1 — Construcció del graf: Puja documents → extreu entitats i relacions → construeix el graf de coneixement (Zep Cloud).',
          'Pas 2 — Configuració de l\'entorn: Genera perfils d\'agent a partir de les entitats del graf, configura els paràmetres de simulació.',
          'Pas 3 — Simulació: Llança la simulació multi-agent OASIS a Info Plaza (similar a Twitter) i Topic Community (similar a Reddit).',
          'Pas 4 — Informe: Un agent analista de IA consulta el graf de coneixement i genera un informe estructurat.',
          'Pas 5 — Interacció: Xateja en directe amb els agents simulats usant el seu perfil i memòria complets.',
        ]},
        { type: 'p', text: 'Usa la barra lateral per anar directament a l\'ajuda de qualsevol pas.' },
      ],
    },

    step1: {
      title: 'Pas 1 — Construcció del graf',
      body: [
        { type: 'p', text: 'Puja un o més documents (PDF, Markdown o text pla). El sistema els analitza amb un LLM per extreure entitats (persones, organitzacions, conceptes) i relacions, i les emmagatzema en un graf de coneixement Zep Cloud.' },
        { type: 'h3', text: 'Opcions' },
        { type: 'table',
          headers: ['Opció', 'Descripció'],
          rows: [
            ['Generar ontologia', 'Per defecte. El LLM infereix els tipus d\'entitat i relació a partir dels documents.'],
            ['Importar ontologia (JSON)', 'Carrega una ontologia exportada prèviament per reutilitzar un esquema conegut. Útil quan es fan múltiples simulacions sobre el mateix domini.'],
          ]
        },
        { type: 'h3', text: 'Després de la generació d\'ontologia' },
        { type: 'p', text: 'Revisa els tipus d\'entitat inferits al panell. Clica "Proceed to GraphRAG" per construir el graf complet. El panell del graf a l\'esquerra mostra nodes i arestes a mesura que es creen.' },
        { type: 'p', text: 'Mínim recomanat: almenys 15 nodes d\'entitat distincts per obtenir simulacions significatives.' },
      ],
    },

    step2: {
      title: 'Pas 2 — Configuració de l\'entorn',
      body: [
        { type: 'p', text: 'El sistema genera un perfil d\'agent OASIS per a cada entitat extreta del graf, i després crea la configuració de la simulació.' },

        { type: 'h3', text: 'Camps del perfil d\'agent' },
        { type: 'p', text: 'Clica qualsevol targeta d\'agent per veure o editar el seu perfil. Aquests camps determinen com el LLM genera els posts, comentaris i reaccions de l\'agent.' },
        { type: 'table',
          headers: ['Camp', 'Valors', 'Efecte a la simulació'],
          rows: [
            ['name', 'text', 'El @username que apareix als posts.'],
            ['bio', 'text', 'Descripció pública breu. Usada pel LLM com a context en escriure posts.'],
            ['persona', 'text (llarg)', 'Descripció interna de la personalitat. El camp més influent: el LLM llegeix la persona completa abans de cada decisió.'],
            ['age', 'enter', 'Ajusta el registre lingüístic i els temes d\'interès.'],
            ['gender', 'male / female / other', 'Informa la consistència del perfil.'],
            ['country', 'text', 'Proporciona context cultural i de fus horari.'],
            ['mbti', '16 codis (veure taula)', 'Estil de comunicació, proactivitat i patrons de reacció.'],
            ['profession', 'text', 'Determina el nivell de credibilitat i el tipus de contingut generat.'],
            ['stance', 'supportive / opposing / neutral / observer', 'Com es posiciona l\'agent davant el tema de la simulació.'],
            ['interested_topics', 'llista d\'etiquetes', 'Quins posts nota i als quals reacciona l\'agent.'],
          ]
        },

        { type: 'h3', text: 'Tipus de personalitat MBTI' },
        { type: 'p', text: 'L\'Indicador de Tipus Myers-Briggs descriu la personalitat en 4 dimensions binàries. MiroFish passa el codi MBTI al LLM dins del perfil, influint en el to, la iniciativa i l\'estil de raonament.' },
        { type: 'table',
          headers: ['Dimensió', 'Valors', 'Efecte a la simulació'],
          rows: [
            ['E / I  Extroversió / Introversió', 'E o I', 'Els agents E publiquen de manera proactiva i inicien converses. Els agents I responen més que no inicien.'],
            ['S / N  Sensació / Intuïció', 'S o N', 'Els agents S citen fets i dades concretes. Els agents N fan connexions abstractes i arguments conceptuals.'],
            ['T / F  Pensament / Sentiment', 'T o F', 'Els agents T usen un to analític i razonat. Els agents F usen un to emocional i empàtic.'],
            ['J / P  Judici / Percepció', 'J o P', 'Els agents J prenen posicions clares i són decisius. Els agents P escriuen missatges oberts i exploratoris.'],
          ]
        },
        { type: 'p', text: 'Codis MBTI vàlids: ISTJ, ISFJ, INFJ, INTJ, ISTP, ISFP, INFP, INTP, ESTP, ESFP, ENFP, ENTP, ESTJ, ESFJ, ENFJ, ENTJ.' },

        { type: 'h3', text: 'Valors de stance (postura)' },
        { type: 'table',
          headers: ['Valor', 'Significat'],
          rows: [
            ['supportive', 'L\'agent promou activament el tema/posició de la simulació.'],
            ['opposing', 'L\'agent qüestiona o critica el tema/posició.'],
            ['neutral', 'L\'agent discuteix el tema sense posició fixa.'],
            ['observer', 'L\'agent principalment observa i rarament participa directament.'],
          ]
        },

        { type: 'h3', text: 'Paràmetres d\'activitat (per agent)' },
        { type: 'table',
          headers: ['Paràmetre', 'Rang', 'Efecte'],
          rows: [
            ['activity_level', '0.0 – 1.0', 'Probabilitat global de fer qualsevol acció en una ronda donada.'],
            ['posts_per_hour', '0.0 – N', 'Quants posts originals crea l\'agent per hora simulada.'],
            ['comments_per_hour', '0.0 – N', 'Quants comentaris/respostes per hora simulada.'],
            ['response_delay_min / max', 'minuts', 'Latència simulada abans de respondre. Modela la disponibilitat real.'],
            ['sentiment_bias', '-1.0 – +1.0', 'To emocional: −1 = molt negatiu, 0 = neutre, +1 = molt positiu.'],
            ['influence_weight', '0.0 – N', 'Multiplicador: pes més alt → més agents veuen i reaccionen als posts d\'aquest agent.'],
            ['active_hours', 'llista 0–23', 'Hores del dia simulat en què l\'agent és actiu.'],
          ]
        },

        { type: 'h3', text: 'Paràmetres globals de la simulació' },
        { type: 'table',
          headers: ['Paràmetre', 'Rang', 'Efecte'],
          rows: [
            ['total_simulation_hours', '1 – 720 h', 'Durada total del món simulat.'],
            ['minutes_per_round', '1 – 1440 min', 'Granularitat temporal: cada ronda de processament = N minuts de temps fictici.'],
            ['agents_per_hour_min / max', 'enter', 'Quants agents s\'activen per hora simulada.'],
            ['following_probability', '0.0 – 1.0', 'Probabilitat que un agent segueixi un altre després d\'una interacció.'],
            ['recsys_type', 'random / interest / twhin', 'Algorisme de recomanació de contingut (veure taula).'],
          ]
        },

        { type: 'h3', text: 'Algorisme de recomanació (recsys_type)' },
        { type: 'table',
          headers: ['Valor', 'Descripció'],
          rows: [
            ['random', 'Els agents veuen posts aleatoris. Màxima diversitat, mínimes cambres d\'eco.'],
            ['interest', 'Els agents veuen posts relacionats amb els seus interested_topics. Polarització moderada.'],
            ['twhin', 'Recomanació basada en graf (topologia del graf social). Alt potencial de polarització.'],
          ]
        },

        { type: 'h3', text: 'Multiplicadors d\'activitat per franja horària' },
        { type: 'p', text: 'Els multiplicadors de pic, laboral, matí i valle (rang 0.1 – 5.0) escalen l\'activitat dels agents durant franges horàries específiques. Un multiplicador de 2.0 significa el doble d\'agents actius durant aquell període.' },

        { type: 'h3', text: 'Paràmetres de plataforma (Info Plaza i Topic Community)' },
        { type: 'table',
          headers: ['Paràmetre', 'Rang', 'Efecte'],
          rows: [
            ['recency_weight', '0.0 – 1.0', 'Quant es potencien els posts recents al feed.'],
            ['popularity_weight', '0.0 – 1.0', 'Quant es potencien els posts amb més interaccions.'],
            ['relevance_weight', '0.0 – 1.0', 'Quant es potencien els posts temàticament rellevants.'],
            ['viral_threshold', '0.0 – 1.0', 'Ràtio d\'interaccions necessari per activar l\'amplificació viral.'],
            ['echo_chamber_strength', '0.0 – 1.0', '0 = feed divers; 1 = feed completament homofílic (només opinions similars).'],
          ]
        },

        { type: 'learnMore', links: [
          { label: 'Myers-Briggs Type Indicator (Viquipèdia)', url: 'https://ca.wikipedia.org/wiki/Myers_Briggs_Type_Indicator' },
          { label: 'Documentació OASIS', url: 'https://docs.oasis.camel-ai.org/introduction' },
        ]},
      ],
    },

    step3: {
      title: 'Pas 3 — Simulació',
      body: [
        { type: 'p', text: 'La simulació executa agents OASIS en dues plataformes simultànies. A cada ronda, un conjunt d\'agents s\'activa i decideix quina acció fer basant-se en el seu perfil, el contingut visible i l\'algorisme de recomanació.' },
        { type: 'h3', text: 'Plataformes' },
        { type: 'table',
          headers: ['Plataforma', 'Model', 'Accions disponibles'],
          rows: [
            ['Info Plaza', 'Feed públic similar a Twitter/X', 'POST, LIKE, REPOST, QUOTE, FOLLOW, IDLE'],
            ['Topic Community', 'Discussió en fils similar a Reddit', 'POST, COMMENT, LIKE, IDLE'],
          ]
        },
        { type: 'h3', text: 'Llegir el panell de progrés' },
        { type: 'list', items: [
          'ROUND: ronda actual / total de rondes.',
          'TIME: temps de rellotge transcorregut.',
          'ACTS: nombre d\'accions realitzades fins ara.',
        ]},
        { type: 'h3', text: 'Aturar la simulació' },
        { type: 'p', text: 'Clica "Atura la simulació" per interrompre-la en qualsevol moment. Els resultats parcials es guarden i pots generar igualment un informe. No es pot reprendre una simulació aturada.' },
        { type: 'h3', text: 'Sobrescriure el nombre de rondes' },
        { type: 'p', text: 'El nombre de rondes es calcula com total_simulation_hours ÷ minutes_per_round configurats al Pas 2. Pots sobreescriure-ho amb un valor personalitzat abans de llançar.' },
      ],
    },

    step4: {
      title: 'Pas 4 — Informe',
      body: [
        { type: 'p', text: 'Un agent analista de IA llegeix la sortida de la simulació i el graf de coneixement per produir un informe estructurat. Pot fer fins a 5 consultes al graf Zep i 2 rondes de reflexió abans d\'escriure el text final.' },
        { type: 'h3', text: 'Contingut de l\'informe' },
        { type: 'list', items: [
          'Visió general dels patrons de propagació de la informació.',
          'Agents més influents i el seu impacte.',
          'Distribució de postures i polarització d\'opinions.',
          'Temes clau i arcs narratius que han emergit.',
          'Anomalies o comportaments inesperats.',
        ]},
        { type: 'h3', text: 'Regenerar l\'informe' },
        { type: 'p', text: 'Pots regenerar l\'informe en qualsevol moment. Cada regeneració executa una nova anàlisi — els resultats poden variar lleugerament per la no-determinisme del LLM.' },
      ],
    },

    step5: {
      title: 'Pas 5 — Interacció',
      body: [
        { type: 'p', text: 'Xateja en temps real amb els agents que han participat a la simulació. Cada agent respon usant el seu perfil, la seva memòria dels esdeveniments de la simulació i el graf de coneixement.' },
        { type: 'h3', text: 'Com usar-ho' },
        { type: 'list', items: [
          'Selecciona un agent de la llista de l\'esquerra.',
          'Escriu el teu missatge i prem Enter o clica Envia.',
          'L\'agent respon en el seu personatge, basant-se en el seu perfil i historial de simulació.',
          'Canvia d\'agent en qualsevol moment — cada agent té memòria independent.',
        ]},
        { type: 'h3', text: 'Consells' },
        { type: 'list', items: [
          'Pregunta a l\'agent sobre esdeveniments específics que han passat durant la simulació.',
          'Demana la seva opinió sobre altres agents o temes.',
          'Els agents amb influence_weight alt tendeixen a ser més amb opinions i articulats.',
        ]},
      ],
    },
  },

  // ─── ESPAÑOL ────────────────────────────────────────────────────────────────
  es: {
    overview: {
      title: 'MiroFish — Cómo funciona',
      body: [
        { type: 'p', text: 'MiroFish es una plataforma de simulación social multi-agente con IA. Proporcionas documentos semilla (artículos, informes, noticias) y describes un escenario; MiroFish extrae los actores principales, construye un grafo de conocimiento, genera perfiles de agente realistas y ejecuta una simulación de redes sociales en dos plataformas.' },
        { type: 'h3', text: 'El flujo de 5 pasos' },
        { type: 'list', items: [
          'Paso 1 — Construcción del grafo: Sube documentos → extrae entidades y relaciones → construye el grafo de conocimiento (Zep Cloud).',
          'Paso 2 — Configuración del entorno: Genera perfiles de agente a partir de las entidades del grafo, configura los parámetros de simulación.',
          'Paso 3 — Simulación: Lanza la simulación multi-agente OASIS en Info Plaza (similar a Twitter) y Topic Community (similar a Reddit).',
          'Paso 4 — Informe: Un agente analista de IA consulta el grafo de conocimiento y genera un informe estructurado.',
          'Paso 5 — Interacción: Chatea en directo con los agentes simulados usando su perfil y memoria completos.',
        ]},
        { type: 'p', text: 'Usa la barra lateral para ir directamente a la ayuda de cualquier paso.' },
      ],
    },

    step1: {
      title: 'Paso 1 — Construcción del grafo',
      body: [
        { type: 'p', text: 'Sube uno o más documentos (PDF, Markdown o texto plano). El sistema los analiza con un LLM para extraer entidades (personas, organizaciones, conceptos) y relaciones, y las almacena en un grafo de conocimiento Zep Cloud.' },
        { type: 'h3', text: 'Opciones' },
        { type: 'table',
          headers: ['Opción', 'Descripción'],
          rows: [
            ['Generar ontología', 'Por defecto. El LLM infiere los tipos de entidad y relación a partir de los documentos.'],
            ['Importar ontología (JSON)', 'Carga una ontología exportada previamente para reutilizar un esquema conocido. Útil para múltiples simulaciones sobre el mismo dominio.'],
          ]
        },
        { type: 'h3', text: 'Después de la generación de ontología' },
        { type: 'p', text: 'Revisa los tipos de entidad inferidos en el panel. Haz clic en "Proceed to GraphRAG" para construir el grafo completo. El panel del grafo a la izquierda muestra nodos y aristas a medida que se crean.' },
        { type: 'p', text: 'Mínimo recomendado: al menos 15 nodos de entidad distintos para obtener simulaciones significativas.' },
      ],
    },

    step2: {
      title: 'Paso 2 — Configuración del entorno',
      body: [
        { type: 'p', text: 'El sistema genera un perfil de agente OASIS para cada entidad extraída del grafo, y luego crea la configuración de la simulación.' },

        { type: 'h3', text: 'Campos del perfil de agente' },
        { type: 'p', text: 'Haz clic en cualquier tarjeta de agente para ver o editar su perfil. Estos campos determinan cómo el LLM genera los posts, comentarios y reacciones del agente.' },
        { type: 'table',
          headers: ['Campo', 'Valores', 'Efecto en la simulación'],
          rows: [
            ['name', 'texto', 'El @username que aparece en los posts.'],
            ['bio', 'texto', 'Descripción pública breve. Usada por el LLM como contexto al escribir posts.'],
            ['persona', 'texto (largo)', 'Descripción interna de la personalidad. El campo más influyente: el LLM lee la persona completa antes de cada decisión.'],
            ['age', 'entero', 'Ajusta el registro lingüístico y los temas de interés.'],
            ['gender', 'male / female / other', 'Informa la consistencia del perfil.'],
            ['country', 'texto', 'Proporciona contexto cultural y de zona horaria.'],
            ['mbti', '16 códigos (ver tabla)', 'Estilo de comunicación, proactividad y patrones de reacción.'],
            ['profession', 'texto', 'Determina el nivel de credibilidad y el tipo de contenido generado.'],
            ['stance', 'supportive / opposing / neutral / observer', 'Cómo se posiciona el agente ante el tema de la simulación.'],
            ['interested_topics', 'lista de etiquetas', 'Qué posts nota y a cuáles reacciona el agente.'],
          ]
        },

        { type: 'h3', text: 'Tipos de personalidad MBTI' },
        { type: 'p', text: 'El Indicador de Tipos Myers-Briggs describe la personalidad en 4 dimensiones binarias. MiroFish pasa el código MBTI al LLM dentro del perfil, influyendo en el tono, la iniciativa y el estilo de razonamiento.' },
        { type: 'table',
          headers: ['Dimensión', 'Valores', 'Efecto en la simulación'],
          rows: [
            ['E / I  Extraversión / Introversión', 'E o I', 'Los agentes E publican proactivamente e inician conversaciones. Los agentes I responden más que no inician.'],
            ['S / N  Sensación / Intuición', 'S o N', 'Los agentes S citan hechos y datos concretos. Los agentes N hacen conexiones abstractas y argumentos conceptuales.'],
            ['T / F  Pensamiento / Sentimiento', 'T o F', 'Los agentes T usan un tono analítico y razonado. Los agentes F usan un tono emocional y empático.'],
            ['J / P  Juicio / Percepción', 'J o P', 'Los agentes J toman posiciones claras y son decisivos. Los agentes P escriben mensajes abiertos y exploratorios.'],
          ]
        },
        { type: 'p', text: 'Códigos MBTI válidos: ISTJ, ISFJ, INFJ, INTJ, ISTP, ISFP, INFP, INTP, ESTP, ESFP, ENFP, ENTP, ESTJ, ESFJ, ENFJ, ENTJ.' },

        { type: 'h3', text: 'Valores de stance (postura)' },
        { type: 'table',
          headers: ['Valor', 'Significado'],
          rows: [
            ['supportive', 'El agente promueve activamente el tema/posición de la simulación.'],
            ['opposing', 'El agente cuestiona o critica el tema/posición.'],
            ['neutral', 'El agente discute el tema sin una posición fija.'],
            ['observer', 'El agente principalmente observa y raramente participa directamente.'],
          ]
        },

        { type: 'h3', text: 'Parámetros de actividad (por agente)' },
        { type: 'table',
          headers: ['Parámetro', 'Rango', 'Efecto'],
          rows: [
            ['activity_level', '0.0 – 1.0', 'Probabilidad global de realizar cualquier acción en una ronda dada.'],
            ['posts_per_hour', '0.0 – N', 'Cuántos posts originales crea el agente por hora simulada.'],
            ['comments_per_hour', '0.0 – N', 'Cuántos comentarios/respuestas por hora simulada.'],
            ['response_delay_min / max', 'minutos', 'Latencia simulada antes de responder. Modela la disponibilidad real.'],
            ['sentiment_bias', '-1.0 – +1.0', 'Tono emocional: −1 = muy negativo, 0 = neutro, +1 = muy positivo.'],
            ['influence_weight', '0.0 – N', 'Multiplicador: peso más alto → más agentes ven y reaccionan a los posts de este agente.'],
            ['active_hours', 'lista 0–23', 'Horas del día simulado en que el agente está activo.'],
          ]
        },

        { type: 'h3', text: 'Parámetros globales de la simulación' },
        { type: 'table',
          headers: ['Parámetro', 'Rango', 'Efecto'],
          rows: [
            ['total_simulation_hours', '1 – 720 h', 'Duración total del mundo simulado.'],
            ['minutes_per_round', '1 – 1440 min', 'Granularidad temporal: cada ronda de procesamiento = N minutos de tiempo ficticio.'],
            ['agents_per_hour_min / max', 'entero', 'Cuántos agentes se activan por hora simulada.'],
            ['following_probability', '0.0 – 1.0', 'Probabilidad de que un agente siga a otro tras una interacción.'],
            ['recsys_type', 'random / interest / twhin', 'Algoritmo de recomendación de contenido (ver tabla).'],
          ]
        },

        { type: 'h3', text: 'Algoritmo de recomendación (recsys_type)' },
        { type: 'table',
          headers: ['Valor', 'Descripción'],
          rows: [
            ['random', 'Los agentes ven posts aleatorios. Máxima diversidad, mínimas cámaras de eco.'],
            ['interest', 'Los agentes ven posts relacionados con sus interested_topics. Polarización moderada.'],
            ['twhin', 'Recomendación basada en grafo (topología del grafo social). Alto potencial de polarización.'],
          ]
        },

        { type: 'h3', text: 'Multiplicadores de actividad por franja horaria' },
        { type: 'p', text: 'Los multiplicadores de pico, laboral, mañana y valle (rango 0.1 – 5.0) escalan la actividad de los agentes durante franjas horarias específicas. Un multiplicador de 2.0 significa el doble de agentes activos durante ese período.' },

        { type: 'h3', text: 'Parámetros de plataforma (Info Plaza y Topic Community)' },
        { type: 'table',
          headers: ['Parámetro', 'Rango', 'Efecto'],
          rows: [
            ['recency_weight', '0.0 – 1.0', 'Cuánto se potencian los posts recientes en el feed.'],
            ['popularity_weight', '0.0 – 1.0', 'Cuánto se potencian los posts con más interacciones.'],
            ['relevance_weight', '0.0 – 1.0', 'Cuánto se potencian los posts temáticamente relevantes.'],
            ['viral_threshold', '0.0 – 1.0', 'Ratio de interacciones necesario para activar la amplificación viral.'],
            ['echo_chamber_strength', '0.0 – 1.0', '0 = feed diverso; 1 = feed completamente homofílico (solo opiniones similares).'],
          ]
        },

        { type: 'learnMore', links: [
          { label: 'Indicador de Tipos Myers-Briggs (Wikipedia)', url: 'https://es.wikipedia.org/wiki/Indicador_Myers-Briggs' },
          { label: 'Documentación OASIS', url: 'https://docs.oasis.camel-ai.org/introduction' },
        ]},
      ],
    },

    step3: {
      title: 'Paso 3 — Simulación',
      body: [
        { type: 'p', text: 'La simulación ejecuta agentes OASIS en dos plataformas simultáneas. En cada ronda, un conjunto de agentes se activa y decide qué acción realizar basándose en su perfil, el contenido visible y el algoritmo de recomendación.' },
        { type: 'h3', text: 'Plataformas' },
        { type: 'table',
          headers: ['Plataforma', 'Modelo', 'Acciones disponibles'],
          rows: [
            ['Info Plaza', 'Feed público similar a Twitter/X', 'POST, LIKE, REPOST, QUOTE, FOLLOW, IDLE'],
            ['Topic Community', 'Discusión en hilos similar a Reddit', 'POST, COMMENT, LIKE, IDLE'],
          ]
        },
        { type: 'h3', text: 'Leer el panel de progreso' },
        { type: 'list', items: [
          'ROUND: ronda actual / total de rondas.',
          'TIME: tiempo de reloj transcurrido.',
          'ACTS: número de acciones realizadas hasta ahora.',
        ]},
        { type: 'h3', text: 'Detener la simulación' },
        { type: 'p', text: 'Haz clic en "Detener simulación" para interrumpirla en cualquier momento. Los resultados parciales se guardan y puedes generar igualmente un informe. No se puede reanudar una simulación detenida.' },
        { type: 'h3', text: 'Sobrescribir el número de rondas' },
        { type: 'p', text: 'El número de rondas se calcula como total_simulation_hours ÷ minutes_per_round configurados en el Paso 2. Puedes sobrescribirlo con un valor personalizado antes de lanzar.' },
      ],
    },

    step4: {
      title: 'Paso 4 — Informe',
      body: [
        { type: 'p', text: 'Un agente analista de IA lee la salida de la simulación y el grafo de conocimiento para producir un informe estructurado. Puede realizar hasta 5 consultas al grafo Zep y 2 rondas de reflexión antes de escribir el texto final.' },
        { type: 'h3', text: 'Contenido del informe' },
        { type: 'list', items: [
          'Visión general de los patrones de propagación de la información.',
          'Agentes más influyentes y su impacto.',
          'Distribución de posturas y polarización de opiniones.',
          'Temas clave y arcos narrativos que han emergido.',
          'Anomalías o comportamientos inesperados.',
        ]},
        { type: 'h3', text: 'Regenerar el informe' },
        { type: 'p', text: 'Puedes regenerar el informe en cualquier momento. Cada regeneración ejecuta un nuevo análisis — los resultados pueden variar ligeramente por el no-determinismo del LLM.' },
      ],
    },

    step5: {
      title: 'Paso 5 — Interacción',
      body: [
        { type: 'p', text: 'Chatea en tiempo real con los agentes que participaron en la simulación. Cada agente responde usando su perfil, su memoria de los eventos de la simulación y el grafo de conocimiento.' },
        { type: 'h3', text: 'Cómo usarlo' },
        { type: 'list', items: [
          'Selecciona un agente de la lista de la izquierda.',
          'Escribe tu mensaje y pulsa Enter o haz clic en Enviar.',
          'El agente responde en su personaje, basándose en su perfil e historial de simulación.',
          'Cambia de agente en cualquier momento — cada agente tiene memoria independiente.',
        ]},
        { type: 'h3', text: 'Consejos' },
        { type: 'list', items: [
          'Pregunta al agente sobre eventos específicos que ocurrieron durante la simulación.',
          'Pide su opinión sobre otros agentes o temas.',
          'Los agentes con influence_weight alto tienden a ser más expresivos y articulados.',
        ]},
      ],
    },
  },
}

export const SECTIONS = ['overview', 'step1', 'step2', 'step3', 'step4', 'step5']
