# SPDX-License-Identifier: MIT

from pathlib import Path
from urllib.parse import unquote, urlparse
import os

import pytest
from gi.repository import GLib

from harness import tree
from harness.browser import ENTRY_ROLES
from harness.portal import open_file_request


def _find_row(chooser, name):
    for role in ENTRY_ROLES:
        node = chooser.find(role=role, name=name)
        if node is not None:
            return node
    return None


def _row(chooser, name):
    return tree.wait_until(lambda: _find_row(chooser, name), message=f"the {name!r} row")


def _selected(chooser, name):
    row = _find_row(chooser, name)
    return row is not None and row.has_state("selected")


@pytest.mark.parametrize("browser_mode", ["list", "columns"])
def test_enter_returns_every_selected_file_in_a_multiple_open_request(
    pathfm_binary, headless_display, test_environment, fixture_tree, keyboard, pointer, browser_mode
):
    options = {
        "current_folder": GLib.Variant("ay", os.fsencode(fixture_tree.root) + b"\0"),
        "multiple": GLib.Variant("b", True),
    }
    with open_file_request(
        pathfm_binary, headless_display, test_environment, fixture_tree,
        title="Multiple selection test", options=options, browser_mode=browser_mode,
    ) as (chooser, response):
        pointer.click(_row(chooser, "readme.md"))
        pointer.click(_row(chooser, "todo.txt"), modifiers=["ctrl"])
        tree.wait_until(
            lambda: _selected(chooser, "readme.md") and _selected(chooser, "todo.txt"),
            message="both files selected",
        )
        keyboard.press("Return")

        tree.wait_until(response.done, message="portal response", timeout=20)
        status, values = response.result().unpack()
        assert status == 0
        chosen = {Path(unquote(urlparse(uri).path)).name for uri in values["uris"]}
        assert chosen == {"readme.md", "todo.txt"}


@pytest.mark.parametrize("tenxer", [False, True], ids=["default", "tenxer"])
def test_pdf_zoom_reset_in_chooser_keeps_interface_text_size(
    pathfm_binary, headless_display, test_environment, fixture_tree, keyboard, pointer, tenxer
):
    fixture_tree.path("page.pdf").write_bytes(
        (Path(__file__).resolve().parents[2] / "fixtures" / "documents" / "text.pdf").read_bytes()
    )
    options = {
        "current_folder": GLib.Variant("ay", os.fsencode(fixture_tree.root) + b"\0"),
    }
    with open_file_request(
        pathfm_binary, headless_display, test_environment, fixture_tree,
        title="PDF zoom reset", options=options, browser_mode="list",
    ) as (chooser, response):
        pointer.click(_row(chooser, "page.pdf"))
        keyboard.press("ctrl+=")
        tree.wait_until(
            lambda: test_environment.read_preferences()["text_size"] == "14",
            message="custom chooser interface text size",
        )
        keyboard.press("space")
        page = tree.wait_until(
            lambda: chooser.find(role="image", name="PDF page text"),
            message="PDF page in chooser preview",
        )
        pointer.click(page)
        if tenxer:
            keyboard.press("ctrl+shift+m")
            tree.wait_until(
                lambda: test_environment.read_preferences().get("tenxer_mode") == "true",
                message="10xer enabled in chooser",
            )
        fitted = page.screen_bounds().width
        pointer.scroll(page.screen_bounds().center, clicks=2, down=False, modifiers=["ctrl"])
        tree.wait_until(
            lambda: page.screen_bounds().width > fitted,
            message="Ctrl+wheel over the chooser PDF to enlarge its page",
        )
        keyboard.press("ctrl+0")
        tree.wait_until(
            lambda: page.screen_bounds().width == fitted,
            message="Ctrl+0 on the focused chooser PDF to restore the fitted page width",
        )
        assert test_environment.read_preferences()["text_size"] == "14"
        assert not response.done()
        keyboard.press("Escape")
        tree.wait_until(
            lambda: chooser.find(role="image", name="PDF page text") is None,
            message="preview closed before resetting interface text",
        )
        keyboard.press("ctrl+0")
        tree.wait_until(
            lambda: test_environment.read_preferences()["text_size"] == "13",
            message="interface reset after returning focus to chooser files",
        )
