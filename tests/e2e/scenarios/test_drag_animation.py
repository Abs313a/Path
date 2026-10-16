# SPDX-License-Identifier: MIT

import time

from PIL import ImageGrab
import pytest

from harness.environment import TestEnvironment as IsolatedEnvironment
from harness.interaction import MODIFIER_KEYSYMS, keysym
from harness.modes import ALL_MODES


@pytest.fixture
def test_environment():
    environment = IsolatedEnvironment()
    settings = environment.config_home / "gtk-4.0/settings.ini"
    settings.write_text(settings.read_text().replace(
        "gtk-enable-animations=false", "gtk-enable-animations=true"
    ))
    try:
        yield environment
    finally:
        environment.cleanup()


def text_position(image, bounds):
    """Measure glyph position independently of selection color and opacity."""
    pixels = image.convert("L").load()
    weights = []
    for y in range(bounds.y, bounds.y + bounds.height):
        row = [pixels[x, y] for x in range(bounds.x, bounds.x + bounds.width)]
        background = sorted(row)[len(row) // 2]
        weights.append(sum(abs(value - background) for value in row))
    contrast = sum(weights)
    assert contrast > 0, "the source label disappeared"
    return sum(y * weight for y, weight in enumerate(weights)) / contrast, contrast


@pytest.mark.preferences(reduce_motion=False)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_delete_animation_preserves_survivors_and_restores_interaction(pathfm, mode):
    assert pathfm.view_mode() == mode
    fixture = pathfm.fixture
    fixture.path("zz-survivor.txt").write_text("survivor")
    original_names = set(fixture.names())
    pathfm.entry("zz-survivor.txt")
    pathfm.select_entry("todo.txt")

    pathfm.keyboard.press("shift+Delete")
    pathfm.wait_for_dialog()
    pathfm.pointer.click(pathfm.dialog_button("Permanently delete 1 item"))
    pathfm.wait(
        lambda: not fixture.path("todo.txt").exists(),
        "the file to be deleted",
    )
    pathfm.wait(lambda: pathfm.dialog() is None, "the delete dialog to disappear")
    pathfm.wait_for_entry_gone("todo.txt")
    assert set(fixture.names()) == original_names - {"todo.txt"}

    pathfm.select_entry("zz-survivor.txt")
    pathfm.keyboard.press("F2")
    field = pathfm.editable_field()
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("renamed-survivor.txt")
    pathfm.wait(lambda: field.text == "renamed-survivor.txt", "the survivor name to be typed")
    pathfm.keyboard.press("Return")
    pathfm.wait(lambda: fixture.path("renamed-survivor.txt").exists(), "the survivor to be renamed")
    assert fixture.path("renamed-survivor.txt").read_text() == "survivor"
    assert set(fixture.names()) == (
        original_names - {"todo.txt", "zz-survivor.txt"} | {"renamed-survivor.txt"}
    )


@pytest.mark.preferences(browser_mode="columns", reduce_motion=False)
@pytest.mark.parametrize("outcome", [
    "escape", "outside", "copy", "move", "noop", "failed",
    pytest.param("copy", marks=pytest.mark.preferences(open_folder_after_drop=True), id="copy-open"),
    pytest.param("move", marks=pytest.mark.preferences(open_folder_after_drop=True), id="move-open"),
    pytest.param("escape", marks=pytest.mark.preferences(reduce_motion=True), id="reduced-motion"),
])
def test_drag_completion_keeps_the_source_label_in_place(pathfm, outcome):
    fixture = pathfm.fixture
    original = fixture.path("todo.txt").read_bytes()
    source = pathfm.select_entry("todo.txt")
    label = source.find(role="label", name="todo.txt")
    assert label is not None
    bounds = label.screen_bounds()
    target = pathfm.entry("archive").screen_bounds().center
    if outcome in ("escape", "outside"):
        window = pathfm.window.screen_bounds()
        target = (window.x + window.width + 30, window.y + window.height + 20)
    elif outcome == "noop":
        pane = pathfm.pane().screen_bounds()
        target = (pane.x + pane.width // 2, pane.y + pane.height - 20)
    elif outcome == "failed":
        fixture.path("archive").chmod(0o555)

    connection = pathfm.pointer.connection
    grab = lambda: ImageGrab.grab(xdisplay=pathfm.display.display)
    try:
        pathfm.pointer.move_to(*target)
        pathfm.settle(source)
        resting_y, resting_contrast = text_position(grab(), bounds)
        pathfm.pointer.drag_points(pathfm.pointer.drag_origin(source), target, release=False)
        if outcome == "copy":
            connection.key(MODIFIER_KEYSYMS["ctrl"], True)
            pathfm.pointer.move_to(*target)
        _, dragging_contrast = text_position(grab(), bounds)
        assert dragging_contrast < resting_contrast * 0.8, "a real source drag must start"

        released = time.monotonic()
        if outcome == "escape":
            connection.key(keysym("Escape"), True)
            connection.key(keysym("Escape"), False)
        connection.button(1, False)
        samples = []
        # Sample at exact deadlines, not the UI readiness poller's 50 ms intervals.
        for delay in (0.06, 0.12, 0.18):
            time.sleep(max(0, released + delay - time.monotonic()))
            image = grab()
            samples.append((time.monotonic() - released, image))
        samples = [(elapsed, text_position(image, bounds)) for elapsed, image in samples]
        assert all(elapsed < 0.24 for elapsed, _ in samples), samples
        for _, (position, _) in samples:
            assert abs(position - resting_y) < 1.5, "source label slid out after drag completion"
        assert samples[-1][1][1] > dragging_contrast * 1.25, "dragging opacity must recover"

        if outcome in ("copy", "move"):
            pathfm.wait(lambda: fixture.path("archive/todo.txt").exists(), "the transferred file")
            assert fixture.path("archive/todo.txt").read_bytes() == original
            open_after_drop = pathfm.environment.read_preferences().get("open_folder_after_drop") == "true"
            if open_after_drop:
                pathfm.entry("todo.txt", directory="archive")
            else:
                assert pathfm.pane_names() == [fixture.root.name]
            if outcome == "move":
                pathfm.wait(lambda: not fixture.path("todo.txt").exists(), "source removal")
                pathfm.wait_for_entry_gone("todo.txt", directory=fixture.root.name)
            else:
                assert fixture.path("todo.txt").read_bytes() == original
        else:
            if outcome == "failed":
                pathfm.wait(lambda: "could not" in pathfm.diagnostics().lower()
                            or "permission denied" in pathfm.diagnostics().lower(), "transfer failure")
            pathfm.wait(lambda: time.monotonic() - released >= 0.6,
                        "the deferred drop handler to finish")
            pathfm.entry("todo.txt")
            assert fixture.path("todo.txt").read_bytes() == original
            assert fixture.names("archive") == []
    finally:
        connection.button(1, False)
        connection.key(MODIFIER_KEYSYMS["ctrl"], False)
        fixture.path("archive").chmod(0o755)
