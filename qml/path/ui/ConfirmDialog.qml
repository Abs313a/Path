import QtQuick
import ".." as Path

Rectangle {
    id: dlg
    visible: false
    anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.5); z: 96
    property string title: ""
    property string message: ""
    property string confirmLabel: "Delete"
    property bool danger: true
    property var _cb: null
    function ask(opts, cb) { title = opts.title || ""; message = opts.message || ""; confirmLabel = opts.label || "Delete"; danger = opts.danger !== false; _cb = cb; visible = true; box.forceActiveFocus() }
    function answer(yes) { visible = false; const cb = _cb; _cb = null; if (cb) cb(yes) }
    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; hoverEnabled: true; onClicked: mouse => { if (mouse.button === Qt.LeftButton) dlg.answer(false) }; onWheel: wheel => wheel.accepted = true }
    Rectangle {
        id: box
        anchors.centerIn: parent; width: 460; height: col.height + 44; color: Path.Theme.bg; border.width: 2; border.color: dlg.danger ? Path.Theme.danger : Path.Theme.accent
        focus: true
        Keys.onEscapePressed: dlg.answer(false)
        Keys.onReturnPressed: dlg.answer(true)
        Keys.onEnterPressed: dlg.answer(true)
        MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; hoverEnabled: true }
        Column {
            id: col; x: 22; y: 22; width: parent.width - 44; spacing: 12
            Text { text: dlg.title; color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: 15; font.bold: true }
            Text { width: parent.width; wrapMode: Text.WordWrap; text: dlg.message; color: Path.Theme.fgDim; font.family: Path.Theme.mono; font.pixelSize: 12 }
            Row {
                spacing: 8; anchors.right: parent.right
                Button { text: Path.T.tr("common.cancel"); onClicked: dlg.answer(false) }
                Rectangle {
                    width: okText.width + 32; height: 30; radius: 2; color: dlg.danger ? Path.Theme.danger : Path.Theme.accent
                    Text { id: okText; anchors.centerIn: parent; text: dlg.confirmLabel + "  ⏎"; color: Path.Theme.bg; font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize; font.bold: true }
                    MouseArea { anchors.fill: parent; onClicked: dlg.answer(true) }
                }
            }
        }
    }
}
