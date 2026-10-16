# SPDX-License-Identifier: MIT
"""The saved thumbnail-worker stepper is discoverable and responds to pointer input."""

import pytest


@pytest.mark.preferences(thumbnail_workers=16)
def test_thumbnail_workers_stepper_persists_changes_and_resets(pathfm):
    settings = pathfm.window.find(role="button", name="Settings")
    assert settings is not None and settings.activate()
    search = pathfm.wait(
        lambda: pathfm.window.find(role="text", name="Search settings"),
        "settings search",
    )
    pathfm.pointer.click(search)
    pathfm.keyboard.type_text("thumbnail workers")

    def control(name):
        return pathfm.wait(
            lambda: pathfm.window.find(role="button", name=name),
            name,
        )

    for name, expected in [
        ("Decrease thumbnail workers", "15"),
        ("Increase thumbnail workers", "16"),
    ]:
        pathfm.pointer.click(control(name))
        pathfm.wait(
            lambda: pathfm.environment.read_preferences().get("thumbnail_workers") == expected,
            f"worker count saved as {expected}",
        )
    assert not control("Increase thumbnail workers").has_state("sensitive")
    reset = control("16")
    assert reset.description == "Reset thumbnail workers"
    pathfm.pointer.click(reset)
    pathfm.wait(
        lambda: pathfm.environment.read_preferences().get("thumbnail_workers") in {"1", "2", "3", "4"},
        "CPU-based default restored",
    )
