import QtQuick
import QtTest
import "../../qml/path/ui" as UI

TestCase {
    name: "WheelDirection"
    when: windowShown
    visible: true
    width: 300; height: 300
    Flickable {
        id: view
        anchors.fill: parent
        contentHeight: 1200
        UI.NaturalScroll { id: handler }
    }
    function init() { view.contentHeight = 1200; view.contentY = 300; handler.whenItFits = null }
    function test_wheel_down_moves_toward_later_files() {
        mouseWheel(view, 100, 100, 0, -120)
        verify(view.contentY > 300)
    }
    function test_wheel_up_moves_toward_earlier_files() {
        mouseWheel(view, 100, 100, 0, 120)
        verify(view.contentY < 300)
    }
    function test_pixel_scroll_and_boundaries() {
        handler.scroll({ pixelDelta: Qt.point(0, -30), angleDelta: Qt.point(0, 0), accepted: false })
        compare(view.contentY, 330)
        view.contentY = 0
        mouseWheel(view, 100, 100, 0, 120)
        compare(view.contentY, 0)
        view.contentY = 900
        mouseWheel(view, 100, 100, 0, -120)
        compare(view.contentY, 900)
    }
    function test_short_columns_receive_the_same_direction() {
        view.contentHeight = 100
        let delta = 0
        handler.whenItFits = d => delta = d
        mouseWheel(view, 100, 100, 0, -120)
        verify(delta > 0)
    }
}
