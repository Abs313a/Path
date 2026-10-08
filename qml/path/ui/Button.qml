import QtQuick
import ".." as Path

Rectangle {
    id: b
    property string text: ""
    property bool primary: false
    property bool enabled: true
    /// The card's size : shorter, tighter, a smaller face.
    property bool small: false
    signal clicked()
    height: small ? 24 : 30; width: t.implicitWidth + (small ? 24 : 32); radius: 2
    activeFocusOnTab: enabled
    // Under the pointer the box lights a little; pressed, the accent is on the edge and the face
    // darkens for the length of the press — a button that gives nothing back looks broken.
    readonly property bool pressed: press.pressed
    readonly property bool hovered: press.containsMouse
    color: primary ? (pressed ? Qt.darker(Path.Theme.accent, 1.25) : Path.Theme.accent)
                   : (pressed ? Path.Theme.bgDark : (activeFocus || hovered ? Path.Theme.surface : "transparent"))
    border.width: primary && !activeFocus && !pressed ? 0 : 1
    border.color: activeFocus || pressed ? Path.Theme.accent : Path.Theme.gutter
    Keys.onReturnPressed: if (b.enabled) b.clicked()
    Keys.onEnterPressed: if (b.enabled) b.clicked()
    Keys.onSpacePressed: if (b.enabled) b.clicked()
    opacity: enabled ? 1 : 0.5
    Text { id: t; anchors.centerIn: parent; text: b.text; color: b.primary ? Path.Theme.bg : Path.Theme.fgDim; font.family: Path.Theme.mono; font.pixelSize: small ? 12 : Path.Theme.fontSize; font.bold: b.primary }
    MouseArea { id: press; anchors.fill: parent; enabled: b.enabled; hoverEnabled: true; onClicked: b.clicked() }
}
