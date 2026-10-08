import QtQuick
import ".." as Path

Item {
    id: pop
    visible: false
    z: 60
    /// Where its pointer aims: the orb's centre, in this item's parent's coordinates.
    property real aimX: parent ? parent.width - 22 : 0
    property real aimY: parent ? parent.height - Path.Theme.barHeight : 0
    signal logRequested(var job)
    signal revealRequested(string uri)

    /// When it was last closed by something other than the orb: a click on the orb lands just
    /// after the outside-click that closed it, and must count as that close, not as a reopen.
    property double _closedAt: 0
    function open() { entries = Path.Jobs.shown(); visible = true; Path.Jobs.markSeen() }
    function close() { if (visible) { visible = false; _closedAt = Date.now() } }
    function toggle() { if (visible) { visible = false; return } if (Date.now() - _closedAt > 250) open() }

    /// Rebuilt only while it is up: hidden, the model and the orb are all that need to move.
    property var entries: []
    /// Which entries have their file-in-hand row open, by job id.
    property var opened: ({})
    Connections { target: Path.Jobs; function onChanged() { if (pop.visible) { pop.entries = Path.Jobs.shown(); Path.Jobs.markSeen() } } }

    anchors.fill: parent
    // Anywhere else closes it.
    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; hoverEnabled: true; onPressed: pop.close(); onWheel: wheel => wheel.accepted = true }

    Rectangle {
        id: card
        objectName: "activity-card"
        width: Math.min(400, pop.width - 16)
        height: Math.min(header.height + Math.max(listCol.height, 64) + 2, pop.aimY - 24)
        x: Math.max(8, Math.min(pop.width - width - 8, pop.aimX - width + 28))
        y: pop.aimY - height - 10
        radius: 12; color: "transparent"; border.width: 1; border.color: Path.Theme.gutter
        // Darker than the default frost : the entries are read against it.
        Frost { anchors.fill: parent; radius: parent.radius; tintOpacity: 0.92; z: -2 }
        // Swallows what lands on the card, so only a click OUTSIDE closes.
        MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; hoverEnabled: true }

        // The point, sliding along the bottom edge to stay on the orb but never into a corner.
        Rectangle {
            width: 14; height: 14; rotation: 45; color: Path.Theme.bgDark; border.width: 1; border.color: Path.Theme.gutter
            x: Math.max(card.radius + 4, Math.min(card.width - card.radius - 18, pop.aimX - card.x - 7)); y: card.height - 8; z: -1
        }
        Rectangle { x: 1; width: card.width - 2; y: card.height - 12; height: 11; color: Path.Theme.bgDark; radius: 10 }

        Item {
            id: header
            width: parent.width; height: 40
            Text { anchors.centerIn: parent; text: Path.T.tr("activity.title"); color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: 13; font.bold: true }
            Rectangle {
                objectName: "activity-clear"
                visible: pop.entries.some(j => !Path.Jobs.live(j))
                anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
                width: clearText.implicitWidth + 20; height: 22; radius: 11
                color: clearArea.containsMouse ? Path.Theme.surface : "transparent"; border.width: 1; border.color: Path.Theme.gutter
                Text { id: clearText; anchors.centerIn: parent; text: Path.T.tr("activity.clear"); color: Path.Theme.fgDim; font.family: Path.Theme.mono; font.pixelSize: 11 }
                MouseArea { id: clearArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: Path.Jobs.clear() }
            }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Path.Theme.line }
        }

        Flickable {
            id: scroller
            NaturalScroll { }
            anchors.top: header.bottom; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.bottomMargin: 2
            contentHeight: listCol.height; clip: true; boundsBehavior: Flickable.StopAtBounds
            Column {
                id: listCol
                width: scroller.width
                Text {
                    objectName: "activity-empty"
                    visible: pop.entries.length === 0
                    width: parent.width; height: 64; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    text: Path.T.tr("orb.idle"); color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 12
                }
                Repeater {
                    // Newest at the top; an entry keeps its place when it finishes.
                    model: pop.entries.slice().reverse()
                    delegate: ActivityEntry {
                        required property var modelData
                        required property int index
                        width: listCol.width
                        job: modelData
                        first: index === 0
                        expanded: pop.opened[modelData.id] === true
                        onToggleDetail: { const o = Object.assign({}, pop.opened); o[modelData.id] = !o[modelData.id]; pop.opened = o }
                        onLog: pop.logRequested(modelData)
                        onReveal: { pop.close(); pop.revealRequested(modelData.revealUri) }
                    }
                }
            }
        }
    }
}
