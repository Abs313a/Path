# SPDX-License-Identifier: MIT
"""Custom typography remains editable and usable across browser presentations."""

import pytest

from harness.artifacts import ArtifactCollector


@pytest.mark.preferences(text_size=17)
def test_settings_text_size_keeps_switches_inside_the_page(pathfm, request):
    settings = pathfm.window.find(role="button", name="Settings")
    assert settings is not None and settings.activate()
    for pixels, next_pixels, width in [(17, 11, 1000), (11, 32, 1000), (32, None, 640)]:
        bounds = pathfm.window.screen_bounds()
        pathfm.keyboard.connection.resize_surface(bounds.width, bounds.height, width, 600)
        pathfm.wait(lambda: pathfm.window.screen_bounds().width == width, "resized settings window")
        general = pathfm.wait(
            lambda: pathfm.window.find(role="button", name="General"),
            "General settings navigation",
        )
        assert general.activate()
        toggle = pathfm.wait(
            lambda: next(
                (node for node in pathfm.window.find_all(name="Folder peeking")
                 if node.role in {"check box", "toggle button", "switch"}),
                None,
            ),
            "visible folder-peeking switch",
        )
        toggle = _reveal_page_control(pathfm, "Folder peeking", role=toggle.role)
        scroll = next(node for node in toggle.ancestors() if node.role == "scroll pane")
        bounds, viewport = toggle.screen_bounds(), scroll.screen_bounds()
        assert viewport.x <= bounds.x
        assert bounds.x + bounds.width <= viewport.x + viewport.width
        was_checked = toggle.has_state("checked")
        pathfm.pointer.click(toggle)
        pathfm.wait(lambda: toggle.has_state("checked") != was_checked, "resized switch responds to pointer")
        pathfm.pointer.click(toggle)
        pathfm.wait(lambda: toggle.has_state("checked") == was_checked, "restore folder peeking")
        if request.config.getoption("--keep-artifacts"):
            pathfm.screenshot(
                ArtifactCollector(test_name=f"settings-text-size-{pixels}").directory
                / "general.png"
            )
        _reveal_page_control(pathfm, "Complete setup")
        if request.config.getoption("--keep-artifacts"):
            pathfm.screenshot(
                ArtifactCollector(test_name=f"settings-text-size-{pixels}").directory
                / "desktop-integration.png"
            )
        theme = pathfm.window.find(role="button", name="Appearance settings")
        assert theme is not None and theme.activate()
        control = pathfm.wait(
            lambda: pathfm.window.find(role="spin button", name="Text size in pixels", rendered=False),
            "numeric text-size control",
        )
        control = _reveal_page_control(pathfm, "Text size in pixels", role="spin button")
        pathfm.wait(lambda: _inside_scroll_view(control), "text-size control scrolled into view")
        # GTK exposes the spin button as one accessible value, not separate buttons.
        for fraction, expected in [(1, pixels - 1), (7, pixels)]:
            bounds = control.screen_bounds()
            pathfm.pointer.click(
                control,
                at=(bounds.x + bounds.width * fraction // 8, bounds.y + bounds.height // 2),
            )
            pathfm.wait(
                lambda: pathfm.environment.read_preferences().get("text_size")
                == str(expected),
                "left decrement and right increment buttons",
            )
        if request.config.getoption("--keep-artifacts"):
            pathfm.screenshot(
                ArtifactCollector(test_name=f"settings-text-size-{pixels}").directory
                / "selector.png"
            )
        if next_pixels is not None:
            pathfm.pointer.click(control)
            pathfm.keyboard.press("ctrl+a")
            pathfm.keyboard.type_text(str(next_pixels))
            pathfm.keyboard.press("Return")
            pathfm.wait(
                lambda: pathfm.environment.read_preferences().get("text_size")
                == str(next_pixels),
                "updated settings text",
            )
        else:
            pathfm.keyboard.press("ctrl+0")
            pathfm.wait(
                lambda: pathfm.environment.read_preferences().get("text_size") == "13",
                "Reset to restore the default text size",
            )
    updates = pathfm.window.find(role="button", name="Updates")
    assert updates is not None and updates.activate()
    _reveal_page_control(pathfm, "Check now")
    if request.config.getoption("--keep-artifacts"):
        pathfm.screenshot(
            ArtifactCollector(test_name="settings-updates").directory / "check-now.png"
        )


def _reveal_page_control(pathfm, name, role="button"):
    node = pathfm.wait(lambda: pathfm.window.find(role=role, name=name, rendered=False), f"{name} control")
    scroll = next(parent for parent in node.ancestors() if parent.role == "scroll pane")

    def revealed():
        if _inside_scroll_view(node):
            return True
        viewport = scroll.screen_bounds()
        # Stay in the content gutter: the scrollbar scrolls by whole pages,
        # which can jump over a control without ever showing all of it.
        # The nested theme library ends before this gutter.
        at = (viewport.x + viewport.width - 16, viewport.y + viewport.height // 2)
        bounds = node.screen_bounds()
        below = bounds.y + bounds.height - (viewport.y + viewport.height)
        above = viewport.y - bounds.y
        # Large text makes General several viewports tall. Traverse distant
        # sections faster, then use single notches so we cannot skip the control.
        distance = max(below, above)
        clicks = min(12, max(1, int(distance / viewport.height) * 3))
        pathfm.pointer.scroll(at, clicks=clicks, down=below > 0)
        return False

    pathfm.wait(revealed, f"reachable {name} control")
    return pathfm.settle(node)


def _inside_scroll_view(node):
    scroll = next(parent for parent in node.ancestors() if parent.role == "scroll pane")
    bounds, viewport = node.screen_bounds(), scroll.screen_bounds()
    return (
        bounds.width > 0
        and bounds.height > 0
        and viewport.x <= bounds.x
        and viewport.y <= bounds.y
        and bounds.x + bounds.width <= viewport.x + viewport.width
        and bounds.y + bounds.height <= viewport.y + viewport.height
    )


@pytest.mark.preferences(text_size=24)
def test_custom_text_size_shortcuts_numeric_control_and_restart(pathfm, request):
    pathfm.select_entry("todo.txt")
    pathfm.keyboard.press("ctrl+=")
    pathfm.wait(
        lambda: pathfm.environment.read_preferences().get("text_size") == "25",
        "zoom in to persist a numeric size",
    )
    pathfm.keyboard.press("ctrl+-")
    pathfm.wait(
        lambda: pathfm.environment.read_preferences().get("text_size") == "24",
        "zoom out to restore the custom size",
    )
    pathfm.keyboard.press("ctrl+0")
    pathfm.wait(
        lambda: pathfm.environment.read_preferences().get("text_size") == "13",
        "reset to the default size",
    )
    if request.config.getoption("--keep-artifacts"):
        pathfm.screenshot(ArtifactCollector(test_name="text-size").directory / "before.png")
    pathfm.open_appearance_menu()
    for name, pixels in [
        ("Increase text size (Ctrl++)", "14"),
        ("Decrease text size (Ctrl+−)", "13"),
        ("Decrease text size (Ctrl+−)", "12"),
        ("12 px", "13"),
    ]:
        button = pathfm.wait(
            lambda: pathfm.window.find(role="button", name=name),
            f"appearance text-size control {name}",
        )
        pathfm.pointer.click(button)
        pathfm.wait(
            lambda: pathfm.environment.read_preferences().get("text_size") == pixels,
            f"appearance text-size control to persist {pixels}px",
        )
    if request.config.getoption("--keep-artifacts"):
        pathfm.screenshot(
            ArtifactCollector(test_name="text-size").directory / "appearance.png"
        )
    pathfm.keyboard.press("Escape")
    pathfm.keyboard.press("F2")
    rename = pathfm.wait(
        lambda: pathfm.window.find(role="text", name="Rename"), "inline rename editor"
    )
    pathfm.keyboard.press("ctrl+=")
    pathfm.wait(
        lambda: pathfm.environment.read_preferences().get("text_size") == "14",
        "zoom while renaming without submitting the editor",
    )
    assert rename.alive
    pathfm.keyboard.press("Escape")
    assert pathfm.fixture.path("todo.txt").exists()

    settings = pathfm.window.find(role="button", name="Settings")
    assert settings is not None and settings.activate()
    theme = pathfm.wait(
        lambda: pathfm.window.find(role="button", name="Appearance settings"),
        "appearance settings",
    )
    assert theme.activate()
    control = pathfm.wait(
        lambda: pathfm.window.find(role="spin button", name="Text size in pixels", rendered=False),
        "numeric text size control",
    )
    control = _reveal_page_control(pathfm, "Text size in pixels", role="spin button")
    pathfm.pointer.click(control)
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("27")
    pathfm.keyboard.press("Return")
    pathfm.wait(
        lambda: pathfm.environment.read_preferences().get("text_size") == "27",
        "an arbitrary typed text size to persist",
    )
    pathfm.application.stop()
    pathfm.application.start()
    assert pathfm.environment.read_preferences()["text_size"] == "27"
    pathfm.select_entry("todo.txt")
    pathfm.keyboard.press("ctrl+=")
    pathfm.wait(
        lambda: pathfm.environment.read_preferences().get("text_size") == "28",
        "restart to load the exact custom size",
    )
    if request.config.getoption("--keep-artifacts"):
        pathfm.screenshot(ArtifactCollector(test_name="text-size").directory / "after.png")
