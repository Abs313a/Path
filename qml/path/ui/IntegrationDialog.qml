import QtQuick
import ".." as Path

Rectangle {
    id: dlg
    visible: false
    anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.55); z: 95
    property var status: ({})
    property var picked: ({ mime: true, dbus: true, portal: true })
    property var results: []
    property bool busy: false
    readonly property var items: [
        { id: "mime", label: Path.T.tr("integration.mime"), detail: "inode/directory in ~/.config/mimeapps.list" },
        { id: "dbus", label: Path.T.tr("integration.dbus"), detail: "user D-Bus activation for org.freedesktop.FileManager1" },
        { id: "portal", label: Path.T.tr("integration.portal"), detail: "FileChooser=path;gtk in ~/.config/xdg-desktop-portal/portals.conf" },
    ]
    function open() { results = []; Path.Daemon.request("Integration", {}, ok => { if (ok) status = ok; visible = true }) }
    function decide(apply) {
        Path.Settings.set("integration", "asked", true)
        if (!apply) { visible = false; return }
        const parts = items.map(i => i.id).filter(id => picked[id])
        // An empty backend parts array means "all"; unchecked boxes must never invoke it.
        if (parts.length === 0) { visible = false; return }
        busy = true
        Path.Daemon.request("Integrate", { parts: parts }, (ok, err) => {
            busy = false
            if (err) { results = [{ part: "all", ok: false, message: err.message }]; return }
            results = ok.results; status = ok.status
            if (results.every(r => r.ok)) visible = false
        })
    }
    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; hoverEnabled: true; onWheel: wheel => wheel.accepted = true }
    Rectangle {
        anchors.centerIn: parent; width: 640; height: col.height + 48; color: Path.Theme.bg; border.width: 2; border.color: Path.Theme.accent
        Column {
            id: col; x: 24; y: 24; width: parent.width - 48; spacing: 12
            Text { text: Path.T.tr("integration.title"); color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: 16; font.bold: true }
            Text { width: parent.width; wrapMode: Text.WordWrap; text: Path.T.tr("integration.note"); color: Path.Theme.fgDim; font.family: Path.Theme.mono; font.pixelSize: 12 }
            Repeater {
                model: dlg.items
                delegate: Row {
                    required property var modelData
                    spacing: 10; width: col.width
                    Rectangle {
                        width: 16; height: 16; radius: 2; anchors.top: parent.top; anchors.topMargin: 2
                        color: dlg.picked[modelData.id] ? Path.Theme.accent : "transparent"; border.width: 1; border.color: dlg.picked[modelData.id] ? Path.Theme.accent : Path.Theme.gutter
                        Text { anchors.centerIn: parent; text: "✓"; visible: dlg.picked[modelData.id]; color: Path.Theme.bg; font.pixelSize: 11; font.bold: true }
                        MouseArea { anchors.fill: parent; onClicked: { const p = Object.assign({}, dlg.picked); p[modelData.id] = !p[modelData.id]; dlg.picked = p } }
                    }
                    Column {
                        width: parent.width - 26; spacing: 2
                        Text { width: parent.width; wrapMode: Text.WordWrap; text: modelData.label + (dlg.status[modelData.id] ? "  ·  already set" : ""); color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: 12 }
                        Text { width: parent.width; wrapMode: Text.WordWrap; text: modelData.detail; color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 11 }
                        Text { visible: !!(dlg.results.find(r => r.part === modelData.id && !r.ok)); width: parent.width; wrapMode: Text.WordWrap; text: (dlg.results.find(r => r.part === modelData.id) || {}).message || ""; color: Path.Theme.danger; font.family: Path.Theme.mono; font.pixelSize: 11 }
                    }
                }
            }
            Row {
                spacing: 8; anchors.right: parent.right
                Button { text: Path.T.tr("integration.notNow"); onClicked: dlg.decide(false) }
                Button { text: dlg.busy ? "Applying…" : "Make Path the default"; primary: true; enabled: !dlg.busy; onClicked: dlg.decide(true) }
            }
        }
    }
}
