import QtQuick
import QtTest
import "../../qml/path" as Path
import "../../qml/path/ui" as UI

TestCase {
    name: "AboutDialog"
    when: windowShown
    width: 600; height: 600
    visible: true
    UI.AboutDialog { id: dlg; anchors.fill: parent }
    property string wasLanguage

    function init() {
        wasLanguage = Path.T.language
        Path.T.language = "en"
        dlg.about = ({ version: "0.2.2", build: "private-build-hash" })
        dlg.visible = true
    }
    function cleanup() { dlg.close(); Path.T.language = wasLanguage }

    function test_version_has_no_build_stamp() {
        compare(findChild(dlg, "about-version").text, "Version 0.2.2")
    }
    function test_branding_and_supplied_logo() {
        compare(findChild(dlg, "about-tagline").text, "Light, Practical File Manager")
        compare(findChild(dlg, "about-credit").text, "ChrisTitusTech")
        const icon = findChild(dlg, "about-icon")
        verify(String(icon.source).endsWith("/assets/path-about.png"))
        compare(icon.width, 112)
        compare(icon.height, 112)
        compare(icon.fillMode, Image.PreserveAspectFit)
        tryCompare(icon, "status", Image.Ready)
    }
}
