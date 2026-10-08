import QtQuick
import QtTest
import "../../qml/path" as Path
import PathTest

// A listing cache that is destroyed lets go of its listing: the daemon is told, and the client
// no longer dispatches that listing's events to a dead object. Column view makes and destroys
// one for every folder walked into.
TestCase {
    name: "WindowCacheLifetime"
    Component { id: comp; Path.WindowCache {} }

    function test_destroying_a_cache_closes_its_listing() {
        Wire.reset()
        const c = comp.createObject(this)
        c.open("file:///tmp")
        const lid = c.lid
        verify(Path.Daemon._listings[lid] !== undefined)
        c.destroy()
        tryVerify(() => Wire.count("Close") === 1)
        compare(Wire.last("Close").lid, lid)
        compare(Path.Daemon._listings[lid], undefined)
    }
}
