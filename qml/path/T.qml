pragma Singleton
import QtQuick
import "i18n/en.js" as En
import "i18n/es.js" as Es
import "i18n/ja.js" as Ja

QtObject {
    id: t
    readonly property var catalogs: ({ en: En.strings, es: Es.strings, ja: Ja.strings })
    property string language: pick(Qt.locale().uiLanguages)

    function pick(uiLanguages) {
        for (const l of uiLanguages || []) {
            const lang = String(l).split(/[-_]/)[0].toLowerCase()
            if (catalogs[lang]) return lang
        }
        return "en"
    }

    /// The sentence for `key`, with `{name}` placeholders filled from `args`; a plural key
    /// picks its form by `args.n`. A key the language lacks shows English and is logged once;
    /// a key nobody has shows the key itself, logged once, so it is seen and never silent.
    function tr(key, args) {
        const own = catalogs[language] || En.strings
        let s = own[key]
        if (s === undefined) {
            s = En.strings[key]
            if (s === undefined) { _missing("no such key: " + key); return key }
            if (language !== "en") _missing(language + " has no " + key)
        }
        if (typeof s === "object") {
            const n = args && args.n !== undefined ? Number(args.n) : NaN
            s = (n === 1 && s.one !== undefined) ? s.one : (s.other !== undefined ? s.other : s.one)
        }
        return fill(s, args)
    }
    function fill(s, args) {
        if (!args) return String(s)
        return String(s).replace(/\{(\w+)\}/g, (m, k) => {
            const v = args[k]
            if (v === undefined) return m
            return typeof v === "number" ? Number(v).toLocaleString(Qt.locale(), "f", 0) : String(v)
        })
    }
    function sent(o) {
        if (!o) return ""
        if (o.labels && o.labels[language] !== undefined) return o.labels[language]
        return o.label !== undefined ? o.label : (o.value !== undefined ? o.value : "")
    }
    /// Whether the language in use, or English, has words for `key`.
    function has(key) { return (catalogs[language] || En.strings)[key] !== undefined || En.strings[key] !== undefined }
    function errorText(e) {
        if (!e) return ""
        if (e.n === undefined || e.n === null) return e.message || ""
        if (!has("error." + e.n)) return e.message || String(e.n)
        const base = "error." + e.n
        const more = e.params && Number(e.params.more) > 0 && has(base + ".more") ? base + ".more" : base
        return tr(more, e.params || {})
    }
    property var _said: ({})
    function _missing(what) { if (_said[what]) return; _said[what] = true; console.warn("T:", what) }
}
