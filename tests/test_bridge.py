"""Contract tests for the Python/CLIPS bridge and the headless harness."""

from pathlib import Path
import textwrap

import pytest

pytest.importorskip("clips")

from wumpus import ClipsAgent, ProtocolError, WumpusWorld, run_episode


PROGRAM_HEADER = """
(deftemplate percept
  (slot x) (slot y) (slot steps)
  (slot breeze) (slot stench) (slot glitter) (slot energy))

(deftemplate counter
  (slot step))

(deftemplate action
  (slot move))

(deffacts initial
  (counter (step 0)))
"""


def write_program(tmp_path, rules=""):
    path = tmp_path / "agent.clp"
    path.write_text(textwrap.dedent(PROGRAM_HEADER + rules), encoding="utf-8")
    return str(path)


def make_agent(tmp_path, rules=""):
    return ClipsAgent(write_program(tmp_path, rules))


def make_obs(**overrides):
    obs = {
        "x": 0,
        "y": 0,
        "steps": 0,
        "breeze": False,
        "stench": False,
        "glitter": False,
        "energy": 10,
    }
    obs.update(overrides)
    return obs


def facts_named(agent, name):
    return [f for f in agent.env.facts() if f.template.name == name]


def test_set_percept_asserts_one_fact_and_updates_counter(tmp_path):
    agent = make_agent(tmp_path)
    agent.set_percept(make_obs(x=2, y=1, steps=3, breeze=True))

    percepts = facts_named(agent, "percept")
    counters = facts_named(agent, "counter")

    assert len(percepts) == 1
    assert len(counters) == 1
    assert str(percepts[0]["x"]) == "2"
    assert str(percepts[0]["y"]) == "1"
    assert str(percepts[0]["steps"]) == "3"
    assert str(percepts[0]["breeze"]) == "TRUE"
    assert str(counters[0]["step"]) == "3"


def test_set_percept_retracts_old_percept_facts(tmp_path):
    agent = make_agent(tmp_path)
    agent.set_percept(make_obs(x=0, steps=0))
    agent.set_percept(make_obs(x=1, steps=1))

    percepts = facts_named(agent, "percept")

    assert len(percepts) == 1
    assert str(percepts[0]["x"]) == "1"
    assert str(percepts[0]["steps"]) == "1"


def test_reset_asserts_initial_percept_and_one_counter(tmp_path):
    agent = make_agent(tmp_path)
    agent.set_percept(make_obs(x=3, steps=7))

    agent.reset(make_obs())

    percepts = facts_named(agent, "percept")
    counters = facts_named(agent, "counter")

    assert len(percepts) == 1
    assert str(percepts[0]["x"]) == "0"
    assert str(percepts[0]["steps"]) == "0"
    assert len(counters) == 1
    assert str(counters[0]["step"]) == "0"


def test_reset_without_percept_leaves_one_counter(tmp_path):
    agent = make_agent(tmp_path)
    agent.set_percept(make_obs(steps=4))

    agent.reset()

    assert len(facts_named(agent, "percept")) == 0
    assert len(facts_named(agent, "counter")) == 1


def test_run_and_get_action_returns_single_action(tmp_path):
    agent = make_agent(
        tmp_path,
        """
        (defrule act
          (percept (x ?x))
          =>
          (assert (action (move right))))
        """,
    )
    agent.set_percept(make_obs())

    assert agent.run_and_get_action() == "right"


def test_zero_action_facts_raise_protocol_error(tmp_path):
    agent = make_agent(tmp_path)
    agent.set_percept(make_obs())

    with pytest.raises(ProtocolError, match="exactly one action"):
        agent.run_and_get_action()


def test_multiple_action_facts_raise_protocol_error(tmp_path):
    agent = make_agent(
        tmp_path,
        """
        (defrule act
          (percept (x ?x))
          =>
          (assert (action (move right)))
          (assert (action (move left))))
        """,
    )
    agent.set_percept(make_obs())

    with pytest.raises(ProtocolError, match="found 2"):
        agent.run_and_get_action()


def test_clear_action_facts_removes_action_facts(tmp_path):
    agent = make_agent(
        tmp_path,
        """
        (defrule act
          (percept (x ?x))
          =>
          (assert (action (move up))))
        """,
    )
    agent.set_percept(make_obs())
    agent.run_and_get_action()

    agent.clear_action_facts()

    assert facts_named(agent, "action") == []


AGENT_RULES = """
(defrule explore
  (percept (x ?x) (steps ?s) (glitter FALSE))
  (test (< ?s 2))
  =>
  (assert (action (move right))))

(defrule grab-gold
  (percept (glitter TRUE))
  =>
  (assert (action (move grab))))

(defrule return-home
  (percept (x ?x) (steps ?s) (glitter FALSE))
  (test (and (>= ?s 2) (> ?x 0)))
  =>
  (assert (action (move left))))

(defrule quit-home
  (percept (x 0) (steps ?s) (glitter FALSE))
  (test (>= ?s 2))
  =>
  (assert (action (move quit))))
"""


@pytest.mark.parametrize(
    ("end_on_grab", "termination"),
    [(True, "gold"), (False, "quit")],
)
def test_headless_episode_with_real_agent(tmp_path, end_on_grab, termination):
    world = WumpusWorld(
        width=3,
        height=1,
        gold=(2, 0),
        max_steps=10,
        end_on_grab=end_on_grab,
    )
    agent = ClipsAgent(write_program(tmp_path, AGENT_RULES))

    result = run_episode(world, agent)

    assert result.termination == termination
    assert result.gold_collected is True
    assert result.reward == 100.0
    assert result.visited == [(0, 0), (1, 0), (2, 0)]
    assert last_action_is_valid(result)


def last_action_is_valid(result):
    return result.actions[-1] in {"grab", "quit"}


def test_episode_starts_at_project_root_map():
    map_path = Path(__file__).resolve().parent.parent / "map1.json"
    world = WumpusWorld.from_json(map_path)

    assert world.end_on_grab is False
