# SPDX-License-Identifier: MIT
"""Type-to-search, pane filtering, sorting, and hidden files."""

from __future__ import annotations

import pytest

from harness.keyboard_layout import RUSSIAN_ONLY, US
from harness.modes import ALL_MODES, COLUMNS_AND_ONE

ROOT_ENTRIES = ["archive", "documents", "pictures", "readme.md", "todo.txt"]
# Folders stay grouped first, so descending is not simply the reverse.
ROOT_ENTRIES_DESCENDING = ["pictures", "documents", "archive", "todo.txt", "readme.md"]
DOUBLE_CLICK_PREFERENCES = {
    "list_folder_clicks": 2,
    "list_file_clicks": 2,
    "grid_folder_clicks": 2,
    "grid_file_clicks": 2,
    "explorer_folder_clicks": 2,
    "explorer_file_clicks": 2,
    "single_click_previews": True,
}
DOUBLE_CLICK = pytest.mark.preferences(**DOUBLE_CLICK_PREFERENCES)


@pytest.fixture
def launch_counter(test_environment):
    applications = test_environment.data_home / "applications"
    applications.mkdir()
    launches = test_environment.root / "filtered-launches"
    launcher = test_environment.root / "record-filtered-launch"
    launcher.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" >> "{launches}"\n')
    launcher.chmod(0o755)
    (applications / "pathfm-filtered.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Filtered Result Viewer\n"
        f"Exec={launcher} %U\nMimeType=text/csv;\nNoDisplay=true\n"
    )
    (test_environment.config_home / "mimeapps.list").write_text(
        "[Default Applications]\ntext/csv=pathfm-filtered.desktop;\n"
        "[Added Associations]\ntext/csv=pathfm-filtered.desktop;\n"
    )
    return launches


@pytest.fixture
def root(pathfm) -> str:
    return pathfm.fixture.root.name


@pytest.mark.parametrize("mode", ALL_MODES)
def test_type_to_search_finds_matches_anywhere_in_the_tree(pathfm, mode, root):
    pathfm.select_entry("readme.md", directory=root)

    pathfm.keyboard.type_text("photo")

    field = pathfm.editable_field()
    pathfm.wait(lambda: field.text == "photo", "the typed query to reach the search box")
    pathfm.wait(
        lambda: pathfm.matches(root) == ["photo.txt"],
        "the search to list the nested match",
    )

    pathfm.keyboard.press("Escape")
    pathfm.wait(
        lambda: pathfm.entry_names(root) == ROOT_ENTRIES,
        "Escape to restore the directory listing",
    )


# Escape from the field and from a focused result. Recursive hits (the default) and the
# in-place Columns filter (Include subfolders off) are separate result routes in Columns;
# Icons and List show both in the same results view.
ESCAPE_CASES = [
    *[
        pytest.param(
            mode.values[0], route, "spreadsheet", "spreadsheet.csv",
            marks=mode.marks, id=f"{mode.id}-{route}",
        )
        for mode in ALL_MODES
        for route in ("input", "result")
    ],
    pytest.param(
        "Columns", "result", "todo", "todo.txt",
        marks=pytest.mark.preferences(browser_mode="columns", filter_include_subfolders=False),
        id="columns-result-in-place",
    ),
]


@pytest.mark.parametrize("mode,route,query,match", ESCAPE_CASES)
def test_filtering_a_pane_narrows_the_listing(pathfm, mode, route, query, match, root):
    pathfm.select_entry("readme.md", directory=root)
    pathfm.wait(
        lambda: footer_label(pathfm, "1 file selected (10 B)") is not None,
        "the footer to describe the directory selection",
    )

    pathfm.keyboard.press("ctrl+f")
    field = pathfm.editable_field()
    pathfm.keyboard.type_text(query)
    pathfm.wait(lambda: field.text == query, "the filter query to be typed")

    pathfm.wait(
        lambda: pathfm.matches(root) == [match],
        "the filter to list only matching entries",
    )
    pathfm.wait(
        lambda: footer_label(pathfm, "1 item") is not None
        and footer_label(pathfm, "1 file selected (10 B)") is None,
        "the footer to report the displayed result total",
    )
    assert footer_label(pathfm, f"filter: {query}") is None
    if route == "input":
        pathfm.keyboard.press("ctrl+a")
        pathfm.keyboard.type_text("zzz")
        pathfm.wait(lambda: field.text == "zzz", "the miss query to be typed")
        pathfm.wait(
            lambda: footer_label(pathfm, "0 items") is not None,
            "the footer to report 0 items on a miss",
        )
        pathfm.keyboard.press("ctrl+a")
        pathfm.keyboard.type_text(query)
        pathfm.wait(
            lambda: pathfm.matches(root) == [match] and footer_label(pathfm, "1 item") is not None,
            "the original query to list its match again",
        )
    if route == "result":
        pathfm.keyboard.press("Down")
        pathfm.wait_for_focused_entry(match)
        assert not field.has_state("focused")

    pathfm.keyboard.press("Escape")
    pathfm.wait(
        lambda: pathfm.entry_names(root) == ROOT_ENTRIES,
        "Escape to restore the full listing",
    )
    # The directory's own selection and cursor return, whichever result had focus.
    pathfm.wait_for_focused_entry("readme.md")
    pathfm.wait(
        lambda: pathfm.selected_names(root) == ["readme.md"],
        "the listing to show the directory's selection",
    )
    assert pathfm.window.find(role="text", states={"editable", "focused"}) is None
    pathfm.wait(
        lambda: footer_label(pathfm, "1 file selected (10 B)") is not None,
        "the footer to describe the directory selection again",
    )


def footer_label(pathfm, text):
    return pathfm.window.find(role="label", name=text)


@pytest.fixture
def pattern_files(fixture_tree):
    photos = fixture_tree.path("Photos")
    photos.mkdir()
    (photos / "album.MOV").mkdir()
    for name in [
        "clip.MOV", "IMG_001.MOV", "IMG_001.jpg", "clip.MOV.bak", ".hidden.MOV",
        "album.MOV/deep.MOV", "album.MOV/unrelated.txt",
    ]:
        (photos / name).write_text("fixture\n")


@pytest.mark.parametrize("preferences", [
    {"filter_include_subfolders": False},
    {"filter_include_subfolders": True},
], ids=["directory", "subfolders"])
@pytest.mark.parametrize("mode", ALL_MODES)
def test_wildcard_filter_patterns_preserve_scope_and_clear(
    pattern_files, pathfm, mode, preferences,
):
    pathfm.open_directory("Photos")
    pathfm.select_entry("clip.MOV.bak", directory="Photos")
    original = {"album.MOV", "clip.MOV", "IMG_001.MOV", "IMG_001.jpg", "clip.MOV.bak"}
    pathfm.keyboard.press("ctrl+f")
    field = pathfm.editable_field()
    recursive = preferences["filter_include_subfolders"]
    for query, expected in [
        ("*.MOV", {"album.MOV", "clip.MOV", "IMG_001.MOV"} | ({"deep.MOV"} if recursive else set())),
        ("IMG*", {"IMG_001.MOV", "IMG_001.jpg"}),
        ("IMG*.MOV", {"IMG_001.MOV"}),
        ("IMG*_001*.mov", {"IMG_001.MOV"}),
        ("*.MOV.b", set()),
        ("*.MOV.b*", {"clip.MOV.bak"}),
        ("*.MOV.b", set()),
        (".MOV.b", {"clip.MOV.bak"}),
        ("*", original | ({"deep.MOV", "unrelated.txt"} if recursive else set())),
    ]:
        pathfm.keyboard.press("ctrl+a")
        pathfm.keyboard.type_text(query)
        pathfm.wait(lambda: field.text == query, "the wildcard query to be typed")
        pathfm.wait(
            lambda: set(pathfm.matches("Photos")) == expected,
            f"wildcard results for {query} (subfolders={recursive})",
        )
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.press("BackSpace")
    pathfm.wait(lambda: field.text == "", "the query to clear")
    pathfm.wait(
        lambda: set(pathfm.entry_names("Photos")) == original,
        "clearing the wildcard to restore the listing without hidden or nested entries",
    )


def assert_filtered_result_opens(pathfm):
    pathfm.select_entry("documents")
    pathfm.keyboard.press("ctrl+f")
    field = pathfm.editable_field()
    pathfm.keyboard.type_text("doc*ments")
    pathfm.wait(lambda: field.text == "doc*ments", "the filter query")
    result = pathfm.wait(
        lambda: pathfm.search_result("documents"),
        "the filtered folder result",
    )
    pathfm.pointer.click(result)
    pathfm.wait_for_directory("documents")


@pytest.mark.preferences(
    **DOUBLE_CLICK_PREFERENCES, filter_include_subfolders=False
)
@pytest.mark.parametrize("mode", COLUMNS_AND_ONE)
def test_local_filtered_results_open_with_one_activation(pathfm, mode):
    assert_filtered_result_opens(pathfm)


@DOUBLE_CLICK
@pytest.mark.parametrize("mode", COLUMNS_AND_ONE)
def test_recursive_filtered_results_open_with_one_activation(pathfm, mode):
    assert_filtered_result_opens(pathfm)


@DOUBLE_CLICK
@pytest.mark.preferences(browser_mode="list")
def test_recursive_file_double_click_launches_once(launch_counter, pathfm):
    pathfm.keyboard.press("ctrl+f")
    field = pathfm.editable_field()
    pathfm.keyboard.type_text("spreadsheet")
    result = pathfm.wait(
        lambda: pathfm.search_result("spreadsheet.csv"),
        "the recursive file result",
    )

    pathfm.pointer.double_click(result)
    pathfm.wait(
        lambda: launch_counter.exists() and len(launch_counter.read_text().splitlines()) >= 1,
        "the file launch",
    )
    pathfm.keyboard.press("ctrl+f")
    pathfm.wait(lambda: field.has_state("focused"), "focus to return to the filter")
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("photo")
    pathfm.wait(lambda: field.text == "photo", "the follow-up query")
    pathfm.wait(
        lambda: pathfm.search_result("photo.txt") is not None,
        "the follow-up results",
    )
    assert len(launch_counter.read_text().splitlines()) == 1


@pytest.mark.parametrize("mode", ALL_MODES)
def test_filtered_result_waits_for_release_before_launching(launch_counter, pathfm, mode):
    pathfm.keyboard.press("ctrl+f")
    field = pathfm.editable_field()
    pathfm.keyboard.type_text("spreadsheet")
    pathfm.wait(lambda: field.text == "spreadsheet", "the filter query")
    result = pathfm.wait(
        lambda: pathfm.search_result("spreadsheet.csv"),
        "the filtered file result",
    )

    def assert_not_launched_on_press():
        assert not launch_counter.exists(), "a held press must not launch the file"

    start = pathfm.pointer.drag_origin(result)
    end = (start[0] + 40, start[1] + 40)
    pathfm.pointer.drag_points(
        start, end, release=False, after_press=assert_not_launched_on_press
    )
    try:
        assert not launch_counter.exists(), "crossing the drag threshold must not launch the file"
    finally:
        pathfm.pointer.connection.button(1, False)


@pytest.mark.preferences(filter_include_subfolders=False)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_directory_only_filter_matches_immediate_files_and_folders(pathfm, mode, root):
    pathfm.select_entry("readme.md", directory=root)
    pathfm.keyboard.press("ctrl+f")
    field = pathfm.editable_field()
    for query, expected in [
        ("txt", ["todo.txt"]),
        ("photo", []),
        ("archive", ["archive"]),
    ]:
        pathfm.keyboard.press("ctrl+a")
        pathfm.keyboard.type_text(query)
        pathfm.wait(lambda: field.text == query, "the filter query to be typed")
        pathfm.wait(
            lambda: pathfm.matches(root) == expected,
            f"directory-only matches for {query}",
        )
    pathfm.keyboard.press("Escape")
    pathfm.wait(lambda: pathfm.entry_names(root) == ROOT_ENTRIES, "the listing to return")


def test_dismissing_a_filter_keeps_hidden_files_hidden(pathfm, root):
    """A cleared query must not also clear the dotfile filter."""

    assert ".hidden.txt" not in pathfm.entry_names(root)

    pathfm.select_entry("readme.md", directory=root)
    pathfm.keyboard.press("ctrl+f")
    pathfm.editable_field()
    pathfm.keyboard.type_text("readme")
    pathfm.wait(
        lambda: pathfm.matches(root) == ["readme.md"],
        "the filter to narrow the listing",
    )
    pathfm.keyboard.press("Escape")

    pathfm.wait(
        lambda: pathfm.entry_names(root) == ROOT_ENTRIES,
        "the listing to come back without hidden files",
    )


def test_hidden_files_toggle(pathfm, root):
    assert ".hidden.txt" not in pathfm.entry_names(root)

    pathfm.keyboard.press("ctrl+h")

    pathfm.wait(
        lambda: ".hidden.txt" in pathfm.entry_names(root),
        "Ctrl+H to reveal hidden files",
    )

    pathfm.keyboard.press("ctrl+h")
    pathfm.wait(
        lambda: ".hidden.txt" not in pathfm.entry_names(root),
        "Ctrl+H to hide them again",
    )


def test_reversing_the_sort_direction(pathfm, root):
    assert pathfm.entry_names(root) == ROOT_ENTRIES

    pathfm.pointer.click(pathfm.header_button("Ascending — click to reverse"))

    pathfm.wait(
        lambda: pathfm.entry_names(root) == ROOT_ENTRIES_DESCENDING,
        "the pane to sort descending with folders still grouped first",
    )

    pathfm.pointer.click(pathfm.header_button("Descending — click to reverse"))
    pathfm.wait(
        lambda: pathfm.entry_names(root) == ROOT_ENTRIES,
        "the pane to sort ascending again",
    )


def test_sorting_by_size_reorders_the_files(pathfm, root):
    pathfm.pointer.click(pathfm.header_button("Choose sort field"))
    pathfm.pointer.click(
        pathfm.wait(
            lambda: pathfm.window.find(role="radio menu item", name="Size"),
            "the Size sort option",
        )
    )

    pathfm.wait(
        lambda: pathfm.entry_names(root)[-2:] == ["todo.txt", "readme.md"],
        "the files to be ordered by size",
    )


def test_global_search_arrows_keep_typing_in_the_query_and_enter_opens_selection(pathfm):
    names = [
        "navigation-alpha",
        "navigation-beta",
        "navigation-final",
        "navigation-gamma",
    ]
    for name in names:
        (pathfm.environment.home / name).mkdir()

    pathfm.keyboard.press("ctrl+k")
    field = pathfm.editable_field()
    pathfm.keyboard.type_text("nav")
    pathfm.wait(lambda: field.text == "nav", "the initial global-search query")
    pathfm.wait(
        lambda: all(
            pathfm.window.find(role="label", name=name) is not None for name in names
        ),
        "all navigation results to be indexed",
    )

    results = [
        node
        for node in pathfm.window.find_all(role="list item")
        if any(node.name.endswith(f"/{name}") for name in names)
    ]
    assert len(results) == len(names)
    assert results[0].has_state("selected")
    pathfm.keyboard.press("Down")
    pathfm.wait(
        lambda: results[1].has_state("selected"),
        "the first Down press to advance past the preselected result",
    )
    for _ in range(2):
        pathfm.keyboard.press("Down")
    pathfm.keyboard.type_text("igation-final")
    pathfm.wait(
        lambda: field.text == "navigation-final",
        "typing after arrow navigation to extend the query",
    )
    result = pathfm.wait(
        lambda: next(
            (
                node
                for node in pathfm.window.find_all(role="list item")
                if node.name.endswith("/navigation-final")
            ),
            None,
        ),
        "the refined selected result",
    )
    pathfm.wait(
        lambda: result.has_state("selected"),
        "the refined result to be selected",
    )
    pathfm.keyboard.press("Return")
    pathfm.wait_for_directory("navigation-final")


@pytest.mark.preferences(search_open_files_directly=False)
def test_global_search_preview_follows_neighbor_when_same_folder_result_is_deleted(pathfm):
    folder = pathfm.environment.home / "preview-deletion"
    folder.mkdir()
    previewed = folder / "preview-deletion-fixture.txt"
    previewed.write_text("search preview deletion fixture\n")
    (folder / "remaining.txt").write_text("remaining file\n")
    pathfm.keyboard.press("ctrl+l")
    pathfm.keyboard.type_text(str(folder))
    pathfm.keyboard.press("Return")
    pathfm.wait_for_directory(folder.name)
    pathfm.wait(lambda: "remaining.txt" in pathfm.entry_names(), "loaded folder")
    pathfm.keyboard.press("ctrl+k")
    pathfm.keyboard.type_text("preview-deletion-fixture")
    pathfm.wait(
        lambda: pathfm.window.find(role="label", name=previewed.name) is not None,
        "indexed search result",
    )
    pathfm.keyboard.press("Return")
    pathfm.wait(
        lambda: pathfm.preview_shows("search preview deletion fixture"),
        "search result preview",
    )
    previewed.unlink()
    pathfm.wait(
        lambda: pathfm.preview_shows("remaining file"),
        "deleted result preview to follow the remaining file",
    )
    assert "remaining.txt" in pathfm.entry_names()


def create_activation_folder(pathfm, name):
    parent = pathfm.environment.home / name
    parent.mkdir()
    for sibling in ("alpha.txt", "zeta.txt"):
        (parent / sibling).write_text(f"{sibling}\n")
    target = parent / "omega-target.txt"
    target.write_text("activation target preview\n")
    return parent, target


def open_typed_folder(pathfm, folder):
    pathfm.keyboard.press("ctrl+l")
    field = pathfm.editable_field()
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text(str(folder))
    pathfm.wait(lambda: field.text == str(folder), "the typed folder path")
    pathfm.keyboard.press("Return")
    pathfm.wait_for_directory(folder.name)


def search_for(pathfm, target):
    pathfm.keyboard.press("ctrl+k")
    pathfm.editable_field()
    pathfm.keyboard.type_text(target.stem)
    return pathfm.wait(
        lambda: next(
            (node for node in pathfm.window.find_all(role="list item")
             if node.name.endswith(f"/{target.name}")),
            None,
        ),
        "global search result",
    )


@pytest.mark.preferences(search_open_files_directly=False)
@pytest.mark.parametrize("visited", [
    pytest.param(False, marks=pytest.mark.preferences(browser_mode="columns"), id="columns"),
    pytest.param(False, marks=pytest.mark.preferences(browser_mode="icons"), id="icons"),
    pytest.param(False, marks=pytest.mark.preferences(browser_mode="list"), id="list"),
    pytest.param(True, marks=pytest.mark.preferences(browser_mode="list"), id="list-visited"),
])
def test_global_search_activation_selects_and_previews_the_file_result(pathfm, visited):
    parent, target = create_activation_folder(pathfm, "activation-parent")
    if visited:
        open_typed_folder(pathfm, parent)
        pathfm.wait_for_focused_entry("alpha.txt")
        pathfm.keyboard.press("alt+Left")
        pathfm.wait_for_directory(pathfm.fixture.root.name)
    search_for(pathfm, target)
    pathfm.keyboard.press("Return")
    pathfm.wait_for_directory(parent.name)
    pathfm.wait_for_selection([target.name], directory=parent.name)
    pathfm.wait_for_focused_entry(target.name)
    pathfm.wait(
        lambda: pathfm.preview_shows("activation target preview"),
        "the activated file's preview",
    )


@pytest.mark.preferences(search_open_files_directly=False)
def test_global_search_activation_in_the_open_folder_moves_the_selection(pathfm):
    parent, target = create_activation_folder(pathfm, "activation-same-folder")
    open_typed_folder(pathfm, parent)
    pathfm.wait_for_selection(["alpha.txt"])
    search_for(pathfm, target)
    pathfm.keyboard.press("Return")
    pathfm.wait_for_selection([target.name], directory=parent.name)
    pathfm.wait(
        lambda: pathfm.preview_shows("activation target preview"),
        "the activated file's preview",
    )


@pytest.mark.preferences(browser_mode="list")
def test_global_search_reveal_into_a_visited_list_folder_keeps_the_target(pathfm):
    parent, target = create_activation_folder(pathfm, "reveal-visited-parent")
    open_typed_folder(pathfm, parent)
    pathfm.wait_for_focused_entry("alpha.txt")
    pathfm.keyboard.press("End")
    pathfm.wait_for_focused_entry("zeta.txt")
    pathfm.keyboard.press("alt+Left")
    pathfm.wait_for_directory(pathfm.fixture.root.name)
    search_for(pathfm, target)
    pathfm.keyboard.press("alt+Return")
    pathfm.wait_for_directory(parent.name)
    pathfm.wait_for_selection([target.name], directory=parent.name)
    pathfm.wait_for_focused_entry(target.name)


# With no Latin layout configured, GTK's own matching finds no K key.
@pytest.mark.parametrize("layout", [US, RUSSIAN_ONLY], ids=lambda layout: layout.name)
def test_global_search_finds_a_file_under_home(pathfm, keyboard_layout, root, layout):
    """Ctrl+K searches the home directory, not the browsed location."""

    nested = pathfm.environment.home / "reports" / "quarterly-summary.txt"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text("summary\n")

    with keyboard_layout(layout):
        pathfm.keyboard.press("ctrl+k")
        field = pathfm.editable_field()
    pathfm.keyboard.type_text("quarterly")
    pathfm.wait(lambda: field.text == "quarterly", "the query to be typed")

    pathfm.wait(
        lambda: any(
            node.name == "quarterly-summary.txt"
            for node in pathfm.window.find_all(role="label")
        ),
        "the file under home to appear in the search results",
    )

    pathfm.keyboard.press("Escape")
    pathfm.wait(
        lambda: pathfm.window.find(role="text", states={"editable"}) is None,
        "Escape to close the search palette",
    )


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("directory", [False, True], ids=["file", "directory"])
@pytest.mark.parametrize("route", ["menu", "shortcut"])
def test_global_search_reveal(pathfm, mode, directory, route):
    parent = pathfm.environment.home / "reveal-parent"
    parent.mkdir()
    target = parent / "reveal-target"
    if directory:
        target.mkdir()
    else:
        target.write_text("reveal without opening\n")
    pathfm.keyboard.press("ctrl+k")
    field = pathfm.editable_field()
    pathfm.keyboard.type_text(target.name)
    result = pathfm.wait(
        lambda: next(
            (node for node in pathfm.window.find_all(role="list item")
             if node.name.endswith(f"/{target.name}")),
            None,
        ),
        "global search result",
    )
    if route == "shortcut":
        pathfm.keyboard.press("alt+Return")
    else:
        pathfm.pointer.right_click(result)
        pathfm.wait(
            lambda: pathfm.window.find(role="menu item", name="Open containing folder"),
            "reveal context menu",
        )
        assert field.text == target.name
        assert pathfm.window.find(role="text", states={"editable"}) is not None
        pathfm.keyboard.press("Escape")
        pathfm.wait(
            lambda: pathfm.window.find(role="menu item", name="Open containing folder") is None,
            "dismissed menu",
        )
        assert field.text == target.name
        pathfm.pointer.right_click(result)
        reveal = pathfm.wait(
            lambda: pathfm.window.find(role="menu item", name="Open containing folder"),
            "reopened reveal menu",
        )
        pathfm.pointer.click(reveal)
    pathfm.wait_for_directory(parent.name)
    pathfm.wait_for_selection([target.name], directory=parent.name)
    pathfm.wait_for_focused_entry(target.name)
    assert pathfm.window.find(role="text", states={"editable"}) is None


@pytest.mark.preferences(tenxer_mode=True, type_to_search=False, single_click_previews=False)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_tenxer_footer_find_moves_the_cursor_without_hiding_rows(pathfm, mode, root):
    pathfm.keyboard.press("Home")
    pathfm.wait_for_focused_entry("archive")

    pathfm.keyboard.press("/")
    field = pathfm.editable_field()
    pathfm.keyboard.type_text("do")
    pathfm.wait(lambda: field.text == "do", "the find query to stay in the footer prompt")
    assert pathfm.entry_names(root) == ROOT_ENTRIES
    pathfm.keyboard.press("Return")
    pathfm.wait_for_focused_entry("documents")

    for key, expected in (("n", "todo.txt"), ("n", "documents"), ("N", "todo.txt")):
        pathfm.keyboard.press(key)
        pathfm.wait_for_focused_entry(expected)
    assert pathfm.entry_names(root) == ROOT_ENTRIES

    pathfm.keyboard.press("?")
    pathfm.keyboard.type_text("zzz")
    pathfm.keyboard.press("Return")
    pathfm.wait(
        lambda: pathfm.window.find(role="label", name="No matches for “zzz”")
        is not None,
        "a miss to be reported",
    )
    pathfm.wait_for_focused_entry("todo.txt")

    pathfm.keyboard.press("/")
    pathfm.editable_field()
    pathfm.keyboard.type_text("j")
    pathfm.click_entry("readme.md", root)
    pathfm.wait_for_selection(["readme.md"], root)
    pathfm.wait(
        lambda: pathfm.window.find(role="text", states={"editable", "focused"}) is None,
        "clicking a row to close the prompt",
    )
    pathfm.wait_for_focused_entry("readme.md")
    assert pathfm.entry_names(root) == ROOT_ENTRIES


@pytest.mark.preferences(
    tenxer_mode=True,
    type_to_search=False,
    single_click_previews=False,
    filter_include_subfolders=False,
)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_tenxer_footer_filter_commits_reopens_and_clears(pathfm, mode, root):
    pathfm.select_entry("readme.md", directory=root)

    pathfm.keyboard.press("f")
    field = pathfm.editable_field()
    pathfm.keyboard.type_text("do")
    pathfm.wait(lambda: field.text == "do", "the filter query to stay in the footer prompt")
    pathfm.wait(
        lambda: pathfm.matches(root) == ["documents", "todo.txt"],
        "the filter to hide non-matches while typing",
    )
    pathfm.keyboard.press("Return")
    pathfm.wait(
        lambda: pathfm.window.find(role="text", states={"editable", "focused"}) is None
        and pathfm.window.find(role="label", name="filter: do") is not None,
        "Enter to commit the filter into the footer",
    )
    pathfm.wait(
        lambda: pathfm.focused_name() in ("documents", "todo.txt"),
        "focus to return to the filtered results",
    )

    pathfm.keyboard.press("f")
    field = pathfm.editable_field()
    pathfm.wait(lambda: field.text == "do", "f to pre-fill the committed query")
    pathfm.keyboard.press("Escape")
    pathfm.wait(
        lambda: pathfm.entry_names(root) == ROOT_ENTRIES,
        "Escape in the prompt to clear the filter",
    )
    pathfm.wait(
        lambda: pathfm.window.find(role="label", name="filter: do") is None,
        "the footer to drop the filter mark",
    )
    pathfm.wait_for_selection(["readme.md"], root)


@pytest.mark.preferences(
    tenxer_mode=True,
    type_to_search=False,
    single_click_previews=False,
    filter_include_subfolders=False,
)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_tenxer_footer_search_covers_subfolders_and_restores_the_filter(pathfm, mode, root):
    pathfm.select_entry("readme.md", directory=root)
    pathfm.keyboard.press("f")
    pathfm.editable_field()
    pathfm.keyboard.type_text("do")
    pathfm.keyboard.press("Return")
    pathfm.wait(
        lambda: pathfm.window.find(role="label", name="filter: do") is not None,
        "the filter to commit",
    )

    pathfm.keyboard.press("s")
    field = pathfm.editable_field()
    pathfm.keyboard.type_text("photo")
    pathfm.wait(lambda: field.text == "photo", "the search query to stay in the prompt")
    pathfm.wait(
        lambda: pathfm.matches(root) == ["photo.txt"],
        "the search to list the nested match with Include subfolders off",
    )
    pathfm.keyboard.press("Return")
    pathfm.wait(
        lambda: pathfm.window.find(role="text", states={"editable", "focused"}) is None
        and pathfm.window.find(role="label", name="search: photo") is not None,
        "Enter to apply the search into the footer",
    )
    pathfm.wait_for_focused_entry("photo.txt")

    pathfm.keyboard.press("Escape")
    pathfm.wait(
        lambda: pathfm.matches(root) == ["documents", "todo.txt"],
        "listing Escape to restore the earlier filter",
    )
    pathfm.wait(
        lambda: pathfm.window.find(role="label", name="filter: do") is not None
        and pathfm.window.find(role="label", name="search: photo") is None,
        "the footer to show the restored filter",
    )


TXT_HITS = {
    "notes.txt": "documents/notes.txt",
    "diagram.txt": "pictures/diagram.txt",
    "photo.txt": "pictures/photo.txt",
    "todo.txt": "todo.txt",
}


def footer_hit(pathfm):
    """The hit path beside the footer's search mark: folder and name labels."""
    mark = pathfm.window.find(role="label", name="search: txt")
    if mark is None or mark.parent is None:
        return None
    for part in mark.parent.children:
        if part.role != "panel":
            continue
        text = "".join(
            label.name for label in part.children if label.role == "label" and label.is_rendered()
        )
        if text in TXT_HITS.values():
            return text
    return None


@pytest.mark.preferences(
    tenxer_mode=True,
    type_to_search=False,
    single_click_previews=False,
    filter_include_subfolders=False,
)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_tenxer_footer_hit_path_follows_the_cursor_over_a_fill(pathfm, mode, root):
    pathfm.keyboard.press("s")
    field = pathfm.editable_field()
    pathfm.keyboard.type_text("txt")
    pathfm.wait(lambda: field.text == "txt", "the search query to stay in the prompt")
    pathfm.wait(
        lambda: sorted(pathfm.matches(root)) == sorted(TXT_HITS),
        "the search to list every .txt hit",
    )
    pathfm.keyboard.press("Return")
    order = pathfm.matches(root)
    pathfm.wait_for_focused_entry(order[0])
    pathfm.wait(
        lambda: footer_hit(pathfm) == TXT_HITS[order[0]],
        "the footer to show the first hit",
    )

    # Space focuses the next hit only once GTK lands focus there; the Rust
    # dispatch tests own the other cursor motions over a fill.
    pathfm.keyboard.press("space")
    pathfm.wait_for_focused_entry(order[1])
    pathfm.wait(
        lambda: footer_hit(pathfm) == TXT_HITS[order[1]],
        f"the footer hit to follow Space to {order[1]}",
    )


@pytest.mark.preferences(
    tenxer_mode=True,
    type_to_search=False,
    single_click_previews=False,
    filter_include_subfolders=False,
)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_tenxer_sort_chords_and_dot_keep_the_cursor(pathfm, mode, root):
    pathfm.select_entry_with_keyboard("readme.md")

    pathfm.keyboard.press(",")
    pathfm.wait(lambda: pathfm.window.find(role="label", name=",-") is not None, "the armed sort chord")
    pathfm.keyboard.press("s")
    pathfm.wait(
        lambda: pathfm.entry_names(root)[-2:] == ["todo.txt", "readme.md"],
        ", s to sort by size",
    )
    pathfm.keyboard.press(",")
    pathfm.keyboard.press("S")
    pathfm.wait(
        lambda: pathfm.entry_names(root)[-2:] == ["readme.md", "todo.txt"],
        ", S to reverse the size sort",
    )
    pathfm.wait_for_focused_entry("readme.md")

    before = pathfm.entry_names(root)
    pathfm.keyboard.press(",")
    pathfm.keyboard.press("n")
    pathfm.wait(lambda: pathfm.window.find(role="label", name="Unknown chord") is not None, ", n to cancel")
    assert pathfm.entry_names(root) == before
    assert pathfm.window.find(role="text", states={"editable", "focused"}) is None

    pathfm.keyboard.press(",")
    pathfm.keyboard.press("a")
    pathfm.wait(lambda: pathfm.entry_names(root) == ROOT_ENTRIES, ", a to sort by name")
    assert pathfm.window.find(role="text", states={"editable", "focused"}) is None, ", a creates nothing"
    pathfm.wait_for_focused_entry("readme.md")

    pathfm.keyboard.press(".")
    pathfm.wait(lambda: ".hidden.txt" in pathfm.entry_names(root), ". to show hidden files")
    pathfm.keyboard.press(".")
    pathfm.wait(lambda: ".hidden.txt" not in pathfm.entry_names(root), ". to hide them again")
    pathfm.wait_for_focused_entry("readme.md")
