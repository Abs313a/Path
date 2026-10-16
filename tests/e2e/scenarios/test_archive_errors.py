# SPDX-License-Identifier: MIT
import gzip
import io
import os
import re
import shutil
import struct
import tarfile
import zipfile
import zlib
from pathlib import Path

import pytest

from harness.artifacts import ArtifactCollector


ARCHIVE_FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.mark.parametrize("format", ["7Z", "TAR.GZ"])
def test_cancel_compression_stops_before_publishing_and_allows_another_operation(pathfm, format):
    fixture = pathfm.fixture
    payload_size = 64 * 1024 * 1024
    fixture.path("payload.bin").write_bytes(os.urandom(payload_size))
    pathfm.entry("payload.bin")
    pathfm.open_context_menu("payload.bin")
    pathfm.choose_menu_item("Compress…")
    dialog = pathfm.wait_for_dialog()
    pathfm.pointer.click(dialog.find(role="toggle button", name=format))
    pathfm.pointer.click(pathfm.dialog_button("Compress"))
    cancel = pathfm.wait(
        lambda: pathfm.window.find(role="button", name="Cancel compressing"),
        "docked compression cancellation action",
    )
    pathfm.wait(lambda: pathfm.dialog() is None, "compression configuration dismissal")
    pathfm.pointer.click(cancel)
    pathfm.wait(
        lambda: (dialog := pathfm.dialog()) is not None and dialog.name == "Operation cancelled",
        "compression worker to stop and report cancellation",
    )
    assert not pathfm.window.find(role="progress bar")
    assert not list(fixture.root.glob(".pathfm-compression-*"))
    assert not list(fixture.root.glob("*.7z"))
    assert not list(fixture.root.glob("*.tar.gz"))
    assert fixture.path("payload.bin").stat().st_size == payload_size
    pathfm.pointer.click(pathfm.dialog_button("Close"))
    pathfm.wait(lambda: pathfm.dialog() is None, "cancellation summary dismissal")

    pathfm.open_context_menu("todo.txt")
    pathfm.choose_menu_item("Compress…")
    pathfm.wait_for_dialog()
    pathfm.pointer.click(pathfm.dialog_button("Compress"))
    pathfm.wait(lambda: fixture.path("todo.txt.zip").exists(), "subsequent compression")
    pathfm.wait(lambda: pathfm.dialog() is None, "subsequent progress dismissal")
    with zipfile.ZipFile(fixture.path("todo.txt.zip")) as archive:
        assert archive.read("todo.txt") == fixture.path("todo.txt").read_bytes()


INVALID_ARCHIVE = "This file is not a valid archive or is damaged."


def _write_text(path):
    path.write_bytes(b"This is harmless text, not an archive.\n")


def _write_zip_with_absolute_member(path):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ok.txt", "ok")
        archive.writestr("second.txt", "2")
        archive.writestr(zipfile.ZipInfo("/etc/evil.txt"), "evil")


def _write_tar_gz_with_bad_trailer(path):
    raw = io.BytesIO()
    data = b"x" * 50_000
    with tarfile.open(fileobj=raw, mode="w") as archive:
        info = tarfile.TarInfo("a.txt")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    damaged = bytearray(gzip.compress(raw.getvalue()))
    damaged[-8] ^= 0xFF
    path.write_bytes(bytes(damaged))


@pytest.mark.parametrize("name,write_fixture,detail,kept,members", [
    *(
        pytest.param(name, _write_text, INVALID_ARCHIVE, None, [], id=name)
        for name in ["fake.zip", "fake.7z", "fake.tar", "fake.tar.gz", "fake.rar"]
    ),
    pytest.param(
        "scatter.zip",
        _write_zip_with_absolute_member,
        "Refusing unsafe archive path: /etc/evil.txt. Extracted entries remain in “scatter”.",
        "scatter",
        ["ok.txt", "second.txt"],
        id="scatter.zip",
    ),
    pytest.param(
        "trailer.tar.gz",
        _write_tar_gz_with_bad_trailer,
        f"{INVALID_ARCHIVE} Extracted entries remain in “trailer”.",
        "trailer",
        ["a.txt"],
        id="trailer.tar.gz",
    ),
])
def test_invalid_archive_reports_damage_and_allows_another_extraction(
    pathfm, name, write_fixture, detail, kept, members
):
    fixture = pathfm.fixture
    write_fixture(fixture.path(name))
    original = fixture.path(name).read_bytes()
    with zipfile.ZipFile(fixture.path("valid.zip"), "w") as archive:
        archive.writestr("extracted.txt", "harmless contents")
    pathfm.keyboard.press("ctrl+r")
    pathfm.pointer.right_click(pathfm.entry(name))
    pathfm.choose_menu_item("Extract here")
    dialog = pathfm.wait(
        lambda: (
            dialog
            if (dialog := pathfm.dialog()) is not None
            and dialog.name == "Unable to complete operation"
            else None
        ),
        "the archive error dialog to replace the progress dialog",
    )
    # The dialog wraps long messages, so the label may contain line breaks.
    detail_pattern = r"\s+".join(re.escape(word) for word in detail.split())
    assert dialog.find(role="label", name_matches=f"^{detail_pattern}$")
    assert not pathfm.window.find(role="progress bar")
    assert fixture.path(name).read_bytes() == original
    for member in members:
        assert (fixture.path(kept) / member).is_file()
        assert not fixture.path(member).exists()
    assert not list(fixture.root.glob(".pathfm-extraction-*"))
    pathfm.pointer.click(pathfm.dialog_button("Close"))
    pathfm.wait(lambda: pathfm.dialog() is None, "error dismissal")
    pathfm.pointer.right_click(pathfm.entry("valid.zip"))
    pathfm.choose_menu_item("Extract here")
    pathfm.wait(lambda: fixture.path("extracted.txt").exists(), "valid archive extraction")
    assert fixture.path("extracted.txt").read_text() == "harmless contents"
    pathfm.wait(lambda: pathfm.dialog() is None, "extraction progress dismissal")


def test_folder_named_like_an_archive_offers_no_extract_actions(pathfm):
    pathfm.fixture.path("photos.zip").mkdir()
    pathfm.keyboard.press("ctrl+r")
    pathfm.open_context_menu("photos.zip")
    items = pathfm.menu_items()
    assert "Extract here" not in items and "Extract to…" not in items, items
    assert "Open in Terminal" in items or "Pin to sidebar" in items, items
    pathfm.dismiss_menu()


@pytest.mark.parametrize("source,password,member,contents", [
    (ARCHIVE_FIXTURES / "content-encrypted.7z", "secret", "protected.txt", "password retry works\n"),
    (Path(__file__).parents[2] / "fixtures/rar/encrypted.rar", "unrar", ".gitignore", "target\nCargo.lock\n"),
    (Path(__file__).parents[2] / "fixtures/rar/comment-hpw-password.rar", "password", ".gitignore", "target\nCargo.lock\n"),
])
def test_wrong_extract_password_reopens_dialog_until_password_is_correct(pathfm, source, password, member, contents):
    fixture = pathfm.fixture
    archive_name = source.name
    shutil.copyfile(source, fixture.path(archive_name))
    pathfm.keyboard.press("ctrl+r")
    pathfm.pointer.right_click(pathfm.entry(archive_name))
    pathfm.choose_menu_item("Extract here")

    dialog = pathfm.wait(
        lambda: (
            dialog
            if (dialog := pathfm.dialog()) is not None and dialog.name == "Extract"
            else None
        ),
        "the password dialog to replace the progress dialog",
    )
    pathfm.pointer.click(pathfm.dialog_button("Extract"))
    dialog = pathfm.wait_for_dialog()
    assert dialog.find(role="label", name="Enter a password") is not None

    pathfm.keyboard.type_text("wrong")
    pathfm.pointer.click(pathfm.dialog_button("Extract"))

    dialog = pathfm.wait(
        lambda: (
            dialog
            if (dialog := pathfm.dialog()) is not None
            and dialog.name == "Extract"
            and dialog.find(role="password text", states={"focused"}) is not None
            else None
        ),
        "the password dialog to reopen after the wrong password",
    )
    assert dialog.find(role="label", name="Invalid password") is not None
    assert dialog.find(role="label", name="Unable to complete operation") is None
    if source.suffix == ".rar":
        assert not fixture.path(member).exists()

    if source.suffix == ".rar":
        collector = ArtifactCollector(test_name=f"rar-password-{source.stem}")
        pathfm.screenshot(collector.directory / "password-retry.png")
    pathfm.keyboard.type_text(password)
    pathfm.pointer.click(pathfm.dialog_button("Extract"))
    extracted = fixture.path(member)
    pathfm.wait(lambda: extracted.exists(), "the archive to extract with the correct password")
    pathfm.wait(lambda: pathfm.dialog() is None, "extraction progress dismissal")
    assert extracted.read_text() == contents


def test_cancelled_extract_to_does_not_hijack_later_extract_here(pathfm):
    fixture = pathfm.fixture
    archive_name = "content-encrypted.7z"
    shutil.copyfile(ARCHIVE_FIXTURES / archive_name, fixture.path(archive_name))
    with zipfile.ZipFile(fixture.path("later.zip"), "w") as archive:
        archive.writestr("later.txt", "later extraction\n")
    pathfm.keyboard.press("ctrl+r")
    pathfm.open_context_menu(archive_name)
    pathfm.choose_menu_item("Extract to…")
    destination = fixture.path("documents")
    chooser = pathfm.destination_chooser("Extract to")
    pathfm.navigate_destination(chooser, destination)
    pathfm.confirm_destination(chooser, "Extract here")
    pathfm.wait(
        lambda: (dialog := pathfm.dialog()) is not None and dialog.name == "Extract",
        "the password prompt",
    )
    pathfm.keyboard.press("Escape")
    pathfm.wait(lambda: pathfm.dialog() is None, "password prompt cancellation")
    assert not (destination / "later.txt").exists()
    pathfm.open_context_menu("later.zip")
    pathfm.choose_menu_item("Extract here")
    pathfm.wait(lambda: fixture.path("later.txt").exists(), "later extraction")
    pathfm.wait(lambda: pathfm.dialog() is None, "extraction progress dismissal")
    assert pathfm.current_directory() == fixture.root.name
    assert fixture.path("later.txt").read_text() == "later extraction\n"
    assert not (destination / "later.txt").exists()
    pathfm.entry("later.txt")
    collector = ArtifactCollector(test_name="cancelled-extract-to")
    pathfm.screenshot(collector.directory / "after.png")


_CRCTABLE = None


def _zipcrypto_crc32(ch, crc):
    global _CRCTABLE
    if _CRCTABLE is None:
        table = []
        for value in range(256):
            for _ in range(8):
                value = (value >> 1) ^ 0xEDB88320 if value & 1 else value >> 1
            table.append(value)
        _CRCTABLE = table
    return (crc >> 8) ^ _CRCTABLE[(crc ^ ch) & 0xFF]


def _zipcrypto_encrypt(password, data):
    key0, key1, key2 = 305419896, 591751049, 878082192

    def update(byte):
        nonlocal key0, key1, key2
        key0 = _zipcrypto_crc32(byte, key0)
        key1 = (key1 + (key0 & 0xFF)) & 0xFFFFFFFF
        key1 = (key1 * 134775813 + 1) & 0xFFFFFFFF
        key2 = _zipcrypto_crc32(key1 >> 24, key2)

    for byte in password:
        update(byte)
    out = bytearray()
    for byte in data:
        key = key2 | 2
        out.append(byte ^ (((key * (key ^ 1)) >> 8) & 0xFF))
        update(byte)
    return bytes(out)


def _raw_deflate(data):
    compressor = zlib.compressobj(level=9, wbits=-15)
    return compressor.compress(data) + compressor.flush()


def _write_zipcrypto(path, password, name, contents, *, deflated=False):
    crc = zlib.crc32(contents) & 0xFFFFFFFF
    payload = _raw_deflate(contents) if deflated else contents
    header = os.urandom(11) + bytes([(crc >> 24) & 0xFF])
    encrypted = _zipcrypto_encrypt(password, header + payload)
    name_b = name.encode("utf-8")
    flags = 0x0001
    method = 8 if deflated else 0
    local = struct.pack(
        "<IHHHHHIIIHH",
        0x04034B50,
        20,
        flags,
        method,
        0,
        0,
        crc,
        len(encrypted),
        len(contents),
        len(name_b),
        0,
    )
    local_data = local + name_b + encrypted
    central = struct.pack(
        "<IHHHHHHIIIHHHHHII",
        0x02014B50,
        20,
        20,
        flags,
        method,
        0,
        0,
        crc,
        len(encrypted),
        len(contents),
        len(name_b),
        0,
        0,
        0,
        0,
        0,
        0,
    )
    cd = central + name_b
    eocd = struct.pack(
        "<IHHHHIIH",
        0x06054B50,
        0,
        0,
        1,
        1,
        len(cd),
        len(local_data),
        0,
    )
    path.write_bytes(local_data + cd + eocd)


def _zipcrypto_crc_collision(path, member="some.txt"):
    for candidate in range(4096):
        password = str(candidate).encode()
        try:
            with zipfile.ZipFile(path) as archive:
                archive.read(member, pwd=password)
        except RuntimeError as error:
            if "Bad password" in str(error):
                continue
            return str(candidate)
        except (zipfile.BadZipFile, OSError, zlib.error):
            return str(candidate)
    raise AssertionError("no ZipCrypto CRC collision in 0..4096")


@pytest.mark.parametrize(
    "deflated,contents",
    [
        pytest.param(False, b"hello from zipcrypto", id="stored"),
        pytest.param(True, b"hello from zipcrypto\n" * 64, id="deflated"),
    ],
)
def test_zipcrypto_collision_reopens_extract_dialog(pathfm, deflated, contents):
    fixture = pathfm.fixture
    archive_name = "password.zip"
    archive_path = fixture.path(archive_name)
    _write_zipcrypto(
        archive_path, b"zipsecret", "some.txt", contents, deflated=deflated
    )
    collision = _zipcrypto_crc_collision(archive_path)
    pathfm.keyboard.press("ctrl+r")
    pathfm.pointer.right_click(pathfm.entry(archive_name))
    pathfm.choose_menu_item("Extract here")

    dialog = pathfm.wait(
        lambda: (
            dialog
            if (dialog := pathfm.dialog()) is not None and dialog.name == "Extract"
            else None
        ),
        "the password dialog to replace the progress dialog",
    )
    pathfm.pointer.click(pathfm.dialog_button("Extract"))
    dialog = pathfm.wait_for_dialog()
    assert dialog.find(role="label", name="Enter a password") is not None

    pathfm.keyboard.type_text(collision)
    pathfm.pointer.click(pathfm.dialog_button("Extract"))

    dialog = pathfm.wait(
        lambda: (
            dialog
            if (dialog := pathfm.dialog()) is not None
            and dialog.name == "Extract"
            and dialog.find(role="password text", states={"focused"}) is not None
            else None
        ),
        "the password dialog to reopen after a ZipCrypto CRC collision",
    )
    assert dialog.find(role="label", name="Invalid password") is not None
    assert dialog.find(role="label", name="Unable to complete operation") is None
    assert dialog.find(role="label", name="This file is not a valid archive or is damaged.") is None

    pathfm.keyboard.type_text("zipsecret")
    pathfm.keyboard.press("Return")
    extracted = fixture.path("some.txt")
    pathfm.wait(lambda: extracted.exists(), "the archive to extract with the correct password")
    assert extracted.read_text() == contents.decode()
    pathfm.wait(lambda: pathfm.dialog() is None, "extraction progress dismissal")
