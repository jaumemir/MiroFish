# backend/tests/test_simulation_config_assign_agents.py
"""
Tests for _assign_initial_post_agents in SimulationConfigGenerator.

Regression: all initial posts were assigned to the same agent because the LLM
returns poster_type as entity names (e.g. "DGIA") while the index was built on
entity_type labels (long descriptions). The fix adds name-based matching and a
round-robin fallback.
"""
import pytest
from backend.app.services.simulation_config_generator import (
    AgentActivityConfig,
    EventConfig,
    SimulationConfigGenerator,
)


def _make_agent(agent_id, entity_name, entity_type="Organization", influence=1.0):
    return AgentActivityConfig(
        agent_id=agent_id,
        entity_uuid=f"uuid-{agent_id}",
        entity_name=entity_name,
        entity_type=entity_type,
        influence_weight=influence,
    )


def _make_generator():
    gen = SimulationConfigGenerator.__new__(SimulationConfigGenerator)
    return gen


def test_name_match_distributes_posts():
    """LLM returns poster_type as entity name — each agent gets its own posts."""
    gen = _make_generator()
    agents = [
        _make_agent(0, "ciutadania"),
        _make_agent(1, "CTTI"),
        _make_agent(2, "DGIA"),
        _make_agent(3, "RGPD"),
    ]
    event_config = EventConfig(initial_posts=[
        {"content": "Post about citizens", "poster_type": "ciutadania"},
        {"content": "Post about CTTI", "poster_type": "CTTI"},
        {"content": "Post about DGIA", "poster_type": "DGIA"},
        {"content": "Post about RGPD", "poster_type": "RGPD"},
    ])
    result = gen._assign_initial_post_agents(event_config, agents)
    assigned = {p["poster_agent_id"] for p in result.initial_posts}
    assert assigned == {0, 1, 2, 3}, "Each entity should get its own post"


def test_name_match_case_insensitive():
    """poster_type matching by name is case-insensitive."""
    gen = _make_generator()
    agents = [_make_agent(0, "DGIA"), _make_agent(1, "ciutadania")]
    event_config = EventConfig(initial_posts=[
        {"content": "Post", "poster_type": "dgia"},
    ])
    result = gen._assign_initial_post_agents(event_config, agents)
    assert result.initial_posts[0]["poster_agent_id"] == 0


def test_type_label_match():
    """poster_type matching by entity_type label still works."""
    gen = _make_generator()
    agents = [
        _make_agent(0, "Org A", entity_type="organization"),
        _make_agent(1, "Org B", entity_type="organization"),
    ]
    event_config = EventConfig(initial_posts=[
        {"content": "Post 1", "poster_type": "organization"},
        {"content": "Post 2", "poster_type": "organization"},
    ])
    result = gen._assign_initial_post_agents(event_config, agents)
    ids = [p["poster_agent_id"] for p in result.initial_posts]
    assert set(ids) == {0, 1}, "Round-robin across same type should distribute"


def test_fallback_round_robin_no_repeated_agent():
    """When no match, round-robin fallback should not always return the same agent."""
    gen = _make_generator()
    agents = [
        _make_agent(0, "Agent A", influence=2.0),
        _make_agent(1, "Agent B", influence=1.0),
        _make_agent(2, "Agent C", influence=0.5),
    ]
    event_config = EventConfig(initial_posts=[
        {"content": f"Post {i}", "poster_type": "unknowntype"} for i in range(6)
    ])
    result = gen._assign_initial_post_agents(event_config, agents)
    ids = [p["poster_agent_id"] for p in result.initial_posts]
    # All 3 agents should appear (round-robin over 6 posts with 3 agents)
    assert set(ids) == {0, 1, 2}, f"Round-robin fallback should distribute, got {ids}"


def test_empty_initial_posts():
    """No crash on empty initial_posts."""
    gen = _make_generator()
    agents = [_make_agent(0, "Agent")]
    event_config = EventConfig(initial_posts=[])
    result = gen._assign_initial_post_agents(event_config, agents)
    assert result.initial_posts == []
