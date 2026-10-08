use crate::json::Value;
use crate::kinds::Kind;
use crate::listing;
use crate::vfs::uri::Uri;
use crate::vfs::VfsError;
use std::time::Duration;

#[derive(Clone)]
pub struct Node {
    pub uri: Uri,
    pub name: String,
    pub kind: Kind,
    pub is_dir: bool,
    pub depth: u32,
    pub expanded: bool,
    pub git: Option<crate::git::Entry>,
}

pub struct Tree {
    pub root: Uri,
    pub nodes: Vec<Node>, // flattened, visible order
    pub filter: String,
    pub visible: Vec<usize>,
}

fn children_of(uri: &Uri) -> Result<Vec<Node>, VfsError> {
    let (l, _) = listing::open(uri)?;
    if !listing::wait_scan(&l, Duration::from_secs(10)) {
        return Err(VfsError::said(1280, &[], "listing timed out"));
    }
    let w = l.window(0, 0, 0, 100_000, None);
    let rows: Vec<Value> = w.get("rows").and_then(Value::as_arr).map(|a| a.to_vec()).unwrap_or_default();
    let dir = if uri.is_local() { Some(uri.to_path()) } else { None };
    Ok(rows
        .iter()
        .filter(|r| r.str_field("name") != Some(".git"))
        .map(|r| {
            let name = r.str_field("name").unwrap_or("").to_string();
            let is_dir = r.get("isDir").and_then(Value::as_bool).unwrap_or(false);
            let git = r.get("git").filter(|g| !matches!(g, Value::Null)).map(|g| crate::git::Entry {
                state: match g.str_field("state") {
                    Some("modified") => crate::git::State::Modified,
                    Some("added") => crate::git::State::Added,
                    Some("deleted") => crate::git::State::Deleted,
                    Some("renamed") => crate::git::State::Renamed,
                    Some("conflicted") => crate::git::State::Conflicted,
                    Some("untracked") => crate::git::State::Untracked,
                    Some("ignored") => crate::git::State::Ignored,
                    _ => crate::git::State::Clean,
                },
                staged: g.get("staged").and_then(Value::as_bool).unwrap_or(false),
            });
            let git = git.or_else(|| dir.as_ref().and_then(|d| crate::git::state_for(d, &name, is_dir)));
            Node {
                uri: uri.join(&name),
                name,
                kind: Kind::from_u8(match r.str_field("kind") {
                    Some("folder") => 0,
                    Some("image") => 3,
                    Some("video") => 4,
                    Some("audio") => 5,
                    Some("document") => 6,
                    Some("pdf") => 7,
                    Some("text") => 8,
                    Some("code") => 9,
                    Some("archive") => 10,
                    Some("link") => 2,
                    _ => 1,
                }),
                is_dir,
                depth: 0,
                expanded: false,
                git,
            }
        })
        .collect())
}

impl Tree {
    pub fn open(root: &Uri) -> Result<Tree, VfsError> {
        let mut nodes = children_of(root)?;
        for n in &mut nodes {
            n.depth = 0;
        }
        let mut t = Tree { root: root.clone(), nodes, filter: String::new(), visible: Vec::new() };
        t.refilter();
        Ok(t)
    }

    pub fn expand(&mut self, row: usize, expanded: bool) -> Result<(), VfsError> {
        let idx = *self.visible.get(row).ok_or(VfsError::NotFound)?;
        let node = self.nodes[idx].clone();
        if !node.is_dir || node.expanded == expanded {
            return Ok(());
        }
        if expanded {
            let mut kids = children_of(&node.uri)?;
            for k in &mut kids {
                k.depth = node.depth + 1;
            }
            self.nodes[idx].expanded = true;
            let n = kids.len();
            self.nodes.splice(idx + 1..idx + 1, kids);
            let _ = n;
        } else {
            let end = self.nodes[idx + 1..].iter().position(|n| n.depth <= node.depth).map(|p| idx + 1 + p).unwrap_or(self.nodes.len());
            self.nodes.drain(idx + 1..end);
            self.nodes[idx].expanded = false;
        }
        self.refilter();
        Ok(())
    }

    pub fn set_filter(&mut self, text: &str) {
        self.filter = text.to_ascii_lowercase();
        self.refilter();
    }

    fn refilter(&mut self) {
        if self.filter.is_empty() {
            self.visible = (0..self.nodes.len()).collect();
            return;
        }
        // Matching rows plus their ancestors.
        let mut keep = vec![false; self.nodes.len()];
        for i in 0..self.nodes.len() {
            if self.nodes[i].name.to_ascii_lowercase().contains(&self.filter) {
                keep[i] = true;
                let mut d = self.nodes[i].depth;
                let mut j = i;
                while d > 0 && j > 0 {
                    j -= 1;
                    if self.nodes[j].depth < d {
                        keep[j] = true;
                        d = self.nodes[j].depth;
                    }
                }
            }
        }
        self.visible = keep.iter().enumerate().filter(|(_, k)| **k).map(|(i, _)| i).collect();
    }

    /// Expands ancestors so `uri` is visible; returns its visible row.
    pub fn reveal(&mut self, uri: &Uri) -> Result<usize, VfsError> {
        let rel = uri.path.strip_prefix(&self.root.path).ok_or(VfsError::NotFound)?.trim_start_matches('/').to_string();
        let parts: Vec<&str> = rel.split('/').filter(|s| !s.is_empty()).collect();
        let mut cur_depth = 0;
        let mut search_from = 0;
        let mut found = 0;
        for (i, part) in parts.iter().enumerate() {
            let idx = self.nodes.iter().enumerate().skip(search_from).find(|(_, n)| n.depth == cur_depth && n.name == *part).map(|(i, _)| i).ok_or(VfsError::NotFound)?;
            found = idx;
            if i + 1 < parts.len() {
                if !self.nodes[idx].expanded {
                    let row = self.visible.iter().position(|&v| v == idx).ok_or(VfsError::NotFound)?;
                    self.expand(row, true)?;
                }
                cur_depth += 1;
                search_from = idx + 1;
            }
        }
        self.visible.iter().position(|&v| v == found).ok_or(VfsError::NotFound)
    }

    pub fn row_json(&self, row: usize) -> Option<Value> {
        let n = self.nodes.get(*self.visible.get(row)?)?;
        let rel = n.uri.path.strip_prefix(&self.root.path).unwrap_or("").trim_start_matches('/');
        Some(
            Value::obj()
                .s("name", n.name.clone())
                .s("kind", n.kind.as_str())
                .b("isDir", n.is_dir)
                .b("isLink", n.kind == Kind::Link)
                .v("meta", Value::Null)
                .v("thumb", Value::Null)
                .v("git", n.git.as_ref().map(crate::git::entry_json).unwrap_or(Value::Null))
                .u("depth", n.depth as u64)
                .v("expanded", if n.is_dir { Value::Bool(n.expanded) } else { Value::Null })
                .s("rel", rel)
                .s("uri", n.uri.to_string())
                .done(),
        )
    }
}

// ---------------------------------------------------------------- X11 arrangement (window manager managed)

pub fn pick_window(clients: &[Value], class: &str, pid: Option<u64>, taken: &[String]) -> Option<String> {
    let free = |c: &&Value| c.str_field("address").is_some_and(|a| !taken.iter().any(|t| t == a));
    let by_pid = clients.iter().filter(free).find(|c| pid.is_some_and(|p| p > 0) && c.u64_field("pid") == pid);
    let by_class = || clients.iter().filter(free).find(|c| !class.is_empty() && c.str_field("class") == Some(class));
    by_pid.or_else(by_class).and_then(|c| c.str_field("address").map(str::to_string))
}

/// Under pure X11, window layout is managed natively by dwm / window manager.
pub fn arrange(_windows: &[Value], _left_width: u32) -> Value {
    Value::obj().v("arranged", Value::Arr(vec![])).v("missing", Value::Arr(vec![])).done()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tree_expand_filter_reveal() {
        let d = std::env::temp_dir().join(format!("path-tree-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(d.join("src/vfs")).unwrap();
        std::fs::create_dir_all(d.join("docs")).unwrap();
        std::fs::write(d.join("src/main.rs"), b"").unwrap();
        std::fs::write(d.join("src/vfs/local.rs"), b"").unwrap();
        std::fs::write(d.join("README.md"), b"").unwrap();
        let mut t = Tree::open(&Uri::from_path(&d)).unwrap();
        assert_eq!(t.visible.len(), 3); // docs, src, README.md (folders first)
        assert_eq!(t.row_json(1).unwrap().str_field("name"), Some("src"));
        t.expand(1, true).unwrap();
        assert_eq!(t.visible.len(), 5);
        assert_eq!(t.row_json(2).unwrap().u64_field("depth"), Some(1));
        let row = t.reveal(&Uri::from_path(&d.join("src/vfs/local.rs"))).unwrap();
        assert_eq!(t.row_json(row).unwrap().str_field("name"), Some("local.rs"));
        assert_eq!(t.row_json(row).unwrap().str_field("rel"), Some("src/vfs/local.rs"));
        t.set_filter("local");
        assert_eq!(t.visible.len(), 3); // src, vfs, local.rs
        t.set_filter("");
        t.expand(1, false).unwrap();
        assert_eq!(t.visible.len(), 3);
        std::fs::remove_dir_all(&d).unwrap();
    }

    /// Project mode puts three windows side by side, and has to know which is which.
    #[test]
    fn a_window_is_found_by_pid_first_and_never_twice() {
        let client = |addr: &str, class: &str, pid: u64| Value::obj().s("address", addr).s("class", class).u("pid", pid).done();
        let clients = vec![client("0xa", "org.quickshell", 100), client("0xb", "path-tool-neovim", 200), client("0xc", "path-tool-claude", 300), client("0xd", "path-tool-claude", 301)];
        // path's own window has Quickshell's class: only the pid finds it.
        assert_eq!(pick_window(&clients, "", Some(100), &[]), Some("0xa".into()));
        assert_eq!(pick_window(&clients, "path", Some(0), &[]), None, "no pid and a class nobody has: not found, rather than the first window");
        // The pid is THE window, even when another shares its class.
        assert_eq!(pick_window(&clients, "path-tool-claude", Some(301), &[]), Some("0xd".into()));
        // A terminal that forks (its pid is not the window's) is found by its class instead…
        assert_eq!(pick_window(&clients, "path-tool-neovim", Some(999), &[]), Some("0xb".into()));
        // …and a window already given to one role is not given to another.
        assert_eq!(pick_window(&clients, "path-tool-claude", Some(999), &["0xc".to_string()]), Some("0xd".into()));
        assert_eq!(pick_window(&clients, "path-tool-claude", None, &["0xc".to_string(), "0xd".to_string()]), None);
    }
}
