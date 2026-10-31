"""Tkinter front end for the Wumpus World simulator.

The module is imported lazily by ``wumpus.main`` so the simulator and the
headless harness keep working on systems without Tk.
"""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wumpus import ClipsAgent, WumpusWorld


class WumpusWorldGUI:
    def __init__(self, world: WumpusWorld, agent: ClipsAgent):
        self.world = world
        self.agent = agent

        self.root = tk.Tk()
        self.root.title("Wumpus World with Walls")

        self.cell = 60
        self.pad = 10

        width = world.width * self.cell + 2 * self.pad
        height = world.height * self.cell + 2 * self.pad

        self.canvas = tk.Canvas(self.root, width=width, height=height, bg="white")
        self.canvas.pack(side="left")

        self.side = tk.Frame(self.root)
        self.side.pack(side="right", fill="y")

        tk.Label(self.side, text="Facts").pack()
        self.facts = tk.Listbox(self.side, height=15, width=45)
        self.facts.pack()

        tk.Label(self.side, text="Agenda").pack()
        self.agenda = tk.Listbox(self.side, height=10, width=45)
        self.agenda.pack()

        self.energy = tk.Label(
            self.side,
            text=f"Agent's Energy = {self.world.energy}",
            font=("Arial", 10, "bold"),
        )
        self.energy.pack(pady=10)
        self.reward = tk.Label(
            self.side,
            text=f"Agent's Reward = {self.world.reward}",
            font=("Arial", 10, "bold"),
        )
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
        self.agent.reset(self.obs)
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

        for x, y in self.world.walls:
            self.canvas.create_rectangle(*self.cell_box(x, y), fill="black")

        for x, y in self.world.pits:
            self.canvas.create_text(
                *self._center(x, y),
                text="P",
                fill="black",
                font=("Arial", 16, "bold"),
            )

        if self.world.wumpus:
            self.canvas.create_text(
                *self._center(*self.world.wumpus),
                text="W",
                fill="red",
                font=("Arial", 16, "bold"),
            )

        if self.world.gold and not self.world.has_gold:
            self.canvas.create_text(
                *self._center(*self.world.gold),
                text="$",
                fill="gold",
                font=("Arial", 18, "bold"),
            )

        exit_image = str(Path(__file__).with_name("exit.gif"))
        self.img = tk.PhotoImage(file=exit_image)
        self.img = self.img.subsample(20, 20)
        self.canvas.create_image(*self._center(0, 0), image=self.img, anchor="c")

        self.canvas.create_text(
            *self._center(self.world.x, self.world.y),
            text="A",
            fill="blue",
            font=("Arial", 18, "bold"),
        )

    def _center(self, x, y):
        x0, y0, x1, y1 = self.cell_box(x, y)
        return (x0 + x1) // 2, (y0 + y1) // 2

    def refresh(self, agenda_snapshot=None):
        self.facts.delete(0, tk.END)
        for fact in self.agent.env.facts():
            self.facts.insert(tk.END, str(fact))

        self.agenda.delete(0, tk.END)
        for activation in agenda_snapshot or []:
            self.agenda.insert(tk.END, activation)

    def run_clips(self):
        self.iterate = True
        self._run_loop()

    def _run_loop(self):
        if not self.iterate or self.world.done:
            self.iterate = False
            return

        self.step()
        self.root.after(200, self._run_loop)

    def stop_clips(self):
        self.iterate = False

    def step(self):
        self.refresh([])

        action = self.agent.run_and_get_action()
        result = self.world.step(action)
        self.obs = result.obs

        self.agent.clear_action_facts()
        self.agent.set_percept(self.obs)

        self.refresh(self.agent.agenda_snapshot())
        self.energy.config(text=f"Agent's Energy = {self.world.energy}")
        self.reward.config(text=f"Agent's Reward = {self.world.reward}")
        self.draw()

    def reset(self):
        self.obs = self.world.reset()
        self.agent.reset(self.obs)
        self.energy.config(text=f"Agent's Energy = {self.world.energy}")
        self.reward.config(text=f"Agent's Reward = {self.world.reward}")
        self.draw()
        self.refresh([])

    def run(self):
        self.root.mainloop()
