"""Tests for the seeded map suite and the agent benchmark."""

import json
from pathlib import Path

import pytest

from tools.benchmark import (
    SeededClipsAgent,
    aggregate_records,
    build_payload,
    episode_metrics,
    error_record,
    format_table,
    run_benchmark,
    write_json,
)
from wumpus import EpisodeResult, PitGuess, WumpusWorld, run_episode


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAP_DIR = PROJECT_ROOT / "maps"
MAP_FILES = sorted(MAP_DIR.glob("map*.json"))
AGENT_PATH = PROJECT_ROOT / "agent.clp"
RANDOM_PATH = PROJECT_ROOT / "agent_random.clp"


def make_result(**overrides):
    values = {
        "actions": ["right", "grab", "left", "quit"],
        "visited": [(0, 0), (1, 0)],
        "guesses": [PitGuess("pit-east", (1, 0), True)],
        "termination": "quit",
        "energy": 7,
        "reward": 125.0,
        "steps": 4,
        "gold_collected": True,
        "final_position": (0, 0),
    }
    values.update(overrides)
    return EpisodeResult(**values)


def make_world(**overrides):
    values = {
        "width": 3,
        "height": 2,
        "start": (0, 0),
        "walls": set(),
        "pits": set(),
        "wumpus": None,
        "gold": (2, 1),
        "max_steps": 10,
        "step_cost": -1.0,
        "death_cost": -100.0,
        "grab_reward": 100.0,
        "end_on_grab": False,
    }
    values.update(overrides)
    return WumpusWorld(**values)


def write_tiny_map(tmp_path):
    data = {
        "width": 2,
        "height": 1,
        "start": [0, 0],
        "walls": [],
        "pits": [],
        "wumpus": None,
        "gold": [1, 0],
        "max_steps": 12,
        "step_cost": -1.0,
        "death_cost": -100.0,
        "grab_reward": 100.0,
        "end_on_grab": False,
    }
    path = tmp_path / "tiny.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def make_records():
    finished = {"agent": "expert", **episode_metrics(make_result(), (0, 0))}
    exhausted = {
        "agent": "expert",
        **episode_metrics(
            make_result(
                guesses=[],
                termination="energy",
                energy=0,
                reward=-100.0,
                gold_collected=False,
                final_position=(1, 0),
            ),
            (0, 0),
        ),
    }
    random = {
        "agent": "random",
        **episode_metrics(make_result(guesses=[]), (0, 0)),
    }
    return [finished, exhausted, random]


@pytest.mark.parametrize("map_path", MAP_FILES, ids=lambda path: path.name)
def test_map_suite_loads_with_a_safe_start(map_path):
    world = WumpusWorld.from_json(map_path)

    assert world.start == (0, 0)
    assert world.start not in world.walls
    assert world.start not in world.pits
    assert world.wumpus != world.start
    assert 0 <= world.start[0] < world.width
    assert 0 <= world.start[1] < world.height


def test_map_suite_has_ten_fixed_layouts():
    assert len(MAP_FILES) == 10


def test_episode_metrics_capture_the_outcome_flags():
    metrics = episode_metrics(make_result(), (0, 0))

    assert metrics["termination"] == "quit"
    assert metrics["gold_collected"] is True
    assert metrics["returned"] is True
    assert metrics["survived"] is True
    assert metrics["reward"] == 125.0


def test_episode_metrics_capture_episode_counters():
    metrics = episode_metrics(make_result(), (0, 0))

    assert metrics["energy"] == 7
    assert metrics["steps"] == 4
    assert metrics["visited"] == 2
    assert metrics["guesses"] == 1
    assert metrics["correct_guesses"] == 1
    assert metrics["guess_accuracy"] == 1.0


def test_episode_metrics_handle_zero_guesses():
    result = make_result(
        guesses=[],
        termination="energy",
        energy=0,
        reward=-100.0,
        gold_collected=False,
        final_position=(1, 0),
    )

    metrics = episode_metrics(result, (0, 0))

    assert metrics["guess_accuracy"] is None
    assert metrics["survived"] is False
    assert metrics["returned"] is False


def test_aggregate_computes_rates_and_means():
    expert = aggregate_records(make_records())["expert"]

    assert expert["maps"] == 2
    assert expert["survival_rate"] == 0.5
    assert expert["gold_rate"] == 0.5
    assert expert["return_rate"] == 0.5
    assert expert["avg_energy"] == 3.5
    assert expert["avg_steps"] == 4.0
    assert expert["total_reward"] == 25.0


def test_aggregate_computes_guess_accuracy():
    aggregates = aggregate_records(make_records())
    expert = aggregates["expert"]

    assert expert["guesses"] == 1
    assert expert["correct_guesses"] == 1
    assert expert["guess_accuracy"] == 1.0
    assert aggregates["random"]["guess_accuracy"] is None
    assert "-" in format_table(aggregates)


def test_aggregate_ignores_missing_numeric_values():
    records = [
        {"agent": "expert", **episode_metrics(make_result(), (0, 0))},
        error_record(
            "missing.json", "expert", "agent.clp", "load_error", "missing"
        ),
    ]

    expert = aggregate_records(records)["expert"]

    assert expert["maps"] == 2
    assert expert["avg_energy"] == 7.0
    assert expert["avg_steps"] == 4.0


def test_seeded_baseline_is_deterministic_across_fresh_runs():
    first = run_episode(make_world(), SeededClipsAgent(RANDOM_PATH, 7))
    second = run_episode(make_world(), SeededClipsAgent(RANDOM_PATH, 7))

    assert first.actions == second.actions
    assert first.termination == second.termination


def test_missing_map_becomes_a_load_error_record(tmp_path):
    records = run_benchmark(
        [tmp_path / "missing.json"],
        str(AGENT_PATH),
        str(RANDOM_PATH),
        7,
    )

    assert len(records) == 2
    assert {record["termination"] for record in records} == {"load_error"}
    assert all("error" in record for record in records)


def test_tiny_benchmark_runs_both_agents(tmp_path):
    map_path = write_tiny_map(tmp_path)

    records = run_benchmark([map_path], str(AGENT_PATH), str(RANDOM_PATH), 7)

    assert len(records) == 2
    assert {record["agent"] for record in records} == {"expert", "random"}
    assert all("error" not in record for record in records)
    expert = next(
        record for record in records if record["agent"] == "expert"
    )
    assert expert["gold_collected"] is True
    assert expert["termination"] == "quit"


def test_json_payload_contains_aggregate_and_episodes(tmp_path):
    record = {
        "map": "tiny.json",
        "agent": "expert",
        "program": "agent.clp",
        **episode_metrics(make_result(), (0, 0)),
    }
    records = [record]
    aggregates = aggregate_records(records)
    payload = build_payload([tmp_path / "tiny.json"], aggregates, records, 7)
    output = tmp_path / "report.json"

    write_json(output, payload)
    loaded = json.loads(output.read_text(encoding="utf-8"))

    assert loaded["seed"] == 7
    assert loaded["aggregate"]["expert"]["gold_rate"] == 1.0
    assert len(loaded["episodes"]) == 1
    assert loaded["episodes"][0]["agent"] == "expert"
