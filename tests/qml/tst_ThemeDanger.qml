import QtQuick
import QtTest
import "../../qml/path" as Path

// Danger is a meaning, not a palette slot: a theme whose "red" is green (hackerman) must not
// turn "Move to Trash" green.
TestCase {
    name: "ThemeDanger"
    property color was
    function init() { was = Path.Theme.red }
    function cleanup() { Path.Theme.red = was }

    function test_a_red_red_is_used_as_it_is() {
        Path.Theme.red = "#f7768e"
        verify(Qt.colorEqual(Path.Theme.danger, "#f7768e"))
        Path.Theme.red = "#e06c75"
        verify(Qt.colorEqual(Path.Theme.danger, "#e06c75"))
        Path.Theme.red = "#ff5f87"                       // towards pink: still says stop
        verify(Qt.colorEqual(Path.Theme.danger, "#ff5f87"))
    }

    function test_a_green_red_is_not() {
        Path.Theme.red = "#50f872"                       // hackerman
        verify(Qt.colorEqual(Path.Theme.danger, "#f7768e"))
        verify(Path.Theme.isReddish(Path.Theme.danger))
    }

    function test_nor_is_a_grey_one() {
        Path.Theme.red = "#8a8a8a"                       // a monochrome theme: no hue to speak of
        verify(Qt.colorEqual(Path.Theme.danger, "#f7768e"))
    }

    // The same rule the other way about: "changed" is the theme's yellow, unless that yellow is
    // red (matte-black) — a modified file must not wear the colour of a conflicted one.
    function test_changed_is_never_the_colour_of_danger() {
        const y = Path.Theme.yellow
        Path.Theme.yellow = "#e5c07b"
        verify(Qt.colorEqual(Path.Theme.changed, "#e5c07b"), "a yellow yellow is used as it is")
        Path.Theme.yellow = "#b91c1c"                    // matte-black
        verify(!Path.Theme.isReddish(Path.Theme.changed), "a red yellow is not")
        verify(!Qt.colorEqual(Path.Format.gitColor({ state: "modified" }), Path.Format.gitColor({ state: "conflicted" })))
        Path.Theme.yellow = y
    }
}
