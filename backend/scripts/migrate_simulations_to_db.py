#!/usr/bin/env python3
"""
Migra les simulacions existents al disc a la base de dades.

Per a cada carpeta a OASIS_SIMULATION_DATA_DIR que contingui un state.json vàlid:
- Si el project_id existeix a la BD → insereix una fila a SimulationModel (si no existia)
- Si el project_id no existeix → s'ignora (pot ser un projecte eliminat)

Ús (des de l'arrel del projecte):
    uv run python backend/scripts/migrate_simulations_to_db.py

Flags:
    --dry-run    Mostra què faria sense escriure res a la BD
"""
import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def main(dry_run: bool = False):
    from app.config import Config
    from app.db import init_db, get_session
    from app.models.db_models import SimulationModel, ProjectModel, GraphModel
    from sqlalchemy import select

    db_url = Config.DATABASE_URL
    short_url = db_url.split('@')[-1] if '@' in db_url else db_url
    print(f"BD: {short_url}")
    print(f"Dir simulacions: {Config.OASIS_SIMULATION_DATA_DIR}")
    if dry_run:
        print("MODE DRY-RUN — no s'escriu res\n")
    else:
        print()

    init_db(Config.DATABASE_URL)

    sim_dir = Config.OASIS_SIMULATION_DATA_DIR
    if not os.path.exists(sim_dir):
        print(f"Directori no trobat: {sim_dir}")
        sys.exit(1)

    entries = sorted(
        d for d in os.listdir(sim_dir)
        if not d.startswith('.') and os.path.isdir(os.path.join(sim_dir, d))
    )
    print(f"Carpetes trobades: {len(entries)}\n")

    stats = {'inserted': 0, 'skipped_exists': 0, 'skipped_no_project': 0, 'skipped_invalid': 0}

    for sim_id in entries:
        state_file = os.path.join(sim_dir, sim_id, "state.json")
        if not os.path.exists(state_file):
            print(f"  {sim_id}  → sense state.json, ignorat")
            stats['skipped_invalid'] += 1
            continue

        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"  {sim_id}  → error llegint state.json: {e}")
            stats['skipped_invalid'] += 1
            continue

        project_id = data.get('project_id', '')
        graph_ext_id = data.get('graph_id', '')
        enable_twitter = data.get('enable_twitter', True)
        status = data.get('status', 'created')
        platform = 'twitter' if enable_twitter else 'reddit'
        try:
            created_at = datetime.fromisoformat(data.get('created_at', ''))
        except Exception:
            created_at = datetime.now()

        with get_session() as db:
            # Comprova si ja existeix a la BD
            existing = db.get(SimulationModel, sim_id)
            if existing:
                print(f"  {sim_id}  → ja existeix a la BD (status={existing.status}), omès")
                stats['skipped_exists'] += 1
                continue

            # Comprova que el projecte existeix
            project = db.get(ProjectModel, project_id)
            if not project:
                print(f"  {sim_id}  → projecte {project_id!r} no trobat a la BD, ignorat")
                stats['skipped_no_project'] += 1
                continue

            # Resol external_id → GraphModel.id
            graph_uuid = None
            if graph_ext_id:
                stmt = select(GraphModel).where(GraphModel.external_id == graph_ext_id)
                graph_rec = db.execute(stmt).scalars().first()
                if graph_rec:
                    graph_uuid = graph_rec.id

            print(f"  {sim_id}  → projecte={project_id[:8]}… status={status} platform={platform}"
                  f" graph={'✓' if graph_uuid else '—'}", end='')

            if dry_run:
                print("  [dry-run, no inserit]")
            else:
                rec = SimulationModel(
                    id=sim_id,
                    project_id=project_id,
                    graph_id=graph_uuid,
                    status=status,
                    platform=platform,
                    created_at=created_at,
                )
                db.add(rec)
                db.commit()
                print("  → inserit ✓")

            stats['inserted'] += 1

    print(f"""
Resum:
  Inserides:             {stats['inserted']}
  Ja existien a la BD:   {stats['skipped_exists']}
  Projecte no trobat:    {stats['skipped_no_project']}
  state.json invàlid:    {stats['skipped_invalid']}
""")
    if dry_run:
        print("Torna a executar sense --dry-run per aplicar els canvis.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migra simulacions del disc a la BD')
    parser.add_argument('--dry-run', action='store_true', help='Mostra el pla sense escriure')
    args = parser.parse_args()
    main(dry_run=args.dry_run)
