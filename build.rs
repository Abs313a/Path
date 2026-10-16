use std::{env, fmt::Write as _, fs, path::Path};

fn main() {
    println!("cargo::rerun-if-changed=data/locales");
    write_translation_catalogs();
    glib_build_tools::compile_resources(&["data"], "data/pathfm.gresource.xml", "pathfm.gresource");

    println!("cargo::rerun-if-env-changed=PATHFM_BUILD_COMMIT");

    if let Some(commit) = env::var("PATHFM_BUILD_COMMIT")
        .ok()
        .and_then(|value| value.lines().next().map(str::trim).map(str::to_owned))
        .filter(|value| !value.is_empty())
    {
        println!("cargo::rustc-env=PATHFM_BUILD_COMMIT={commit}");
    }

    println!("cargo::rerun-if-env-changed=PATHFM_RELEASE_TAG");
    println!("cargo::rerun-if-env-changed=PATHFM_BUILD_KIND");

    let release_tag = env::var("PATHFM_RELEASE_TAG")
        .ok()
        .and_then(|value| value.lines().next().map(str::trim).map(str::to_owned))
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| format!("v{}", env!("CARGO_PKG_VERSION")));
    println!("cargo::rustc-env=PATHFM_RELEASE_TAG={release_tag}");

    let build_kind = env::var("PATHFM_BUILD_KIND")
        .ok()
        .and_then(|value| value.lines().next().map(str::trim).map(str::to_owned))
        .filter(|value| {
            matches!(
                value.as_str(),
                "stable" | "alpha" | "beta" | "rc" | "nightly"
            )
        })
        .unwrap_or_else(|| "stable".to_owned());
    println!("cargo::rustc-env=PATHFM_BUILD_KIND={build_kind}");
}

/// Embeds the catalogs as static tables. rust-i18n's own `i18n!` loader emits one
/// statement per message, and that unoptimized frame overflows 2 MiB thread stacks.
fn write_translation_catalogs() {
    let catalogs = rust_i18n_support::load_locales("data/locales", |_| false);
    // load_locales silently returns nothing when the catalog directory is absent.
    assert!(
        catalogs.contains_key("en"),
        "translation catalogs are missing from data/locales"
    );
    let mut source = String::from("pub(crate) static CATALOGS: &[(&str, &[(&str, &str)])] = &[\n");
    for (locale, messages) in &catalogs {
        writeln!(source, "({locale:?}, &[").expect("format catalog");
        for (key, text) in messages {
            writeln!(source, "({key:?}, {text:?}),").expect("format catalog");
        }
        source.push_str("]),\n");
    }
    source.push_str("];\n");
    let output = Path::new(&env::var_os("OUT_DIR").expect("OUT_DIR")).join("catalogs.rs");
    fs::write(output, source).expect("write translation catalogs");
}
