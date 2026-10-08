import QtQuick
import ".." as Path

Rectangle {
    id: win
    visible: false
    anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.5); z: 95
    signal copyText(string text)

    property var job: null              // the job, or null for a location's log
    property string location: ""
    property string heading: ""
    property var lines: []
    property double next: 0
    property double dropped: 0
    property string filter: ""
    property bool follow: true

    function openJob(j) { job = j; location = ""; heading = Path.Jobs.headline(j) + " — log"; _begin() }
    function openLocation(name) { job = null; location = name; heading = Path.T.tr("log.connectionLog", { name: name }); _begin() }
    function close() { visible = false }
    function _begin() { lines = []; next = 0; dropped = 0; filter = ""; filterInput.text = ""; follow = true; visible = true; fetch(); filterInput.forceActiveFocus() }

    function fetch() {
        if (!visible) return
        const done = (ok, err) => {
            if (!ok) return
            if (ok.lines.length) lines = lines.concat(ok.lines).slice(-4000)
            next = ok.next; dropped = ok.dropped
            if (follow) Qt.callLater(() => view.positionViewAtEnd())
        }
        if (job) Path.Daemon.request("JobLog", { job: job.id, from: next }, done)
        else Path.Daemon.request("LocationLog", { location: location, from: next }, done)
    }
    Connections { target: Path.Jobs; function onChanged() { win.fetch() } }
    property Timer tick: Timer { interval: 1000; repeat: true; running: win.visible; onTriggered: win.fetch() }

    readonly property var shownLines: filter === "" ? lines : lines.filter(l => (l.text + " " + l.source).toLowerCase().indexOf(filter.toLowerCase()) >= 0)
    readonly property double t0: lines.length ? lines[0].t : 0
    function stamp(t) { const s = Math.max(0, (t - t0) / 1000); return "+" + (s < 100 ? s.toFixed(2) : Math.round(s)) + "s" }
    function asText() { return (dropped ? Path.T.tr("log.dropped", { n: dropped }) + "\n" : "") + shownLines.map(l => stamp(l.t) + "  " + l.level.padEnd(5) + "  " + l.source + "  " + l.text).join("\n") + "\n" }

    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; hoverEnabled: true; onPressed: win.close(); onWheel: wheel => wheel.accepted = true }
    Keys.onEscapePressed: win.close()

    Rectangle {
        objectName: "joblog-card"
        anchors.centerIn: parent
        width: Math.min(900, parent.width - 48); height: Math.min(620, parent.height - 48)
        radius: 4; color: Path.Theme.bg; border.width: 1; border.color: Path.Theme.gutter
        MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; hoverEnabled: true }

        Item {
            id: top
            width: parent.width; height: 44
            Text { x: 16; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 420; elide: Text.ElideMiddle; text: win.heading; color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: 13; font.bold: true }
            Row {
                anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter; spacing: 8
                Rectangle {
                    width: 200; height: 28; radius: 2; color: Path.Theme.bgDark; border.width: 1; border.color: filterInput.activeFocus ? Path.Theme.accent : Path.Theme.gutter
                    TextInput {
                        id: filterInput
                        objectName: "joblog-filter"
                        anchors.fill: parent; anchors.margins: 7; clip: true; verticalAlignment: TextInput.AlignVCenter
                        color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: 12
                        onTextChanged: win.filter = text
                        Keys.onEscapePressed: { if (text !== "") text = ""; else win.close() }
                        Text { visible: !parent.text.length; text: Path.T.tr("log.filter"); color: Path.Theme.muted; font: parent.font; anchors.verticalCenter: parent.verticalCenter }
                    }
                }
                Button { objectName: "joblog-copy"; text: Path.T.tr("log.copyAll"); onClicked: win.copyText(win.asText()) }
                Button { objectName: "joblog-close"; text: Path.T.tr("common.close"); onClicked: win.close() }
            }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Path.Theme.line }
        }

        Text {
            id: droppedNote
            objectName: "joblog-dropped"
            visible: win.dropped > 0
            anchors.top: top.bottom; x: 16; height: visible ? 24 : 0; verticalAlignment: Text.AlignVCenter
            text: Path.T.tr("log.dropped", { n: win.dropped }); color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 11
        }

        ListView {
            id: view
            objectName: "joblog-lines"
            NaturalScroll { }
            anchors.top: droppedNote.bottom; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: foot.top
            anchors.leftMargin: 16; anchors.rightMargin: 8
            clip: true; boundsBehavior: Flickable.StopAtBounds
            model: win.shownLines
            // Scrolled away from the end is "leave me here"; back at the end is "follow again".
            onMovementEnded: win.follow = atYEnd
            onContentYChanged: if (moving || dragging) win.follow = atYEnd
            delegate: Row {
                required property var modelData
                width: view.width; spacing: 10
                readonly property bool own: modelData.source === "path"
                readonly property color ink: modelData.level === "error" ? Path.Theme.danger : (modelData.level === "warn" ? Path.Theme.yellow : (own ? Path.Theme.fg : Path.Theme.fgDim))
                Text { width: 64; horizontalAlignment: Text.AlignRight; text: win.stamp(modelData.t); color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 11 }
                Text { width: 150; elide: Text.ElideRight; text: modelData.source; color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 11 }
                // What the libraries say sits a little back from what path says.
                Text { width: parent.width - 64 - 150 - 20; wrapMode: Text.WrapAnywhere; text: modelData.text; color: parent.ink; opacity: parent.own || modelData.level !== "debug" ? 1 : 0.8; font.family: Path.Theme.mono; font.pixelSize: 11 }
            }
        }
        Text {
            visible: win.shownLines.length === 0
            anchors.centerIn: view
            text: win.lines.length ? "Nothing matches" : "Nothing logged yet"; color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 12
        }

        Item {
            id: foot
            anchors.bottom: parent.bottom; width: parent.width; height: 28
            Rectangle { width: parent.width; height: 1; color: Path.Theme.line }
            Text {
                x: 16; anchors.verticalCenter: parent.verticalCenter
                text: win.shownLines.length + (win.filter ? " of " + win.lines.length : "") + " lines" + (win.follow ? "" : " · scrolled — End to follow")
                color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 11
            }
        }
    }
}
