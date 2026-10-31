"""Unit tests for the Wumpus World state machine."""

import subprocess
import sys
from pathlib import Path

import pytest

from wumpus import WumpusWorld


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def make_world(**overrides):
    """Build a small world with explicit, deterministic parameters."""
    params = {
        "width": 4,
        "height": 4,
        "start": (0, 0),
        "walls": set(),
        "pits": set(),
        "wumpus": None,
        "gold": None,
        "max_steps": 10,
        "step_cost": -1.0,
        "death_cost": -100.0,
        "grab_reward": 100.0,
        "end_on_grab": True,
    }
    params.update(overrides)
    return WumpusWorld(**params)


def test_move_returns_accumulated_reward():
    world = make_world(gold=(2, 0), end_on_grab=False)

    world.step("right")
    second_move = world.step("right")
    world.step("grab")
    after_grab = world.step("left")

    assert second_move.reward == 0.0
    assert after_grab.reward == 100.0
    assert after_grab.reward == world.reward
    assert after_grab.done is False


def test_step_cost_is_not_added_to_accumulated_reward():
    world = make_world()

    for _ in range(3):
        world.step("right")

    assert world.reward == 0.0
    assert world.energy == 7


def test_successful_grab_ends_episode_when_configured():
    world = make_world(gold=(0, 0), end_on_grab=True)

    result = world.step("grab")

    assert result.reward == 100.0
    assert result.done is True
    assert world.done is True
    assert world.has_gold is True
    assert world.gold is None


def test_successful_grab_keeps_episode_running_when_configured():
    world = make_world(gold=(1, 0), end_on_grab=False)

    world.step("right")
    result = world.step("grab")
    next_result = world.step("left")

    assert result.reward == 100.0
    assert result.done is False
    assert world.done is False
    assert next_result.reward == 100.0
    assert world.has_gold is True
    assert world.gold is None


def test_failed_grab_returns_accumulated_reward():
    world = make_world()

    result = world.step("grab")

    assert result.reward == world.reward == 0.0
    assert result.done is False
    assert world.has_gold is False


def test_quit_sets_done_without_scoring():
    world = make_world()

    result = world.step("quit")

    assert result.reward == 0.0
    assert result.done is True
    assert world.done is True
    assert world.dead is False


def test_quit_is_allowed_outside_start_by_simulator():
    world = make_world()

    world.step("right")
    result = world.step("quit")

    assert result.done is True
    assert world.x == 1


def test_moving_into_pit_causes_death():
    world = make_world(pits={(1, 0)})

    result = world.step("right")

    assert result.done is True
    assert world.dead is True
    assert world.energy == 0
    assert world.reward == -100.0
    assert result.reward == -100.0


def test_moving_into_wumpus_causes_death():
    world = make_world(wumpus=(0, 1))

    result = world.step("down")

    assert result.done is True
    assert world.dead is True
    assert result.reward == -100.0


def test_energy_exhaustion_ends_episode():
    world = make_world(max_steps=1)

    result = world.step("right")

    assert result.done is True
    assert world.dead is False
    assert world.energy == 0
    assert world.reward == -100.0
    assert result.reward == -100.0


def test_wall_bump_costs_extra_energy_and_does_not_move():
    world = make_world(walls={(1, 0)})

    result = world.step("right")

    assert (world.x, world.y) == (0, 0)
    assert world.energy == 8
    assert result.done is False
    assert result.reward == world.reward == 0.0


def test_out_of_bounds_bump_costs_extra_energy_and_does_not_move():
    world = make_world()

    world.step("up")

    assert (world.x, world.y) == (0, 0)
    assert world.energy == 8


def test_correct_pit_guess_scores_without_moving():
    world = make_world(pits={(1, 0)})

    result = world.step("pit-east")

    assert (world.x, world.y) == (0, 0)
    assert world.energy == 9
    assert world.reward == 25.0
    assert result.reward == 25.0
    assert result.done is False


def test_incorrect_pit_guess_costs_without_moving():
    world = make_world()

    result = world.step("pit-east")

    assert (world.x, world.y) == (0, 0)
    assert world.energy == 9
    assert world.reward == -25.0
    assert result.reward == -25.0


def test_steps_after_done_are_idempotent():
    world = make_world()
    world.step("quit")
    snapshot = (world.x, world.y, world.steps, world.energy, world.reward)

    result = world.step("right")

    assert (world.x, world.y, world.steps, world.energy, world.reward) == snapshot
    assert result.reward == world.reward
    assert result.done is True


def test_steps_after_grab_with_end_on_grab_are_idempotent():
    world = make_world(gold=(0, 0), end_on_grab=True)
    world.step("grab")
    snapshot = (world.steps, world.energy, world.reward)

    result = world.step("left")

    assert (world.steps, world.energy, world.reward) == snapshot
    assert result.done is True


def test_observe_returns_public_percept_mapping():
    world = make_world(pits={(1, 0)})

    observation = world.observe()

    assert observation == {
        "x": 0,
        "y": 0,
        "steps": 0,
        "breeze": True,
        "stench": False,
        "glitter": False,
        "energy": 10,
    }


def test_reset_restores_initial_state():
    world = make_world(gold=(0, 0), end_on_grab=True)
    world.step("grab")

    observation = world.reset()

    assert observation["steps"] == 0
    assert observation["energy"] == 10
    assert observation["glitter"] is True
    assert world.done is False
    assert world.has_gold is False
    assert world.gold == (0, 0)
    assert world.reward == 0.0


def test_unknown_action_consumes_one_energy_without_moving():
    world = make_world()

    result = world.step("dance")

    assert (world.x, world.y) == (0, 0)
    assert world.energy == 9
    assert result.done is False


def test_constructor_rejects_invalid_entity_overlap():
    with pytest.raises(ValueError):
        WumpusWorld(width=2, height=2, pits={(0, 0)})


def test_importing_wumpus_does_not_load_tkinter():
    code = "import sys, wumpus; assert 'tkinter' not in sys.modules"

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
