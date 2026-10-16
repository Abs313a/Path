# SPDX-License-Identifier: MIT
"""Opening, reading, and closing the quick preview."""

from __future__ import annotations

import pytest
from pathlib import Path
import io
import zipfile
from PIL import Image

from harness.fixtures import FixtureTree
from harness.modes import ALL_MODES, NEXT_ENTRY_KEY, PREVIOUS_ENTRY_KEY

PREVIEW_FIXTURE = {
    "notes.txt": "the quick brown fox\n",
    "page.md": "# Heading\n\nBody text.\n",
    "third.txt": "third preview fixture\n",
    "data.csv": "name,value\nalpha,1\n",
    "folder": {"inner.txt": "inner\n", "nested-notes.txt": "nested preview fixture\n"},
}


@pytest.mark.preferences(browser_mode="list", single_click_previews=False)
def test_model_preview_renders_stl_prefers_thumbnails_and_reports_limits(pathfm):
    folder = pathfm.fixture.root
    (folder / "sample.stl").write_text(
        "solid sample\nfacet normal 0 0 1\nouter loop\n"
        "vertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\n"
        "endloop\nendfacet\nendsolid\n"
    )
    with zipfile.ZipFile(folder / "sample.3mf", "w") as package:
        package.writestr(
            "3D/3dmodel.model",
            'geometry must not be parsed when one usable thumbnail exists',
        )
        thumbnail = io.BytesIO()
        Image.new("RGB", (32, 32), "red").save(thumbnail, format="PNG")
        package.writestr("Metadata/thumbnail.png", thumbnail.getvalue())
        package.writestr("Metadata/invalid-thumbnail.png", b"invalid image")
    (folder / "sample.3mf").rename(folder / "model-blob")
    (folder / "sample.3mf").symlink_to("model-blob")

    pathfm.wait(lambda: pathfm.entry("sample.stl"), "STL file in listing")
    pathfm.select_entry("sample.stl")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview() and pathfm.preview().find(role="image", name="Model preview"), "rendered STL preview")
    pathfm.pointer.click(pathfm.preview().find(role="button", name="Close preview (Space)"))
    pathfm.wait(lambda: pathfm.preview() is None, "STL preview to close")

    pathfm.select_entry("sample.3mf")
    pathfm.keyboard.press("space")
    pathfm.wait(
        lambda: pathfm.preview() and pathfm.preview().find(role="image", name="Model preview"),
        "embedded 3MF thumbnail",
    )
    pathfm.pointer.click(pathfm.preview().find(role="button", name="Close preview (Space)"))
    pathfm.wait(lambda: pathfm.preview() is None, "model preview to close")
    with zipfile.ZipFile(folder / "assembly.3mf", "w") as package:
        package.writestr("3D/Objects/part.model", "<model/>")
        package.writestr("3D/3dmodel.model", "<model/>")
    pathfm.wait(lambda: pathfm.entry("assembly.3mf"), "multipart model in listing")
    pathfm.select_entry("assembly.3mf")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("Multipart model detected. Unable to render preview."), "multipart model notice")
    pathfm.pointer.click(pathfm.preview().find(role="button", name="Close preview (Space)"))
    pathfm.wait(lambda: pathfm.preview() is None, "multipart preview to close")
    with zipfile.ZipFile(folder / "missing.FCStd", "w") as package:
        package.writestr("Document.xml", "<Document/>")
    pathfm.wait(lambda: pathfm.entry("missing.FCStd"), "FreeCAD file in listing")
    pathfm.select_entry("missing.FCStd")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("This FreeCAD file has no usable embedded thumbnail"), "specific sandbox error")
    pathfm.pointer.click(pathfm.preview().find(role="button", name="Close preview (Space)"))
    pathfm.wait(lambda: pathfm.preview() is None, "FreeCAD preview to close")
    with (folder / "oversized.stl").open("wb") as file:
        file.truncate(128 * 1024 * 1024 + 1)
    pathfm.wait(lambda: pathfm.entry("oversized.stl"), "oversized STL in listing")
    pathfm.select_entry("oversized.stl")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("128 MiB preview limit"), "explicit file size limit")


@pytest.fixture
def root(pathfm) -> str:
    return pathfm.fixture.root.name


@pytest.fixture
def fixture_tree(request):
    """Replaces the shared fixture with file types the preview can render."""

    layout = getattr(request, "param", PREVIEW_FIXTURE)
    tree = FixtureTree.create({name: "" if isinstance(value, Path) else value for name, value in layout.items()})
    for name, value in layout.items():
        if isinstance(value, Path):
            (tree.root / name).write_bytes(value.read_bytes())
    try:
        yield tree
    finally:
        tree.cleanup()


@pytest.mark.parametrize(
    "mode,selection",
    [
        pytest.param(
            "Columns",
            "keyboard",
            marks=pytest.mark.preferences(browser_mode="columns"),
            id="columns-keyboard",
        ),
        pytest.param(
            "Icons",
            "keyboard",
            marks=pytest.mark.preferences(browser_mode="icons"),
            id="icons-keyboard",
        ),
        pytest.param(
            "List",
            "keyboard",
            marks=pytest.mark.preferences(browser_mode="list"),
            id="list-keyboard",
        ),
        pytest.param(
            "List",
            "pointer",
            marks=pytest.mark.preferences(browser_mode="list"),
            id="list-pointer",
        ),
    ],
)
@pytest.mark.preferences(single_click_previews=False)
def test_space_opens_and_closes_the_quick_preview(pathfm, mode, selection):
    before = pathfm.entry_names()
    if selection == "keyboard":
        pathfm.select_entry_with_keyboard("notes.txt")
    else:
        pathfm.select_entry("notes.txt")

    pathfm.keyboard.press("space")

    pathfm.wait(
        lambda: pathfm.preview_shows("the quick brown fox"),
        "the preview to render the file's text",
    )

    preview = pathfm.preview()
    assert preview.find(role="label", name="notes.txt") is not None
    assert pathfm.preview_shows("text/plain")
    assert pathfm.entry_names() == before
    close = preview.find(role="button", name="Close preview (Space)")
    pathfm.pointer.click(close)
    pathfm.wait(lambda: pathfm.preview() is None, "the preview to close")

    original = pathfm.window_bounds()
    pathfm.keyboard.connection.resize_surface(original.width, original.height, 640, 480)
    # Re-clicking the already selected name would start inline renaming.
    pathfm.select_entry("page.md")
    pathfm.select_entry("notes.txt")
    pathfm.keyboard.press("space")
    bounds = pathfm.window_bounds()
    pathfm.keyboard.connection.resize_surface(bounds.width, bounds.height, 320, 320)
    pathfm.wait(lambda: pathfm.preview() is None, "the constrained preview to stay hidden")
    pathfm.wait_for_focused_entry("notes.txt")
    pathfm.keyboard.press("End")
    pathfm.wait_for_selection(["third.txt"])
    bounds = pathfm.window_bounds()
    pathfm.keyboard.connection.resize_surface(bounds.width, bounds.height, original.width, original.height)
    pathfm.wait(lambda: pathfm.preview_shows("third preview fixture"), "the latest preview to resume")
    bounds = pathfm.window_bounds()
    pathfm.keyboard.connection.resize_surface(bounds.width, bounds.height, 480, 480)
    pathfm.wait(lambda: pathfm.preview() is None, "the preview to suspend again")
    pathfm.wait_for_focused_entry("third.txt")
    pathfm.keyboard.press("space")
    bounds = pathfm.window_bounds()
    pathfm.keyboard.connection.resize_surface(bounds.width, bounds.height, original.width, original.height)
    pathfm.wait(lambda: pathfm.window_bounds().width == original.width, "the expanded window")
    assert pathfm.preview() is None
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("third preview fixture"), "the explicitly reopened preview")
    pathfm.pointer.click(pathfm.preview().find(role="button", name="Close preview (Space)"))
    pathfm.wait(lambda: pathfm.preview() is None, "the close button to return to browsing")
    assert pathfm.selected_names() == ["third.txt"]


@pytest.mark.preferences(browser_mode="columns", single_click_previews=True)
def test_columns_keyboard_selection_opens_the_preview(pathfm, fixture_tree, root):
    pathfm.select_entry_with_keyboard("data.csv")
    pathfm.wait(
        lambda: pathfm.preview_shows("alpha"),
        "keyboard selection to open the preview without Space",
    )
    pathfm.keyboard.press(PREVIOUS_ENTRY_KEY["Columns"])
    pathfm.wait_for_selection(["folder"], root)
    pathfm.wait(lambda: pathfm.preview() is None, "the folder to hand the right pane to its child column")
    pathfm.pane("folder")
    pathfm.keyboard.press(NEXT_ENTRY_KEY["Columns"])
    pathfm.wait_for_selection(["data.csv"], root)
    pathfm.wait(lambda: pathfm.preview_shows("alpha"), "the preview to resume")
    pathfm.wait(lambda: "folder" not in pathfm.pane_names(), "the child column to yield to the preview")


@pytest.mark.preferences(browser_mode="columns", single_click_previews=True)
@pytest.mark.parametrize("dismissal", ["space", "startup-panel"])
def test_columns_dismissed_preview_ignores_keyboard_mirroring_until_reopened(pathfm, root, dismissal):
    if dismissal == "startup-panel":
        pathfm.open_appearance_menu()
        option = pathfm.wait(
            lambda: pathfm.window.find(role="toggle button", name="Preview panel"),
            "the session preview toggle",
        )
        pathfm.pointer.click(option)
        pathfm.wait_for_menu_closed()
        pathfm.keyboard.press("ctrl+l")
        pathfm.wait(
            lambda: pathfm.window.find(role="text", states={"editable", "focused"}),
            "the location editor to take focus",
        )
        pathfm.keyboard.press("Escape")
        pathfm.wait(lambda: pathfm.focused_pane(), "focus to return to the listing")
    pathfm.select_entry_with_keyboard("data.csv")
    if dismissal == "space":
        pathfm.wait(lambda: pathfm.preview_shows("alpha"), "keyboard selection to open the preview")
        pathfm.keyboard.press("space")
        pathfm.wait(lambda: pathfm.preview() is None, "Space to dismiss the preview")
    else:
        pathfm.settle(pathfm.entry("data.csv"))
        assert pathfm.preview() is None, "the startup panel toggle must block the first mirror"
    pathfm.keyboard.press(NEXT_ENTRY_KEY["Columns"])
    pathfm.wait_for_selection(["notes.txt"], root)
    pathfm.settle(pathfm.entry("notes.txt"))
    assert pathfm.preview() is None, "a dismissed preview must not follow keyboard selection"
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("the quick brown fox"), "Space to reopen the preview")
    pathfm.keyboard.press(NEXT_ENTRY_KEY["Columns"])
    pathfm.wait_for_selection(["page.md"], root)
    pathfm.wait(lambda: pathfm.preview_shows("Body text."), "the reopened preview to follow again")


@pytest.mark.preferences(browser_mode="columns", single_click_previews=False)
def test_columns_keyboard_selection_respects_disabled_previews(pathfm, fixture_tree):
    pathfm.select_entry_with_keyboard("data.csv")
    pathfm.settle(pathfm.entry("data.csv"))
    assert pathfm.preview() is None
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("alpha"), "Space to open the preview")


@pytest.mark.preferences(browser_mode="columns", columns_mirror_selection=False)
def test_columns_keyboard_selection_stays_put_when_mirror_is_disabled(pathfm, fixture_tree):
    pathfm.select_entry_with_keyboard("folder")
    pathfm.wait_for_selection(["folder"])
    pathfm.settle(pathfm.entry("folder"))
    assert len(pathfm.containers()) == 1


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("selection", ["keyboard", "pointer"])
def test_space_previews_a_filtered_result_without_changing_the_query(pathfm, mode, selection):
    pathfm.select_entry("notes.txt")
    pathfm.keyboard.press("ctrl+f")
    field = pathfm.editable_field()
    pathfm.keyboard.type_text("nested-notes")
    pathfm.wait(
        lambda: pathfm.matches() == ["nested-notes.txt"],
        "the nested search result",
    )
    if selection == "keyboard":
        pathfm.keyboard.press("Down")
    else:
        result = pathfm.search_result("nested-notes.txt")
        assert result is not None
        pathfm.pointer.right_click(result)
        pathfm.wait(pathfm.context_menu, "the pointer-selected search result menu")
        pathfm.keyboard.press("Escape")
        pathfm.wait(lambda: result.has_state("selected"), "pointer-selected search result")

    pathfm.keyboard.press("space")
    pathfm.wait(
        lambda: pathfm.preview_shows("nested preview fixture"),
        "Space to preview the search result, not the stale directory selection",
    )
    assert field.text == "nested-notes"
    assert pathfm.matches() == ["nested-notes.txt"]
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview() is None, "Space to close the filtered preview")
    assert field.text == "nested-notes"
    assert pathfm.matches() == ["nested-notes.txt"]


@pytest.mark.preferences(single_click_previews=False)
@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("selection", ["keyboard", "pointer"])
def test_preview_follows_the_selection(pathfm, mode, selection):
    pathfm.select_entry_with_keyboard("notes.txt")
    pathfm.keyboard.press("space")
    pathfm.wait(
        lambda: pathfm.preview_shows("the quick brown fox"),
        "the first preview to render",
    )

    if selection == "keyboard":
        pathfm.keyboard.press(NEXT_ENTRY_KEY[mode])
    else:
        pathfm.select_entry("page.md")
    pathfm.wait_for_selection(["page.md"])

    pathfm.wait(
        lambda: pathfm.preview_shows("Body text."),
        "the preview to follow the newly selected file",
    )
    assert pathfm.focused_name() == "page.md"
    assert not pathfm.preview_shows("the quick brown fox")


def test_list_preview_keyboard_navigation_preserves_horizontal_scroll(pathfm, fixture_tree):
    pathfm.switch_view("List")
    pathfm.select_entry_with_keyboard("notes.txt")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("the quick brown fox"), "the first preview")

    def list_scroll_origin():
        container = pathfm.pane()
        list_view = container.find(description="Files")
        assert list_view is not None, "the List file view"
        panes = [
            ancestor for ancestor in list_view.ancestors() if ancestor.role == "scroll pane"
        ]
        assert len(panes) >= 2, "the List view content is wrapped by its listing scroller"
        return panes[0].window_bounds().x

    origin = list_scroll_origin()
    for key, name, preview in (
        ("Down", "page.md", "Body text."),
        ("Down", "third.txt", "third preview fixture"),
        ("Up", "page.md", "Body text."),
    ):
        pathfm.keyboard.press(key)
        pathfm.wait_for_selection([name])
        pathfm.wait(lambda: pathfm.focused_name() == name, f"focus on {name}")
        pathfm.wait(lambda: pathfm.preview_shows(preview), f"preview for {name}")
        assert list_scroll_origin() == origin, (origin, list_scroll_origin())


@pytest.mark.preferences(single_click_previews=False)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_space_enters_folder_without_opening_preview(pathfm, mode):
    pathfm.select_entry_with_keyboard("folder")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: "inner.txt" in pathfm.entry_names(), "Space to enter the folder")
    assert pathfm.preview() is None


@pytest.mark.preferences(single_click_previews=False)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_preview_follows_extended_selection_without_collapsing_it(pathfm, mode):
    pathfm.select_entry_with_keyboard("notes.txt")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("the quick brown fox"), "the first preview")

    pathfm.keyboard.press(f"shift+{NEXT_ENTRY_KEY[mode]}")

    pathfm.wait_for_selection(["notes.txt", "page.md"])
    pathfm.wait(lambda: pathfm.preview_shows("Body text."), "the newly focused preview")
    assert pathfm.focused_name() == "page.md"


@pytest.mark.preferences(single_click_previews=False)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_preview_hides_on_a_folder_and_resumes_when_selection_moves(pathfm, mode, root):
    pathfm.select_entry_with_keyboard("data.csv")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("alpha"), "the file preview")

    pathfm.keyboard.press(PREVIOUS_ENTRY_KEY[mode])

    pathfm.wait_for_selection(["folder"], root)
    if mode == "Icons":
        pathfm.wait(lambda: pathfm.preview_shows("No preview for this selection"), "the folder's reserved preview space")
    else:
        pathfm.wait(lambda: pathfm.preview() is None, "the folder to dismiss the preview")
    pathfm.keyboard.press(NEXT_ENTRY_KEY[mode])
    pathfm.wait_for_selection(["data.csv"], root)
    pathfm.wait(lambda: pathfm.preview_shows("alpha"), "the still-enabled preview to resume")


@pytest.mark.preferences(browser_mode="list")
def test_marquee_does_not_reopen_enabled_preview(pathfm):
    pathfm.select_entry_with_keyboard("data.csv")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("alpha"), "the enabled preview")
    pathfm.keyboard.press("Up")
    pathfm.wait_for_selection(["folder"])
    pathfm.wait(lambda: pathfm.preview() is None, "the folder to hide preview")
    pathfm.settle(pathfm.entry("third.txt"))

    last = pathfm.entry("third.txt").screen_bounds()
    first = pathfm.entry("data.csv").screen_bounds()
    start = (last.x + last.width // 2, last.y + last.height + 60)
    end = (first.x + 50, first.center[1])
    pathfm.pointer.drag_points(start, end, release=False)
    try:
        pathfm.wait_for_selection(["data.csv", "notes.txt", "page.md", "third.txt"])
        assert pathfm.preview() is None, "held marquee must not open preview"
    finally:
        pathfm.pointer.connection.button(1, False)
    assert pathfm.preview() is None
    pathfm.select_entry_with_keyboard("notes.txt")
    pathfm.wait(lambda: pathfm.preview_shows("the quick brown fox"), "keyboard preview to resume")


def test_preview_hides_on_shift_range_folder_focus(pathfm):
    pathfm.switch_view("List")
    pathfm.select_entry_with_keyboard("notes.txt")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("the quick brown fox"), "the file preview")

    pathfm.keyboard.press("shift+Up")
    pathfm.wait_for_selection(["data.csv", "notes.txt"])
    pathfm.wait(lambda: pathfm.focused_name() == "data.csv", "the focused upper file")
    pathfm.wait(lambda: pathfm.preview_shows("alpha"), "the upper file preview")

    pathfm.keyboard.press("shift+Up")
    pathfm.wait_for_selection(["folder", "data.csv", "notes.txt"])
    pathfm.wait(lambda: pathfm.focused_name() == "folder", "the focused folder")
    pathfm.wait(lambda: pathfm.preview() is None, "the focused folder to dismiss the preview")

    pathfm.keyboard.press("shift+Down")
    pathfm.wait_for_selection(["data.csv", "notes.txt"])
    pathfm.wait(lambda: pathfm.preview_shows("alpha"), "preview to resume after the folder")


@pytest.mark.preferences(single_click_previews=False)
def test_preview_renders_markdown(pathfm, fixture_tree):
    from PIL import Image

    Image.new("RGB", (80, 32), "green").save(fixture_tree.path("folder/local image.png"))
    fixture_tree.path("folder/shapes.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="32">'
        '<circle cx="16" cy="16" r="12" fill="red"/></svg>'
    )
    fixture_tree.path("page.md").write_text(
        "# Heading\n\nBody text.\n\n"
        "![Local PNG](folder/local%20image.png)\n\n"
        "![Local SVG](folder/shapes.svg)\n\n"
        "```mermaid\nflowchart LR\nA[Open] --> B[Preview]\n```\n\n"
        "![Missing fixture](folder/missing.png)\n"
    )
    pathfm.select_entry_with_keyboard("page.md")
    pathfm.keyboard.press("space")

    pathfm.wait(
        lambda: pathfm.preview_shows("Body text."),
        "the markdown preview to render its body",
    )
    for name in ("Local PNG", "Local SVG", "Mermaid diagram"):
        pathfm.wait(
            lambda name=name: pathfm.preview().find(role="image", description=name) is not None,
            f"the sandboxed Markdown media to render: {name}",
        )
    pathfm.wait(lambda: pathfm.preview_shows("Missing fixture"), "missing-image fallback")
    pathfm.pointer.click(pathfm.preview().find(role="button", name="View source"))
    pathfm.wait(lambda: pathfm.preview_shows("flowchart LR"), "original Mermaid source")
    pathfm.pointer.click(pathfm.preview().find(role="button", name="View rendered"))
    pathfm.wait(
        lambda: pathfm.preview().find(role="image", description="Mermaid diagram") is not None,
        "the cached diagram after switching back to rendered view",
    )
    pathfm.select_entry("notes.txt")
    pathfm.wait(lambda: pathfm.preview_shows("the quick brown fox"), "next preview")
    assert pathfm.preview().find(role="image", description="Mermaid diagram") is None


@pytest.mark.preferences(single_click_previews=False)
def test_markdown_equations_preserve_inline_prose_source_and_fallbacks(pathfm, fixture_tree):
    fixture_tree.path("page.md").write_text(
        "# Equations\n\nEnergy $E=mc^2$ in prose.\n\n"
        "$$\\frac{-b\\pm\\sqrt{b^2-4ac}}{2a}$$\n\n"
        "```latex\n\\sum_{n=1}^{\\infty}\\frac{1}{n^2}=\\frac{\\pi^2}{6}\n```\n\n"
        "Unsupported $\\unknowncommand{x}$ remains readable.\n"
    )
    pathfm.select_entry_with_keyboard("page.md")
    pathfm.keyboard.press("space")
    pathfm.wait(
        lambda: len(pathfm.preview().find_all(role="image", description="LaTeX equation")) == 3,
        "inline, display, and fenced equations rendered through the sandbox",
    )
    assert pathfm.preview_shows("Energy") and pathfm.preview_shows("in prose."), "\n".join(
        repr((node.role, node.text)) for node in pathfm.preview().find_all(rendered=False) if node.text
    )
    pathfm.wait(lambda: pathfm.preview_shows("$\\unknowncommand{x}$"), "unsupported equation fallback")
    pathfm.pointer.click(pathfm.preview().find(role="button", name="View source"))
    pathfm.wait(lambda: pathfm.preview_shows("$E=mc^2$"), "unchanged equation source")
    pathfm.pointer.click(pathfm.preview().find(role="button", name="View rendered"))
    pathfm.wait(
        lambda: len(pathfm.preview().find_all(role="image", description="LaTeX equation")) == 3,
        "equations retained across view switching",
    )


def _large_table(extension):
    rows = [(f"record-{index}", index) for index in range(1000)]
    if extension in ("csv", "tsv"):
        separator = "," if extension == "csv" else "\t"
        return separator.join(("name", "value")) + "\n" + "".join(
            f"{name}{separator}{value}\n" for name, value in rows
        )
    if extension == "md":
        return "| name | value |\n| --- | --- |\n" + "".join(
            f"| {name} | {value} |\n" for name, value in rows
        )
    return "<table><tr><th>name</th><th>value</th></tr>" + "".join(
        f"<tr><td>{name}</td><td>{value}</td></tr>" for name, value in rows
    ) + "</table>"


@pytest.mark.parametrize("fixture_tree,filename", [
    ({f"table.{extension}": _large_table(extension)}, f"table.{extension}")
    for extension in ("csv", "tsv", "md", "html")
], indirect=["fixture_tree"])
@pytest.mark.preferences(render_documents_by_default=True)
def test_large_table_header_sort_reaches_rows_beyond_old_limits(pathfm, filename):
    pathfm.select_entry_with_keyboard(filename)
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("record-0"), "the first table row")
    header = pathfm.preview().find(role="column header", name="value")
    if header is None:
        header = pathfm.preview().find(role="filler", name="value")
    assert header is not None
    pathfm.pointer.click(header)
    pathfm.pointer.click(header)
    pathfm.wait(lambda: pathfm.preview_shows("record-999"), "numeric descending sort across every loaded row")
    assert pathfm.preview().find(role="button", name="Copy table") is None
    cell = pathfm.preview().find(role="label", name="record-999")
    assert cell is not None
    pathfm.pointer.click(cell)
    pathfm.keyboard.press("End")
    for _ in range(3):
        pathfm.keyboard.press("shift+Left")
    pathfm.keyboard.press("ctrl+c")
    pathfm.keyboard.press("ctrl+l")
    field = pathfm.editable_field()
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.press("ctrl+v")
    pathfm.wait(lambda: field.text == "999", "only the selected cell text to reach the clipboard")
    pathfm.keyboard.press("Escape")
    first = pathfm.preview().find(role="label", name="999").screen_bounds()
    last = pathfm.preview().find(role="label", name="997").screen_bounds()
    start = (first.x, first.center[1])
    end = (last.x + last.width - 1, last.center[1])
    for origin, destination in [(start, end), (end, start)]:
        pathfm.pointer.drag_points(origin, destination)
        pathfm.keyboard.press("ctrl+c")
        assert table_clipboard_text(pathfm) == "999\nrecord-998\t998\nrecord-997\t997"
    def click_cell_and_copy():
        pathfm.pointer.click(pathfm.preview().find(role="label", name="record-998"))
        pathfm.keyboard.press("ctrl+c")

    assert table_clipboard_text(pathfm, before_read=click_cell_and_copy) == "selection-cleared"
    preview = pathfm.preview().screen_bounds()
    pathfm.pointer.drag_points(start, (end[0], preview.y + preview.height - 12), release=False)
    try:
        pathfm.wait(
            lambda: any(
                (text := node.text).startswith("record-")
                and text.removeprefix("record-").isdigit()
                and int(text.removeprefix("record-")) <= 950
                for node in pathfm.preview().find_all(role="label")
            ),
            "selection drag to autoscroll through recycled rows",
        )
    finally:
        pathfm.pointer.connection.button(1, False)
    pathfm.keyboard.press("ctrl+c")
    copied = table_clipboard_text(pathfm)
    assert copied.startswith("999\nrecord-998\t998\n")
    assert "record-970\t970\n" in copied

    def dismiss_and_copy():
        pathfm.pointer.click(pathfm.preview(), at=(preview.x + 180, preview.y + 16))
        pathfm.keyboard.press("ctrl+c")

    assert table_clipboard_text(pathfm, before_read=dismiss_and_copy) == "selection-cleared"


@pytest.mark.preferences(single_click_previews=False)
def test_preview_source_text_takes_pointer_focus_and_copies(pathfm):
    pathfm.select_entry_with_keyboard("notes.txt")
    pathfm.keyboard.press("space")
    pathfm.wait(
        lambda: pathfm.preview_shows("the quick brown fox"),
        "the preview to render the file's text",
    )
    text = pathfm.preview().find(role="text")
    assert text is not None, pathfm.preview().dump()
    pathfm.pointer.click(text)
    pathfm.wait(lambda: text.has_state("focused"), "the preview text to take focus")
    pathfm.keyboard.press("ctrl+Home")
    pathfm.keyboard.press_repeatedly("shift+Right", 3)
    pathfm.keyboard.press("ctrl+c")
    assert table_clipboard_text(pathfm) == "the"
    pathfm.pointer.click(text)
    bounds = text.screen_bounds()
    pathfm.pointer.drag_points(
        (bounds.x + 34, bounds.y + 14),
        (bounds.x + 140, bounds.y + 14),
    )
    pathfm.keyboard.press("ctrl+c")
    pathfm.keyboard.press("ctrl+l")
    field = pathfm.editable_field()
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.press("ctrl+v")
    pathfm.wait(
        lambda: "quick" in field.text or "fox" in field.text,
        "the copied preview text to reach the clipboard",
    )


@pytest.mark.preferences(single_click_previews=False)
def test_pdf_preview_selects_and_copies_text(pathfm, fixture_tree):
    fixture_tree.path("page.pdf").write_bytes(
        (Path(__file__).resolve().parents[2] / "fixtures" / "documents" / "text.pdf").read_bytes()
    )
    pathfm.select_entry_with_keyboard("page.pdf")
    pathfm.keyboard.press("space")
    pathfm.wait(
        lambda: pathfm.preview() is not None
        and pathfm.preview().find(role="image", name="PDF page text") is not None,
        "the PDF page to appear in the preview",
    )
    page = pathfm.preview().find(role="image", name="PDF page text")
    # The overlay starts at the loading placeholder's 560px and shrinks to the
    # rendered page's aspect ratio once the PNG and text layer arrive.
    pathfm.wait(
        lambda: page.screen_bounds().height != 560,
        "the rendered PDF page to replace the placeholder",
    )
    bounds = page.screen_bounds()
    line_y = bounds.y + int(bounds.height * 0.11)
    pathfm.pointer.drag_points(
        (bounds.x + int(bounds.width * 0.13), line_y),
        (bounds.x + int(bounds.width * 0.48), line_y),
    )
    pathfm.keyboard.press("ctrl+c")
    assert "Hello PDF text" in table_clipboard_text(pathfm)


@pytest.mark.preferences(single_click_previews=False, text_size=21)
@pytest.mark.parametrize(("gesture", "tenxer"), [
    pytest.param("wheel", False, marks=pytest.mark.preferences(tenxer_mode=False), id="wheel"),
    pytest.param("reset", False, marks=pytest.mark.preferences(tenxer_mode=False), id="reset"),
    pytest.param("reset", True, marks=pytest.mark.preferences(tenxer_mode=True), id="reset-tenxer"),
])
def test_pdf_zoom_keeps_interface_text_size(pathfm, fixture_tree, gesture, tenxer):
    fixture_tree.path("page.pdf").write_bytes(
        (Path(__file__).resolve().parents[2] / "fixtures" / "documents" / "text.pdf").read_bytes()
    )
    pathfm.select_entry_with_keyboard("page.pdf")
    pathfm.keyboard.press("i" if tenxer else "space")
    page = pathfm.wait(
        lambda: pathfm.preview()
        and pathfm.preview().find(role="image", name="PDF page text"),
        "PDF page",
    )
    pathfm.settle(page)
    saved = pathfm.environment.read_preferences()["text_size"]
    fitted = page.screen_bounds().width

    if gesture == "reset":
        pathfm.pointer.click(page)
    pathfm.pointer.scroll(page.screen_bounds().center, clicks=2, down=False, modifiers=["ctrl"])
    pathfm.wait(
        lambda: page.screen_bounds().width > fitted,
        "Ctrl+wheel over the PDF to enlarge its pages",
    )
    if gesture == "reset":
        pathfm.keyboard.press("ctrl+0")
        pathfm.wait(
            lambda: page.screen_bounds().width == fitted,
            "Ctrl+0 on the focused PDF to restore the fitted page width",
        )
    pathfm.settle(page)
    assert pathfm.environment.read_preferences()["text_size"] == saved

    pathfm.pointer.click(page)
    listing = pathfm.entry("page.pdf")
    pathfm.pointer.scroll(listing.screen_bounds().center, clicks=2, down=False, modifiers=["ctrl"])
    pathfm.wait(
        lambda: pathfm.environment.read_preferences()["text_size"] == "23",
        "wheel outside the PDF to resize interface text despite PDF keyboard focus",
    )
    pathfm.pointer.click(pathfm.entry("page.pdf"))
    pathfm.keyboard.press("ctrl+0")
    pathfm.wait(
        lambda: pathfm.environment.read_preferences()["text_size"] == "13",
        "reset outside the PDF to restore interface text size",
    )


def table_clipboard_text(pathfm, *, before_read=None):
    from gi.repository import Gdk, GLib

    display = Gdk.Display.open(pathfm.display.display)
    assert display is not None
    result = []
    try:
        if before_read is not None:
            display.get_clipboard().set("selection-cleared")
            display.flush()
            before_read()
        display.get_clipboard().read_text_async(
            None, lambda clipboard, response: result.append(clipboard.read_text_finish(response))
        )

        def received():
            context = GLib.MainContext.default()
            while context.pending():
                context.iteration(False)
            return bool(result)

        pathfm.wait(received, "selected table text on the private display clipboard")
        return result[0]
    finally:
        display.close()


@pytest.mark.parametrize("fixture_tree,filename,shown", [
    *[
        ({f"book.{extension}": (Path(__file__).resolve().parents[2] / "fixtures" / "spreadsheets" / f"any_sheets.{extension}")}, f"book.{extension}", "3")
        for extension in ("xls", "xlsx", "ods")
    ],
    ({"report.docx": (Path(__file__).resolve().parents[2] / "fixtures" / "documents" / "report.docx")}, "report.docx", "Quarterly Report"),
], indirect=["fixture_tree"])
def test_sandboxed_office_files_use_the_shared_rendered_preview(pathfm, filename, shown):
    pathfm.select_entry_with_keyboard(filename)
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows(shown), "the sandboxed document content")
    assert pathfm.preview().find(role="button", name="Copy table") is None
    assert pathfm.preview().find(role="button", name="View source") is None


@pytest.mark.preferences(browser_mode="columns", single_click_previews=False)
def test_column_preview_fills_free_space_and_keeps_a_dragged_session_minimum(pathfm):
    def adjacent():
        column = pathfm.containers()[-1].screen_bounds()
        preview = pathfm.preview().screen_bounds()
        return abs(preview.x - (column.x + column.width)) <= 3

    pathfm.select_entry_with_keyboard("notes.txt")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("the quick brown fox"), "the first preview")
    pathfm.wait(adjacent, "the preview to meet the last column")
    initial = pathfm.preview().screen_bounds().width
    pathfm.keyboard.press("Down")
    pathfm.wait(lambda: pathfm.preview_shows("Body text."), "keyboard selection to update the preview")
    pathfm.keyboard.press("space")
    pathfm.open_directory("folder")
    pathfm.select_entry_with_keyboard("inner.txt")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("inner"), "the nested preview")
    pathfm.wait(adjacent, "the nested preview to meet the last column")
    nested = pathfm.preview().screen_bounds().width
    assert nested < initial

    bounds = pathfm.preview().screen_bounds()
    start = (bounds.x + 2, bounds.y + bounds.height // 2)
    distance = bounds.width // 5
    pathfm.pointer.drag_points(start, (start[0] - distance, start[1]))
    pathfm.wait(
        lambda: pathfm.preview().screen_bounds().width > nested + distance // 2,
        "the dragged width to widen the preview",
    )
    chosen = pathfm.preview().screen_bounds().width
    resized = pathfm.preview().screen_bounds()
    window = pathfm.window_bounds()
    assert abs(resized.x + resized.width - window.x - window.width) <= 2
    pathfm.keyboard.press("space")
    pathfm.select_entry_with_keyboard("nested-notes.txt")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("nested preview fixture"), "the reopened preview")
    assert abs(pathfm.preview().screen_bounds().width - chosen) <= 2, "the dragged width is the session minimum"
    pathfm.keyboard.press("space")
    pathfm.keyboard.press("alt+Left")
    pathfm.select_entry_with_keyboard("notes.txt")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("the quick brown fox"), "the parent preview")
    pathfm.wait(adjacent, "the parent preview to fill the space beside the column")
    assert pathfm.preview().screen_bounds().width > chosen + 2, "more room widens the preview past the minimum"


@pytest.mark.preferences(browser_mode="columns", single_click_previews=False)
def test_dragging_a_filled_column_preview_narrower_outlines_the_new_minimum(pathfm):
    def outline():
        return pathfm.window.find(role="label", name="Preview panel minimum width")

    def adjacent():
        column = pathfm.containers()[-1].screen_bounds()
        preview = pathfm.preview().screen_bounds()
        return abs(preview.x - (column.x + column.width)) <= 3

    pathfm.select_entry_with_keyboard("notes.txt")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("the quick brown fox"), "the first preview")
    pathfm.wait(adjacent, "the preview to fill the space beside the column")
    filled = pathfm.preview().screen_bounds()
    start = (filled.x + 2, filled.y + filled.height // 2)
    distance = filled.width // 3
    pathfm.pointer.drag_points(start, (start[0] + distance, start[1]), release=False)
    try:
        pathfm.wait(lambda: outline() is not None, "the minimum width outline")
        assert abs(pathfm.preview().screen_bounds().width - filled.width) <= 2, "the panel stays put"
    finally:
        pathfm.pointer.connection.button(1, False)
    pathfm.wait(lambda: outline() is None, "the outline to go once the drag ends")
    assert abs(pathfm.preview().screen_bounds().width - filled.width) <= 2

    pathfm.keyboard.press("space")
    pathfm.open_directory("folder")
    pathfm.select_entry_with_keyboard("inner.txt")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("inner"), "the nested preview")
    pathfm.wait(
        lambda: abs(pathfm.preview().screen_bounds().width - (filled.width - distance)) <= 4,
        "the dragged minimum to hold where the columns need the space",
    )


@pytest.mark.preferences(browser_mode="columns", single_click_previews=False)
@pytest.mark.parametrize(("side", "offset"), [("column", -3), ("preview", -1), ("preview", 3)])
def test_the_column_preview_boundary_resizes_the_side_it_is_grabbed_from(pathfm, side, offset):
    pathfm.select_entry_with_keyboard("notes.txt")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("the quick brown fox"), "the first preview")
    pathfm.settle(pathfm.preview())
    column = pathfm.containers()[-1].screen_bounds()
    preview = pathfm.preview().screen_bounds()
    # -1 is the divider line itself, drawn over the column's last pixel.
    start = (preview.x + offset, preview.y + preview.height // 2)
    def caption(name):
        return pathfm.window.find(role="label", name=name)

    pathfm.pointer.move_to(*start)
    hint = "Column width" if side == "column" else "Preview panel minimum width"
    pathfm.wait(lambda: caption(hint) is not None, "a resize hint before the drag starts")
    pathfm.pointer.drag_points(start, (start[0] + 40, start[1]), release=False)
    try:
        if side == "column":
            pathfm.wait(
                lambda: pathfm.containers()[-1].screen_bounds().width > column.width + 20,
                "the column beside the preview to widen",
            )
            pathfm.wait(lambda: caption("Column width") is not None, "the column width caption")
            assert caption("Preview panel minimum width") is None
        else:
            pathfm.wait(
                lambda: caption("Preview panel minimum width") is not None,
                "the preview divider to outline its minimum",
            )
            assert caption("Column width") is None
            assert pathfm.containers()[-1].screen_bounds().width == column.width
    finally:
        pathfm.pointer.connection.button(1, False)
    pathfm.wait(
        lambda: caption("Column width") is None and caption("Preview panel minimum width") is None,
        "the resize captions to go once the drag ends",
    )


@pytest.mark.preferences(browser_mode="columns", single_click_previews=False)
def test_columns_preview_can_reopen_after_closing(pathfm):
    pathfm.open_directory("folder")
    pathfm.wait_for_entries(sorted(PREVIEW_FIXTURE["folder"]), "folder")
    pathfm.select_entry_with_keyboard("inner.txt")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("inner"), "the nested preview")
    close = pathfm.preview().find(role="button", name="Close preview (Space)")
    pathfm.pointer.click(close)
    pathfm.wait(lambda: pathfm.preview() is None, "the preview to close")
    pathfm.select_entry("nested-notes.txt")
    assert pathfm.preview() is None, "closing the content must stop automatic previews"
    pathfm.open_appearance_menu()
    option = pathfm.wait(lambda: pathfm.window.find(role="toggle button", name="Preview panel"), "the preview toggle")
    assert option.has_state("pressed"), "closing a preview must keep its space reserved"
    pathfm.dismiss_menu()
    pathfm.select_entry("inner.txt")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("inner"), "the preview to reopen")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview() is None, "Space to dismiss the preview content")
    pathfm.open_appearance_menu()
    option = pathfm.wait(lambda: pathfm.window.find(role="toggle button", name="Preview panel"), "the retained preview toggle")
    assert option.has_state("pressed")
    pathfm.pointer.click(option)
    pathfm.wait_for_menu_closed()
    pathfm.open_appearance_menu()
    option = pathfm.wait(lambda: pathfm.window.find(role="toggle button", name="Preview panel"), "the disabled preview toggle")
    assert not option.has_state("pressed"), "Appearance explicitly releases the preview reservation"
    pathfm.dismiss_menu()


@pytest.mark.preferences(browser_mode="columns", single_click_previews=False)
def test_narrow_window_prioritizes_the_last_column_and_restores_the_latest_preview(pathfm):
    browser_left = pathfm.pane().screen_bounds().x
    pathfm.open_directory("folder")
    pathfm.select_entry_with_keyboard("inner.txt")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("inner"), "the initial preview")
    preferred = pathfm.preview().screen_bounds().width

    def resize(width):
        bounds = pathfm.window_bounds()
        pathfm.keyboard.connection.resize_surface(bounds.width, bounds.height, width, bounds.height)
        pathfm.wait(lambda: pathfm.window_bounds().width == width, "the resized window")

    def last_column_visible():
        column = pathfm.pane("folder").screen_bounds()
        window = pathfm.window_bounds()
        return column.x >= browser_left and column.x + column.width <= window.x + window.width

    resize(900)
    pathfm.wait(lambda: pathfm.preview().screen_bounds().width < preferred, "the preview minimum to yield")
    pathfm.wait(last_column_visible, "the entire last column to stay visible")
    column = pathfm.pane("folder").screen_bounds()
    assert column.x + column.width <= pathfm.preview().screen_bounds().x
    resize(480)
    pathfm.wait(lambda: pathfm.preview() is None, "the preview to yield to browsing")
    # The drawer can disappear before its deferred focus restoration reaches the column.
    pathfm.wait(lambda: pathfm.focused_name() == "inner.txt", "focus to return to the listing")
    pathfm.keyboard.press("Down")
    pathfm.wait_for_selection(["nested-notes.txt"])
    resize(900)
    pathfm.wait(lambda: pathfm.preview_shows("nested preview fixture"), "the same selection after expansion")
    pathfm.wait(last_column_visible, "the last column beside the resumed preview")
    resize(1200)
    pathfm.wait(lambda: pathfm.preview().screen_bounds().width == preferred, "the preferred preview width to return")


@pytest.mark.parametrize("fixture_tree,filename,word", [
    ({"selection.md": "alpha bravo charlie delta\n\nsecond paragraph\n"}, "selection.md", "alpha"),
    ({"selection.docx": Path(__file__).resolve().parents[2] / "fixtures/documents/report.docx"}, "selection.docx", "Quarterly"),
], indirect=["fixture_tree"])
@pytest.mark.preferences(single_click_previews=False)
def test_rendered_document_word_and_shift_selection(pathfm, filename, word):
    pathfm.select_entry_with_keyboard(filename)
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows(word), "rendered document text")
    pathfm.keyboard.press("ctrl+l")
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("selection-cleared")
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.press("ctrl+c")
    pathfm.keyboard.press("Escape")
    row = pathfm.wait(lambda: pathfm.preview().find(role="list item"), "first prose row")
    text = row.find_all(role="panel")[-1]
    bounds = text.screen_bounds()
    start = (bounds.x + 17, bounds.center[1])
    end = (bounds.x + bounds.width * 3 // 4, bounds.center[1])
    pathfm.pointer.double_click(text, at=start)
    pathfm.keyboard.press("ctrl+c")
    assert table_clipboard_text(pathfm) == word
    pathfm.pointer.click(text, at=start)
    pathfm.pointer.click(text, at=end, modifiers=["shift"])
    pathfm.keyboard.press("ctrl+c")
    copied = table_clipboard_text(pathfm)
    assert copied.startswith(word) and len(copied) > len(word)
    pathfm.keyboard.press("ctrl+Home")
    pathfm.keyboard.press_repeatedly("shift+Right", 5)
    pathfm.keyboard.press("ctrl+c")
    assert table_clipboard_text(pathfm) == word[:5]
    pathfm.keyboard.press_repeatedly("shift+Left", 2)
    pathfm.keyboard.press("ctrl+c")
    assert table_clipboard_text(pathfm) == word[:3]
    assert pathfm.selected_names() == [filename]


@pytest.mark.parametrize("fixture_tree,filename", [
    ({"find.txt": "alpha needle omega\nsecond NEEDLE line\n", "after.txt": "unrelated text\n"}, "find.txt"),
    ({"find.txt": "alpha needle omega\n" + "padding line\n" * 600 + "second NEEDLE line\n", "after.txt": "unrelated text\n"}, "find.txt"),
    ({"find.py": "# alpha needle omega\n" + "# padding line\n" * 600 + "# second NEEDLE line\n", "after.txt": "unrelated text\n"}, "find.py"),
    ({"find.md": "alpha needle omega\n\nsecond NEEDLE line\n", "after.txt": "unrelated text\n"}, "find.md"),
], indirect=["fixture_tree"], ids=["source", "virtual-source", "incremental-source", "rendered"])
@pytest.mark.parametrize("tenxer", [
    pytest.param(False, marks=pytest.mark.preferences(tenxer_mode=False), id="default"),
    pytest.param(True, marks=pytest.mark.preferences(tenxer_mode=True), id="tenxer"),
])
@pytest.mark.preferences(single_click_previews=False, type_to_search=False)
def test_preview_find_navigates_content_without_filtering_files(pathfm, filename, tenxer):
    pathfm.select_entry_with_keyboard(filename)
    selected_before = pathfm.selected_names()
    entries_before = pathfm.entry_names()
    pathfm.keyboard.press("l" if tenxer else "space")
    pathfm.wait(lambda: pathfm.preview_shows("alpha needle omega"), "preview text")
    if not tenxer:
        pathfm.keyboard.press("Right")
    pathfm.wait(lambda: pathfm.focused_name() is None, "preview keyboard ownership")
    find_key = "/" if tenxer else "ctrl+f"
    pathfm.keyboard.press(find_key)
    field = pathfm.wait(lambda: pathfm.preview().find(role="text", name="Find in preview"), "preview find field")
    pathfm.keyboard.type_text("needle")
    pathfm.wait(lambda: pathfm.preview_shows("Match 1 of 2"), "first match")
    pathfm.keyboard.press("Return")
    pathfm.wait(lambda: pathfm.preview_shows("Match 2 of 2"), "Enter to find the next match")
    pathfm.keyboard.press("shift+Return")
    pathfm.wait(lambda: pathfm.preview_shows("Match 1 of 2"), "Shift+Enter to find the previous match")
    pathfm.pointer.click(pathfm.preview().find(role="button", name="Previous match"))
    pathfm.wait(lambda: pathfm.preview_shows("Match 2 of 2"), "previous match to wrap")
    pathfm.pointer.click(pathfm.preview().find(role="button", name="Next match"))
    pathfm.wait(lambda: pathfm.preview_shows("Match 1 of 2"), "next match to wrap")
    pathfm.pointer.click(pathfm.preview().find(role="button", name="Next match"))
    pathfm.wait(lambda: pathfm.preview_shows("Match 2 of 2"), "next match")
    pathfm.keyboard.press("Escape")
    pathfm.wait(lambda: pathfm.preview().find(role="text", name="Find in preview") is None, "find dismissal")
    pathfm.keyboard.press("ctrl+c")
    assert table_clipboard_text(pathfm) == "NEEDLE"
    assert pathfm.selected_names() == selected_before
    assert pathfm.entry_names() == entries_before
    pathfm.keyboard.press(find_key)
    pathfm.wait(lambda: pathfm.preview().find(role="text", name="Find in preview"), "find to reopen")
    if filename.endswith(".md"):
        pathfm.pointer.click(pathfm.preview().find(role="button", name="View source"))
        pathfm.wait(lambda: pathfm.preview_shows("Match 1 of 2"), "query to follow the source view")
        pathfm.pointer.click(pathfm.preview().find(role="button", name="View rendered"))
        pathfm.wait(lambda: pathfm.preview_shows("Match 1 of 2"), "query to follow the rendered view")
        pathfm.pointer.click(pathfm.preview().find(role="text", name="Find in preview"))
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("missing passage")
    pathfm.wait(lambda: pathfm.preview_shows("No matches"), "empty search results")
    pathfm.keyboard.press("Escape")
    pathfm.wait(lambda: pathfm.preview().find(role="text", name="Find in preview") is None, "find to dismiss without closing the document")
    pathfm.pointer.click(pathfm.preview().find(role="button", name=f"Close preview ({'i' if tenxer else 'Space'})"))
    pathfm.wait(lambda: pathfm.preview() is None, "preview to close")
    pathfm.select_entry_with_keyboard("after.txt")
    selected_after = pathfm.selected_names()
    pathfm.keyboard.press("l" if tenxer else "space")
    pathfm.wait(lambda: pathfm.preview_shows("unrelated text"), "a different file preview")
    pathfm.pointer.click(pathfm.preview().find(role="button", name=f"Find in preview ({'/' if tenxer else 'Ctrl+F'})"))
    field = pathfm.wait(lambda: pathfm.preview().find(role="text", name="Find in preview"), "find in the new preview")
    assert field.text == ""
    pathfm.keyboard.press("Escape")
    assert pathfm.selected_names() == selected_after


LONG_DOCUMENT = {
    "long.txt": "".join(f"document line {line}\n" for line in range(400)),
    "notes.txt": "the quick brown fox\n",
    "package.deb": "!<arch>\n",
    "empty": {},
}


@pytest.mark.parametrize("fixture_tree", [LONG_DOCUMENT], indirect=True)
@pytest.mark.parametrize(
    "mode",
    [
        pytest.param("List", marks=pytest.mark.preferences(browser_mode="list"), id="list"),
        pytest.param("Columns", marks=pytest.mark.preferences(browser_mode="columns"), id="columns"),
    ],
)
@pytest.mark.preferences(tenxer_mode=True, type_to_search=False, single_click_previews=False)
def test_tenxer_l_enters_the_preview_and_h_returns_without_navigating(pathfm, fixture_tree, mode):
    root = pathfm.current_directory()
    pathfm.select_entry_with_keyboard("long.txt")
    names = pathfm.entry_names()
    selection = pathfm.selected_names()

    pathfm.keyboard.press("l")
    pathfm.wait(lambda: pathfm.preview_shows("document line 0"), "l to open the preview")
    pathfm.wait(lambda: pathfm.focused_name() is None, "the preview to own the keys")
    for key in ("l", "Right", "j", "End", "ctrl+u", "Page_Down", "Home", "space"):
        pathfm.keyboard.press(key)
    assert pathfm.preview_shows("document line 0")
    assert pathfm.focused_name() is None, "preview keys stayed in the preview"
    assert pathfm.current_directory() == root
    assert pathfm.selected_names() == selection
    assert pathfm.entry_names() == names

    pathfm.keyboard.press("h")
    pathfm.wait_for_focused_entry("long.txt")
    assert pathfm.preview_shows("document line 0"), "h keeps the preview open"
    assert pathfm.current_directory() == root
    pathfm.keyboard.press("J")
    assert pathfm.focused_name() == "long.txt", "J scrolls without taking focus"

    pathfm.keyboard.press("Right")
    pathfm.wait(lambda: pathfm.focused_name() is None, "Right to re-enter the preview")
    pathfm.keyboard.press("Escape")
    pathfm.wait(lambda: pathfm.preview() is None, "Escape to close the preview")
    pathfm.wait_for_focused_entry("long.txt")
    pathfm.keyboard.press("l")
    pathfm.wait(lambda: pathfm.focused_name() is None, "l to re-enter the preview")
    pathfm.keyboard.press("i")
    pathfm.wait(lambda: pathfm.preview() is None, "i to close the focused preview")
    pathfm.wait_for_focused_entry("long.txt")

    pathfm.select_entry_with_keyboard("package.deb")
    pathfm.keyboard.press("l")
    pathfm.wait(lambda: pathfm.window.find(name="Nothing to preview") is not None, "the unpreviewable file hint")
    assert pathfm.preview() is None
    assert pathfm.focused_name() == "package.deb"

    pathfm.select_entry_with_keyboard("long.txt")
    pathfm.keyboard.press("l")
    pathfm.wait(lambda: pathfm.preview_shows("document line 0"), "l to reopen the preview")
    pathfm.wait(lambda: pathfm.focused_name() is None, "the preview to own the keys again")
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.press("ctrl+c")
    pathfm.keyboard.press("ctrl+l")
    field = pathfm.editable_field()
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.press("ctrl+v")
    pathfm.wait(
        lambda: "document line 0" in field.text,
        "Ctrl+A / Ctrl+C in the preview to copy the document text",
    )
