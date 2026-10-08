use pathd::config;

#[test]
fn shortcut_footer_is_enabled_by_default_and_explicit_false_is_preserved() {
    let dir = std::env::temp_dir().join(format!("path-core-defaults-{}", std::process::id()));
    std::fs::create_dir(&dir).unwrap();
    std::env::set_var("PATHFM_CONFIG_DIR", &dir);
    let defaults = config::settings();
    let default_enabled = defaults.get("view").unwrap().get("shortcutChips").unwrap().as_bool();
    std::fs::write(dir.join("settings.toml"), "[view]\nshortcutChips = false\n").unwrap();
    let explicit = config::settings();
    let explicit_enabled = explicit.get("view").unwrap().get("shortcutChips").unwrap().as_bool();
    std::fs::remove_dir_all(&dir).unwrap();
    assert_eq!(default_enabled, Some(true), "the shortcut footer must be enabled without a saved preference");
    assert_eq!(explicit_enabled, Some(false), "an explicit user preference must be preserved");
}
