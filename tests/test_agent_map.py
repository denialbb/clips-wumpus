"""Rule-level tests for agent.clp perception, map closure, and bump detection."""

from pathlib import Path

import pytest

pytest.importorskip("clips")

from wumpus import ClipsAgent


AGENT_PATH = Path(__file__).resolve().parent.parent / "agent.clp"


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


def make_agent(obs=None):
    agent = ClipsAgent(str(AGENT_PATH))
    agent.reset(obs or make_obs())
    return agent


def facts_named(agent, name):
    return [fact for fact in agent.env.facts() if fact.template.name == name]


def cells(agent, name):
    return {(int(fact["x"]), int(fact["y"])) for fact in facts_named(agent, name)}


def run_cycle(agent, obs):
    agent.clear_action_facts()
    agent.set_percept(obs)
    return agent.run_and_get_action()


def record_move(agent, move, x, y):
    agent.env.assert_string(
        f"(last-move (move {move}) (from-x {x}) (from-y {y}))"
    )


def test_origin_seeds_position_and_neighbour_graph():
    agent = make_agent()
    agent.run_and_get_action()

    assert len(facts_named(agent, "pos")) == 1
    assert cells(agent, "visited") == {(0, 0)}
    assert cells(agent, "safe") == {(0, 0), (1, 0), (0, 1)}
    assert (0, 0) in cells(agent, "no-pit")
    assert (0, 0) in cells(agent, "no-wumpus")

    links = {
        (str(fact["dir"]), int(fact["nx"]), int(fact["ny"]), int(fact["rank"]))
        for fact in facts_named(agent, "nbr")
    }
    assert links == {
        ("up", 0, -1, 1),
        ("right", 1, 0, 2),
        ("down", 0, 1, 3),
        ("left", -1, 0, 4),
    }


def test_negative_neighbours_are_outside_and_hazard_free():
    agent = make_agent()
    agent.run_and_get_action()

    outside = {(0, -1), (-1, 0)}
    assert cells(agent, "blocked") == outside
    assert outside <= cells(agent, "no-wumpus")
    assert outside <= cells(agent, "no-pit")
    assert cells(agent, "safe").isdisjoint(outside)


def test_frontier_appears_for_safe_unvisited_cell_and_disappears_when_blocked():
    agent = make_agent()
    agent.run_and_get_action()
    assert cells(agent, "frontier") == set()

    agent.clear_action_facts()
    agent.env.assert_string("(safe (x 1) (y 0))")
    agent.env.run()
    assert cells(agent, "frontier") == {(1, 0), (0, 1)}

    agent.clear_action_facts()
    agent.env.assert_string("(blocked (x 1) (y 0))")
    agent.env.run()
    assert (1, 0) not in cells(agent, "safe")
    assert cells(agent, "frontier") == {(0, 1)}


def test_frontier_disappears_when_cell_becomes_visited():
    agent = make_agent()
    agent.run_and_get_action()

    agent.clear_action_facts()
    agent.env.assert_string("(safe (x 1) (y 0))")
    agent.env.run()
    assert cells(agent, "frontier") == {(1, 0), (0, 1)}

    agent.clear_action_facts()
    agent.env.assert_string("(visited (x 1) (y 0))")
    agent.env.run()
    assert cells(agent, "frontier") == {(0, 1)}


def test_act_records_movement_intent():
    agent = make_agent()
    agent.run_and_get_action()

    agent.clear_action_facts()
    agent.env.assert_string("(action (move right))")
    agent.env.eval("(focus ACT)")
    agent.env.run()

    intents = facts_named(agent, "last-move")
    assert len(intents) == 1
    assert str(intents[0]["move"]) == "right"
    assert (int(intents[0]["from-x"]), int(intents[0]["from-y"])) == (0, 0)


def test_successful_move_updates_position_and_consumes_intent():
    agent = make_agent()
    agent.run_and_get_action()

    agent.clear_action_facts()
    record_move(agent, "right", 0, 0)
    agent.set_percept(make_obs(x=1, y=0, steps=1, energy=199))
    agent.run_and_get_action()

    positions = facts_named(agent, "pos")
    assert len(positions) == 1
    assert (int(positions[0]["x"]), int(positions[0]["y"])) == (1, 0)
    assert cells(agent, "visited") == {(0, 0), (1, 0)}
    assert facts_named(agent, "last-move") == []
    assert (1, 0) not in cells(agent, "blocked")


def test_bump_blocks_target_without_marking_it_pit_free():
    agent = make_agent(make_obs(breeze=True))
    agent.run_and_get_action()

    agent.clear_action_facts()
    record_move(agent, "right", 0, 0)
    agent.set_percept(make_obs(steps=1, energy=198, breeze=True))
    agent.run_and_get_action()

    assert (1, 0) in cells(agent, "blocked")
    assert (1, 0) in cells(agent, "no-wumpus")
    assert (1, 0) not in cells(agent, "no-pit")
    assert facts_named(agent, "last-move") == []


def test_blocked_cell_alone_does_not_imply_pit_free():
    agent = make_agent()
    agent.env.assert_string("(blocked (x 1) (y 1))")
    agent.env.eval("(focus MAP)")
    agent.env.run()

    assert (1, 1) in cells(agent, "blocked")
    assert (1, 1) in cells(agent, "no-wumpus")
    assert (1, 1) not in cells(agent, "no-pit")
    assert (1, 1) not in cells(agent, "safe")


def test_repeated_cycles_do_not_duplicate_map_facts():
    agent = make_agent()
    for step in range(3):
        run_cycle(agent, make_obs(steps=step, energy=200 - step))

    assert len(facts_named(agent, "nbr")) == 12
    assert len(facts_named(agent, "visited")) == 1
    assert len(facts_named(agent, "safe")) == 3
    assert cells(agent, "frontier") == {(1, 0), (0, 1)}
    assert cells(agent, "blocked") == {(0, -1), (1, -1), (-1, 0), (-1, 1)}
    assert len(facts_named(agent, "no-breeze-at")) == 1
    assert len(facts_named(agent, "no-stench-at")) == 1
