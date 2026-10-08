mod common;

use pathd::listing;
use pathd::vfs::uri::Uri;
use std::time::{Duration, Instant};

fn settled(l: &std::sync::Arc<listing::Listing>, timeout: Duration) -> bool {
    let start = Instant::now();
    while start.elapsed() < timeout {
        if l.count().1 {
            return true;
        }
        std::thread::sleep(Duration::from_millis(20));
    }
    false
}

#[test]
fn a_remote_folder_opens_at_once_and_a_bad_host_fails_by_number_on_the_scan() {
    let dir = common::setup("remote-open");
    common::save_location("lab");

    // A location that exists: `open` comes back before the plugin has answered anything.
    let start = Instant::now();
    let (l, cached) = listing::open(&Uri::parse("stub://lab/docs").unwrap()).unwrap();
    assert!(start.elapsed() < Duration::from_millis(200), "open waited for the server: {:?}", start.elapsed());
    assert!(!cached);
    assert!(settled(&l, Duration::from_secs(20)), "the scan never finished");
    assert!(l.error().is_none(), "{:?}", l.error());
    assert!(l.count().0 > 0, "the stub's folder has files");

    // A host nobody knows: still an immediate open, and the scan says 1260 with the host.
    let (l, _) = listing::open(&Uri::parse("nosuch://server/made-up").unwrap()).unwrap();
    assert!(settled(&l, Duration::from_secs(20)));
    let said = l.error_said().expect("said by number");
    assert_eq!(said.0, 1260, "{:?}", said);
    assert!(l.error().unwrap().contains("no location for nosuch://server"), "{:?}", l.error());

    let _ = std::fs::remove_dir_all(&dir);
}
