import QtQuick
import ".." as Path

Rectangle {
    id: bar
    property Path.Pane pane
    property int total: 0            // rows before filtering, for the "n of m" count
    /// How many rows the filtered listing shows now. The pane's listing's count, unless the
    /// view says otherwise: in columns it is the focused column's (0.1.1).
    property int count: pane ? pane.listing.count : 0
    /// "Filter this folder", or the folder's name when the view filters a column of its own.
    property string placeholder: Path.T.tr("filter.thisFolder")
    property alias text: input.text
    signal promote(string text)
    signal closed()
    /// The text, debounced: the shell applies it where the view says (`Shell.applyFilter`).
    signal apply(string text)

    height: 34
    color: Path.Theme.bg
    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Path.Theme.line }

    function focusInput() { input.forceActiveFocus(); input.selectAll() }
    function clear() { input.text = "" }

    Icon {
        id: glass
        x: 12; anchors.verticalCenter: parent.verticalCenter
        name: "search"; size: 13; color: input.activeFocus ? Path.Theme.accent : Path.Theme.muted
    }
    TextInput {
        id: input
        x: 32; width: Math.max(0, count.x - x - 12); height: parent.height
        verticalAlignment: TextInput.AlignVCenter; clip: true
        color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize
        selectionColor: Path.Theme.accent
        onTextChanged: debounce.restart()
        onAccepted: bar.promote(text)
        // Esc clears first, then closes, so it never loses the filter and the bar in one press.
        Keys.onEscapePressed: { if (text.length) text = ""; else bar.closed() }
        Text {
            visible: !input.text.length
            anchors.verticalCenter: parent.verticalCenter
            text: bar.placeholder; color: Path.Theme.muted; font: input.font
        }
    }
    Text {
        id: count
        anchors.right: closeBtn.left; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter
        text: bar.pane && bar.pane.filterText ? bar.count + " of " + bar.total : ""
        color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 11
    }
    ToggleButton {
        id: closeBtn
        anchors.right: parent.right; anchors.rightMargin: 4; anchors.verticalCenter: parent.verticalCenter
        icon: "x"; tip: Path.T.tr("filter.closeTip")
        onClicked: bar.closed()
    }
    Timer { id: debounce; interval: Path.Settings.timers.searchDebounceMs; onTriggered: bar.apply(input.text) }
}
