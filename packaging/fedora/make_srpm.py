#!/usr/bin/env python3
"""Create an SRPM from one immutable Git commit, including offline Cargo sources."""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[2]


def run(*args, cwd=ROOT, **kwargs):
    return subprocess.run(args, cwd=cwd, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True, help='full 40-character reviewed Git commit')
    parser.add_argument('--outdir', required=True, type=Path)
    parser.add_argument('--spec', default='packaging/fedora/path.spec', type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-f]{40}', args.commit):
        parser.error('--commit must be a full Git commit, not a branch or tag')
    actual = run('git', 'rev-parse', f'{args.commit}^{{commit}}', capture_output=True, text=True).stdout.strip()
    if actual != args.commit:
        parser.error('commit does not resolve exactly')
    try:
        spec = args.spec.resolve().relative_to(ROOT)
    except ValueError:
        parser.error('spec must be inside the repository')
    if '..' in spec.parts:
        parser.error('spec must be inside the repository')
    out = args.outdir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    epoch = run('git', 'show', '-s', '--format=%ct', args.commit, capture_output=True, text=True).stdout.strip()
    with tempfile.TemporaryDirectory(prefix='path-srpm-') as work:
        work = Path(work)
        tree = work / 'tree'
        tree.mkdir()
        archive = work / 'source.tar'
        run('git', 'archive', '--format=tar', f'--output={archive}', args.commit)
        run('tar', '-xf', str(archive), '-C', str(tree))
        version = tomllib.loads((tree / 'Cargo.toml').read_text())['package']['version']
        source = work / f'path-{version}'
        tree.rename(source)
        (source / 'SOURCE-COMMIT').write_text(args.commit + '\n')
        rpm = work / 'rpm'
        for directory in ('SOURCES', 'SPECS', 'BUILD', 'RPMS', 'SRPMS'):
            (rpm / directory).mkdir(parents=True, exist_ok=True)
        sources = rpm / 'SOURCES'
        with (work / 'vendor-config.toml').open('w') as config:
            run('cargo', 'vendor', '--locked', '--versioned-dirs', str(source / 'vendor'), cwd=source, stdout=config)
        (source / '.cargo').mkdir(exist_ok=True)
        (source / '.cargo/config.toml').write_text('[source.crates-io]\nreplace-with = "vendored-sources"\n[source.vendored-sources]\ndirectory = "vendor"\n')
        metadata = work / 'metadata.json'
        with metadata.open('w') as output:
            run('cargo', 'metadata', '--offline', '--locked', '--format-version', '1',
                '--filter-platform', 'x86_64-unknown-linux-gnu', cwd=source, stdout=output)
        bundle = work / 'license-bundle'
        run('python3', str(source / 'packaging/fedora/license_bundle.py'), str(metadata),
            str(source / 'vendor'), str(bundle), cwd=source)
        expression = (bundle / 'LICENSE-EXPRESSION').read_text().strip()
        (source / 'packaging/fedora/license-expression.txt').write_text(expression + '\n')
        shutil.copyfile(bundle / 'BUNDLED-PROVIDES.inc', sources / 'bundled-rust-provides.inc')
        run('tar', '--sort=name', f'--mtime=@{epoch}', '--owner=0', '--group=0', '--numeric-owner',
            f'--exclude=path-{version}/vendor', '-czf', str(sources / f'path-{version}.tar.gz'),
            '-C', str(work), source.name)
        run('tar', '--sort=name', f'--mtime=@{epoch}', '--owner=0', '--group=0', '--numeric-owner',
            '-czf', str(sources / f'path-{version}-vendor.tar.gz'), '-C', str(source), 'vendor')
        spec_text = re.sub(r'^License:.*$', 'License: ' + expression + ' AND LicenseRef-UnRAR',
                           (source / spec).read_text(), flags=re.MULTILINE)
        (rpm / 'SPECS/path.spec').write_text(f'%global path_commit {args.commit[:12]}\n' + spec_text)
        # The exact source commit travels in both the tarball and the RPM release identity.
        run('rpmbuild', '-bs', '--define', f'_topdir {rpm}', '--define', f'_srcrpmdir {out}',
            '--define', f'path_commit {args.commit[:12]}', str(rpm / 'SPECS/path.spec'),
            env=dict(os.environ, SOURCE_DATE_EPOCH=epoch))
        print(f'SRPM source commit: {args.commit}')


if __name__ == '__main__':
    main()
