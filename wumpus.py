from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import clips  # pip install clipspy


MOVE_DELTAS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}

PIT_GUESS_DELTAS = {
    "pit-north": (0, -1),
    "pit-south": (0, 1),
    "pit-west": (-1, 0),
    "pit-east": (1, 0),
}

TERMINATION_GOLD = "gold"
TERMINATION_QUIT = "quit"
TERMINATION_DEATH = "death"
TERMINATION_ENERGY = "energy"
TERMINATION_MAX_STEPS = "max_steps"
TERMINATION_PROTOCOL_ERROR = "protocol_error"


@dataclass(frozen=True)
class StepResult:
    obs: Dict[str, object]
    reward: float
    done: bool


@dataclass(frozen=True)
class PitGuess:
    action: str
    target: Tuple[int, int]
    correct: bool


@dataclass(frozen=True)
class EpisodeResult:
    actions: List[str]
    visited: List[Tuple[int, int]]
    guesses: List[PitGuess]
    termination: str
    energy: int
    reward: float
    steps: int
    gold_collected: bool
    final_position: Tuple[int, int]
    protocol_error: Optional[str] = None

    @property
    def visited_cells(self) -> List[Tuple[int, int]]:
        return self.visited

    @property
    def final_energy(self) -> int:
        return self.energy

    @property
    def termination_cause(self) -> str:
        return self.termination


class WumpusWorld:
    """Deterministic Wumpus World state machine.

    The simulator is intentionally permissive about ``quit``: it accepts the
    action from any cell. The harness is responsible for enforcing the
    return-to-start rule and for reporting an invalid quit as a protocol
    error.
    """

    def __init__(
        self,
        width: int,
        height: int,
        start: Tuple[int, int] = (0, 0),
        walls: Optional[Set[Tuple[int, int]]] = None,
        pits: Optional[Set[Tuple[int, int]]] = None,
        wumpus: Optional[Tuple[int, int]] = None,
        gold: Optional[Tuple[int, int]] = None,
        max_steps: int = 200,
        step_cost: float = -1.0,
        death_cost: float = -100.0,
        grab_reward: float = 100.0,
        end_on_grab: bool = True,
    ):
        self.width = width
        self.height = height
        self.start = tuple(start)
        self.walls = walls or set()
        self.pits = pits or set()
        self.wumpus = wumpus
        self.gold = gold
        self.original_gold = gold

        self.max_steps = max_steps
        self.energy = max_steps
        self.reward = 0.0
        self.step_cost = step_cost
        self.death_cost = death_cost
        self.grab_reward = grab_reward
        self.end_on_grab = end_on_grab
        self.done = False

        if self.start in self.walls:
            raise ValueError("Start cannot be inside a wall.")
        if self.start in self.pits:
            raise ValueError("Start cannot be a pit.")
        if self.wumpus == self.start:
            raise ValueError("Start cannot contain wumpus.")

        for obj in self.pits | self.walls:
            if obj == self.wumpus or obj == self.gold:
                raise ValueError("Cannot overlap walls/pits with wumpus/gold.")

        self.x, self.y = self.start
        self.steps = 0
        self.dead = False
        self.has_gold = False

    @classmethod
    def from_json(cls, path: str | Path) -> "WumpusWorld":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        def to_tuple(value):
            return tuple(value) if value is not None else None

        def to_tuple_set(values):
            return {tuple(value) for value in values} if values else set()

        return cls(
            width=data["width"],
            height=data["height"],
            start=to_tuple(data.get("start", [0, 0])),
            walls=to_tuple_set(data.get("walls", [])),
            pits=to_tuple_set(data.get("pits", [])),
            wumpus=to_tuple(data.get("wumpus")),
            gold=to_tuple(data.get("gold")),
            max_steps=data.get("max_steps", 200),
            step_cost=data.get("step_cost", -1.0),
            death_cost=data.get("death_cost", -100.0),
            grab_reward=data.get("grab_reward", 100.0),
            end_on_grab=data.get("end_on_grab", True),
        )

    def reset(self) -> Dict[str, object]:
        self.x, self.y = self.start
        self.steps = 0
        self.energy = self.max_steps
        self.reward = 0.0
        self.dead = False
        self.has_gold = False
        self.done = False
        self.gold = self.original_gold
        return self.observe()

    def _in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def _is_blocked(self, x: int, y: int) -> bool:
        return (x, y) in self.walls

    def _neighbors_4(self, x: int, y: int) -> Set[Tuple[int, int]]:
        candidates = {(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)}
        return {(nx, ny) for (nx, ny) in candidates if self._in_bounds(nx, ny)}

    def _percepts(self, x: int, y: int) -> Dict[str, bool]:
        neighbors = self._neighbors_4(x, y)
        breeze = any(cell in self.pits for cell in neighbors)
        stench = self.wumpus in neighbors if self.wumpus else False
        glitter = self.gold == (x, y)
        return {"breeze": breeze, "stench": stench, "glitter": glitter}

    def observe(self) -> Dict[str, object]:
        """Return the current percept without changing the world."""
        percepts = self._percepts(self.x, self.y)
        return {
            "x": self.x,
            "y": self.y,
            "steps": self.steps,
            "breeze": percepts["breeze"],
            "stench": percepts["stench"],
            "glitter": percepts["glitter"],
            "energy": self.energy,
        }

    def _obs(self) -> Dict[str, object]:
        return self.observe()

    def _is_death_cell(self, x: int, y: int) -> bool:
        return (x, y) in self.pits or self.wumpus == (x, y)

    def step(self, action: str) -> StepResult:
        """Apply one action; repeated calls after ``done`` are no-ops."""
        if self.done:
            return StepResult(self.observe(), self.reward, True)

        self.steps += 1
        self.energy -= 1

        if action == "grab":
            return self._handle_grab()

        self._apply_move(action)
        if self._is_death_cell(self.x, self.y):
            return self._handle_death()
        if action == "quit":
            return self._handle_quit()
        if action in PIT_GUESS_DELTAS:
            self._score_pit_guess(action)

        self._finish_turn()
        return StepResult(self.observe(), self.reward, self.done)

    def _apply_move(self, action: str) -> None:
        delta = MOVE_DELTAS.get(action)
        if delta is None:
            return

        next_x = self.x + delta[0]
        next_y = self.y + delta[1]
        if self._in_bounds(next_x, next_y) and not self._is_blocked(next_x, next_y):
            self.x, self.y = next_x, next_y
        else:
            # Bumping a wall or the boundary costs one extra energy unit.
            self.energy -= 1

    def _handle_grab(self) -> StepResult:
        if self.gold == (self.x, self.y) and not self.has_gold:
            self.has_gold = True
            self.gold = None
            self.reward += self.grab_reward
            self.done = self.end_on_grab
        return StepResult(self.observe(), self.reward, self.done)

    def _handle_death(self) -> StepResult:
        self.dead = True
        self.energy = 0
        self.done = True
        self.reward += self.death_cost
        return StepResult(self.observe(), self.reward, True)

    def _handle_quit(self) -> StepResult:
        self.done = True
        return StepResult(self.observe(), self.reward, True)

    def _score_pit_guess(self, action: str) -> None:
        delta = PIT_GUESS_DELTAS[action]
        target = (self.x + delta[0], self.y + delta[1])
        if target in self.pits:
            self.reward += 25.0
        else:
            self.reward -= 25.0

    def _finish_turn(self) -> None:
        self.done = self.energy <= 0
        if self.dead or self.done:
            self.reward += self.death_cost


class ProtocolError(RuntimeError):
    """Raised when the agent violates the one-action-per-cycle protocol."""


def clips_bool(value: bool) -> str:
    return "TRUE" if value else "FALSE"


class ClipsAgent:
    """Thin clipspy bridge implementing the perception/action protocol."""

    def __init__(self, program: str):
        self.env = clips.Environment()
        self.env.load(program)
        self.env.reset()

    def reset(self, obs: Optional[Dict[str, object]] = None) -> None:
        """Reset working memory, leaving one counter and the initial percept."""
        self.env.reset()
        self._ensure_single_counter(0)
        if obs is not None:
            self.set_percept(obs)

    def _facts(self, template_name: str) -> List[clips.Fact]:
        return [f for f in self.env.facts() if f.template.name == template_name]

    def _retract_template(self, template_name: str) -> None:
        for fact in self._facts(template_name):
            fact.retract()

    def _ensure_single_counter(self, step: Optional[int] = None) -> None:
        counters = self._facts("counter")
        if not counters:
            self.env.assert_string("(counter (step 0))")
            return
        for extra in counters[1:]:
            extra.retract()
        if step is not None:
            self.env.eval(f"(modify {counters[0].index} (step {step}))")

    def set_percept(self, obs: Dict[str, object]) -> None:
        """Replace the working-memory percept and synchronize the counter."""
        self._retract_template("percept")
        self.env.assert_string(self._percept_string(obs))
        self.update_time_counter(obs)

    def _percept_string(self, obs: Dict[str, object]) -> str:
        return (
            f"(percept (x {obs['x']}) (y {obs['y']}) "
            f"(steps {obs['steps']}) "
            f"(breeze {clips_bool(obs['breeze'])}) "
            f"(stench {clips_bool(obs['stench'])}) "
            f"(glitter {clips_bool(obs['glitter'])}) "
            f"(energy {obs['energy']}))"
        )

    def update_time_counter(self, obs: Dict[str, object]) -> None:
        for fact in self._facts("counter"):
            self.env.eval(f"(modify {fact.index} (step {obs['steps']}))")

    def clear_action_facts(self) -> None:
        self._retract_template("action")

    def agenda_snapshot(self) -> List[str]:
        return [str(activation) for activation in self.env.activations()]

    def run_and_get_action(self) -> str:
        """Run CLIPS and return the single action asserted in this cycle."""
        self.env.run()
        actions = [str(fact["move"]) for fact in self._facts("action")]
        if len(actions) != 1:
            raise ProtocolError(
                "Expected exactly one action fact per cycle, "
                f"found {len(actions)}"
            )
        return actions[0]


def _position(world: WumpusWorld) -> Tuple[int, int]:
    return (world.x, world.y)


def _record_visit(
    visited: List[Tuple[int, int]], x: int, y: int
) -> None:
    cell = (x, y)
    if cell not in visited:
        visited.append(cell)


def _pit_guess(
    action: str, x: int, y: int, pits: Set[Tuple[int, int]]
) -> Optional[PitGuess]:
    delta = PIT_GUESS_DELTAS.get(action)
    if delta is None:
        return None
    target = (x + delta[0], y + delta[1])
    return PitGuess(action=action, target=target, correct=target in pits)


def _termination_cause(
    world: WumpusWorld,
    actions: List[str],
    protocol_error: Optional[str],
) -> str:
    if protocol_error is not None:
        return TERMINATION_PROTOCOL_ERROR
    if world.dead:
        return TERMINATION_DEATH
    if not world.done:
        return TERMINATION_MAX_STEPS

    last_action = actions[-1] if actions else None
    if last_action == "quit":
        return TERMINATION_QUIT
    if last_action == "grab":
        return TERMINATION_GOLD
    return TERMINATION_ENERGY if world.energy <= 0 else TERMINATION_GOLD


def run_episode(
    world: WumpusWorld,
    agent,
    max_steps: Optional[int] = None,
) -> EpisodeResult:
    """Run one headless episode from a fresh world state.

    The initial percept is asserted before the first ``run`` call. After each
    action the action fact and the old percept are retracted, and the new
    percept is asserted. A successful grab ends the episode only when the
    world is configured with ``end_on_grab``.

    ``max_steps`` caps the number of actions; by default it matches the
    world's energy budget.
    """
    agent.reset(world.reset())

    actions: List[str] = []
    visited: List[Tuple[int, int]] = [_position(world)]
    guesses: List[PitGuess] = []
    protocol_error: Optional[str] = None
    limit = world.max_steps if max_steps is None else max_steps

    while not world.done and len(actions) < limit:
        try:
            action = agent.run_and_get_action()
        except ProtocolError as exc:
            protocol_error = str(exc)
            break

        guess = _pit_guess(action, world.x, world.y, world.pits)
        result = world.step(action)
        actions.append(action)
        if guess is not None:
            guesses.append(guess)
        _record_visit(visited, world.x, world.y)

        agent.clear_action_facts()
        agent.set_percept(result.obs)

        if action == "quit" and _position(world) != world.start:
            protocol_error = (
                f"Invalid quit at {_position(world)}; "
                f"the agent must return to {world.start}"
            )
            break

    return EpisodeResult(
        actions=actions,
        visited=visited,
        guesses=guesses,
        termination=_termination_cause(world, actions, protocol_error),
        energy=world.energy,
        reward=world.reward,
        steps=len(actions),
        gold_collected=world.has_gold,
        final_position=_position(world),
        protocol_error=protocol_error,
    )


def default_world() -> WumpusWorld:
    return WumpusWorld(
        width=8,
        height=6,
        start=(0, 0),
        walls={(1, 1), (1, 2), (3, 0), (3, 5), (4, 2), (5, 1), (5, 2), (5, 3), (6, 2)},
        pits={(2, 3), (5, 4)},
        wumpus=(3, 2),
        gold=(7, 5),
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Wumpus World + CLIPS GUI")
    parser.add_argument(
        "-m",
        "--map",
        dest="map_file",
        type=str,
        help="Path to JSON map file",
    )
    parser.add_argument(
        "-a",
        "--agent",
        dest="agent_file",
        type=str,
        default="agent.clp",
        help="Path to CLIPS agent file",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        if args.map_file:
            world = WumpusWorld.from_json(args.map_file)
        else:
            world = default_world()
    except Exception as exc:
        print(f"Error loading map: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        agent = ClipsAgent(args.agent_file)
    except Exception as exc:
        print(f"Error loading CLIPS agent: {exc}", file=sys.stderr)
        sys.exit(1)

    from gui import WumpusWorldGUI

    gui = WumpusWorldGUI(world, agent)
    gui.run()


if __name__ == "__main__":
    main()
