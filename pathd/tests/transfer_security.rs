//! Hostile remote listings and pre-planted local transfer symlinks, through a real plugin.
mod common;
use pathd::{locations, mirror, vfs::uri::Uri};
use std::os::unix::fs::PermissionsExt;
use std::sync::atomic::AtomicBool;

#[test]
fn remote_paths_and_temporary_downloads_are_confined() {
    let dir = common::setup("transfer-security");
    std::env::set_var("PATHFM_STUB_UNSAFE_SCAN", "1");
    common::save_location("lab");
    let (session, _) = locations::resolve(&Uri::parse("stub://lab/").unwrap()).unwrap();
    let cancel = AtomicBool::new(false);
    for root in ["/unsafe-recursive", "/unsafe-fallback"] {
        let side = mirror::Side::Remote(session.clone(), root.into());
        assert!(mirror::scan_side(&side, &[], &mut 0, &cancel).is_err());
    }
    let destination = tempfile::tempdir().unwrap();
    let victim = dir.join("victim");
    std::fs::write(&victim, b"preserve").unwrap();
    std::os::unix::fs::symlink(&victim, destination.path().join("notes.txt.path-part")).unwrap();
    std::os::unix::fs::symlink(&victim, destination.path().join("notes.txt")).unwrap();
    let source = mirror::Side::Remote(session.clone(), "/docs".into());
    let dest = mirror::Side::Local(destination.path().into());
    let ctx = mirror::ExecCtx { cancel: &cancel, workers: 1, on_change: &|_| {}, on_bytes: &|_| {}, exact_times: false };
    mirror::copy_file(&source, "notes.txt", &dest, "notes.txt", 5, 0, &ctx).unwrap();
    assert_eq!(std::fs::read(&victim).unwrap(), b"preserve");
    assert_eq!(std::fs::read(destination.path().join("notes.txt")).unwrap(), b"hello");
    assert_eq!(std::fs::metadata(destination.path().join("notes.txt")).unwrap().permissions().mode() & 0o777, 0o600);
    // The same-process remote pair uses an anonymous spool and reads back through its handle.
    let remote = mirror::Side::Remote(session, "/empty".into());
    mirror::copy_file(&source, "notes.txt", &remote, "relayed.txt", 5, 0, &ctx).unwrap();
    mirror::copy_file(&remote, "relayed.txt", &dest, "roundtrip.txt", 5, 0, &ctx).unwrap();
    assert_eq!(std::fs::read(destination.path().join("roundtrip.txt")).unwrap(), b"hello");
    std::fs::remove_dir_all(dir).unwrap();
}
