"""Tests for GUI handling of CLIPS protocol errors without a display."""

import pytest

pytest.importorskip("tkinter")

from gui import WumpusWorldGUI
from wumpus import ProtocolError, WumpusWorld


class RecordingLabel:
    def __init__(self):
        self.options = {}

    def config(self, **options):
        self.options.update(options)

    @property
    def text(self):
        return self.options.get("text", "")


class RecordingRoot:
    def __init__(self):
        self.after_calls = []

    def after(self, delay, callback):
        self.after_calls.append((delay, callback))


class BrokenAgent:
    def run_and_get_action(self):
        raise ProtocolError("Expected exactly one action fact per cycle, found 0")


def make_gui(agent):
    gui = object.__new__(WumpusWorldGUI)
    gui.world = WumpusWorld(width=2, height=1)
    gui.agent = agent
    gui.status = RecordingLabel()
    gui.root = RecordingRoot()
    gui.iterate = True
    gui.refresh = lambda *args: None
    return gui


def test_step_reports_protocol_error_without_stepping():
    gui = make_gui(BrokenAgent())

    gui.step()

    assert gui.iterate is False
    assert "Protocol error" in gui.status.text
    assert (gui.world.x, gui.world.y) == (0, 0)
    assert gui.world.steps == 0


def test_run_loop_stops_after_protocol_error():
    gui = make_gui(BrokenAgent())

    gui._run_loop()

    assert gui.iterate is False
    assert gui.root.after_calls == []
    assert "Protocol error" in gui.status.text


def test_run_loop_catches_protocol_error_raised_by_step():
    gui = make_gui(BrokenAgent())

    def broken_step():
        raise ProtocolError("malformed action")

    gui.step = broken_step

    gui._run_loop()

    assert gui.iterate is False
    assert gui.root.after_calls == []
    assert "malformed action" in gui.status.text
