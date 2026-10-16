# SPDX-License-Identifier: MIT
"""Golden screenshots for a small set of deliberately stable states.

Interaction assertions are the primary gate; these catch rendering
regressions the accessible tree cannot see. Keep the set small: every image
here has to be reviewed whenever the design changes.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from harness.fixtures import FixtureTree

BASELINE_FIXTURE = {
    "documents": {
        "notes.txt": "notes\n",
        "projects": {"release": {"summary.md": "# Release\n"}},
        "report.md": "# Report\n",
    },
    "pictures": {},
    "readme.md": "# Fixture\n",
    "todo.txt": "todo\n",
}

pytestmark = pytest.mark.baseline


# The breadcrumb and the context menu both render the fixture's path, so the
# baseline scenarios use a fixed directory instead of a randomized one.
BASELINE_ROOT = Path("/tmp/pathfm-e2e-baseline")
BASELINE_ENTRIES = ["documents", "pictures", "readme.md", "todo.txt"]
ICONS_BASELINE_FIXTURE = {
    "Applications": {},
    "DataGripProjects": {},
    "pictures": {},
    "readme.md": "# Fixture\n",
    "todo.txt": "todo\n",
}
ICONS_BASELINE_ENTRIES = [
    "Applications", "DataGripProjects", "pictures", "portrait.png", "readme.md",
    "todo.txt", "wide.png",
]
ICONS_BASELINE_THUMBNAILS = {
    "portrait.png": ((32, 64), (255, 140, 0)),
    "wide.png": ((64, 32), (70, 130, 180)),
}


@pytest.fixture
def fixture_tree(request):
    """Stable names and content, including mixed caption lengths and image shapes."""

    preferences = request.node.get_closest_marker("preferences")
    icons = preferences is not None and preferences.kwargs.get("browser_mode") == "icons"
    tree = FixtureTree.create_at(
        BASELINE_ROOT, ICONS_BASELINE_FIXTURE if icons else BASELINE_FIXTURE
    )
    if icons:
        for name, (size, color) in ICONS_BASELINE_THUMBNAILS.items():
            Image.new("RGB", size, color).save(BASELINE_ROOT / name)
    try:
        yield tree
    finally:
        tree.cleanup()


@pytest.mark.preferences(browser_mode="columns")
def test_columns_view_baseline(pathfm, baseline):
    _settle(pathfm)
    baseline(pathfm, "columns-view")


@pytest.mark.preferences(browser_mode="columns")
def test_columns_overflow_baseline(pathfm, baseline):
    pathfm.open_directory("documents")
    pathfm.open_directory("projects", "documents")
    pathfm.open_directory("release", "projects")
    _settle(pathfm, ["summary.md"])
    baseline(pathfm, "columns-overflow")


@pytest.mark.preferences(browser_mode="icons")
def test_icons_view_baseline(pathfm, baseline, tmp_path):
    _settle_icons(pathfm, tmp_path)
    pathfm.select_entry_with_keyboard("DataGripProjects")
    baseline(pathfm, "icons-view")


@pytest.mark.preferences(browser_mode="icons", browser_density="airy")
def test_icons_airy_view_baseline(pathfm, baseline, tmp_path):
    _settle_icons(pathfm, tmp_path)
    pathfm.select_entry_with_keyboard("Applications")
    baseline(pathfm, "icons-airy-view")


@pytest.mark.preferences(browser_mode="icons")
def test_icons_hover_baseline(pathfm, baseline, tmp_path):
    _settle_icons(pathfm, tmp_path)
    pathfm.pointer.move_to(*pathfm.entry("todo.txt").screen_bounds().center)
    pathfm.settle(pathfm.pane())
    baseline(pathfm, "icons-hover")


@pytest.mark.preferences(browser_mode="list")
def test_list_view_baseline(pathfm, baseline):
    _settle(pathfm)
    baseline(pathfm, "list-view")


@pytest.mark.preferences(browser_mode="list")
def test_selection_and_focus_baseline(pathfm, baseline):
    pathfm.select_entry_with_keyboard("readme.md")
    pathfm.keyboard.press("shift+Down")
    pathfm.wait(
        lambda: pathfm.selected_names() == ["readme.md", "todo.txt"],
        "both files to be selected",
    )
    _settle(pathfm)
    baseline(pathfm, "selection-and-focus")


@pytest.mark.preferences(browser_mode="list")
def test_context_menu_baseline(pathfm, baseline):
    pathfm.open_context_menu("readme.md")
    pathfm.wait(
        lambda: "Copy" in pathfm.menu_items(), "the context menu to be populated"
    )
    baseline(pathfm, "context-menu")


@pytest.mark.preferences(browser_mode="list")
def test_delete_confirmation_baseline(pathfm, baseline):
    pathfm.select_entry_with_keyboard("todo.txt")
    pathfm.keyboard.press("shift+Delete")
    pathfm.wait_for_dialog()
    _settle(pathfm)
    baseline(pathfm, "delete-confirmation")


def _settle_icons(pathfm, tmp_path) -> None:
    _settle(pathfm, ICONS_BASELINE_ENTRIES)
    icons = {
        name: pathfm.entry(name).find(role="image")
        for name in ICONS_BASELINE_THUMBNAILS
    }
    assert all(icon is not None for icon in icons.values())

    def thumbnails_ready():
        capture = pathfm.screenshot(tmp_path / "thumbnail-readiness.png")
        with Image.open(capture) as image:
            pixels = image.convert("RGB")
            return all(
                pixels.getpixel(icons[name].screen_bounds().center) == color
                for name, (_, color) in ICONS_BASELINE_THUMBNAILS.items()
            )

    pathfm.wait(thumbnails_ready, "both image shapes to finish rendering")


def _settle(pathfm, entries=BASELINE_ENTRIES) -> None:
    """Park the pointer and wait for the listing before capturing."""

    pathfm.park_pointer()
    pathfm.wait(
        lambda: pathfm.entry_names()
        == entries,
        "the fixture listing to be complete",
    )
    pathfm.settle(pathfm.pane())
