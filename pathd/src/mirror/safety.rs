//! Validate untrusted relative names before joining them to either transfer root.
use super::*;
use std::fs::{File, OpenOptions};
use std::os::fd::AsRawFd;
use std::os::unix::fs::OpenOptionsExt;

pub(crate) fn validate_rel(rel: &str) -> Result<(), VfsError> {
    if rel.contains('\0') || rel.split('/').any(|c| c.is_empty() || c == "." || c == "..") {
        return Err(VfsError::Io(format!("unsafe relative transfer path: {rel:?}")));
    }
    Ok(())
}

pub(crate) fn validate_name(name: &str) -> Result<(), VfsError> {
    validate_rel(name)?;
    if name.contains('/') {
        return Err(VfsError::Io(format!("unsafe remote entry name: {name:?}")));
    }
    Ok(())
}

/// Keep the parent open while operating on its leaf. Each untrusted directory component is
/// opened without following symlinks. Linux's fd path keeps subsequent operations anchored to
/// that directory even if its original pathname is replaced with a symlink during a transfer.
pub(crate) struct LocalPath {
    _parent: File,
    pub path: PathBuf,
}

pub(crate) fn local_path(root: &Path, rel: &str) -> Result<LocalPath, VfsError> {
    validate_rel(rel)?;
    let directory = |p: &Path| OpenOptions::new().read(true).custom_flags(libc::O_DIRECTORY | libc::O_NOFOLLOW | libc::O_CLOEXEC).open(p);
    let mut parent = directory(root)?;
    let mut parts = rel.split('/').peekable();
    while let Some(part) = parts.next() {
        let path = PathBuf::from(format!("/proc/self/fd/{}", parent.as_raw_fd())).join(part);
        if parts.peek().is_none() {
            return Ok(LocalPath { _parent: parent, path });
        }
        parent = directory(&path)?;
    }
    unreachable!("validated nonempty relative path")
}

pub(crate) fn open_source(path: &Path) -> Result<File, VfsError> {
    let file = OpenOptions::new().read(true).custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK).open(path)?;
    if !file.metadata()?.is_file() {
        return Err(VfsError::Io("transfer source is not a regular file".into()));
    }
    Ok(file)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn remote_paths_must_be_nonempty_normal_components() {
        for rel in ["", "/tmp/x", "../x", "a/../../x", "a/./b", "a//b", "a/", "a\0b"] {
            assert!(validate_rel(rel).is_err(), "{rel:?}");
        }
        for rel in ["a", "a/b", "space and 'quotes'", "a\\b"] {
            assert!(validate_rel(rel).is_ok(), "{rel:?}");
        }
        assert!(validate_name("a/b").is_err());
    }

    #[test]
    fn parent_symlinks_are_rejected_and_open_parents_stay_pinned() {
        let root = tempfile::tempdir().unwrap();
        let outside = tempfile::tempdir().unwrap();
        std::os::unix::fs::symlink(outside.path(), root.path().join("escape")).unwrap();
        assert!(local_path(root.path(), "escape/victim").is_err());
        std::fs::create_dir(root.path().join("safe")).unwrap();
        let held = local_path(root.path(), "safe/file").unwrap();
        std::fs::rename(root.path().join("safe"), root.path().join("moved")).unwrap();
        std::os::unix::fs::symlink(outside.path(), root.path().join("safe")).unwrap();
        std::fs::write(&held.path, b"safe").unwrap();
        assert!(!outside.path().join("file").exists());
        assert_eq!(std::fs::read(root.path().join("moved/file")).unwrap(), b"safe");
    }
}
