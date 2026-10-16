# Source0 and Source1 are prepared from an immutable commit by make_srpm.py.
%global debug_package %{nil}
Name:           path
Version:        1.0.0
Release:        1%{?path_commit:.git%{path_commit}}%{?dist}
Summary:        Keyboard-first GTK4 file manager
License:        MIT AND LicenseRef-UnRAR
URL:            https://github.com/ChrisTitusTech/Path
Source0:        path-%{version}.tar.gz
Source1:        path-%{version}-vendor.tar.gz
Source2:        bundled-rust-provides.inc
ExclusiveArch:  x86_64
%include %{SOURCE2}

BuildRequires:  cargo
BuildRequires:  rust
BuildRequires:  gcc-c++
BuildRequires:  make
BuildRequires:  python3
BuildRequires:  pkgconfig(gtk4) >= 4.12
BuildRequires:  pkgconfig(gtksourceview-5)
BuildRequires:  pkgconfig(poppler-glib)
BuildRequires:  pkgconfig(gstreamer-1.0) >= 1.20
BuildRequires:  pkgconfig(gstreamer-app-1.0)
BuildRequires:  pkgconfig(fontconfig)
BuildRequires:  desktop-file-utils
Requires:       bubblewrap
Requires:       gvfs
Requires:       xdg-desktop-portal
Requires:       xdg-desktop-portal-gtk
Recommends:     gvfs-smb
Recommends:     gstreamer1-plugins-good

%description
Path provides column, icon and list views, file previews, keyboard navigation,
and local and GIO-backed file operations. Folder association and file chooser
integration remain user choices.

%prep
%autosetup -n path-%{version}
tar -xzf %{SOURCE1}

%build
export CARGO_BUILD_JOBS=%{_smp_build_ncpus}
cargo metadata --offline --locked --format-version 1 --filter-platform x86_64-unknown-linux-gnu > bundled-metadata.json
# Revision-pinned auxiliary notices (including poppler-rs/sys 0.26.0 MIT)
# are bundled from packaging/fedora/license-supplements without editing vendor.
python3 packaging/fedora/license_bundle.py bundled-metadata.json vendor target/license-bundle
cmp target/license-bundle/LICENSE-EXPRESSION packaging/fedora/license-expression.txt
cmp target/license-bundle/BUNDLED-PROVIDES.inc %{SOURCE2}
cargo build --release --frozen

%install
make install PREFIX=%{_prefix} DESTDIR=%{buildroot}
install -Dm644 packaging/fedora/install-source.toml %{buildroot}%{_datadir}/pathfm/install-source.toml

%check
cargo test --frozen services::install_source::tests
desktop-file-validate %{buildroot}%{_datadir}/applications/pathfm.desktop
python3 tests/branding_check.py

%files
%license %{_datadir}/licenses/pathfm/ target/license-bundle
%doc README.md SOURCE-COMMIT
%{_bindir}/pathfm
%{_datadir}/applications/pathfm.desktop
%{_datadir}/icons/hicolor/512x512/apps/pathfm.png
%{_datadir}/icons/hicolor/512x512/apps/io.github.christitustech.Path.png
%{_datadir}/pathfm/
%{_datadir}/dbus-1/services/org.freedesktop.impl.portal.desktop.pathfm.service
%{_datadir}/xdg-desktop-portal/portals/pathfm.portal
