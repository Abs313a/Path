# SPDX-License-Identifier: MIT
"""Opening locations directly and reacting to filesystem changes."""

from __future__ import annotations

import shutil

import pytest

from harness.modes import COLUMNS_AND_ONE


def test_typing_a_path_navigates_there(pathfm):
    pathfm.keyboard.press("ctrl+l")
    field = pathfm.editable_field()
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text(str(pathfm.fixture.path("documents")))
    pathfm.wait(
        lambda: field.text.endswith("documents"),
        "the path to be typed into the address bar",
    )
    pathfm.keyboard.press("Return")

    pathfm.wait_for_directory("documents")
    pathfm.entry("notes.txt", directory="documents")


@pytest.mark.parametrize("mode", COLUMNS_AND_ONE)
def test_typed_dot_segments_open_the_resolved_folder(pathfm, mode):
    pictures = pathfm.fixture.path("pictures")
    typed = pathfm.fixture.path("documents") / ".." / "pictures"

    pathfm.keyboard.press("ctrl+l")
    field = pathfm.editable_field()
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text(str(typed))
    pathfm.wait(lambda: field.text == str(typed), "the typed dotted path")
    pathfm.keyboard.press("Return")

    pathfm.wait_for_directory("pictures")
    pathfm.wait(
        lambda: pathfm.window.find(role="label", name="pictures", description=str(pictures)),
        "the current crumb to carry the resolved path",
    )
    assert pathfm.window.find(role="button", name="documents") is None
    pathfm.keyboard.press("alt+Up")
    pathfm.wait_for_directory(pathfm.fixture.root.name)


def test_named_location_controls_navigate_and_cancel(pathfm):
    pathfm.keyboard.press("ctrl+l")
    field = pathfm.window.find(role="text", name="Location (Ctrl+L)")
    assert field is not None, pathfm.window.dump()
    confirm = pathfm.window.find(role="button", name="Navigate (Enter)")
    cancel = pathfm.window.find(role="button", name="Cancel (Escape)")
    assert confirm is not None and cancel is not None, pathfm.window.dump()

    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text(str(pathfm.fixture.path("documents")))
    pathfm.wait(lambda: field.text.endswith("documents"), "typed location")
    pathfm.pointer.click(confirm)
    pathfm.wait_for_directory("documents")
    pathfm.entry("notes.txt", directory="documents")

    pathfm.keyboard.press("ctrl+l")
    cancel = pathfm.window.find(role="button", name="Cancel (Escape)")
    assert cancel is not None
    pathfm.pointer.click(cancel)
    pathfm.wait(
        lambda: pathfm.window.find(role="button", name="Navigate (Enter)") is None,
        "the location entry to close",
    )
    assert pathfm.window.find(role="text", name="Location (Ctrl+L)") is None
    pathfm.wait_for_directory("documents")


def test_a_breadcrumb_returns_to_the_parent(pathfm):
    pathfm.open_directory("documents")

    crumb = pathfm.wait(
        lambda: pathfm.window.find(role="button", name=pathfm.fixture.root.name),
        "the breadcrumb for the fixture root",
    )
    pathfm.pointer.click(crumb)

    pathfm.wait_for_directory(pathfm.fixture.root.name)


def test_current_breadcrumb_opens_hierarchy_instead_of_window_menu(pathfm):
    path = pathfm.fixture.root
    for index in range(6):
        path = path / f"deep-breadcrumb-component-{index}"
    path.mkdir(parents=True)
    pathfm.entry("deep-breadcrumb-component-0")
    pathfm.keyboard.press("ctrl+l")
    field = pathfm.editable_field()
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text(str(path))
    pathfm.wait(lambda: field.text == str(path), "typed location")
    pathfm.keyboard.press("Return")
    pathfm.wait_for_directory(path.name)
    label = pathfm.wait(
        lambda: pathfm.window.find(role="label", name=path.name),
        "current breadcrumb",
    )
    pathfm.pointer.click(label, button=3)
    pathfm.wait(
        lambda: pathfm.window.find(role="button", name=path.name),
        "current hierarchy item",
    )
    item = pathfm.window.find_all(role="button", name=path.parent.name)[-1]
    pathfm.pointer.click(item)
    pathfm.wait_for_directory(path.parent.name)


@pytest.fixture
def music_place(test_environment):
    home = test_environment.home
    music = home / "Audio Library"
    music.mkdir()
    (music / "song.txt").write_text("music\n")
    (test_environment.config_home / "user-dirs.dirs").write_text(
        'XDG_MUSIC_DIR="$HOME/Audio Library"\n'
    )
    return music


def test_a_sidebar_place_navigates_there(music_place, pathfm):
    home = pathfm.environment.home
    (home / "sidebar-target.txt").write_text("target\n")

    pathfm.pointer.click(pathfm.sidebar_button("Home"))

    pathfm.wait_for_directory(home.name)
    pathfm.entry("sidebar-target.txt")

    pathfm.pointer.click(pathfm.sidebar_button("Music"))
    pathfm.wait_for_directory(music_place.name)
    pathfm.entry("song.txt")


@pytest.fixture
def places(test_environment):
    """Downloads and Music exist; Documents is missing; pins are stored beta,
    Downloads (hidden as a standard place), alpha."""

    home = test_environment.home
    for name in ("Downloads", "Audio Library", "pins/beta", "pins/alpha"):
        (home / name).mkdir(parents=True)
    config = test_environment.config_home
    (config / "user-dirs.dirs").write_text(
        'XDG_DOWNLOAD_DIR="$HOME/Downloads"\n'
        'XDG_DOCUMENTS_DIR="$HOME/Documents"\n'
        'XDG_MUSIC_DIR="$HOME/Audio Library"\n'
    )
    (config / "gtk-3.0").mkdir(exist_ok=True)
    (config / "gtk-3.0" / "bookmarks").write_text(
        "".join(
            f"{(home / name).as_uri()} {label}\n"
            for name, label in (
                ("pins/beta", "Beta"),
                ("Downloads", "Downloads"),
                ("pins/alpha", "Alpha"),
            )
        )
    )
    return home


@pytest.mark.preferences(tenxer_mode=True, type_to_search=False)
def test_tenxer_go_chord_jumps_to_places_and_visible_pins(places, pathfm):
    root = pathfm.current_directory()

    for second, message in (
        ("k", "No Documents folder"),
        ("3", "No pin 3"),
        ("z", "Unknown chord"),
    ):
        pathfm.keyboard.press("g")
        pathfm.keyboard.press(second)
        pathfm.wait(
            lambda: pathfm.window.find(role="label", name=message) is not None,
            f"g {second} to report {message!r}",
        )
        assert pathfm.current_directory() == root

    for second, directory in (
        ("h", places.name),
        ("d", "Downloads"),
        ("m", "Audio Library"),
        ("2", "alpha"),
        ("1", "beta"),
    ):
        pathfm.keyboard.press("g")
        pathfm.keyboard.press(second)
        pathfm.wait_for_directory(directory)

    pathfm.keyboard.press("g")
    pathfm.keyboard.press("Escape")
    pathfm.keyboard.press("h")
    pathfm.wait_for_directory("pins")


@pytest.mark.preferences(tenxer_mode=True, type_to_search=False)
def test_tenxer_go_prompt_picks_folders_and_navigates(pathfm):
    (pathfm.fixture.path("documents") / "drafts").mkdir()

    pathfm.keyboard.press("g")
    pathfm.keyboard.press("space")
    field = pathfm.editable_field()
    assert pathfm.window.find(role="text", name="Go to a path or URI") is not None
    pathfm.keyboard.type_text("doc dr")
    pathfm.wait(
        lambda: pathfm.window.find(role="label", name="drafts") is not None,
        "the matching folder to be listed",
    )
    pathfm.keyboard.press("Tab")
    pathfm.wait(
        lambda: field.text == "./documents/drafts/",
        "Tab to write the chosen folder into the prompt",
    )
    assert pathfm.current_directory() != "drafts", "Tab never navigates"
    pathfm.keyboard.press("Return")
    pathfm.wait_for_directory("drafts")

    secret = "sftp://user:hunter2@inert.invalid/srv/"
    pathfm.keyboard.press("g")
    pathfm.keyboard.press("space")
    field = pathfm.editable_field()
    pathfm.keyboard.type_text(secret)
    pathfm.keyboard.press("Tab")
    assert field.text == secret, "Tab leaves a URI alone"
    pathfm.keyboard.press("Escape")
    pathfm.wait(
        lambda: pathfm.window.find(role="text", states={"editable", "focused"}) is None,
        "Escape to close the go prompt",
    )
    pathfm.wait_for_directory("drafts")

    pathfm.keyboard.press("g")
    pathfm.keyboard.press("space")
    field = pathfm.editable_field()
    assert field.text == "", "reopening recovers no typed text"
    pathfm.keyboard.press("Escape")


@pytest.mark.preferences(tenxer_mode=True, type_to_search=False)
def test_tenxer_history_prompts_jump_to_visited_folders(pathfm):
    for path, directory in (
        ("documents", "documents"),
        ("../pictures", "pictures"),
        ("../archive", "archive"),
    ):
        pathfm.keyboard.press("g")
        pathfm.keyboard.press("space")
        pathfm.editable_field()
        pathfm.keyboard.type_text(path)
        pathfm.keyboard.press("Return")
        pathfm.wait_for_directory(directory)

    pathfm.keyboard.press("z")
    field = pathfm.editable_field()
    assert pathfm.window.find(role="text", name="Jump to a visited folder") is not None
    pathfm.keyboard.type_text("qqqq")
    pathfm.wait(
        lambda: pathfm.window.find(role="label", name="No matching folders")
        is not None,
        "a miss to report no matching folders",
    )
    pathfm.keyboard.press("Return")
    assert pathfm.current_directory() == "archive", "a miss never navigates"
    for _ in "qqqq":
        pathfm.keyboard.press("BackSpace")
    pathfm.keyboard.type_text("doc")
    pathfm.wait(lambda: field.text == "doc", "the query to be typed")
    pathfm.keyboard.press("Return")
    pathfm.wait_for_directory("documents")

    pathfm.keyboard.press("shift+Z")
    assert (
        pathfm.window.find(role="text", name="Jump to a recently visited folder")
        is not None
    )
    pathfm.keyboard.press("Down")
    pathfm.keyboard.press("Escape")
    pathfm.wait(
        lambda: pathfm.window.find(role="text", states={"editable", "focused"}) is None,
        "Escape to close the recent prompt",
    )
    assert pathfm.current_directory() == "documents", "Escape opens nothing"

    pathfm.keyboard.press("shift+Z")
    pathfm.editable_field()
    pathfm.keyboard.type_text("arch")
    pathfm.keyboard.press("Return")
    pathfm.wait_for_directory("archive")


@pytest.mark.parametrize("mode", COLUMNS_AND_ONE)
def test_refresh_reconciles_external_file_creation_and_removal(pathfm, mode):
    pathfm.entry("todo.txt")
    pathfm.fixture.path("appeared-later.txt").write_text("new\n")
    pathfm.fixture.path("todo.txt").unlink()

    pathfm.keyboard.press("F5")

    pathfm.entry("appeared-later.txt")
    pathfm.wait_for_entry_gone("todo.txt")


def test_an_unreadable_location_reports_an_error(pathfm):
    blocked = pathfm.fixture.path("blocked")
    blocked.mkdir()
    blocked.chmod(0o000)
    try:
        pathfm.keyboard.press("F5")
        pathfm.select_entry("blocked")

        dialog = pathfm.wait_for_dialog()
        assert dialog.name == "Unable to open directory", (
            f"unexpected dialog {dialog.name!r}"
        )
        assert any(
            "do not have permission" in node.name
            for node in dialog.find_all(role="label")
        ), f"the dialog should give the reason\n{dialog.dump()}"

        pathfm.pointer.click(pathfm.dialog_button("Close"))
        pathfm.wait(lambda: pathfm.dialog() is None, "the dialog to close")
    finally:
        blocked.chmod(0o755)


# Columns opens a child folder as a second pane, whose parent pane already watches it;
# typing the path makes the folder the root (depth 0) column, like List and Icons.
OPEN_FOLDER_ROUTES = [
    pytest.param(
        "List", False, marks=pytest.mark.preferences(browser_mode="list"), id="list"
    ),
    pytest.param(
        "Columns",
        False,
        marks=pytest.mark.preferences(browser_mode="columns"),
        id="columns-child",
    ),
    pytest.param(
        "Columns",
        True,
        marks=pytest.mark.preferences(browser_mode="columns"),
        id="columns-root",
    ),
]


def _open_folder(pathfm, name, as_root):
    if not as_root:
        pathfm.open_directory(name)
        return
    target = pathfm.fixture.path(name)
    pathfm.keyboard.press("ctrl+l")
    field = pathfm.editable_field()
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text(str(target))
    pathfm.wait(lambda: field.text == str(target), "typed location")
    pathfm.keyboard.press("Return")
    pathfm.wait_for_directory(name)
    assert pathfm.pane_names() == [name]


# A move into another folder is a deletion for the browser; the Rust tests own its other routes.
DEPARTURES = [
    pytest.param(*route.values, "delete", marks=route.marks, id=f"{route.id}-delete")
    for route in OPEN_FOLDER_ROUTES
] + [
    pytest.param(
        "List",
        False,
        "move-into-another-folder",
        marks=pytest.mark.preferences(browser_mode="list"),
        id="list-move-into-another-folder",
    )
]


@pytest.mark.parametrize("mode, as_root, departure", DEPARTURES)
def test_deleting_the_open_folder_returns_to_its_parent(pathfm, mode, as_root, departure):
    _open_folder(pathfm, "documents", as_root)
    pathfm.entry("notes.txt")

    if departure == "delete":
        shutil.rmtree(pathfm.fixture.path("documents"))
    else:
        pathfm.fixture.path("documents").rename(pathfm.fixture.path("archive/documents"))

    pathfm.wait_for_directory(pathfm.fixture.root.name)
    pathfm.wait_for_entry_gone("documents")
    pathfm.entry("pictures")
    pathfm.fixture.path("documents").mkdir()
    pathfm.entry("documents")


@pytest.mark.parametrize("mode, as_root", OPEN_FOLDER_ROUTES)
def test_renaming_the_open_folder_follows_it(pathfm, mode, as_root):
    _open_folder(pathfm, "documents", as_root)
    pathfm.select_entry("report.md")

    pathfm.fixture.path("documents").rename(pathfm.fixture.path("documents-moved"))

    pathfm.wait_for_directory("documents-moved")
    pathfm.wait_for_selection(["report.md"])
    (pathfm.fixture.path("documents-moved") / "after-rename.txt").write_text("new\n")
    pathfm.entry("after-rename.txt")
    if mode == "Columns" and not as_root:
        assert pathfm.pane_names()[0] == pathfm.fixture.root.name


@pytest.mark.preferences(browser_mode="columns")
def test_deleting_the_open_root_closes_its_child_columns(pathfm):
    pathfm.fixture.path("documents/drafts").mkdir()
    (pathfm.fixture.path("documents/drafts") / "draft.txt").write_text("draft\n")
    _open_folder(pathfm, "documents", as_root=True)
    pathfm.open_directory("drafts")
    pathfm.entry("draft.txt")

    shutil.rmtree(pathfm.fixture.path("documents"))

    pathfm.wait(
        lambda: pathfm.pane_names() == [pathfm.fixture.root.name],
        "the path to collapse to the fixture root",
    )
    pathfm.entry("pictures")
