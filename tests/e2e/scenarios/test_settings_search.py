# SPDX-License-Identifier: MIT
"""Settings-wide search keeps input focus while navigating and filtering pages."""

import pytest


@pytest.mark.parametrize("width", [1360, 640], ids=["sidebar", "compact-popover"])
def test_settings_search_filters_navigates_and_clears(pathfm, width):
    bounds = pathfm.window.screen_bounds()
    pathfm.keyboard.connection.resize_surface(bounds.width, bounds.height, width, 700)
    pathfm.wait(lambda: pathfm.window.screen_bounds().width == width, "resized window")
    settings = pathfm.window.find(role="button", name="Settings")
    assert settings is not None and settings.activate()
    if width == 640:
        button = pathfm.wait(
            lambda: pathfm.window.find(role="button", name="Search settings"),
            "compact settings search",
        )
        pathfm.pointer.click(button)
    search = pathfm.wait(
        lambda: pathfm.window.find(role="text", name="Search settings"),
        "settings search field",
    )
    original = pathfm.environment.read_preferences()
    pathfm.pointer.click(search)
    pathfm.keyboard.type_text("tezt size")
    pathfm.wait(lambda: search.text == "tezt size", "search retains focus across page changes")
    pathfm.wait(
        lambda: pathfm.window.find(role="spin button", name="Text size in pixels"),
        "nearest text-size setting",
    )
    assert pathfm.window.find(name="Reduce motion") is None
    assert pathfm.window.find(name="Search themes") is None
    preferences = pathfm.environment.read_preferences()
    for key in ("folder_peeking", "text_size", "follow_distro", "theme"):
        assert preferences.get(key) == original.get(key)

    bounds = pathfm.window.screen_bounds()
    width = 640 if width == 1360 else 1360
    pathfm.keyboard.connection.resize_surface(bounds.width, bounds.height, width, 700)
    pathfm.wait(lambda: pathfm.window.screen_bounds().width == width, "resize with an active query")
    search = pathfm.wait(
        lambda: pathfm.window.find(role="text", name="Search settings"),
        "search follows the responsive navigation",
    )
    pathfm.wait(lambda: search.has_state("focused"), "search input focus survives resize")
    assert search.text == "tezt size"
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("folder peeking")
    pathfm.wait(lambda: search.text == "folder peeking", "replace global query")
    pathfm.wait(lambda: pathfm.window.find(name="Folder peeking"), "matching General setting")
    assert pathfm.window.find(name="Single-click file previews") is None

    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("keep arrows")
    pathfm.wait(lambda: pathfm.window.find(name="Keep arrows in file list"), "arrow scope setting")
    assert pathfm.window.find(name="Folder peeking") is None

    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("default directory")
    pathfm.wait(
        lambda: pathfm.window.find(role="button", name="Home directory"),
        "startup directory setting",
    )
    assert pathfm.window.find(name="Keep arrows in file list") is None

    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("modified date format")
    date_format = pathfm.wait(
        lambda: pathfm.window.find(role="button", name="Modified date format"),
        "date format setting in General",
    )
    assert pathfm.window.find(role="label", name="General") is not None
    if width == 640:
        pathfm.pointer.click(date_format)
        pathfm.wait(
            lambda: pathfm.window.find(role="text", name="Search settings") is None,
            "compact search closes before opening date choices",
        )
    pathfm.pointer.click(date_format)
    iso = pathfm.wait(
        lambda: pathfm.window.find(role="label", name="ISO 8601"),
        "ISO date format choice",
    )
    pathfm.pointer.click(iso)
    pathfm.wait(
        lambda: pathfm.environment.read_preferences().get("date_format") == '"iso"',
        "date format selection persists from General",
    )
    # Hidden choice labels precede GTK releasing the popover's input grab.
    pathfm.wait(
        lambda: date_format.find(role="toggle button", states={"focused"}),
        "date format choices close and return focus to their button",
    )
    if width == 640:
        pathfm.pointer.click(pathfm.window.find(role="button", name="Search settings"))
    search = pathfm.wait(
        lambda: pathfm.window.find(role="text", name="Search settings"),
        "settings search after changing date format",
    )
    pathfm.pointer.click(search)
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("exclusions")
    exclusion = pathfm.wait(
        lambda: pathfm.window.find(role="text", name="Search exclusion"),
        "inline exclusion form is directly available in Settings",
    )
    if width == 640:
        pathfm.pointer.click(exclusion)
        pathfm.wait(
            lambda: pathfm.window.find(role="text", name="Search settings") is None,
            "compact search closes before editing exclusions",
        )
    pathfm.pointer.click(exclusion)
    pathfm.keyboard.type_text("private-build")
    pathfm.keyboard.press("Return")
    remove = pathfm.wait(
        lambda: pathfm.window.find(role="button", name="Remove exclusion private-build"),
        "exclusion added inline with Enter",
    )
    pathfm.wait(
        lambda: pathfm.environment.read_preferences().get("search_exclusions") == '["private-build"]',
        "inline exclusion persists",
    )
    pathfm.pointer.click(remove)
    pathfm.wait(
        lambda: pathfm.window.find(role="button", name="Remove exclusion private-build") is None,
        "exclusion removed inline",
    )
    pathfm.wait(
        lambda: "search_exclusions" not in pathfm.environment.read_preferences(),
        "removing the last exclusion persists",
    )
    if width == 640:
        pathfm.pointer.click(pathfm.window.find(role="button", name="Search settings"))
    search = pathfm.wait(
        lambda: pathfm.window.find(role="text", name="Search settings"),
        "settings search after editing exclusions",
    )
    pathfm.pointer.click(search)
    pathfm.keyboard.press("ctrl+a")
    pathfm.keyboard.type_text("unfindablequantumsetting")
    pathfm.wait(
        lambda: pathfm.window.find(role="label", name="No settings match your search."),
        "explicit empty results",
    )
    pathfm.keyboard.press("Escape")
    pathfm.wait(lambda: search.text == "", "Escape clears the query before closing Settings")
    if width == 640:
        pathfm.keyboard.press("Escape")
    pathfm.wait(
        lambda: pathfm.window.find(name="Single-click file previews"),
        "unfiltered settings restored",
    )
    assert pathfm.window.find(role="button", name="Close settings") is not None
