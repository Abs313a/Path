use pathd::json::Value;
use pathd::listing::{self, Subscriber};
use pathd::vfs::uri::Uri;
use std::sync::mpsc;
use std::time::{Duration, Instant};

const PATIENCE: Duration = Duration::from_secs(5);

fn names(l: &std::sync::Arc<listing::Listing>) -> Vec<String> {
    let rows = l.window(1, 1, 0, 512, None);
    let mut n: Vec<String> = rows.get("rows").and_then(Value::as_arr).map(|a| a.to_vec()).unwrap_or_default().iter().filter_map(|r| r.str_field("name").map(str::to_string)).collect();
    n.sort();
    n
}

fn until(l: &std::sync::Arc<listing::Listing>, what: &str, want: &[&str]) {
    let since = Instant::now();
    while names(l) != want {
        assert!(since.elapsed() < PATIENCE, "{what}: the trash view still shows {:?}, not {want:?}", names(l));
        std::thread::sleep(Duration::from_millis(20));
    }
}

#[test]
fn the_trash_view_follows_the_trash() {
    let _guard = pathd::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    let dir = std::env::temp_dir().join(format!("path-trash-watch-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    for (k, d) in [("PATHFM_CONFIG_DIR", "config"), ("PATHFM_STATE_DIR", "state"), ("PATHFM_DATA_DIR", "data"), ("PATHFM_THUMB_DIR", "thumbs"), ("PATHFM_TRASH_DIR", "trash")] {
        std::env::set_var(k, dir.join(d));
    }
    let files = dir.join("trash/files");
    std::fs::create_dir_all(&files).unwrap();
    std::fs::create_dir_all(dir.join("trash/info")).unwrap();
    std::fs::write(files.join("old.txt"), b"x").unwrap();

    let (l, _) = listing::open(&Uri::parse("trash:///").unwrap()).unwrap();
    assert!(listing::wait_scan(&l, PATIENCE));
    // Somebody has to be looking, or nobody is told.
    let (tx, _rx) = mpsc::channel();
    l.subscribe(Subscriber { client: 1, lid: 1, tx, first: 0, count: 512, view_first: 0, view_count: 512 });
    until(&l, "as opened", &["old.txt"]);

    // Something else is thrown away while the view is open…
    std::fs::write(files.join("new.txt"), b"y").unwrap();
    until(&l, "a second file trashed", &["new.txt", "old.txt"]);
    // …and the trash is emptied.
    std::fs::remove_file(files.join("new.txt")).unwrap();
    std::fs::remove_file(files.join("old.txt")).unwrap();
    until(&l, "emptied", &[]);

    let _ = std::fs::remove_dir_all(&dir);
}
