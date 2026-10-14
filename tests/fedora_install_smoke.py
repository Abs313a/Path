#!/usr/bin/env python3
"""Verify a normally installed RPM inside a disposable Fedora environment."""
import argparse
import json, os, socket, stat, subprocess, tempfile, time
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--version', required=True)
parser.add_argument('--commit', required=True)
args = parser.parse_args()

assert subprocess.check_output(['pathd','--version'],text=True).strip() == f'pathd {args.version}'
subprocess.run(['pathd','--help'],check=True)
subprocess.run(['rpm','-V','path'],check=True)
for name in ['sftp','ftps','smb','dbus','share-mail','share-tailscale']:
    assert os.access('/usr/lib/path/plugins/path-plugin-'+name,os.X_OK)
unit=Path('/usr/lib/systemd/user/pathfm.socket').read_text()
assert 'SocketMode=0600' in unit
assert f'pathfm-{args.version}.sock' in unit
assert Path('/usr/share/doc/path/SOURCE-COMMIT').read_text().strip() == args.commit
with tempfile.TemporaryDirectory(prefix='path-install-smoke-') as tmp:
    root=Path(tmp)
    env=dict(os.environ, HOME=tmp, XDG_RUNTIME_DIR=tmp, PATHFM_SOCKET=str(root/'daemon.sock'), PATHFM_CONFIG_DIR=str(root/'config'),PATHFM_STATE_DIR=str(root/'state'),PATHFM_CACHE_DIR=str(root/'cache'),PATHFM_DATA_DIR=str(root/'data'))
    with (root/'daemon.log').open('w+') as log:
        proc=subprocess.Popen(['pathd'],env=env,stdout=log,stderr=log)
        try:
            for i in range(100):
                if (root/'daemon.sock').exists(): break
                assert proc.poll() is None
                time.sleep(.05)
            assert stat.S_IMODE((root/'daemon.sock').stat().st_mode) == 0o600
            with socket.socket(socket.AF_UNIX) as sock:
                sock.settimeout(10)
                sock.connect(str(root/'daemon.sock'))
                sock.sendall(b'{"id":1,"type":"Hello","version":1}\n')
                stream=sock.makefile('rb')
                for i in range(30):
                    reply=json.loads(stream.readline())
                    if reply.get('id')==1:
                        assert 'ok' in reply,reply
                        break
                else: raise AssertionError('no Hello response')
        finally:
            proc.terminate()
            proc.wait(timeout=10)
            log.seek(0)
            print(log.read())
print('RPM integrity, installed files, version, socket permissions and daemon Hello passed')
