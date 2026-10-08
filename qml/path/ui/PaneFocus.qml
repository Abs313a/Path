import QtQuick

Item {
    id: pf
    signal wanted()
    /// Off with one pane: there is nothing to choose between.
    property bool active: true
    PointHandler {
        enabled: pf.active
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
        onActiveChanged: if (active) pf.wanted()
    }
}
