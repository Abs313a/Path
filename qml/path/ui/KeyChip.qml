import QtQuick
import ".." as Path

Row {
    property string key: ""
    property string label: ""
    objectName: "chip-" + key
    spacing: 5
    Rectangle {
        height: 16; width: keyText.implicitWidth + 10; radius: 2
        color: "transparent"; border.color: Path.Theme.gutter; border.width: 1
        Text { id: keyText; anchors.centerIn: parent; text: key; color: Path.Theme.fgDim; font.family: Path.Theme.mono; font.pixelSize: 10 }
    }
    Text { anchors.verticalCenter: parent.verticalCenter; text: label; color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 11 }
}
