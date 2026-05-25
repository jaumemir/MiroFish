"""Admin API: configuració sistema i historial d'execucions."""
from flask import request, jsonify
from sqlalchemy import select, desc, func
from . import admin_bp
from .. import require_admin
from ..db import get_session
from ..models.db_models import SystemConfigModel, SimulationModel, ProjectModel, UserModel, GraphModel


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


@admin_bp.route('/config', methods=['PATCH'])
@require_admin
def patch_config():
    data = request.get_json(silent=True) or {}
    with get_session() as db:
        for key, value in data.items():
            entry = db.get(SystemConfigModel, key)
            if entry is None:
                continue
            if entry.is_secret and value in (None, ''):
                continue
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

        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar()
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


@admin_bp.route('/projects/<project_id>', methods=['GET'])
@require_admin
def get_admin_project(project_id):
    with get_session() as db:
        proj = db.get(ProjectModel, project_id)
        if not proj:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        user = db.get(UserModel, proj.user_id) if proj.user_id else None
        graphs = db.execute(
            select(GraphModel).where(GraphModel.project_id == project_id)
            .order_by(GraphModel.created_at)
        ).scalars().all()
        simulations = db.execute(
            select(SimulationModel).where(SimulationModel.project_id == project_id)
            .order_by(SimulationModel.created_at)
        ).scalars().all()
        data = {
            'project_id': proj.id,
            'name': proj.name,
            'status': proj.status,
            'created_at': proj.created_at.isoformat(),
            'owner_email': user.email if user else None,
            'owner_name': user.name if user else None,
            'graphs': [
                {
                    'graph_id': g.id,
                    'external_id': g.external_id,
                    'backend': g.backend,
                    'status': g.status,
                    'node_count': g.node_count,
                    'edge_count': g.edge_count,
                    'created_at': g.created_at.isoformat(),
                }
                for g in graphs
            ],
            'simulations': [
                {
                    'simulation_id': s.id,
                    'graph_id': s.graph_id,
                    'status': s.status,
                    'platform': s.platform,
                    'rounds_total': s.rounds_total,
                    'rounds_completed': s.rounds_completed,
                    'created_at': s.created_at.isoformat(),
                }
                for s in simulations
            ],
        }
    return jsonify({'success': True, 'data': data})


@admin_bp.route('/projects/<project_id>', methods=['DELETE'])
@require_admin
def delete_admin_project(project_id):
    import logging
    logger = logging.getLogger('mirofish.admin')
    from .. import get_storage
    from ..services.graph_builder import GraphBuilderService
    from sqlalchemy.orm import selectinload

    storage = get_storage()
    with get_session() as db:
        proj = db.execute(
            select(ProjectModel)
            .where(ProjectModel.id == project_id)
            .options(selectinload(ProjectModel.graphs))
        ).scalar_one_or_none()
        if not proj:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        for graph in proj.graphs:
            if graph.external_id:
                try:
                    GraphBuilderService().delete_graph(graph.external_id)
                except Exception as exc:
                    logger.warning('delete_admin_project: delete_graph(%s) failed: %s',
                                   graph.external_id, exc)
        try:
            storage.delete_prefix(f'projects/{project_id}')
        except Exception as exc:
            logger.warning('delete_admin_project: storage.delete_prefix(%s) failed: %s',
                           project_id, exc)

        db.delete(proj)
        db.commit()

    return jsonify({'success': True})


@admin_bp.route('/simulations/<simulation_id>', methods=['DELETE'])
@require_admin
def delete_admin_simulation(simulation_id):
    import shutil, os, logging
    from ..services.simulation_manager import SimulationManager
    from ..config import Config

    logger = logging.getLogger('mirofish.api.admin')

    with get_session() as db:
        sim = db.get(SimulationModel, simulation_id)
        if not sim:
            return jsonify({'success': False, 'error': 'Simulation not found'}), 404
        db.delete(sim)
        db.commit()

    # Delete per-simulation graph from Neo4j/Zep if it exists
    manager = SimulationManager()
    sim_state = manager.get_simulation(simulation_id)
    if sim_state and sim_state.graph_id_simulation:
        try:
            from ..graph import get_graph_backend as _get_gb
            _get_gb().delete_graph(sim_state.graph_id_simulation)
            logger.info(f"Deleted simulation graph: {sim_state.graph_id_simulation}")
        except Exception as graph_err:
            logger.warning(f"Could not delete simulation graph {sim_state.graph_id_simulation}: {graph_err}")

    # Remove filesystem data
    manager._simulations.pop(simulation_id, None)
    sim_dir = manager._get_simulation_dir(simulation_id)
    if os.path.isdir(sim_dir):
        shutil.rmtree(sim_dir, ignore_errors=True)

    return jsonify({'success': True})


@admin_bp.route('/projects', methods=['GET'])
@require_admin
def list_admin_projects():
    with get_session() as db:
        stmt = (
            select(
                ProjectModel,
                UserModel,
                func.count(SimulationModel.id).label('simulation_count'),
            )
            .outerjoin(UserModel, ProjectModel.user_id == UserModel.id)
            .outerjoin(SimulationModel, SimulationModel.project_id == ProjectModel.id)
            .group_by(ProjectModel.id, UserModel.id)
            .order_by(desc(ProjectModel.created_at))
        )
        rows = db.execute(stmt).all()
        result = []
        for proj, user, sim_count in rows:
            result.append({
                'project_id': proj.id,
                'name': proj.name,
                'status': proj.status,
                'owner_email': user.email if user else None,
                'owner_name': user.name if user else None,
                'simulation_count': sim_count,
                'created_at': proj.created_at.isoformat(),
            })
    return jsonify({'success': True, 'data': result, 'total': len(result)})
