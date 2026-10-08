import QtQuick
import Quickshell
import ".." as Path

// Configure → Preflight → Review → Running. Replaces the split panes while open.
Rectangle {
    id: ws
    property string localUri: ""
    property string remoteUri: ""
    property string home: ""
    signal closed()
    signal relist()
    /// "Save report…" needs a place to put it: the window opens path's own chooser and answers
    /// `reply(uri)` — or `reply("")` for cancel. The workspace cannot reach the chooser itself.
    signal saveWanted(string name, var reply)
    /// What the last save said: "Saved to ~/…" or the error, for the flow and the toast.
    property string saved: ""
    function saveReport() {
        const name = "path-mirror-" + Path.Format.display(remoteUri, home).replace(/^[a-z]+:\/\//, "").replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^-|-$/g, "") + ".txt"
        saveWanted(name, uri => {
            if (!uri) return
            Path.Daemon.request("MirrorReport", { job: scanJob, saveTo: uri }, (ok, err) => {
                if (ok) reportText = ok.text
                saved = err ? err.message : Path.T.tr("mirror.reportSaved", { path: Path.Format.display(uri, home) })
                Path.Jobs.showToast({ text: saved, undoable: false })
            })
        })
    }

    color: Path.Theme.bg
    property string screen: "configure"     // configure | preflight | review | running
    property bool upload: true
    property string detector: "auto"
    property bool deleteExtras: false
    property bool applyFilters: true
    /// The filter rules the check above applies, as the daemon last answered: `{ kind, value }`
    /// each, and whether they are still the built-in set. Read when the workspace opens.
    property var rules: []
    property bool rulesDefault: true
    onVisibleChanged: if (visible) loadRules()
    property bool windowOn: false
    property int windowValue: 7
    property string windowUnit: "days"
    property bool offsetAuto: true
    property int offsetHours: 0
    property int scanJob: 0
    /// A Cancel pressed before the scan's own `Submit` has answered. The reply and the events
    /// travel separately, so the id may not be here yet — and a cancel that found `scanJob` still
    /// 0 used to be dropped on the floor, leaving the compare running where nobody could see it.
    property bool scanStopped: false
    /// How many entries the daemon has walked so far, as the compare reports them. There is no
    /// total: nobody knows how big a tree is until it has been walked.
    property int scanSeen: 0
    property int runJob: 0
    /// The scan whose plan is open, so a second "done" for it does not open a second one.
    property int planJob: 0
    property var counts: ({})
    property string reviewTab: "all"
    property string status: ""
    /// Whether `status` is a refusal or a failure. It is drawn in the danger colour only then:
    /// "Comparing …" used to be as red as "no such folder", and stayed on the Configure screen
    /// looking like one after a compare that was over.
    property bool statusError: false
    function say(text) { status = text; statusError = false }
    function complain(text) { status = text || ""; statusError = status !== "" }
    /// How many actions a run does at once — the daemon's own default, said again here so the
    /// Running screen's label is the number that is really used. There is no control behind it.
    property int concurrency: 5
    property var runInfo: null
    /// What "Save report…" saves, once it has been asked for.
    property string reportText: ""

    property Path.WindowCache plan: Path.WindowCache { padAhead: 100; padBehind: 50 }

    function spec() {
        const master = upload ? localUri : remoteUri, replica = upload ? remoteUri : localUri
        const ms = { hours: 3600000, days: 86400000, weeks: 604800000 }[windowUnit]
        return { master: master, replica: replica, direction: upload ? "upload" : "download", deleteExtras: deleteExtras, blastRadius: 0.5, confirmedLargeDelete: false,
                 clockOffsetMs: offsetAuto ? 0 : offsetHours * 3600000, clockOffsetAuto: offsetAuto, detector: detector, modifiedWithinMs: windowOn ? windowValue * ms : null, applyFilters: applyFilters }
    }
    /// The one pairing that does damage without anybody asking for it: a folder mirrored into
    /// something inside it copies its own tree into itself, and with deletes on takes what it has
    /// just made for extras. Refused before the scan, in the words the Configure screen shows.
    function overlap() {
        const a = (upload ? localUri : remoteUri).replace(/\/+$/, ""), b = (upload ? remoteUri : localUri).replace(/\/+$/, "")
        if (!a || !b) return ""
        if (a === b) return "The source and the destination are the same folder."
        if (b.indexOf(a + "/") === 0) return Path.T.tr("mirror.destInsideSource")
        if (a.indexOf(b + "/") === 0) return Path.T.tr("mirror.sourceInsideDest")
        return ""
    }
    function preflight() {
        const bad = overlap(); if (bad) { complain(bad); screen = "configure"; return }
        scanStopped = false; scanSeen = 0
        screen = "preflight"; say(comparingText())
        Path.Jobs.submit({ op: "mirrorScan", spec: spec() }, (ok, err) => {
            if (err) { complain(err.message); screen = "configure"; return }
            // Cancelled while this reply was in flight: the job exists now, so stop it now.
            if (scanStopped) { Path.Jobs.cancel(ok.job); return }
            scanJob = ok.job; catchUp(ok.job)
        })
    }
    /// What the Preflight screen says: which folder is being compared, and how far the daemon has
    /// got. There is no bar, because there is no total to fill one with.
    function comparingText() {
        return Path.T.tr("mirror.comparing", { path: Path.Format.display(localUri, home) }) + (scanSeen > 0 ? Path.T.tr("mirror.soFar", { n: grouped(scanSeen) }) : "")
    }
    /// 12400 → "12,400". Long numbers are read in threes, and this one is watched while it moves.
    function grouped(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",") }
    /// A job that was over before its own Submit answered is not lost: the reply and the events
    /// travel separately, and a scan of two small folders can finish before its id is known here.
    function catchUp(id) { const j = Path.Jobs.list.find(x => x.id === id); if (j) jobEvent(j) }
    function openPlan() {
        plan.close()
        plan.lid = Path.Daemon.allocLid(); Path.Daemon.bind(plan.lid, plan)
        Path.Daemon.request("MirrorPlan", { job: scanJob, lid: plan.lid }, (ok, err) => {
            if (err) { complain(err.message); screen = "configure"; return }
            counts = ok.counts; plan._rows = ({}); plan.count = ok.n; plan.done = true
            plan._request(0, 100)
            screen = "review"; say("")
        })
    }
    function setTab(t) { reviewTab = t; Path.Daemon.request("MirrorFilter", { lid: plan.lid, reason: t }) }
    function toggleRow(i, checked) { Path.Daemon.request("MirrorCheck", { lid: plan.lid, first: i, count: 1, checked: checked }, ok => { if (ok) { counts = ok.counts; plan._request(Math.max(0, i - 1), 3) } }) }
    function mirror(confirmed) {
        if (screen !== "review") return
        const deletes = counts.deletes || 0, replica = counts.replicaEntries || 0
        if (deletes > 0 && replica > 0 && deletes / replica > 0.5 && !confirmed) { confirmBox.visible = true; return }
        const s = spec(); s.confirmedLargeDelete = !!confirmed
        Path.Jobs.submit({ op: "mirrorRun", plan: scanJob, spec: s, workers: concurrency }, (ok, err) => { if (err) { complain(err.message); return } runJob = ok.job; screen = "running"; setTab("all"); catchUp(ok.job) })
    }
    function cancelRun() { if (runJob) Path.Jobs.cancel(runJob) }
    /// Cancel on the Preflight screen: stop the compare and go back to the form, with nothing left
    /// behind. The job's id is forgotten too — a `done` that was already on its way for the
    /// compare somebody has just cancelled would otherwise open its plan and pull the workspace
    /// through to Review.
    function cancelScan() {
        scanStopped = true
        if (scanJob) Path.Jobs.cancel(scanJob)
        scanJob = 0; planJob = 0; scanSeen = 0
        screen = "configure"; say("Compare cancelled")
    }
    /// The button that stops what is going: the compare on Preflight, the run on Running.
    function stop() { if (screen === "preflight") cancelScan(); else cancelRun() }
    /// Escape. On Preflight it is Cancel — the way out of a compare that is taking too long, for
    /// a hand that is already on the keyboard. The other screens keep what Escape does elsewhere.
    function escapeKey() { if (screen === "preflight") { cancelScan(); return true } return false }
    /// Back: from Preflight it cancels the compare (no side effects), from Review it returns to
    /// the form, leaving no word about a compare that is over on the screen that starts one.
    function back() {
        if (screen === "preflight") cancelScan()
        else if (screen === "review") { screen = "configure"; say("") }
    }
    function answerLargeDelete(yes) { confirmBox.visible = false; if (yes) ws.mirror(true) }
    /// The offset row's second line: which way the hours go, in words. `master.mtime − offset −
    /// replica.mtime` is the comparison, so a positive offset says the source's times read later
    /// than the destination's for the same file — a destination whose clock is behind.
    readonly property string offsetText: {
        if (offsetAuto) return Path.T.tr("mirror.offsetAuto")
        if (offsetHours === 0) return Path.T.tr("mirror.clocksSame")
        const h = Math.abs(offsetHours) + (Math.abs(offsetHours) === 1 ? " hour" : " hours")
        return Path.T.tr(offsetHours > 0 ? "mirror.clockBehind" : "mirror.clockAhead", { h: h })
    }
    /// What the Review footer adds up. The two copy counts are added, not written one after the
    /// other: 3 new and 1 changed used to read as "31 copy", because the string in front of them
    /// turned the sum into a join.
    readonly property string planSummary: Path.T.tr("mirror.planSummary", { copies: (counts.new || 0) + (counts.changed || 0), deletes: counts.deletes || 0, bytes: Path.Format.bytes(counts.copyBytes || 0), filtered: counts.filtered || 0 })
    /// What it asks, in one place, so the dialog and a script read the same sentence.
    readonly property string largeDeleteText: Path.T.tr("mirror.largeDeleteText", { n: counts.deletes || 0, total: counts.replicaEntries || 0, pct: Math.round(100 * (counts.deletes || 0) / Math.max(1, counts.replicaEntries || 1)) })
    readonly property string doneText: {
        const j = runInfo
        if (!j || j.state === "running" || j.state === "queued") return "a mirror run is not undoable; re-run to converge"
        if (j.state === "failed") return Path.T.tr("mirror.failed", { error: j.errorN ? Path.T.errorText({ n: j.errorN, params: j.errorParams, message: j.error }) : Path.Format.cleanError(j.error) })
        if (j.state === "cancelled") return "Mirror cancelled"
        const r = j.result || ({})
        return Path.T.tr("mirror.complete", { copies: r.copies || 0, deletes: r.deletes || 0, bytes: Path.Format.bytes(j.bytes) }) + (r.skipped ? Path.T.tr("mirror.skippedSuffix", { n: r.skipped }) : "")
    }
    function fetchReport(then) {
        Path.Daemon.request("MirrorReport", { job: scanJob }, (ok, err) => {
            if (err) { complain(err.message); return }
            reportText = ok.text
            if (then) then(ok.text)
        })
    }
    /// Closing puts the workspace back at Configure, so the next run starts where the last one
    /// began rather than on the table of the one before. A run still going is followed to the
    /// end — that is what re-lists both panes when it finishes with the workspace shut.
    function leave() { if (!(runInfo && (runInfo.state === "running" || runInfo.state === "queued"))) forget(); ws.closed() }
    function forget() {
        // A compare still walking when the workspace is shut goes with it: it has no side effects
        // and nobody left to show it to. `scanStopped` stays set, so one whose id is still in
        // flight is stopped the moment it arrives.
        if (screen === "preflight") cancelScan()
        plan.close(); plan.count = 0
        screen = "configure"; scanJob = 0; runJob = 0; planJob = 0; runInfo = null; counts = ({}); say(""); reportText = ""
        scanSeen = 0
        confirmBox.visible = false
    }

    function jobEvent(j) {
        // Only the compare this workspace is waiting on: `cancelScan` forgets the id, so a `done`
        // still on its way for the one that was just cancelled lands on nobody.
        if (j.id === ws.scanJob) {
            if (j.state === "done") { if (ws.planJob !== j.id) { ws.planJob = j.id; ws.openPlan() } }
            else if (j.state === "failed") { ws.complain(j.error || "scan failed"); ws.screen = "configure" }
            else if (j.state === "cancelled") { ws.scanJob = 0; ws.scanSeen = 0; ws.screen = "configure"; ws.say("Compare cancelled") }
            else if (ws.screen === "preflight") { ws.scanSeen = j.done || 0; ws.say(ws.comparingText()) }
        } else if (j.id === ws.runJob) {
            ws.runInfo = j
            // Refetch the visible window so per-action states update.
            ws.plan._request(ws.plan.viewportFirst, Math.min(ws.plan.viewportCount + 20, 200))
            if (j.state === "done" || j.state === "failed" || j.state === "cancelled") ws.relist()
        }
    }

    Connections {
        target: Path.Daemon
        function onEvent(msg) { if (msg.event === "JobEvent") ws.jobEvent(msg.job) }
    }

    // ---- what the Configure screen's controls do. One function each, so a script drives the
    // very code a click does and the two cannot drift apart.
    function setDirection(up) { if (screen === "configure") upload = up }
    function cycleDetector() { const o = ["auto", "sizeMtime", "sizeOnly"]; detector = o[(o.indexOf(detector) + 1) % o.length] }
    function cycleWindowUnit() { const o = ["hours", "days", "weeks"]; windowUnit = o[(o.indexOf(windowUnit) + 1) % o.length] }
    function toggleDeletes() { deleteExtras = !deleteExtras }
    function toggleFilters() { applyFilters = !applyFilters }
    /// Edit rules…: the dialog beside the check, which reads and writes the rules itself.
    function editRules() { rulesDialog.open() }
    /// The rules as the daemon last answered, so the Configure screen and a script see the same
    /// list. Read when the workspace opens and again after every save.
    function loadRules() {
        Path.Daemon.request("MirrorFilters", {}, (ok, err) => {
            if (err) { ws.complain(err.message); return }
            ws.rules = ok.rules || []; ws.rulesDefault = ok.defaults === true
        })
    }
    /// A save changed the rules. They are read at SCAN, so a plan already on the Review screen was
    /// made with the old ones: back to Configure, the same way the Back button goes.
    function rulesSaved() {
        rules = rulesDialog.rows; rulesDefault = rulesDialog.defaults
        if (screen === "review") back()
    }
    /// The rules from a script: one `<kind> <value>` per line — newline-separated because IPC
    /// hands a function one string and eats the quotes out of it, the way `shell drop` takes a
    /// list of URIs. Nothing at all is "no rules", which is a real answer and not the defaults.
    /// It goes through the dialog's own save, so this is the Done button.
    function setRules(text) {
        rulesDialog.rows = (text || "").split("\n").map(l => l.trim()).filter(l => l !== "").map(l => {
            const sp = l.indexOf(" ")
            return sp < 0 ? { kind: l, value: "" } : { kind: l.slice(0, sp), value: l.slice(sp + 1).trim() }
        })
        rulesDialog.restoring = false; rulesDialog.error = ""; rulesDialog.bad = []
        rulesDialog.save()
    }
    /// Restore defaults, then Done.
    function restoreRules() { rulesDialog.restoreDefaults(); rulesDialog.save() }
    /// The rules dialog's Cancel.
    function cancelRules() { rulesDialog.cancel() }
    function toggleWindow() { windowOn = !windowOn }
    function toggleOffsetAuto() { offsetAuto = !offsetAuto }
    function setOffsetHours(v) {
        const n = parseInt(v, 10)
        if (!isFinite(n) || n < -24 || n > 24) return false
        offsetHours = n
        return true
    }
    /// One option by name, for scripts and tests: each presses its control until it says what was
    /// asked for.
    function setOption(name, value) {
        const on = value === "on" || value === "true" || value === "yes"
        if (name === "direction") setDirection(value !== "download")
        else if (name === "detector") { for (let i = 0; i < 3 && detector !== value; i++) cycleDetector() }
        else if (name === "deletes") { if (deleteExtras !== on) toggleDeletes() }
        else if (name === "filters") { if (applyFilters !== on) toggleFilters() }
        else if (name === "window") { if (windowOn !== on) toggleWindow() }
        else if (name === "windowValue") windowValue = parseInt(value) || 1
        else if (name === "windowUnit") { for (let i = 0; i < 3 && windowUnit !== value; i++) cycleWindowUnit() }
        // `offset auto` is the check let go; `offset <hours>` is it pressed and a number typed —
        // and an hour count the box would refuse changes nothing at all, not even the check.
        else if (name === "offset") {
            if (value === "auto") { if (!offsetAuto) toggleOffsetAuto() }
            else if (setOffsetHours(value) && offsetAuto) toggleOffsetAuto()
        }
    }

    /// The plan as the table is showing it — the rows the window holds, which for a plan of this
    /// size is all of them. For scripts and tests.
    function planRows() {
        const out = []
        for (let i = 0; i < plan.count; i++) {
            const r = plan.row(i)
            if (r) out.push({ i: i, rel: r.rel, action: r.action, reason: r.reason, bytes: r.bytes, checked: r.checked === true, state: r.state, error: r.error || "" })
        }
        return out
    }
    /// Everything on the four screens, for scripts and tests. (Not `state`: an Item has one.)
    function info() {
        const j = runInfo
        return { open: visible, screen: screen, direction: upload ? "upload" : "download", local: localUri, remote: remoteUri,
                 detector: detector, deleteExtras: deleteExtras, applyFilters: applyFilters, windowOn: windowOn, window: windowValue + " " + windowUnit,
                 offsetAuto: offsetAuto, offsetHours: offsetHours, offsetMs: spec().clockOffsetMs, offsetText: offsetText,
                 status: status, statusError: statusError, scanning: scanSeen, counts: counts, planCount: plan.count, planSummary: planSummary, tab: reviewTab, rows: planRows(),
                 confirm: confirmBox.visible, confirmText: largeDeleteText, summary: doneText, report: reportText, saved: saved,
                 rules: rules.map(r => ({ kind: r.kind, value: r.value })), rulesDefault: rulesDefault, rulesDialog: rulesDialog.info(),
                 run: j ? { state: j.state, done: j.done, total: j.total, bytes: j.bytes, bytesTotal: j.bytesTotal, error: j.error || "", result: j.result || ({}) } : null }
    }

    // ---- header: local ⇄ remote
    Column {
        anchors.fill: parent
        Item {
            id: head
            // A long path wraps rather than running under the arrows or off the edge, and the
            // header grows to hold it; the screen below gives up the room.
            width: parent.width; height: Math.max(104, header.height + 24)
            readonly property int sideWidth: Math.max(120, Math.min(340, Math.floor((width - 48 - 68) / 2)))
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Path.Theme.line }
            Row {
                id: header
                anchors.centerIn: parent; spacing: 24
                Column { width: head.sideWidth; spacing: 4
                    Icon { anchors.right: parent.right; name: "hdd"; size: 36; strokeWidth: 1; color: Path.Theme.fgDim }
                    Text { anchors.right: parent.right; text: Path.T.tr("mirror.local"); color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize; font.bold: true }
                    Text { objectName: "mirror-local-path"; width: parent.width; horizontalAlignment: Text.AlignRight; wrapMode: Text.WrapAnywhere; text: Path.Format.display(ws.localUri, ws.home); color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 11 }
                }
                Row { spacing: 4; anchors.verticalCenter: parent.verticalCenter
                    Repeater { model: [{ i: "arr-l", up: false }, { i: "arr-r", up: true }]
                        delegate: Rectangle { required property var modelData; width: 32; height: 32; radius: 2; color: ws.upload === modelData.up ? Path.Theme.surface : "transparent"
                            Icon { anchors.centerIn: parent; name: modelData.i; size: 20; color: ws.upload === modelData.up ? Path.Theme.accent : Path.Theme.gutter }
                            MouseArea { anchors.fill: parent; enabled: ws.screen === "configure"; onClicked: ws.setDirection(modelData.up) } } }
                }
                Column { width: head.sideWidth; spacing: 4
                    Icon { name: "server"; size: 36; strokeWidth: 1; color: Path.Theme.green }
                    Text { text: ws.remoteUri.split("://")[1] ? ws.remoteUri.split("://")[1].split("/")[0] : ""; color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize; font.bold: true }
                    Text { objectName: "mirror-remote-path"; width: parent.width; wrapMode: Text.WrapAnywhere; text: Path.Format.display(ws.remoteUri, ws.home).replace(/^[^/]*/, ""); color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 11 }
                }
            }
        }
        Loader {
            width: parent.width; height: parent.height - head.height - 56
            sourceComponent: ws.screen === "configure" ? configure : (ws.screen === "preflight" ? preflight : (ws.screen === "review" ? review : running))
        }
        // ---- footer
        Item {
            width: parent.width; height: 56
            Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: Path.Theme.line }
            Row {
                id: footLeft
                objectName: "mirror-footer-left"
                anchors.left: parent.left; anchors.leftMargin: 20; height: parent.height; spacing: 8
                Button { visible: ws.screen === "review"; anchors.verticalCenter: parent.verticalCenter; text: Path.T.tr("common.back"); onClicked: ws.back() }
                Text { objectName: "mirror-plan-summary"; anchors.verticalCenter: parent.verticalCenter; visible: ws.screen === "review"; text: "  " + ws.planSummary; elide: Text.ElideRight; width: Math.min(implicitWidth, Math.max(0, footRight.x - footLeft.x - 90)); color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 12 }
                Text { objectName: "mirror-done-summary"; anchors.verticalCenter: parent.verticalCenter; visible: ws.screen === "running"; text: ws.doneText; elide: Text.ElideRight; width: Math.min(implicitWidth, Math.max(0, footRight.x - footLeft.x - 16)); color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 12 }
            }
            Row {
                id: footRight
                objectName: "mirror-footer-right"
                anchors.right: parent.right; anchors.rightMargin: 20; height: parent.height; spacing: 8
                Button { visible: ws.screen !== "running" && ws.screen !== "preflight"; anchors.verticalCenter: parent.verticalCenter; text: Path.T.tr("common.cancel"); onClicked: ws.leave() }
                Button { visible: ws.screen === "review"; anchors.verticalCenter: parent.verticalCenter; text: Path.T.tr("mirror.saveReport"); onClicked: ws.saveReport() }
                Button { visible: ws.screen === "configure"; anchors.verticalCenter: parent.verticalCenter; text: Path.T.tr("mirror.preflight"); primary: true; onClicked: ws.preflight() }
                Button { visible: ws.screen === "review"; anchors.verticalCenter: parent.verticalCenter; text: Path.T.tr("mirror.go"); primary: true; onClicked: ws.mirror(false) }
                // The one button that stops what is going, in the place a button that does
                // something is looked for: the compare on Preflight, the run on Running. It used
                // to read "Back" on Preflight, which is not what somebody waiting on a compare of
                // a server is looking for.
                Button { objectName: "mirror-stop"; visible: ws.screen === "preflight" || (ws.screen === "running" && ws.runInfo && (ws.runInfo.state === "running" || ws.runInfo.state === "queued")); anchors.verticalCenter: parent.verticalCenter; text: Path.T.tr("common.cancel"); primary: true; onClicked: ws.stop() }
                Button { visible: ws.screen === "running" && ws.runInfo && ws.runInfo.state !== "running" && ws.runInfo.state !== "queued"; anchors.verticalCenter: parent.verticalCenter; text: Path.T.tr("common.close"); primary: true; onClicked: ws.leave() }
            }
        }
    }

    component Check: Row {
        property bool on: false
        property string label: ""
        property bool enabled: true
        signal toggled()
        spacing: 10; height: 30
        Rectangle { width: 16; height: 16; radius: 2; anchors.verticalCenter: parent.verticalCenter; color: on ? Path.Theme.accent : Path.Theme.bgDark; border.width: 1; border.color: on ? Path.Theme.accent : Path.Theme.gutter
            Icon { visible: parent.parent.on; anchors.centerIn: parent; name: "check"; size: 10; strokeWidth: 2.5; color: Path.Theme.bg }
            MouseArea { anchors.fill: parent; enabled: parent.parent.enabled; onClicked: parent.parent.toggled() } }
        Text { anchors.verticalCenter: parent.verticalCenter; text: label; color: enabled ? Path.Theme.fg : Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize }
    }

    Component {
        id: configure
        Item {
            id: configScreen
            readonly property int optionsHeight: 30 + 30 + 30 + 30 + (18 + 2 + 30 + 2 + 16)
            readonly property bool tight: height < optionsHeight + 4 * 14 + 28 + 150
            readonly property int gap: tight ? 8 : 14
            readonly property int topGap: tight ? 12 : 28
            readonly property int planRoom: Math.max(56, height - topGap - optionsHeight - 5 * gap - (ws.status !== "" ? 26 : 0) - 8)
            Column {
                anchors.horizontalCenter: parent.horizontalCenter; y: configScreen.topGap; width: Math.min(620, parent.width - 48); spacing: configScreen.gap
                Row { id: detectRow; spacing: 12; height: 30; width: parent.width
                    Text { width: 150; anchors.verticalCenter: parent.verticalCenter; text: Path.T.tr("mirror.detectBy"); color: Path.Theme.fgDim; font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize }
                    Rectangle { width: Math.max(160, detectRow.width - 162); height: 30; radius: 2; color: Path.Theme.bgDark; border.width: 1; border.color: Path.Theme.gutter
                        Text { x: 10; anchors.verticalCenter: parent.verticalCenter; text: Path.T.tr("mirror.detector." + ws.detector); color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize }
                        Icon { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; name: "chev-d"; size: 12; color: Path.Theme.muted }
                        MouseArea { anchors.fill: parent; onClicked: ws.cycleDetector() } }
                }
                Check { on: ws.deleteExtras; label: Path.T.tr("mirror.deleteExtras"); onToggled: ws.toggleDeletes() }
                // The rules can be edited whether or not the check is on: what they say is worth
                // seeing before deciding to apply them.
                Row { spacing: 12; height: 30
                    Check { on: ws.applyFilters; label: Path.T.tr("mirror.applyFilters"); onToggled: ws.toggleFilters() }
                    Button { objectName: "mirror-edit-rules"; anchors.verticalCenter: parent.verticalCenter; text: Path.T.tr("mirror.editRules"); onClicked: ws.editRules() }
                }
                Row { spacing: 8
                    Check { on: ws.windowOn; label: Path.T.tr("mirror.window"); onToggled: ws.toggleWindow() }
                    Rectangle { width: 70; height: 30; radius: 2; color: Path.Theme.bgDark; border.width: 1; border.color: Path.Theme.gutter; opacity: ws.windowOn ? 1 : 0.5
                        TextInput { anchors.fill: parent; anchors.margins: 8; clip: true; verticalAlignment: TextInput.AlignVCenter; text: ws.windowValue; enabled: ws.windowOn; inputMethodHints: Qt.ImhDigitsOnly; color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize; onTextChanged: ws.windowValue = parseInt(text) || 1 } }
                    Rectangle { width: 100; height: 30; radius: 2; color: Path.Theme.bgDark; border.width: 1; border.color: Path.Theme.gutter; opacity: ws.windowOn ? 1 : 0.5
                        Text { x: 10; anchors.verticalCenter: parent.verticalCenter; text: Path.T.tr("mirror.unit." + ws.windowUnit); color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize }
                        MouseArea { anchors.fill: parent; enabled: ws.windowOn; onClicked: ws.cycleWindowUnit() } }
                }
                Column { spacing: 2; width: parent.width
                    Text { text: Path.T.tr("mirror.offset"); color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize }
                    Row { spacing: 8; height: 30
                        Check { on: !ws.offsetAuto; label: Path.T.tr("mirror.setManually"); onToggled: ws.toggleOffsetAuto() }
                        Rectangle { objectName: "mirror-offset-box"; width: 70; height: 30; radius: 2; color: Path.Theme.bgDark; border.width: 1; border.color: Path.Theme.gutter; opacity: ws.offsetAuto ? 0.5 : 1
                            TextInput { objectName: "mirror-offset-hours"; anchors.fill: parent; anchors.margins: 8; clip: true; verticalAlignment: TextInput.AlignVCenter; text: ws.offsetHours; enabled: !ws.offsetAuto; inputMethodHints: Qt.ImhFormattedNumbersOnly; color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize; onTextChanged: ws.setOffsetHours(text) } }
                        Text { anchors.verticalCenter: parent.verticalCenter; text: Path.T.tr("mirror.hours"); color: ws.offsetAuto ? Path.Theme.muted : Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize } }
                    Text { objectName: "mirror-offset-note"; text: ws.offsetText; color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 11 } }
                Rectangle { objectName: "mirror-plan-box"; width: parent.width; height: Math.min(planText.contentHeight + 40, configScreen.planRoom); radius: 2; color: Path.Theme.bgDark; border.width: 1; border.color: Path.Theme.line; clip: true
                    Column { anchors.fill: parent; anchors.margins: 14; spacing: 6
                        Text { text: Path.T.tr("mirror.plan"); color: Path.Theme.accent; font.family: Path.Theme.mono; font.pixelSize: 11; font.bold: true; font.letterSpacing: 1 }
                        // StyledText rather than RichText: only the former lets the type shrink
                        // to fit (`fontSizeMode`), and it has `<font color>` for the emphasis.
                        Text { id: planText; objectName: "mirror-plan-text"; width: parent.width; height: configScreen.planRoom - 40 + 6 - 11; wrapMode: Text.WordWrap; lineHeight: 1.4; textFormat: Text.StyledText; color: Path.Theme.fgDim; font.family: Path.Theme.mono
                            font.pixelSize: Path.Theme.fontSize; fontSizeMode: Text.VerticalFit; minimumPixelSize: 12
                            text: Path.T.tr("mirror.explain", { src: "<font color='" + Path.Theme.fg + "'><b>" + Path.T.tr(ws.upload ? "mirror.local" : "mirror.remote") + "</b></font>", dest: "<font color='" + Path.Theme.fg + "'><b>" + Path.T.tr(ws.upload ? "mirror.remote" : "mirror.local") + "</b></font>" }) + (ws.deleteExtras ? "<font color='" + Path.Theme.danger + "'><b>" + Path.T.tr("mirror.explainDelete") + "</b></font>." : Path.T.tr("mirror.explainKeep")) + (ws.applyFilters ? Path.T.tr("mirror.explainFilters") : "") } }
                }
                Text { objectName: "mirror-status"; visible: ws.status !== ""; text: ws.status; color: ws.statusError ? Path.Theme.danger : Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 12 }
            }
        }
    }

    Component {
        id: preflight
        Item {
            Column { anchors.centerIn: parent; spacing: 16; width: 400
                Rectangle { width: parent.width; height: 6; radius: 3; color: Path.Theme.surface; clip: true
                    Rectangle { id: bar; width: 120; height: 6; radius: 3; color: Path.Theme.accent
                        SequentialAnimation on x { loops: Animation.Infinite; NumberAnimation { from: -120; to: 400; duration: 1200 } } } }
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: ws.status; color: Path.Theme.fgDim; font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize }
            }
        }
    }

    component PlanRow: Item {
        required property int index
        property var r: ws.plan.row(index)
        property bool running: ws.screen === "running"
        width: parent ? parent.width : 900; height: 28
        Connections { target: ws.plan; function onRowsUpdated(first, n) { if (index >= first && index < first + n) r = ws.plan.row(index) } function onReset() { r = ws.plan.row(index) } }
        Row {
            anchors.fill: parent; anchors.leftMargin: 16; anchors.rightMargin: 16; spacing: 12
            Rectangle { visible: !running; width: 16; height: 16; radius: 2; anchors.verticalCenter: parent.verticalCenter; opacity: r && r.action === "skip" ? 0 : 1
                color: r && r.checked ? Path.Theme.accent : Path.Theme.bgDark; border.width: 1; border.color: r && r.checked ? Path.Theme.accent : Path.Theme.gutter
                Icon { visible: r && r.checked; anchors.centerIn: parent; name: "check"; size: 10; strokeWidth: 2.5; color: Path.Theme.bg }
                MouseArea { anchors.fill: parent; enabled: r && r.action !== "skip"; onClicked: ws.toggleRow(index, !r.checked) } }
            Row { width: Math.min(150, Math.floor(parent.width * 0.3)); spacing: 6; anchors.verticalCenter: parent.verticalCenter; clip: true
                Icon { anchors.verticalCenter: parent.verticalCenter; size: 12; name: r ? (r.action === "delete" || r.action === "rmdir" ? "x" : (r.action === "skip" ? "equals" : (ws.upload ? "arr-u" : "arr-dn"))) : "equals"; color: r ? (r.action === "delete" || r.action === "rmdir" ? Path.Theme.danger : (r.reason === "changed" ? Path.Theme.yellow : (r.action === "skip" ? Path.Theme.gutter : Path.Theme.accent))) : Path.Theme.gutter }
                Text { text: r ? (r.action === "copy" ? Path.T.tr("mirror.copyReason", { reason: r.reason }) : (r.action === "skip" ? Path.T.tr("mirror.unchanged") : r.action)) : ""; color: r && (r.action === "delete" || r.action === "rmdir") ? Path.Theme.danger : (r && r.action === "skip" ? Path.Theme.muted : Path.Theme.fgDim); font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize } }
            Text { width: Math.max(60, parent.width - 16 - 12 - Math.min(150, Math.floor(parent.width * 0.3)) - 12 - 90 - (running ? 232 : 0)); anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideMiddle; text: r ? r.rel : ""; color: r && r.action === "skip" ? Path.Theme.muted : Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize }
            Text { width: 90; anchors.verticalCenter: parent.verticalCenter; horizontalAlignment: Text.AlignRight; text: r && r.bytes ? Path.Format.bytes(r.bytes) : "—"; color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize }
            Row { visible: running; width: 220; spacing: 6; anchors.verticalCenter: parent.verticalCenter
                Icon { visible: r && r.state === "done"; name: "check"; size: 14; color: Path.Theme.green; anchors.verticalCenter: parent.verticalCenter }
                Icon { visible: r && r.state === "skipped"; name: "warn"; size: 14; color: Path.Theme.yellow; anchors.verticalCenter: parent.verticalCenter }
                Rectangle { visible: r && r.state === "running"; width: 120; height: 4; radius: 2; color: Path.Theme.surface; anchors.verticalCenter: parent.verticalCenter
                    Rectangle { height: 4; radius: 2; color: Path.Theme.accent; width: parent.width * 0.5; SequentialAnimation on width { loops: Animation.Infinite; NumberAnimation { from: 10; to: 120; duration: 900 } } } }
                Text { anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight; width: 90; text: r ? (r.state === "skipped" ? Path.T.tr("mirror.skippedError", { error: r.error || "" }) : (r.state === "pending" ? Path.T.tr("mirror.queued") : r.state)) : ""; color: r && r.state === "done" ? Path.Theme.green : (r && r.state === "skipped" ? Path.Theme.yellow : (r && r.state === "pending" ? Path.Theme.gutter : Path.Theme.fgDim)); font.family: Path.Theme.mono; font.pixelSize: 12 } }
        }
    }

    Component {
        id: review
        Column {
            Row { height: 36; spacing: 20; x: 20
                Repeater { model: ["all", "new", "changed", "equal", "delete"]
                    delegate: Item { required property string modelData; width: tl.implicitWidth + 24; height: 36
                        Row { id: tl; anchors.centerIn: parent; spacing: 6
                            Text { text: Path.T.tr("mirror.tab." + modelData); color: ws.reviewTab === modelData ? Path.Theme.fg : Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize }
                            Text { text: modelData === "all" ? ws.plan.count : (modelData === "delete" ? (ws.counts.deletes || 0) : (ws.counts[modelData] || 0)); color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter } }
                        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 2; color: ws.reviewTab === modelData ? Path.Theme.accent : "transparent" }
                        MouseArea { anchors.fill: parent; onClicked: ws.setTab(modelData) } } }
            }
            Rectangle { width: parent.width; height: 1; color: Path.Theme.line }
            ListView { id: reviewList; width: parent.width; height: parent.height - 37; clip: true; reuseItems: true; model: ws.plan.count
                NaturalScroll { }
                onContentYChanged: ws.plan.setViewport(Math.max(0, Math.floor(contentY / 28)), Math.ceil(height / 28) + 1)
                // By id: a Connections has no `parent`, so the name found the Loader this screen sits
                // in — "forceLayout is not a function", fourteen times a run, and no relayout.
                Connections { target: ws.plan; function onReset() { reviewList.forceLayout() } }
                delegate: PlanRow {} }
        }
    }

    Component {
        id: running
        Column {
            Column { width: parent.width; spacing: 10; padding: 0
                Item { width: parent.width; height: 52
                    Row { anchors.fill: parent; anchors.leftMargin: 20; anchors.rightMargin: 20; spacing: 12
                        Text { anchors.verticalCenter: parent.verticalCenter; text: Path.T.tr(ws.upload ? "mirror.mirroringUp" : "mirror.mirroringDown", { host: (ws.remoteUri.split("://")[1] || "").split("/")[0] }); color: Path.Theme.fg; font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize; font.bold: true }
                        Item { width: parent.width - 620; height: 1 }
                        Text { anchors.verticalCenter: parent.verticalCenter; text: ws.runInfo ? Path.T.tr("mirror.runProgress", { done: ws.runInfo.done, total: ws.runInfo.total, bytes: Path.Format.bytes(ws.runInfo.bytes), bytesTotal: Path.Format.bytes(ws.runInfo.bytesTotal) }) : ""; color: Path.Theme.muted; font.family: Path.Theme.mono; font.pixelSize: 12 }
                        Rectangle { anchors.verticalCenter: parent.verticalCenter; height: 22; width: 100; radius: 2; border.width: 1; border.color: Path.Theme.gutter; color: "transparent"
                            Text { anchors.centerIn: parent; text: Path.T.tr("mirror.atATime", { n: ws.concurrency }); color: Path.Theme.fgDim; font.family: Path.Theme.mono; font.pixelSize: 11 } }
                    }
                }
                Rectangle { width: parent.width - 40; x: 20; height: 6; radius: 3; color: Path.Theme.surface
                    Rectangle { height: 6; radius: 3; color: Path.Theme.accent; width: ws.runInfo && ws.runInfo.total ? parent.width * ws.runInfo.done / ws.runInfo.total : 0 } }
                Rectangle { width: parent.width; height: 1; color: Path.Theme.line }
            }
            ListView { id: planList; width: parent.width; height: parent.height - 80; clip: true; reuseItems: true; model: ws.plan.count
                NaturalScroll { }
                onContentYChanged: ws.plan.setViewport(Math.max(0, Math.floor(contentY / 28)), Math.ceil(height / 28) + 1)
                // By id: a Connections has no `parent`, so the name found the Loader this screen sits
                // in — "forceLayout is not a function", fourteen times a run, and no relayout.
                Connections { target: ws.plan; function onReset() { planList.forceLayout() } }
                delegate: PlanRow {} }
        }
    }

    // Blast-radius confirmation
    Rectangle {
        id: confirmBox
        visible: false; anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.5); z: 20
        MouseArea { anchors.fill: parent }
        Rectangle { anchors.centerIn: parent; width: 460; height: 160; color: Path.Theme.bg; border.width: 2; border.color: Path.Theme.danger
            Column { anchors.fill: parent; anchors.margins: 20; spacing: 14
                Text { text: Path.T.tr("mirror.largeDelete"); color: Path.Theme.danger; font.family: Path.Theme.mono; font.pixelSize: 15; font.bold: true }
                Text { width: parent.width; wrapMode: Text.WordWrap; text: ws.largeDeleteText; color: Path.Theme.fgDim; font.family: Path.Theme.mono; font.pixelSize: Path.Theme.fontSize }
                Row { spacing: 8; anchors.right: parent.right
                    Button { text: Path.T.tr("common.cancel"); onClicked: ws.answerLargeDelete(false) }
                    Button { text: Path.T.tr("mirror.deleteAndMirror"); primary: true; onClicked: ws.answerLargeDelete(true) } }
            }
        }
    }

    // Edit rules…
    MirrorRulesDialog { id: rulesDialog; objectName: "mirror-rules-dialog"; onSaved: ws.rulesSaved() }
}
