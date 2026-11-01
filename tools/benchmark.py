#!/usr/bin/env python3
"""Benchmark the expert CLIPS agent against the random baseline."""

import argparse
import json
import sys
from pathlib import Path

import clips  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wumpus import (  # noqa: E402
    ClipsAgent,
    TERMINATION_DEATH,
    TERMINATION_ENERGY,
    TERMINATION_QUIT,
    WumpusWorld,
    run_episode,
)


TABLE_HEADERS = (
    "Agent",
    "Maps",
    "Surv%",
    "Gold%",
    "Return%",
    "AvgE",
    "AvgSteps",
    "Guesses",
    "Correct",
    "Acc%",
    "Reward",
)
TABLE_WIDTHS = (10, 4, 6, 6, 7, 5, 8, 7, 7, 6, 8)


class StdoutMute(clips.Router):
    """Drop CLIPS stdout so the benchmark report stays readable."""

    def __init__(self):
        super().__init__("benchmark-stdout-mute", 20)

    def query(self, name):
        return name == "stdout"

    def write(self, name, message):
        return None


class SeededClipsAgent(ClipsAgent):
    """CLIPS agent whose random generator is reseeded after each reset.

    ``run_episode`` resets the bridge before the first action, so seeding in
    the constructor would be overwritten. The seed belongs to ``reset``.
    """

    def __init__(self, program, seed, quiet=True):
        super().__init__(str(program))
        self.seed = int(seed)
        if quiet:
            self.env._routers.add_router(StdoutMute())

    def reset(self, obs=None):
        super().reset(obs)
        self.env.eval(f"(seed {self.seed})")


def map_label(path):
    """Return a project-relative map name when possible."""
    path = Path(path)
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def map_sort_key(path):
    """Order map2, map3, ... map10 by their numeric suffix."""
    name = Path(path).stem
    suffix = name[3:] if name.startswith("map") else ""
    if suffix.isdigit():
        return (0, int(suffix))
    return (1, name)


def default_maps():
    """Return map1 followed by the committed suite in numeric order."""
    suite = sorted(
        (PROJECT_ROOT / "maps").glob("*.json"), key=map_sort_key
    )
    return [PROJECT_ROOT / "map1.json"] + suite


def collect_maps(entries):
    """Expand files and directories into an ordered map list."""
    paths = []
    for entry in entries:
        path = Path(entry)
        if path.is_dir():
            paths.extend(sorted(path.glob("*.json"), key=map_sort_key))
        else:
            paths.append(path)
    return paths


def guess_accuracy(correct, total):
    """Return a fraction, or None when the agent made no guess."""
    if total == 0:
        return None
    return round(correct / total, 4)


def episode_metrics(result, start):
    """Extract the benchmark metrics from one episode result."""
    total_guesses = len(result.guesses)
    correct_guesses = sum(1 for guess in result.guesses if guess.correct)
    returned = (
        tuple(result.final_position) == tuple(start)
        and result.termination == TERMINATION_QUIT
    )
    survived = result.termination not in {
        TERMINATION_DEATH,
        TERMINATION_ENERGY,
    }
    return {
        "termination": result.termination,
        "gold_collected": bool(result.gold_collected),
        "returned": returned,
        "survived": survived,
        "reward": float(result.reward),
        "energy": result.energy,
        "steps": result.steps,
        "visited": len(result.visited),
        "guesses": total_guesses,
        "correct_guesses": correct_guesses,
        "guess_accuracy": guess_accuracy(correct_guesses, total_guesses),
    }


def error_record(map_path, agent_name, program, termination, exc):
    """Build a record for a map or agent that could not be evaluated."""
    return {
        "map": map_label(map_path),
        "agent": agent_name,
        "program": str(program),
        "termination": termination,
        "gold_collected": False,
        "returned": False,
        "survived": False,
        "reward": 0.0,
        "energy": None,
        "steps": None,
        "visited": None,
        "guesses": 0,
        "correct_guesses": 0,
        "guess_accuracy": None,
        "error": str(exc),
    }


def run_episode_for_map(map_path, agent_name, program, seed):
    """Run one episode and convert failures into benchmark records."""
    try:
        world = WumpusWorld.from_json(map_path)
    except Exception as exc:
        return error_record(
            map_path, agent_name, program, "load_error", exc
        )

    try:
        agent = SeededClipsAgent(program, seed)
        result = run_episode(world, agent)
    except Exception as exc:
        return error_record(
            map_path, agent_name, program, "agent_error", exc
        )

    record = {
        "map": map_label(map_path),
        "agent": agent_name,
        "program": str(program),
    }
    record.update(episode_metrics(result, world.start))
    return record


def run_benchmark(map_paths, agent_program, baseline_program, seed):
    """Run both agents once on every map and return per-episode records."""
    roles = (("expert", agent_program), ("random", baseline_program))
    return [
        run_episode_for_map(path, name, program, seed)
        for path in map_paths
        for name, program in roles
    ]


def mean(values):
    """Return the rounded mean, or None for an empty sample."""
    values = list(values)
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def rate(count, total):
    """Return a rounded fraction, or None for an empty sample."""
    if total == 0:
        return None
    return round(count / total, 4)


def count_true(records, field):
    """Count records whose boolean field is true."""
    return sum(1 for record in records if record[field])


def total_of(records, field):
    """Sum a numeric field across records."""
    return sum(record[field] for record in records)


def present_values(records, field):
    """Collect non-null values of a numeric field."""
    return [
        record[field] for record in records if record[field] is not None
    ]


def aggregate_agent(agent_name, records):
    """Aggregate one agent's episode records."""
    total = len(records)
    guesses = total_of(records, "guesses")
    correct = total_of(records, "correct_guesses")
    return {
        "agent": agent_name,
        "maps": total,
        "survival_rate": rate(count_true(records, "survived"), total),
        "gold_rate": rate(count_true(records, "gold_collected"), total),
        "return_rate": rate(count_true(records, "returned"), total),
        "avg_energy": mean(present_values(records, "energy")),
        "avg_steps": mean(present_values(records, "steps")),
        "guesses": guesses,
        "correct_guesses": correct,
        "guess_accuracy": rate(correct, guesses),
        "total_reward": round(total_of(records, "reward"), 2),
    }


def aggregate_records(records):
    """Group episode records by agent and aggregate each group."""
    grouped = {}
    for record in records:
        grouped.setdefault(record["agent"], []).append(record)
    return {
        name: aggregate_agent(name, group)
        for name, group in grouped.items()
    }


def percent(value):
    """Format a fraction for the report table."""
    if value is None:
        return "-"
    return f"{value * 100:.1f}%"


def number(value):
    """Format an optional mean for the report table."""
    if value is None:
        return "-"
    return f"{value:.1f}"


def table_row(values):
    """Format one left-aligned report row."""
    cells = (
        str(value).ljust(width)
        for value, width in zip(values, TABLE_WIDTHS)
    )
    return " ".join(cells).rstrip()


def format_table(aggregates):
    """Render the aggregate comparison as a compact text table."""
    rows = [table_row(TABLE_HEADERS)]
    for name, aggregate in aggregates.items():
        rows.append(
            table_row(
                (
                    name,
                    aggregate["maps"],
                    percent(aggregate["survival_rate"]),
                    percent(aggregate["gold_rate"]),
                    percent(aggregate["return_rate"]),
                    number(aggregate["avg_energy"]),
                    number(aggregate["avg_steps"]),
                    aggregate["guesses"],
                    aggregate["correct_guesses"],
                    percent(aggregate["guess_accuracy"]),
                    number(aggregate["total_reward"]),
                )
            )
        )
    return "\n".join(rows)


def build_payload(map_paths, aggregates, records, seed):
    """Assemble the JSON report."""
    return {
        "seed": seed,
        "maps": [map_label(path) for path in map_paths],
        "aggregate": aggregates,
        "episodes": records,
    }


def write_json(path, payload):
    """Write the report, creating parent directories when needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def parse_args(argv=None):
    """Parse benchmark command-line options."""
    parser = argparse.ArgumentParser(
        description="Compare the expert Wumpus agent with a random baseline"
    )
    parser.add_argument(
        "--maps",
        nargs="+",
        help="Map files or directories (default: map1.json and maps/*.json)",
    )
    parser.add_argument(
        "--agent",
        default=str(PROJECT_ROOT / "agent.clp"),
        help="Expert CLIPS agent file",
    )
    parser.add_argument(
        "--baseline",
        default=str(PROJECT_ROOT / "agent_random.clp"),
        help="Baseline CLIPS agent file",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Seed applied after every agent reset",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        help="Optional path for the JSON report",
    )
    return parser.parse_args(argv)


def main(argv=None):
    """Run the benchmark and print the aggregate table."""
    args = parse_args(argv)
    map_paths = collect_maps(args.maps) if args.maps else default_maps()
    records = run_benchmark(
        map_paths, args.agent, args.baseline, args.seed
    )
    aggregates = aggregate_records(records)
    print(format_table(aggregates))
    if args.json_path:
        write_json(
            args.json_path,
            build_payload(map_paths, aggregates, records, args.seed),
        )
        print(f"JSON report: {args.json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
