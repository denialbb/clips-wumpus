"""End-to-end episodes for movement, energy budgeting, risk, and return/quit."""

from pathlib import Path

import pytest

pytest.importorskip("clips")

from wumpus import ClipsAgent, WumpusWorld, run_episode


AGENT_PATH = Path(__file__).resolve().parent.parent / "agent.clp"
MAP_PATH = Path(__file__).resolve().parent.parent / "map1.json"


def make_world(**overrides):
    params = {
        "width": 3,
        "height": 1,
        "start": (0, 0),
        "walls": set(),
        "pits": set(),
        "wumpus": None,
        "gold": None,
        "max_steps": 30,
        "step_cost": -1.0,
        "death_cost": -100.0,
        "grab_reward": 100.0,
        "end_on_grab": False,
    }
    params.update(overrides)
    return WumpusWorld(**params)


def run(world):
    return run_episode(world, ClipsAgent(str(AGENT_PATH)))


def run_with_agent(world):
    agent = ClipsAgent(str(AGENT_PATH))
    return run_episode(world, agent), agent


def cells(agent, name):
    return {
        (int(fact["x"]), int(fact["y"]))
        for fact in agent.env.facts()
        if fact.template.name == name
    }


def probe_count(agent):
    counts = [
        int(fact["count"])
        for fact in agent.env.facts()
        if fact.template.name == "probes-used"
    ]
    assert len(counts) == 1
    return counts[0]


def test_collect_gold_and_return_to_the_exit():
    world = make_world(width=2, gold=(1, 0), end_on_grab=False)

    result = run(world)

    assert result.actions == ["right", "grab", "left", "quit"]
    assert result.termination == "quit"
    assert result.gold_collected is True
    assert result.final_position == (0, 0)
    assert result.energy >= 0
    assert result.protocol_error is None


def test_end_on_grab_terminates_on_the_gold():
    world = make_world(width=2, gold=(1, 0), end_on_grab=True)

    result = run(world)

    assert result.actions == ["right", "grab"]
    assert result.termination == "gold"
    assert result.gold_collected is True
    assert result.energy >= 0
    assert result.protocol_error is None


def test_low_cf_pit_barrier_is_an_accepted_death_risk():
    world = make_world(width=3, pits={(1, 0)}, gold=(2, 0))

    result = run(world)

    assert result.termination == "death"
    assert result.gold_collected is False
    assert result.protocol_error is None


def test_unaffordable_probe_is_refused():
    world = make_world(
        width=2,
        height=2,
        pits={(0, 1)},
        walls={(1, 0)},
        max_steps=7,
    )

    result, agent = run_with_agent(world)

    assert result.termination == "quit"
    assert result.final_position == (0, 0)
    assert cells(agent, "probe-attempted") == set()
    assert probe_count(agent) == 0
    assert result.protocol_error is None


def test_wall_probe_bumps_once_then_stops():
    world = make_world(
        width=2,
        height=2,
        pits={(0, 1)},
        walls={(1, 0)},
    )

    result, agent = run_with_agent(world)

    assert result.actions == ["right", "quit"]
    assert result.termination == "quit"
    assert result.final_position == (0, 0)
    assert cells(agent, "probe-attempted") == {(1, 0)}
    assert (1, 0) in cells(agent, "blocked")
    assert probe_count(agent) == 1
    assert result.protocol_error is None


def test_wall_is_bumped_once_and_never_repeated():
    world = make_world(width=2, walls={(1, 0)})

    result = run(world)

    assert result.termination == "quit"
    assert result.final_position == (0, 0)
    assert result.actions.count("right") == 1
    assert result.protocol_error is None


def test_unaffordable_gold_is_skipped_for_survival():
    world = make_world(width=2, gold=(1, 0), max_steps=8)

    result = run(world)

    assert "grab" not in result.actions
    assert result.gold_collected is False
    assert result.termination == "quit"
    assert result.final_position == (0, 0)
    assert result.energy >= 0
    assert result.protocol_error is None


def test_map1_collects_the_gold():
    world = WumpusWorld.from_json(MAP_PATH)

    result, agent = run_with_agent(world)

    assert result.gold_collected is True
    assert result.termination == "quit"
    assert result.final_position == (0, 0)
    assert result.energy >= 0
    assert result.protocol_error is None
    assert {(3, 4), (4, 3)} <= cells(agent, "probe-attempted")
    assert (5, 4) not in cells(agent, "probe-attempted")
    assert probe_count(agent) == 2
    assert len([f for f in agent.env.facts() if f.template.name == "probe-success"]) == 1


def test_map1_is_deterministic():
    first = run(WumpusWorld.from_json(MAP_PATH))
    second = run(WumpusWorld.from_json(MAP_PATH))

    assert first.actions == second.actions
    assert first.gold_collected is True
