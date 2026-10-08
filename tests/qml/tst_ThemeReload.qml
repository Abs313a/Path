import QtQuick
import QtTest
import "../../qml/path" as Path

TestCase {
    name: "ThemeReload"

    function reads() {
        const t = Path.Theme
        return [t.omarchy.reloads, t.iconsFile.reloads, t.legacy.reloads, t.olderLegacy.reloads]
    }

    function test_only_the_theme_name_is_watched() {
        const t = Path.Theme
        verify(t.themeName.watchChanges)
        for (const f of [t.omarchy, t.iconsFile, t.legacy, t.olderLegacy, t.gtk3, t.gtk4])
            verify(!f.watchChanges, f.path + " is inside a folder Omarchy replaces: a watch there dies")
    }

    function test_a_switch_reads_everything_again_and_a_second_one_does_too() {
        const before = reads()
        Path.Theme.themeName.fileChanged()
        compare(reads(), before.map(n => n + 1))
        Path.Theme.themeName.fileChanged()
        compare(reads(), before.map(n => n + 2))
    }

    function test_nothing_is_read_while_nothing_changes() {
        const before = reads()
        wait(2300)       // longer than the old timer's interval
        compare(reads(), before)
        verify(Path.Theme.poll === undefined, "the polling timer is gone")
    }

    // The files that need not exist — the older palette, GTK's settings — are read without a
    // warning in the log on every start.
    function test_optional_files_are_read_quietly() {
        const t = Path.Theme
        for (const f of [t.legacy, t.olderLegacy, t.gtk3, t.gtk4, t.iconsFile, t.omarchy, t.themeName]) verify(!f.printErrors, f.path)
    }
}
