"""Rule-level tests for hazard inference and explicit pit certainty factors."""

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


def candidates(agent):
    return {
        (
            int(fact["bx"]),
            int(fact["by"]),
            int(fact["px"]),
            int(fact["py"]),
        )
        for fact in facts_named(agent, "candidate")
    }


def hypotheses(agent, x, y):
    return [
        fact
        for fact in facts_named(agent, "pit-hypothesis")
        if int(fact["x"]) == x and int(fact["y"]) == y
    ]


def hypothesis_cfs(agent, x, y):
    return sorted(float(fact["cf"]) for fact in hypotheses(agent, x, y))


def drive(agent, *modules):
    agent.env.eval("(focus " + " ".join(modules) + ")")
    return agent.env.run()


def add_breeze_source(agent, source, target, extra):
    bx, by = source
    px, py = target
    ex, ey = extra
    agent.env.assert_string(f"(breeze-at (x {bx}) (y {by}))")
    agent.env.assert_string(
        f"(nbr (x {bx}) (y {by}) (nx {px}) (ny {py}) (dir up) (rank 1))"
    )
    agent.env.assert_string(
        f"(nbr (x {bx}) (y {by}) (nx {ex}) (ny {ey}) (dir down) (rank 3))"
    )


def breeze_origin_agent():
    agent = make_agent(make_obs(breeze=True))
    agent.run_and_get_action()
    return agent


def test_origin_without_hazards_derives_neighbour_constraints():
    agent = make_agent(make_obs(breeze=False, stench=False))
    agent.run_and_get_action()

    assert cells(agent, "no-breeze-at") == {(0, 0)}
    assert cells(agent, "no-stench-at") == {(0, 0)}

    neighbours = {(0, -1), (1, 0), (0, 1), (-1, 0)}
    assert neighbours <= cells(agent, "no-pit")
    assert neighbours <= cells(agent, "no-wumpus")
    assert {(1, 0), (0, 1)} <= cells(agent, "safe")

    outside = {(0, -1), (-1, 0)}
    assert outside <= cells(agent, "blocked")
    assert outside <= cells(agent, "no-pit")
    assert outside <= cells(agent, "no-wumpus")
    assert cells(agent, "safe").isdisjoint(outside)


def test_unique_remaining_candidate_confirms_pit():
    agent = breeze_origin_agent()

    assert candidates(agent) == {
        (0, 0, 1, 0),
        (0, 0, 0, 1),
    }
    assert cells(agent, "pit") == set()

    agent.env.assert_string("(no-pit (x 1) (y 0))")
    drive(agent, "HYPO")

    assert cells(agent, "pit") == {(0, 1)}
    assert candidates(agent) == {(0, 0, 0, 1)}
    assert hypothesis_cfs(agent, 0, 1) == [pytest.approx(1.0)]
    assert hypotheses(agent, 1, 0) == []


def test_confirmed_pit_remains_a_candidate_for_a_second_breeze():
    agent = breeze_origin_agent()
    agent.env.assert_string("(no-pit (x 1) (y 0))")
    drive(agent, "HYPO")
    assert cells(agent, "pit") == {(0, 1)}

    agent.env.assert_string("(breeze-at (x 0) (y 2))")
    agent.env.assert_string(
        "(nbr (x 0) (y 2) (nx 0) (ny 1) (dir up) (rank 1))"
    )
    agent.env.assert_string(
        "(nbr (x 0) (y 2) (nx 1) (ny 2) (dir right) (rank 2))"
    )
    drive(agent, "HYPO")

    assert (0, 2, 0, 1) in candidates(agent)
    assert (0, 2, 1, 2) in candidates(agent)
    assert (1, 2) not in cells(agent, "pit")
    assert cells(agent, "pit") == {(0, 1)}


def test_stench_limits_wumpus_to_compatible_cells_and_confirms_unique_cell():
    agent = make_agent(make_obs(stench=True))
    agent.run_and_get_action()

    assert cells(agent, "wumpus-possible") == {(1, 0), (0, 1)}
    assert cells(agent, "wumpus") == set()

    agent.env.assert_string("(no-wumpus (x 1) (y 0))")
    drive(agent, "HYPO")

    assert cells(agent, "wumpus-possible") == {(0, 1)}
    assert cells(agent, "wumpus") == {(0, 1)}


def test_second_stench_prunes_to_the_shared_neighbour():
    agent = make_agent(make_obs(stench=True))
    agent.run_and_get_action()
    assert cells(agent, "wumpus-possible") == {(1, 0), (0, 1)}

    agent.env.assert_string("(stench-at (x 2) (y 0))")
    agent.env.assert_string(
        "(nbr (x 2) (y 0) (nx 1) (ny 0) (dir left) (rank 4))"
    )
    drive(agent, "HYPO")

    assert cells(agent, "wumpus-possible") == {(1, 0)}
    assert cells(agent, "wumpus") == {(1, 0)}


def test_no_stench_creates_no_wumpus_possibilities():
    agent = make_agent(make_obs(stench=False))
    agent.run_and_get_action()

    assert cells(agent, "wumpus-possible") == set()
    assert cells(agent, "wumpus") == set()


def test_single_breeze_gives_one_hypothesis_per_candidate():
    agent = make_agent()
    add_breeze_source(agent, (0, 1), (1, 1), (0, 2))
    drive(agent, "HYPO")

    assert hypothesis_cfs(agent, 1, 1) == [pytest.approx(0.4)]
    assert hypothesis_cfs(agent, 0, 2) == [pytest.approx(0.4)]
    assert cells(agent, "pit") == set()
    assert (1, 1) not in cells(agent, "safe")


def test_two_breezes_combine_to_mycin_positive_value():
    agent = make_agent()
    add_breeze_source(agent, (0, 1), (1, 1), (0, 2))
    add_breeze_source(agent, (1, 0), (1, 1), (2, 0))
    drive(agent, "HYPO")

    assert hypothesis_cfs(agent, 1, 1) == [pytest.approx(0.64)]
    assert cells(agent, "pit") == set()
    assert (1, 1) not in cells(agent, "safe")


def test_three_breezes_combine_to_mycin_positive_value():
    agent = make_agent()
    add_breeze_source(agent, (0, 1), (1, 1), (0, 2))
    add_breeze_source(agent, (1, 0), (1, 1), (2, 0))
    add_breeze_source(agent, (1, 2), (1, 1), (2, 2))
    drive(agent, "HYPO")

    assert hypothesis_cfs(agent, 1, 1) == [pytest.approx(0.784)]
    assert cells(agent, "pit") == set()


def test_repeated_cycles_do_not_inflate_certainty_factor():
    agent = make_agent()
    add_breeze_source(agent, (0, 1), (1, 1), (0, 2))
    add_breeze_source(agent, (1, 0), (1, 1), (2, 0))
    drive(agent, "HYPO")
    assert hypothesis_cfs(agent, 1, 1) == [pytest.approx(0.64)]

    drive(agent, "HYPO")
    drive(agent, "HYPO")

    assert hypothesis_cfs(agent, 1, 1) == [pytest.approx(0.64)]
    assert len(hypotheses(agent, 1, 1)) == 1
    evidence = [
        fact
        for fact in facts_named(agent, "evidence-seen")
        if (int(fact["x"]), int(fact["y"])) == (1, 1)
    ]
    assert len(evidence) == 2


def test_confirmed_pit_raises_hypothesis_to_full_certainty():
    agent = breeze_origin_agent()
    agent.env.assert_string("(no-pit (x 1) (y 0))")
    drive(agent, "HYPO")

    assert cells(agent, "pit") == {(0, 1)}
    assert hypothesis_cfs(agent, 0, 1) == [pytest.approx(1.0)]
    assert hypotheses(agent, 1, 0) == []


def test_wumpus_target_drops_pit_candidate_and_hypothesis():
    agent = make_agent()
    add_breeze_source(agent, (0, 1), (1, 1), (0, 2))
    drive(agent, "HYPO")
    assert (0, 1, 1, 1) in candidates(agent)
    assert hypothesis_cfs(agent, 1, 1) == [pytest.approx(0.4)]

    agent.env.assert_string("(wumpus (x 1) (y 1))")
    drive(agent, "HYPO")

    assert (0, 1, 1, 1) not in candidates(agent)
    assert hypotheses(agent, 1, 1) == []


def test_wall_pit_candidate_keeps_evidence_without_becoming_safe():
    agent = make_agent()
    agent.env.assert_string("(blocked (x 1) (y 1))")
    agent.env.assert_string("(breeze-at (x 0) (y 1))")
    agent.env.assert_string(
        "(nbr (x 0) (y 1) (nx 1) (ny 1) (dir right) (rank 2))"
    )
    agent.env.assert_string(
        "(nbr (x 0) (y 1) (nx 0) (ny 2) (dir down) (rank 3))"
    )
    drive(agent, "MAP", "HYPO")

    assert (0, 1, 1, 1) in candidates(agent)
    assert hypothesis_cfs(agent, 1, 1) == [pytest.approx(0.4)]
    assert (1, 1) not in cells(agent, "safe")
    assert cells(agent, "pit") == set()
    assert facts_named(agent, "guessed") == []
