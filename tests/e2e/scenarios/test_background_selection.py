# SPDX-License-Identifier: MIT
"""Empty-space clicks clear selection without taking over item clicks or drags."""

import subprocess

import pytest
from PIL import Image

from harness.modes import ALL_MODES


def _select_files(pathfm):
    root = pathfm.fixture.root.name
    pathfm.select_entry("readme.md", root)
    pathfm.click_entry_with("todo.txt", ["ctrl"], root)
    pathfm.wait_for_selection(["readme.md", "todo.txt"], root)
    return root


def _blank_point(pathfm, directory):
    bounds = pathfm.pane(directory).screen_bounds()
    return bounds.center[0], bounds.y + bounds.height - 60


@pytest.mark.parametrize("mode", ALL_MODES)
def test_background_click_clears_all_selection(pathfm, mode):
    root = _select_files(pathfm)
    pathfm.pointer.click(pathfm.pane(root), at=_blank_point(pathfm, root))
    pathfm.wait(lambda: not pathfm.all_selected_names(), "empty space to deselect every file")
    assert pathfm.pane().name == root


@pytest.mark.parametrize("mode", ALL_MODES)
def test_background_press_clears_selection_before_drag_intent(pathfm, mode):
    root = _select_files(pathfm)
    start = _blank_point(pathfm, root)
    end = pathfm.entry("todo.txt", root).screen_bounds().center

    def cleared_on_press():
        assert pathfm.selected_names(root) == []

    pathfm.pointer.drag_points(start, end, after_press=cleared_on_press)
    pathfm.wait(lambda: bool(pathfm.selected_names(root)), "marquee selection to survive release")


@pytest.mark.usefixtures("unreserved_columns")
def test_clicking_an_empty_column_clears_other_columns_without_closing_them(pathfm):
    pathfm.open_directory("archive")
    _select_files(pathfm)
    panes = pathfm.pane_names()
    pathfm.pointer.click(pathfm.pane("archive"), at=_blank_point(pathfm, "archive"))
    pathfm.wait(lambda: not pathfm.all_selected_names(), "empty column to clear all selections")
    assert pathfm.pane_names() == panes
    assert pathfm.current_directory() == "archive"


def test_clicking_beside_the_last_column_clears_selection(pathfm):
    root = _select_files(pathfm)
    window = pathfm.window.screen_bounds()
    pane = pathfm.pane(root).screen_bounds()
    point = (window.x + window.width - 40, pane.center[1])
    pathfm.pointer.click(pathfm.window, at=point)
    pathfm.wait(lambda: not pathfm.all_selected_names(), "blank space beside Columns to deselect")


def _write_photo(pathfm):
    Image.new("RGB", (1600, 900), "green").save(pathfm.fixture.path("photo.png"))


def _blank_preview_point(pathfm):
    preview = pathfm.preview()
    bounds = preview.screen_bounds()
    point = (bounds.center[0], bounds.y + bounds.height - 30)
    for node in preview.find_all():
        if node is preview:
            continue
        box = node.screen_bounds()
        inside = box.x <= point[0] < box.x + box.width and box.y <= point[1] < box.y + box.height
        assert not inside or node.role in ("panel", "filler", "group"), (
            f"the blank preview point lands on {node!r}"
        )
    return point


@pytest.mark.preferences(single_click_previews=True)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_preview_blank_click_keeps_the_selection_and_a_drag_still_selects(pathfm, mode):
    _write_photo(pathfm)
    root = pathfm.fixture.root.name
    pathfm.wait(lambda: pathfm.entry("photo.png", root), "the generated photo")
    pathfm.select_entry("photo.png", root)
    pathfm.wait(lambda: pathfm.preview_shows("photo.png"), "the image preview")
    point = _blank_preview_point(pathfm)
    pathfm.pointer.click(pathfm.preview(), at=point)
    pathfm.settle(pathfm.pane(root))
    assert pathfm.selected_names(root) == ["photo.png"]
    assert pathfm.preview_shows("photo.png")
    if mode == "Columns":
        assert pathfm.pane().name == root
    pathfm.pointer.drag_points(point, pathfm.entry("readme.md", root).screen_bounds().center)
    pathfm.wait(
        lambda: "readme.md" in pathfm.selected_names(root)
        and "photo.png" not in pathfm.selected_names(root),
        "a plain marquee from the preview to replace the selection",
    )


def _write_sound(pathfm):
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y", "-f", "lavfi",
            "-i", "sine=frequency=440:sample_rate=44100:duration=3",
            "-c:a", "pcm_s16le", str(pathfm.fixture.path("sound.wav")),
        ],
        check=True,
        timeout=30,
    )


def _write_clip(pathfm):
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=320x180:r=24:d=2",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2",
            "-c:v", "libx264", "-c:a", "aac", "-ac", "2", "-shortest",
            str(pathfm.fixture.path("clip.mp4")),
        ],
        check=True,
        timeout=30,
    )


@pytest.mark.preferences(single_click_previews=True)
@pytest.mark.parametrize(
    "name, write, control",
    [
        ("sound.wav", _write_sound, "Next audio file"),
        ("clip.mp4", _write_clip, "Next video"),
    ],
    ids=["audio", "video"],
)
def test_disabled_transport_click_keeps_the_selection(pathfm, name, write, control):
    write(pathfm)
    root = pathfm.fixture.root.name
    pathfm.wait(lambda: pathfm.entry(name, root), "the generated media file")
    pathfm.select_entry(name, root)
    next_button = pathfm.wait(
        lambda: pathfm.preview() and pathfm.preview().find(role="button", name=control),
        "the media transport",
    )
    assert not next_button.has_state("sensitive")
    pathfm.pointer.click(next_button)
    pathfm.settle(pathfm.pane(root))
    assert pathfm.selected_names(root) == [name]
    button = pathfm.preview() and pathfm.preview().find(role="button", name=control)
    assert button is not None
    assert not button.has_state("sensitive")
