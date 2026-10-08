import QtQuick
import QtTest
import "../../qml/path/ui" as UI

// Home leads the rail; connection access remains available with an empty saved list.
TestCase {
    name: "Sidebar"
    when: windowShown
    visible: true
    width: 224; height: 400
    UI.Sidebar {
        id: sidebar
        width: 224; height: 400
        favorites: [{ name: "Home", uri: "file:///home/t" }, { name: "Documents", uri: "file:///home/t/Documents" }]
        locations: [{ name: "lab", plugin: "sftp", remoteUri: "sftp://lab/", connected: false }]
    }
    SignalSpy { id: connections; target: sidebar; signalName: "connectionsRequested" }
    SignalSpy { id: opens; target: sidebar; signalName: "open" }
    readonly property var twoFavorites: [{ name: "Home", uri: "file:///home/t" }, { name: "Documents", uri: "file:///home/t/Documents" }]
    function init() { connections.clear(); opens.clear(); sidebar.keyIndex = -1 }
    function cleanup() { sidebar.height = 400; sidebar.favorites = twoFavorites }

    // Too short a window for the rail : what does not fit is under the
    // bottom edge, and the wheel brings it up.
    function test_a_short_rail_scrolls_to_what_is_below_the_edge() {
        sidebar.favorites = Array.from({ length: 12 }, (_, i) => ({ name: "f" + i, uri: "file:///home/t/f" + i }))
        sidebar.height = 160; wait(30)
        const scroll = findChild(sidebar, "sidebar-scroll")
        verify(scroll.contentHeight > sidebar.height, "more than fits: " + scroll.contentHeight)
        const last = findChild(sidebar, "sidebar-f11")
        verify(last, "the last favorite is drawn")
        verify(last.mapToItem(sidebar, 0, 0).y > sidebar.height, "the last favorite is below the edge")
        mouseWheel(scroll, 20, 80, 0, -120)
        tryVerify(() => scroll.contentY > 0, 1000, "the wheel scrolls it")
        // (A synthetic wheel is one small flick; the strip's end is reached by scrolling there.)
        scroll.contentY = scroll.contentHeight - scroll.height
        tryVerify(() => findChild(sidebar, "sidebar-f11").mapToItem(sidebar, 0, 0).y + 20 <= sidebar.height, 1000, "and the last favorite is within the strip at the end")
    }
    function test_home_is_the_first_entry() {
        compare(sidebar.entries[0].kind, "favorite")
        compare(sidebar.entries[0].item.name, "Home")
        verify(findChild(sidebar, "sidebar-search") === null)
    }
    function test_keyboard_opens_home_then_documents() {
        sidebar.moveKey(1)
        compare(sidebar.keyIndex, 0)
        sidebar.activateKey()
        compare(opens.count, 1)
        compare(opens.signalArguments[0][0], "file:///home/t")
        sidebar.moveKey(1)
        sidebar.activateKey()
        compare(opens.count, 2)
        compare(opens.signalArguments[1][0], "file:///home/t/Documents")
    }
    function test_connections_access_opens_no_fake_location() {
        const control = findChild(sidebar, "sidebar-connections")
        mouseClick(control, control.width / 2, control.height / 2)
        compare(connections.count, 1)
        compare(opens.count, 0)
    }
    function test_section_keyboard_indexes_are_consistent() {
        compare(sidebar.keyOffset("favorite", 0), 0)
        compare(sidebar.keyOffset("trash", 0), 2)
        compare(sidebar.keyOffset("connections", 0), 3)
        compare(sidebar.keyOffset("location", 0), 4)
        sidebar.keyIndex = 3
        sidebar.activateKey()
        compare(connections.count, 1)
        compare(opens.count, 0)
    }
    function test_known_folder_icons_remain_correct() {
        compare(sidebar.favIcon("Projects"), "code")
        compare(sidebar.favIcon("Desktop"), "grid")
    }
}
