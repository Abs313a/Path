#!/usr/bin/env bash
# Installs Path from the latest GitHub release or local package:
#
#   curl -fsSL https://raw.githubusercontent.com/Abs313a/Path/main/install.sh | bash
#
# It downloads the package built for this machine's architecture, verifies sha256,
# and installs via the native package manager (pacman or dnf/rpm).
# If no prebuilt binary is published for the system, it builds and installs from source.
#
#   PATHFM_VERSION=v0.2.2 ...             install that release rather than the latest
#   PATHFM_PACKAGE=/path/to/pkg ...       install a package already on disk (.rpm or .pkg.tar.zst)
set -euo pipefail

repo="Abs313a/Path"
api="https://api.github.com/repos/${repo}/releases"

say() { printf ':: %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

if command -v dnf >/dev/null; then
  PKG_MGR="dnf"
elif command -v rpm >/dev/null; then
  PKG_MGR="rpm"
elif command -v pacman >/dev/null; then
  PKG_MGR="pacman"
else
  PKG_MGR="source"
fi

command -v curl >/dev/null || die "curl is needed to fetch the release."

arch="$(uname -m)"
case "$arch" in
  x86_64|aarch64) ;;
  *) die "no Path package is supported for ${arch} (x86_64 and aarch64 are)." ;;
esac

as_root() { if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo "$@"; fi; }

install_package() {
  local pkg="$1"
  if [[ "$pkg" == *.rpm ]]; then
    if [ "$PKG_MGR" = "dnf" ]; then
      as_root dnf install -y "$pkg"
    else
      as_root rpm -Uvh --replacepkgs "$pkg"
    fi
    return
  fi

  if command -v pacman >/dev/null; then
    if ( : </dev/tty ) 2>/dev/null; then
      as_root pacman -U --needed "$pkg" </dev/tty
    else
      as_root pacman -U --needed --noconfirm "$pkg"
    fi
    pacman -Q path >/dev/null 2>&1 || die "pacman did not install path."
  else
    die "cannot install ${pkg}: pacman not available on this system."
  fi
}

install_from_source() {
  say "building Path from source..."
  command -v cargo >/dev/null || die "cargo is required to build from source. Install rust/cargo first."
  command -v make >/dev/null || die "make is required to build from source."

  local src_dir
  if [ -f "Cargo.toml" ] && grep -q 'members = \["pathd"' "Cargo.toml" 2>/dev/null; then
    src_dir="$PWD"
  else
    src_dir="$(mktemp -d)"
    trap 'rm -rf "$src_dir"' EXIT
    say "cloning Path repository..."
    git clone --depth 1 "https://github.com/${repo}.git" "$src_dir"
  fi

  say "building release binaries..."
  ( cd "$src_dir" && cargo build --release && as_root make install PREFIX=/usr )
  say "done. Path is installed, and 'pathfm' starts it."
}

if [ -n "${PATHFM_PACKAGE:-}" ]; then
  [ -f "$PATHFM_PACKAGE" ] || die "${PATHFM_PACKAGE}: no such file"
  say "installing ${PATHFM_PACKAGE}"
  install_package "$PATHFM_PACKAGE"
  say "done. Path is in the launcher, and 'pathfm' starts it."
  exit 0
fi

# Query GitHub Releases
if [ -n "${PATHFM_VERSION:-}" ]; then
  tag="${PATHFM_VERSION}"; [ "${tag#v}" = "$tag" ] && tag="v${tag}"
  release_url="${api}/tags/${tag}"
else
  release_url="${api}/latest"
fi

json="$(curl -fsSL -H 'Accept: application/vnd.github+json' "$release_url" 2>/dev/null || true)"
tag="$(printf '%s' "$json" | sed -n 's/^  "tag_name": "\(.*\)",$/\1/p' | head -1)"

if [ -z "$tag" ]; then
  say "no published release found; falling back to source build."
  install_from_source
  exit 0
fi

version="${tag#v}"
base="https://github.com/${repo}/releases/download/${tag}"

# Determine target asset name by package manager
if [ "$PKG_MGR" = "dnf" ] || [ "$PKG_MGR" = "rpm" ]; then
  file="path-${version}-1.${arch}.rpm"
elif [ "$PKG_MGR" = "pacman" ]; then
  file="path-${version}-1-${arch}.pkg.tar.zst"
else
  file=""
fi

tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

if [ -n "$file" ] && curl -fsSL -o "${tmp}/${file}" "${base}/${file}" 2>/dev/null; then
  say "fetching checksum for ${file}"
  if curl -fsSL -o "${tmp}/${file}.sha256" "${base}/${file}.sha256" 2>/dev/null; then
    want="$(cut -d' ' -f1 "${tmp}/${file}.sha256")"
    have="$(sha256sum "${tmp}/${file}" | cut -d' ' -f1)"
    [ "$want" = "$have" ] || die "checksum mismatch for ${file}: expected ${want}, got ${have}"
  fi
  say "installing ${file}..."
  install_package "${tmp}/${file}"
  say "done. Path ${version} is in the launcher, and 'pathfm' starts it."
else
  say "no prebuilt package for ${PKG_MGR} (${arch}) found in release ${tag}."
  install_from_source
fi
