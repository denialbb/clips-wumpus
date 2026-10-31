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

; A hazard candidate for a source cell; owned by HYPO.
(deftemplate MAIN::candidate
  (slot bx (type INTEGER))
  (slot by (type INTEGER))
  (slot px (type INTEGER))
  (slot py (type INTEGER)))

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
(deffunction MAIN::combine-cf-positive (?a ?b)
  "Combine two positive certainty factors and clamp to [0.0, 1.0]."
  (bind ?cf (+ ?a (* ?b (- 1.0 ?a))))
  (if (> ?cf 1.0) then (bind ?cf 1.0))
  (if (< ?cf 0.0) then (bind ?cf 0.0))
  ?cf)

(deffacts MAIN::initial-state
  (counter (step 0))
  (config (reserve 5) (evidence 0.4) (guess-threshold 0.75)))

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
; the map. They are blocked and cannot hide the Wumpus, but a pit may share a
; wall cell, hence no-pit is never derived here.
(defrule MAP::negative-neighbour-is-outside
  (nbr (nx ?nx) (ny ?ny))
  (test (or (< ?nx 0) (< ?ny 0)))
  (not (blocked (x ?nx) (y ?ny)))
  =>
  (assert (blocked (x ?nx) (y ?ny))))

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

; Record hazard evidence; candidate and CF rules extend this phase later.
(defrule HYPO::record-breeze
  (percept (x ?x) (y ?y) (breeze TRUE))
  (not (breeze-at (x ?x) (y ?y)))
  =>
  (assert (breeze-at (x ?x) (y ?y))))

(defrule HYPO::record-stench
  (percept (x ?x) (y ?y) (stench TRUE))
  (not (stench-at (x ?x) (y ?y)))
  =>
  (assert (stench-at (x ?x) (y ?y))))


; ---------------------------------------------------------------------------
; DECIDE: goal selection and distance fields
; ---------------------------------------------------------------------------

; Seed the home field at the assumed exit. Relaxation is added later.
(defrule DECIDE::seed-home-root
  (not (home (x 0) (y 0) (d ?)))
  =>
  (assert (home (x 0) (y 0) (d 0))))


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

; SCAFFOLD FALLBACK: remove once DECIDE selects a goal-driven action.
; At the exit, quit; anywhere else, stay put and grab.
(defrule ACT::scaffold-quit-at-origin
  (declare (salience 100))
  (pos (x 0) (y 0))
  (not (action (move ?)))
  =>
  (assert (action (move quit))))

; SCAFFOLD FALLBACK: remove once DECIDE selects a goal-driven action.
(defrule ACT::scaffold-grab-elsewhere
  (declare (salience 90))
  (pos (x ?x) (y ?y))
  (test (or (neq ?x 0) (neq ?y 0)))
  (not (action (move ?)))
  =>
  (assert (action (move grab))))
