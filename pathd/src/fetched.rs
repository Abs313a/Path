use crate::json::Value;
use crate::vfs::uri::Uri;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

/// Where fetched copies go: `<cache>/open` — `~/.cache/path/open`, or wherever `PATHFM_CACHE_DIR`
/// says (a checkout's run keeps its own).
pub fn cache_dir() -> Result<PathBuf, String> {
    let dir = crate::config::cache_dir().join("open");
    std::fs::create_dir_all(&dir).map_err(|e| format!("{}: {e}", dir.display()))?;
    Ok(dir)
}

/// Brings `uris` (remote, all of them) to a folder of the moment: the copy job's id, and where
/// each will be once it is done, in the order given.
pub fn bring(uris: &[Uri]) -> Result<(u64, Vec<PathBuf>), String> {
    let moment = SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_millis()).unwrap_or(0);
    let mut dir = cache_dir()?.join(moment.to_string());
    let mut n = 0;
    while dir.exists() {
        n += 1;
        dir = dir.with_file_name(format!("{moment}-{n}"));
    }
    std::fs::create_dir_all(&dir).map_err(|e| format!("{}: {e}", dir.display()))?;
    let locals: Vec<PathBuf> = uris.iter().map(|u| dir.join(u.name())).collect();
    // Hidden: the window that asked shows the fetch's progress itself, and a copy into the
    // cache is nothing to toast about or to undo (it showed as "Copy X to 1790392334311 · Undo").
    let op = Value::obj().s("op", "copy").v("items", Value::Arr(uris.iter().map(|u| Value::Str(u.to_string())).collect())).s("dest", Uri::from_path(&dir).to_string()).b("_silent", true).done();
    let job = crate::jobs::submit(op, None).map_err(|(_, m)| m)?;
    Ok((job, locals))
}

/// At the daemon's start: whatever a previous life fetched goes.
pub fn clear() {
    let Ok(dir) = cache_dir() else { return };
    let Ok(entries) = std::fs::read_dir(&dir) else { return };
    for e in entries.flatten() {
        let _ = std::fs::remove_dir_all(e.path());
    }
}

#[cfg(test)]
mod tests {
    /// `PATHFM_CACHE_DIR` moves the copies with the rest of the cache: what `make run` sets so a
    /// checkout never writes into the installed path's folders.
    #[test]
    fn the_copies_follow_the_cache_directory() {
        let d = std::env::temp_dir().join(format!("path-fetched-{}", std::process::id()));
        std::env::set_var("PATHFM_CACHE_DIR", &d);
        assert_eq!(super::cache_dir().unwrap(), d.join("open"));
        std::env::remove_var("PATHFM_CACHE_DIR");
        let _ = std::fs::remove_dir_all(&d);
    }
}
