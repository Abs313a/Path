import QtQuick
import ".." as Path

Item {
    id: orb
    /// "idle" | "running" | "failed"
    property string state_: Path.Jobs.orbState()
    property string tip: Path.Jobs.orbTip()
    /// Lit while the popup it opens is up.
    property bool open: false
    signal clicked()

    Connections { target: Path.Jobs; function onChanged() { orb.state_ = Path.Jobs.orbState(); orb.tip = Path.Jobs.orbTip() } function onSeenFailureChanged() { orb.state_ = Path.Jobs.orbState(); orb.tip = Path.Jobs.orbTip() } }

    // A palette's "green" is a slot, not a promise: some themes put a red there.
    readonly property color go: Path.Theme.isReddish(Path.Theme.green) ? "#34b354" : Path.Theme.green
    width: 28; height: Path.Theme.barHeight

    Rectangle {
        objectName: "activity-orb-hover"
        anchors.centerIn: parent; width: 22; height: 22; radius: 11
        color: area.containsMouse || orb.open ? Path.Theme.surface : "transparent"
    }
    Rectangle {
        id: dot
        objectName: "activity-orb-dot"
        anchors.centerIn: parent
        width: orb.state_ === "failed" ? 14 : 10; height: width; radius: width / 2
        color: orb.state_ === "failed" ? Path.Theme.danger : (orb.state_ === "running" ? orb.go : Path.Theme.gutter)
        // Breathing, not blinking: about 45% to full and back over two and a half seconds.
        SequentialAnimation on opacity {
            id: breathe
            running: orb.state_ === "running"
            loops: Animation.Infinite
            NumberAnimation { from: 1; to: 0.45; duration: 1250; easing.type: Easing.InOutSine }
            NumberAnimation { from: 0.45; to: 1; duration: 1250; easing.type: Easing.InOutSine }
        }
        // Left part-way through a breath when the last job ends, it would stay dim for ever.
        readonly property bool breathing: breathe.running
        onBreathingChanged: if (!breathing) opacity = 1
        Text { visible: orb.state_ === "failed"; anchors.centerIn: parent; text: "!"; color: "white"; font.family: Path.Theme.mono; font.pixelSize: 11; font.bold: true }
    }
    Tip { visible: area.containsMouse && !orb.open; text: orb.tip; y: -height - 4 }
    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: orb.clicked() }
}
