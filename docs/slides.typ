#set page(width: 33.87cm, height: 19.05cm, margin: 1.5cm, fill: rgb("#ffffff"))
#set text(font: ("IBM Plex Sans", "Adwaita Sans"), size: 17pt, fill: rgb("#1f2933"))
#set par(leading: 0.7em)
#set heading(numbering: none)

#let accent = rgb("#0b6e4f")
#let ink = rgb("#1f2933")
#let muted = rgb("#6b7280")
#let rule = rgb("#d1d5db")
#let panel = rgb("#f3f4f6")

#let slide(title, body) = {
  text(size: 30pt, weight: "bold", fill: accent, title)
  line(length: 100%, stroke: 1pt + rule)
  v(0.35em)
  body
  pagebreak(weak: true)
}

#align(center + horizon)[
  #text(size: 46pt, weight: "bold", fill: accent)[A CLIPS Rule-Based Agent for Wumpus World]
  #v(0.6em)
  #text(size: 23pt, fill: ink)[Planning, inference and bounded risk in a dark cave]
  #v(1.4em)
  #text(size: 19pt)[Daniel Biasiotto]
  #text(size: 16pt, fill: muted)[Artificial Intelligence and Laboratory · Planning and Rule Systems · 2025–2026]
]
#pagebreak()

#slide("The problem")[
  - A grid cave, unknown layout, local percepts only.
  - *breeze*: an adjacent pit. *stench*: an adjacent Wumpus. *glitter*: the gold is here.
  - Every action costs energy; bumps cost extra. `quit` is valid only at `(0, 0)`.
  - The Wumpus is unique; the gold is unique; a pit may share a cell with a wall.
  #v(0.8em)
  #block(fill: panel, inset: 14pt, radius: 6pt)[
    *Goals, in priority order:* survive → collect the gold → return to `(0, 0)` and quit → preserve energy → test pit hypotheses.
  ]
]

#slide("Simulator and protocol")[
  #table(
    columns: (2fr, 4fr, 2fr, 2fr),
    inset: 7pt,
    stroke: 0.5pt + rule,
    [*Action*], [*Effect*], [*Energy*], [*Reward*],
    [`up/down/left/right`], [move if free, otherwise bump and stay], [-1 / -2], [step cost],
    [`grab`], [collect the gold in the current cell], [-1], [+100],
    [`quit`], [end the episode], [-1], [0],
    [`pit-*`], [test the adjacent cell, no movement], [-1], [+25 / -25],
  )
  #v(0.7em)
  - Exactly one `(action (move ?))` per cycle; old percepts are retracted.
  - The initial percept is asserted before the first `run()`.
  - A quit outside `(0, 0)` is reported as a protocol error.
]

#slide("Architecture: six phases, one cycle")[
  #block(fill: panel, inset: 10pt, radius: 6pt)[
    #raw(
      "MAIN  (schema, counter, stale cleanup, dispatch)\n  |\n  +--> PERCEPT   percept -> pos + visited\n  +--> MAP       visited/blocked -> no-pit, no-wumpus, safe, nbr, frontier\n  +--> HYPO      breeze/stench closure, candidates, pit/Wumpus, CF\n  +--> DECIDE    home/dist/nav, energy budget, goal, next hop\n  +--> ACT       exactly one action: grab, quit, guess, move",
      block: true,
    )
  ]
  #v(0.7em)
  - `MAIN` focuses `PERCEPT MAP HYPO DECIDE ACT`; the focus stack is one-way.
  - Every action rule carries `(not (action (move ?)))`.
  - No `halt`: the agenda drains naturally.
]

#slide("The fact model")[
  #table(
    columns: (3fr, 6fr),
    inset: 6pt,
    stroke: 0.5pt + rule,
    [*Fact*], [*Meaning*],
    [`percept`, `counter`, `action`], [bridge input/output and clock],
    [`pos`, `visited`, `blocked`], [current cell, explored cells, walls and out-of-map cells],
    [`no-pit`, `no-wumpus`, `safe`, `frontier`], [classical exclusions, hazard-free cells, safe-unvisited leaves],
    [`candidate`, `pit-hypothesis`], [a breeze explanation and its CF evidence],
    [`pit`, `wumpus`, `wumpus-possible`], [confirmed hazards and the Wumpus intersection],
    [`home`, `dist`, `nav`, `goal`, `next`], [return distance, current distance, goal distance, target, ranked hop],
    [`guessed`, `has-gold`, `probes-used`], [persistent mission state],
  )
]

#slide("Hazard inference")[
  - Visited → not a pit, not the Wumpus, safe.
  - No breeze → every orthogonal neighbour is `no-pit` (walls included).
  - No stench → every orthogonal neighbour is `no-wumpus`.
  - A bump blocks a cell and rules out the Wumpus, but *not* a pit: a pit may hide under a wall.
  - Breeze → candidates = adjacent cells that are not `no-pit` and not the Wumpus.
  - One candidate for a breeze → confirmed pit. Confirmed pits stay candidates.
  - Wumpus candidates must be adjacent to *every* stench cell; one survivor → confirmed Wumpus.
  #v(0.5em)
  #block(fill: panel, inset: 12pt, radius: 6pt)[
    The Wumpus intersection uses a negated conjunction: "no stench cell lacks this neighbour". This avoids a derive/prune loop.
  ]
]

#slide("Certainty factors with explicit slots")[
  - CLIPS 6.41 has no native CFs: `(declare (CF ...))` and `(get-cf ...)` fail.
  - Each breeze contributes `0.4` to every surviving candidate, once.
  - `source-x`/`source-y` keep evidence facts distinct under CLIPS fact deduplication.
  - Same target → MYCIN positive combination:
    $ "cf" = "cf"_1 + "cf"_2 (1 - "cf"_1) $
  - `0.4` → `0.64` → `0.784`; a confirmed pit is raised to `1.0`.
  - CF is only a ranking/annotation: it never creates `safe` or `pit`.
]

#slide("Planning and energy")[
  - `home`: shortest return distance over *visited* cells; exact and bump-proof.
  - `dist`: shortest distance from the current cell; `nav`: distance to the chosen goal.
  - Expand/relax to a fixed point; unit costs, deterministic tie-break.
  - Affordability: $ "dist"(f) + "home"(f) + 1 + "reserve" <= "energy" $, reserve = 5.
  - Goal priority: grab → probe → quit → exit → frontier.
  - Grab only if the grab plus the return still leaves the reserve.
  - Next hop: a neighbour with `nav = nav(pos) - 1`; rank `up=1`, `right=2`, `down=3`, `left=4`.
  - A bump is detected by comparing the intended move with the next position.
]

#slide("map1: a dead end that needs a bounded risk")[
  #block(fill: panel, inset: 10pt, radius: 6pt)[
    #raw(
      "safe closure from (0,0):\n\n  (0,0) (0,1) (0,2) (0,3) (0,4)\n              (1,3) (1,4) (2,4)\n\n  the only connection is (3,4)\n  (2,4) breeze: (2,3) pit  (2,5) pit  (3,4) safe\n  -> no sound rule can prove (3,4) safe",
      block: true,
    )
  ]
  #v(0.5em)
  - Last resort only: no safe frontier, no gold yet, return reserve intact.
  - At most two probes; the second unlocks only after the first reached its cell.
  - Candidate ceiling `cf <= 0.75`; exclude blocked, Wumpus-possible, guessed.
  - Rank by visited-neighbour support, then CF, then geometry.
  - `map1`: probe `(3,4)`, then `(4,3)`; both safe. `map10`: the probe hits a real pit — the accepted risk.
]

#slide("Pit guesses")[
  - `pit-*` costs one energy; `+25` if the adjacent cell is a pit, `-25` otherwise.
  - $ "EV" = 25p - 25(1-p) - 1 = 50p - 26 $; positive for $p > 0.52$.
  - Conservative threshold: `cf >= 0.75`.
  - Adjacent only, once per cell, never on blocked/safe/Wumpus-possible targets.
  - Never while holding the gold, returning, or probing: mission goals have priority.
  - Energy guard: `energy > home + reserve + 1`.
  - Directions: `up -> pit-north`, `right -> pit-east`, `down -> pit-south`, `left -> pit-west`.
]

#slide("Evaluation: expert vs random")[
  #table(
    columns: (1.2fr, 0.7fr, 0.9fr, 0.8fr, 0.9fr, 0.9fr, 1.1fr, 0.9fr),
    inset: 6pt,
    stroke: 0.5pt + rule,
    [*Agent*], [*Maps*], [*Survival*], [*Gold*], [*Return*], [*Avg E*], [*Guesses*], [*Reward*],
    [expert], [11], [90.9%], [81.8%], [90.9%], [29.8], [7/7], [975],
    [random], [11], [0.0%], [0.0%], [0.0%], [-0.1], [0/0], [-1100],
  )
  #v(0.6em)
  - `map1`: 76 steps, reward 125, energy 111, gold, return, one correct guess `(2,3)`.
  - `map7`: gold unaffordable under the 14-step budget; the agent returns and quits.
  - `map10`: the bounded probe hits a real pit; the alternative safe crossing is not chosen.
  - No protocol errors on the suite.
]

#slide("Limitations and conclusion")[
  *Limitations*
  - The risk probe can die by design; it is a last resort, not a proof.
  - CFs are heuristic; overlapping breezes can inflate a safe cell.
  - Pit guesses are adjacent-only and can be wrong.
  - The return field is conservative (visited graph only).

  #v(0.5em)
  *Conclusion*
  - A complete, explainable CLIPS agent: six modules, classical inference, explicit MYCIN CFs, distance-field planning, bounded risk, pit guesses.
  - The simulator and harness are headless, deterministic and tested.
  - On 11 maps: 10 survivals, 9 golds, 10 returns, 975 points; the random baseline scores -1100.

  #v(0.7em)
  #align(center)[
    #text(size: 22pt, weight: "bold", fill: accent)[Thank you — questions?]
  ]
]
