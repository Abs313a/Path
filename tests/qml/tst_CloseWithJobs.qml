import QtQuick
import QtTest
import "../../qml/path" as Path
import PathTest

// "If path is not running, stuff should not continue in the background" — so a window closed
// while jobs run asks first, and Yes stops them. The close that can be refused is the real
// window's `closing`; here the event is handed to `closeAsked` as Qt would hand it over. (The
// daemon's half, for a path that went without asking, is `pathd/tests/shell_gone.rs`.)
TestCase {
    id: tc
    name: "CloseWithJobs"
    when: windowShown
    visible: true
    width: 200; height: 200

    Path.Shell { id: shell; width: 1200; height: 760 }
    property int quits: 0

    function job(id, more) { return Object.assign({ id: id, op: "copy", state: "running", name: "site", count: 1, title: "Copy", hidden: false }, more || {}) }
    function dialog() { return findChild(shell.contentItem, "confirm") }
    function close() { const ev = { accepted: true }; shell.closeAsked(ev); return ev.accepted }

    function init() {
        Wire.reset(); Wire.connectAll()
        quits = 0
        shell._quit = () => { tc.quits += 1 }
        shell._quitting = false
        Path.Jobs.list = []
    }
    function cleanup() { if (dialog().visible) dialog().answer(false); Path.Jobs.list = [] }

    function test_the_window_is_found() {
        verify(shell._backing, "no window to hear `closing` from")
        compare(typeof shell._backing.closing, "function")
    }
    function quitItem() { return shell.gearItems().find(it => it.id === "quit") }
    function test_gear_quit_is_last_below_about_with_divider() {
        const items = shell.gearItems()
        compare(items.slice(-2).map(it => it.id), ["about", "quit"])
        compare(quitItem().label, "Quit")
        verify(quitItem().sep === true)
    }
    function test_gear_quit_without_jobs_exits_once() {
        verify(quitItem() !== undefined, "missing Quit menu item")
        quitItem().action()
        compare(quits, 1)
        compare(Wire.count("Cancel"), 0)
    }
    function test_gear_quit_with_jobs_can_be_refused_then_confirmed() {
        verify(quitItem() !== undefined, "missing Quit menu item")
        Path.Jobs.list = [job(7)]
        quitItem().action()
        compare(quits, 0)
        verify(dialog().visible)
        dialog().answer(false)
        compare(quits, 0)
        compare(Wire.count("Cancel"), 0)
        quitItem().action()
        dialog().answer(true)
        compare(quits, 1)
        compare(Wire.requests("Cancel").map(r => r.job), [7])
    }
    function test_nothing_running_closes_without_a_word() {
        Path.Jobs.list = [job(1, { state: "done" }), job(2, { state: "failed" })]
        verify(close())
        verify(!dialog().visible)
    }
    function test_machinery_alone_is_not_worth_a_question() {
        Path.Jobs.list = [job(1, { hidden: true, op: "mirrorScan" })]
        verify(close())
        verify(!dialog().visible)
    }
    function test_a_running_job_holds_the_close_and_asks() {
        Path.Jobs.list = [job(7)]
        verify(!close(), "the window closed over a running job")
        verify(dialog().visible)
        compare(dialog().title, "Quit Path?")
        verify(dialog().message.indexOf("site") >= 0, dialog().message)
        compare(dialog().confirmLabel, "Quit")
    }
    function test_several_are_counted_and_the_queued_count_too() {
        Path.Jobs.list = [job(1), job(2, { state: "queued" }), job(3, { state: "done" })]
        verify(!close())
        verify(dialog().message.indexOf("2 jobs") === 0, dialog().message)
    }
    function test_no_keeps_path_and_the_jobs() {
        Path.Jobs.list = [job(7)]
        close()
        dialog().answer(false)
        compare(quits, 0)
        compare(Wire.count("Cancel"), 0)
        verify(!close(), "asked once, and the next close went through unasked")
    }
    function test_yes_stops_every_job_and_quits() {
        Path.Jobs.list = [job(7), job(8, { hidden: true }), job(9, { state: "done" })]
        close()
        dialog().answer(true)
        compare(Wire.requests("Cancel").map(r => r.job).sort(), [7, 8])
        compare(quits, 1)
        verify(close(), "the close that follows the quit was held up again")
    }
}
