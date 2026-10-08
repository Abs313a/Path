import QtQuick

// Follow the usual wheel direction: wheel down reveals later content. The input deltas
// already reflect the desktop's device configuration. Drop one inside any Flickable.
WheelHandler {
    property var view: {
        let p = parent
        while (p && p.contentY === undefined) p = p.parent
        return p
    }
    target: null
    orientation: Qt.Vertical
    acceptedModifiers: Qt.NoModifier
    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
    /// What the wheel does when this view has nothing to scroll — everything in it fits. Columns
    /// view hands it to the strip, so the wheel over a short column walks the columns.
    property var whenItFits: null
    function scroll(event) {
        const dy = -(event.pixelDelta.y !== 0 ? event.pixelDelta.y : event.angleDelta.y / 2)
        if (dy === 0 || !view) { event.accepted = false; return }
        if (whenItFits && view.contentHeight <= view.height) { whenItFits(dy); event.accepted = true; return }
        view.contentY = Math.max(0, Math.min(view.contentY + dy, Math.max(0, view.contentHeight - view.height)))
        event.accepted = true
    }
    onWheel: event => scroll(event)
}
