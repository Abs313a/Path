//! DWM-Titus integration: making Path the default file manager for the current user,
//! and undoing it. The package installs system files under /usr; everything here is per-user
//! and reversible:
//!
//! 1. MIME: `inode/directory` (and the sftp/ftps scheme handlers) in `~/.config/mimeapps.list`.
//! 2. D-Bus: a reversible user-level `org.freedesktop.FileManager1` ("Show in folder")
//!    selection. Reuse Path's registered portal backend; write a fallback only when needed.
//! 3. Portal: `org.freedesktop.impl.portal.FileChooser=path;gtk` in
//!    `~/.config/xdg-desktop-portal/portals.conf`, then a portal restart.
//!
//! DWM-Titus already launches `xdg-open .` with Super+E. Never edit its managed TOMLs.
//!
//! Every step is idempotent and reports what it did; `PATHFM_INTEGRATE_NO_EXEC=1` skips the
//! external commands (tests), `PATHFM_INTEGRATE_HOME` points at a scratch home.

use crate::json::Value;
use std::path::{Path, PathBuf};
use std::process::Command;

pub const DESKTOP_ID: &str = "pathfm.desktop";
pub const PORTAL_NAME: &str = "org.freedesktop.impl.portal.desktop.pathfm";
pub const PARTS: [&str; 3] = ["mime", "dbus", "portal"];

fn home() -> PathBuf {
    std::env::var("PATHFM_INTEGRATE_HOME").map(PathBuf::from).unwrap_or_else(|_| crate::config::home())
}

fn config_home() -> PathBuf {
    if std::env::var("PATHFM_INTEGRATE_HOME").is_ok() {
        return home().join(".config");
    }
    std::env::var("XDG_CONFIG_HOME").map(PathBuf::from).unwrap_or_else(|_| home().join(".config"))
}

fn data_home() -> PathBuf {
    if std::env::var("PATHFM_INTEGRATE_HOME").is_ok() {
        return home().join(".local/share");
    }
    std::env::var("XDG_DATA_HOME").map(PathBuf::from).unwrap_or_else(|_| home().join(".local/share"))
}

fn no_exec() -> bool {
    std::env::var("PATHFM_INTEGRATE_NO_EXEC").is_ok()
}

fn mimeapps() -> PathBuf {
    config_home().join("mimeapps.list")
}
fn services_dir() -> PathBuf {
    data_home().join("dbus-1/services")
}
fn portals_conf() -> PathBuf {
    config_home().join("xdg-desktop-portal/portals.conf")
}

fn read_optional(path: &Path) -> Result<Option<String>, String> {
    match std::fs::read_to_string(path) {
        Ok(text) => Ok(Some(text)),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None),
        Err(e) => Err(format!("{}: {e}", path.display())),
    }
}

fn pathd_path() -> String {
    std::env::current_exe().ok().map(|p| p.to_string_lossy().into_owned()).filter(|p| p.ends_with("pathd")).unwrap_or_else(|| "/usr/bin/pathd".into())
}

/// Write through a temp file and rename, so a crash never leaves a half-written config.
fn write_atomic(path: &Path, text: &str) -> std::io::Result<()> {
    if let Some(p) = path.parent() {
        std::fs::create_dir_all(p)?;
    }
    let tmp = path.with_extension(format!("path-tmp-{}", std::process::id()));
    std::fs::write(&tmp, text)?;
    std::fs::rename(&tmp, path)
}

fn run(cmd: &str, args: &[&str]) -> Result<String, String> {
    if no_exec() {
        return Ok(String::new());
    }
    let o = Command::new(cmd).args(args).output().map_err(|e| format!("{cmd}: {e}"))?;
    let out = String::from_utf8_lossy(&o.stdout).trim().to_string();
    if o.status.success() {
        Ok(out)
    } else {
        let err = String::from_utf8_lossy(&o.stderr).trim().to_string();
        Err(if err.is_empty() { format!("{cmd} exited with {}", o.status) } else { err })
    }
}

// ---------------------------------------------------------------- backup of what we replaced

/// `~/.config/path/integration.toml`: the values each part replaced, written on the first
/// apply only (a second apply never overwrites the true original) and restored on remove.
fn backup_all() -> Result<Value, String> {
    let path = crate::config::config_dir().join("integration.toml");
    match std::fs::read_to_string(&path) {
        Ok(text) => crate::toml::parse(&text).map_err(|e| format!("integration backup: {e}")),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(Value::obj().done()),
        Err(e) => Err(format!("integration backup: {e}")),
    }
}

fn backup_get(part: &str) -> Result<Option<Value>, String> {
    Ok(backup_all()?.get(part).cloned())
}

fn backup_set(part: &str, v: Value) -> Result<(), String> {
    let mut all = match backup_all()? {
        Value::Obj(m) => m,
        _ => return Err("invalid integration backup".into()),
    };
    if all.contains_key(part) {
        return Ok(());
    }
    all.insert(part.to_string(), v);
    crate::config::write_named("integration.toml", &Value::Obj(all)).map_err(|e| format!("integration backup: {e}"))
}

fn backup_clear(part: &str) -> Result<(), String> {
    if let Value::Obj(mut m) = backup_all()? {
        m.remove(part);
        crate::config::write_named("integration.toml", &Value::Obj(m)).map_err(|e| format!("integration backup: {e}"))?;
    }
    Ok(())
}

// ---------------------------------------------------------------- 1. mime

const MIME_TYPES: [&str; 3] = ["inode/directory", "x-scheme-handler/sftp", "x-scheme-handler/ftps"];

/// Edits an ini-style file's section: sets or removes `key=value` lines under `[section]`.
fn ini_set(text: &str, section: &str, key: &str, value: Option<&str>) -> String {
    let mut out: Vec<String> = Vec::new();
    let mut in_section = false;
    let mut seen_section = false;
    let mut done = false;
    for line in text.lines() {
        let t = line.trim();
        if t.starts_with('[') {
            if in_section && !done {
                if let Some(v) = value {
                    out.push(format!("{key}={v}"));
                }
                done = true;
            }
            in_section = t == format!("[{section}]");
            seen_section |= in_section;
            out.push(line.to_string());
            continue;
        }
        if in_section {
            if let Some((k, _)) = t.split_once('=') {
                if k.trim() == key {
                    if !done {
                        if let Some(v) = value {
                            out.push(format!("{key}={v}"));
                        }
                        done = true;
                    }
                    continue;
                }
            }
        }
        out.push(line.to_string());
    }
    if !done {
        if let Some(v) = value {
            if !seen_section {
                if !out.is_empty() && !out.last().map(|l| l.is_empty()).unwrap_or(true) {
                    out.push(String::new());
                }
                out.push(format!("[{section}]"));
            }
            out.push(format!("{key}={v}"));
        }
    }
    let mut s = out.join("\n");
    s.push('\n');
    s
}

fn ini_get(text: &str, section: &str, key: &str) -> Option<String> {
    let mut in_section = false;
    for line in text.lines() {
        let t = line.trim();
        if t.starts_with('[') {
            in_section = t == format!("[{section}]");
            continue;
        }
        if in_section {
            if let Some((k, v)) = t.split_once('=') {
                if k.trim() == key {
                    return Some(v.trim().to_string());
                }
            }
        }
    }
    None
}

fn mime_status() -> bool {
    let text = std::fs::read_to_string(mimeapps()).unwrap_or_default();
    MIME_TYPES.iter().all(|m| ini_get(&text, "Default Applications", m).map(|v| v.split(';').next() == Some(DESKTOP_ID)).unwrap_or(false))
}

fn mime_apply() -> Result<String, String> {
    // Remember what each type pointed at ("" = no entry) so Remove can put it back.
    let before = read_optional(&mimeapps())?.unwrap_or_default();
    let mut prev = Value::obj();
    for m in MIME_TYPES {
        prev = prev.s(m, ini_get(&before, "Default Applications", m).unwrap_or_default());
    }
    backup_set("mime", prev.done())?;
    // Prefer xdg-mime (it also knows about other mimeapps locations), then verify by reading back.
    for m in MIME_TYPES {
        let _ = run("xdg-mime", &["default", DESKTOP_ID, m]);
    }
    if !mime_status() {
        let mut text = read_optional(&mimeapps())?.unwrap_or_default();
        for m in MIME_TYPES {
            text = ini_set(&text, "Default Applications", m, Some(DESKTOP_ID));
        }
        write_atomic(&mimeapps(), &text).map_err(|e| e.to_string())?;
    }
    if !mime_status() {
        return Err(format!("{} still not the inode/directory handler; is {DESKTOP_ID} installed under /usr/share/applications?", DESKTOP_ID));
    }
    Ok("path opens folders for other applications".into())
}

fn mime_remove() -> Result<String, String> {
    let path = mimeapps();
    let Some(text) = read_optional(&path)? else { return Ok("nothing to remove".into()) };
    let prev = backup_get("mime")?;
    if let Some(ref saved) = prev {
        for m in MIME_TYPES {
            let current = ini_get(&text, "Default Applications", m).unwrap_or_default();
            let original = saved.str_field(m).unwrap_or_default();
            if current.trim_end_matches(';') != DESKTOP_ID && current != original {
                return Err(format!("{m} changed since Path integration; left unchanged"));
            }
        }
    }
    let mut out = text.clone();
    for m in MIME_TYPES {
        // Put back what was there before path; without a record, just drop path from the line.
        let restored: Option<String> = match prev.as_ref().and_then(|p| p.str_field(m)) {
            Some("") => None,
            Some(v) => Some(v.to_string()),
            None => ini_get(&out, "Default Applications", m).map(|v| v.split(';').filter(|d| !d.is_empty() && *d != DESKTOP_ID).collect::<Vec<&str>>().join(";")).filter(|s| !s.is_empty()),
        };
        out = ini_set(&out, "Default Applications", m, restored.as_deref());
        if let Some(v) = ini_get(&out, "Added Associations", m) {
            let rest = v.split(';').filter(|d| !d.is_empty() && *d != DESKTOP_ID).collect::<Vec<&str>>().join(";");
            out = ini_set(&out, "Added Associations", m, if rest.is_empty() { None } else { Some(rest.as_str()) });
        }
    }
    if out != text {
        write_atomic(&path, &out).map_err(|e| e.to_string())?;
    }
    backup_clear("mime")?;
    Ok(match prev.as_ref().and_then(|p| p.str_field("inode/directory")).filter(|v| !v.is_empty()) {
        Some(v) => format!("folders open with {v} again"),
        None => "folder handler released".into(),
    })
}

// ---------------------------------------------------------------- 2. dbus

fn service_files() -> [(PathBuf, String); 2] {
    let dir = services_dir();
    let exec = pathd_path();
    [
        (dir.join("org.freedesktop.FileManager1.service"), format!("[D-BUS Service]\nName=org.freedesktop.FileManager1\nExec={exec}\nSystemdService=pathd.service\n")),
        (dir.join(format!("{PORTAL_NAME}.service")), format!("[D-BUS Service]\nName={PORTAL_NAME}\nExec={exec}\nSystemdService=pathd.service\n")),
    ]
}

fn runtime_services_dir() -> Option<PathBuf> {
    if std::env::var_os("PATHFM_INTEGRATE_HOME").is_some() {
        return Some(home().join(".runtime/dbus-1/services"));
    }
    std::env::var_os("XDG_RUNTIME_DIR").map(PathBuf::from).filter(|p| p.is_absolute()).map(|p| p.join("dbus-1/services"))
}

fn installed_services_dirs() -> Vec<PathBuf> {
    // A scratch integration home must never discover the host's installed services.
    if std::env::var_os("PATHFM_INTEGRATE_HOME").is_some() {
        return vec![home().join("usr/local/share/dbus-1/services"), home().join("usr/share/dbus-1/services")];
    }
    let data_dirs = std::env::var_os("XDG_DATA_DIRS").filter(|v| !v.is_empty()).unwrap_or_else(|| "/usr/local/share:/usr/share".into());
    let mut dirs: Vec<_> = std::env::split_paths(&data_dirs).filter(|p| p.is_absolute()).map(|p| p.join("dbus-1/services")).collect();
    // Fedora's session bus also searches its compiled-in data directory last.
    let system = PathBuf::from("/usr/share/dbus-1/services");
    if !dirs.contains(&system) {
        dirs.push(system);
    }
    // XDG_DATA_DIRS can repeat a per-user directory, including through a symlink.
    // Such a registration is not an installed replacement for the file we may retire.
    let user_dirs: Vec<_> = runtime_services_dir().into_iter().chain(std::iter::once(services_dir())).collect();
    dirs.retain(|dir| !user_dirs.iter().any(|user| dir == user || matches!((dir.canonicalize(), user.canonicalize()), (Ok(a), Ok(b)) if a == b)));
    dirs
}

fn portal_registration(dirs: impl IntoIterator<Item = PathBuf>) -> Result<Option<(PathBuf, String)>, String> {
    for dir in dirs {
        let p = dir.join(format!("{PORTAL_NAME}.service"));
        if let Some(text) = read_optional(&p).map_err(|e| format!("{}: {e}", p.display()))? {
            return Ok(Some((p, text)));
        }
    }
    Ok(None)
}

fn portal_service_dirs() -> impl Iterator<Item = PathBuf> {
    runtime_services_dir().into_iter().chain(std::iter::once(services_dir())).chain(installed_services_dirs())
}

fn path_service_valid(text: &str, name: &str) -> bool {
    let mut fields = std::collections::BTreeMap::new();
    let mut in_section = false;
    let mut seen_section = false;
    for line in text.lines() {
        let t = line.trim();
        if t.starts_with('[') {
            in_section = t == "[D-BUS Service]";
            if in_section {
                if seen_section {
                    return false;
                }
                seen_section = true;
            }
        } else if in_section {
            if let Some((k, v)) = t.split_once('=') {
                let k = k.trim();
                if matches!(k, "Name" | "Exec" | "SystemdService") && fields.insert(k, v.trim()).is_some() {
                    return false;
                }
            }
        }
    }
    fields.get("Name") == Some(&name) && fields.get("SystemdService") == Some(&"pathd.service") && fields.get("Exec").is_some_and(|exec| *exec == "/usr/bin/pathd" || *exec == pathd_path())
}

fn dbus_managed_files(backup: Option<&Value>) -> Result<Vec<String>, String> {
    let names: Vec<_> = service_files().iter().map(|(p, _)| p.file_name().unwrap().to_string_lossy().into_owned()).collect();
    let Some(backup) = backup else { return Ok(names) };
    if !matches!(backup, Value::Obj(_)) {
        return Err("invalid D-Bus integration backup".into());
    }
    // Legacy backups managed both user files, with missing entries meaning absent originals.
    let Some(managed) = backup.get("managedFiles") else { return Ok(names) };
    let entries = managed.as_arr().ok_or("invalid D-Bus integration backup")?;
    let mut result = Vec::new();
    for entry in entries {
        let name = entry.as_str().ok_or("invalid D-Bus integration backup")?;
        if !names.iter().any(|n| n == name) || result.iter().any(|n| n == name) {
            return Err("invalid D-Bus integration backup".into());
        }
        result.push(name.to_string());
    }
    Ok(result)
}

fn dbus_save_backup(mut previous: Value, managed: &[String]) -> Result<(), String> {
    let Value::Obj(ref mut record) = previous else { return Err("invalid D-Bus integration backup".into()) };
    record.insert("managedFiles".into(), Value::Arr(managed.iter().cloned().map(Value::Str).collect()));
    let Value::Obj(mut all) = backup_all()? else { return Err("invalid integration backup".into()) };
    all.insert("dbus".into(), previous);
    crate::config::write_named("integration.toml", &Value::Obj(all)).map_err(|e| format!("integration backup: {e}"))
}

fn dbus_status() -> bool {
    let file_manager = services_dir().join("org.freedesktop.FileManager1.service");
    std::fs::read_to_string(file_manager).is_ok_and(|t| path_service_valid(&t, "org.freedesktop.FileManager1"))
        && portal_registration(portal_service_dirs()).ok().flatten().is_some_and(|(_, t)| path_service_valid(&t, PORTAL_NAME))
}

fn dbus_apply() -> Result<String, String> {
    let registration = portal_registration(portal_service_dirs())?;
    let registered = registration.as_ref().is_some_and(|(_, t)| path_service_valid(t, PORTAL_NAME));
    if !registered {
        if let Some((p, _)) = &registration {
            if runtime_services_dir().is_some_and(|dir| p.parent() == Some(dir.as_path())) {
                return Err(format!("{} shadows Path portal activation; left unchanged", p.display()));
            }
        }
    }
    let files = service_files();
    let selected = &files[..if registered { 1 } else { 2 }];
    let previous = backup_get("dbus")?;
    let mut managed = if previous.is_some() { dbus_managed_files(previous.as_ref())? } else { Vec::new() };
    let mut previous = previous.unwrap_or_else(|| Value::obj().done());
    let Value::Obj(ref mut record) = previous else { return Err("invalid D-Bus integration backup".into()) };
    for (p, _) in selected {
        let name = p.file_name().unwrap().to_string_lossy().into_owned();
        if !managed.contains(&name) {
            if let Some(existing) = read_optional(p)? {
                record.insert(name.clone(), Value::Str(existing));
            } else {
                record.remove(&name);
            }
            managed.push(name);
        }
    }
    dbus_save_backup(previous.clone(), &managed)?;
    for (p, text) in selected {
        write_atomic(p, text).map_err(|e| format!("{}: {e}", p.display()))?;
    }
    // Retire an earlier managed duplicate only when its exact bytes still belong to us,
    // it had no original, and the installed registration can take over. Never touch a
    // pre-existing user registration or a later user edit.
    let (portal, expected) = &files[1];
    let name = portal.file_name().unwrap().to_string_lossy().into_owned();
    if registered && managed.contains(&name) && previous.get(&name).is_none() && portal_registration(installed_services_dirs())?.is_some_and(|(_, t)| path_service_valid(&t, PORTAL_NAME)) {
        let current = read_optional(portal)?;
        if current.as_deref().is_none_or(|t| t == expected) {
            if current.is_some() {
                std::fs::remove_file(portal).map_err(|e| format!("{}: {e}", portal.display()))?;
            }
            managed.retain(|n| n != &name);
            dbus_save_backup(previous, &managed)?;
        }
    }
    // The session bus rescans its service directories on ReloadConfig.
    run("dbus-send", &["--session", "--dest=org.freedesktop.DBus", "--type=method_call", "/org/freedesktop/DBus", "org.freedesktop.DBus.ReloadConfig"])?;
    Ok("\"Show in folder\" from browsers and chat apps opens path".into())
}

fn dbus_remove() -> Result<String, String> {
    let prev = backup_get("dbus")?;
    let managed = dbus_managed_files(prev.as_ref())?;
    let mut owned = Vec::new();
    // Preflight every managed file before changing any. Never remove another handler's file.
    for (p, expected) in service_files() {
        let name = p.file_name().unwrap().to_string_lossy().into_owned();
        if !managed.contains(&name) {
            continue;
        }
        let original = prev.as_ref().and_then(|v| v.str_field(&name));
        let current = match std::fs::read_to_string(&p) {
            Ok(text) => Some(text),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => None,
            Err(e) => return Err(format!("{}: {e}", p.display())),
        };
        if current.as_deref() == Some(expected.as_str()) {
            owned.push((p, original.map(str::to_string)));
        } else if prev.is_some() && current.as_deref() != original {
            return Err(format!("{} changed since Path integration; left unchanged", p.display()));
        }
    }
    for (p, original) in owned {
        match original.as_deref() {
            Some(original) => write_atomic(&p, original).map_err(|e| format!("{}: {e}", p.display()))?,
            None => {
                if p.exists() {
                    std::fs::remove_file(&p).map_err(|e| format!("{}: {e}", p.display()))?;
                }
            }
        }
    }
    run("dbus-send", &["--session", "--dest=org.freedesktop.DBus", "--type=method_call", "/org/freedesktop/DBus", "org.freedesktop.DBus.ReloadConfig"])?;
    backup_clear("dbus")?;
    Ok("D-Bus activation files removed".into())
}

// ---------------------------------------------------------------- 3. portal

fn portal_status() -> bool {
    let text = std::fs::read_to_string(portals_conf()).unwrap_or_default();
    ini_get(&text, "preferred", "org.freedesktop.impl.portal.FileChooser").map(|v| v.split(';').next() == Some("path")).unwrap_or(false)
}

fn portal_chain(current: &str) -> String {
    let mut chain: Vec<&str> = vec!["path"];
    chain.extend(current.split(';').filter(|b| !b.is_empty() && *b != "path"));
    if !chain.contains(&"gtk") {
        chain.push("gtk");
    }
    chain.join(";")
}

fn portal_apply() -> Result<String, String> {
    let text = read_optional(&portals_conf())?.unwrap_or_default();
    let current = ini_get(&text, "preferred", "org.freedesktop.impl.portal.FileChooser").unwrap_or_default();
    backup_set("portal", Value::obj().s("fileChooser", current.clone()).done())?;
    // Keep whatever was there as the fallback chain, gtk last so dialogs never vanish.
    let new = ini_set(&text, "preferred", "org.freedesktop.impl.portal.FileChooser", Some(&portal_chain(&current)));
    if new != text {
        write_atomic(&portals_conf(), &new).map_err(|e| e.to_string())?;
    }
    run("systemctl", &["--user", "restart", "xdg-desktop-portal"])?;
    Ok("Open and Save dialogs from other applications use path".into())
}

fn portal_remove() -> Result<String, String> {
    let path = portals_conf();
    let Some(text) = read_optional(&path)? else { return Ok("nothing to remove".into()) };
    let current = ini_get(&text, "preferred", "org.freedesktop.impl.portal.FileChooser").unwrap_or_default();
    // The recorded original wins; without one, drop path from the chain and keep the rest.
    let rest = match backup_get("portal")?.and_then(|p| p.str_field("fileChooser").map(str::to_string)) {
        Some(original) => {
            if current != portal_chain(&original) && current != original {
                return Err("chooser changed since Path integration; left unchanged".into());
            }
            original
        }
        None => current.split(';').filter(|b| !b.is_empty() && *b != "path").collect::<Vec<&str>>().join(";"),
    };
    let new = ini_set(&text, "preferred", "org.freedesktop.impl.portal.FileChooser", if rest.is_empty() { None } else { Some(rest.as_str()) });
    if new != text {
        write_atomic(&path, &new).map_err(|e| e.to_string())?;
    }
    run("systemctl", &["--user", "restart", "xdg-desktop-portal"])?;
    backup_clear("portal")?;
    Ok("chooser preference removed".into())
}

// ---------------------------------------------------------------- api

pub fn status_json() -> Value {
    Value::obj()
        .b("mime", mime_status())
        .b("dbus", dbus_status())
        .b("portal", portal_status())
        .s("mimeapps", mimeapps().to_string_lossy().into_owned())
        .s("portals", portals_conf().to_string_lossy().into_owned())
        .s("services", services_dir().to_string_lossy().into_owned())
        .done()
}

fn parts_of(v: Option<&Value>) -> Vec<String> {
    match v.and_then(Value::as_arr) {
        Some(a) if !a.is_empty() => a.iter().filter_map(Value::as_str).map(str::to_string).collect(),
        _ => PARTS.iter().map(|s| s.to_string()).collect(),
    }
}

/// Applies the requested parts (all when empty); each entry is `{ part, ok, message }`.
pub fn apply(parts: Option<&Value>) -> Value {
    let mut out = Vec::new();
    for p in parts_of(parts) {
        let r = match p.as_str() {
            "mime" => mime_apply(),
            "dbus" => dbus_apply(),
            "portal" => portal_apply(),
            _ => Err("unknown part".into()),
        };
        out.push(result_json(&p, r));
    }
    Value::obj().v("results", Value::Arr(out)).v("status", status_json()).done()
}

pub fn remove(parts: Option<&Value>) -> Value {
    let mut out = Vec::new();
    for p in parts_of(parts) {
        let r = match p.as_str() {
            "mime" => mime_remove(),
            "dbus" => dbus_remove(),
            "portal" => portal_remove(),
            _ => Err("unknown part".into()),
        };
        out.push(result_json(&p, r));
    }
    Value::obj().v("results", Value::Arr(out)).v("status", status_json()).done()
}

fn result_json(part: &str, r: Result<String, String>) -> Value {
    match r {
        Ok(m) => Value::obj().s("part", part).b("ok", true).s("message", m).done(),
        Err(m) => Value::obj().s("part", part).b("ok", false).s("message", m).done(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn scratch() -> PathBuf {
        let d = std::env::temp_dir().join(format!("path-integrate-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).unwrap();
        std::env::set_var("PATHFM_INTEGRATE_HOME", &d);
        std::env::set_var("PATHFM_INTEGRATE_NO_EXEC", "1");
        d
    }

    fn done(d: &Path) {
        std::env::remove_var("PATHFM_INTEGRATE_HOME");
        std::env::remove_var("PATHFM_INTEGRATE_NO_EXEC");
        let _ = std::fs::remove_dir_all(d);
    }

    fn installed_portal(d: &Path) -> PathBuf {
        let p = d.join("usr/share/dbus-1/services").join(format!("{PORTAL_NAME}.service"));
        write_atomic(&p, include_str!("../../packaging/org.freedesktop.impl.portal.desktop.pathfm.service")).unwrap();
        p
    }

    #[test]
    fn dbus_reuses_installed_portal_and_restores_file_manager() {
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        std::env::set_var("PATHFM_CONFIG_DIR", d.join(".config/path"));
        let installed = installed_portal(&d);
        let installed_before = std::fs::read(&installed).unwrap();
        let file_manager = services_dir().join("org.freedesktop.FileManager1.service");
        let portal = services_dir().join(format!("{PORTAL_NAME}.service"));
        let original = "[D-BUS Service]\nName=org.freedesktop.FileManager1\nExec=/usr/bin/thunar\n";
        write_atomic(&file_manager, original).unwrap();
        for _ in 0..2 {
            dbus_apply().unwrap();
            assert!(!portal.exists(), "installed portal registration must not be copied into the user service directory");
            assert!(dbus_status(), "installed portal plus user FileManager1 must count as integrated");
            assert_eq!(std::fs::read(&installed).unwrap(), installed_before);
        }
        dbus_remove().unwrap();
        assert_eq!(std::fs::read_to_string(file_manager).unwrap(), original);
        assert!(!portal.exists());
        assert_eq!(std::fs::read(installed).unwrap(), installed_before);
        assert!(!dbus_status());
        assert!(backup_get("dbus").unwrap().is_none());
        std::env::remove_var("PATHFM_CONFIG_DIR");
        done(&d);
    }

    #[test]
    fn dbus_remove_preserves_portal_created_after_installed_reuse() {
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        std::env::set_var("PATHFM_CONFIG_DIR", d.join(".config/path"));
        installed_portal(&d);
        dbus_apply().unwrap();
        let portal = services_dir().join(format!("{PORTAL_NAME}.service"));
        let later = format!("[D-BUS Service]\nName={PORTAL_NAME}\nExec=/usr/bin/another-portal\n");
        write_atomic(&portal, &later).unwrap();
        assert!(!dbus_status(), "a user service shadows the installed registration");
        assert!(dbus_remove().is_ok(), "removal must not treat an untouched portal as managed");
        assert_eq!(std::fs::read_to_string(portal).unwrap(), later);
        assert!(!services_dir().join("org.freedesktop.FileManager1.service").exists());
        assert!(backup_get("dbus").unwrap().is_none());
        std::env::remove_var("PATHFM_CONFIG_DIR");
        done(&d);
    }

    #[test]
    fn dbus_reuse_preserves_existing_user_portal_bytes() {
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        std::env::set_var("PATHFM_CONFIG_DIR", d.join(".config/path"));
        installed_portal(&d);
        let portal = services_dir().join(format!("{PORTAL_NAME}.service"));
        let original = format!("# User registration\n[D-BUS Service]\nName = {PORTAL_NAME}\nExec = /usr/bin/pathd\nSystemdService = pathd.service\n");
        write_atomic(&portal, &original).unwrap();
        dbus_apply().unwrap();
        assert_eq!(std::fs::read_to_string(&portal).unwrap(), original, "a valid pre-existing portal must not be rewritten");
        assert!(dbus_status());
        let later = format!("{original}# User edit after Apply\n");
        write_atomic(&portal, &later).unwrap();
        dbus_remove().unwrap();
        assert_eq!(std::fs::read_to_string(portal).unwrap(), later);
        std::env::remove_var("PATHFM_CONFIG_DIR");
        done(&d);
    }

    #[test]
    fn dbus_reuse_falls_back_when_installed_registration_is_invalid() {
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        std::env::set_var("PATHFM_CONFIG_DIR", d.join(".config/path"));
        let installed = installed_portal(&d);
        let valid = std::fs::read_to_string(&installed).unwrap();
        for invalid in [
            valid.replace(PORTAL_NAME, "org.example.Other"),
            valid.replace("Exec=/usr/bin/pathd", "Exec=/usr/bin/other # pathd"),
            valid.replace("SystemdService=pathd.service\n", ""),
            format!("{valid}Name=org.example.Other\n"),
        ] {
            std::fs::write(&installed, &invalid).unwrap();
            dbus_apply().unwrap();
            assert!(services_dir().join(format!("{PORTAL_NAME}.service")).exists());
            assert!(dbus_status());
            dbus_remove().unwrap();
            assert_eq!(std::fs::read_to_string(&installed).unwrap(), invalid);
        }
        std::env::remove_var("PATHFM_CONFIG_DIR");
        done(&d);
    }

    #[test]
    fn dbus_reuse_respects_installed_service_precedence() {
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        std::env::set_var("PATHFM_CONFIG_DIR", d.join(".config/path"));
        installed_portal(&d);
        let higher = d.join("usr/local/share/dbus-1/services").join(format!("{PORTAL_NAME}.service"));
        let invalid = format!("[D-BUS Service]\nName={PORTAL_NAME}\nExec=/usr/bin/other\n");
        write_atomic(&higher, &invalid).unwrap();
        dbus_apply().unwrap();
        assert!(services_dir().join(format!("{PORTAL_NAME}.service")).exists(), "an invalid higher-priority service must not be ignored");
        assert!(dbus_status());
        dbus_remove().unwrap();
        assert_eq!(std::fs::read_to_string(higher).unwrap(), invalid);
        std::env::remove_var("PATHFM_CONFIG_DIR");
        done(&d);
    }

    #[test]
    fn dbus_reuse_tracks_fallback_added_on_later_apply() {
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        std::env::set_var("PATHFM_CONFIG_DIR", d.join(".config/path"));
        let installed = installed_portal(&d);
        dbus_apply().unwrap();
        std::fs::remove_file(installed).unwrap();
        let portal = services_dir().join(format!("{PORTAL_NAME}.service"));
        let later = format!("[D-BUS Service]\nName={PORTAL_NAME}\nExec=/usr/bin/other\n");
        write_atomic(&portal, &later).unwrap();
        dbus_apply().unwrap();
        assert!(dbus_status());
        dbus_remove().unwrap();
        assert_eq!(std::fs::read_to_string(portal).unwrap(), later, "fallback must preserve the choice made while the portal was unmanaged");
        std::env::remove_var("PATHFM_CONFIG_DIR");
        done(&d);
    }

    #[test]
    fn dbus_reuse_retires_only_a_backed_up_owned_portal_duplicate() {
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        std::env::set_var("PATHFM_CONFIG_DIR", d.join(".config/path"));
        installed_portal(&d);
        let original = "[D-BUS Service]\nName=org.freedesktop.FileManager1\nExec=/usr/bin/thunar\n";
        // The old format backed up both files; an absent key means that file did not exist.
        backup_set("dbus", Value::obj().s("org.freedesktop.FileManager1.service", original).done()).unwrap();
        for (p, text) in service_files() {
            write_atomic(&p, &text).unwrap();
        }
        let portal = services_dir().join(format!("{PORTAL_NAME}.service"));
        dbus_apply().unwrap();
        assert!(!portal.exists(), "an owned duplicate with no original must yield to the installed registration");
        assert!(dbus_status());
        let later = format!("[D-BUS Service]\nName={PORTAL_NAME}\nExec=/usr/bin/other\n");
        write_atomic(&portal, &later).unwrap();
        dbus_remove().unwrap();
        assert_eq!(std::fs::read_to_string(portal).unwrap(), later);
        assert_eq!(std::fs::read_to_string(services_dir().join("org.freedesktop.FileManager1.service")).unwrap(), original);
        std::env::remove_var("PATHFM_CONFIG_DIR");
        done(&d);
    }

    #[test]
    fn dbus_reuse_rejects_a_conflicting_runtime_registration_before_writing() {
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        std::env::set_var("PATHFM_CONFIG_DIR", d.join(".config/path"));
        installed_portal(&d);
        let runtime = d.join(".runtime/dbus-1/services").join(format!("{PORTAL_NAME}.service"));
        let original = format!("[D-BUS Service]\nName={PORTAL_NAME}\nExec=/usr/bin/other\n");
        write_atomic(&runtime, &original).unwrap();
        assert_eq!(dbus_apply().unwrap_err(), format!("{} shadows Path portal activation; left unchanged", runtime.display()));
        assert!(!services_dir().exists());
        assert!(backup_get("dbus").unwrap().is_none());
        assert_eq!(std::fs::read_to_string(runtime).unwrap(), original);
        std::env::remove_var("PATHFM_CONFIG_DIR");
        done(&d);
    }

    #[test]
    fn dbus_reuse_rejects_invalid_managed_file_metadata() {
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        std::env::set_var("PATHFM_CONFIG_DIR", d.join(".config/path"));
        backup_set("dbus", Value::obj().v("managedFiles", Value::Arr(vec![Value::Str("../other.service".into())])).done()).unwrap();
        let before = backup_get("dbus").unwrap();
        assert_eq!(dbus_apply().unwrap_err(), "invalid D-Bus integration backup");
        assert_eq!(dbus_remove().unwrap_err(), "invalid D-Bus integration backup");
        assert!(!services_dir().exists());
        assert_eq!(backup_get("dbus").unwrap(), before);
        std::env::remove_var("PATHFM_CONFIG_DIR");
        done(&d);
    }

    #[test]
    fn dbus_status_requires_activation_fields_not_a_pathd_substring() {
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        std::env::set_var("PATHFM_CONFIG_DIR", d.join(".config/path"));
        dbus_apply().unwrap();
        let file_manager = services_dir().join("org.freedesktop.FileManager1.service");
        write_atomic(&file_manager, "[D-BUS Service]\nName=org.freedesktop.FileManager1\nExec=/usr/bin/other\n# pathd\n").unwrap();
        assert!(!dbus_status(), "mentions of pathd must not count as a usable activation registration");
        std::env::remove_var("PATHFM_CONFIG_DIR");
        done(&d);
    }

    #[test]
    fn dbus_reuse_honors_custom_data_dirs_without_retiring_its_own_fallback() {
        // Exercise real XDG lookup in a child, without exposing other tests to these variables.
        const CHILD: &str = "PATHFM_TEST_PORTAL_DATA_DIRS_CHILD";
        if std::env::var_os(CHILD).is_none() {
            let output = Command::new(std::env::current_exe().unwrap())
                .args(["--exact", "integrate::tests::dbus_reuse_honors_custom_data_dirs_without_retiring_its_own_fallback", "--nocapture"])
                .env(CHILD, "1")
                .output()
                .unwrap();
            assert!(output.status.success(), "child XDG test: {}{}", String::from_utf8_lossy(&output.stdout), String::from_utf8_lossy(&output.stderr));
            assert!(String::from_utf8_lossy(&output.stdout).contains("1 passed; 0 failed"));
            return;
        }
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        std::env::remove_var("PATHFM_INTEGRATE_HOME");
        std::env::set_var("HOME", &d);
        std::env::set_var("XDG_CONFIG_HOME", d.join(".config"));
        std::env::set_var("XDG_DATA_HOME", d.join(".local/share"));
        std::env::set_var("XDG_RUNTIME_DIR", d.join(".runtime"));
        std::env::set_var("PATHFM_CONFIG_DIR", d.join(".config/path"));
        std::env::set_var("XDG_DATA_DIRS", "");
        assert_eq!(installed_services_dirs(), vec![PathBuf::from("/usr/local/share/dbus-1/services"), PathBuf::from("/usr/share/dbus-1/services")]);
        let first = d.join("first");
        let second = d.join("second");
        std::env::set_var("XDG_DATA_DIRS", format!("relative:{}::{}", first.display(), second.display()));
        assert_eq!(installed_services_dirs(), vec![first.join("dbus-1/services"), second.join("dbus-1/services"), PathBuf::from("/usr/share/dbus-1/services")]);
        let installed = second.join("dbus-1/services").join(format!("{PORTAL_NAME}.service"));
        write_atomic(&installed, include_str!("../../packaging/org.freedesktop.impl.portal.desktop.pathfm.service")).unwrap();
        dbus_apply().unwrap();
        let portal = services_dir().join(format!("{PORTAL_NAME}.service"));
        assert!(!portal.exists());
        assert!(dbus_status());
        dbus_remove().unwrap();
        // An invalid custom registration shadows any host installation, keeping this fixture hermetic.
        let invalid = format!("[D-BUS Service]\nName={PORTAL_NAME}\nExec=/usr/bin/other\n");
        std::fs::write(&installed, &invalid).unwrap();
        dbus_apply().unwrap();
        assert!(portal.exists());
        let alias = d.join("user-data-alias");
        std::os::unix::fs::symlink(data_home(), &alias).unwrap();
        for data_dir in [data_home(), alias] {
            std::env::set_var("XDG_DATA_DIRS", format!("{}:{}", data_dir.display(), second.display()));
            dbus_apply().unwrap();
            assert!(portal.exists(), "a user-directory entry in XDG_DATA_DIRS is not an installed replacement");
            assert!(dbus_status());
        }
        dbus_remove().unwrap();
        assert!(!portal.exists());
        assert_eq!(std::fs::read_to_string(installed).unwrap(), invalid);
        done(&d);
    }

    #[test]
    fn remove_without_backup_preserves_unrelated_dbus_services() {
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        std::env::set_var("PATHFM_CONFIG_DIR", d.join(".config/path"));
        let p = services_dir().join("org.freedesktop.FileManager1.service");
        let original = "[D-BUS Service]\nName=org.freedesktop.FileManager1\nExec=/usr/bin/thunar\n";
        write_atomic(&p, original).unwrap();
        assert!(dbus_remove().is_ok());
        assert_eq!(std::fs::read_to_string(p).unwrap(), original);
        std::env::remove_var("PATHFM_CONFIG_DIR");
        done(&d);
    }

    #[test]
    fn removal_preserves_later_user_choices_and_backups() {
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        std::env::set_var("PATHFM_CONFIG_DIR", d.join(".config/path"));
        assert!(apply(None).get("results").unwrap().as_arr().unwrap().iter().all(|r| r.get("ok") == Some(&Value::Bool(true))));
        let mime = "[Default Applications]\ninode/directory=thunar.desktop\n";
        let portal = "[preferred]\norg.freedesktop.impl.portal.FileChooser=kde;gtk\n";
        let service = "[D-BUS Service]\nName=org.freedesktop.FileManager1\nExec=/usr/bin/thunar\n";
        write_atomic(&mimeapps(), mime).unwrap();
        write_atomic(&portals_conf(), portal).unwrap();
        write_atomic(&services_dir().join("org.freedesktop.FileManager1.service"), service).unwrap();
        assert!(mime_remove().is_err(), "must report a changed folder handler");
        assert!(portal_remove().is_err(), "must report a changed chooser");
        assert!(dbus_remove().is_err(), "must report a changed activation file");
        assert_eq!(std::fs::read_to_string(mimeapps()).unwrap(), mime);
        assert_eq!(std::fs::read_to_string(portals_conf()).unwrap(), portal);
        assert_eq!(std::fs::read_to_string(services_dir().join("org.freedesktop.FileManager1.service")).unwrap(), service);
        for part in PARTS {
            assert!(backup_get(part).unwrap().is_some(), "{part} backup lost");
        }
        std::env::remove_var("PATHFM_CONFIG_DIR");
        done(&d);
    }

    #[test]
    fn failed_backup_prevents_every_integration_write() {
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        let blocked = d.join("blocked");
        std::fs::write(&blocked, "not a directory").unwrap();
        std::env::set_var("PATHFM_CONFIG_DIR", blocked);
        for r in apply(None).get("results").unwrap().as_arr().unwrap() {
            assert_eq!(r.get("ok"), Some(&Value::Bool(false)), "backup failure must be reported");
        }
        assert!(!mimeapps().exists());
        assert!(!portals_conf().exists());
        assert!(!services_dir().exists());
        std::env::remove_var("PATHFM_CONFIG_DIR");
        done(&d);
    }

    #[test]
    fn removal_preserves_changed_path_portal_fallback() {
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        std::env::set_var("PATHFM_CONFIG_DIR", d.join(".config/path"));
        portal_apply().unwrap();
        let changed = "[preferred]\norg.freedesktop.impl.portal.FileChooser=path;kde;gtk\n";
        write_atomic(&portals_conf(), changed).unwrap();
        assert!(portal_remove().is_err(), "must preserve a changed fallback chain");
        assert_eq!(std::fs::read_to_string(portals_conf()).unwrap(), changed);
        assert!(backup_get("portal").unwrap().is_some());
        std::env::remove_var("PATHFM_CONFIG_DIR");
        done(&d);
    }

    #[test]
    fn partial_mime_apply_sets_all_three_handlers() {
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        std::env::set_var("PATHFM_CONFIG_DIR", d.join(".config/path"));
        write_atomic(&mimeapps(), &format!("[Default Applications]\ninode/directory={DESKTOP_ID}\nx-scheme-handler/sftp=other.desktop\n")).unwrap();
        mime_apply().unwrap();
        let text = std::fs::read_to_string(mimeapps()).unwrap();
        for m in MIME_TYPES {
            assert_eq!(ini_get(&text, "Default Applications", m).as_deref(), Some(DESKTOP_ID));
        }
        std::env::remove_var("PATHFM_CONFIG_DIR");
        done(&d);
    }

    #[test]
    fn failed_portal_write_keeps_the_original_backup() {
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        std::env::set_var("PATHFM_CONFIG_DIR", d.join(".config/path"));
        portal_apply().unwrap();
        let before = backup_get("portal").unwrap();
        std::fs::create_dir(portals_conf().with_extension(format!("path-tmp-{}", std::process::id()))).unwrap();
        assert!(portal_remove().is_err());
        assert_eq!(backup_get("portal").unwrap(), before);
        assert!(portal_status());
        std::env::remove_var("PATHFM_CONFIG_DIR");
        done(&d);
    }

    #[test]
    fn unreadable_config_is_an_error_not_success() {
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        std::env::set_var("PATHFM_CONFIG_DIR", d.join(".config/path"));
        std::fs::create_dir_all(mimeapps()).unwrap();
        std::fs::create_dir_all(portals_conf()).unwrap();
        assert!(mime_remove().is_err());
        assert!(portal_remove().is_err());
        std::env::remove_var("PATHFM_CONFIG_DIR");
        done(&d);
    }

    #[test]
    fn failed_dbus_reload_retains_backup_for_retry() {
        // PATH is process-wide: inject the launch failure only in a child test
        // process, so concurrent Git/process tests retain their executable search.
        const CHILD: &str = "PATHFM_TEST_DBUS_RELOAD_CHILD";
        if std::env::var_os(CHILD).is_none() {
            let before = std::env::var_os("PATH");
            let output = Command::new(std::env::current_exe().unwrap()).args(["--exact", "integrate::tests::failed_dbus_reload_retains_backup_for_retry", "--nocapture"]).env(CHILD, "1").output().unwrap();
            assert!(output.status.success(), "child failure test: {}{}", String::from_utf8_lossy(&output.stdout), String::from_utf8_lossy(&output.stderr));
            assert!(String::from_utf8_lossy(&output.stdout).contains("1 passed; 0 failed"), "child must execute the selected test, not silently match zero tests");
            assert_eq!(std::env::var_os("PATH"), before, "child must not change the parent PATH");
            return;
        }
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        std::env::set_var("PATHFM_CONFIG_DIR", d.join(".config/path"));
        dbus_apply().unwrap();
        std::env::remove_var("PATHFM_INTEGRATE_NO_EXEC");
        let old_path = std::env::var_os("PATH");
        std::env::set_var("PATH", "");
        let result = dbus_remove();
        match old_path {
            Some(p) => std::env::set_var("PATH", p),
            None => std::env::remove_var("PATH"),
        }
        std::env::set_var("PATHFM_INTEGRATE_NO_EXEC", "1");
        assert!(result.unwrap_err().starts_with("dbus-send:"));
        assert!(backup_get("dbus").unwrap().is_some());
        assert!(dbus_remove().is_ok(), "retry must complete after reload is available");
        assert!(backup_get("dbus").unwrap().is_none());
        std::env::remove_var("PATHFM_CONFIG_DIR");
        done(&d);
    }

    #[test]
    fn ini_editing() {
        let t = "[Default Applications]\ntext/plain=nvim.desktop\n\n[Added Associations]\nimage/png=imv.desktop;\n";
        let s = ini_set(t, "Default Applications", "inode/directory", Some("pathfm.desktop"));
        assert_eq!(ini_get(&s, "Default Applications", "inode/directory").as_deref(), Some("pathfm.desktop"));
        assert_eq!(ini_get(&s, "Default Applications", "text/plain").as_deref(), Some("nvim.desktop"));
        let s2 = ini_set(&s, "Default Applications", "inode/directory", None);
        assert!(ini_get(&s2, "Default Applications", "inode/directory").is_none());
        assert!(s2.contains("[Added Associations]\nimage/png=imv.desktop;"));
        // a missing section is appended
        let s3 = ini_set("", "preferred", "org.freedesktop.impl.portal.FileChooser", Some("path;gtk"));
        assert_eq!(s3, "[preferred]\norg.freedesktop.impl.portal.FileChooser=path;gtk\n");
    }

    #[test]
    fn dwm_titus_uses_xdg_defaults_without_editing_wm_configs() {
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        std::env::set_var("PATHFM_CONFIG_DIR", d.join(".config/path"));
        let wm = d.join(".config/dwm-titus");
        std::fs::create_dir_all(&wm).unwrap();
        let hotkeys = "keys = [{ mod=\"SUPER\", key=\"e\", func=\"spawn\", cmd=\"xdg-open .\" }]\n";
        let rules = "rules = [{ class=\"kitty\", isterminal=1 }]\n";
        std::fs::write(wm.join("hotkeys.toml"), hotkeys).unwrap();
        std::fs::write(wm.join("window-rules.toml"), rules).unwrap();
        assert_eq!(PARTS.as_slice(), ["mime", "dbus", "portal"]);
        for _ in 0..2 {
            let r = apply(None);
            assert!(r.get("results").unwrap().as_arr().unwrap().iter().all(|p| p.get("ok") == Some(&Value::Bool(true))));
        }
        assert!(!d.join(".config/hypr").exists());
        let legacy = Value::Arr(vec![Value::Str("hypr".into())]);
        let rejected = apply(Some(&legacy));
        assert_eq!(rejected.get("results").unwrap().as_arr().unwrap()[0].get("ok"), Some(&Value::Bool(false)));
        remove(None);
        assert_eq!(std::fs::read_to_string(wm.join("hotkeys.toml")).unwrap(), hotkeys);
        assert_eq!(std::fs::read_to_string(wm.join("window-rules.toml")).unwrap(), rules);
        std::env::remove_var("PATHFM_CONFIG_DIR");
        done(&d);
    }

    #[test]
    fn apply_and_remove_everything_per_user() {
        let _g = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let d = scratch();
        // pre-existing user config that must survive
        std::fs::create_dir_all(d.join(".config/hypr")).unwrap();
        std::fs::write(d.join(".config/hypr/bindings.conf"), "bindd = SUPER, RETURN, Terminal, exec, alacritty\n").unwrap();
        std::fs::create_dir_all(d.join(".config/xdg-desktop-portal")).unwrap();
        std::fs::write(d.join(".config/xdg-desktop-portal/portals.conf"), "[preferred]\ndefault=hyprland;gtk\norg.freedesktop.impl.portal.FileChooser=gtk\n").unwrap();
        std::fs::write(d.join(".config/mimeapps.list"), "[Default Applications]\ntext/plain=nvim.desktop\ninode/directory=org.gnome.Nautilus.desktop\n").unwrap();
        std::env::set_var("PATHFM_CONFIG_DIR", d.join(".config/path"));

        let r = apply(None);
        let results = r.get("results").unwrap().as_arr().unwrap();
        assert!(results.iter().all(|x| x.get("ok") == Some(&Value::Bool(true))), "{}", crate::json::to_string(&r));
        let st = r.get("status").unwrap();
        for p in PARTS {
            assert_eq!(st.get(p), Some(&Value::Bool(true)), "{p}");
        }
        let mime = std::fs::read_to_string(d.join(".config/mimeapps.list")).unwrap();
        assert!(mime.contains("inode/directory=pathfm.desktop"));
        assert!(mime.contains("text/plain=nvim.desktop"));
        let portals = std::fs::read_to_string(d.join(".config/xdg-desktop-portal/portals.conf")).unwrap();
        assert!(portals.contains("org.freedesktop.impl.portal.FileChooser=path;gtk"));
        assert!(portals.contains("default=hyprland;gtk"));
        assert!(d.join(".local/share/dbus-1/services/org.freedesktop.FileManager1.service").exists());
        let bindings = std::fs::read_to_string(d.join(".config/hypr/bindings.conf")).unwrap();
        assert!(bindings.starts_with("bindd = SUPER, RETURN"));
        assert_eq!(bindings, "bindd = SUPER, RETURN, Terminal, exec, alacritty\n", "other desktops remain untouched");

        let r = remove(None);
        let st = r.get("status").unwrap();
        for p in PARTS {
            assert_eq!(st.get(p), Some(&Value::Bool(false)), "{p} still on");
        }
        assert_eq!(std::fs::read_to_string(d.join(".config/hypr/bindings.conf")).unwrap(), "bindd = SUPER, RETURN, Terminal, exec, alacritty\n");
        assert_eq!(std::fs::read_to_string(d.join(".config/xdg-desktop-portal/portals.conf")).unwrap(), "[preferred]\ndefault=hyprland;gtk\norg.freedesktop.impl.portal.FileChooser=gtk\n");
        assert_eq!(
            std::fs::read_to_string(d.join(".config/mimeapps.list")).unwrap(),
            "[Default Applications]\ntext/plain=nvim.desktop\ninode/directory=org.gnome.Nautilus.desktop\n",
            "the previous folder handler is back"
        );
        assert!(!d.join(".config/path/integration.toml").exists() || !std::fs::read_to_string(d.join(".config/path/integration.toml")).unwrap().contains("mime"), "backup cleared");
        std::env::remove_var("PATHFM_CONFIG_DIR");
        assert!(!d.join(".local/share/dbus-1/services/org.freedesktop.FileManager1.service").exists());
        done(&d);
    }
}
