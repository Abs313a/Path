import QtQuick
import ".." as Path

Item {
    id: root
    property string uri: ""
    property string name: ""
    property var row: null
    /// A test's fake; the real singleton otherwise.
    property var daemon: null
    function d() { return daemon || Path.Daemon }
    property string text: ""
    /// `[[offset, length, kind]…]` in UTF-16 units, as the daemon sent them; none for prose.
    property var runs: []
    readonly property bool coloured: runs.length > 0
    /// The text as rich text with a span per run. Only what a run needs is escaped: `&`, `<`,
    /// `>`, and the newlines and doubled spaces rich text would otherwise fold.
    function richText() {
        const esc = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, "<br>").replace(/  /g, "&nbsp; ")
        let out = "", at = 0
        for (const r of runs) {
            const from = r[0], len = r[1], colour = Path.Theme.code[r[2]]
            if (from < at || len <= 0) continue
            out += esc(text.slice(at, from))
            const piece = esc(text.slice(from, from + len))
            out += colour ? "<span style=\"color:" + colour + "\">" + piece + "</span>" : piece
            at = from + len
        }
        return "<span style=\"white-space:pre-wrap\">" + out + esc(text.slice(at)) + "</span>"
    }
    property bool truncated: false
    property real bytes: 0
    property bool reading: false
    property string error: ""
    focus: true

    /// The URI last read, so the two ways a URI can arrive (set before the item is complete, or
    /// bound after) read the file once between them.
    property string _readFor: ""
    onUriChanged: read()
    Component.onCompleted: read()
    function read() {
        const u = uri
        if (u === _readFor) return
        _readFor = u
        text = ""; runs = []; truncated = false; error = ""; bytes = 0
        if (!u) return
        reading = true
        d().request("ReadText", { uri: u }, (ok, err) => {
            // Moved on before it answered — or gone: the window closed or switched kind while
            // the daemon was reading, and the view this closure belongs to no longer exists
            // (seen as "Cannot read property 'uri' of null" in a live session).
            if (!root || u !== root.uri) return
            root.reading = false
            if (err) { root.error = err.message; return }
            root.text = ok && ok.text ? ok.text : ""
            root.runs = ok && ok.runs && ok.runs.length ? ok.runs : []
            root.truncated = !!ok && ok.truncated === true
            root.bytes = ok && ok.bytes ? ok.bytes : 0
        })
    }

    Flickable {
        anchors.fill: parent
        anchors.bottomMargin: cut.visible ? cut.height : 0
        contentWidth: width; contentHeight: edit.height + 24
        clip: true; boundsBehavior: Flickable.StopAtBounds
        NaturalScroll { }
        TextEdit {
            id: edit
            objectName: "quicklook-text"
            x: 16; y: 12; width: parent.width - 32
            readOnly: true; selectByMouse: true
            wrapMode: TextEdit.Wrap
            textFormat: root.coloured ? TextEdit.RichText : TextEdit.PlainText
            text: root.coloured ? root.richText() : root.text
            color: Path.Theme.fgDim; selectionColor: Path.Theme.accent; selectedTextColor: Path.Theme.bg
            font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize
        }
    }
    // The file went on past what was read: said where the reading stops.
    Rectangle {
        id: cut
        objectName: "quicklook-cut"
        visible: root.truncated
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        height: 26; color: Path.Theme.bgDark
        Rectangle { width: parent.width; height: 1; color: Path.Theme.line }
        Text {
            anchors.centerIn: parent
            text: Path.T.tr("quicklook.cut", { n: Math.max(1, Math.round(root.bytes / (1024 * 1024))) })
            color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 11
        }
    }
    Text {
        anchors.centerIn: parent
        visible: root.reading || root.error !== ""
        text: root.error !== "" ? root.error : Path.T.tr("quicklook.reading")
        color: root.error !== "" ? Path.Theme.danger : Path.Theme.muted
        width: Math.min(parent.width - 48, 420); horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
        font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize
    }
}
