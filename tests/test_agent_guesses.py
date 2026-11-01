"""Rule-level and episode tests for adjacent pit guesses."""

from pathlib import Path

import pytest

pytest.importorskip("clips")

from wumpus import ClipsAgent, PitGuess, WumpusWorld, run_episode


AGENT_PATH = Path(__file__).resolve().parent.parent / "agent.clp"
MAP_PATH = Path(__file__).resolve().parent.parent / "map1.json"

ORIGIN = (2, 2)

DIRECTIONS = [
    ("up", "pit-north", (2, 1), 1),
    ("right", "pit-east", (3, 2), 2),
    ("down", "pit-south", (2, 3), 3),
    ("left", "pit-west", (1, 2), 4),
]


def make_obs(**overrides):
    obs = {
        "x": ORIGIN[0],
        "y": ORIGIN[1],
        "steps": 0,
        "breeze": False,
        "stench": False,
        "glitter": False,
        "energy": 100,
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


def replace_goal(agent, kind, x, y):
    for fact in facts_named(agent, "goal"):
        fact.retract()
    agent.env.assert_string(f"(goal (kind {kind}) (x {x}) (y {y}))")


def guess_agent(
    direction,
    cf=1.0,
    energy=100,
    goal=("frontier", 5, 5),
    extras=(),
):
    """Build a rule-level workspace with one adjacent pit hypothesis."""
    dir_name, _, target, rank = next(
        entry for entry in DIRECTIONS if entry[0] == direction
    )
    tx, ty = target
    agent = make_agent(make_obs(energy=energy))
    agent.env.assert_string(f"(pos (x {ORIGIN[0]}) (y {ORIGIN[1]}))")
    agent.env.assert_string(f"(visited (x {ORIGIN[0]}) (y {ORIGIN[1]}))")
    agent.env.assert_string(
        f"(home (x {ORIGIN[0]}) (y {ORIGIN[1]}) (d 2))"
    )
    agent.env.assert_string(
        f"(nbr (x {ORIGIN[0]}) (y {ORIGIN[1]}) (nx {tx}) (ny {ty}) "
        f"(dir {dir_name}) (rank {rank}))"
    )
    if cf >= 1.0:
        agent.env.assert_string(f"(pit (x {tx}) (y {ty}))")
    agent.env.assert_string(
        f"(pit-hypothesis (x {tx}) (y {ty}) (cf {cf}) "
        "(source-x -1) (source-y -1))"
    )
    agent.env.assert_string(f"(goal (kind {goal[0]}) (x {goal[1]}) (y {goal[2]}))")
    for extra in extras:
        agent.env.assert_string(extra)
    return agent, (tx, ty)


def fire_act(agent):
    agent.env.eval("(focus ACT)")
    agent.env.run(1)
    return [str(fact["move"]) for fact in facts_named(agent, "action")]


def clear_actions(agent):
    for fact in facts_named(agent, "action"):
        fact.retract()


@pytest.mark.parametrize("direction,action,target,rank", DIRECTIONS)
def test_adjacent_confirmed_pit_guesses_and_scores(
    direction, action, target, rank
):
    agent, guess_target = guess_agent(direction)
    assert guess_target == target

    actions = fire_act(agent)

    assert actions == [action]
    assert cells(agent, "guessed") == {target}
    assert facts_named(agent, "last-move") == []

    world = WumpusWorld(
        width=4,
        height=4,
        start=ORIGIN,
        pits={target},
        max_steps=30,
    )
    world.reset()
    result = world.step(action)

    assert (world.x, world.y) == ORIGIN
    assert result.reward == pytest.approx(25.0)
    assert world.energy == 29


def test_headless_episode_scores_a_confirmed_adjacent_guess():
    world = WumpusWorld(
        width=4,
        height=3,
        start=(0, 0),
        walls={(3, 1)},
        pits={(2, 1)},
        wumpus=None,
        gold=None,
        max_steps=40,
        end_on_grab=False,
    )
    agent = ClipsAgent(str(AGENT_PATH))

    result = run_episode(world, agent)

    assert result.guesses == [PitGuess("pit-north", (2, 1), True)]
    assert result.reward == pytest.approx(25.0)
    assert result.termination == "quit"
    assert result.final_position == (0, 0)
    assert result.protocol_error is None
    assert cells(agent, "guessed") == {(2, 1)}


@pytest.mark.parametrize("cf", [0.75, 0.8])
def test_high_cf_adjacent_candidate_is_guessed(cf):
    agent, target = guess_agent("right", cf=cf)

    assert fire_act(agent) == ["pit-east"]
    assert cells(agent, "guessed") == {target}


@pytest.mark.parametrize("cf", [0.4, 0.64])
def test_low_cf_adjacent_candidate_is_not_guessed(cf):
    agent, _ = guess_agent("right", cf=cf)

    actions = fire_act(agent)

    assert "pit-east" not in actions
    assert facts_named(agent, "guessed") == []


def test_guessed_cell_is_never_guessed_twice_and_the_marker_persists():
    agent, target = guess_agent("right")

    assert fire_act(agent) == ["pit-east"]
    assert cells(agent, "guessed") == {target}
    assert len(facts_named(agent, "action")) == 1

    for _ in range(3):
        clear_actions(agent)
        actions = fire_act(agent)
        assert "pit-east" not in actions
        assert cells(agent, "guessed") == {target}

    agent.env.eval("(clear-plan-facts)")
    assert cells(agent, "guessed") == {target}


def test_no_guess_without_the_extra_return_unit():
    agent, _ = guess_agent("right", energy=8)

    actions = fire_act(agent)

    assert "pit-east" not in actions
    assert facts_named(agent, "guessed") == []


def test_guess_needs_more_than_the_return_reserve():
    agent, _ = guess_agent("right", energy=9)

    assert fire_act(agent) == ["pit-east"]


@pytest.mark.parametrize(
    "goal",
    [("probe", 3, 2), ("exit", 0, 0), ("grab", 2, 2)],
)
def test_no_guess_while_a_goal_has_priority(goal):
    agent, _ = guess_agent("right", goal=goal)

    actions = fire_act(agent)

    assert "pit-east" not in actions
    assert facts_named(agent, "guessed") == []


def test_no_guess_while_holding_gold():
    agent, _ = guess_agent("right", extras=("(has-gold)",))

    actions = fire_act(agent)

    assert "pit-east" not in actions
    assert facts_named(agent, "guessed") == []


@pytest.mark.parametrize(
    "blocking_fact",
    [
        "(blocked (x 3) (y 2))",
        "(wumpus (x 3) (y 2))",
        "(wumpus-possible (x 3) (y 2))",
    ],
)
def test_no_guess_on_a_forbidden_target(blocking_fact):
    agent, _ = guess_agent("right", extras=(blocking_fact,))

    actions = fire_act(agent)

    assert "pit-east" not in actions
    assert facts_named(agent, "guessed") == []


def test_map1_guesses_the_adjacent_pit_and_still_returns_home():
    world = WumpusWorld.from_json(MAP_PATH)
    agent = ClipsAgent(str(AGENT_PATH))

    result = run_episode(world, agent)

    assert result.gold_collected is True
    assert result.termination == "quit"
    assert result.final_position == (0, 0)
    assert result.protocol_error is None
    assert result.reward > 100.0
    assert PitGuess("pit-north", (2, 3), True) in result.guesses
    assert result.guesses
    assert all(guess.correct for guess in result.guesses)
    assert (2, 3) in cells(agent, "guessed")
