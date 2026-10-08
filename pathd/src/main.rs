use pathd::server;

use std::os::unix::net::UnixListener;
use std::path::PathBuf;

fn main() {
    tune_allocator();
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("bench") => bench(&args[2..]),
        Some("--version") | Some("-V") => println!("pathd {}", env!("CARGO_PKG_VERSION")),
        Some("--help") | Some("-h") => println!("usage: pathd [bench gen|run|compare …]"),
        _ => serve(),
    }
}

fn serve() {
    let listener = match systemd_socket() {
        Some(l) => l,
        None => {
            let path = socket_path();
            if let Some(dir) = path.parent() {
                let _ = std::fs::create_dir_all(dir);
            }
            let _ = std::fs::remove_file(&path);
            let l = UnixListener::bind(&path).unwrap_or_else(|e| {
                eprintln!("bind {}: {e}", path.display());
                std::process::exit(1)
            });
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                let _ = std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o600));
            }
            eprintln!("pathd listening on {}", path.display());
            l
        }
    };
    pathd::dbus::start();
    pathd::fetched::clear();
    pathd::plugin::start_reaper();
    pathd::locations::migrate_option_labels();
    pathd::devices::start();
    std::thread::spawn(|| {
        std::thread::sleep(std::time::Duration::from_secs(30));
        pathd::index::start();
    });
    if let Err(e) = server::serve(listener) {
        eprintln!("serve: {e}");
        std::process::exit(1);
    }
}

fn socket_path() -> PathBuf {
    if let Ok(p) = std::env::var("PATHFM_SOCKET") {
        return PathBuf::from(p);
    }
    let dir = std::env::var("XDG_RUNTIME_DIR").unwrap_or_else(|_| format!("/tmp/path-{}", unsafe { libc::getuid() }));
    PathBuf::from(dir).join(pathd::config::socket_name())
}

/// systemd socket activation: LISTEN_FDS=1 with the listener on fd 3.
fn systemd_socket() -> Option<UnixListener> {
    use std::os::unix::io::FromRawFd;
    let pid: u32 = std::env::var("LISTEN_PID").ok()?.parse().ok()?;
    if pid != std::process::id() {
        return None;
    }
    let n: u32 = std::env::var("LISTEN_FDS").ok()?.parse().ok()?;
    if n < 1 {
        return None;
    }
    Some(unsafe { UnixListener::from_raw_fd(3) })
}

fn tune_allocator() {
    #[cfg(all(target_os = "linux", target_env = "gnu"))]
    unsafe {
        libc::mallopt(libc::M_MMAP_THRESHOLD, 131072);
        libc::mallopt(libc::M_ARENA_MAX, 2);
        libc::mallopt(libc::M_TRIM_THRESHOLD, 1024 * 1024);
    }
}

/// `pathd bench gen <profile> <dir>` | `bench run <dir> [--json out]` | `bench compare <base> <new> [--tolerance pct]` | `bench <dir>`
fn bench(args: &[String]) {
    let usage = || {
        eprintln!("usage: pathd bench gen <flat10k|flat200k|deep100k|photos|all> <dir>\n       pathd bench run <dir> [--json <out>]\n       pathd bench compare <baseline.json> <results.json> [--tolerance <pct>]");
        std::process::exit(2)
    };
    match args.first().map(String::as_str) {
        Some("gen") => {
            let (Some(profile), Some(dir)) = (args.get(1), args.get(2)) else { usage() };
            if let Err(e) = pathd::bench::gen(profile, &PathBuf::from(dir)) {
                eprintln!("gen: {e}");
                std::process::exit(1)
            }
        }
        Some("run") | Some(_) | None => {
            let dir = if args.first().map(String::as_str) == Some("run") { args.get(1) } else { args.first() };
            let dir = dir.map(PathBuf::from).unwrap_or_else(|| std::env::var("HOME").map(PathBuf::from).unwrap_or_else(|_| PathBuf::from("/")));
            if args.first().map(String::as_str) == Some("compare") {
                let (Some(b), Some(n)) = (args.get(1), args.get(2)) else { usage() };
                let tol: f64 = args.iter().position(|a| a == "--tolerance").and_then(|i| args.get(i + 1)).and_then(|t| t.parse().ok()).unwrap_or(25.0);
                let read = |p: &String| {
                    pathd::json::parse(&std::fs::read(p).unwrap_or_else(|e| {
                        eprintln!("{p}: {e}");
                        std::process::exit(1)
                    }))
                    .unwrap_or_else(|_| {
                        eprintln!("{p}: not JSON");
                        std::process::exit(1)
                    })
                };
                let regressions = pathd::bench::compare(&read(b), &read(n), tol);
                for (p, k, bv, nv) in &regressions {
                    println!("REGRESSION {p}.{k}: {bv} -> {nv} (+{:.0}%)", (nv / bv - 1.0) * 100.0);
                }
                if regressions.is_empty() {
                    println!("no regressions beyond {tol}%");
                } else {
                    std::process::exit(1)
                }
                return;
            }
            let v = pathd::bench::run(&dir);
            pathd::bench::print_table(&v);
            if let Some(out) = args.iter().position(|a| a == "--json").and_then(|i| args.get(i + 1)) {
                if let Err(e) = std::fs::write(out, pathd::json::to_string(&v)) {
                    eprintln!("{out}: {e}");
                    std::process::exit(1)
                }
                eprintln!("wrote {out}");
            }
        }
    }
}
