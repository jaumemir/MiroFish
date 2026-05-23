#!/usr/bin/env python3
"""
Inicialitzar el sistema MiroFish per al primer ús.
Ús: ADMIN_EMAIL=admin@dev.local ADMIN_PASSWORD=adminpass123 uv run python backend/scripts/init_system.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def main():
    from app.config import Config
    from app.db import init_db, get_session
    from app.models.db_models import UserModel, SystemConfigModel
    from app.services.auth_service import hash_password
    from sqlalchemy import select

    db_url = Config.DATABASE_URL
    short_url = db_url.split('@')[-1] if '@' in db_url else db_url
    print(f"[init_system] Connecting to: {short_url}")
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
            ('limits.max_projects_per_user',    '20', 'int', 'limits', 'Màx. projectes per usuari',          '', False),
            ('limits.max_simulations',          '10', 'int', 'limits', 'Màx. simulacions',                   '', False),
            ('limits.parallel_profile_workers', '5',  'int', 'limits', 'Workers paral·lels generació perfils', 'Threads simultanis per generar perfils d\'agent (Step 2)', False),
            ('limits.interview_workers',        '2',  'int', 'limits', 'Workers paral·lels entrevista',        'Threads simultanis per cerques Zep durant l\'entrevista offline', False),
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
