import QtQuick
import ".." as Path

Rectangle {
    id: sheet
    visible: false
    anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.5); z: 92
    property var plugin: null
    property var target: null
    property var uris: []
    property var values: ({})
    property string status: ""
    function open(p, t, u) {
        plugin = p; target = t; uris = u; status = ""
        const v = {}; for (const f of (p.compose || [])) v[f.key] = f.default || ""
        values = v
        if (!(p.compose || []).length) { send(); return }
        visible = true
    }
    function send() {
        visible = false
        Path.Daemon.request("Share", { plugin: plugin.id, uris: uris, target: target ? target.id : null, compose: values }, (ok, err) => { if (err) Path.Jobs.showToast({ text: err.message, undoable: false }) })
    }
    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; hoverEnabled: true; onWheel: wheel => wheel.accepted = true }
    Rectangle {
        anchors.centerIn: parent; width: 480; height: 120 + (sheet.plugin ? (sheet.plugin.compose || []).length * 66 : 0); color: Path.Theme.bg; border.width: 2; border.color: Path.Theme.accent
        Column {
            anchors.fill: parent; anchors.margins: 20; spacing: 12
            Text { text: Path.T.tr(sheet.target ? "share.titleTo" : "share.title", { n: sheet.uris.length, plugin: sheet.plugin ? sheet.plugin.name : "", target: sheet.target ? sheet.target.name : "" }); color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: 15; font.bold: true }
            Repeater {
                model: sheet.plugin ? sheet.plugin.compose : []
                delegate: FormField { required property var modelData; field: modelData; value: sheet.values[modelData.key] || ""; onEdited: v => { const nv = Object.assign({}, sheet.values); nv[modelData.key] = v; sheet.values = nv } }
            }
            Row { spacing: 8; anchors.right: parent.right
                Button { text: Path.T.tr("common.cancel"); onClicked: sheet.visible = false }
                Button { text: Path.T.tr("share.send"); primary: true; onClicked: sheet.send() } }
        }
    }
    Keys.onEscapePressed: visible = false
}
