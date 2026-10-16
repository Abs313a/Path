# SPDX-License-Identifier: MIT
"""Saved preferences and live controls share one application-wide state."""

import subprocess

import pytest

from harness.application import binary_path
from harness.environment import process_environment


def _switch(window, name):
    return next(
        (
            node
            for node in window.find_all(name=name, rendered=False)
            if node.role in {"check box", "toggle button", "switch"}
        ),
        None,
    )


def _open_settings(pathfm, window):
    button = window.find(role="button", name="Settings")
    assert button is not None and button.activate()
    pathfm.wait(lambda: _switch(window, "Folder peeking"), "General settings to exist")


@pytest.mark.preferences(
    folder_peeking=False, type_to_search=False, single_click_previews=False,
    columns_mirror_selection=False,
    filter_include_subfolders=False, open_folder_after_drop=False,
)
def test_preferences_sync_across_windows_and_restart(pathfm):
    variables = process_environment()
    variables.update(pathfm.environment.variables())
    variables.update(pathfm.display.environment)
    subprocess.run(
        [str(binary_path()), str(pathfm.fixture.root)],
        env=variables,
        cwd=pathfm.fixture.root,
        check=True,
        timeout=30,
        capture_output=True,
    )
    windows = pathfm.wait(
        lambda: (
            frames
            if len(frames := pathfm.application.application_node.find_all(
                role="frame", name="Path"
            )) == 2
            else None
        ),
        "two windows in the same Path application",
    )
    for window in windows:
        _open_settings(pathfm, window)
    for label, key in [
        ("Folder peeking", "folder_peeking"),
        ("Type to search", "type_to_search"),
        ("Single-click file previews", "single_click_previews"),
        ("Mirror columns selection", "columns_mirror_selection"),
        ("Include subfolders", "filter_include_subfolders"),
        ("Open folder after dropping files", "open_folder_after_drop"),
    ]:
        switches = [_switch(window, label) for window in windows]
        assert all(not toggle.has_state("checked") for toggle in switches)
        assert switches[0].activate()
        pathfm.wait(
            lambda: all(toggle.has_state("checked") for toggle in switches),
            f"{label} to enable in both windows",
        )
        assert switches[1].activate()
        pathfm.wait(
            lambda: all(not toggle.has_state("checked") for toggle in switches),
            f"{label} to disable in both windows",
        )
        pathfm.wait(
            lambda: pathfm.environment.read_preferences().get(key) == "false",
            f"{label} to be saved",
        )
    pathfm.application.stop()
    pathfm.application.start()
    _open_settings(pathfm, pathfm.window)
    for label in [
        "Folder peeking", "Type to search", "Single-click file previews",
        "Include subfolders", "Open folder after dropping files",
    ]:
        assert not _switch(pathfm.window, label).has_state("checked")


def _search_button(window):
    return window.find(role="button", name="Search (Ctrl+K)")


def _close_button(window):
    return window.find(role="button", name="Close window")


@pytest.mark.preferences(tenxer_mode=True)
def test_enabled_tenxer_applies_before_settings_and_survives_restart(pathfm):
    assert _search_button(pathfm.window) is None
    assert _close_button(pathfm.window) is not None
    pathfm.application.stop()
    pathfm.application.start()
    assert _search_button(pathfm.window) is None
    assert _close_button(pathfm.window) is not None
    assert pathfm.environment.read_preferences().get("tenxer_mode") == "true"


@pytest.mark.preferences(language="fr")
def test_language_selection_and_auto_detection_apply_after_relaunch(pathfm):
    settings = pathfm.wait(
        lambda: pathfm.window.find(role="button", name="Paramètres"),
        "saved French language before opening Settings",
    )
    pathfm.pointer.click(settings)
    language = pathfm.wait(
        lambda: pathfm.window.find(role="button", name="Langue"), "French language selector"
    )
    pathfm.pointer.click(language)
    japanese = pathfm.wait(
        lambda: pathfm.window.find(role="label", name="日本語"), "Japanese autonym"
    )
    pathfm.pointer.click(japanese)
    pathfm.wait(
        lambda: pathfm.environment.read_preferences().get("language") == '"ja"',
        "manual language saved",
    )
    pathfm.wait(
        lambda: pathfm.window.find(role="button", name="Redémarrer maintenant"),
        "restart notice remains in the running French language",
    )
    assert pathfm.window.find(role="button", name="Langue") is not None
    assert pathfm.window.find(role="button", name="言語") is None

    pathfm.application.stop()
    pathfm.application.start()
    settings = pathfm.wait(
        lambda: pathfm.window.find(role="button", name="設定"), "Japanese after relaunch"
    )
    pathfm.pointer.click(settings)
    language = pathfm.wait(
        lambda: pathfm.window.find(role="button", name="言語"), "Japanese language selector"
    )
    pathfm.pointer.click(language)
    automatic = pathfm.wait(
        lambda: pathfm.window.find(role="label", name="自動検出"), "Auto-detect in Japanese"
    )
    pathfm.pointer.click(automatic)
    pathfm.wait(
        lambda: pathfm.environment.read_preferences().get("language") == '"auto"',
        "Auto-detect saved",
    )
    assert pathfm.window.find(role="button", name="言語") is not None

    pathfm.application.stop()
    pathfm.application.start()
    pathfm.wait(
        lambda: pathfm.window.find(role="button", name="Settings"),
        "Auto-detect returns to the isolated C.UTF-8 environment's English UI",
    )


def _tab_to(pathfm, node):
    for _ in range(60):
        if node.has_state("focused"):
            return
        before = pathfm.focused_node()
        pathfm.keyboard.press("Tab")
        pathfm.wait(lambda: pathfm.focused_node() != before, "Tab to move focus", timeout=5)
    raise AssertionError(f"Tab never reached {node}")


@pytest.mark.preferences(folder_peeking=False)
def test_unsaved_changes_show_one_notice_and_return_focus(pathfm):
    settings = pathfm.environment.settings_path
    title = "Settings can't be saved"
    _open_settings(pathfm, pathfm.window)
    settings.unlink()
    settings.mkdir()

    def notice():
        return pathfm.window.find(role="dialog", name=title)

    assert notice() is None, "startup changes nothing"
    toggle = _switch(pathfm.window, "Folder peeking")
    _tab_to(pathfm, toggle)
    pathfm.keyboard.press("space")
    text = " ".join(
        node.text for _, node in pathfm.wait(notice, "the save notice").walk() if node.text
    )
    assert "Changes last only until Path closes" in text
    assert str(settings) in text.replace("\n", "")
    assert toggle.has_state("checked")
    pathfm.keyboard.press("Escape")
    pathfm.wait(
        lambda: notice() is None and toggle.has_state("focused"),
        "the notice to close with focus back on the switch",
    )

    pathfm.keyboard.press("space")
    pathfm.wait(lambda: not toggle.has_state("checked"), "the second change to apply")
    assert notice() is None, "one notice per failure streak"
    assert settings.is_dir()
