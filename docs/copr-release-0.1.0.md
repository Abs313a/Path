# Path 0.1.0 COPR preparation

COPR submission is a separate approval step. The validator and package manifest
in the local `copr-fedora` checkout must not be pushed until publication is
approved: its main-branch workflow submits builds automatically.

## Revisions

- Published `v0.1.0`: `64d261ada0631798d7dbbdd27783a854f1912300`.
- Proposed RPM source pin: `e8548b9338dfdd70bcb1f8a60f968ca500e9d500`.
- CI support: `7e7bb8e` adds manual validation of a specific revision. The release
  workflow selects only push-triggered CI runs, so a manual run of an older
  revision cannot supply packages for the wrong release.

The proposed source pin retains version 0.1.0 and the release's application code.
It corrects the source builder's spec path handling, avoids unnecessary root-only
package installation when source tools are present, adds the RPM changelog, and
adds version/commit-aware installation checks. RPM Release is 0.4 plus the source
commit suffix. The published tag is unchanged.

## Validator integration

`copr-fedora` commit `408c6e5` builds an external SCM SRPM before parsing it.
It extracts that SRPM into a temporary directory, passes its sources directory
to rpmspec, validates the RPM name and every source, then runs rpmlint on the
complete SRPM. It does not suppress a missing include or skip the source checks.
The regression fixture contains a generated include and archive.

`copr-fedora` commit `aaaf639` supplies the pinned Path manifest and installation
instructions. From that checkout, the actual end-to-end check is:

```bash
python3 scripts/copr_automation.py validate --package path
```

The remote clone, package-subdirectory Makefile invocation, vendoring, source
RPM creation, spec expansion, source checks and rpmlint pass. rpmlint reports
zero errors and two nonfatal invalid-URL warnings for local generated tarballs;
those tarballs are included in the SRPM and explicitly checked by the validator.
All 24 validator tests pass.

## Fedora 43 dependency

Fedora 43 uses the explicitly selected `errornointernet/quickshell` COPR.
An isolated Fedora 43 installation resolved `quickshell-0.3.2-1.fc43.x86_64`
and successfully ran `qs --version`. Fedora 44 uses its standard repositories.

After Path is approved and published, Fedora 43 installation is:

```bash
sudo dnf copr enable errornointernet/quickshell
sudo dnf copr enable christitustech/copr-fedora
sudo dnf install path
```

On Fedora 44, omit the first command. Path does not enable repositories in RPM
scriptlets. The extra repository is needed at installation time, not to build
Path's RPM. Keep Quickshell and Qt updated together within the same Fedora release.

## Reproducing source and installation checks

Create an immutable-source SRPM from the Path checkout:

```bash
python3 packaging/fedora/make_srpm.py \
  --commit e8548b9338dfdd70bcb1f8a60f968ca500e9d500 \
  --outdir target/copr-release/candidate-srpm
```

Rebuild it with `rpmbuild --rebuild` inside each Fedora target with networking
disabled, after provisioning BuildRequires. Set a normal private HOME for the
test process; do not use the container default `/`. Install the resulting RPM
with DNF in a separate disposable runtime, with documentation enabled. Then run:

```bash
python3 tests/fedora_install_smoke.py \
  --version 0.1.0 \
  --commit e8548b9338dfdd70bcb1f8a60f968ca500e9d500
```

That checks RPM integrity, installed executable paths, versioned socket unit,
source provenance, daemon startup, socket permissions and a real Hello request.
It is not a full desktop-session/systemd-activation acceptance test.

## Exact release validation

The published tag's SRPM is
`path-0.1.0-0.3.git64d261ada063.fc44.src.rpm`. It was rebuilt offline on
Fedora 43 and Fedora 44. Both builds passed 258 Rust tests with zero failures
and one existing ignored test, plus the packaging/license/i18n/version checks.

Both resulting RPMs installed successfully with DNF and passed the installation
smoke check above using commit `64d261ada0631798d7dbbdd27783a854f1912300`.
Runtime dependencies were provisioned normally first, including Quickshell from
the selected Fedora 43 COPR. The final package installation and smoke checks had
networking disabled and did not bypass dependency checks. Documentation was
explicitly enabled so SOURCE-COMMIT could be verified.

The original tag's missing RPM changelog produces a build warning; the proposed
packaging commit fixes it. These results supersede the old 0.2.2 build evidence
for release validation, without modifying the release tag.

## Proposed COPR pin validation

Both offline candidate RPM rebuilds passed 258 Rust tests, zero failures and one
existing ignored test, plus packaging/license/i18n/version and desktop-file checks.
Both RPMs installed with normal DNF dependency enforcement and passed the installed
version, SOURCE-COMMIT, RPM integrity, plugin/helper paths, socket mode 0600 and
daemon Hello checks. No COPR build has been submitted.

| Source | Fedora 43 x86_64 | Fedora 44 x86_64 |
| --- | --- | --- |
| Published tag `64d261a` | Build, tests, install: passed | Build, tests, install: passed |
| Proposed pin `e8548b9` | Build, tests, install: passed | Build, tests, install: passed |

Candidate artifacts under `target/copr-release/`:

- `candidate-srpm/path-0.1.0-0.4.gite8548b9338df.fc44.src.rpm`
- `fedora43/rpm/RPMS/x86_64/path-0.1.0-0.4.gite8548b9338df.fc43.x86_64.rpm`
- `fedora44/rpm/RPMS/x86_64/path-0.1.0-0.4.gite8548b9338df.fc44.x86_64.rpm`
- `candidate-build43.log`, `candidate-build44.log`
- `install-candidate43.log`, `install-candidate44.log`
- `validator-remote.log`, `validator-tests-final.log`
- `ci-release.log`, `ci-candidate.log`, `SHA256SUMS`

The remaining action is approval to publish the local `copr-fedora` changes and
submit the pinned package. Its shared-validator change triggers builds on push;
do not push it as a documentation-only operation.

## GitHub evidence

- [Updated main Python and Rust CodeQL: passed](https://github.com/ChrisTitusTech/Path/actions/runs/38629975412).
- [Release Python and Rust CodeQL: passed](https://github.com/ChrisTitusTech/Path/actions/runs/38628919898).
- [Release build/test CI: passed](https://github.com/ChrisTitusTech/Path/actions/runs/38629989446).
- [Packaging source-pin build/test CI: passed](https://github.com/ChrisTitusTech/Path/actions/runs/38629993584).

The manual runs use workflow definitions from main but explicitly check out the
specified full source commit. Their workflow head alone is not the tested source
revision. Both runs passed x86_64 and aarch64 Rust/package jobs, including protocol/plugin
contract tests. Each QML run passed 840 leaf/interaction tests and 12 drag tests.
Actionlint also passed for the updated CI and release workflows.

Local logs, SRPMs and RPMs are retained under Git-ignored `target/copr-release/`.
The advisory assessments in `security-review-2026-10-14.md` remain applicable;
this packaging work does not remove the bincode, RSA or suppaftp advisory matches.
