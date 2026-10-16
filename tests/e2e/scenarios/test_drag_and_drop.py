# SPDX-License-Identifier: MIT
"""Moving entries by dragging them between folders."""

from __future__ import annotations

import time

import pytest

from harness.browser import ENTRY_ROLES
from harness.modes import ALL_MODES, SINGLE_PANE_MODES


def _scroll_pane(node):
    for ancestor in node.ancestors():
        if ancestor.role == "scroll pane":
            return ancestor
    raise AssertionError("the node should sit inside a scroll viewport")


def _entry_name(row):
    label = next((node for _, node in row.walk() if node.role == "label"), None)
    return label.name if label is not None and label.name else row.name


def _visible_rows(container, viewport):
    viewport_bounds = viewport.screen_bounds()
    origin = container.screen_bounds().y - container.window_bounds().y
    for row in container.children:
        if row.role not in ENTRY_ROLES:
            continue
        bounds = row.window_bounds()
        if (
            bounds.height > 0
            and bounds.y + origin >= viewport_bounds.y
            and bounds.y + origin + bounds.height <= viewport_bounds.y + viewport_bounds.height
        ):
            yield row


@pytest.mark.preferences(browser_mode="columns", open_folder_after_drop=True)
def test_drop_keeps_selection_only_at_destination(pathfm):
    fixture = pathfm.fixture
    source = pathfm.select_entry("todo.txt")
    target = pathfm.entry("archive")

    pathfm.pointer.drag(source, target)

    pathfm.wait(
        lambda: fixture.path("archive/todo.txt").exists(),
        "the dragged file to arrive in archive",
    )
    pathfm.wait_for_entry_gone("todo.txt", directory=fixture.root.name)
    pathfm.wait_for_selection(["todo.txt"], "archive")
    assert pathfm.all_selected_names() == ["todo.txt"]


@pytest.mark.parametrize("mode", ALL_MODES)
def test_dragging_a_file_onto_a_folder_moves_it(pathfm, mode):
    fixture = pathfm.fixture
    source = pathfm.select_entry("todo.txt")
    target = pathfm.entry("archive")

    pathfm.pointer.drag(source, target)

    pathfm.wait(
        lambda: fixture.path("archive/todo.txt").exists(),
        "the dragged file to arrive in archive",
    )
    pathfm.wait(
        lambda: not fixture.path("todo.txt").exists(),
        "the dragged file to leave its source directory",
    )
    pathfm.wait_for_entry_gone("todo.txt", directory=pathfm.fixture.root.name)
    assert fixture.path("archive/todo.txt").read_text() == "todo\n"


@pytest.mark.parametrize("mode", ALL_MODES)
def test_spring_navigation_keeps_the_file_drag_usable(pathfm, mode):
    source = pathfm.entry("todo.txt")
    target = pathfm.entry("documents")
    pathfm.pointer.drag_points(
        pathfm.pointer.drag_origin(source), target.screen_bounds().center, release=False
    )
    try:
        pathfm.wait(lambda: pathfm.pane("documents"), "spring navigation into documents")
        crumb = pathfm.wait(
            lambda: pathfm.window.find(role="button", name=pathfm.fixture.root.name),
            "source folder breadcrumb",
        )
        pathfm.pointer.move_to(*crumb.screen_bounds().center)
        pathfm.wait_for_directory(pathfm.fixture.root.name)
        target = pathfm.entry("documents")
        pathfm.pointer.move_to(*target.screen_bounds().center)
        pathfm.wait(lambda: pathfm.pane("documents"), "second spring navigation")
        pane = pathfm.pane("documents").screen_bounds()
        pathfm.pointer.move_to(pane.x + pane.width // 2, pane.y + pane.height - 20)
    finally:
        pathfm.pointer.connection.button(1, False)
    pathfm.wait(
        lambda: pathfm.fixture.path("documents/todo.txt").exists(),
        "the held file to drop after spring navigation",
    )
    assert not pathfm.fixture.path("todo.txt").exists()
    assert pathfm.fixture.path("documents/todo.txt").read_text() == "todo\n"


@pytest.mark.parametrize("mode", ALL_MODES)
def test_dropping_on_a_parent_breadcrumb_moves_the_file(pathfm, mode):
    pathfm.open_directory("documents")
    crumb = pathfm.wait(
        lambda: pathfm.window.find(role="button", name=pathfm.fixture.root.name),
        "parent breadcrumb",
    )
    pathfm.pointer.drag(pathfm.entry("notes.txt", directory="documents"), crumb)
    pathfm.wait(lambda: pathfm.fixture.path("notes.txt").exists(), "breadcrumb drop")
    assert not pathfm.fixture.path("documents/notes.txt").exists()
    assert pathfm.fixture.path("notes.txt").read_text() == "notes\n"


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("recursive", [
    pytest.param(False, marks=pytest.mark.preferences(filter_include_subfolders=False)),
    pytest.param(True, marks=pytest.mark.preferences(filter_include_subfolders=True)),
])
def test_dragging_a_filtered_result_to_a_sidebar_folder(pathfm, mode, recursive):
    source_path = (
        next(pathfm.fixture.root.rglob("spreadsheet.csv"))
        if recursive else pathfm.fixture.path("todo.txt")
    )
    contents = source_path.read_bytes()
    destination = pathfm.environment.home / source_path.name
    pathfm.keyboard.press("ctrl+f")
    pathfm.keyboard.type_text(source_path.name)
    source = pathfm.wait(
        lambda: pathfm.search_result(source_path.name),
        "the filtered drag source",
    )
    pathfm.pointer.drag(source, pathfm.sidebar_button("Home"))
    pathfm.wait(lambda: destination.exists(), "the filtered file to arrive in Home")
    pathfm.wait(lambda: not source_path.exists(), "the filtered source to be moved")
    assert destination.read_bytes() == contents
    pathfm.wait(
        lambda: pathfm.search_result(source_path.name) is None,
        "the moved result to leave the filtered listing",
    )


def test_dropping_a_file_on_itself_changes_nothing(pathfm):
    fixture = pathfm.fixture
    before = fixture.listing()
    source = pathfm.select_entry("todo.txt")

    pathfm.pointer.drag(source, source)

    pathfm.entry("todo.txt")
    assert fixture.listing() == before, (
        "dropping an entry on itself must not move anything"
    )


@pytest.mark.parametrize("mode", ALL_MODES)
def test_dropping_a_folder_into_itself_changes_nothing(pathfm, mode):
    fixture = pathfm.fixture
    before = fixture.listing()
    source = pathfm.select_entry("documents")

    pathfm.pointer.drag(source, source)

    pathfm.entry("documents")
    assert fixture.listing() == before, (
        "a folder must not be moved inside itself"
    )
    assert fixture.path("documents/notes.txt").exists()


def test_releasing_outside_the_window_cancels_the_drag(pathfm):
    """The drag crosses a real drop target, then ends where none exists."""

    fixture = pathfm.fixture
    before = fixture.listing()
    source = pathfm.select_entry("todo.txt")
    window = pathfm.window.screen_bounds()
    outside = (window.x + window.width + 60, window.y + window.height + 40)

    pathfm.pointer.abandon_drag(source, outside)

    pathfm.entry("todo.txt")
    assert fixture.listing() == before, (
        "a drag released outside every drop target must not move anything"
    )


def test_dragging_onto_the_pane_background_is_a_no_op(pathfm):
    """Dropping an entry back into the directory it already lives in."""

    fixture = pathfm.fixture
    before = fixture.listing()
    source = pathfm.select_entry("todo.txt")
    pane = pathfm.pane()
    bounds = pane.screen_bounds()
    empty_point = (bounds.x + bounds.width // 2, bounds.y + bounds.height - 20)

    pathfm.pointer.drag_to_point(source, empty_point)

    pathfm.entry("todo.txt")
    assert fixture.listing() == before, (
        "dropping into the same directory must not duplicate or move anything"
    )


@pytest.mark.usefixtures("unreserved_columns")
def test_dragging_a_folder_into_another_folder_moves_its_contents(pathfm):
    fixture = pathfm.fixture
    source = pathfm.select_entry("pictures")
    pathfm.entry("photo.txt", directory="pictures")
    pathfm.settle(source)
    target = pathfm.entry("archive")

    pathfm.pointer.drag(source, target)

    pathfm.wait(
        lambda: fixture.path("archive/pictures/photo.txt").exists(),
        "the dragged folder to arrive with its contents",
    )
    pathfm.wait(
        lambda: not fixture.path("pictures").exists(),
        "the dragged folder to leave its source directory",
    )
    assert sorted(fixture.names("archive/pictures")) == ["diagram.txt", "photo.txt"]


def test_dragging_a_multi_selection_moves_every_entry(pathfm):
    fixture = pathfm.fixture
    pathfm.select_entry("readme.md")
    pathfm.keyboard.press("shift+Down")
    pathfm.wait(
        lambda: pathfm.selected_names() == ["readme.md", "todo.txt"],
        "both files to be selected",
    )

    pathfm.pointer.drag(pathfm.entry("todo.txt"), pathfm.entry("archive"))

    pathfm.wait(
        lambda: fixture.path("archive/todo.txt").exists()
        and fixture.path("archive/readme.md").exists(),
        "both dragged files to arrive in archive",
    )
    assert not fixture.path("todo.txt").exists()
    assert not fixture.path("readme.md").exists()


ROW_DRAG_MODES = [
    mode for mode in ALL_MODES if mode.id != "icons"
]


@pytest.mark.preferences(single_click_previews=True)
@pytest.mark.parametrize("mode", ROW_DRAG_MODES)
def test_empty_name_space_drag_starts_marquee(pathfm, mode):
    source = pathfm.entry("todo.txt")
    target = pathfm.entry("archive")
    start = pathfm.pointer.row_whitespace_point(source, "todo.txt")

    pathfm.pointer.drag_points(start, target.screen_bounds().center)
    expect_name_space_marquee(pathfm)


@pytest.mark.preferences(single_click_previews=True)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_selected_item_blank_space_starts_file_drag(pathfm, mode):
    source = pathfm.entry("todo.txt")
    pathfm.pointer.click(source)
    pathfm.wait(lambda: "todo.txt" in pathfm.selected_names(), "source selection")
    if mode == "Icons":
        icon = source.find(role="image")
        assert icon is not None
        bounds = icon.screen_bounds()
        start = (bounds.x - 6, bounds.center[1])
    else:
        start = pathfm.pointer.row_whitespace_point(source, "todo.txt")
    pathfm.pointer.drag_points(start, pathfm.entry("archive").screen_bounds().center)
    pathfm.wait(
        lambda: pathfm.fixture.path("archive/todo.txt").exists(),
        "the selected file dragged from blank item space",
    )
    assert not pathfm.fixture.path("todo.txt").exists()


def expect_name_space_marquee(pathfm):
    pathfm.wait(
        lambda: {"archive", "todo.txt"} <= set(pathfm.selected_names()),
        "name-column whitespace to select files rather than move one",
    )
    assert pathfm.fixture.path("todo.txt").exists()
    assert not pathfm.fixture.path("archive/todo.txt").exists()
    assert pathfm.preview() is None


def drag_from_row_padding(pathfm, mode, edge):
    fixture = pathfm.fixture
    source = pathfm.entry("todo.txt")
    target = pathfm.entry("archive")
    start = pathfm.pointer.row_padding_point(source, edge)
    start = (pathfm.pointer.row_whitespace_point(source, "todo.txt")[0], start[1])

    pathfm.pointer.drag_points(start, target.screen_bounds().center)

    expect_name_space_marquee(pathfm)
    if mode == "Columns":
        return
    source = pathfm.select_entry_with_keyboard("todo.txt")
    start = metadata_drag_origin(pathfm, source, edge)
    pathfm.pointer.drag_points(start, pathfm.entry("archive").screen_bounds().center)
    pathfm.wait(
        lambda: fixture.path("archive/todo.txt").exists(),
        f"the file dragged from {edge} row padding to arrive in archive",
    )
    pathfm.wait(
        lambda: not fixture.path("todo.txt").exists(),
        f"the file dragged from {edge} row padding to leave its source directory",
    )
    assert pathfm.preview() is None


@pytest.mark.preferences(single_click_previews=True)
@pytest.mark.parametrize("mode", ROW_DRAG_MODES)
@pytest.mark.parametrize("edge", ["top", "bottom"])
def test_row_padding_drag_respects_view_policy(pathfm, mode, edge):
    drag_from_row_padding(pathfm, mode, edge)


@pytest.mark.preferences(
    browser_density="airy", single_click_previews=True, browser_mode="list"
)
def test_airy_row_padding_drag_respects_view_policy(pathfm):
    drag_from_row_padding(pathfm, "List", "top")


def metadata_drag_origin(pathfm, source, edge=None):
    metadata = next(
        label for label in source.find_all(role="label")
        if label.name and label.name != "todo.txt"
    )
    bounds = metadata.screen_bounds()
    y = bounds.center[1] if edge is None else pathfm.pointer.row_padding_point(source, edge)[1]
    return bounds.x + 4, y


@pytest.mark.preferences(folder_peeking=True, browser_mode="columns", columns_mirror_selection=False)
def test_columns_never_open_hover_peeks_even_with_the_preference_enabled(pathfm):
    folder = pathfm.entry("documents")
    pathfm.pointer.move_to(*folder.screen_bounds().center)
    deadline = time.monotonic() + 1.2
    seen_peek = False

    def observed_hover():
        nonlocal seen_peek
        seen_peek = seen_peek or pathfm.peek() is not None
        return time.monotonic() >= deadline

    pathfm.wait(observed_hover, "a sustained column hover to remain free of folder peeks")
    assert not seen_peek, "Miller columns must ignore the folder-peeking preference"
    pathfm.open_directory("documents")
    pathfm.entry("notes.txt", directory="documents")


@pytest.mark.preferences(folder_peeking=True)
@pytest.mark.parametrize("mode", SINGLE_PANE_MODES)
def test_starting_a_drag_cancels_a_folder_peek(pathfm, mode):
    """#621: beginning a drag must cancel any open folder peek."""

    pane = pathfm.pane()
    pane_bounds = pane.screen_bounds()
    pathfm.pointer.move_to(pane_bounds.x + 20, pane_bounds.y + pane_bounds.height - 20)

    folder = pathfm.entry("archive")
    start = pathfm.pointer.drag_origin(folder)
    pathfm.pointer.move_to(*start)
    deadline = time.monotonic() + 0.2
    while time.monotonic() < deadline:
        assert pathfm.peek() is None, "a brief hover must not open a folder peek"
        time.sleep(0.02)
    pathfm.wait(lambda: pathfm.peek() is not None, "the folder peek to open after sustained hover")

    target = pathfm.entry("documents")
    pathfm.pointer.drag_points(start, target.screen_bounds().center, release=False)
    try:
        pathfm.wait(
            lambda: pathfm.peek() is None,
            "the peek to close when the drag starts",
        )
    finally:
        pathfm.pointer.connection.button(1, False)


@pytest.mark.preferences(browser_mode="columns", single_click_previews=False)
def test_dragging_from_a_clipped_column_in_a_narrow_window(pathfm):
    fixture = pathfm.fixture
    pathfm.open_directory("documents")

    bounds = pathfm.window.window_bounds()
    pathfm.keyboard.connection.resize_surface(bounds.width, bounds.height, 600, bounds.height)
    pathfm.wait(lambda: pathfm.window.window_bounds().width == 600, "a narrow window")

    source = pathfm.entry("notes.txt", directory="documents")
    destination = pathfm.environment.home / "notes.txt"

    pathfm.pointer.drag(source, pathfm.sidebar_button("Home"))

    pathfm.wait(lambda: destination.exists(), "the dragged file to arrive in Home")
    pathfm.wait(
        lambda: not fixture.path("documents/notes.txt").exists(),
        "the dragged file to leave the clipped column",
    )
    assert destination.read_text() == "notes\n"


@pytest.mark.preferences(browser_mode="columns", single_click_previews=False)
def test_dragging_a_file_to_the_strip_edge_scrolls_columns_in(pathfm):
    fixture = pathfm.fixture
    nested = fixture.path("documents/deep/deeper")
    nested.mkdir(parents=True)
    (nested / "cargo.txt").write_text("cargo\n")

    bounds = pathfm.window.window_bounds()
    pathfm.keyboard.connection.resize_surface(bounds.width, bounds.height, 640, 360)
    pathfm.wait(lambda: pathfm.window.window_bounds().width == 640, "a narrow window")
    pathfm.wait_for_view("Columns")

    pathfm.open_directory("documents")
    pathfm.open_directory("deep", directory="documents")
    pathfm.open_directory("deeper", directory="deep")
    pathfm.settle(pathfm.pane("deeper"))

    strip = _scroll_pane(pathfm.pane("deeper")).screen_bounds()
    listing = _scroll_pane(pathfm.entry_container("deeper")).screen_bounds()
    edge = (strip.x + 6, listing.y + listing.height - 4)

    source = pathfm.entry("cargo.txt", "deeper")
    pathfm.pointer.drag_points(pathfm.pointer.drag_origin(source), edge, release=False)
    try:
        root = fixture.root.name

        def root_column_under_pointer():
            for pane in pathfm.containers():
                if pane.name == root:
                    bounds = pane.screen_bounds()
                    if bounds.x <= edge[0] < bounds.x + bounds.width:
                        return pane
            return None

        pathfm.wait(
            root_column_under_pointer,
            "the parked drag to edge-scroll the root column under the pointer",
        )
        # Content moved under the held pointer; a nudge refreshes the drop site.
        pathfm.pointer.move_to(edge[0], edge[1] - 4)
    finally:
        pathfm.pointer.connection.button(1, False)

    pathfm.wait(
        lambda: fixture.path("cargo.txt").exists(),
        "the release to drop the file into the revealed root column",
    )
    assert not (nested / "cargo.txt").exists()


@pytest.mark.preferences(browser_mode="columns", single_click_previews=False)
def test_dragging_a_file_to_the_column_edge_scrolls_its_listing(pathfm):
    fixture = pathfm.fixture
    documents = fixture.path("documents")
    for index in range(300):
        (documents / f"{index:03}.txt").write_text("x\n")
    pathfm.open_directory("documents")

    container = pathfm.entry_container("documents")
    assert container is not None
    viewport = _scroll_pane(container)
    bounds = viewport.screen_bounds()

    source = pathfm.entry("000.txt", "documents")
    pathfm.pointer.drag_points(
        pathfm.pointer.drag_origin(source),
        (bounds.center[0], bounds.y + bounds.height - 8),
        release=False,
    )
    try:
        pathfm.wait(
            lambda: any(
                _entry_name(row) >= "040.txt"
                for row in _visible_rows(container, viewport)
            ),
            "the parked drag to edge-scroll the column's listing",
        )
    finally:
        pathfm.pointer.connection.button(1, False)

    pathfm.wait(
        lambda: fixture.path("documents/000.txt").exists(),
        "the file to stay in its own directory after the drag",
    )


@pytest.mark.preferences(browser_mode="columns", single_click_previews=False)
def test_dropping_on_partially_visible_column_moves_file_without_jumping(pathfm):
    fixture = pathfm.fixture
    deep = fixture.path("documents/deep")
    deep.mkdir(parents=True)
    (deep / "cargo.txt").write_text("cargo\n")

    bounds = pathfm.window.window_bounds()
    pathfm.keyboard.connection.resize_surface(bounds.width, bounds.height, 640, 360)
    pathfm.wait(lambda: pathfm.window.window_bounds().width == 640, "a narrow window")

    pathfm.open_directory("documents")
    pathfm.open_directory("deep", directory="documents")
    pathfm.settle(pathfm.pane("deep"))

    documents_pane = pathfm.pane("documents")
    assert documents_pane is not None

    source = pathfm.entry("cargo.txt", "deep")
    doc_bounds = documents_pane.screen_bounds()
    strip = _scroll_pane(pathfm.pane("deep")).screen_bounds()
    drop_x = max(doc_bounds.x + 10, strip.x + 10)
    drop_y = doc_bounds.y + doc_bounds.height // 2

    pathfm.pointer.drag_points(
        pathfm.pointer.drag_origin(source),
        (drop_x, drop_y),
        release=True,
    )

    pathfm.wait(
        lambda: fixture.path("documents/cargo.txt").exists(),
        "the file to arrive in documents directory",
    )
    assert not (deep / "cargo.txt").exists()
    assert pathfm.pane("deep") is not None
