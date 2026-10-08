import QtQuick
import QtTest
import "../../qml/path" as Path
import "../../qml/path/ui" as UI
import "../../qml/path/views" as Views
import PathTest

TestCase {
    id: tc
    name: "ModalPointer"
    when: windowShown
    visible: true
    width: 1000; height: 800

    FakeDaemon { id: fake }
    Path.Pane { id: pane }
    Views.ListRow { id: row; y: 400; width: tc.width; pane: pane; rowIndex: 0 }
    Component { id: settingsC; UI.SettingsWindow {} }
    Component { id: aboutC; UI.AboutDialog {} }
    Component { id: confirmC; UI.ConfirmDialog {} }
    Component { id: integrationC; UI.IntegrationDialog {} }
    Component { id: collisionC; UI.CollisionPrompt {} }
    Component { id: shareC; UI.ShareSheet {} }
    Component { id: locationC; UI.LocationDialog {} }
    Component { id: rulesC; UI.MirrorRulesDialog {} }
    property var dialog: null

    function init() {
        Wire.reset()
        fake.tree = { "file:///modal-test": [fake.file("background.txt")] }
        pane.listing.daemon = fake
        pane.open("file:///modal-test")
        pane.selection.clear()
        mouseMove(tc, 1, 1)
    }
    function cleanup() {
        if (dialog) { dialog.destroy(); dialog = null }
        mouseMove(tc, 1, 1)
    }
    function test_background_pointer_is_blocked_data() {
        return [
            { tag: "settings", component: settingsC },
            { tag: "about", component: aboutC },
            { tag: "confirm", component: confirmC },
            { tag: "integration", component: integrationC },
            { tag: "collision", component: collisionC },
            { tag: "share", component: shareC },
            { tag: "location", component: locationC },
            { tag: "mirror-rules", component: rulesC },
        ]
    }
    function test_background_pointer_is_blocked(data) {
        const mark = findChild(row, "rowmark")
        mouseMove(row, 20, row.height / 2)
        tryVerify(() => mark.color.a > 0, 1000, "the uncovered row responds to hover")
        dialog = data.component.createObject(tc, { visible: true })
        verify(dialog !== null)
        for (const x of [30, 500]) {
            mouseMove(row, x, row.height / 2)
            tryCompare(mark, "color", Qt.rgba(0, 0, 0, 0), 1000,
                       "neither the scrim nor the dialog lets background hover through")
        }
        mouseClick(row, 500, row.height / 2, Qt.RightButton)
        verify(!pane.selection.has(0), "background right-click cannot select the row")
        dialog.visible = false
        mouseMove(tc, 1, 1)
        mouseMove(row, 20, row.height / 2)
        tryVerify(() => mark.color.a > 0, 1000, "hover resumes after closing")
    }
}
