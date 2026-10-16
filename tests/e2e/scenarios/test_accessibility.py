# SPDX-License-Identifier: MIT
"""Accessibility semantics the rest of the suite — and screen readers — rely on."""

from __future__ import annotations

import time

import pytest

from harness.browser import MENU_RETRY_INTERVAL
from harness.modes import ALL_MODES

ROOT_ENTRIES = ["archive", "documents", "pictures", "readme.md", "todo.txt"]
FOLDERS = {"archive", "documents", "pictures"}


@pytest.mark.parametrize("mode", ALL_MODES)
def test_listing_names_descriptions_and_selection_semantics(pathfm, mode):
    root = pathfm.fixture.root.name
    pane = pathfm.pane(root)
    assert pane.name == root
    assert pane.description == f"{mode} view"

    container = pathfm.entry_container(root)
    assert container is not None
    assert container.name == root
    assert container.description == "Files"

    entries = pathfm.entries(root)
    assert [node.name for node in entries] == ROOT_ENTRIES
    for node in entries:
        expected = "Folder" if node.name in FOLDERS else "File"
        assert node.description == expected, (
            f"{node.name} should be described as a {expected}"
        )
        assert "focusable" in node.states, f"{node.name} should be focusable"

    # Exercise observable selection transitions instead of optional SELECTABLE state exports.
    pathfm.select_entry("todo.txt", directory=root)
    assert "selected" in pathfm.entry("todo.txt", directory=root).states
    others = [node for node in pathfm.entries(root) if node.name != "todo.txt"]
    assert all("selected" not in node.states for node in others)


def test_toolbar_controls_are_named(pathfm):
    for name in (
        "Search (Ctrl+K)",
        "Appearance",
        "Settings",
        "Close window",
        "Toggle sidebar (Ctrl+B)",
    ):
        assert pathfm.window.find(name=name) is not None, f"{name!r} is unnamed"


@pytest.mark.parametrize("mode", ALL_MODES)
def test_focus_order_reaches_the_files_from_the_header(pathfm, mode):
    """Tab from the window's first control reaches the listing, which is one named stop."""

    root = pathfm.fixture.root.name
    pathfm.keyboard.press("Tab")
    seen = []
    for _ in range(40):
        focused = pathfm.focused_node()
        if focused is not None:
            seen.append(f"{focused.role}:{focused.name}")
            if pathfm.focused_name() is not None:
                break
        pathfm.keyboard.press("Tab")
    else:
        raise AssertionError(f"Tab never reached a file entry; visited {seen}")
    assert pathfm.focused_name() in ROOT_ENTRIES
    container = pathfm.entry_container(root)
    assert container is not None
    assert container.name == root
    assert container.description == "Files"
    assert container.find(states={"focused"}) is not None

    pathfm.keyboard.press("Tab")
    pathfm.wait(
        lambda: container.find(states={"focused"}) is None,
        "one Tab to leave the listing",
        timeout=5,
    )
    outside = pathfm.focused_node()
    assert outside is not None and outside.name, f"Tab left for an unnamed stop: {outside}"


def _focus_outside(pathfm, surface):
    node = pathfm.focused_node()
    if node is None or not node.name or node == surface:
        return None
    if any(ancestor == surface for ancestor in node.ancestors()):
        return None
    return node


@pytest.mark.parametrize("entry", ["keyboard", "pointer"])
@pytest.mark.parametrize("mode", ALL_MODES)
def test_empty_directory_keeps_focus_and_tab_order(pathfm, mode, entry):
    pathfm.fixture.path("empty").mkdir()
    pathfm.keyboard.press("F5")
    pathfm.entry("empty")
    if entry == "keyboard":
        pathfm.select_entry_with_keyboard("empty")
        pathfm.keyboard.press("Return")
    elif mode == "Columns":
        pathfm.click_entry("empty")
    else:
        pathfm.double_click_entry("empty")
    pathfm.wait_for_directory("empty")

    surface = pathfm.wait(
        lambda: (node := pathfm.focused_node()) is not None and node.name == "empty" and node,
        "focus on the empty directory's pane surface",
        timeout=5,
    )
    assert surface.description == "This directory is empty"

    pathfm.keyboard.press("Tab")
    pathfm.wait(lambda: _focus_outside(pathfm, surface), "Tab to leave the empty pane", timeout=5)
    pathfm.keyboard.press("shift+Tab")
    pathfm.wait(
        lambda: pathfm.focused_node() == surface,
        "Shift+Tab to return to the empty pane",
        timeout=5,
    )
    pathfm.keyboard.press("shift+Tab")
    pathfm.wait(
        lambda: _focus_outside(pathfm, surface),
        "Shift+Tab to reach the control before the empty pane",
        timeout=5,
    )


@pytest.mark.parametrize(
    ("shortcut", "option", "role", "previous"),
    [
        ("ctrl+2", "Icons", "radio menu item", "Columns"),
        ("ctrl+h", "Hidden files", "check menu item", None),
    ],
)
def test_appearance_options_expose_the_chosen_option(pathfm, shortcut, option, role, previous):
    problems = []

    def check(label, node_role, expected, when):
        node = pathfm.window.find(role=node_role, name=label)
        if node is None:
            problems.append(f"{when}: no {node_role} {label!r} in the Appearance menu")
        elif node.has_state("checked") != expected:
            problems.append(
                f"{when}: {label!r} should {'' if expected else 'not '}be checked; "
                f"states={sorted(node.states)}"
            )
        return node

    pathfm.open_appearance_menu()
    node = check(option, role, False, f"before {shortcut}")
    if option == "Hidden files" and node is not None:
        assert node.description == "Ctrl+H"
    if previous is not None:
        check(previous, role, True, f"before {shortcut}")
    pathfm.keyboard.press("Escape")
    pathfm.wait(
        lambda: pathfm.window.find(role="radio menu item", name="Compact") is None,
        "the Appearance menu to close",
    )

    pathfm.keyboard.press(shortcut)
    if option == "Icons":
        pathfm.wait_for_view("Icons")
    else:
        pathfm.wait(lambda: ".hidden.txt" in pathfm.entry_names(), "hidden files to show")

    pathfm.open_appearance_menu()
    check(option, role, True, f"after {shortcut}")
    if previous is not None:
        check(previous, role, False, f"after {shortcut}")
    assert not problems, "\n".join(problems)


PERMISSION_BITS = [
    ("Owner read", 0o400),
    ("Owner write", 0o200),
    ("Owner execute", 0o100),
    ("Others write", 0o002),
]


def test_permission_bits_expose_their_permission_and_state(pathfm):
    path = pathfm.fixture.path("todo.txt")
    pathfm.select_entry("todo.txt")
    pathfm.keyboard.press("alt+Return")
    dialog = pathfm.wait_for_dialog()

    def bit(name):
        return pathfm.wait(
            lambda: dialog.find(role="toggle button", name=name, states={"sensitive"}),
            f"the {name} bit",
        )

    mode = path.stat().st_mode
    for name, mask in PERMISSION_BITS:
        assert bit(name).has_state("pressed") == bool(mode & mask), (name, oct(mode))

    for expected in (True, False):
        pathfm.pointer.click(bit("Owner execute"))
        pathfm.wait(
            lambda: bool(path.stat().st_mode & 0o100) == expected,
            f"owner execute to be {'set' if expected else 'cleared'} on disk",
        )
        pathfm.wait(
            lambda: bit("Owner execute").has_state("pressed") == expected,
            f"the Owner execute bit to report {'pressed' if expected else 'not pressed'}",
        )


def _open_general_settings(pathfm):
    button = pathfm.window.find(role="button", name="Settings")
    assert button is not None and button.activate()
    pathfm.wait(
        lambda: pathfm.window.find(role="button", name="Modified date format", rendered=False),
        "the General settings page",
    )


def _settings_choice(pathfm, title):
    """The choice button and GTK's inner focusable toggle, which mirrors its name."""

    outer = pathfm.reveal(role="button", name=title)
    return [outer, *outer.find_all(role="toggle button", name=title)]


def _open_choice(pathfm, title, option):
    """Open a choice's popover and return its `option`, retrying a click that a
    late focus or scroll change swallowed."""

    toggle = _settings_choice(pathfm, title)[-1]
    pathfm.pointer.click(toggle)
    clicked = time.monotonic()

    def opened():
        nonlocal clicked
        node = pathfm.window.find(role="radio menu item", name=option)
        if (
            node is None
            and time.monotonic() - clicked > MENU_RETRY_INTERVAL
            and not (toggle.has_state("checked") or toggle.has_state("pressed"))
        ):
            pathfm.pointer.click(toggle)
            clicked = time.monotonic()
        return node

    return pathfm.wait(opened, f"the {option!r} option of {title!r}")


def _choice_value_problems(pathfm, title, value):
    return [
        f"{node.role} {title!r} shows {value!r} but is described as {node.description!r}"
        for node in _settings_choice(pathfm, title)
        if node.description != value
    ]


@pytest.mark.preferences(auto_refresh_interval=120)
def test_settings_choice_buttons_expose_their_current_value(pathfm):
    _open_general_settings(pathfm)
    problems = []
    for title, value in [
        ("Drag & drop to another device", "Always ask"),
        ("Modified date format", "Relative"),
        ("Auto-refresh folder", "5 min"),
        ("Video preview hardware backend", "Automatic"),
    ]:
        problems += _choice_value_problems(pathfm, title, value)
    assert not problems, "\n".join(problems)

    pathfm.pointer.click(_open_choice(pathfm, "Modified date format", "ISO 8601"))
    pathfm.wait(
        lambda: pathfm.environment.read_preferences().get("date_format") == '"iso"',
        "the ISO 8601 date format to be saved",
    )
    pathfm.wait(
        lambda: not _choice_value_problems(pathfm, "Modified date format", "ISO 8601"),
        "the date format button to describe ISO 8601",
    )


@pytest.mark.parametrize(
    ("title", "selected", "other"),
    [
        ("Modified date format", "Relative", "ISO 8601"),
        ("Drag & drop to another device", "Always ask", "Always copy"),
    ],
)
def test_settings_choice_options_expose_the_chosen_option(pathfm, title, selected, other):
    _open_general_settings(pathfm)
    _open_choice(pathfm, title, selected)
    for label, expected in [(selected, True), (other, False)]:
        option = pathfm.wait(
            lambda label=label: pathfm.window.find(role="radio menu item", name=label),
            f"the {label!r} option",
        )
        assert option.has_state("checked") == expected, (label, sorted(option.states))
