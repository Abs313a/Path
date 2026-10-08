import QtQuick
import ".." as Path

// Modal for a job that found an existing destination.
Rectangle {
    id: dlg
    property var prompt: Path.Jobs.prompt
    /// Cleared for every new prompt: "apply to all" must never carry over into the next job.
    property bool all: false
    onPromptChanged: dlg.all = false
    visible: prompt !== null
    anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.5); z: 90
    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; hoverEnabled: true; onWheel: wheel => wheel.accepted = true } // swallow background pointer input
    Rectangle {
        anchors.centerIn: parent; width: 480; height: 220; color: Path.Theme.bg; border.width: 2; border.color: Path.Theme.accent
        Column {
            anchors.fill: parent; anchors.margins: 20; spacing: 14
            Text { text: Path.T.tr("collision.title"); color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: 15; font.bold: true }
            Text { width: parent.width; wrapMode: Text.WrapAnywhere; text: dlg.prompt ? decodeURIComponent(dlg.prompt.uri.split("/").pop()) : ""; color: Path.Theme.fgDim; font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize }
            Grid {
                columns: 3; columnSpacing: 12; rowSpacing: 4
                Text { text: ""; font.pixelSize: 11 } Text { text: Path.T.tr("collision.existing"); color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 11 } Text { text: Path.T.tr("collision.incoming"); color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 11 }
                Text { text: Path.T.tr("collision.size"); color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 11 }
                Text { text: dlg.prompt ? Path.Format.bytes(dlg.prompt.existing.size) : ""; color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: 12 }
                Text { text: dlg.prompt ? Path.Format.bytes(dlg.prompt.incoming.size) : ""; color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: 12 }
                Text { text: Path.T.tr("collision.modified"); color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 11 }
                Text { text: dlg.prompt ? Path.Format.date(dlg.prompt.existing.mtime) : ""; color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: 12 }
                Text { text: dlg.prompt ? Path.Format.date(dlg.prompt.incoming.mtime) : ""; color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: 12 }
            }
            Row {
                spacing: 8
                Rectangle { objectName: "collision-all"; width: 16; height: 16; radius: 2; anchors.verticalCenter: parent.verticalCenter; color: dlg.all ? Path.Theme.accent : Path.Theme.bgDark; border.width: 1; border.color: dlg.all ? Path.Theme.accent : Path.Theme.gutter; MouseArea { anchors.fill: parent; onClicked: dlg.all = !dlg.all } }
                Text { anchors.verticalCenter: parent.verticalCenter; text: Path.T.tr("collision.applyAll"); color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 12 }
                Item { width: 40; height: 1 }
                Button { objectName: "collision-skip"; text: Path.T.tr("collision.skip"); onClicked: Path.Jobs.reply("skip", dlg.all) }
                Button { objectName: "collision-keepBoth"; text: Path.T.tr("collision.keepBoth"); onClicked: Path.Jobs.reply("keepBoth", dlg.all) }
                Button { objectName: "collision-replace"; text: Path.T.tr("collision.replace"); primary: true; onClicked: Path.Jobs.reply("replace", dlg.all) }
            }
        }
    }
}
