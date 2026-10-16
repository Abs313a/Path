# SPDX-License-Identifier: MIT

from __future__ import annotations

import base64
import time
import zipfile

import pytest

from harness.fixtures import FixtureTree
from harness.interaction import SEPARATE_CLICK_GAP

# Hover and late release selection follow GTK's next event; give them time to land before asserting
# that they did not happen.
SETTLE_HOLD = 0.3


# ZIP and header-encrypted 7z containing protected.txt; password: fixture-password.
ENCRYPTED_ARCHIVES = {
    "zip": "UEsDBAoACQAAABdsM12zQ1U4JwAAABsAAAANABwAcHJvdGVjdGVkLnR4dFVUCQADXuOual7jrmp1eAsAAQToAwAABOgDAACQyEkvHVKZmURUaFrAXIjmRah+W9tCT9En6fCshzKr4S/pzBgPWBlQSwcIs0NVOCcAAAAbAAAAUEsBAh4DCgAJAAAAF2wzXbNDVTgnAAAAGwAAAA0AGAAAAAAAAQAAAKSBAAAAAHByb3RlY3RlZC50eHRVVAUAA17jrmp1eAsAAQToAwAABOgDAABQSwUGAAAAAAEAAQBTAAAAfgAAAAAA",
    "7z": "N3q8ryccAARK90rXoAAAAAAAAAAvAAAAAAAAAM2lRMsbe4LgOwc6BQCZYKv5bMKO/JVT8lQovoXQhOLoYQdQk+uWUC0i3pVYfHvs3WsWQxoB/iug9vZINEehfZwB2T+4IWJod2G0L8SsGPd8fL2S7eqrf0iiMWv3YxcjHoairfwd3pFxFkmBBuIT/XLKPJC7MVu79tKCB+pPvxRxvfdd0S2wr+A0/f/dCbpioH0eSSubzTPZlYFEs1FLcbo7KwIJFwYgAQmAgAAHCwEAASQG8QcBElMPiTvkREbaQxsUI9zKFIworgxyCgEqHRUKAAA=",
}


@pytest.fixture
def fixture_tree(request):
    extension = request.param
    if extension == "plain":
        tree = FixtureTree.create({"a.txt": "before", "bundle.zip": "", "z.txt": "after"})
        with zipfile.ZipFile(tree.path("bundle.zip"), "w") as archive:
            archive.writestr("docs/inside.txt", "inside")
            archive.writestr("docs/inner/deep.txt", "deep")
            archive.writestr("docs/more/a.txt", "a")
            archive.writestr("docs/more/b.txt", "b")
            archive.writestr("top.txt", "top")
            archive.writestr("zz.txt", "last")
    else:
        tree = FixtureTree.create({f"encrypted.{extension}": ""})
        tree.path(f"encrypted.{extension}").write_bytes(base64.b64decode(ENCRYPTED_ARCHIVES[extension]))
    try:
        yield tree
    finally:
        tree.cleanup()


def archive_row(pathfm, text):
    preview = pathfm.preview()
    if preview is None:
        return None
    for row in preview.find_all(role="list item"):
        if any(label.name == text for label in row.find_all(role="label")):
            return row
    return None


@pytest.mark.parametrize("fixture_tree", ["plain"], indirect=True)
@pytest.mark.parametrize("enter_key", ["Right", "Return", "space"])
@pytest.mark.parametrize("automatic", [
    pytest.param(True, marks=pytest.mark.preferences(single_click_previews=True), id="automatic"),
    pytest.param(False, marks=pytest.mark.preferences(single_click_previews=False), id="manual"),
])
@pytest.mark.preferences(browser_mode="columns", type_to_search=False)
def test_columns_archive_preview_waits_for_explicit_entry(pathfm, fixture_tree, enter_key, automatic):
    root = pathfm.current_directory()
    pathfm.select_entry_with_keyboard("a.txt")
    pathfm.keyboard.press("Down")
    pathfm.wait_for_focused_entry("bundle.zip")
    if automatic:
        pathfm.wait(lambda: pathfm.preview_shows("docs/"), "the passive archive contents")
        assert pathfm.preview().find(states={"selected"}) is None
        member = pathfm.settle(archive_row(pathfm, "top.txt"))
        pathfm.pointer.move_to(*member.screen_bounds().center)
        pathfm.settle(member)
        time.sleep(SETTLE_HOLD)
        assert pathfm.preview().find(states={"selected"}) is None, "hovering selected a member"
        assert pathfm.focused_name() == "bundle.zip"
    else:
        assert pathfm.preview() is None

    pathfm.keyboard.press("Down")
    pathfm.wait_for_focused_entry("z.txt")
    pathfm.keyboard.press("Up")
    pathfm.wait_for_focused_entry("bundle.zip")
    if automatic:
        pathfm.wait(lambda: pathfm.preview_shows("docs/"), "the archive contents again")
    pathfm.keyboard.press(enter_key)
    pathfm.wait(lambda: pathfm.focused_name() is None, "explicit entry to focus the archive tree")
    pathfm.wait(lambda: pathfm.preview_shows("docs/"), "the explicitly opened archive contents")
    pathfm.keyboard.press("Right")
    pathfm.wait(lambda: pathfm.preview_shows("inside.txt"), "Right to open the archive folder")
    pathfm.keyboard.press("Escape")
    pathfm.wait_for_focused_entry("bundle.zip")
    pathfm.keyboard.press("Down")
    pathfm.wait_for_focused_entry("z.txt")
    assert pathfm.current_directory() == root
    assert sorted(path.name for path in fixture_tree.root.iterdir()) == ["a.txt", "bundle.zip", "z.txt"]


@pytest.mark.parametrize("fixture_tree", ["plain"], indirect=True)
@pytest.mark.preferences(browser_mode="list", type_to_search=False)
def test_archive_rows_select_on_click_not_hover(pathfm, fixture_tree):
    pathfm.select_entry("bundle.zip")
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("docs/"), "the archive contents")
    pathfm.wait(
        lambda: archive_row(pathfm, "docs/").has_state("selected"),
        "the first member to be highlighted",
    )

    zz = pathfm.settle(archive_row(pathfm, "zz.txt"))
    pathfm.pointer.move_to(*zz.screen_bounds().center)
    pathfm.settle(zz)
    time.sleep(SETTLE_HOLD)
    assert not zz.has_state("selected"), "hovering selected a member"
    assert archive_row(pathfm, "docs/").has_state("selected")
    pathfm.keyboard.press("Down")
    pathfm.wait(
        lambda: archive_row(pathfm, "top.txt").has_state("selected"),
        "Down to continue from the highlighted member, not the hovered one",
    )

    pathfm.pointer.click(archive_row(pathfm, "top.txt"))
    pathfm.wait(lambda: archive_row(pathfm, "top.txt").has_state("selected"), "the clicked file")
    assert pathfm.preview_shows("top.txt") and not pathfm.preview_shows("inside.txt")
    pathfm.keyboard.press("Down")
    pathfm.wait(lambda: archive_row(pathfm, "zz.txt").has_state("selected"), "Down from the clicked file")

    pathfm.pointer.click(archive_row(pathfm, "docs/"), modifiers=["ctrl"])
    pathfm.wait(lambda: pathfm.preview_shows("inside.txt"), "a Ctrl+click to open the folder")
    pathfm.keyboard.press("Left")
    pathfm.wait(lambda: pathfm.preview_shows("top.txt"), "Left to return to the archive root")

    docs = archive_row(pathfm, "docs/").screen_bounds()
    pathfm.pointer.click(archive_row(pathfm, "docs/"), at=(docs.center[0], docs.y + 1))
    pathfm.wait(lambda: pathfm.preview_shows("inside.txt"), "a click on the row's edge to open the folder")
    pathfm.keyboard.press("Left")
    pathfm.wait(lambda: pathfm.preview_shows("top.txt"), "Left to return to the archive root")

    time.sleep(SEPARATE_CLICK_GAP)
    pathfm.pointer.double_click(archive_row(pathfm, "docs/"))
    pathfm.wait(lambda: pathfm.preview_shows("inner/"), "a double-click to open the folder")
    assert not pathfm.preview_shows("deep.txt"), "a double-click opened two levels"
    assert archive_row(pathfm, "inner/").has_state("selected")

    time.sleep(SEPARATE_CLICK_GAP)
    pathfm.pointer.double_click(archive_row(pathfm, "more/"))
    pathfm.wait(lambda: pathfm.preview_shows("b.txt"), "a double-click to open the second folder")
    time.sleep(SETTLE_HOLD)
    assert archive_row(pathfm, "a.txt").has_state("selected"), "the double-click's second release moved the highlight"

    pathfm.keyboard.press("Escape")
    pathfm.wait(lambda: pathfm.preview() is None, "Escape to close the archive preview")
    assert sorted(path.name for path in fixture_tree.root.iterdir()) == ["a.txt", "bundle.zip", "z.txt"]


@pytest.mark.parametrize("fixture_tree", ["zip", "7z"], indirect=True)
def test_archive_password_retry_crosses_the_real_sandbox(pathfm, fixture_tree):
    filename = next(fixture_tree.root.iterdir()).name
    pathfm.select_entry(filename)
    pathfm.keyboard.press("space")
    pathfm.wait(lambda: pathfm.preview_shows("Password-protected archive"), "the password prompt")
    assert not pathfm.preview_shows("protected.txt")

    pathfm.wait(
        lambda: pathfm.preview().find(states={"editable", "focused"}),
        "the password entry to take focus",
    )
    pathfm.keyboard.type_text("dismiss-this-password")
    pathfm.keyboard.press("Escape")
    pathfm.wait(lambda: pathfm.preview() is None, "Escape to close the password prompt")
    pathfm.wait_for_focused_entry(filename)
    pathfm.keyboard.press("space")
    pathfm.wait(
        lambda: pathfm.preview() and pathfm.preview().find(states={"editable", "focused"}),
        "the reopened password entry to take focus",
    )
    pathfm.keyboard.type_text("incorrect-password")
    pathfm.keyboard.press("Return")
    pathfm.wait(lambda: pathfm.preview_shows("The password is incorrect."), "a rejected password")
    assert not pathfm.preview_shows("protected.txt")

    pathfm.wait(
        lambda: pathfm.preview().find(states={"editable", "focused"}),
        "the cleared password entry to take focus",
    )
    pathfm.keyboard.type_text("fixture-password")
    pathfm.pointer.click(pathfm.preview().find(role="button", name="Unlock"))
    pathfm.wait(lambda: pathfm.preview_shows("protected.txt"), "the unlocked archive listing")
    assert not pathfm.preview_shows("synthetic archive contents")
    assert sorted(path.name for path in fixture_tree.root.iterdir()) == [filename]
    pathfm.pointer.click(pathfm.preview().find(role="button", name="Close preview (Space)"))
    pathfm.wait(lambda: pathfm.preview() is None, "the preview to close")


@pytest.mark.parametrize("fixture_tree", ["zip"], indirect=True)
@pytest.mark.preferences(browser_mode="list", tenxer_mode=True, type_to_search=False)
def test_tenxer_password_and_archive_previews_keep_their_keys(pathfm, fixture_tree):
    filename = next(fixture_tree.root.iterdir()).name
    root = pathfm.current_directory()
    pathfm.select_entry_with_keyboard(filename)

    pathfm.keyboard.press("l")
    pathfm.wait(
        lambda: pathfm.preview() and pathfm.preview().find(states={"editable", "focused"}),
        "l to hand the keys to the password entry",
    )
    pathfm.keyboard.type_text("hjkl q~")
    assert pathfm.environment.read_preferences().get("tenxer_mode") == "true", "q was typed"
    assert pathfm.current_directory() == root
    assert pathfm.preview().find(states={"editable", "focused"}) is not None
    pathfm.keyboard.press("shift+Tab")
    pathfm.wait_for_focused_entry(filename)
    assert pathfm.preview_shows("Password-protected archive"), "Shift+Tab keeps the prompt"

    pathfm.keyboard.press("l")
    pathfm.wait(
        lambda: pathfm.preview().find(states={"editable", "focused"}),
        "l to return to the password entry",
    )
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("fixture-password")
    pathfm.keyboard.press("Return")
    pathfm.wait(lambda: pathfm.preview_shows("protected.txt"), "the unlocked archive listing")
    for key in ("l", "Return", "j", "k", "space"):
        pathfm.keyboard.press(key)
    assert pathfm.preview_shows("protected.txt")
    assert pathfm.focused_name() is None, "the archive tree keeps the keys"
    assert sorted(path.name for path in fixture_tree.root.iterdir()) == [filename]

    pathfm.keyboard.press("h")
    pathfm.wait_for_focused_entry(filename)
    assert pathfm.preview_shows("protected.txt"), "h at the archive root keeps the preview"
    assert pathfm.current_directory() == root
    pathfm.keyboard.press("l")
    pathfm.wait(lambda: pathfm.focused_name() is None, "l to re-enter the archive tree")
    pathfm.keyboard.press("Escape")
    pathfm.wait(lambda: pathfm.preview() is None, "Escape to close the archive preview")
    pathfm.wait_for_focused_entry(filename)
    assert sorted(path.name for path in fixture_tree.root.iterdir()) == [filename]
