"""Tests for the headless episode harness using deterministic scripted agents."""

from wumpus import ProtocolError, WumpusWorld, run_episode


class ScriptedAgent:
    """Agent stub that replays a fixed action script."""

    def __init__(self, actions):
        self.script = list(actions)
        self.index = 0
        self.percepts = []

    def reset(self, obs):
        self.index = 0
        self.percepts = [obs]

    def run_and_get_action(self):
        if self.index >= len(self.script):
            raise ProtocolError("exhausted action script")
        action = self.script[self.index]
        self.index += 1
        return action

    def clear_action_facts(self):
        pass

    def set_percept(self, obs):
        self.percepts.append(obs)


def make_world(**overrides):
    params = {
        "width": 3,
        "height": 1,
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


def test_episode_ends_on_grab_tracks_path():
    world = make_world(gold=(2, 0), end_on_grab=True)
    agent = ScriptedAgent(["right", "right", "grab"])

    result = run_episode(world, agent)

    assert result.actions == ["right", "right", "grab"]
    assert result.visited == [(0, 0), (1, 0), (2, 0)]
    assert result.guesses == []
    assert result.steps == 3


def test_episode_ends_on_grab_returns_metrics():
    world = make_world(gold=(2, 0), end_on_grab=True)
    agent = ScriptedAgent(["right", "right", "grab"])

    result = run_episode(world, agent)

    assert result.termination == "gold"
    assert result.gold_collected is True
    assert result.reward == 100.0
    assert result.energy == 7
    assert result.final_position == (2, 0)
    assert result.protocol_error is None


def test_episode_continues_after_grab_and_quits_at_start():
    world = make_world(gold=(2, 0), end_on_grab=False)
    agent = ScriptedAgent(["right", "right", "grab", "left", "left", "quit"])

    result = run_episode(world, agent)

    assert result.termination == "quit"
    assert result.gold_collected is True
    assert result.reward == 100.0
    assert result.steps == 6
    assert result.final_position == (0, 0)
    assert result.visited == [(0, 0), (1, 0), (2, 0)]


def test_episode_terminates_on_death():
    world = make_world(pits={(1, 0)})
    agent = ScriptedAgent(["right"])

    result = run_episode(world, agent)

    assert result.termination == "death"
    assert result.reward == -100.0
    assert result.energy == 0
    assert result.steps == 1
    assert result.final_position == (1, 0)


def test_episode_terminates_on_energy_exhaustion():
    world = make_world(max_steps=1)
    agent = ScriptedAgent(["right"])

    result = run_episode(world, agent)

    assert result.termination == "energy"
    assert result.reward == -100.0
    assert result.energy == 0
    assert result.steps == 1


def test_episode_terminates_on_max_steps():
    world = make_world(width=5)
    agent = ScriptedAgent(["right", "right", "right"])

    result = run_episode(world, agent, max_steps=2)

    assert result.termination == "max_steps"
    assert result.actions == ["right", "right"]
    assert result.steps == 2
    assert result.final_position == (2, 0)


def test_episode_reports_protocol_error_when_agent_has_no_action():
    world = make_world()
    agent = ScriptedAgent([])

    result = run_episode(world, agent)

    assert result.termination == "protocol_error"
    assert result.protocol_error == "exhausted action script"
    assert result.steps == 0


def test_episode_detects_invalid_quit_outside_start():
    world = make_world()
    agent = ScriptedAgent(["right", "quit"])

    result = run_episode(world, agent)

    assert result.termination == "protocol_error"
    assert "quit" in result.protocol_error
    assert result.final_position == (1, 0)
    assert result.steps == 2


def test_episode_scores_correct_guess():
    world = make_world(pits={(1, 0)})
    agent = ScriptedAgent(["pit-east", "quit"])

    result = run_episode(world, agent)

    assert result.termination == "quit"
    assert result.reward == 25.0
    assert len(result.guesses) == 1
    guess = result.guesses[0]
    assert guess.action == "pit-east"
    assert guess.target == (1, 0)
    assert guess.correct is True


def test_episode_scores_incorrect_guess():
    world = make_world()
    agent = ScriptedAgent(["pit-east", "quit"])

    result = run_episode(world, agent)

    assert result.termination == "quit"
    assert result.reward == -25.0
    assert len(result.guesses) == 1
    assert result.guesses[0].target == (1, 0)
    assert result.guesses[0].correct is False


def test_initial_percept_is_asserted_before_first_action():
    world = make_world(gold=(2, 0), end_on_grab=True)
    agent = ScriptedAgent(["right", "right", "grab"])

    result = run_episode(world, agent)

    initial = agent.percepts[0]
    assert initial["x"] == 0
    assert initial["steps"] == 0
    assert initial["energy"] == 10
    assert len(agent.percepts) == result.steps + 1


def test_episode_requires_one_action_per_step():
    world = make_world(width=5)
    agent = ScriptedAgent(["right"])

    result = run_episode(world, agent, max_steps=4)

    assert result.termination == "protocol_error"
    assert result.steps == 1


def test_quit_at_start_terminates_as_quit():
    world = make_world()
    agent = ScriptedAgent(["quit"])

    result = run_episode(world, agent)

    assert result.termination == "quit"
    assert result.reward == 0.0
    assert result.steps == 1
