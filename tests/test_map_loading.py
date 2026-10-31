"""Tests for the canonical JSON map schema."""

import json
from pathlib import Path

from wumpus import WumpusWorld


MAP_PATH = Path(__file__).resolve().parent.parent / "map1.json"


def load_map():
    with open(MAP_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_map1_has_canonical_dimensions():
    """Verify default map integrity and canonical schema dimensions."""
    assert MAP_PATH.exists(), "map1.json must exist in project root"
    data = load_map()

    assert data["width"] == 8
    assert data["height"] == 6
    assert data["start"] == [0, 0]
    assert data["max_steps"] > 0
    assert "energy" not in data


def test_map1_uses_expected_costs_and_grab_setting():
    data = load_map()

    assert data["step_cost"] == -1.0
    assert data["death_cost"] == -100.0
    assert data["grab_reward"] == 100.0
    assert data["end_on_grab"] is False, "Agent must be able to return to start"


def test_map1_defines_all_entities():
    data = load_map()

    for field in ("walls", "pits", "wumpus", "gold"):
        assert field in data


def test_map_bounds():
    """Verify that all entities are placed within grid boundaries."""
    data = load_map()
    width, height = data["width"], data["height"]

    for wall in data["walls"]:
        assert 0 <= wall[0] < width and 0 <= wall[1] < height, f"Wall {wall} out of bounds"

    for pit in data["pits"]:
        assert 0 <= pit[0] < width and 0 <= pit[1] < height, f"Pit {pit} out of bounds"

    wumpus = data["wumpus"]
    assert 0 <= wumpus[0] < width and 0 <= wumpus[1] < height, "Wumpus out of bounds"

    gold = data["gold"]
    assert 0 <= gold[0] < width and 0 <= gold[1] < height, "Gold out of bounds"


def test_map1_loads_into_world():
    world = WumpusWorld.from_json(MAP_PATH)

    assert world.width == 8
    assert world.height == 6
    assert world.start == (0, 0)
    assert world.gold == (7, 5)
    assert world.wumpus == (3, 2)
    assert world.end_on_grab is False
    assert world.energy == world.max_steps
