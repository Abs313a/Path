# Development RPM for Fedora 44; not a published release or Fedora submission.
# Source0 is a snapshot of the reviewed Path tree, Source1 is cargo vendor --locked.
# The bundled-license expression and Provides are checked against the offline Cargo graph.
%global debug_package %{nil}

Name:           path
Version:        0.2.2
Release:        0.2%{?dist}
Summary:        Light, practical file manager with a Quickshell interface
License:        ((MIT OR Apache-2.0) AND Unicode-3.0) AND (0BSD OR MIT OR Apache-2.0) AND Apache-2.0 AND (Apache-2.0 AND ISC) AND (Apache-2.0 OR ISC OR MIT) AND (Apache-2.0 OR MIT) AND (Apache-2.0 WITH LLVM-exception) AND (Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT) AND (BSD-2-Clause OR Apache-2.0 OR MIT) AND BSD-3-Clause AND (BSD-3-Clause OR Apache-2.0) AND CDLA-Permissive-2.0 AND ISC AND MIT AND (MIT OR Apache-2.0) AND (MIT OR Apache-2.0 OR Zlib) AND (MIT OR Zlib OR Apache-2.0) AND (Unlicense OR MIT) AND Zlib AND (Zlib OR Apache-2.0 OR MIT)
URL:            https://github.com/Abs313a/Path
Source0:        path-%{version}.tar.gz
Source1:        path-%{version}-vendor.tar.gz
Source2:        bundled-rust-provides.inc
ExclusiveArch:  x86_64
%include %{SOURCE2}

BuildRequires:  cargo
BuildRequires:  rust
BuildRequires:  gcc
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  python3
BuildRequires:  desktop-file-utils
BuildRequires:  systemd-rpm-macros

Requires:       quickshell
Requires:       qt6-qtdeclarative
Requires:       qt6-qtmultimedia
Requires:       xdg-desktop-portal
Requires:       xdg-desktop-portal-gtk
Requires:       gnome-keyring
Requires:       libsecret
Requires:       bsdtar
Requires:       udisks2
Requires:       git
Requires:       poppler-utils
Requires:       gvfs
Requires:       /usr/bin/ffmpeg
Requires:       /usr/bin/ffprobe
Recommends:     gvfs-smb
Recommends:     openssh-clients

%description
Path provides list, icon, column and gallery views, file previews, and SFTP,
FTPS and SMB locations. Its Rust daemon starts on demand through a user socket.
Desktop integration is opt-in; installation does not select a folder handler
or replace the user's file chooser preferences.

%prep
%autosetup -n path-%{version}
tar -xzf %{SOURCE1}
mkdir -p .cargo
cat > .cargo/config.toml <<'EOF'
[source.crates-io]
replace-with = "vendored-sources"
[source.vendored-sources]
directory = "vendor"
EOF

%build
export CARGO_BUILD_JOBS=%{_smp_build_ncpus}
export CARGO_TARGET_DIR="${PATHFM_RPM_TARGET_DIR:-target}"
cargo metadata --offline --locked --format-version 1 --filter-platform x86_64-unknown-linux-gnu > bundled-metadata.json
python3 packaging/fedora/license_bundle.py bundled-metadata.json vendor target/license-bundle
cmp target/license-bundle/LICENSE-EXPRESSION packaging/fedora/license-expression.txt
cmp target/license-bundle/BUNDLED-PROVIDES.inc %{SOURCE2}
cargo build --release --frozen

%install
install -Dm755 "${PATHFM_RPM_TARGET_DIR:-target}/release/pathd" %{buildroot}%{_bindir}/pathd
install -Dm755 packaging/bin/pathfm %{buildroot}%{_bindir}/pathfm
# Application-private executable paths currently form Path's runtime contract.
# Do not substitute _libdir (lib64 on Fedora) without adapting discovery first.
install -Dm755 "${PATHFM_RPM_TARGET_DIR:-target}/release/path-thumber" %{buildroot}/usr/lib/path/path-thumber
for plugin in sftp ftps dbus share-mail share-tailscale; do
    install -Dm755 "${PATHFM_RPM_TARGET_DIR:-target}/release/path-plugin-$plugin" "%{buildroot}/usr/lib/path/plugins/path-plugin-$plugin"
done
install -Dm755 "${PATHFM_RPM_TARGET_DIR:-target}/release/path-plugin-gio" %{buildroot}/usr/lib/path/plugins/path-plugin-smb
install -d %{buildroot}%{_datadir}/path
cp -a qml/. %{buildroot}%{_datadir}/path/
install -Dm644 packaging/systemd/pathd.service %{buildroot}%{_userunitdir}/pathd.service
install -d %{buildroot}%{_userunitdir}
sed 's/@VERSION@/%{version}/g' packaging/systemd/pathfm.socket > %{buildroot}%{_userunitdir}/pathfm.socket
install -Dm644 packaging/pathfm.desktop %{buildroot}%{_datadir}/applications/pathfm.desktop
install -Dm644 app-images/path-app-list.png %{buildroot}%{_datadir}/icons/hicolor/512x512/apps/pathfm.png
install -Dm644 packaging/org.freedesktop.impl.portal.desktop.pathfm.service %{buildroot}%{_datadir}/dbus-1/services/org.freedesktop.impl.portal.desktop.pathfm.service
install -Dm644 packaging/path.portal %{buildroot}%{_datadir}/xdg-desktop-portal/portals/path.portal

%check
export CARGO_BUILD_JOBS=%{_smp_build_ncpus}
export CARGO_TARGET_DIR="${PATHFM_RPM_TARGET_DIR:-target}"
cargo test --frozen
python3 tests/branding_check.py
python3 tests/packaging_hooks_check.py
python3 tests/fedora_packaging_check.py
python3 tests/fedora_license_check.py
python3 tests/i18n_check.py
python3 tests/version_check.py
desktop-file-validate %{buildroot}%{_datadir}/applications/pathfm.desktop

%post
%systemd_user_post pathfm.socket

%preun
%systemd_user_preun pathfm.socket pathd.service

%postun
%systemd_user_postun pathfm.socket pathd.service

%files
%license LICENSE target/license-bundle
%doc README.md
%{_bindir}/pathd
%{_bindir}/pathfm
/usr/lib/path/
%{_datadir}/path/
%{_userunitdir}/pathd.service
%{_userunitdir}/pathfm.socket
%{_datadir}/applications/pathfm.desktop
%{_datadir}/icons/hicolor/512x512/apps/pathfm.png
%{_datadir}/dbus-1/services/org.freedesktop.impl.portal.desktop.pathfm.service
%{_datadir}/xdg-desktop-portal/portals/path.portal
