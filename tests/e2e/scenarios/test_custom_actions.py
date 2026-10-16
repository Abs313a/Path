# SPDX-License-Identifier: MIT

import tomllib

import pytest

from harness.tree import Atspi


def _open_new_action(pathfm):
    assert pathfm.window.find(role="button", name="Settings").activate()
    actions = pathfm.wait(
        lambda: pathfm.window.find(role="button", name="Actions"), "Actions settings"
    )
    assert actions.activate()
    create = pathfm.wait(
        lambda: pathfm.window.find(role="button", name="New action…"), "New action"
    )
    assert create.activate()
    return pathfm.wait(
        lambda: pathfm.window.find(role="dialog", name="New action"), "New action"
    )


def test_action_editor_tabs_validate_save_and_reopen(pathfm):
    _open_new_action(pathfm)

    def editor(title="New action"):
        return pathfm.wait(
            lambda: pathfm.window.find(role="dialog", name=title), title
        )

    dialog = editor()

    def control(name, role=None):
        return pathfm.wait(lambda: dialog.find(name=name, role=role), name)

    def tab(name):
        pathfm.pointer.click(control(name, "page tab"))
        pathfm.wait(
            lambda: control(name, "page tab").has_state("selected"), f"{name} tab"
        )

    def fill(name, value):
        node = control(name, "text")
        pathfm.pointer.click(node)
        pathfm.keyboard.press("ctrl+a")
        for index, line in enumerate(value.split("\n")):
            if index:
                pathfm.keyboard.press("Return")
            pathfm.keyboard.type_text(line)
        pathfm.wait(lambda: node.text == value, f"{name} text")

    def click_backdrop():
        bounds = pathfm.window.screen_bounds()
        pathfm.pointer.click(pathfm.window, at=(bounds.x + 5, bounds.y + 5))

    fill("Name", "Batch rename")
    fill("Description", "Process selected files")
    click_backdrop()
    pathfm.pointer.click(control("scissors icon", "toggle button"))
    tab("Script")
    pathfm.pointer.click(control("Command", "toggle button"))
    fill("Program", "printf")
    fill("Arguments", "%s\\n\n{paths}")
    assert dialog.alive, "Enter in the multiline editor must not submit the form"

    tab("Behavior")
    assert not control("Stop", "toggle button").has_state("sensitive")
    pathfm.pointer.click(control("Per item", "toggle button"))
    pathfm.wait(
        lambda: control("Stop", "toggle button").has_state("sensitive"),
        "per-item failure policy to become available",
    )
    pathfm.pointer.click(control("Stop", "toggle button"))
    pathfm.pointer.click(control("Menu item", "toggle button"))
    fill("Extensions", "txt")
    pathfm.pointer.click(pathfm.settle(control("Create action", "button")))
    pathfm.wait(
        lambda: control("Script", "page tab").has_state("selected"),
        "invalid argument token to return to Script",
    )
    action_dir = pathfm.environment.config_home / "pathfm/actions/batch-rename"
    assert not action_dir.exists(), "invalid drafts must not write an action"
    fill("Arguments", "%s\\n\n{path}")
    pathfm.pointer.click(pathfm.settle(control("Create action", "button")))
    manifest = action_dir / "action.toml"
    pathfm.wait(manifest.exists, "the action manifest")
    pathfm.wait(
        lambda: pathfm.window.find(role="dialog", name="New action") is None,
        "the saved editor to close",
    )
    saved = tomllib.loads(manifest.read_text())
    assert saved["name"] == "Batch rename"
    assert saved["description"] == "Process selected files"
    assert saved["icon"] == "scissors"
    assert saved["menu"] == "top"
    assert saved["when"]["extensions"] == ["txt"]
    assert saved["run"]["runtime"] == "command"
    assert saved["run"]["program"] == "printf"
    assert saved["run"]["args"] == ["%s\\n", "{path}"]
    assert saved["run"]["mode"] == "per-item"
    assert saved["run"]["on_error"] == "stop"

    assert pathfm.window.find(role="button", name="Edit").activate()
    dialog = editor("Edit action")
    name = control("Name", "text")
    pathfm.wait(lambda: name.has_state("focused"), "Name focused on opening the editor")
    text = Atspi.Accessible.get_text_iface(name.accessible)
    assert Atspi.Text.get_n_selections(text) == 0
    assert Atspi.Text.get_caret_offset(text) == len(saved["name"])
    pathfm.keyboard.type_text(" edited")
    pathfm.wait(lambda: name.text == saved["name"] + " edited", "typing appends to the action name")
    assert control("Id", "text").text == "batch-rename"
    assert not control("Id", "text").has_state("editable")
    tab("Script")
    assert control("Arguments", "text").text == "%s\\n\n{path}"
    click_backdrop()
    fill("Program", "false")
    pathfm.keyboard.press("Escape")
    pathfm.wait(
        lambda: pathfm.window.find(role="dialog", name="Edit action") is None,
        "Escape to discard the edit",
    )
    assert tomllib.loads(manifest.read_text()) == saved

    assert pathfm.window.find(role="button", name="Close settings").activate()
    pathfm.wait(
        lambda: pathfm.window.find(role="button", name="Close settings") is None,
        "Settings to close",
    )
    pathfm.open_context_menu("todo.txt")
    assert "Batch rename" in pathfm.menu_items()
    pathfm.dismiss_menu()


def test_batch_rename_template_confirms_before_renaming_and_opens_jobs(pathfm):
    editor = _open_new_action(pathfm)
    pathfm.pointer.click(editor.find(role="page tab", name="Script"))
    pathfm.pointer.click(editor.find(name="Library"))
    picker = pathfm.wait(lambda: pathfm.window.find(name="Script library"), "library")
    pathfm.pointer.click(picker.find(role="text", name="Search templates"))
    pathfm.keyboard.type_text("rename")
    pathfm.pointer.click(pathfm.wait(lambda: picker.find(role="button", name="Batch rename"), "rename template"))
    pathfm.wait(lambda: pathfm.window.find(name="Script library") is None, "applied template")
    pathfm.pointer.click(editor.find(role="page tab", name="Behavior"))
    pathfm.pointer.click(editor.find(role="toggle button", name="Menu item"))
    confirm = next(node for node in editor.find_all(name="Confirm") if node.role in {"check box", "toggle button", "switch"})
    pathfm.pointer.click(confirm)
    pathfm.pointer.click(editor.find(role="button", name="Create action"))
    pathfm.wait(lambda: pathfm.window.find(role="dialog", name="New action") is None, "saved template")
    assert pathfm.window.find(role="button", name="Close settings").activate()
    pathfm.wait(lambda: pathfm.window.find(role="button", name="Close settings") is None, "settings closed")
    originals = {name: pathfm.fixture.path(name).read_bytes() for name in ("readme.md", "todo.txt")}
    pathfm.select_entry("readme.md")
    pathfm.click_entry_with("todo.txt", ["ctrl"])
    pathfm.wait(lambda: set(pathfm.selected_names()) == set(originals), "both files selected")
    pathfm.open_context_menu("todo.txt")
    pathfm.choose_menu_item("Batch rename")
    confirmation = pathfm.wait(lambda: pathfm.window.find(role="dialog", name="Run this action?"), "confirmation")
    assert pathfm.window.find(role="button", name="Minimize") is None
    pathfm.pointer.click(confirmation.find(role="button", name="Cancel"))
    pathfm.wait(lambda: pathfm.window.find(role="dialog", name="Run this action?") is None, "cancelled confirmation")
    for name, contents in originals.items():
        assert pathfm.fixture.path(name).read_bytes() == contents
    assert pathfm.window.find(name="1 job finished") is None
    pathfm.open_context_menu("todo.txt")
    pathfm.choose_menu_item("Batch rename")
    confirmation = pathfm.wait(lambda: pathfm.window.find(role="dialog", name="Run this action?"), "confirmation")
    pathfm.pointer.click(confirmation.find(role="button", name="Run"))
    pathfm.wait(lambda: pathfm.window.find(role="label", name_matches="Done in "), "automatically opened rename result")
    assert pathfm.window.find(role="dialog", name="Run this action?") is None
    pathfm.pointer.click(pathfm.window.find(role="button", name="Details"))
    pathfm.wait(lambda: pathfm.window.find(role="label", name_matches="001_readme.md"), "rename output")
    for index, (name, contents) in enumerate(originals.items(), start=1):
        renamed = f"{index:03d}_{name}"
        assert pathfm.fixture.path(renamed).read_bytes() == contents
        assert not pathfm.fixture.path(name).exists()


@pytest.fixture
def numbered_action(test_environment):
    output = test_environment.root / "numbered-action"
    directory = test_environment.config_home / "pathfm/actions/record-names"
    directory.mkdir(parents=True)
    (directory / "action.toml").write_text(
        'schema_version = 1\nid = "record-names"\nname = "Record names"\nmenu = "top"\n\n'
        '[when]\nextensions = ["txt"]\n\n'
        '[run]\nruntime = "command"\nprogram = "/bin/sh"\nconfirm = true\n'
        f'args = ["-c", "printf \'%s\\\\n\' \\"$@\\" >> \'{output}\'", "sh", "{{paths}}"]\n'
    )
    return output


@pytest.mark.preferences(tenxer_mode=True, type_to_search=False, single_click_previews=False)
def test_tenxer_numbered_action_confirms_before_running(numbered_action, pathfm):
    pathfm.select_entry_with_keyboard("todo.txt")

    pathfm.keyboard.press(";")
    pathfm.wait(lambda: pathfm.window.find(role="label", name=";-") is not None, "the armed action chord")
    pathfm.keyboard.press("2")
    pathfm.wait(lambda: pathfm.window.find(role="label", name="No action 2") is not None, "a vacant slot")

    pathfm.keyboard.press(";")
    pathfm.keyboard.press("1")
    confirmation = pathfm.wait(lambda: pathfm.window.find(role="dialog", name="Run this action?"), "confirmation")
    pathfm.pointer.click(confirmation.find(role="button", name="Cancel"))
    pathfm.wait(lambda: pathfm.window.find(role="dialog", name="Run this action?") is None, "cancelled confirmation")
    assert not numbered_action.exists()
    pathfm.wait_for_focused_entry("todo.txt")

    pathfm.keyboard.press(";")
    pathfm.keyboard.press("1")
    confirmation = pathfm.wait(lambda: pathfm.window.find(role="dialog", name="Run this action?"), "confirmation")
    pathfm.pointer.click(confirmation.find(role="button", name="Run"))
    pathfm.wait(lambda: pathfm.window.find(role="label", name_matches="Done in ") is not None, "Jobs to show the completed run")
    assert numbered_action.read_text().splitlines() == [str(pathfm.fixture.path("todo.txt"))]
