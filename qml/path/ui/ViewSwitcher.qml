import QtQuick
import ".." as Path

// One toolbar button showing the current view's icon; clicking opens the view menu
// (icon / list / columns, then Show hidden files).
Rectangle {
    id: sw
    property string view: "list"
    signal menu()
    width: 52; height: 34; radius: 2
    color: hover.containsMouse ? Path.Theme.surface : "transparent"
    Row {
        anchors.centerIn: parent; spacing: 4
        Icon { name: sw.view === "icon" ? "grid" : (sw.view === "columns" ? "columns" : (sw.view === "gallery" ? "image" : "list")); color: Path.Theme.chrome; anchors.verticalCenter: parent.verticalCenter }
        Icon { name: "chev-d"; size: 10; color: Path.Theme.chrome; anchors.verticalCenter: parent.verticalCenter }
    }
    MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; onClicked: sw.menu() }
}
