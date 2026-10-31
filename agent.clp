; Intelligent Wumpus agent.
;
; MAIN owns the schema and the cycle clock. Each phase module imports the
; complete MAIN namespace so templates and shared functions have one owner.
; The bridge owns the counter and the percept; the agent only reads them.

(defmodule MAIN (export ?ALL))
(defmodule PERCEPT (import MAIN ?ALL))
(defmodule MAP (import MAIN ?ALL))
(defmodule HYPO (import MAIN ?ALL))
(defmodule DECIDE (import MAIN ?ALL))
(defmodule ACT (import MAIN ?ALL))


; ---------------------------------------------------------------------------
; MAIN schema
; ---------------------------------------------------------------------------

; Simulator input; read by every phase, replaced by the bridge each step.
(deftemplate MAIN::percept
  (slot x (type INTEGER))
  (slot y (type INTEGER))
  (slot steps (type INTEGER))
  (slot breeze (type SYMBOL) (allowed-values TRUE FALSE))
  (slot stench (type SYMBOL) (allowed-values TRUE FALSE))
  (slot glitter (type SYMBOL) (allowed-values TRUE FALSE))
  (slot energy (type INTEGER)))

; Cycle clock; the bridge keeps exactly one counter and updates its step.
(deftemplate MAIN::counter
  (slot step (type INTEGER)))

; Intentional output; ACT asserts exactly one per cycle.
(deftemplate MAIN::action
  (slot move (type SYMBOL) (default ?NONE)
        (allowed-values up down left right grab quit
                        pit-north pit-south pit-west pit-east)))

; Tuning values shared by the decision and hypothesis phases.
(deftemplate MAIN::config
  (slot reserve (type INTEGER) (default 5))
  (slot evidence (type FLOAT) (default 0.4))
  (slot guess-threshold (type FLOAT) (default 0.75)))

; Current agent position; PERCEPT maintains exactly one fact.
(deftemplate MAIN::pos
  (slot x (type INTEGER))
  (slot y (type INTEGER)))

; Persistent map knowledge discovered by the agent.
(deftemplate MAIN::visited
  (slot x (type INTEGER))
  (slot y (type INTEGER)))

; A wall or out-of-bounds cell discovered by a bump.
(deftemplate MAIN::blocked
  (slot x (type INTEGER))
  (slot y (type INTEGER)))

(deftemplate MAIN::no-pit
  (slot x (type INTEGER))
  (slot y (type INTEGER)))

(deftemplate MAIN::no-wumpus
  (slot x (type INTEGER))
  (slot y (type INTEGER)))

(deftemplate MAIN::pit
  (slot x (type INTEGER))
  (slot y (type INTEGER)))

(deftemplate MAIN::wumpus
  (slot x (type INTEGER))
  (slot y (type INTEGER)))

(deftemplate MAIN::safe
  (slot x (type INTEGER))
  (slot y (type INTEGER)))

(deftemplate MAIN::frontier
  (slot x (type INTEGER))
  (slot y (type INTEGER)))

; Singleton planner workspace marker; DECIDE advances its step once per cycle.
(deftemplate MAIN::plan
  (slot step (type INTEGER) (default -1)))

; The agent holds the gold; it survives grab actions and all cycle cleanup.
(deftemplate MAIN::has-gold)

; Best affordable frontier for the current cycle; owned by DECIDE.
(deftemplate MAIN::best-frontier
  (slot x (type INTEGER))
  (slot y (type INTEGER))
  (slot d (type INTEGER)))

; The reserve would be consumed by the return path; owned by DECIDE.
(deftemplate MAIN::low-energy)

; Orthogonal movement deltas. The direction symbols are the simulator's
; action names; rank fixes the deterministic tie-break order used by later
; phases: up=1 (north), right=2 (east), down=3 (south), left=4 (west).
(deftemplate MAIN::delta
  (slot dir (type SYMBOL) (allowed-values up down left right))
  (slot dx (type INTEGER))
  (slot dy (type INTEGER))
  (slot rank (type INTEGER)))

; Directed link from a safe source to one of its four neighbours. The target
; may lie outside the known map; MAP marks it blocked once a bump proves it.
(deftemplate MAIN::nbr
  (slot x (type INTEGER))
  (slot y (type INTEGER))
  (slot nx (type INTEGER))
  (slot ny (type INTEGER))
  (slot dir (type SYMBOL) (allowed-values up down left right))
  (slot rank (type INTEGER)))

; Cells whose percept reported a local hazard.
(deftemplate MAIN::breeze-at
  (slot x (type INTEGER))
  (slot y (type INTEGER)))

(deftemplate MAIN::stench-at
  (slot x (type INTEGER))
  (slot y (type INTEGER)))

; Cells whose percept explicitly reported no local hazard.
(deftemplate MAIN::no-breeze-at
  (slot x (type INTEGER))
  (slot y (type INTEGER)))

(deftemplate MAIN::no-stench-at
  (slot x (type INTEGER))
  (slot y (type INTEGER)))

; A hazard candidate for a source cell; owned by HYPO.
(deftemplate MAIN::candidate
  (slot bx (type INTEGER))
  (slot by (type INTEGER))
  (slot px (type INTEGER))
  (slot py (type INTEGER)))

; A cell consistent with every stench observed so far; owned by HYPO.
(deftemplate MAIN::wumpus-possible
  (slot x (type INTEGER))
  (slot y (type INTEGER)))

; Per-source pit belief; source slots keep evidence facts distinct.
(deftemplate MAIN::pit-hypothesis
  (slot x (type INTEGER))
  (slot y (type INTEGER))
  (slot cf (type FLOAT) (default 0.0))
  (slot source-x (type INTEGER))
  (slot source-y (type INTEGER)))

; Evidence already folded into a hypothesis; owned by HYPO.
(deftemplate MAIN::evidence-seen
  (slot source-x (type INTEGER))
  (slot source-y (type INTEGER))
  (slot x (type INTEGER))
  (slot y (type INTEGER)))

; Pit cells already guessed; owned by HYPO.
(deftemplate MAIN::guessed
  (slot x (type INTEGER))
  (slot y (type INTEGER)))

; Distance fields owned by DECIDE; d=-1 marks an unreached cell.
(deftemplate MAIN::home
  (slot x (type INTEGER))
  (slot y (type INTEGER))
  (slot d (type INTEGER)))

(deftemplate MAIN::dist
  (slot x (type INTEGER))
  (slot y (type INTEGER))
  (slot d (type INTEGER)))

(deftemplate MAIN::nav
  (slot x (type INTEGER))
  (slot y (type INTEGER))
  (slot d (type INTEGER)))

; Selected target for the current cycle; owned by DECIDE.
(deftemplate MAIN::goal
  (slot kind (type SYMBOL))
  (slot x (type INTEGER))
  (slot y (type INTEGER)))

; Ranked next hop; owned by DECIDE and consumed by ACT.
(deftemplate MAIN::next
  (slot dir (type SYMBOL))
  (slot rank (type INTEGER)))

; Previous action and its origin; owned by ACT for bump detection.
(deftemplate MAIN::last-move
  (slot move (type SYMBOL))
  (slot from-x (type INTEGER))
  (slot from-y (type INTEGER)))

; MYCIN positive-evidence combination for explicit CF slots.
(deffunction combine-cf-positive (?a ?b)
  "Combine two positive certainty factors and clamp to [0.0, 1.0]."
  (bind ?cf (+ ?a (* ?b (- 1.0 ?a))))
  (if (> ?cf 1.0) then (bind ?cf 1.0))
  (if (< ?cf 0.0) then (bind ?cf 0.0))
  ?cf)

; Number of pit candidates explained by one breeze source.
(deffunction candidate-count (?bx ?by)
  "Count the candidate facts attached to a breeze source."
  (length$ (find-all-facts ((?c candidate))
             (and (= ?c:bx ?bx) (= ?c:by ?by)))))

; Number of cells compatible with every observed stench.
(deffunction wumpus-count ()
  "Count the cells that can hold the single Wumpus."
  (length$ (find-all-facts ((?w wumpus-possible)) TRUE)))

; Drop the navigation field when the goal changes inside a planning cycle.
(deffunction clear-nav-facts ()
  "Retract every navigation distance fact."
  (foreach ?nav-fact (find-all-facts ((?fact nav)) TRUE)
    (retract ?nav-fact)))

; Reset the transient planning workspace. Persistent map knowledge, the plan
; marker, and the held-gold flag are deliberately preserved.
(deffunction clear-plan-facts ()
  "Retract the planning facts that are rebuilt every cycle."
  (clear-nav-facts)
  (foreach ?dist-fact (find-all-facts ((?fact dist)) TRUE)
    (retract ?dist-fact))
  (foreach ?best-fact (find-all-facts ((?fact best-frontier)) TRUE)
    (retract ?best-fact))
  (foreach ?low-fact (find-all-facts ((?fact low-energy)) TRUE)
    (retract ?low-fact))
  (foreach ?goal-fact (find-all-facts ((?fact goal)) TRUE)
    (retract ?goal-fact))
  (foreach ?next-fact (find-all-facts ((?fact next)) TRUE)
    (retract ?next-fact)))

(deffacts MAIN::initial-state
  (counter (step 0))
  (config (reserve 5) (evidence 0.4) (guess-threshold 0.75))
  (plan (step -1)))

(deffacts MAIN::movement-deltas
  (delta (dir up) (dx 0) (dy -1) (rank 1))
  (delta (dir right) (dx 1) (dy 0) (rank 2))
  (delta (dir down) (dx 0) (dy 1) (rank 3))
  (delta (dir left) (dx -1) (dy 0) (rank 4)))


; ---------------------------------------------------------------------------
; MAIN cycle control
; ---------------------------------------------------------------------------

; Keep only the percept that belongs to the current bridge step.
(defrule MAIN::drop-stale-percepts
  (declare (salience 950))
  (counter (step ?step))
  ?stale <- (percept (steps ?steps))
  (test (< ?steps ?step))
  =>
  (retract ?stale))

; Start one phase sweep and let the focus stack unwind through ACT.
(defrule MAIN::dispatch-cycle
  (declare (salience 900))
  (counter (step ?step))
  (not (action (move ?)))
  =>
  (focus PERCEPT MAP HYPO DECIDE ACT))


; ---------------------------------------------------------------------------
; PERCEPT: normalize the current percept into persistent facts
; ---------------------------------------------------------------------------

(defrule PERCEPT::seed-position
  (percept (x ?x) (y ?y))
  (not (pos (x ?) (y ?)))
  =>
  (assert (pos (x ?x) (y ?y))))

(defrule PERCEPT::move-position
  ?current <- (pos (x ?x) (y ?y))
  (percept (x ?next-x) (y ?next-y))
  (test (or (neq ?x ?next-x) (neq ?y ?next-y)))
  =>
  (modify ?current (x ?next-x) (y ?next-y)))

(defrule PERCEPT::record-visited
  (percept (x ?x) (y ?y))
  (not (visited (x ?x) (y ?y)))
  =>
  (assert (visited (x ?x) (y ?y))))


; ---------------------------------------------------------------------------
; MAP: persistent map closure
; ---------------------------------------------------------------------------

; A visited cell is known to be free of both hazards. The blocked guard keeps
; contradictory manual facts from deriving safety for a cell known to be wall.
(defrule MAP::visited-is-no-pit
  (visited (x ?x) (y ?y))
  (not (blocked (x ?x) (y ?y)))
  (not (no-pit (x ?x) (y ?y)))
  =>
  (assert (no-pit (x ?x) (y ?y))))

(defrule MAP::visited-is-no-wumpus
  (visited (x ?x) (y ?y))
  (not (blocked (x ?x) (y ?y)))
  (not (no-wumpus (x ?x) (y ?y)))
  =>
  (assert (no-wumpus (x ?x) (y ?y))))

; A visited cell is safe; blocked cells never become safe.
(defrule MAP::visited-is-safe
  (visited (x ?x) (y ?y))
  (not (blocked (x ?x) (y ?y)))
  (not (safe (x ?x) (y ?y)))
  =>
  (assert (safe (x ?x) (y ?y))))

; Every safe cell exposes one directed link per orthogonal direction. Targets
; outside the known map are kept: the agent discovers bounds by bumping.
(defrule MAP::safe-has-neighbours
  (safe (x ?x) (y ?y))
  (delta (dir ?dir) (dx ?dx) (dy ?dy) (rank ?rank))
  (not (blocked (x ?x) (y ?y)))
  (not (nbr (x ?x) (y ?y) (dir ?dir)))
  =>
  (assert (nbr (x ?x) (y ?y) (nx (+ ?x ?dx)) (ny (+ ?y ?dy))
               (dir ?dir) (rank ?rank))))

; The agent assumes (0,0) is a corner, so negative coordinates are outside
; the map. They are blocked, cannot hide a pit, and cannot hide the Wumpus.
; The negated conjunction keeps the three conclusions in one closure step.
(defrule MAP::negative-neighbour-is-outside
  (nbr (nx ?nx) (ny ?ny))
  (test (or (< ?nx 0) (< ?ny 0)))
  (not (and (blocked (x ?nx) (y ?ny))
            (no-pit (x ?nx) (y ?ny))
            (no-wumpus (x ?nx) (y ?ny))))
  =>
  (assert (blocked (x ?nx) (y ?ny))
          (no-pit (x ?nx) (y ?ny))
          (no-wumpus (x ?nx) (y ?ny))))

; Walls and out-of-bounds cells cannot contain the Wumpus.
(defrule MAP::blocked-is-no-wumpus
  (blocked (x ?x) (y ?y))
  (not (no-wumpus (x ?x) (y ?y)))
  =>
  (assert (no-wumpus (x ?x) (y ?y))))

; A blocked cell can never stay safe or queued for exploration.
(defrule MAP::blocked-drops-safe
  ?safe <- (safe (x ?x) (y ?y))
  (blocked (x ?x) (y ?y))
  =>
  (retract ?safe))

(defrule MAP::blocked-drops-frontier
  ?frontier <- (frontier (x ?x) (y ?y))
  (blocked (x ?x) (y ?y))
  =>
  (retract ?frontier))

; Frontier: safe, unvisited, and still enterable.
(defrule MAP::frontier-is-safe-unvisited
  (safe (x ?x) (y ?y))
  (not (visited (x ?x) (y ?y)))
  (not (blocked (x ?x) (y ?y)))
  (not (frontier (x ?x) (y ?y)))
  =>
  (assert (frontier (x ?x) (y ?y))))

; Reaching a frontier removes it from the exploration set.
(defrule MAP::visited-drops-frontier
  ?frontier <- (frontier (x ?x) (y ?y))
  (visited (x ?x) (y ?y))
  =>
  (retract ?frontier))

; A movement that left the position unchanged hit a wall or the map boundary.
; The target is blocked, not pit-free: a pit may share a wall cell.
(defrule MAP::bump-blocks-target
  ?last <- (last-move (move ?dir) (from-x ?x) (from-y ?y))
  (pos (x ?x) (y ?y))
  (delta (dir ?dir) (dx ?dx) (dy ?dy))
  =>
  (assert (blocked (x (+ ?x ?dx)) (y (+ ?y ?dy))))
  (retract ?last))

; A movement that changed the position succeeded; no wall is learned.
(defrule MAP::move-succeeded
  ?last <- (last-move (move ?dir) (from-x ?x) (from-y ?y))
  (pos (x ?nx) (y ?ny))
  (test (or (neq ?nx ?x) (neq ?ny ?y)))
  =>
  (retract ?last))


; ---------------------------------------------------------------------------
; HYPO: hazard evidence and pit hypotheses
; ---------------------------------------------------------------------------

; Record hazard evidence for the current cell. Positive and negative facts for
; the same cell exclude each other.
(defrule HYPO::record-breeze
  (declare (salience 500))
  (percept (x ?x) (y ?y) (breeze TRUE))
  (not (breeze-at (x ?x) (y ?y)))
  (not (no-breeze-at (x ?x) (y ?y)))
  =>
  (assert (breeze-at (x ?x) (y ?y))))

(defrule HYPO::record-no-breeze
  (declare (salience 500))
  (percept (x ?x) (y ?y) (breeze FALSE))
  (not (no-breeze-at (x ?x) (y ?y)))
  (not (breeze-at (x ?x) (y ?y)))
  =>
  (assert (no-breeze-at (x ?x) (y ?y))))

(defrule HYPO::record-stench
  (declare (salience 500))
  (percept (x ?x) (y ?y) (stench TRUE))
  (not (stench-at (x ?x) (y ?y)))
  (not (no-stench-at (x ?x) (y ?y)))
  =>
  (assert (stench-at (x ?x) (y ?y))))

(defrule HYPO::record-no-stench
  (declare (salience 500))
  (percept (x ?x) (y ?y) (stench FALSE))
  (not (no-stench-at (x ?x) (y ?y)))
  (not (stench-at (x ?x) (y ?y)))
  =>
  (assert (no-stench-at (x ?x) (y ?y))))

; A cell without breeze cannot have a pit in any orthogonal neighbour, even
; when the neighbour is a wall or lies outside the map.
(defrule HYPO::no-breeze-rules-out-pit
  (declare (salience 480))
  (no-breeze-at (x ?x) (y ?y))
  (nbr (x ?x) (y ?y) (nx ?nx) (ny ?ny))
  (not (no-pit (x ?nx) (y ?ny)))
  =>
  (assert (no-pit (x ?nx) (y ?ny))))

; A cell without stench cannot have the Wumpus in any orthogonal neighbour.
(defrule HYPO::no-stench-rules-out-wumpus
  (declare (salience 480))
  (no-stench-at (x ?x) (y ?y))
  (nbr (x ?x) (y ?y) (nx ?nx) (ny ?ny))
  (not (no-wumpus (x ?nx) (y ?ny)))
  =>
  (assert (no-wumpus (x ?nx) (y ?ny))))

; A pit cannot contain the Wumpus.
(defrule HYPO::pit-is-no-wumpus
  (declare (salience 460))
  (pit (x ?x) (y ?y))
  (not (no-wumpus (x ?x) (y ?y)))
  =>
  (assert (no-wumpus (x ?x) (y ?y))))

; The Wumpus cannot share a pit.
(defrule HYPO::wumpus-is-no-pit
  (declare (salience 460))
  (wumpus (x ?x) (y ?y))
  (not (no-pit (x ?x) (y ?y)))
  =>
  (assert (no-pit (x ?x) (y ?y))))

; A candidate that later stops being a possible pit no longer explains a breeze.
(defrule HYPO::drop-invalid-candidate
  (declare (salience 440))
  ?candidate <- (candidate (px ?px) (py ?py))
  (or (no-pit (x ?px) (y ?py))
      (wumpus (x ?px) (y ?py)))
  =>
  (retract ?candidate))

; A hypothesis is not a classical fact: discard it when the target is excluded.
(defrule HYPO::drop-invalid-pit-hypothesis
  (declare (salience 440))
  ?hypothesis <- (pit-hypothesis (x ?x) (y ?y))
  (or (no-pit (x ?x) (y ?y))
      (wumpus (x ?x) (y ?y)))
  =>
  (retract ?hypothesis))

; A cell compatible with every stench must be adjacent to every stench cell.
; The negated conjunction expresses "no stench cell lacks this neighbour" as a
; single condition, so a new stench invalidates stale possibilities without a
; derive/prune oscillation.
(defrule HYPO::wumpus-possible-from-stench
  (declare (salience 400))
  (stench-at (x ?sx) (y ?sy))
  (nbr (x ?sx) (y ?sy) (nx ?px) (ny ?py))
  (not (no-wumpus (x ?px) (y ?py)))
  (not (wumpus-possible (x ?px) (y ?py)))
  (not (and (stench-at (x ?ox) (y ?oy))
            (not (nbr (x ?ox) (y ?oy) (nx ?px) (ny ?py)))))
  =>
  (assert (wumpus-possible (x ?px) (y ?py))))

; Discard a possibility when a newer stench cell is not adjacent to it.
(defrule HYPO::prune-wumpus-possible
  (declare (salience 420))
  ?possible <- (wumpus-possible (x ?px) (y ?py))
  (stench-at (x ?ox) (y ?oy))
  (not (nbr (x ?ox) (y ?oy) (nx ?px) (ny ?py)))
  =>
  (retract ?possible))

; Discard a possibility once another rule proves the cell Wumpus-free.
(defrule HYPO::drop-invalid-wumpus-possible
  (declare (salience 420))
  ?possible <- (wumpus-possible (x ?px) (y ?py))
  (no-wumpus (x ?px) (y ?py))
  =>
  (retract ?possible))

; The Wumpus is unique, so a single remaining possibility is a certainty.
; The negated conjunction rebuilds the activation whenever the possibility set
; shrinks, and the count is read at firing time to avoid a stale match.
(defrule HYPO::confirm-wumpus
  (declare (salience 380))
  (stench-at (x ?sx) (y ?sy))
  (wumpus-possible (x ?px) (y ?py))
  (not (wumpus (x ?) (y ?)))
  (not (and (wumpus-possible (x ?ox) (y ?oy))
            (test (or (neq ?ox ?px) (neq ?oy ?py)))))
  =>
  (if (= (wumpus-count) 1)
     then
     (assert (wumpus (x ?px) (y ?py)))))

; Safety is classical: both hazards excluded and the cell is enterable.
(defrule HYPO::infer-safe
  (declare (salience 360))
  (no-pit (x ?x) (y ?y))
  (no-wumpus (x ?x) (y ?y))
  (not (blocked (x ?x) (y ?y)))
  (not (pit (x ?x) (y ?y)))
  (not (wumpus (x ?x) (y ?y)))
  (not (safe (x ?x) (y ?y)))
  =>
  (assert (safe (x ?x) (y ?y))))

; Cells made safe in this phase have no later MAP sweep in the same cycle, so
; the frontier set must be maintained here as well or planning starts blind.
(defrule HYPO::frontier-is-safe-unvisited
  (declare (salience 350))
  (safe (x ?x) (y ?y))
  (not (visited (x ?x) (y ?y)))
  (not (blocked (x ?x) (y ?y)))
  (not (frontier (x ?x) (y ?y)))
  =>
  (assert (frontier (x ?x) (y ?y))))

; Every neighbour of a breeze that is not already excluded explains the breeze.
; Confirmed pits stay candidates: removing them would make a second cell look
; like the unique explanation and cause a false confirmation.
(defrule HYPO::breeze-pit-candidate
  (declare (salience 340))
  (breeze-at (x ?bx) (y ?by))
  (nbr (x ?bx) (y ?by) (nx ?px) (ny ?py))
  (not (no-pit (x ?px) (y ?py)))
  (not (wumpus (x ?px) (y ?py)))
  (not (candidate (bx ?bx) (by ?by) (px ?px) (py ?py)))
  =>
  (assert (candidate (bx ?bx) (by ?by) (px ?px) (py ?py))))

; A breeze with a single candidate proves that candidate is a pit. The
; negated conjunction keeps the activation fresh when a candidate is retracted;
; the count is read at firing time so a stale unique match cannot confirm early.
(defrule HYPO::confirm-pit
  (declare (salience 300))
  (breeze-at (x ?bx) (y ?by))
  (candidate (bx ?bx) (by ?by) (px ?px) (py ?py))
  (not (pit (x ?px) (y ?py)))
  (not (and (candidate (bx ?bx) (by ?by) (px ?ox) (py ?oy))
            (test (or (neq ?ox ?px) (neq ?oy ?py)))))
  =>
  (if (= (candidate-count ?bx ?by) 1)
     then
     (assert (pit (x ?px) (y ?py)))))

; A confirmed pit always carries full certainty.
(defrule HYPO::raise-confirmed-pit
  (declare (salience 280))
  ?hypothesis <- (pit-hypothesis (x ?x) (y ?y) (cf ?cf))
  (pit (x ?x) (y ?y))
  (test (< ?cf 1.0))
  =>
  (modify ?hypothesis (cf 1.0)))

; A confirmed pit without prior evidence still gets one full-certainty fact.
; An excluded target is not a pit hypothesis, even if contradictory pit facts
; remain in working memory.
(defrule HYPO::assert-confirmed-pit-hypothesis
  (declare (salience 270))
  (pit (x ?x) (y ?y))
  (not (no-pit (x ?x) (y ?y)))
  (not (pit-hypothesis (x ?x) (y ?y)))
  =>
  (assert (pit-hypothesis (x ?x) (y ?y) (cf 1.0)
                          (source-x -1) (source-y -1))))

; Each breeze contributes one piece of evidence per surviving candidate.
; The source slots keep otherwise identical facts distinct; evidence-seen stops
; the same breeze from contributing again on a later cycle.
(defrule HYPO::pit-hypothesis-evidence
  (declare (salience 260))
  (candidate (bx ?bx) (by ?by) (px ?px) (py ?py))
  (config (evidence ?evidence))
  (not (pit (x ?px) (y ?py)))
  (not (evidence-seen (source-x ?bx) (source-y ?by)
                      (x ?px) (y ?py)))
  =>
  (assert (evidence-seen (source-x ?bx) (source-y ?by)
                         (x ?px) (y ?py)))
  (assert (pit-hypothesis (x ?px) (y ?py) (cf ?evidence)
                          (source-x ?bx) (source-y ?by))))

; Combine all positive evidence about the same target. The MYCIN formula is
; commutative and associative, so the final value does not depend on pair order.
(defrule HYPO::combine-pit-hypotheses
  (declare (salience 240))
  ?first <- (pit-hypothesis (x ?x) (y ?y) (cf ?cf1))
  ?second <- (pit-hypothesis (x ?x) (y ?y) (cf ?cf2))
  (test (neq ?first ?second))
  =>
  (retract ?first)
  (modify ?second (cf (combine-cf-positive ?cf1 ?cf2))))



; ---------------------------------------------------------------------------
; DECIDE: goal selection and distance fields
; ---------------------------------------------------------------------------

; Open a fresh planning workspace once per bridge step. Retracting the previous
; cycle's transient facts removes stale goals, paths, and rankings before any
; rule can read them.
(defrule DECIDE::clear-plan
  (declare (salience 1000))
  ?plan <- (plan (step ?old))
  (counter (step ?step))
  (test (neq ?old ?step))
  =>
  (clear-plan-facts)
  (modify ?plan (step ?step)))

; ---------------------------------------------------------------------------
; DECIDE: persistent home field over the visited graph
; ---------------------------------------------------------------------------

; The assumed exit anchors the home field. The field persists across cycles and
; only relaxes downward as the visited graph grows.
(defrule DECIDE::seed-home-root
  (declare (salience 980))
  (not (home (x 0) (y 0) (d ?)))
  =>
  (assert (home (x 0) (y 0) (d 0))))

; Expand home through links whose source and target were both visited. A
; frontier is a leaf: it receives a distance but never propagates one.
(defrule DECIDE::home-expand
  (declare (salience 960))
  (home (x ?x) (y ?y) (d ?d))
  (visited (x ?x) (y ?y))
  (nbr (x ?x) (y ?y) (nx ?nx) (ny ?ny))
  (visited (x ?nx) (y ?ny))
  (not (home (x ?nx) (y ?ny) (d ?)))
  =>
  (assert (home (x ?nx) (y ?ny) (d (+ ?d 1)))))

; A shorter route to an existing home distance always wins.
(defrule DECIDE::home-relax
  (declare (salience 960))
  ?old <- (home (x ?x) (y ?y) (d ?old-d))
  (home (x ?px) (y ?py) (d ?pd))
  (visited (x ?px) (y ?py))
  (nbr (x ?px) (y ?py) (nx ?x) (ny ?y))
  (test (< (+ ?pd 1) ?old-d))
  =>
  (modify ?old (d (+ ?pd 1))))

; Give each frontier a return distance through its visited neighbours without
; ever routing the field through unvisited cells.
(defrule DECIDE::home-extend-frontier
  (declare (salience 950))
  (home (x ?x) (y ?y) (d ?d))
  (visited (x ?x) (y ?y))
  (nbr (x ?x) (y ?y) (nx ?fx) (ny ?fy))
  (frontier (x ?fx) (y ?fy))
  (not (home (x ?fx) (y ?fy) (d ?)))
  =>
  (assert (home (x ?fx) (y ?fy) (d (+ ?d 1)))))

; ---------------------------------------------------------------------------
; DECIDE: current-position distance field
; ---------------------------------------------------------------------------

(defrule DECIDE::seed-dist
  (declare (salience 940))
  (pos (x ?x) (y ?y))
  (not (dist (x ?x) (y ?y) (d ?)))
  =>
  (assert (dist (x ?x) (y ?y) (d 0))))

(defrule DECIDE::dist-expand
  (declare (salience 930))
  (dist (x ?x) (y ?y) (d ?d))
  (visited (x ?x) (y ?y))
  (nbr (x ?x) (y ?y) (nx ?nx) (ny ?ny))
  (visited (x ?nx) (y ?ny))
  (not (dist (x ?nx) (y ?ny) (d ?)))
  =>
  (assert (dist (x ?nx) (y ?ny) (d (+ ?d 1)))))

(defrule DECIDE::dist-relax
  (declare (salience 930))
  ?old <- (dist (x ?x) (y ?y) (d ?old-d))
  (dist (x ?px) (y ?py) (d ?pd))
  (visited (x ?px) (y ?py))
  (nbr (x ?px) (y ?py) (nx ?x) (ny ?y))
  (test (< (+ ?pd 1) ?old-d))
  =>
  (modify ?old (d (+ ?pd 1))))

(defrule DECIDE::dist-extend-frontier
  (declare (salience 920))
  (dist (x ?x) (y ?y) (d ?d))
  (visited (x ?x) (y ?y))
  (nbr (x ?x) (y ?y) (nx ?fx) (ny ?fy))
  (frontier (x ?fx) (y ?fy))
  (not (dist (x ?fx) (y ?fy) (d ?)))
  =>
  (assert (dist (x ?fx) (y ?fy) (d (+ ?d 1)))))

; ---------------------------------------------------------------------------
; DECIDE: energy budget, goal, and route
; ---------------------------------------------------------------------------

; The reserve is no longer enough for a comfortable return.
(defrule DECIDE::derive-low-energy
  (declare (salience 900))
  (pos (x ?x) (y ?y))
  (home (x ?x) (y ?y) (d ?h))
  (percept (energy ?e))
  (config (reserve ?r))
  (test (<= ?e (+ ?h ?r)))
  (not (low-energy))
  =>
  (assert (low-energy)))

; A frontier is affordable only when reaching it, returning home, taking the
; final quit step, and keeping the reserve all fit in the current energy.
(defrule DECIDE::seed-best-frontier
  (declare (salience 870))
  (not (best-frontier (x ?) (y ?) (d ?)))
  (frontier (x ?x) (y ?y))
  (dist (x ?x) (y ?y) (d ?d))
  (home (x ?x) (y ?y) (d ?h))
  (config (reserve ?r))
  (percept (energy ?e))
  (test (<= (+ ?d ?h 1 ?r) ?e))
  =>
  (assert (best-frontier (x ?x) (y ?y) (d ?d))))

; Rank candidates by distance, then by the lower row, then by the lower column.
; The strict comparison cannot oscillate because it never rewrites an equal key.
(defrule DECIDE::improve-best-frontier
  (declare (salience 860))
  ?best <- (best-frontier (x ?bx) (y ?by) (d ?bd))
  (frontier (x ?x) (y ?y))
  (dist (x ?x) (y ?y) (d ?d))
  (home (x ?x) (y ?y) (d ?h))
  (config (reserve ?r))
  (percept (energy ?e))
  (test (<= (+ ?d ?h 1 ?r) ?e))
  (test (or (< ?d ?bd)
            (and (= ?d ?bd) (< ?y ?by))
            (and (= ?d ?bd) (= ?y ?by) (< ?x ?bx))))
  =>
  (modify ?best (x ?x) (y ?y) (d ?d)))

; Grab only when the return path, the grab, the final quit, and the reserve all
; remain affordable; otherwise survival wins.
(defrule DECIDE::goal-grab
  (declare (salience 820))
  (percept (x ?x) (y ?y) (glitter TRUE) (energy ?e))
  (pos (x ?x) (y ?y))
  (home (x ?x) (y ?y) (d ?h))
  (config (reserve ?r))
  (not (has-gold))
  (test (>= ?e (+ ?h ?r 2)))
  (not (goal (kind ?) (x ?) (y ?)))
  =>
  (assert (goal (kind grab) (x ?x) (y ?y))))

(defrule DECIDE::goal-quit-with-gold
  (declare (salience 810))
  (pos (x 0) (y 0))
  (has-gold)
  (not (goal (kind ?) (x ?) (y ?)))
  =>
  (assert (goal (kind quit) (x 0) (y 0))))

(defrule DECIDE::goal-quit-low-energy
  (declare (salience 805))
  (pos (x 0) (y 0))
  (low-energy)
  (not (goal (kind ?) (x ?) (y ?)))
  =>
  (assert (goal (kind quit) (x 0) (y 0))))

(defrule DECIDE::goal-quit-no-frontier
  (declare (salience 800))
  (pos (x 0) (y 0))
  (not (best-frontier (x ?) (y ?) (d ?)))
  (not (goal (kind ?) (x ?) (y ?)))
  =>
  (assert (goal (kind quit) (x 0) (y 0))))

(defrule DECIDE::goal-exit-with-gold
  (declare (salience 790))
  (pos (x ?x) (y ?y))
  (test (or (neq ?x 0) (neq ?y 0)))
  (has-gold)
  (not (goal (kind ?) (x ?) (y ?)))
  =>
  (assert (goal (kind exit) (x 0) (y 0))))

(defrule DECIDE::goal-exit-low-energy
  (declare (salience 785))
  (pos (x ?x) (y ?y))
  (test (or (neq ?x 0) (neq ?y 0)))
  (low-energy)
  (not (goal (kind ?) (x ?) (y ?)))
  =>
  (assert (goal (kind exit) (x 0) (y 0))))

(defrule DECIDE::goal-exit-no-frontier
  (declare (salience 780))
  (pos (x ?x) (y ?y))
  (test (or (neq ?x 0) (neq ?y 0)))
  (not (best-frontier (x ?) (y ?) (d ?)))
  (not (goal (kind ?) (x ?) (y ?)))
  =>
  (assert (goal (kind exit) (x 0) (y 0))))

(defrule DECIDE::goal-frontier
  (declare (salience 770))
  (best-frontier (x ?x) (y ?y) (d ?))
  (not (goal (kind ?) (x ?) (y ?)))
  =>
  (assert (goal (kind frontier) (x ?x) (y ?y))))

; Seed the navigation field at the chosen goal. The exit is visited, so the
; ordinary expansion rules can carry its field; a frontier is entered from the
; visited neighbours that the link graph already exposes.
(defrule DECIDE::nav-seed-exit
  (declare (salience 740))
  (goal (kind exit))
  (not (nav (x 0) (y 0) (d ?)))
  =>
  (assert (nav (x 0) (y 0) (d 0))))

(defrule DECIDE::nav-seed-frontier
  (declare (salience 740))
  (goal (kind frontier) (x ?gx) (y ?gy))
  (not (nav (x ?gx) (y ?gy) (d ?)))
  =>
  (assert (nav (x ?gx) (y ?gy) (d 0))))

(defrule DECIDE::nav-seed-frontier-neighbour
  (declare (salience 730))
  (goal (kind frontier) (x ?gx) (y ?gy))
  (nbr (x ?nx) (y ?ny) (nx ?gx) (ny ?gy))
  (visited (x ?nx) (y ?ny))
  (not (nav (x ?nx) (y ?ny) (d ?)))
  =>
  (assert (nav (x ?nx) (y ?ny) (d 1))))

(defrule DECIDE::nav-expand
  (declare (salience 720))
  (nav (x ?x) (y ?y) (d ?d))
  (visited (x ?x) (y ?y))
  (nbr (x ?x) (y ?y) (nx ?nx) (ny ?ny))
  (visited (x ?nx) (y ?ny))
  (not (nav (x ?nx) (y ?ny) (d ?)))
  =>
  (assert (nav (x ?nx) (y ?ny) (d (+ ?d 1)))))

(defrule DECIDE::nav-relax
  (declare (salience 720))
  ?old <- (nav (x ?x) (y ?y) (d ?old-d))
  (nav (x ?px) (y ?py) (d ?pd))
  (visited (x ?px) (y ?py))
  (nbr (x ?px) (y ?py) (nx ?x) (ny ?y))
  (test (< (+ ?pd 1) ?old-d))
  =>
  (modify ?old (d (+ ?pd 1))))

; A neighbour one navigation step closer to the goal is a valid next hop.
(defrule DECIDE::next-hop
  (declare (salience 700))
  (pos (x ?x) (y ?y))
  (nav (x ?x) (y ?y) (d ?d))
  (nbr (x ?x) (y ?y) (nx ?nx) (ny ?ny) (dir ?dir) (rank ?rank))
  (nav (x ?nx) (y ?ny) (d ?nd))
  (test (= ?nd (- ?d 1)))
  (not (next (dir ?dir) (rank ?rank)))
  =>
  (assert (next (dir ?dir) (rank ?rank))))

; If the frontier route produced no hop, abandon exploration for survival and
; rebuild the plan toward the exit.
(defrule DECIDE::fallback-frontier-to-exit
  (declare (salience 690))
  ?goal <- (goal (kind frontier) (x ?gx) (y ?gy))
  (not (next (dir ?dir) (rank ?rank)))
  =>
  (clear-nav-facts)
  (retract ?goal)
  (assert (goal (kind exit) (x 0) (y 0))))


; ---------------------------------------------------------------------------
; ACT: exactly one action per cycle
; ---------------------------------------------------------------------------

; Record the intended movement so MAP can distinguish a step from a bump.
(defrule ACT::record-move-intent
  (action (move ?dir))
  (pos (x ?x) (y ?y))
  (delta (dir ?dir) (dx ?dx) (dy ?dy))
  (not (last-move (move ?dir) (from-x ?x) (from-y ?y)))
  =>
  (assert (last-move (move ?dir) (from-x ?x) (from-y ?y))))

; Collect the gold only when DECIDE selected the grab goal for a glittering
; cell and the agent does not already hold it.
(defrule ACT::act-grab
  (declare (salience 500))
  (goal (kind grab) (x ?x) (y ?y))
  (percept (x ?x) (y ?y) (glitter TRUE))
  (not (has-gold))
  (not (action (move ?)))
  =>
  (assert (action (move grab)))
  (assert (has-gold)))

; Quit only from the exit; the plan never selects quit elsewhere.
(defrule ACT::act-quit
  (declare (salience 480))
  (goal (kind quit))
  (pos (x 0) (y 0))
  (not (action (move ?)))
  =>
  (assert (action (move quit))))

; Follow the best-ranked hop toward a frontier or the exit.
(defrule ACT::act-move
  (declare (salience 460))
  (goal (kind ?kind))
  (test (or (eq ?kind frontier) (eq ?kind exit)))
  (next (dir ?dir) (rank ?rank))
  (not (and (next (dir ?) (rank ?other-rank))
            (test (< ?other-rank ?rank))))
  (not (action (move ?)))
  =>
  (assert (action (move ?dir))))

; Safety net for the one-action protocol: if planning produced no action, stay
; alive at the exit or hold position. It never overrides a goal-driven action.
(defrule ACT::last-resort
  (declare (salience 10))
  (pos (x ?x) (y ?y))
  (not (action (move ?)))
  =>
  (if (and (= ?x 0) (= ?y 0))
     then
     (assert (action (move quit)))
     else
     (assert (action (move grab)))))
