import QtQuick
import QtTest
import "../../qml/path" as Path
import PathTest

TestCase {
    id: tc
    name: "ThemeIcons"

    property var fake: null
    Component { id: fakeC; FakeDaemon {} }

    function init() {
        Wire.reset()
        fake = fakeC.createObject(tc)
        Path.Theme.daemon = fake
        // Naming a theme is also what empties the cache, so each test starts clean.
        Path.Theme.iconTheme = "Alpha"
        fake.reset()
    }
    function cleanup() {
        Path.Theme.daemon = null
        Path.Theme.iconTheme = ""
        fake.destroy()
    }

    // The first ask goes to the daemon and answers "" for now; the second is answered on the spot.
    function test_a_name_is_asked_for_once_then_answered_instantly() {
        let got = ""
        const first = Path.Theme.iconPath("folder", 16, p => got = p)
        compare(first, "")
        compare(fake.count("Icon"), 1)
        compare(fake.last("Icon").fields.theme, "Alpha")
        compare(fake.last("Icon").fields.size, 16)
        compare(got, "file:///icons/Alpha/16/folder.png")

        const second = Path.Theme.iconPath("folder", 16, () => {})
        compare(second, "file:///icons/Alpha/16/folder.png")
        compare(fake.count("Icon"), 1)       // no second round trip
    }

    // Size is part of the key: a 16 px folder and a 96 px folder are different files.
    function test_each_size_is_its_own_entry() {
        Path.Theme.iconPath("folder", 16, () => {})
        Path.Theme.iconPath("folder", 96, () => {})
        compare(fake.count("Icon"), 2)
        compare(Path.Theme.iconPath("folder", 96, () => {}), "file:///icons/Alpha/96/folder.png")
    }

    // Thirty rows appearing at once ask for the same handful of names. One request each.
    function test_callers_waiting_on_the_same_name_share_one_request() {
        fake.defer = true
        const answers = []
        for (let i = 0; i < 5; i++) compare(Path.Theme.iconPath("text-x-generic", 16, p => answers.push(p)), "")
        compare(fake.count("Icon"), 1)
        fake.flush()
        compare(answers.length, 5)
        for (const a of answers) compare(a, "file:///icons/Alpha/16/text-x-generic.png")
        fake.defer = false
        compare(Path.Theme.iconPath("text-x-generic", 16, () => {}), "file:///icons/Alpha/16/text-x-generic.png")
        compare(fake.count("Icon"), 1)
    }

    // A caller that throws (its delegate was destroyed while the request was in flight) must not
    // cost the callers queued behind it their answer: at first launch that left live rows on
    // path's own icon.
    function test_a_failing_caller_does_not_starve_the_others() {
        fake.defer = true
        const answers = []
        Path.Theme.iconPath("folder", 16, p => answers.push(p))
        Path.Theme.iconPath("folder", 16, () => { throw new TypeError("delegate is gone") })
        Path.Theme.iconPath("folder", 16, p => answers.push(p))
        ignoreWarning(/a waiting caller failed/)
        fake.flush()
        compare(answers.length, 2)
        for (const a of answers) compare(a, "file:///icons/Alpha/16/folder.png")
        fake.defer = false
    }

    // A new icon theme means every answer we hold is for the wrong theme.
    function test_a_theme_change_empties_the_cache() {
        Path.Theme.iconPath("folder", 16, () => {})
        compare(Path.Theme.iconPath("folder", 16, () => {}), "file:///icons/Alpha/16/folder.png")
        Path.Theme.iconTheme = "Beta"
        compare(Path.Theme.iconPath("folder", 16, () => {}), "")
        compare(fake.count("Icon"), 2)
        compare(fake.last("Icon").fields.theme, "Beta")
        compare(Path.Theme.iconPath("folder", 16, () => {}), "file:///icons/Beta/16/folder.png")
    }

    // An answer that arrives after the theme has moved on is not ours to cache or to show.
    function test_a_late_answer_for_a_theme_we_have_left_is_dropped() {
        fake.defer = true
        let got = "unset"
        Path.Theme.iconPath("folder", 16, p => got = p)
        Path.Theme.iconTheme = "Beta"
        fake.flush()
        compare(got, "unset")                                   // the callback never fired
        compare(Path.Theme.iconPath("folder", 16, () => {}), "") // and nothing was cached under Beta
    }

    // Without a theme there is nothing to resolve: the drawn icon is what shows.
    function test_no_icon_theme_means_no_request() {
        Path.Theme.iconTheme = ""
        fake.reset()
        compare(Path.Theme.iconPath("folder", 16, () => {}), "")
        compare(fake.count("Icon"), 0)
    }
}
