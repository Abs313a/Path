pragma Singleton
import QtQuick
import "." as Path

QtObject {
    id: jobs
    property var list: []            // [Job]
    property var toast: null         // { job, text, undoable, until }
    property var prompt: null        // { job, kind, uri, existing, incoming, choices }
    signal changed()

    function submit(op, cb) { Path.Daemon.request("Submit", { op: op }, cb) }
    function cancel(id) { Path.Daemon.request("Cancel", { job: id }) }
    function undo() { Path.Daemon.request("Undo", {}, (ok, err) => { if (err) jobs.showToast({ text: Path.T.tr("jobs.nothingToUndo"), undoable: false }) }) }
    function redo() { Path.Daemon.request("Redo", {}) }
    function reply(choice, all) { if (prompt) { Path.Daemon.request("PromptReply", { job: prompt.job, choice: choice, applyToAll: !!all }); prompt = null } }
    function live(j) { return j.state === "running" || j.state === "queued" }
    function running() { return list.filter(live) }
    function showToast(t) { toast = t; toastTimer.restart() }
    function dismissToast() { toast = null; toastTimer.stop() }
    /// Forgetting is the daemon's to do — the list is fetched again on every reconnect — and it
    /// answers with `JobsCleared`, which is what takes them out of `list`.
    function clear() { Path.Daemon.request("ClearJobs", {}) }
    function dismiss(id) { Path.Daemon.request("DismissJob", { job: id }) }

    // ---------------------------------------------------------------- the activity view

    /// One step and gone: shown while they run and if they go wrong, not kept as history. (A
    /// list of "Deleted 1 item" is noise beside the transfers somebody is waiting on.)
    readonly property var quietWhenDone: ["delete", "chmod", "trash", "restore", "mkdir", "rename", "emptyTrash"]
    /// What the popup lists: not the machinery (an undo's inverse ops, a mirror's preflight), and
    /// not the quiet ones once they have finished well. In the order they were asked for — an
    /// entry keeps its place when it finishes.
    function shown() { return list.filter(j => !j.hidden && !(j.state === "done" && quietWhenDone.indexOf(j.op) >= 0)) }

    /// The highest failed job the popup has been opened on. A failure nobody saw is still news.
    property int seenFailure: 0
    function unseenFailures() { return shown().filter(j => j.state === "failed" && j.id > seenFailure) }
    function markSeen() { seenFailure = list.reduce((m, j) => j.state === "failed" ? Math.max(m, j.id) : m, seenFailure) }
    /// `failed` outranks `running`: something is always running somewhere.
    function orbState() { return unseenFailures().length ? "failed" : (running().filter(j => !j.hidden).length ? "running" : "idle") }
    function orbTip() {
        const f = unseenFailures().length, r = running().filter(j => !j.hidden).length
        return f ? Path.T.tr("orb.failed", { n: f }) + (r ? " · " + Path.T.tr("orb.running", { n: r }) : "") : (r ? Path.T.tr("orb.running", { n: r }) : Path.T.tr("orb.idle"))
    }

    function isTransfer(j) { return j.op === "copy" || j.op === "move" || j.op === "share" }
    function isMirror(j) { return j.op === "mirrorRun" }
    /// The bold line: the thing itself, not a sentence about it.
    function headline(j) {
        if (j.cancelling && live(j)) return Path.T.tr("jobs.cancelling")
        if (!j.name) return j.title
        return j.count > 1 ? Path.T.tr("jobs.andMore", { name: j.name, n: j.count - 1 }) : j.name
    }
    /// No bar at all / a bar with no length yet / a fraction.
    function barMode(j) { return !live(j) ? "none" : (j.state === "queued" || j.phase === "preparing" || j.cancelling || !(j.total || j.bytesTotal) ? "busy" : "value") }
    /// A single file is measured in bytes; many, in files — a bar of bytes stalls on the big one.
    function fraction(j) {
        if (j.total <= 1 && j.bytesTotal) return Math.min(1, j.bytes / j.bytesTotal)
        return j.total ? Math.min(1, j.done / j.total) : 0
    }
    function rateText(j) { return j.rate > 0 ? Path.T.tr("jobs.rate", { rate: Path.Format.transferSize(j.rate) }) : "" }
    /// The dim line under the bar while it runs.
    function statusLine(j) {
        if (j.state === "queued") return Path.T.tr("jobs.waiting")
        if (j.cancelling) return ""
        if (j.phase === "preparing") return isTransfer(j) ? Path.T.tr("jobs.preparingTransfer") : Path.T.tr("jobs.preparing")
        const rate = rateText(j)
        if (isMirror(j)) return Path.T.tr("jobs.mirrorProgress", { done: j.done, total: j.total, bytes: Path.Format.transferSize(j.bytes), bytesTotal: Path.Format.transferSize(j.bytesTotal) }) + (rate ? " · " + rate : "")
        if (isTransfer(j) || j.op === "extract" || j.op === "compress") {
            if (j.total <= 1 && j.bytesTotal) { const p = Path.T.tr("jobs.bytesProgress", { bytes: Path.Format.transferSize(j.bytes), bytesTotal: Path.Format.transferSize(j.bytesTotal) }); return rate ? Path.T.tr("jobs.withRate", { progress: p, rate: rate }) : p }
            return Path.T.tr("jobs.transferProgress", { done: j.done, total: j.total, pct: Math.floor(fraction(j) * 100) })
        }
        return Path.T.tr("jobs.processing", { done: j.done, total: j.total })
    }
    /// The file in hand, for the row that opens under a transfer. "" when there is nothing to add
    /// to the line above — one file is its own detail.
    function detailLine(j) {
        const c = j.current
        if (!c || !(j.total > 1 || isMirror(j))) return ""
        if (!c.size) return ""
        const rate = rateText(j)
        const p = Path.T.tr("jobs.bytesProgress", { bytes: Path.Format.transferSize(c.bytes), bytesTotal: Path.Format.transferSize(c.size) })
        return rate ? Path.T.tr("jobs.withRate", { progress: p, rate: rate }) : p
    }
    function hasDetail(j) { return live(j) && j.phase !== "preparing" && !j.cancelling && !!j.current && (j.total > 1 || isMirror(j)) }
    function items(n) { return Path.T.tr("count.items", { n: n }) }
    /// What replaces the bar once it is over.
    function completion(j) {
        if (j.state === "failed") return j.errorN ? Path.T.errorText({ n: j.errorN, params: j.errorParams, message: j.error }) : Path.Format.cleanError(j.error)
        if (j.state === "cancelled") return isMirror(j) ? Path.T.tr("jobs.mirrorCancelled") : Path.T.tr("jobs.cancelled")
        if (isMirror(j)) {
            const r = j.result || {}
            const a = { copies: r.copies || 0, deletes: r.deletes || 0, skipped: r.skipped || 0 }
            return r.skipped ? Path.T.tr("jobs.mirrorResultSkipped", a) : Path.T.tr("jobs.mirrorResult", a)
        }
        const n = items(Math.max(j.done, 1))
        switch (j.op) {
        case "copy": case "move":
            if (j.direction === "download") return Path.T.tr("jobs.downloaded", { what: n })
            if (j.direction === "upload") return Path.T.tr("jobs.uploaded", { what: n })
            return Path.T.tr(j.op === "move" ? "jobs.moved" : "jobs.copied", { what: n })
        case "delete": return Path.T.tr("jobs.deleted", { what: n })
        case "trash": return Path.T.tr("jobs.trashed", { what: n })
        case "chmod": return Path.T.tr("jobs.chmod", { what: n })
        case "extract": return Path.T.tr("jobs.extracted")
        case "compress": return Path.T.tr("jobs.compressed", { what: n })
        case "share": return Path.T.tr("jobs.shared", { what: n })
        default: return Path.T.tr("jobs.done")
        }
    }

    function _upsert(job) {
        const l = list.slice()
        const i = l.findIndex(j => j.id === job.id)
        if (i >= 0) l[i] = job; else l.push(job)
        // Every job still going, however old, and the fifty most recent that are not: the same
        // rule as the daemon's. ("The last fifty of everything" lost a long transfer.)
        const over = l.filter(j => !live(j))
        const cut = over.length > 50 ? over[over.length - 50].id : 0
        list = l.filter(j => live(j) || j.id >= cut)
        changed()
    }

    property Timer toastTimer: Timer { interval: Path.Settings.timers.toastMs; onTriggered: jobs.toast = null }
    property Connections c: Connections {
        target: Path.Daemon
        function onReadyChanged() { if (Path.Daemon.ready) { Path.Daemon.request("JobEvents", {}); Path.Daemon.request("Jobs", {}, ok => { if (ok) { jobs.list = ok.jobs; jobs.changed() } }) } }
        function onEvent(msg) {
            if (msg.event === "JobEvent") jobs._upsert(msg.job)
            else if (msg.event === "JobsCleared") { const gone = msg.jobs || []; jobs.list = jobs.list.filter(j => gone.indexOf(j.id) < 0); jobs.changed() }
            else if (msg.event === "Toast") jobs.showToast({ job: msg.job, text: msg.text, undoable: msg.undoable })
            else if (msg.event === "Prompt") jobs.prompt = msg
        }
    }
}
