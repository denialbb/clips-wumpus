from __future__ import annotations




import argparse
import sys
import time

from tkinter import*
import tkinter as tk
from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple, List

import json


import clips  # pip install clipspy


Action = str  # "up" | "down" | "left" | "right" | "grab" | "quit" | "pit-north" | "pit-south" | "pit-west" | "pit-east"


@dataclass(frozen=True)
class StepResult:
    obs: Dict[str, object]
    reward: float
    done: bool


class WumpusWorld:

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
        self.start = start
        self.walls = walls or set()
        self.pits = pits or set()
        self.wumpus = wumpus
        self.gold = gold
        self.original_gold = gold  # For reset

        self.max_steps = max_steps
        self.energy = max_steps
        self.reward = 0.0
        self.step_cost = step_cost
        self.death_cost = death_cost
        self.grab_reward = grab_reward
        self.end_on_grab = end_on_grab
        self.done = False

        # Sanity checks
        if start in self.walls:
            raise ValueError("Start cannot be inside a wall.")
        if start in self.pits:
            raise ValueError("Start cannot be a pit.")
        if wumpus == start:
            raise ValueError("Start cannot contain wumpus.")
        if gold == start:
            pass

        for obj in self.pits | self.walls:
            if obj == self.wumpus or obj == self.gold:
                raise ValueError("Cannot overlap walls/pits with wumpus/gold.")

        self.x, self.y = start
        self.steps = 0
        self.dead = False
        self.has_gold = False

    @classmethod
    def from_json(cls, path: str | Path) -> "WumpusWorld":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        def to_tuple(v):
            return tuple(v) if v is not None else None

        def to_tuple_set(values):
            return {tuple(v) for v in values} if values else set()

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
        self.gold = self.original_gold  # Reset
        return self._obs()

    def _in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def _is_blocked(self, x: int, y: int) -> bool:
        return (x, y) in self.walls

    def _neighbors_4(self, x: int, y: int) -> Set[Tuple[int, int]]:
        candidates = {(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)}
        return {(nx, ny) for (nx, ny) in candidates if self._in_bounds(nx, ny)}

    def _percepts(self, x: int, y: int) -> Dict[str, bool]:
        nbrs = self._neighbors_4(x, y)
        breeze = any(n in self.pits for n in nbrs)
        stench = self.wumpus in nbrs if self.wumpus else False
        glitter =  (self.gold == (x, y)) #(not self.has_gold) and
        return {"breeze": breeze, "stench": stench, "glitter": glitter}

    def _obs(self) -> Dict[str, object]:
        p = self._percepts(self.x, self.y)
        return {
            "x": self.x,
            "y": self.y,
            "steps": self.steps,
            "breeze": p["breeze"],
            "stench": p["stench"],
            "glitter": p["glitter"],
            "energy": self.energy
            }

    def _is_death_cell(self, x: int, y: int) -> bool:
        return (x, y) in self.pits or (self.wumpus == (x, y))

    def step(self, action: Action) -> StepResult:

        self.steps += 1
        self.energy -= 1

        if action == "grab":
            if self.gold == (self.x, self.y) and not self.has_gold:
                self.has_gold = True
                self.gold = None
                self.reward += self.grab_reward
                return StepResult(self._obs(), self.reward, self.end_on_grab)
            return StepResult(self._obs(), self.step_cost, False)

        dx, dy = 0, 0
        if action == "up":
            dy = -1
        elif action == "down":
            dy = 1
        elif action == "left":
            dx = -1
        elif action == "right":
            dx = 1

        nx, ny = self.x + dx, self.y + dy

        if self._in_bounds(nx, ny) and not self._is_blocked(nx, ny):
            self.x, self.y = nx, ny
        else:
            # Bump into wall, stay in place
            self.energy -= 1  # Extra penalty for hitting wall

        if self._is_death_cell(self.x, self.y):
            self.dead = True
            self.energy = 0
            self.done = True
            self.reward += self.death_cost
            return StepResult(self._obs(), self.reward, self.done)
        
        if action == "quit":
            self.done = True
            return StepResult(self._obs(), self.reward, self.done)
        
        guess_pit = False
        if action == "pit-north":
            dy = -1
            guess_pit = True
        elif action == "pit-south":
            dy = 1
            guess_pit = True
        elif action == "pit-west":
            dx = -1
            guess_pit = True
        elif action == "pit-east":
            dx = 1
            guess_pit = True

        if guess_pit:    
            nx, ny = self.x + dx, self.y + dy

            if (nx, ny) in self.pits:
                    self.reward+= 25 
            else:
                    self.reward-=25

        
        done = self.energy <= 0
        self.done = done
        if self.dead or self.done:
            self.reward += self.death_cost

        return StepResult(self._obs(), self.step_cost, done)


# ------------------ CLIPS BRIDGE ------------------

def build_many(env: clips.Environment, program: str):
    buf, depth = [], 0
    for ch in program:
        buf.append(ch)
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                env.build("".join(buf).strip())
                buf.clear()


def clips_bool(v: bool) -> str:
    return "TRUE" if v else "FALSE"


class ClipsAgent:
    def __init__(self, program: str):
        self.env = clips.Environment()
        self.env.load(program)
        self.env.reset()

    def reset(self):
        self.env.reset()

    def clear_action_facts(self):
        for f in list(self.env.facts()):
            if f.template.name == "action":
                f.retract()

    def assert_percept(self, obs):
        fact = (
           f'(percept (x {obs["x"]}) (y {obs["y"]}) '
#           f'(gx {obs.get("gx", 0)}) (gy {obs.get("gy", 0)}) '  # Add gold coords if available
#           f'(w {obs["w"]}) (h {obs["h"]}) (steps {obs["steps"]}) '
           f'(steps {obs["steps"]}) '
           f'(breeze {clips_bool(obs["breeze"])}) '
           f'(stench {clips_bool(obs["stench"])}) '
           f'(glitter {clips_bool(obs["glitter"])}) ' 
           f'(energy {obs["energy"]}))'
        )
        self.env.assert_string(fact)
        
    def update_time_counter(self, obs):
        for f in self.env.facts():
           if f.template.name == "counter":
               self.env.eval(f"(modify {f.index} (step {obs["steps"]}))")

    def agenda_snapshot(self):
        return [str(a) for a in self.env.activations()]

    def run_and_get_action(self):
        self.env.run()
        for f in self.env.facts():
            if f.template.name == "action":
                return str(f["move"])
        return "right" # Default action if none provided 


# ------------------ GUI ------------------

class WumpusWorldGUI:
    def __init__(self, world: WumpusWorld, agent: ClipsAgent):
        self.world = world
        self.agent = agent

        self.root = tk.Tk()
        self.root.title("Wumpus World with Walls")

        self.cell = 60
        self.pad = 10

        w = world.width * self.cell + 2 * self.pad
        h = world.height * self.cell + 2 * self.pad

        self.canvas = tk.Canvas(self.root, width=w, height=h, bg="white")
        self.canvas.pack(side="left")

        self.side = tk.Frame(self.root)
        self.side.pack(side="right", fill="y")


        tk.Label(self.side, text="Facts").pack()
        self.facts = tk.Listbox(self.side, height=15, width=45)
        self.facts.pack()

        tk.Label(self.side, text="Agenda").pack()
        self.agenda = tk.Listbox(self.side, height=10, width=45)
        self.agenda.pack()


        self.energy = tk.Label(self.side, text=f"Agent's Energy = {self.world.energy}", font=("Arial", 10, "bold")) 
        self.energy.pack(pady=10)
        self.reward = tk.Label(self.side, text=f"Agent's Reward = {self.world.reward}", font=("Arial", 10, "bold")) 
        self.reward.pack(pady=10)        

        self.btn_step = tk.Button(self.side, text="Step", command=self.step)
        self.btn_step.pack(fill="x")

        self.btn_run = tk.Button(self.side, text="Run", command=self.run_clips)
        self.btn_run.pack(fill="x")

        self.btn_stop = tk.Button(self.side, text="Stop", command=self.stop_clips)
        self.btn_stop.pack(fill="x")        

        self.btn_reset = tk.Button(self.side, text="Reset", command=self.reset)
        self.btn_reset.pack(fill="x")

        self.obs = self.world.reset()
        self.draw()
        self.refresh()

    def cell_box(self, x, y):
        x0 = self.pad + x * self.cell
        y0 = self.pad + y * self.cell
        return x0, y0, x0 + self.cell, y0 + self.cell

    def draw(self):
        self.canvas.delete("all")

        for y in range(self.world.height):
            for x in range(self.world.width):
                self.canvas.create_rectangle(*self.cell_box(x, y), outline="gray")

        # Walls
        for x, y in self.world.walls:
            self.canvas.create_rectangle(*self.cell_box(x, y), fill="black")

        # Pits
        for x, y in self.world.pits:
            self.canvas.create_text(*self._center(x, y), text="P", fill="black", font=("Arial", 16, "bold"))

        # Wumpus
        if self.world.wumpus:
            self.canvas.create_text(*self._center(*self.world.wumpus), text="W", fill="red", font=("Arial", 16, "bold"))

        # Gold
        if self.world.gold and not self.world.has_gold:
            self.canvas.create_text(*self._center(*self.world.gold), text="$", fill="gold", font=("Arial", 18, "bold"))
            
        self.img = tk.PhotoImage(file = 'exit.gif')
        self.img = self.img.subsample(20, 20)   #create a new image half as large as the original
        self.canvas.create_image(*self._center(0,0),image=self.img,anchor='c')             

        # Agent
        self.canvas.create_text(*self._center(self.world.x, self.world.y), text="A", fill="blue", font=("Arial", 18, "bold"))

    def _center(self, x, y):
        x0, y0, x1, y1 = self.cell_box(x, y)
        return (x0 + x1) // 2, (y0 + y1) // 2

    def refresh(self, agenda_snapshot=None):
        self.facts.delete(0, tk.END)
        for f in self.agent.env.facts():
            self.facts.insert(tk.END, str(f))

        self.agenda.delete(0, tk.END)
        acts = agenda_snapshot if agenda_snapshot else []
        for a in acts:
            self.agenda.insert(tk.END, a)

    def run_clips(self):
        self.iterate = True
        self._run_loop()

    def _run_loop(self):
        if not self.iterate or self.world.done:
            self.iterate = False
            return

        self.step()

        # schedule next iteration (500 ms)
        self.root.after(200, self._run_loop)

    def stop_clips(self):
        self.iterate = False

    def step(self):
        self.refresh([])

        action = self.agent.run_and_get_action()
        result = self.world.step(action)

        self.obs = result.obs
       

        self.agent.clear_action_facts()
        self.agent.assert_percept(self.obs)
        self.agent.update_time_counter(self.obs)

        agenda_before = self.agent.agenda_snapshot()
        self.refresh(agenda_before)

        self.energy.config(text=f"Agent's Energy = {self.world.energy}")
        self.reward.config(text=f"Agent's Reward = {self.world.reward}")

        self.draw()


    def reset(self):
        self.obs = self.world.reset()
        self.agent.reset()
        self.agent.assert_percept(self.obs)
        self.energy.config(text=f"Agent's Energy = {self.world.energy}")
        self.reward.config(text=f"Agent's Reward = {self.world.reward}")
        self.draw()
        self.refresh([])

    def run(self):
        self.root.mainloop()


# ------------------ MAIN ------------------



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
    except Exception as e:
        print(f"Error loading map: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        agent = ClipsAgent(args.agent_file)
    except Exception as e:
        print(f"Error loading CLIPS agent: {e}", file=sys.stderr)
        sys.exit(1)

    gui = WumpusWorldGUI(world, agent)
    gui.run()




if __name__ == "__main__":
    main()
