import QtQuick
import QtTest
import "../../qml/path" as Path
import PathTest

TestCase {
    id: tc
    name: "Wire"
    when: windowShown
    visible: true

    function init() { Wire.reset() }

    function test_a_submitted_operation_is_recorded_with_its_op() {
        Path.Jobs.submit({ op: "rename", uri: "file:///home/t/a.txt", name: "b.txt" })
        const req = Wire.last("Submit")
        verify(req !== null)
        compare(req.op.op, "rename")
        compare(req.op.uri, "file:///home/t/a.txt")
        compare(req.op.name, "b.txt")
        compare(Wire.count("Submit"), 1)
    }

    function test_a_reply_reaches_the_callback_that_asked() {
        let got = null
        Path.Jobs.submit({ op: "trash", uris: ["file:///home/t/a.txt"] }, (ok, err) => got = ok)
        const req = Wire.last("Submit")
        Wire.reply(req.id, { job: 7 })
        compare(got.job, 7)
    }

    function test_an_error_reply_reaches_the_callback() {
        let err = null
        Path.Jobs.submit({ op: "trash", uris: [] }, (ok, e) => err = e)
        Wire.fail(Wire.last("Submit").id, "Denied", "no")
        compare(err.code, "Denied")
    }

    // Events carry no id: they are dispatched by the singleton's event signal.
    function test_a_toast_event_reaches_jobs() {
        Path.Jobs.dismissToast()
        Wire.emitEvent({ event: "Toast", job: 3, text: "Moved 2 items", undoable: true })
        verify(Path.Jobs.toast !== null)
        compare(Path.Jobs.toast.text, "Moved 2 items")
        compare(Path.Jobs.toast.undoable, true)
        Path.Jobs.dismissToast()
    }

    function test_undo_and_redo_go_out_as_their_own_requests() {
        Path.Jobs.undo()
        Path.Jobs.redo()
        compare(Wire.count("Undo"), 1)
        compare(Wire.count("Redo"), 1)
    }
}
