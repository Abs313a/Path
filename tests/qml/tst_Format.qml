import QtQuick
import QtTest
import "../../qml/path" as Path

TestCase {
    name: "Format"
    when: windowShown
    visible: true
    function test_bytes() {
        compare(Path.Format.bytes(0), "0 B")
        compare(Path.Format.bytes(1126), "1.1 KB")
        compare(Path.Format.bytes(84 * 1024 * 1024 + 512 * 1024), "84.5 MB")
        compare(Path.Format.bytes(2.3 * 1024 * 1024 * 1024), "2.3 GB")
    }
    function test_friendly_dates() {
        const now = Date.now()
        compare(Path.Format.friendlyDate(now - 10 * 1000), "just now")
        compare(Path.Format.friendlyDate(now - 12 * 60 * 1000), "12 min ago")
        const y = new Date(now); y.setDate(y.getDate() - 1); y.setHours(14, 2, 0, 0)
        compare(Path.Format.friendlyDate(y.getTime()), "yesterday 14:02")
        const old = new Date(2024, 8, 12, 9, 30).getTime()
        compare(Path.Format.friendlyDate(old), "12 Sep 2024")
        compare(Path.Format.friendlyDate(0), "")
        compare(Path.Format.date(old), "12 Sep 2024 09:30")
    }
    function test_relative_and_heat() {
        const now = Date.now(), h = 3600000
        compare(Path.Format.relative(now - 10 * 1000), "just now")
        compare(Path.Format.relative(now - 5 * 60 * 1000), "5 min ago")
        compare(Path.Format.relative(now - 3 * h), "3 h ago")
        compare(Path.Format.relative(now - 2 * 24 * h), "2 days ago")
        compare(Path.Format.relative(now - 21 * 24 * h), "3 weeks ago")
        compare(Path.Format.relative(now - 150 * 24 * h), "5 months ago")
        compare(Path.Format.relative(now - 800 * 24 * h), "2 years ago")
        compare(Path.Format.relative(0), "—")
        const accent = Qt.rgba(0.48, 0.64, 0.97, 1)
        fuzzyCompare(Path.Format.heat(now - h, accent).a, 0.5, 0.01)
        fuzzyCompare(Path.Format.heat(now - 24 * h, accent).a, 0.28, 0.03)
        fuzzyCompare(Path.Format.heat(now - 365 * 24 * h, accent).a, 0.05, 0.01)
        compare(Path.Format.heat(0, accent).a, 0)
    }
    function test_display_and_crumbs() {
        compare(Path.Format.display("file:///home/david/Projects/path", "/home/david"), "~/Projects/path")
        compare(Path.Format.display("file:///home/david", "/home/david"), "~")
        compare(Path.Format.display("sftp://homelab/srv/path", "/home/david"), "homelab/srv/path")
        // A bare path, which is what the trash records where a file came from as: shortened the
        // same way, and never mistaken for a URI (it used to come back as "ome/david/Projects").
        compare(Path.Format.display("/home/david/Projects", "/home/david"), "~/Projects")
        compare(Path.Format.display("/home/david", "/home/david"), "~")
        compare(Path.Format.display("/etc/hosts", "/home/david"), "/etc/hosts")
        compare(Path.Format.display("/home/david/Projects", ""), "/home/david/Projects")
        compare(Path.Format.crumbs("file:///home/david/Projects/path", "/home/david"), ["~", "Projects", "path"])
        compare(Path.Format.crumbs("file:///", "/home/david"), ["/"])
    }

    function test_clock() {
        compare(Path.Format.clock(0), "0:00")
        compare(Path.Format.clock(7400), "0:07")
        compare(Path.Format.clock(220000), "3:40")
        compare(Path.Format.clock(3725000), "1:02:05")
        compare(Path.Format.clock(undefined), "0:00")
        compare(Path.Format.clock(-5), "0:00")
    }
}
