#!/usr/bin/env python3
"""Run one headless Wumpus episode and print its metrics."""

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate a CLIPS Wumpus agent")
    parser.add_argument("-m", "--map", dest="map_file", required=True)
    parser.add_argument("-a", "--agent", dest="agent_file", required=True)
    parser.add_argument(
        "--max-steps",
        dest="max_steps",
        type=int,
        default=None,
        help="Optional cap on the number of actions",
    )
    return parser.parse_args()


def result_payload(result):
    return {
        "termination": result.termination,
        "steps": result.steps,
        "reward": result.reward,
        "energy": result.energy,
        "gold_collected": result.gold_collected,
        "final_position": list(result.final_position),
        "visited": [list(cell) for cell in result.visited],
        "actions": result.actions,
        "guesses": [
            {
                "action": guess.action,
                "target": list(guess.target),
                "correct": guess.correct,
            }
            for guess in result.guesses
        ],
        "protocol_error": result.protocol_error,
    }


def print_text(payload):
    print(f"Termination: {payload['termination']}")
    print(f"Steps: {payload['steps']}")
    print(f"Reward: {payload['reward']}")
    print(f"Energy: {payload['energy']}")
    print(f"Gold collected: {payload['gold_collected']}")
    print(f"Final position: {tuple(payload['final_position'])}")
    print(f"Visited cells: {len(payload['visited'])}")
    if payload["guesses"]:
        for guess in payload["guesses"]:
            outcome = "correct" if guess["correct"] else "incorrect"
            print(f"Guess {guess['action']} -> {tuple(guess['target'])}: {outcome}")
    else:
        print("Guesses: none")
    if payload["protocol_error"]:
        print(f"Protocol error: {payload['protocol_error']}")


def main():
    from wumpus import ClipsAgent, WumpusWorld, run_episode

    args = parse_args()
    world = WumpusWorld.from_json(args.map_file)
    agent = ClipsAgent(args.agent_file)
    result = run_episode(world, agent, max_steps=args.max_steps)
    print_text(result_payload(result))

    return 1 if result.termination == "protocol_error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
