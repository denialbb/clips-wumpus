"""Tests for the agent.clp module skeleton and control cycle."""

from pathlib import Path

import pytest

pytest.importorskip("clips")

from wumpus import ClipsAgent


AGENT_PATH = Path(__file__).resolve().parent.parent / "agent.clp"
VALID_ACTIONS = {
    "up",
    "down",
    "left",
    "right",
    "grab",
    "quit",
    "pit-north",
    "pit-south",
    "pit-west",
    "pit-east",
}


def make_obs(**overrides):
    obs = {
        "x": 0,
        "y": 0,
        "steps": 0,
        "breeze": False,
        "stench": False,
        "glitter": False,
        "energy": 200,
    }
    obs.update(overrides)
    return obs


def make_agent(obs):
    agent = ClipsAgent(str(AGENT_PATH))
    agent.reset(obs)
    return agent


def facts_named(agent, name):
    return [fact for fact in agent.env.facts() if fact.template.name == name]


def test_reset_leaves_one_percept_and_one_counter():
    agent = make_agent(make_obs())

    assert len(facts_named(agent, "percept")) == 1
    assert len(facts_named(agent, "counter")) == 1

    action = agent.run_and_get_action()

    assert action in VALID_ACTIONS
    assert len(facts_named(agent, "action")) == 1


def test_new_percept_replaces_old_percept_and_advances_counter():
    agent = make_agent(make_obs())
    agent.run_and_get_action()

    agent.clear_action_facts()
    agent.set_percept(make_obs(x=1, y=0, steps=1, energy=199))

    percepts = facts_named(agent, "percept")
    counters = facts_named(agent, "counter")

    assert len(percepts) == 1
    assert str(percepts[0]["steps"]) == "1"
    assert len(counters) == 1
    assert str(counters[0]["step"]) == "1"


def test_scaffold_fallback_quits_only_at_origin():
    origin_agent = make_agent(make_obs(x=0, y=0))
    assert origin_agent.run_and_get_action() == "quit"

    away_agent = make_agent(make_obs(x=1, y=0))
    assert away_agent.run_and_get_action() == "grab"
