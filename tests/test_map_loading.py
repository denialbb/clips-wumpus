import json
from pathlib import Path
import pytest


def test_map1_structure():
    """Verify default map integrity and required JSON schema fields."""
    map_path = Path(__file__).resolve().parent.parent / "map1.json"
    assert map_path.exists(), "map1.json must exist in project root"

    with open(map_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "size" in data, "Map must specify grid size"
    assert len(data["size"]) == 2, "Size must be [width, height]"
    assert "start" in data, "Map must define start position"
    assert data["start"] == [0, 0], "Start position should default to [0, 0]"
    assert "pits" in data, "Map must define pit locations"
    assert "wumpus" in data, "Map must define wumpus location"
    assert "gold" in data, "Map must define gold location"
    assert "energy" in data, "Map must define initial energy limit"
    assert data["energy"] > 0, "Initial energy must be strictly positive"


def test_map_bounds():
    """Verify that all entities are placed within grid boundaries."""
    map_path = Path(__file__).resolve().parent.parent / "map1.json"
    with open(map_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    w, h = data["size"]
    for pit in data["pits"]:
        assert 0 <= pit[0] < w and 0 <= pit[1] < h, f"Pit {pit} out of bounds"

    wumpus = data["wumpus"]
    assert 0 <= wumpus[0] < w and 0 <= wumpus[1] < h, "Wumpus out of bounds"

    gold = data["gold"]
    assert 0 <= gold[0] < w and 0 <= gold[1] < h, "Gold out of bounds"
