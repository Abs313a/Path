import QtQuick
import QtTest
import "../../qml/path" as Path
import "../../qml/path/ui" as UI
import PathTest

TestCase {
    id: tc
    name: "CoreControls"
    when: windowShown
    visible: true
    width: 1200; height: 760
    Path.Shell { id: shell; width: 1200; height: 760; visible: true }
    UI.Sidebar { id: rail; compact: true; width: 44; height: 600; favorites: [{ name: "Home", uri: "file:///home/t" }] }
    property var savedView
    property var savedKeys
    function toolbar() { return findChild(shell.contentItem, "toolbar") }
    function footer(item) {
        if (item.statusInset !== undefined && item.keys !== undefined) return item
        for (let child of item.children || []) { const found = footer(child); if (found) return found }
        return null
    }
    function init() {
        savedView = Path.Settings.view; savedKeys = Path.Settings.keys
        const view = Object.assign({}, savedView); delete view.shortcutChips
        Path.Settings.view = view; Path.Settings.keys = ({})
        Wire.reset(); Wire.connectAll()
        shell.sideBySide = false; shell.locations = []
        toolbar().width = 1200
        wait(20)
    }
    function cleanup() { Path.Settings.view = savedView; Path.Settings.keys = savedKeys }

    function test_home_leads_the_sidebar_without_duplicate_search() {
        compare(rail.entries[0].kind, "favorite", "Home must lead the demo sidebar")
        compare(rail.entries[0].item.name, "Home")
        verify(findChild(rail, "sidebar-search") === null)
    }
    function test_connections_access_exists_with_no_saved_connections() {
        const button = findChild(rail, "sidebar-connections")
        verify(button !== null, "Connections access must exist with an empty list")
        verify(button.visible)
        let requests = 0
        rail.connectionsRequested.connect(() => requests++)
        mouseClick(button, button.width / 2, button.height / 2)
        compare(requests, 1)
    }
    function test_empty_connections_control_opens_add_dialog_without_connecting() {
        const button = findChild(shell.contentItem, "sidebar-connections")
        const dialog = findChild(shell.contentItem, "location-card").parent
        dialog.visible = false
        Wire.reset()
        button.clicked()
        verify(Wire.last("Plugins") !== null)
        Wire.replyTo("Plugins", { plugins: [] })
        verify(dialog.visible)
        compare(Wire.count("Connect"), 0)
        compare(Wire.count("AddLocation"), 0)
        dialog.visible = false
    }
    function test_connection_menu_preserves_saved_targets_and_add_access() {
        shell.locations = [{ name: "lab", plugin: "sftp", remoteUri: "sftp://lab/", localUri: "" }]
        const items = shell.connectionItems()
        compare(items.map(item => item.id), ["connection-lab", "addLocation"])
        compare(items[0].label, "lab")
        Wire.reset()
        items[0].action()
        compare(shell.right.uri, "sftp://lab/")
        verify(shell.split)
    }
    function test_toolbar_search_precedes_info_and_opens_existing_search() {
        const search = findChild(shell.contentItem, "toolbar-search")
        verify(search !== null, "Search must be available in the toolbar")
        verify(search.visible)
        verify(search.x < findChild(shell.contentItem, "toolbar-info").x)
        shell.toggleSearch(); if (search.active) shell.toggleSearch()
        search.clicked(); verify(search.active)
        search.clicked(); verify(!search.active)
    }
    function test_compact_menu_preserves_search_access() {
        const search = shell.hamburgerItems().find(item => item.id === "search")
        verify(search !== undefined, "Collapsed toolbar must retain Search")
        toolbar().width = 260
        verify(toolbar().compact)
        search.action()
        verify(findChild(shell.contentItem, "toolbar-search").active)
        search.action()
    }
    function test_footer_default_matches_the_original_shortcuts() {
        const bar = footer(shell.contentItem)
        verify(bar !== null)
        compare(bar.keys.map(item => item.key), ["Enter", "←", "→", "^I", "F2", "Del", "❖C", "❖V", "/", "^?"])
        compare(bar.keys.map(item => item.label), ["open", "up", "into", "info", "rename", "trash", "copy", "paste", "filter", "keys"])
    }
    function test_explicit_footer_preference_is_preserved() {
        Path.Settings.view = Object.assign({}, Path.Settings.view, { shortcutChips: false })
        compare(footer(shell.contentItem).keys.length, 0)
    }
    function test_footer_describes_rebound_and_disabled_actions() {
        Path.Settings.view = Object.assign({}, Path.Settings.view, { shortcutChips: true })
        Path.Settings.keys = ({ inspector: "F7", copy: "Ctrl+C", paste: "" })
        const keys = footer(shell.contentItem).keys
        compare(keys.find(item => item.label === "info").key, "F7")
        compare(keys.find(item => item.label === "copy").key, "^C")
        verify(!keys.some(item => item.label === "paste"))
    }
}
