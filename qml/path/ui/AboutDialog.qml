import QtQuick
import ".." as Path

// About path: the panel you get from the gear menu. Laid out the way macOS does it — the mark,
// the name, the version under it, and the project credit at the foot.
Rectangle {
    id: dlg
    anchors.fill: parent
    visible: false
    color: Qt.rgba(0, 0, 0, 0.5)
    z: 96

    property var about: ({})

    function open() {
        Path.Daemon.request("About", {}, ok => { if (ok) dlg.about = ok })
        visible = true
        panel.forceActiveFocus()
    }
    function close() { visible = false; closed() }
    signal closed()

    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; hoverEnabled: true; onClicked: mouse => { if (mouse.button === Qt.LeftButton) dlg.close() }; onWheel: wheel => wheel.accepted = true }

    Rectangle {
        id: panel
        anchors.centerIn: parent
        width: 380; height: col.height + 56
        radius: 12
        color: Path.Theme.bg
        border.width: 1; border.color: Path.Theme.line
        focus: dlg.visible
        Keys.onEscapePressed: dlg.close()
        Keys.onReturnPressed: dlg.close()
        MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; hoverEnabled: true } // panel input never reaches the backdrop

        ToggleButton {
            anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 6
            icon: "x"; tip: Path.T.tr("common.close"); onClicked: dlg.close()
        }

        Column {
            id: col
            y: 28
            width: parent.width
            spacing: 6

            Image {
                objectName: "about-icon"
                anchors.horizontalCenter: parent.horizontalCenter
                width: 112; height: 112
                source: "../assets/path-about.png"
                fillMode: Image.PreserveAspectFit
            }
            Item { width: 1; height: 8 }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Path"; color: Path.Theme.fg
                font.family: Path.Theme.mono; font.pixelSize: 26; font.bold: true
            }
            Text {
                objectName: "about-tagline"
                anchors.horizontalCenter: parent.horizontalCenter
                text: Path.T.tr("about.tagline")
                color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 12
            }
            Item { width: 1; height: 10 }
            Text {
                objectName: "about-version"
                anchors.horizontalCenter: parent.horizontalCenter
                text: Path.T.tr("about.version", { version: dlg.about.version || "—" })
                color: Path.Theme.fgDim; font.family: Path.Theme.mono; font.pixelSize: 12
            }
            Item { width: 1; height: 16 }
            Rectangle { anchors.horizontalCenter: parent.horizontalCenter; width: parent.width - 80; height: 1; color: Path.Theme.line }
            Item { width: 1; height: 14 }
            Text {
                objectName: "about-credit"
                anchors.horizontalCenter: parent.horizontalCenter
                text: Path.T.tr("about.crafted")
                color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 11
            }
        }
    }
}
