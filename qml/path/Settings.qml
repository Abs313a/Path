pragma Singleton
import QtQuick
import "." as Path

// settings.toml as served by the daemon, with the same defaults it applies.
QtObject {
    id: settings
    property var view: ({ "default": "list", icons: "path", sort: "name", order: "asc", inspector: false, sidebar: true, sidebarStyle: "rail", railHover: true, shortcutChips: true, rememberPerFolder: true, slideshowDelay: 4, slideshowLoop: true, columns: ["mtime", "size", "kind"], listColumnWidths: ({}) })
    property var viewPrefs: ({})
    function viewPref(uri) { return view.rememberPerFolder ? viewPrefs[uri] || null : null }
    function setViewPref(uri, v, sort, order, hidden) {
        if (!view.rememberPerFolder || !uri) return
        const was = viewPrefs[uri]
        if (was && was.view === v && was.sort === sort && was.order === order && was.hidden === hidden) return      // nothing new to write
        const p = Object.assign({}, viewPrefs); p[uri] = { view: v, sort: sort, order: order, hidden: hidden }; viewPrefs = p
        _written[uri] = true
        Path.Daemon.request("SetViewPref", { uri: uri, view: v, sort: sort, order: order, hidden: hidden })
    }
    property var _written: ({})
    function onViewPrefsChanged(uri) {
        if (uri && _written[uri]) { delete _written[uri]; return }
        loadViewPrefs()
    }
    signal viewPrefsLoaded()
    function loadViewPrefs() { Path.Daemon.request("ViewPrefs", {}, ok => { if (ok) { viewPrefs = ok.folders; viewPrefsLoaded() } }) }
    property var timers: ({ toastMs: 8000, searchDebounceMs: 150, mirrorPollMs: 400 })
    property var editor: ({ terminal: "auto", placement: "right" })
    property var git: ({ enabled: true, showIgnored: "dim", folders: "aggregate" })
    property var project: ({ width: 320, arrange: true, agent: true })
    property var jarvis: ({ provider: "omarchy", cliCommand: "" })
    property var index: ({ roots: [], excludes: [] })
    property var integration: ({ asked: false })
    /// Rebound shortcuts: action id -> chord. Empty means everything is on its default.
    property var keys: ({})
    property var mirror: ({ last: {} })
    property bool loaded: false

    function load() {
        Path.Daemon.request("Settings", {}, (ok, err) => {
            if (!ok) return
            for (const k of ["view", "timers", "editor", "git", "project", "jarvis", "index", "integration", "mirror", "keys"]) if (ok[k]) settings[k] = Object.assign({}, settings[k], ok[k])
            loaded = true
        })
        loadViewPrefs()
    }
    /// Take one entry out of a map setting (`[view.listColumnWidths]`, `[view.columnsWidths]`).
    /// `set` cannot: the daemon merges maps, so a map sent without the entry leaves it in the
    /// file. `null` is how it is told to forget.
    function forget(section, key, entry) {
        const map = Object.assign({}, (settings[section] || ({}))[key] || ({}))
        delete map[entry]
        const local = {}; local[key] = map
        settings[section] = Object.assign({}, settings[section], local)
        const gone = {}; gone[entry] = null
        const patch = {}; patch[section] = {}; patch[section][key] = gone
        Path.Daemon.request("SetSettings", { patch: patch })
    }
    function set(section, key, value) {
        const patch = {}; patch[section] = {}; patch[section][key] = value
        settings[section] = Object.assign({}, settings[section], patch[section])
        Path.Daemon.request("SetSettings", { patch: patch })
    }
    property Connections c: Connections { target: Path.Daemon; function onReadyChanged() { if (Path.Daemon.ready) settings.load() } function onEvent(msg) { if (msg.event === "ViewPrefsChanged") settings.onViewPrefsChanged(msg.uri || "") } }
}
