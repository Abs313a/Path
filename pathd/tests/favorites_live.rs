//! Default favorites change on the live shell socket even while its pane is elsewhere.
#![cfg(target_os = "linux")]

use pathd::json::Value;
use std::io::{BufRead, BufReader, Write};
use std::os::unix::fs::PermissionsExt;
use std::os::unix::net::UnixStream;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

struct Daemon {
    child: std::process::Child,
    runtime: PathBuf,
}
impl Drop for Daemon {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
        let _ = std::fs::remove_dir_all(&self.runtime);
    }
}
struct Client {
    stream: UnixStream,
    lines: BufReader<UnixStream>,
    id: u64,
}
impl Client {
    fn read(&mut self) -> Value {
        let mut line = String::new();
        assert!(self.lines.read_line(&mut line).expect("FavoritesChanged did not arrive on the live shell socket") > 0);
        pathd::json::parse(line.trim().as_bytes()).unwrap()
    }
    fn ask(&mut self, kind: &str, body: Value) -> Value {
        self.id += 1;
        let Value::Obj(mut obj) = body else { panic!("object body") };
        obj.insert("id".into(), Value::Uint(self.id));
        obj.insert("type".into(), Value::Str(kind.into()));
        writeln!(self.stream, "{}", pathd::json::to_string(&Value::Obj(obj))).unwrap();
        loop {
            let v = self.read();
            if v.u64_field("id") == Some(self.id) {
                assert!(v.get("err").is_none(), "{kind}: {v:?}");
                return v.get("ok").unwrap().clone();
            }
        }
    }
    fn changed(&mut self) {
        let start = Instant::now();
        loop {
            assert!(start.elapsed() < Duration::from_secs(3), "FavoritesChanged missing after HOME directory change");
            if self.read().str_field("event") == Some("FavoritesChanged") {
                return;
            }
        }
    }
    fn names(&mut self) -> Vec<String> {
        self.ask("Favorites", Value::obj().done()).get("items").unwrap().as_arr().unwrap().iter().map(|v| v.str_field("name").unwrap().to_owned()).collect()
    }
}
fn uri(p: &Path) -> String {
    pathd::vfs::uri::Uri::from_path(p).to_string()
}

#[test]
fn defaults_refresh_live_and_survive_home_listing_release_and_eviction() {
    let sandbox = std::env::temp_dir().join(format!("path-favorites-live-{}", std::process::id()));
    std::fs::create_dir_all(sandbox.join("home")).unwrap();
    std::fs::create_dir_all(sandbox.join("elsewhere")).unwrap();
    let home = sandbox.join("home");
    // Unix socket paths are limited to 108 bytes; TMPDIR may be a long scratch path.
    let runtime = PathBuf::from(format!("/tmp/path-favorites-runtime-{}", std::process::id()));
    std::fs::create_dir(&runtime).unwrap();
    std::fs::set_permissions(&runtime, std::fs::Permissions::from_mode(0o700)).unwrap();
    let socket = runtime.join("path.sock");
    let plugins = sandbox.join("plugins");
    std::fs::create_dir(&plugins).unwrap();
    // PATHFM_PLUGIN_DIR prepends rather than replacing system discovery. Shadow the
    // startup D-Bus helper with an owned no-op so an installed helper cannot be launched.
    let dbus = plugins.join("path-plugin-dbus");
    std::fs::write(&dbus, b"#!/bin/sh\nexit 0\n").unwrap();
    std::fs::set_permissions(&dbus, std::fs::Permissions::from_mode(0o700)).unwrap();
    let stderr = sandbox.join("daemon.stderr");
    let mut command = std::process::Command::new(env!("CARGO_BIN_EXE_pathd"));
    // Clear inherited D-Bus/display credentials, socket activation, PATHFM overrides,
    // and XDG homes together. All state and executable discovery belong to this test.
    command.env_clear().env("PATH", sandbox.join("bin")).env("XDG_RUNTIME_DIR", &runtime).env("PATHFM_SYSFS_USB", sandbox.join("sysfs"));
    for (key, dir) in [("CONFIG", "xdg-config"), ("DATA", "xdg-data"), ("STATE", "xdg-state"), ("CACHE", "xdg-cache")] {
        command.env(format!("XDG_{key}_HOME"), sandbox.join(dir));
    }
    command.env("HOME", &home).env("PATHFM_SOCKET", &socket);
    for (key, dir) in [("CONFIG", "config"), ("STATE", "state"), ("DATA", "data"), ("TRASH", "trash"), ("THUMB", "thumbs"), ("PLUGIN", "plugins")] {
        command.env(format!("PATHFM_{key}_DIR"), sandbox.join(dir));
    }
    let daemon = Daemon { child: command.stdout(std::process::Stdio::null()).stderr(std::fs::File::create(&stderr).unwrap()).spawn().unwrap(), runtime };
    let start = Instant::now();
    let stream = loop {
        if let Ok(s) = UnixStream::connect(&socket) {
            break s;
        }
        assert!(start.elapsed() < Duration::from_secs(3), "daemon startup timeout");
        std::thread::sleep(Duration::from_millis(10));
    };
    stream.set_read_timeout(Some(Duration::from_secs(3))).unwrap();
    let mut c = Client { lines: BufReader::new(stream.try_clone().unwrap()), stream, id: 0 };
    c.ask("Hello", Value::obj().s("client", "pathfm").done());
    c.ask("JobEvents", Value::obj().done());
    c.ask("Open", Value::obj().u("lid", 1).s("uri", uri(&sandbox.join("elsewhere"))).done());
    assert!(!c.names().iter().any(|n| n == "Projects"));
    std::fs::create_dir(home.join("Projects")).unwrap();
    c.changed();
    assert!(c.names().iter().any(|n| n == "Projects"));
    // A Home listing shares the pinned inotify descriptor; closing it must preserve favorites.
    c.ask("Open", Value::obj().u("lid", 2).s("uri", uri(&home)).done());
    c.ask("Close", Value::obj().u("lid", 2).done());
    std::fs::rename(home.join("Projects"), home.join("Other")).unwrap();
    c.changed();
    assert!(!c.names().iter().any(|n| n == "Projects"));
    std::fs::rename(home.join("Other"), home.join("Desktop")).unwrap();
    c.changed();
    assert!(c.names().iter().any(|n| n == "Desktop"));
    std::fs::remove_dir(home.join("Desktop")).unwrap();
    c.changed();
    std::fs::write(home.join("Projects"), b"file, not directory").unwrap();
    assert!(!c.names().iter().any(|n| n == "Projects"));
    std::fs::remove_file(home.join("Projects")).unwrap();
    std::fs::create_dir(home.join("Projects")).unwrap();
    c.changed();
    assert!(c.names().iter().any(|n| n == "Projects"));
    // Evict Home's listing role while leaving the favorites role alive.
    c.ask("Open", Value::obj().u("lid", 2).s("uri", uri(&home)).done());
    for i in 0..=pathd::watch::MAX_WATCHES {
        let p = sandbox.join(format!("listing-{i}"));
        std::fs::create_dir(&p).unwrap();
        c.ask("Open", Value::obj().u("lid", 10 + i as u64).s("uri", uri(&p)).done());
    }
    std::fs::remove_dir(home.join("Projects")).unwrap();
    c.changed();
    assert!(!c.names().iter().any(|n| n == "Projects"));
    let custom = Value::Arr(vec![Value::obj().s("name", "Custom").s("uri", uri(&home.join("Projects"))).done()]);
    c.ask("SetFavorites", Value::obj().v("items", custom.clone()).done());
    std::fs::create_dir(home.join("Projects")).unwrap();
    std::fs::create_dir(home.join("Desktop")).unwrap();
    assert_eq!(c.ask("Favorites", Value::obj().done()).get("items"), Some(&custom));
    drop(c);
    drop(daemon);
    assert_eq!(std::fs::read_to_string(stderr).unwrap(), format!("pathd listening on {}\n", socket.display()), "daemon startup and execution must not emit unexpected errors");
    std::fs::remove_dir_all(sandbox).unwrap();
}
