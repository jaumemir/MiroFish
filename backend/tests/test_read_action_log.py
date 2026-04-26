import json
import os
import tempfile
import pytest
from unittest.mock import patch


def _make_state(sim_id="test-sim"):
    from app.services.simulation_runner import SimulationRunState
    return SimulationRunState(simulation_id=sim_id)


def _call_read(path, position, state, platform="twitter"):
    from app.services.simulation_runner import SimulationRunner
    with patch.dict(SimulationRunner._graph_memory_enabled, {}, clear=False):
        return SimulationRunner._read_action_log(path, position, state, platform)


_ACTION = {
    "action_type": "post", "agent_id": 1, "agent_name": "Alice",
    "round": 1, "timestamp": "2026-01-01T00:00:00",
    "action_args": {}, "result": None, "success": True,
}


def test_complete_lines_all_processed():
    """All lines ending with \n are processed; final position equals file size."""
    state = _make_state()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        f.write(json.dumps(_ACTION) + '\n')
        f.write(json.dumps({**_ACTION, "agent_id": 2, "agent_name": "Bob"}) + '\n')
        path = f.name
    try:
        new_pos = _call_read(path, 0, state)
        assert len(state.recent_actions) == 2
        assert new_pos == os.path.getsize(path)
    finally:
        os.unlink(path)


def test_partial_last_line_not_processed():
    """Partial last line (no trailing \n) is NOT processed; position stays before it."""
    state = _make_state("test-partial")
    complete = json.dumps(_ACTION) + '\n'
    partial = '{"action_type": "like", "agent_id": 2'  # no \n — in-progress write

    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        f.write(complete)
        f.write(partial)
        path = f.name
    try:
        new_pos = _call_read(path, 0, state)
        assert len(state.recent_actions) == 1
        assert state.recent_actions[0].action_type == 'post'
        # Position must be at end of the complete line, before the partial
        assert new_pos == len(complete.encode('utf-8'))
    finally:
        os.unlink(path)


def test_incremental_reads_pick_up_new_lines():
    """Second read from returned position picks up lines added after first read."""
    state = _make_state("test-incr")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        f.write(json.dumps(_ACTION) + '\n')
        path = f.name
    try:
        pos1 = _call_read(path, 0, state)
        assert len(state.recent_actions) == 1

        with open(path, 'a') as f:
            f.write(json.dumps({**_ACTION, "agent_id": 3, "agent_name": "Charlie"}) + '\n')

        pos2 = _call_read(path, pos1, state)
        assert len(state.recent_actions) == 2
        assert pos2 > pos1
    finally:
        os.unlink(path)


def test_empty_file_returns_zero():
    """Empty file returns position 0 and processes nothing."""
    state = _make_state("test-empty")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        path = f.name
    try:
        new_pos = _call_read(path, 0, state)
        assert new_pos == 0
        assert len(state.recent_actions) == 0
    finally:
        os.unlink(path)
