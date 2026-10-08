import QtQuick
import ".." as Path
import "../ui" as UI

Item {
    id: cap
    objectName: "git-capsule"
    /// The row's `git`, as `Format.gitCapsule` hands it over; null draws nothing.
    property var mark: null
    /// A selected row draws it in the bar's colour, as the letter badge does.
    property bool onBar: false
    /// The most it may take. The file's name has priority, so the caller gives it a share of the
    /// name column and a long branch elides inside that.
    property int maxWidth: 120
    readonly property color tint: onBar ? Path.Theme.bg : Path.Format.gitColor(mark)

    visible: !!mark
    implicitWidth: pill.width
    implicitHeight: pill.height
    width: implicitWidth
    height: implicitHeight

    Rectangle {
        id: pill
        // Shorter than a row, so nothing about the row's height changes.
        width: Math.min(cap.maxWidth, glyph.width + label.width + 13)
        height: 16
        radius: 2
        // Over the accent bar the surface colour is invisible, so the pill is a breath of the
        // bar's own background instead, and the text takes the badge's selected colour.
        color: cap.onBar ? Qt.rgba(Path.Theme.bg.r, Path.Theme.bg.g, Path.Theme.bg.b, 0.18) : Path.Theme.surface
        clip: true
        Row {
            anchors.centerIn: parent
            spacing: 4
            UI.Icon { id: glyph; name: "mirror"; size: 9; color: cap.tint; anchors.verticalCenter: parent.verticalCenter }
            Text {
                id: label
                objectName: "git-capsule-text"
                anchors.verticalCenter: parent.verticalCenter
                width: Math.min(implicitWidth, cap.maxWidth - 17)
                elide: Text.ElideRight
                text: cap.mark ? cap.mark.branch : ""
                color: cap.tint
                font.family: Path.Theme.mono; font.pixelSize: 10
            }
        }
    }
}
