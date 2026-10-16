# SPDX-License-Identifier: MIT
import re
import subprocess
import time

import pytest

from harness.fixtures import FixtureTree

CLOCK = re.compile(r"^\d+:\d\d$")
TIMELINE = "Playback position"


@pytest.fixture
def fixture_tree():
    fixture = FixtureTree.create({})
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
         "color=c=green:size=160x90:rate=5:duration=60", "-c:v", "libx264",
         "-threads", "1", "-pix_fmt", "yuv420p", "-an", str(fixture.path("clip.mp4"))],
        check=True, capture_output=True, timeout=60,
    )
    try:
        yield fixture
    finally:
        fixture.cleanup()


def _settles(condition, timeout: float = 3.0, hold: float = 0.0) -> bool:
    deadline = time.monotonic() + timeout
    since = None
    while time.monotonic() < deadline:
        if not condition():
            since = None
        elif since is None:
            since = time.monotonic()
        if since is not None and time.monotonic() - since >= hold:
            return True
        time.sleep(0.05)
    return bool(condition())


def _elapsed(pathfm) -> str | None:
    preview = pathfm.preview()
    if preview is None:
        return None
    clocks = preview.find_all(role="label", name_matches=CLOCK.pattern)
    return clocks[0].name if clocks else None


def _tab_to(pathfm, wanted) -> object:
    for _ in range(16):
        pathfm.keyboard.press("Tab")
        node = pathfm.focused_node()
        if node is not None and wanted(node):
            return node
    raise AssertionError(f"Tab never reached the control; focus is on {pathfm.focused_node()}")


@pytest.mark.parametrize(
    "tenxer",
    [
        pytest.param(False, marks=pytest.mark.preferences(tenxer_mode=False), id="default"),
        pytest.param(True, marks=pytest.mark.preferences(tenxer_mode=True), id="tenxer"),
    ],
)
@pytest.mark.preferences(browser_mode="list", type_to_search=False, single_click_previews=False)
def test_keys_step_page_and_jump_the_timeline_and_volume(pathfm, fixture_tree, tenxer):
    pathfm.select_entry_with_keyboard("clip.mp4")
    if tenxer:
        pathfm.keyboard.press("l")
    else:
        pathfm.keyboard.press("space")
        pathfm.wait(lambda: pathfm.preview() is not None, "the preview")
        pathfm.keyboard.press("Right")
    pathfm.wait(lambda: pathfm.preview_shows("1:00"), "the clip duration")
    pathfm.wait(lambda: pathfm.focused_name() is None, "the preview to own the keys")
    mismatches = []
    # The volume sits in the header, before the timeline in focus order.
    volume = _tab_to(pathfm, lambda node: node.role == "slider" and node.name != TIMELINE)
    assert volume.numeric_value == 0.0, "the harness starts muted"
    for key, value, muted in (("Right", 0.1, "false"), ("Page_Up", 0.3, "false"),
                              ("Down", 0.2, "false"), ("End", 1.0, "false"),
                              ("Page_Down", 0.8, "false"), ("Home", 0.0, "true")):
        pathfm.keyboard.press(key)
        settled = _settles(
            lambda: (current := volume.numeric_value) is not None
            and abs(current - value) < 0.01
            and pathfm.environment.read_preferences().get("preview_muted") == muted
        )
        if not settled:
            saved = pathfm.environment.read_preferences()
            mismatches.append(
                f"volume {key}: slider {volume.numeric_value}, saved volume "
                f"{saved.get('preview_volume')}, saved muted {saved.get('preview_muted')}; "
                f"expected {value}, muted={muted}"
            )

    timeline = _tab_to(pathfm, lambda node: node.role == "slider" and node.name == TIMELINE)

    # End stops on the last frame, short of the 1:00 duration. A seek within
    # 200 ms of the previous one can briefly report the earlier target, so each
    # position must hold before the next relative step.
    for key, shown in (("Right", "0:05"), ("Page_Up", "0:35"), ("Home", "0:00"),
                       ("Page_Up", "0:30"), ("Page_Down", "0:00"), ("End", "0:59"),
                       ("shift+Left", "0:29"), ("0", "0:00"), ("shift+Right", "0:30"),
                       ("G", "0:59")):
        pathfm.keyboard.press(key)
        if not _settles(lambda: _elapsed(pathfm) == shown, hold=0.4):
            mismatches.append(
                f"timeline {key}: elapsed {_elapsed(pathfm)!r}, expected {shown!r}, "
                f"AT-SPI value {timeline.numeric_value}"
            )

    # The volume slider ended muted at 0, keeping 0.8 to restore.
    for key, value, muted in (("+", 0.1, "false"), ("=", 0.2, "false"),
                              ("-", 0.1, "false"), ("-", 0.0, "true")):
        pathfm.keyboard.press(key)
        settled = _settles(
            lambda: (current := volume.numeric_value) is not None
            and abs(current - value) < 0.01
            and pathfm.environment.read_preferences().get("preview_muted") == muted
        )
        if not settled:
            saved = pathfm.environment.read_preferences()
            mismatches.append(
                f"timeline volume {key}: slider {volume.numeric_value}, saved muted "
                f"{saved.get('preview_muted')}; expected {value}, muted={muted}"
            )
    if pathfm.focused_node() != timeline:
        mismatches.append(f"the timeline lost focus to {pathfm.focused_node()}")
    assert not mismatches, "\n".join(mismatches)
