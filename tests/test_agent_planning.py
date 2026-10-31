"""Rule-level tests for the DECIDE planning fields, goals, and next hops."""

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


def distances(agent, name):
    return {
        (int(fact["x"]), int(fact["y"])): int(fact["d"])
        for fact in facts_named(agent, name)
    }


def advance(agent, obs):
    """Run one fresh cycle from a supplied percept."""
    agent.clear_action_facts()
    for intent in facts_named(agent, "last-move"):
        intent.retract()
    agent.set_percept(obs)
    return agent.run_and_get_action()


def setup_at_one():
    """Visit (0,0) and (1,0) in an open corridor."""
    agent = make_agent()
    advance(agent, make_obs(steps=0))
    advance(agent, make_obs(x=1, y=0, steps=1, energy=199))
    return agent


def goal_fact(agent):
    goals = facts_named(agent, "goal")
    assert len(goals) == 1
    return (
        str(goals[0]["kind"]),
        int(goals[0]["x"]),
        int(goals[0]["y"]),
    )


def test_home_field_is_exact_over_the_visited_graph():
    agent = setup_at_one()

    homes = distances(agent, "home")
    assert homes[(0, 0)] == 0
    assert homes[(1, 0)] == 1
    assert homes[(0, 1)] == 1


def test_origin_plans_distance_goal_and_next_hop():
    agent = make_agent()
    assert advance(agent, make_obs(steps=0)) == "right"

    assert distances(agent, "dist")[(0, 0)] == 0
    assert distances(agent, "dist")[(1, 0)] == 1
    assert distances(agent, "dist")[(0, 1)] == 1
    assert distances(agent, "nav")[(1, 0)] == 0
    assert distances(agent, "nav")[(0, 0)] == 1
    assert goal_fact(agent) == ("frontier", 1, 0)

    nexts = {
        (str(fact["dir"]), int(fact["rank"]))
        for fact in facts_named(agent, "next")
    }
    assert nexts == {("right", 2)}


def test_frontier_tie_break_uses_x_after_y():
    agent = make_agent()
    advance(agent, make_obs(steps=0))

    # Keep the current plan step so the manual candidates survive, then remove
    # the previous selection and offer two equally distant cells on row 0.
    for name in ("goal", "best-frontier", "next"):
        for fact in facts_named(agent, name):
            fact.retract()
    agent.env.assert_string("(frontier (x 2) (y 0))")
    agent.env.assert_string("(dist (x 2) (y 0) (d 1))")
    agent.env.assert_string("(home (x 2) (y 0) (d 2))")

    agent.env.eval("(focus DECIDE)")
    agent.env.run()

    best = facts_named(agent, "best-frontier")
    assert len(best) == 1
    assert (int(best[0]["x"]), int(best[0]["y"])) == (1, 0)


def test_grab_when_the_return_reserve_stays_affordable():
    agent = setup_at_one()

    assert (
        advance(
            agent,
            make_obs(x=1, y=0, steps=2, energy=50, glitter=True),
        )
        == "grab"
    )
    assert goal_fact(agent) == ("grab", 1, 0)
    assert len(facts_named(agent, "has-gold")) == 1


def test_no_grab_when_the_return_reserve_would_break():
    agent = setup_at_one()

    action = advance(
        agent, make_obs(x=1, y=0, steps=2, energy=7, glitter=True)
    )

    assert action == "left"
    assert goal_fact(agent) == ("exit", 0, 0)
    assert facts_named(agent, "has-gold") == []


def test_low_energy_returns_to_the_exit():
    agent = setup_at_one()

    action = advance(
        agent, make_obs(x=1, y=0, steps=2, energy=5, glitter=True)
    )

    assert action == "left"
    assert goal_fact(agent) == ("exit", 0, 0)
    assert len(facts_named(agent, "low-energy")) == 1


def test_exit_when_no_frontier_is_affordable():
    agent = setup_at_one()

    action = advance(agent, make_obs(x=1, y=0, steps=2, energy=8))

    assert action == "left"
    assert goal_fact(agent) == ("exit", 0, 0)
    assert facts_named(agent, "low-energy") == []


def test_held_gold_changes_the_goal_from_exit_to_quit():
    agent = setup_at_one()
    advance(agent, make_obs(x=1, y=0, steps=2, energy=50, glitter=True))

    assert advance(agent, make_obs(x=1, y=0, steps=3, energy=49)) == "left"
    assert goal_fact(agent) == ("exit", 0, 0)

    assert advance(agent, make_obs(x=0, y=0, steps=4, energy=48)) == "quit"
    assert goal_fact(agent) == ("quit", 0, 0)


def navigation_roots(agent):
    return {cell for cell, d in distances(agent, "nav").items() if d == 0}


def test_grab_clears_the_navigation_field():
    agent = make_agent()
    advance(agent, make_obs(steps=0))
    advance(agent, make_obs(x=1, y=0, steps=1, energy=199))

    assert navigation_roots(agent) == {(2, 0)}

    action = advance(
        agent,
        make_obs(x=2, y=0, steps=2, energy=198, glitter=True),
    )

    assert action == "grab"
    assert facts_named(agent, "nav") == []


def test_each_cycle_seeds_one_navigation_root():
    agent = make_agent()
    advance(agent, make_obs(steps=0))
    advance(agent, make_obs(x=1, y=0, steps=1, energy=199))
    advance(agent, make_obs(x=2, y=0, steps=2, energy=198, glitter=True))

    advance(agent, make_obs(x=1, y=0, steps=3, energy=197))

    assert navigation_roots(agent) == {(0, 0)}
    assert goal_fact(agent) == ("exit", 0, 0)
    assert len(facts_named(agent, "plan")) == 1
    assert len(facts_named(agent, "action")) == 1

    assert advance(agent, make_obs(x=0, y=0, steps=4, energy=196)) == "quit"
    assert goal_fact(agent) == ("quit", 0, 0)
