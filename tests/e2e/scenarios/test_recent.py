# SPDX-License-Identifier: MIT
"""The pinned image has no GVfs and uses GIO_USE_VFS=local, so Recent is unavailable."""

from __future__ import annotations

RECENT_URIS = ("recent:///", "recent://")


def _switch(window, name):
    return next(
        (
            node
            for node in window.find_all(name=name, rendered=False)
            if node.role in {"check box", "toggle button", "switch"}
        ),
        None,
    )


def _navigate(pathfm, uri):
    pathfm.keyboard.press("ctrl+l")
    field = pathfm.editable_field()
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text(uri)
    pathfm.wait(lambda: field.text == uri, f"{uri} to be typed")
    pathfm.keyboard.press("Return")


def test_recent_is_absent_from_the_sidebar_without_a_platform_backend(pathfm):
    pathfm.sidebar_button("Home")
    pathfm.sidebar_button("Trash")

    assert pathfm.window.find(role="button", name="Recent") is None, (
        "Recent must not be offered when the recent backend is unavailable"
    )


def test_neither_recent_preference_state_can_add_an_unsupported_place(pathfm):
    settings = pathfm.window.find(role="button", name="Settings")
    assert settings is not None and settings.activate()
    pathfm.wait(
        lambda: _switch(pathfm.window, "Show Recent in sidebar"),
        "the Recent sidebar preference",
    )
    enabled = "pressed" in _switch(pathfm.window, "Show Recent in sidebar").states

    for _ in range(2):
        _switch(pathfm.window, "Show Recent in sidebar").activate()
        enabled = not enabled
        pathfm.wait(
            lambda: (
                "pressed" in _switch(pathfm.window, "Show Recent in sidebar").states
            )
            == enabled,
            "the Recent preference to change",
        )
        pathfm.wait(
            lambda: pathfm.window.find(role="button", name="Recent") is None,
            "Recent to stay hidden while its backend is unavailable",
        )

    pathfm.keyboard.press("Escape")
    pathfm.sidebar_button("Home")
    pathfm.sidebar_button("Trash")


def test_every_recent_uri_spelling_is_refused_without_disturbing_the_session(pathfm):
    root = pathfm.fixture.root.name
    pathfm.entry("documents")

    for uri in RECENT_URIS:
        _navigate(pathfm, uri)

        dialog = pathfm.wait(
            lambda: pathfm.window.find(role="dialog", name="Unable to open location"),
            f"the failure report for {uri}",
        )
        assert "backend isn't installed" in dialog.dump(), (
            f"{uri} should explain why it cannot be opened"
        )
        pathfm.keyboard.press("Escape")
        pathfm.wait(
            lambda: pathfm.window.find(role="dialog", name="Unable to open location")
            is None,
            "the failure report to close",
        )
        pathfm.wait_for_directory(root)
        pathfm.entry("documents")
