// SPDX-License-Identifier: MIT

use super::*;

#[test]
fn package_metadata_is_available_to_the_about_page() {
    assert_eq!(DISPLAY_VERSION, "2.0");
    assert_eq!(COMMIT, "ENTER_COMMIT_HERE");
    assert_eq!(REPOSITORY, "https://github.com/ChrisTitusTech/Path");
    assert_eq!(AUTHOR, "Chris Titus Tech");
}

/// The default `RELEASE_TAG` injected by `build.rs` (no `PATHFM_RELEASE_TAG`
/// override, i.e. every developer build and this test run) must be a
/// well-formed tag the release-channel grammar accepts.
#[test]
fn default_release_tag_parses_to_a_version() {
    assert!(
        crate::services::Version::parse(RELEASE_TAG).is_some(),
        "expected {RELEASE_TAG:?} to parse as a Version"
    );
}

/// A developer build has no `PATHFM_BUILD_KIND` override, so it must
/// report itself as `Stable` -- the fallback that keeps a build unable to
/// identify itself from silently claiming to be a preview.
#[test]
fn developer_build_reports_stable_build_kind() {
    assert_eq!(build_kind(), BuildKind::Stable);
}

/// For a default build, `installed_version()` parses `RELEASE_TAG`
/// (`v{CARGO_PKG_VERSION}`), which must agree with `VERSION`
/// (`CARGO_PKG_VERSION` itself) once rendered back out.
#[test]
fn installed_version_agrees_with_version_for_a_default_build() {
    assert_eq!(installed_version().to_string(), VERSION);
}
