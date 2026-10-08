import QtQuick
import QtTest
import "../../qml/path" as Path
import "../../qml/path/ui" as UI
import PathTest

TestCase {
    name: "IntegrationDialog"
    when: windowShown
    width: 900; height: 700
    visible: true
    UI.IntegrationDialog { id: dlg; anchors.fill: parent }
    property var wasIntegration
    function init() {
        wasIntegration = Path.Settings.integration
        Wire.connectAll()
        Wire.reset()
        dlg.picked = ({ mime: true, dbus: true, portal: true })
        dlg.results = []
        dlg.busy = false
        dlg.visible = true
    }
    function cleanup() {
        dlg.visible = false
        Path.Settings.integration = wasIntegration
    }
    function test_only_reversible_dwm_titus_controls() {
        compare(dlg.items.map(i => i.id), ["mime", "dbus", "portal"])
        compare(Object.keys(dlg.picked), ["mime", "dbus", "portal"])
    }
    function test_unchecked_parts_do_not_apply_everything() {
        dlg.picked = ({ mime: false, dbus: false, portal: false })
        dlg.decide(true)
        compare(Wire.count("Integrate"), 0)
        compare(dlg.busy, false)
    }
    function test_only_selected_parts_are_sent() {
        dlg.picked = ({ mime: false, dbus: true, portal: false })
        dlg.decide(true)
        compare(Wire.last("Integrate").parts, ["dbus"])
    }
}
