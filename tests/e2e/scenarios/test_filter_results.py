# SPDX-License-Identifier: GPL-3.0-or-later
import tomllib
from pathlib import Path

import pytest
from PIL import Image, ImageColor

from harness.fixtures import FixtureTree
from harness.keyboard_layout import PINYIN
from harness.modes import ALL_MODES


@pytest.fixture
def fixture_tree():
    fixture = FixtureTree.create({
        "match-note.txt": "root decoy\n",
        "alpha": {"match-note.txt": "alpha source\n"},
        "beta": {"match-note.txt": "beta source\n", "only-match.txt": "beta source\n"},
        "match-note-other.md": "other match\n",
        "destination": {},
        "thumb.txt": "thumbnail search companion",
    })
    Image.new("RGB", (64, 64), (230, 40, 60)).save(fixture.path("beta/thumb.png"))
    try:
        yield fixture
    finally:
        fixture.cleanup()


def result_rows(pathfm):
    container = pathfm.window.find(role="list", name="Search results")
    role = "list item"
    if container is None:
        container = pathfm.window.find(role="table", name="Search results")
        role = "table cell"
    if container is None:
        return pathfm.window.find_all(role="list item")
    return container.find_all(role=role)


def result(pathfm, path):
    for row in result_rows(pathfm):
        if row.name == Path(path).name and any(
            label.name.endswith(path) for label in row.find_all(role="label")
        ):
            return row
    return None


def filter_results(pathfm, query="match-note", count=4, directory=None):
    pathfm.select_entry("match-note.txt", directory)
    pathfm.keyboard.press("ctrl+f")
    field = pathfm.editable_field()
    pathfm.keyboard.type_text(query)
    pathfm.wait(lambda: len(pathfm.matches()) == count, "all recursive matches")
    return field


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("route", ["shift", "keyboard-range", "select-all", "marquee"])
@pytest.mark.parametrize("recursive", [
    pytest.param(False, marks=pytest.mark.preferences(filter_include_subfolders=False)),
    pytest.param(True, marks=pytest.mark.preferences(filter_include_subfolders=True)),
])
def test_filtered_results_support_group_selection(pathfm, mode, route, recursive):
    count = 4 if recursive else 2
    filter_results(pathfm, count=count)
    rows = [row for row in result_rows(pathfm) if "match-note" in row.name]
    assert len(rows) == count
    if route == "marquee":
        first = rows[0].screen_bounds()
        last = rows[-1].screen_bounds()
        pathfm.pointer.drag_points(
            (last.center[0], last.y + last.height + 25),
            (first.x + 15, first.y + 2),
        )
    else:
        pathfm.pointer.click(rows[0], modifiers=("ctrl",))
        if route == "shift":
            pathfm.pointer.click(rows[-1], modifiers=("shift",))
        else:
            pathfm.keyboard.press("ctrl+f")
            pathfm.keyboard.press("Down")
            if route == "keyboard-range":
                step = "shift+Right" if mode == "Icons" else "shift+Down"
                for _ in range(count - 1):
                    pathfm.keyboard.press(step)
            else:
                pathfm.keyboard.press("ctrl+a")
    pathfm.wait(
        lambda: all(row.has_state("selected") for row in rows),
        "all filtered results to be selected",
    )


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("route", ["keyboard", "context-menu"])
@pytest.mark.parametrize("recursive", [
    pytest.param(False, marks=pytest.mark.preferences(filter_include_subfolders=False)),
    pytest.param(True, marks=pytest.mark.preferences(filter_include_subfolders=True)),
])
@pytest.mark.preferences(list_file_clicks=2, grid_file_clicks=2, explorer_file_clicks=2)
def test_filtered_properties_uses_visible_selection(pathfm, mode, route, recursive):
    pathfm.select_entry("match-note.txt")
    pathfm.pointer.click(pathfm.entry("match-note-other.md"), modifiers=("ctrl",))
    pathfm.keyboard.press("ctrl+f")
    pathfm.keyboard.type_text("match-note")
    pathfm.wait(lambda: len(pathfm.matches()) == (4 if recursive else 2), "matching files")
    rows = result_rows(pathfm)
    first = result(pathfm, "alpha/match-note.txt") if recursive else next(row for row in rows if row.name == "match-note.txt")
    second = next(row for row in rows if row.name == "match-note-other.md")
    assert first is not None and second is not None
    for row in rows:
        if row.has_state("selected"):
            pathfm.pointer.click(row, modifiers=("ctrl",))
    pathfm.pointer.click(first, modifiers=("ctrl",))
    pathfm.pointer.click(second, modifiers=("ctrl",))
    pathfm.wait(lambda: first.has_state("selected") and second.has_state("selected"), "selected hits")
    if route == "keyboard":
        pathfm.keyboard.press("alt+Return")
    else:
        pathfm.pointer.right_click(first)
        pathfm.wait(pathfm.context_menu, "selected results menu")
        pathfm.choose_menu_item("Properties")
    dialog = pathfm.wait_for_dialog()
    pathfm.wait(lambda: dialog.find(role="label", name="≥ 2 files, ≥ 0 folders"), "selected search hits")
    assert dialog.find(role="label", name="≥ 0 B")
    pathfm.keyboard.press("Escape")
    pathfm.wait(lambda: not dialog.is_rendered(), "Properties to close")
    pathfm.pointer.click(second, modifiers=("ctrl",))
    pathfm.wait(lambda: first.has_state("selected") and not second.has_state("selected"), "one selected hit")
    pathfm.keyboard.press("alt+Return")
    dialog = pathfm.wait_for_dialog()
    pathfm.wait(lambda: dialog.find(role="label", name="13 B" if recursive else "11 B"), "single result size")
    assert dialog.find(role="label", name="OPENS WITH")


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("operation", ["drag", "copy"])
def test_filtered_control_selection_operates_on_the_selected_group(pathfm, mode, operation):
    filter_results(pathfm, query="match", count=5)
    first = result(pathfm, "beta/only-match.txt")
    second = result(pathfm, "match-note-other.md")
    assert first is not None and second is not None
    pathfm.pointer.click(first, modifiers=("ctrl",))
    pathfm.pointer.click(second, modifiers=("ctrl",))
    pathfm.pointer.click(first, modifiers=("ctrl",))
    pathfm.wait(lambda: not first.has_state("selected"), "Ctrl-click to deselect a result")
    pathfm.pointer.click(first, modifiers=("ctrl",))
    pathfm.wait(
        lambda: first.has_state("selected") and second.has_state("selected"),
        "both filtered files to be selected",
    )
    if operation == "drag":
        pathfm.pointer.drag(first, pathfm.sidebar_button("Home"))
    else:
        pathfm.pointer.right_click(first)
        pathfm.wait(pathfm.context_menu, "the selected group menu")
        assert first.has_state("selected") and second.has_state("selected")
        pathfm.choose_menu_item("Copy")
        pathfm.keyboard.press("ctrl+l")
        pathfm.keyboard.press("ctrl+a")
        pathfm.keyboard.type_text(str(pathfm.environment.home))
        pathfm.keyboard.press("Return")
        pathfm.wait_for_directory(pathfm.environment.home.name)
        pathfm.keyboard.press("ctrl+v")
    for path, contents in [("beta/only-match.txt", "beta source\n"),
                           ("match-note-other.md", "other match\n")]:
        destination = pathfm.environment.home / Path(path).name
        pathfm.wait(lambda: destination.exists(), "the selected file to arrive in Home")
        assert destination.read_text() == contents
        assert pathfm.fixture.path(path).exists() == (operation == "copy")
    assert pathfm.fixture.path("match-note.txt").read_text() == "root decoy\n"


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("shortcut", ["ctrl+c", "ctrl+x"])
@pytest.mark.parametrize("hints", [
    pytest.param(False, marks=pytest.mark.preferences(show_keybinding_hints=False)),
    pytest.param(True, marks=pytest.mark.preferences(show_keybinding_hints=True)),
])
def test_filtered_keyboard_clipboard_keeps_status_visible(pathfm, mode, shortcut, hints):
    filter_results(pathfm, query="match", count=5)
    for path in ["beta/only-match.txt", "match-note-other.md"]:
        row = result(pathfm, path)
        assert row is not None
        pathfm.pointer.click(row, modifiers=("ctrl",))
    pathfm.keyboard.press(shortcut)
    pathfm.wait(
        lambda: pathfm.window.find(role="label", name="Files on clipboard"),
        "the file clipboard status badge",
    )
    assert bool(pathfm.window.find(role="toggle button", name="F1  Shortcuts")) == hints
    assert pathfm.fixture.path("beta/only-match.txt").exists()
    assert pathfm.fixture.path("match-note-other.md").exists()
    pathfm.keyboard.press("ctrl+l")
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text(str(pathfm.fixture.path("destination")))
    pathfm.keyboard.press("Return")
    pathfm.wait_for_directory("destination")
    pathfm.keyboard.press("ctrl+v")
    for path, contents in [("beta/only-match.txt", "beta source\n"),
                           ("match-note-other.md", "other match\n")]:
        destination = pathfm.fixture.path(f"destination/{Path(path).name}")
        pathfm.wait(lambda: destination.exists(), "the clipboard file to arrive")
        assert destination.read_text() == contents
        assert pathfm.fixture.path(path).exists() == (shortcut == "ctrl+c")
    assert pathfm.fixture.path("match-note.txt").read_text() == "root decoy\n"


@pytest.mark.parametrize("mode", ALL_MODES)
def test_filter_right_arrow_moves_the_text_cursor(pathfm, mode):
    pathfm.switch_view(mode)
    field = filter_results(pathfm)
    pathfm.keyboard.press("Home")
    pathfm.keyboard.press("Right")
    pathfm.keyboard.type_text("X")
    pathfm.wait(lambda: field.text == "mXatch-note", "Right to move the filter caret")


def test_filter_text_selection_uses_the_active_theme(pathfm, tmp_path):
    field = filter_results(pathfm)
    pathfm.keyboard.press("ctrl+a")
    settings = tomllib.loads(pathfm.environment.settings_path.read_text())
    catalog = Path(__file__).resolve().parents[3] / "data/themes/catalog.toml"
    themes = tomllib.loads(catalog.read_text())["themes"]
    theme = next(theme for theme in themes if theme["id"] == settings["theme"])
    accent = ImageColor.getrgb(theme["accent"])

    def selected_text_has_theme_background():
        bounds = field.screen_bounds()
        capture = pathfm.screenshot(tmp_path / "filter-selection.png")
        with Image.open(capture) as image:
            pixels = image.convert("RGB").crop((
                bounds.x + 2, bounds.y + 2,
                bounds.x + bounds.width - 2, bounds.y + bounds.height - 2,
            ))
            return sum(count for count, color in pixels.getcolors(pixels.width * pixels.height)
                       if color == accent) > 100

    pathfm.wait(selected_text_has_theme_background, "theme-colored filter text selection")


@pytest.mark.parametrize("mode", [mode for mode in ALL_MODES if mode.id != "list"])
@pytest.mark.parametrize("trigger,query,count,target", [
    ("pointer", "match-note", 4, "beta/match-note.txt"),
    ("keyboard", "match-note", 4, "beta/match-note.txt"),
    ("keyboard", "only-match", 1, "beta/only-match.txt"),
])
def test_filtered_item_menu_actions_use_the_real_location(pathfm, mode, trigger, query, count, target):
    directory = "beta" if mode == "Columns" and count == 1 else None
    if directory:
        pathfm.open_directory(directory)
    field = filter_results(pathfm, query, count, directory)
    row = pathfm.wait(lambda: result(pathfm, target), "the beta result")
    if mode == "Columns" and count == 1:
        pathfm.hover_pane(pathfm.fixture.root.name)
    if trigger == "pointer":
        pathfm.pointer.right_click(row)
        pathfm.wait(pathfm.context_menu, "the result menu")
        pathfm.keyboard.press("Escape")
        pathfm.wait(lambda: pathfm.context_menu() is None, "the pointer result menu to close")
        pathfm.wait(lambda: row.has_state("focused"), "focus to return to the right-clicked result")
        pathfm.pointer.right_click(row)
    else:
        pathfm.keyboard.press("Down")
        pathfm.wait(lambda: not field.has_state("focused"), "Down to leave the filter input")
        result_step = "Right" if mode == "Icons" else "Down"
        for _ in range(count):
            if row.has_state("focused"):
                break
            pathfm.keyboard.press(result_step)
        pathfm.wait(lambda: row.has_state("focused"), "keyboard focus on the actual result")
        pathfm.keyboard.press("ctrl+f")
        pathfm.wait(lambda: field.has_state("focused"), "Ctrl+F to refocus the query")
        assert field.text == query
        pathfm.keyboard.press("Down")
        pathfm.wait(lambda: row.has_state("focused"), "Down to resume the selected result")
        for _ in range(count):
            pathfm.keyboard.press("Up")
            if field.has_state("focused"):
                break
        pathfm.wait(lambda: field.has_state("focused"), "Up from the first result to the query")
        assert field.text == query
        pathfm.keyboard.press("Down")
        pathfm.wait(lambda: not field.has_state("focused"), "Down to reenter results")
        for _ in range(count):
            if row.has_state("focused"):
                break
            pathfm.keyboard.press(result_step)
        pathfm.wait(lambda: row.has_state("focused"), "keyboard result focus after the round trip")
        pathfm.keyboard.press("Menu")
        pathfm.wait(pathfm.context_menu, "the keyboard result menu")
        pathfm.keyboard.press("Escape")
        pathfm.wait(lambda: pathfm.context_menu() is None, "the result menu to close")
        pathfm.wait(lambda: row.has_state("focused"), "focus to return to the result")
        pathfm.keyboard.press("shift+F10")
    pathfm.wait(pathfm.context_menu, "the result menu")
    assert row.has_state("selected")
    assert "Quick preview" in pathfm.menu_items()
    assert "Open file location" in pathfm.menu_items()
    assert "New Folder" not in pathfm.menu_items()
    assert "New Folder with Selection" not in pathfm.menu_items()
    if trigger == "keyboard":
        pathfm.keyboard.press("Home")
        pathfm.keyboard.press("Up")
        assert not field.has_state("focused")
        pathfm.keyboard.press("Home")
        for _ in pathfm.menu_items():
            if pathfm.menu_item("Properties").has_state("focused"):
                break
            pathfm.keyboard.press("Down")
        assert pathfm.menu_item("Properties").has_state("focused")
        assert row.has_state("selected"), "menu navigation changed selection"
        pathfm.keyboard.press("Return")
    else:
        pathfm.choose_menu_item("Properties")
    dialog = pathfm.wait_for_dialog()
    assert target in dialog.dump()
    assert row.has_state("selected"), "selection changed while Properties was opening"
    pathfm.keyboard.press("Escape")
    pathfm.wait(lambda: pathfm.dialog() is None, "result Properties to close")
    pathfm.wait(lambda: row.has_state("focused"), "Properties to restore the actual search result")
    assert row.has_state("selected")
    assert field.text == query
    if trigger == "pointer":
        pathfm.pointer.right_click(row)
    else:
        pathfm.keyboard.press("Menu")
    pathfm.wait(pathfm.context_menu, "the restored result menu")
    pathfm.choose_menu_item("Quick preview")
    pathfm.wait(lambda: pathfm.preview_shows("beta source"), "preview of the nested result")
    pathfm.wait(lambda: result(pathfm, target).has_state("selected"),
                "preview to retain the selected result")
    assert field.text == query
    pathfm.keyboard.press("ctrl+f")
    pathfm.wait(lambda: field.has_state("focused"), "Ctrl+F to return from the preview")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview() is None, "Space to close preview")
    assert field.text == query
    pathfm.pointer.right_click(result(pathfm, target))
    pathfm.wait(pathfm.context_menu, "the selected result menu")
    pathfm.choose_menu_item("Copy")
    assert field.text == query
    pathfm.keyboard.press("ctrl+l")
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text(str(pathfm.fixture.path("destination")))
    pathfm.keyboard.press("Return")
    pathfm.wait_for_directory("destination")
    pathfm.keyboard.press("ctrl+v")
    destination = pathfm.fixture.path(f"destination/{Path(target).name}")
    pathfm.wait(lambda: destination.exists() and destination.read_text() == "beta source\n",
                "the actual nested file to be copied")
    assert pathfm.fixture.path("match-note.txt").read_text() == "root decoy\n"
    assert pathfm.fixture.path("alpha/match-note.txt").read_text() == "alpha source\n"


def test_space_completes_a_composition_instead_of_previewing_the_selected_result(
    pathfm, keyboard_layout
):
    field = filter_results(pathfm)
    row = pathfm.wait(lambda: result(pathfm, "beta/match-note.txt"), "the beta result")
    pathfm.pointer.click(row, modifiers=("ctrl",))
    pathfm.pointer.click(field)
    pathfm.keyboard.press("End")
    with keyboard_layout(PINYIN):
        pathfm.keyboard.press("altgr+1")
        pathfm.keyboard.press("space")
        pathfm.wait(lambda: field.text == "match-note¯", "Space to complete the tone mark")
    assert pathfm.preview() is None


@pytest.mark.parametrize("mode", ALL_MODES)
def test_query_updates_retain_selection_focus_preview_and_background_menu(pathfm, mode):
    field = filter_results(pathfm)
    row = pathfm.wait(lambda: result(pathfm, "beta/match-note.txt"), "the beta result")
    pathfm.pointer.click(row, modifiers=("ctrl",))
    pathfm.pointer.click(field)
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("beta source"), "the selected preview")
    hovered = result(pathfm, "alpha/match-note.txt")
    pathfm.pointer.move_to(*hovered.screen_bounds().center)
    pathfm.settle(hovered)
    assert not hovered.has_state("selected")
    assert result(pathfm, "beta/match-note.txt").has_state("selected")
    assert pathfm.preview_shows("beta source")
    for query, count in [("match-note.t", 3), ("match-note", 4)] * 2:
        pathfm.keyboard.press("ctrl+a")
        pathfm.keyboard.type_text(query)
        pathfm.wait(lambda: len(pathfm.matches()) == count, "the updated result count")
        assert result(pathfm, "beta/match-note.txt").has_state("selected")
        assert field.has_state("focused")
        assert field.text == query
        assert pathfm.preview_shows("beta source")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview() is None, "Space to close after updates")
    assert field.text == "match-note"
    pathfm.pointer.right_click(pathfm.pane(), at=pathfm.background_point())
    pathfm.wait(pathfm.context_menu, "the empty-space menu")
    assert "New Folder" in pathfm.menu_items()
    assert "Quick preview" not in pathfm.menu_items()


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("trigger,focus_filter", [
    ("menu", False),
    ("F2", False),
    ("F2", True),
    ("ctrl+r", False),
    ("ctrl+r", True),
])
def test_filtered_rename_targets_the_nested_duplicate(pathfm, mode, trigger, focus_filter):
    field = filter_results(pathfm)
    row = pathfm.wait(lambda: result(pathfm, "beta/match-note.txt"), "the beta result")
    if trigger == "menu":
        pathfm.pointer.right_click(row)
        pathfm.wait(pathfm.context_menu, "the result menu")
        pathfm.choose_menu_item("Rename")
    else:
        pathfm.pointer.click(row, modifiers=("ctrl",))
        if focus_filter:
            pathfm.pointer.click(field)
        pathfm.keyboard.press(trigger)
    pathfm.editable_field()
    assert pathfm.dialog() is None
    pathfm.keyboard.press("Escape")
    pathfm.wait(
        lambda: pathfm.window.find(role="text", name="Rename", states={"editable"}) is None,
        "inline rename to close",
    )
    pathfm.wait(
        lambda: result(pathfm, "beta/match-note.txt").has_state("focused"),
        "focus to return to the originating result",
    )
    assert result(pathfm, "beta/match-note.txt").has_state("selected")
    assert field.text == "match-note"
    assert pathfm.fixture.path("beta/match-note.txt").read_text() == "beta source\n"
    assert pathfm.fixture.path("match-note.txt").read_text() == "root decoy\n"
    pathfm.keyboard.press("F2")
    pathfm.editable_field()
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("renamed.txt")
    pathfm.keyboard.press("Return")
    renamed = pathfm.fixture.path("beta/renamed.txt")
    pathfm.wait(lambda: renamed.exists() and renamed.read_text() == "beta source\n", "the nested rename")
    assert not pathfm.fixture.path("beta/match-note.txt").exists()
    assert pathfm.fixture.path("alpha/match-note.txt").read_text() == "alpha source\n"
    assert pathfm.fixture.path("match-note.txt").read_text() == "root decoy\n"
    assert field.text == "match-note"
    pathfm.wait(lambda: result(pathfm, "beta/match-note.txt") is None, "the stale hit to disappear")
    pathfm.pointer.click(field)
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("match-note.t")
    pathfm.wait(lambda: len(pathfm.matches()) == 2, "only the surviving matches after a query change")
    assert result(pathfm, "beta/match-note.txt") is None


@pytest.mark.parametrize("mode", ALL_MODES)
def test_matching_rename_stays_searchable_at_the_real_parent(pathfm, mode):
    field = filter_results(pathfm)
    row = pathfm.wait(lambda: result(pathfm, "beta/match-note.txt"), "the beta result")
    pathfm.pointer.click(row, modifiers=("ctrl",))
    pathfm.keyboard.press("F2")
    pathfm.editable_field()
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("match-note-renamed.txt")
    pathfm.keyboard.press("Return")
    renamed = pathfm.fixture.path("beta/match-note-renamed.txt")
    pathfm.wait(lambda: renamed.exists(), "the nested rename")
    assert renamed.read_text() == "beta source\n"
    assert not pathfm.fixture.path("beta/match-note.txt").exists()
    assert pathfm.fixture.path("alpha/match-note.txt").read_text() == "alpha source\n"
    assert pathfm.fixture.path("match-note.txt").read_text() == "root decoy\n"
    assert field.text == "match-note"
    pathfm.wait(lambda: result(pathfm, "beta/match-note-renamed.txt"), "the matching renamed result")
    pathfm.wait(lambda: result(pathfm, "beta/match-note.txt") is None, "the old result to leave")
    pathfm.pointer.click(field)
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("nothing-matches")
    pathfm.wait(lambda: not pathfm.matches(), "the empty query result")
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("renamed")
    row = pathfm.wait(lambda: result(pathfm, "beta/match-note-renamed.txt"), "the fresh index result")
    pathfm.pointer.right_click(row)
    items = pathfm.menu_items()
    assert items.index("Quick preview") < items.index("Open file location")
    pathfm.choose_menu_item("Open file location")
    pathfm.wait_for_directory("beta")
    pathfm.wait_for_selection(["match-note-renamed.txt"], "beta")


@pytest.mark.parametrize("mode", ALL_MODES)
def test_filtered_properties_rename_opens_the_result_inline(pathfm, mode):
    field = filter_results(pathfm)
    row = pathfm.wait(lambda: result(pathfm, "beta/match-note.txt"), "the beta result")
    pathfm.pointer.right_click(row)
    pathfm.choose_menu_item("Properties")
    dialog = pathfm.wait_for_dialog()
    pathfm.pointer.click(dialog.find(role="button", name="Rename"))
    pathfm.wait(lambda: pathfm.dialog() is None, "properties dialog to close")
    rename = pathfm.editable_field()
    assert rename.text == "match-note.txt"
    assert field.text == "match-note"
    pathfm.keyboard.press("Escape")
    pathfm.wait(
        lambda: pathfm.window.find(role="text", name="Rename", states={"editable"}) is None,
        "inline rename to close",
    )
    assert pathfm.fixture.path("beta/match-note.txt").read_text() == "beta source\n"


@pytest.mark.parametrize("mode", ALL_MODES)
def test_delete_trashes_filtered_result_without_touching_hidden_selection(pathfm, mode):
    filter_results(pathfm)
    row = pathfm.wait(lambda: result(pathfm, "beta/match-note.txt"), "the beta result")
    pathfm.pointer.click(row, modifiers=("ctrl",))
    pathfm.keyboard.press("F2")
    pathfm.editable_field()
    pathfm.keyboard.press("Escape")
    pathfm.wait(lambda: result(pathfm, "beta/match-note.txt").has_state("focused"), "result focus")
    pathfm.keyboard.press("Delete")
    pathfm.wait(
        lambda: not pathfm.fixture.path("beta/match-note.txt").exists(),
        "the selected result to be trashed",
    )
    assert pathfm.fixture.path("match-note.txt").read_text() == "root decoy\n"
    assert pathfm.fixture.path("alpha/match-note.txt").read_text() == "alpha source\n"


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("recursive", [
    pytest.param(False, marks=pytest.mark.preferences(filter_include_subfolders=False)),
    pytest.param(True, marks=pytest.mark.preferences(filter_include_subfolders=True)),
])
def test_filter_results_follow_external_changes(pathfm, mode, recursive):
    field = filter_results(pathfm, count=4 if recursive else 2)

    pathfm.fixture.path("match-note-new.txt").write_text("new\n")
    pathfm.wait(lambda: result(pathfm, "match-note-new.txt"), "an externally created hit")
    assert field.has_state("focused")
    assert field.text == "match-note"

    # Only the watched folder updates live; deeper changes wait for a refresh.
    pathfm.fixture.path("alpha/match-note-deep.txt").write_text("deep\n")
    pathfm.settle(field)
    assert result(pathfm, "alpha/match-note-deep.txt") is None
    pathfm.keyboard.press("F5")
    if recursive:
        pathfm.wait(lambda: result(pathfm, "alpha/match-note-deep.txt"), "F5 to re-index subfolders")
    pathfm.wait(lambda: len(pathfm.matches()) == (6 if recursive else 3), "the refreshed hits")
    if not recursive:
        assert result(pathfm, "alpha/match-note-deep.txt") is None
    pathfm.wait(lambda: field.has_state("focused"), "the filter field to keep focus across F5")
    assert field.text == "match-note"

    # The deleted hit is also the listing's cursor, whose removal must not move focus.
    pathfm.fixture.path("match-note.txt").unlink()
    pathfm.wait(
        lambda: pathfm.matches().count("match-note.txt") == (2 if recursive else 0),
        "the deleted hit to leave",
    )
    steady: list[bool] = []

    def keeps_focus() -> bool:
        steady.append(field.has_state("focused"))
        del steady[:-10]
        return len(steady) == 10 and all(steady)

    pathfm.wait(keeps_focus, "the filter field to keep focus after the deletion")

    pathfm.keyboard.press("Down")
    pathfm.wait(lambda: not field.has_state("focused"), "Down to leave the filter field")
    focused = pathfm.wait(pathfm.focused_node, "a focused widget")
    assert any(row.has_state("focused") for row in result_rows(pathfm)), focused.name
    assert "Shortcuts" not in focused.name
    if mode == "Columns":
        pathfm.keyboard.press("Return")
        pathfm.settle(focused)
        assert pathfm.window.find(role="label", name="Unable to open file") is None


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("query", ["", "no-such-result"])
def test_filter_rename_shortcuts_do_not_target_the_hidden_directory_selection(pathfm, mode, query):
    pathfm.select_entry("match-note.txt")
    pathfm.keyboard.press("ctrl+f")
    field = pathfm.editable_field()
    if query:
        pathfm.keyboard.type_text(query)
        pathfm.wait(lambda: len(pathfm.matches()) == 0, "no matching results")
        pathfm.keyboard.press("Down")
        assert field.has_state("focused")
        assert field.text == query
    for shortcut in ["F2", "ctrl+r"]:
        pathfm.keyboard.press(shortcut)
        pathfm.settle(field)
        assert pathfm.dialog() is None
        assert field.has_state("focused")
        assert field.text == query
    assert pathfm.fixture.path("match-note.txt").read_text() == "root decoy\n"


@pytest.mark.parametrize("mode", ALL_MODES)
def test_filtered_thumbnail_stays_rendered_across_updates_and_rename(pathfm, mode, tmp_path):
    pathfm.keyboard.press("ctrl+f")
    field = pathfm.editable_field()
    pathfm.keyboard.type_text("thumb")
    pathfm.wait(lambda: len(pathfm.matches()) == 2, "image and text results")
    row = result(pathfm, "beta/thumb.png")
    assert row is not None
    pathfm.pointer.click(row, modifiers=("ctrl",))
    pathfm.pointer.click(field)
    icon = row.find(role="image")
    assert icon is not None

    def thumbnail_pixel():
        bounds = pathfm.settle(icon).screen_bounds()
        capture = pathfm.screenshot(tmp_path / "thumbnail.png")
        with Image.open(capture) as image:
            return image.convert("RGB").getpixel(bounds.center)

    pathfm.wait(lambda: thumbnail_pixel() == (230, 40, 60), "the generated red thumbnail")
    for query, count in [("thumb.p", 1), ("thumb", 2)]:
        pathfm.keyboard.press("ctrl+a")
        pathfm.keyboard.type_text(query)
        pathfm.wait(lambda: len(pathfm.matches()) == count, "updated image results")
        assert row.has_state("selected")
        # AT-SPI result updates can precede the corresponding rendered frame.
        pathfm.wait(lambda: thumbnail_pixel() == (230, 40, 60), "the updated red thumbnail")
        assert field.has_state("focused")

    original = pathfm.fixture.path("beta/thumb.png").read_bytes()
    pathfm.keyboard.press("Down")
    pathfm.keyboard.press("F2")
    pathfm.editable_field()
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("thumb-renamed.png")
    pathfm.keyboard.press("Return")
    renamed = pathfm.fixture.path("beta/thumb-renamed.png")
    pathfm.wait(lambda: renamed.exists(), "the image rename")
    assert renamed.read_bytes() == original
    assert not pathfm.fixture.path("beta/thumb.png").exists()
    assert field.text == "thumb"
    row = pathfm.wait(lambda: result(pathfm, "beta/thumb-renamed.png"), "the renamed image result")
    icon = row.find(role="image")
    assert icon is not None
    pathfm.wait(lambda: thumbnail_pixel() == (230, 40, 60), "the renamed red thumbnail")


@pytest.mark.preferences(
    tenxer_mode=True,
    type_to_search=False,
    single_click_previews=False,
    filter_include_subfolders=False,
)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_tenxer_escape_leaves_visual_and_preview_before_search_results(pathfm, mode):
    def footer_mark(name):
        return pathfm.window.find(role="label", name=name) is not None

    pathfm.select_entry("match-note.txt")
    everything = pathfm.entry_names()
    pathfm.keyboard.press("f")
    pathfm.editable_field()
    pathfm.keyboard.type_text("other")
    pathfm.keyboard.press("Return")
    pathfm.wait(lambda: footer_mark("filter: other"), "the filter to commit")
    pathfm.keyboard.press("s")
    pathfm.editable_field()
    pathfm.keyboard.type_text("only")
    pathfm.keyboard.press("Return")
    pathfm.wait(lambda: footer_mark("search: only"), "the search to apply")
    pathfm.wait_for_focused_entry("only-match.txt")
    pathfm.keyboard.press("i")
    pathfm.wait(pathfm.preview, "i to preview the hit")
    pathfm.keyboard.press("v")
    pathfm.wait(lambda: footer_mark("Visual select"), "v to start a range")

    pathfm.keyboard.press("Escape")
    pathfm.wait(lambda: not footer_mark("Visual select"), "Esc to leave visual mode")
    assert footer_mark("search: only")
    assert pathfm.preview() is not None
    assert pathfm.matches() == ["only-match.txt"]

    pathfm.keyboard.press("Escape")
    pathfm.wait(lambda: pathfm.preview() is None, "Esc to close the preview")
    assert footer_mark("search: only")
    pathfm.wait_for_focused_entry("only-match.txt")

    pathfm.keyboard.press("Escape")
    pathfm.wait(
        lambda: footer_mark("filter: other") and not footer_mark("search: only"),
        "Esc to dismiss the hits and restore the filter",
    )
    pathfm.wait(lambda: pathfm.matches() == ["match-note-other.md"], "the restored filter")

    pathfm.keyboard.press("Escape")
    pathfm.wait(lambda: not footer_mark("filter: other"), "Esc to clear the restored filter")
    pathfm.wait(lambda: pathfm.entry_names() == everything, "the full listing")
