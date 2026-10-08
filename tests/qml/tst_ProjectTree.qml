import QtQuick
import QtTest
import "../../qml/path/views" as Views
import PathTest

TestCase {
    id: tc
    name: "ProjectTree"
    when: windowShown
    visible: true
    width: 320; height: 600

    Views.ProjectTree { id: tree; anchors.fill: parent; rootUri: "file:///home/t/site"; home: "/home/t"; focus: true }
    SignalSpy { id: left; target: tree; signalName: "leave" }

    function init() { Wire.reset(); Wire.connectAll(); left.clear(); tree.forceActiveFocus() }

    function test_the_tree_takes_the_keys() { verify(tree.activeFocus) }

    function test_escape_leaves() {
        keyClick(Qt.Key_Escape)
        compare(left.count, 1)
    }

    function test_the_chord_that_came_in_goes_out() {
        keyClick(Qt.Key_P, Qt.ControlModifier | Qt.ShiftModifier)
        compare(left.count, 1)
    }

    function test_a_bare_p_is_not_the_chord() {
        keyClick(Qt.Key_P)
        compare(left.count, 0)
    }
}
