# Security remediation and Fedora validation

Public COPR publication remains unapproved. No package was submitted to COPR.
The target installation environments are Fedora 43 and Fedora 44, x86_64.

## Source fixes

- SFTP rejects an unknown host key during the handshake, before password,
  keyboard-interactive, or public-key authentication. The existing daemon trust
  prompt receives `Invalid/fingerprint`; confirmation reconnects with that exact
  fingerprint pinned. Known-host mismatches and changed pins fail closed.
- Recursive remote paths and individual directory-entry names are validated before
  use. Empty paths, absolute paths, NUL, and dot/dot-dot components are rejected.
  Copy, directory creation, rename, deletion, and source reads validate paths.
  Local parent directories are opened with `O_DIRECTORY | O_NOFOLLOW` and retained
  during operations through Linux `/proc/self/fd` paths. This also rejects parent
  symlinks and prevents pathname replacement from redirecting an open directory.
- Neovim reuse invokes `nvim --server ... --remote-expr ...` with argument arrays.
  Filenames become character-number expressions passed to `fnameescape`, rather
  than shell fragments or remote-send keystrokes. Regression cases include shell
  substitutions, quotes, Ex separators, newline, and `<CR>` text.
- Downloads use exclusive random temporary files with mode 0600 in the held
  destination directory. The open file receives data and timestamps before an
  atomic persist. Same-plugin relays use anonymous private temporary files and
  rewind the same handle for upload. Failures clean up through RAII. Local copies
  preserve original permissions after publishing the staged file.

Regression coverage includes a real mock SSH server counting authentication
attempts, malicious recursive and fallback plugin scans, planted destination and
old `.path-part` symlinks, changing a directory pathname after opening it, cancelled
or killed downloads, and same-plugin relays. The Neovim expression test executes
Neovim headlessly with configuration and shada disabled.

## Dependencies

The lockfile now contains russh 0.64.1, russh-cryptovec 0.62.0, and rustls 0.23.46.
Russh uses its ring backend, with RSA key compatibility retained. The new Russh
certificate callback explicitly rejects certificates: this application supports
pinned public keys and known_hosts keys, not SSH certificate-authority trust.

An OSV query of all 295 registry packages in the updated lockfile on 2026-10-14
returned these three matches. This is an advisory assessment, not a claim that
all dependency risk has been eliminated.

| Dependency | Advisory | Assessment |
| --- | --- | --- |
| bincode 1.3.3 | [RUSTSEC-2025-0141](https://rustsec.org/advisories/RUSTSEC-2025-0141.html) | Maintenance warning, retained through syntect. No vulnerability fix is supplied by this advisory. |
| rsa 0.10.0-rc.18 | [RUSTSEC-2023-0071](https://rustsec.org/advisories/RUSTSEC-2023-0071.html) | No patched release. Path uses SSH client key signing, not a network RSA decryption service. This narrows applicability but does not establish that RSA signing is constant time; retain as a release-review item. |
| suppaftp 6.3.0 | [RUSTSEC-2026-0271](https://rustsec.org/advisories/RUSTSEC-2026-0271.html) | Path validates credentials and all directly used path/rename arguments with `on_the_wire`, rejecting CR/LF/NUL before calling FTP operations. Existing regression coverage passes. Upstream fixed this in 10.0.2; the major-version migration is deferred, and any future command call must retain validation. |

The former Russh transport/allocation and rustls matches no longer appear.
The license inventory was regenerated from the filtered offline Cargo graph;
252 build dependencies have preserved notices. Missing Russh crate notices are
supplied from the exact Git revisions recorded in each crate's VCS metadata.

## Local source-RPM workflow

`.copr/Makefile` implements COPR's external SCM `srpm` target. Before any future
approved publication, set the SCM committish to the full validated commit, not a
moving branch. The source builder accepts only a full commit hash and archives
that commit, excluding working-tree edits. The source contains `SOURCE-COMMIT`,
and the RPM spec records the commit suffix in its Release. The SRPM includes both
source and locked vendor tarballs plus the bundled dependency inventory.

To generate a local SRPM with tools already installed:

```bash
python3 packaging/fedora/make_srpm.py \
  --commit "$(git rev-parse HEAD)" \
  --outdir target/security/srpm
```

Only source preparation downloads dependencies. RPM compilation and tests use
`--offline --locked` / `--frozen`; isolated validation containers disable networking
for the entire RPM rebuild. Runtime dependencies now include xclip and xdotool;
the test build also requires bsdtar, git, openssh-clients, and Neovim.

## Validation record

- Host workspace tests, including the new security regressions: 258 passed,
  zero failed, one existing ignored test. Focused mirror/editor tests also passed
  after the final compatibility adjustments.
- `cargo fmt --all -- --check`: passed.
- `cargo clippy --workspace --all-targets -- -D warnings`: passed.
- Identity, branding, packaging hooks, Fedora packaging/license, i18n, X11 and
  version checks: passed.
- Invalid source pins (for example `--commit main`) are rejected.
- Local SRPM generation: passed.
- Final package source pin: `a16e92c48926be826241ce1437f2d0a78321c464`.
- Fedora 43 and 44 offline RPM builds: passed. Each ran 258 Rust tests with zero
  failures and one existing ignored test, plus packaging/license/i18n/version
  checks and desktop-file validation.
- Fedora 44 installation: passed with dependencies resolved normally. `rpm -V`,
  installed executable checks, source-commit provenance, daemon startup, a real
  Hello request, and socket mode 0600 all passed. Documentation was enabled for
  this check because Fedora container images default to omitting doc files.
- Fedora 44 runtime dependencies installed successfully in an isolated image.
- Fedora 43 installation is blocked: DNF exited 1 with `nothing provides quickshell`
  for the built RPM. Neither the standard repositories nor
  `christitustech/copr-fedora` provides it. A dependency source was requested;
  dependency checks were not bypassed.
- Container validation uses `HOME=/work/home`; the image default `HOME=/` caused
  an existing tilde-expansion test to expect a double slash. The full suites passed
  after correcting that environment, without weakening or skipping the test.
- The only RPM build warning was the missing changelog timestamp; archive timestamp
  normalization handlers were consequently skipped. This is not a test failure,
  but these results do not claim byte-for-byte reproducible RPMs.

Local evidence and packages are under `target/security/` (Git-ignored):

- `path-rpm43-final.log`, `path-rpm44-final.log`, `path-install43.log`, `path-install44.log`
- `osv.json`, `path-tests.log`, `path-clippy.log`
- `final-srpm/path-0.2.2-0.3.gita16e92c48926.fc44.src.rpm`
- `fedora43/rpm/RPMS/x86_64/path-0.2.2-0.3.gita16e92c48926.fc43.x86_64.rpm`
- `fedora44/rpm/RPMS/x86_64/path-0.2.2-0.3.gita16e92c48926.fc44.x86_64.rpm`

Implementation commits: `849202a` (security fixes and dependencies), `90e25ec`
(offline packaging and licenses), `be4d2ba` (local mode preservation), and
`a16e92c` (custom editor command compatibility). No changes have been pushed.

The disposable runtime has no session D-Bus, so its helper logged a missing bus
while the daemon and its Hello request worked. Session D-Bus integration, systemd
user activation, a graphical desktop session, and public COPR deployment are outside this local
validation. Installation checks must not be described as a full GUI acceptance
run.
