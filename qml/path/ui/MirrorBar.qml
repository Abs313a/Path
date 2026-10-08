import QtQuick
import ".." as Path

Rectangle {
    id: bar
    property Path.Pane leftPane
    property Path.Pane rightPane
    property string home: ""
    property var lastMirrored: null      // ms since epoch, or null
    signal swap()
    signal mirror(bool upload)
    signal options(point pos)
    readonly property string remoteName: { const u = rightPane && rightPane.uri.startsWith("file://") ? (leftPane ? leftPane.uri : "") : (rightPane ? rightPane.uri : ""); const m = u.match(/^[a-z]+:\/\/([^/]+)/); return m ? m[1] : "" }
    readonly property bool localLeft: leftPane && leftPane.uri.startsWith("file://")
    width: parent ? parent.width : 0; height: 44; color: Path.Theme.bg
    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Path.Theme.line }
    Row {
        anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 14; spacing: 10
        Icon { anchors.verticalCenter: parent.verticalCenter; name: bar.localLeft ? "hdd" : "server"; size: 14; color: bar.localLeft ? Path.Theme.fgDim : Path.Theme.green }
        Text { anchors.verticalCenter: parent.verticalCenter; text: bar.leftPane ? Path.Format.display(bar.leftPane.uri, bar.home) : ""; color: Path.Theme.fgDim; font.family: Path.Theme.mono; font.pixelSize: 12; elide: Text.ElideMiddle; width: Math.min(implicitWidth, 260) }
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter; width: 26; height: 26; radius: 2; color: swapHover.containsMouse ? Path.Theme.surface : "transparent"; border.width: 1; border.color: Path.Theme.gutter
            Icon { anchors.centerIn: parent; name: "mirror"; size: 12; color: Path.Theme.muted }
            MouseArea { id: swapHover; anchors.fill: parent; hoverEnabled: true; onClicked: bar.swap() }
        }
        Icon { anchors.verticalCenter: parent.verticalCenter; name: bar.localLeft ? "server" : "hdd"; size: 14; color: bar.localLeft ? Path.Theme.green : Path.Theme.fgDim }
        Text { anchors.verticalCenter: parent.verticalCenter; text: bar.rightPane ? Path.Format.display(bar.rightPane.uri, bar.home) : ""; color: Path.Theme.fgDim; font.family: Path.Theme.mono; font.pixelSize: 12; elide: Text.ElideMiddle; width: Math.min(implicitWidth, 260) }
        Item { width: parent.width - 14 * 2 - 26 - 10 * 7 - 14 * 2 - lhs.width - rhs.width - status.width - action.width; height: 1; property Item lhs: parent.children[1]; property Item rhs: parent.children[4] }
        Text { id: status; anchors.verticalCenter: parent.verticalCenter; text: bar.lastMirrored ? Path.T.tr("mirror.lastMirrored", { when: Path.Format.relative(bar.lastMirrored) }) : Path.T.tr("mirror.notYet"); color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 11 }
        // The action: accent split button with the direction arrow, the label, the key chip and an options chevron.
        Rectangle {
            id: action
            anchors.verticalCenter: parent.verticalCenter; height: 32; radius: 2; color: Path.Theme.accent
            width: actionRow.width + 18
            Row {
                id: actionRow; anchors.verticalCenter: parent.verticalCenter; x: 12; spacing: 10
                Icon { anchors.verticalCenter: parent.verticalCenter; name: "arr-u"; size: 14; color: Path.Theme.bg }
                Text { anchors.verticalCenter: parent.verticalCenter; text: Path.T.tr("mirror.barMirrorTo", { name: bar.remoteName || Path.T.tr("mirror.remote") }); color: Path.Theme.bg; font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize; font.bold: true }
                Rectangle { anchors.verticalCenter: parent.verticalCenter; width: chip.width + 12; height: 18; radius: 2; color: "transparent"; border.width: 1; border.color: Qt.rgba(Path.Theme.bg.r, Path.Theme.bg.g, Path.Theme.bg.b, 0.35)
                    Text { id: chip; anchors.centerIn: parent; text: "⌃M"; color: Path.Theme.bg; font.family: Path.Theme.mono; font.pixelSize: 10 } }
                Rectangle { anchors.verticalCenter: parent.verticalCenter; width: 22; height: 22; color: "transparent"
                    Rectangle { x: -4; width: 1; height: parent.height; color: Qt.rgba(Path.Theme.bg.r, Path.Theme.bg.g, Path.Theme.bg.b, 0.35) }
                    Icon { anchors.centerIn: parent; name: "chev-d"; size: 10; color: Path.Theme.bg }
                    MouseArea { anchors.fill: parent; onClicked: bar.options(Qt.point(action.x + action.width - 232, bar.y + bar.height)) } }
            }
            MouseArea { anchors.fill: parent; anchors.rightMargin: 30; onClicked: bar.mirror(true) }
        }
    }
}
