# Wumpus World: a CLIPS rule-based agent

Project for **Artificial Intelligence and Laboratory** (a.y. 2025–2026),
module *Planning and Rule Systems*. The repository contains a rule-based agent
written in CLIPS, a Python discrete-event simulator, a `clipspy` bridge, a
headless evaluation harness, and a benchmark against the provided random
baseline.

## Highlights

- `agent.clp`: a complete agent with six CLIPS modules, classical hazard
  inference, explicit certainty factors combined with the MYCIN formula,
  distance-field planning, energy-aware return, a bounded last-resort risk
  probe, and pit guesses.
- `wumpus.py`: deterministic simulator and headless runner with a strict
  one-action protocol.
- `tools/evaluate.py`: run one episode and print its metrics.
- `tools/benchmark.py`: run the expert and the random baseline over the
  committed map suite and print a comparison table.
- On the 11-map suite the expert survives 10 maps, collects the gold on 9,
  returns to `(0, 0)` on 10, and scores 975; the random baseline scores -1100.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# GUI (needs Tk; on Debian/Ubuntu: sudo apt install python3-tk)
python wumpus.py -m map1.json -a agent.clp

# One headless episode
python tools/evaluate.py -m map1.json -a agent.clp

# Expert vs random over map1 + maps/
python tools/benchmark.py
```

Example map1 episode:

```text
Termination: quit
Steps: 76
Reward: 125.0
Energy: 111
Gold collected: True
Final position: (0, 0)
Visited cells: 31
Guess pit-north -> (2, 3): correct
```

## Domain and protocol

The cave is an unknown grid. The agent starts at `(0, 0)`, which is also the
exit. Percepts are local and four-neighbour:

- `breeze`: at least one adjacent cell is a pit;
- `stench`: an adjacent cell contains the Wumpus;
- `glitter`: the gold is in the current cell.

| Action | Effect | Energy | Reward |
|---|---|---|---|
| `up/down/left/right` | move if the target is free, otherwise bump and stay | -1, or -2 on a bump | step cost |
| `grab` | collect the gold in the current cell | -1 | +100 |
| `quit` | end the episode; valid only at `(0, 0)` | -1 | 0 |
| `pit-north/south/west/east` | test the adjacent cell without moving | -1 | +25 / -25 |

The bridge asserts the initial percept before the first run, replaces the
percept every step, and requires exactly one `(action (move ?))` fact per
cycle. A zero-action or multi-action cycle is a protocol error. The simulator
itself accepts `quit` anywhere; the harness and the agent enforce the exit.

Pits may share a cell with a wall. The Wumpus is unique and cannot share a cell
with a pit, a wall, or the gold. The gold cannot share a cell with a pit or a
wall. These rules drive the inference.

`map1.json` uses `end_on_grab: false`, so the agent must return to the exit.
The harness also supports `end_on_grab: true`, where the episode ends on the
grab.

## Agent architecture

```text
MAIN  (templates, counter, stale-percept cleanup, single dispatch)
  |
  +--> PERCEPT   percept -> pos + visited
  +--> MAP       visited/blocked -> no-pit, no-wumpus, safe, nbr, frontier
  +--> HYPO      breeze/stench closure, candidates, pit/Wumpus, CF
  +--> DECIDE    home/dist/nav fields, energy budget, goal, next hop
  +--> ACT       exactly one action: grab, quit, guess, move
```

`MAIN` focuses `PERCEPT MAP HYPO DECIDE ACT` and each module imports
`MAIN ?ALL`. Every action rule carries `(not (action (move ?)))`; no `halt` is
used, so the agenda drains naturally. The focus stack is one-way, which is why
`HYPO` also asserts frontiers for newly inferred safe cells: `DECIDE` must see
them in the same cycle.

Key facts include `pos`, `visited`, `blocked`, `no-pit`, `no-wumpus`, `safe`,
`frontier`, `breeze-at`, `no-breeze-at`, `stench-at`, `no-stench-at`,
`candidate`, `wumpus-possible`, `pit`, `wumpus`, `pit-hypothesis`, `home`,
`dist`, `nav`, `goal`, `next`, `guessed`, `has-gold`, and `probes-used`.

## Hazard inference and certainty factors

The inference is classical and monotone:

- a visited cell is not a pit, not the Wumpus, and safe;
- no breeze rules out pits in every orthogonal neighbour, walls included;
- no stench rules out the Wumpus in every neighbour;
- negative coordinates are outside the map: `blocked`, `no-pit`, `no-wumpus`;
- a bump blocks a cell and rules out the Wumpus, but not a pit (a pit may hide
  under a wall);
- a breeze with exactly one remaining candidate confirms a pit;
- the Wumpus must be adjacent to every stench cell; one survivor confirms it.

CLIPS 6.41 has no native certainty factors. The agent uses explicit `cf` slots,
one `pit-hypothesis` per breeze source with `cf = 0.4`, and combines evidence
with the MYCIN positive formula:

```text
cf = cf1 + cf2 * (1 - cf1)
```

The `source-x`/`source-y` slots keep evidence facts distinct under CLIPS fact
deduplication, and `evidence-seen` prevents the same breeze from contributing
twice. One breeze gives `0.4`, two give `0.64`, three give `0.784`, and a
confirmed pit is raised to `1.0`. CF never creates `safe` or `pit`: classical
facts always win.

## Planning, energy, and risk

Three distance fields drive the plan:

- `home`: shortest return distance over visited cells; exact and bump-proof;
- `dist`: shortest distance from the current cell over visited cells;
- `nav`: distance to the chosen goal, over visited cells plus the goal frontier.

A frontier `f` is affordable only when
`dist(f) + home(f) + 1 + reserve <= energy`, with `reserve = 5` and the final
`+1` for `quit`. The goal priority is:

```text
grab > risk probe > quit > exit > frontier
```

The agent grabs only when the grab plus the return still leaves the reserve.
It returns and quits when the gold is held, the energy is low, or no affordable
safe frontier remains. `quit` is selected only at `(0, 0)`. The next hop is a
neighbour with `nav = nav(pos) - 1`, with the fixed direction rank
`up=1, right=2, down=3, left=4`.

`map1.json` has a genuine dead end: the safe pocket reaches `(2,4)`, and the
only connection to the rest of the cave is `(3,4)`, whose pit cannot be
disproved. The agent therefore includes a bounded last-resort risk probe:

- only when no safe frontier remains and the gold is missing;
- only for unvisited, non-blocked, non-Wumpus-possible cells with
  `cf <= 0.75`;
- at most two probes, and the second only after the first reached its target;
- return reserve must fit;
- candidates ranked by visited-neighbour support, then CF, then geometry.

This is a deliberate trade-off, not a proof of safety. On `map1` the probes
`(3,4)` and `(4,3)` are safe and the agent collects the gold; on `map10` the
probe hits a real pit. The budget and threshold are configurable in the
`config` deffact.

## Pit guesses

A `pit-*` action costs one energy and pays `+25` for a pit, `-25` otherwise:

```text
EV = 25p - 25(1-p) - 1 = 50p - 26
```

The agent uses a conservative `cf >= 0.75` threshold. It guesses only an
adjacent cell, once per episode, never on a blocked/safe/Wumpus-possible cell,
and only when `energy > home + reserve + 1`. It does not guess while holding
the gold, returning to the exit, or probing. Direction mapping:
`up -> pit-north`, `right -> pit-east`, `down -> pit-south`,
`left -> pit-west`.

## Evaluation

```bash
python tools/benchmark.py --json benchmark.json
```

Aggregate over `map1` plus the ten maps in `maps/` (seed 7):

| Agent | Maps | Survival | Gold | Return | Avg energy | Avg steps | Guesses | Accuracy | Reward |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| expert | 11 | 90.9% | 81.8% | 90.9% | 29.8 | 33.5 | 7/7 | 100% | 975 |
| random | 11 | 0.0% | 0.0% | 0.0% | -0.1 | 43.3 | 0/0 | — | -1100 |

The expert's two non-successes are documented policy outcomes: `map7` has an
unaffordable gold under its low energy budget, and `map10` is a bounded risk
probe into a real pit. The suite is kept as-is so the comparison shows the
trade-off rather than a curated win rate.

## Repository layout

```text
agent.clp              expert CLIPS agent
agent_random.clp       provided random baseline
wumpus.py              simulator, bridge, headless runner
gui.py                 Tk front end (lazy import)
map1.json              course map (end_on_grab: false)
maps/                  evaluation suite (10 maps)
tools/evaluate.py      one-episode CLI
tools/benchmark.py     expert-vs-random benchmark
tests/                 simulator, bridge, agent, benchmark, GUI tests
docs/report.md         project report source
docs/report.pdf        project report
docs/slides.typ        presentation source
docs/slides.pdf        presentation
```

## Tests and quality gates

```bash
pytest -q tests/
flake8 . --count --select=E9,F63,F7,F82 \
  --show-source --statistics --exclude=.venv,__pycache__,.git
radon cc -s -a -nb wumpus.py gui.py tools/ tests/
```

The suite covers simulator semantics, the Python/CLIPS bridge, the agent
contract, perception and map closure, hazard inference and CF, planning and
risk probes, pit guesses, the benchmark, and GUI protocol errors. CI runs the
same checks on Python 3.11.

## Report and slides

- [Project report](docs/report.md) — [PDF](docs/report.pdf)
- [Presentation](docs/slides.typ) — [PDF](docs/slides.pdf)

## Notes and limitations

- The risk probe can die by design; set `max-probes` to 0 for a strict
  survival-only policy.
- Certainty factors are heuristic; overlapping breezes can inflate a safe
  cell, which is why probe ranking uses support first.
- Pit guesses are adjacent-only and can be wrong.
- The return field is conservative: it uses the visited graph, so the agent
  may prefer a longer known path over a shorter unproven one.
