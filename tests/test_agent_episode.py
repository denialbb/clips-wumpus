"""End-to-end episodes for movement, energy budgeting, and return/quit."""

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


def test_pit_blocks_the_gold_and_the_agent_survives():
    world = make_world(width=3, pits={(1, 0)}, gold=(2, 0))

    result = run(world)

    assert result.termination == "quit"
    assert result.gold_collected is False
    assert result.final_position == (0, 0)
    assert result.energy >= 0
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


def test_map1_returns_to_the_exit_without_dying():
    world = WumpusWorld.from_json(MAP_PATH)

    result = run(world)

    assert result.termination == "quit"
    assert result.final_position == (0, 0)
    assert result.energy >= 0
    assert result.protocol_error is None


@pytest.mark.xfail(
    strict=True,
    reason=(
        "map1 has no safe route to the gold: the visited safe region is cut "
        "at (3,4), whose only visited neighbour (2,4) reports a breeze"
    ),
)
def test_map1_collects_the_gold():
    world = WumpusWorld.from_json(MAP_PATH)

    result = run(world)

    assert result.gold_collected is True
    assert result.termination == "quit"
    assert result.final_position == (0, 0)
    assert result.protocol_error is None


def test_map1_is_deterministic():
    first = run(WumpusWorld.from_json(MAP_PATH))
    second = run(WumpusWorld.from_json(MAP_PATH))

    assert first.actions == second.actions
