# SPDX-License-Identifier: MIT

import subprocess

import pytest

from harness import keyboard_layout
from harness.display import HeadlessDisplay
from harness.environment import process_environment
from harness.keyboard_layout import PINYIN, RUSSIAN, Layout, LayoutError, switched
from harness.xtest import LOCK_MASK, KeyboardState, XTestConnection, XTestError


class FakeXkb:
    def __init__(self, accepted, status):
        self.accepted = accepted
        self.status = status

    def XkbLockGroup(self, _display, _device, _group):
        return self.accepted

    def XkbLockModifiers(self, _display, _device, _affect, _values):
        return self.accepted

    def XkbGetState(self, _display, _device, _state):
        return self.status


def connection_for(x11):
    connection = object.__new__(XTestConnection)
    connection._display = 1
    connection._x11 = x11
    return connection


@pytest.mark.parametrize(
    "send",
    [
        lambda connection: connection.lock_group(1),
        lambda connection: connection.lock_modifiers(LOCK_MASK, LOCK_MASK),
        lambda connection: connection.keyboard_state(),
    ],
    ids=["group", "modifiers", "state"],
)
def test_refused_keyboard_requests_fail_loudly(send):
    with pytest.raises(XTestError):
        send(connection_for(FakeXkb(accepted=False, status=1)))


class RecordingKeyboard:
    display_name = ":1999"

    def __init__(self, events, state):
        self.events = events
        self.state = state

    def lock_group(self, group):
        self.events.append(("lock group", group))

    def lock_modifiers(self, affect, values):
        self.events.append(("lock modifiers", affect, values))

    def keyboard_state(self):
        return self.state


def record_setxkbmap(monkeypatch, events, query="layout:     us\n"):
    def run(command, **options):
        assert command[:3] == ["setxkbmap", "-display", ":1999"]
        assert options["env"] == process_environment()
        events.append(tuple(command[3:]))
        output = "rules:      evdev\nmodel:      pc105\n" + query
        return subprocess.CompletedProcess(command, 0, output if command[3] == "-query" else "", "")

    monkeypatch.setattr(keyboard_layout.subprocess, "run", run)


@pytest.mark.parametrize(
    "layout, selected",
    [
        (RUSSIAN, [("-layout", "us,ru"), ("lock group", 1)]),
        (PINYIN, [("-layout", "cn", "-variant", "altgr-pinyin"), ("lock group", 0)]),
    ],
    ids=["layouts", "variant"],
)
def test_switches_run_only_against_the_connected_display_and_restore_after_a_failure(
    monkeypatch, layout, selected
):
    events = []
    record_setxkbmap(monkeypatch, events)
    keyboard = RecordingKeyboard(events, KeyboardState(0, 0, 0))
    with pytest.raises(RuntimeError, match="scenario failed"):
        with switched(keyboard, layout):
            events.append("scenario")
            raise RuntimeError("scenario failed")
    assert events[: events.index("scenario")] == selected
    assert ("-layout", "us") in events[events.index("scenario"):]


@pytest.mark.parametrize(
    "state, query",
    [
        (KeyboardState(1, 1, 0), "layout:     us\n"),
        (KeyboardState(0, 0, 0), "layout:     us\nvariant:    altgr-pinyin\n"),
    ],
    ids=["group", "variant"],
)
def test_a_keyboard_left_in_another_layout_fails_the_scenario(monkeypatch, state, query):
    events = []
    record_setxkbmap(monkeypatch, events, query)
    keyboard = RecordingKeyboard(events, state)
    with pytest.raises(LayoutError, match="not restored"):
        with switched(keyboard, PINYIN):
            pass


@pytest.mark.parametrize(
    "layout, query, state",
    [
        (
            Layout("ru-caps", "us,ru", group=1, caps_lock=True),
            {"layout": "us,ru"},
            KeyboardState(1, 1, LOCK_MASK),
        ),
        (PINYIN, {"layout": "cn", "variant": "altgr-pinyin"}, KeyboardState(0, 0, 0)),
    ],
    ids=["ru-caps", "variant"],
)
def test_a_live_switch_on_a_private_display_restores_the_us_keyboard(layout, query, state):
    display = HeadlessDisplay()
    try:
        display.start()
        connection = XTestConnection(display.display)
        try:
            with pytest.raises(RuntimeError, match="scenario failed"):
                with switched(connection, layout):
                    loaded = keyboard_layout._query(connection)
                    assert {key: loaded.get(key) for key in query} == query
                    assert connection.keyboard_state() == state
                    raise RuntimeError("scenario failed")
            restored = keyboard_layout._query(connection)
            assert restored["layout"] == "us" and "variant" not in restored
            assert connection.keyboard_state() == KeyboardState(0, 0, 0)
        finally:
            connection.close()
    finally:
        display.stop()
