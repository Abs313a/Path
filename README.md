# Path

**Path** (`pathfm`) is a fast, responsive, and modular X11 file manager for Linux. It combines a lightweight, multi-threaded Rust backend daemon (`pathd`) with a smooth, declarative Qt6/QML frontend powered by [Quickshell](https://quickshell.outfoxxed.me/).

---

## Highlights

* **Native X11 Integration:** Designed specifically for traditional and tiling X11 window managers (`dwm`, `i3`, `bspwm`, `awesome`, `xmonad`, `xfce`, etc.) with full EWMH/ICCCM support, standard clipboard (`xclip`), and window raising (`xdotool`).
* **Decoupled Architecture:** Heavy filesystem operations, background transfers, file indexing, and protocol drivers run asynchronously in `pathd`, keeping the graphical user interface fluid and responsive.
* **Extensible Protocol Plugins:** First-class plugin system supporting remote protocols and transports:
  * **SFTP** (SSH File Transfer Protocol)
  * **FTPS** (Explicit & Implicit TLS FTP)
  * **GIO / GVFS** (Network mounts, SMB, WebDAV)
  * Custom Rust plugin SDK (`crates/path-plugin-sdk`)
* **XDG Desktop Portal Provider:** Implements `org.freedesktop.impl.portal.FileChooser` (`path.portal`), allowing desktop applications to use Path as their native file chooser.
* **Modern Desktop Conveniences:** Interactive breadcrumbs, instant search/filtering, thumbnail caching, and integrated quick preview inspection.

---

## Architecture Overview

```
┌──────────────────────────────────────────┐
│      Quickshell / Qt6 UI (pathfm)       │  <── Client layer (QML / X11)
└────────────────────┬─────────────────────┘
                     │ UNIX Domain Socket
┌────────────────────▼─────────────────────┐
│           pathd (Rust Daemon)            │  <── Core service & worker pool
└────────┬─────────────────────────┬───────┘
         │                         │
┌────────▼────────┐       ┌────────▼───────┐
│ System Storage  │       │ Plugin Drivers │  <── SFTP / FTPS / GIO / SMB
└─────────────────┘       └────────────────┘
```

---

## Dependencies

### Runtime
* **X11 Utilities:** `xclip`, `xdotool`
* **Qt6 Libraries:** `qt6-base`, `qt6-declarative`, `qt6-svg`, `qt6-multimedia`
* **Shell Framework:** `quickshell`
* **Desktop Integration:** `xdg-desktop-portal`, `dbus`, `hicolor-icon-theme`

### Build Dependencies
* `rust` & `cargo` (1.80+)
* `clang` & `pkgconf`
* `make`

---

## Installation

### Automatic Installer (`install.sh`)
The universal installer detects your distribution package manager (`dnf`, `pacman`) or compiles from source:

```bash
curl -fsSL https://raw.githubusercontent.com/Abs313a/Path/main/install.sh | bash
```

### Building from Source (`Makefile`)
Standard build and installation with GNU Make:

```bash
# Build daemon and plugins in release mode
make build

# Install to /usr (or PREFIX=/usr/local)
sudo make install PREFIX=/usr
```

To uninstall:
```bash
sudo make uninstall PREFIX=/usr
```

### Packaging Assets
* **Fedora / RHEL:** RPM spec file available at [`packaging/fedora/path.spec`](packaging/fedora/path.spec) for local `rpmbuild` or COPR repos.
* **Arch Linux:** `PKGBUILD` available in [`packaging/PKGBUILD`](packaging/PKGBUILD).

---

## Usage

Start Path via terminal, application launcher (`dmenu`, `rofi`, etc.), or desktop menu:

```bash
# Open home directory
pathfm

# Open a specific folder
pathfm /path/to/directory
```

### Daemon & Socket Activation
Path ships systemd user units for on-demand socket activation:

```bash
systemctl --user enable --now pathfm.socket
```

When activated, `pathd` automatically launches when a client connects or when the portal file chooser is invoked.

---

## Development & Testing

```bash
# Run linters and consistency checks
make lint

# Run Rust unit and integration test suite
make test-rust

# Run headless QML interaction tests
make test-qml
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
