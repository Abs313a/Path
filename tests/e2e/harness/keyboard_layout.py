# SPDX-License-Identifier: MIT
"""Live keyboard layouts on the harness's private display.

`setxkbmap` loads layouts into the display and an XKB group lock selects the
active one, as a layout switch shortcut does. The XTest keymap was read once
from the default US layout, so key names keep meaning US key positions: under
`RUSSIAN`, `press("ctrl+c")` presses the key that types с.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from .environment import process_environment
from .xtest import ALL_MODIFIERS, LOCK_MASK, KeyboardState, XTestConnection

DEFAULT_LAYOUT = "us"
SETXKBMAP_TIMEOUT = 10.0


class LayoutError(RuntimeError):
    pass


@dataclass(frozen=True)
class Layout:
    """`name` is the test id."""

    name: str
    layouts: str
    group: int = 0
    caps_lock: bool = False
    variants: str = ""


US = Layout("us", "us")
# Beside US, as Russian users usually configure it: GTK finds Latin keys in US.
RUSSIAN = Layout("ru", "us,ru", group=1)
# No configured layout has Latin letters.
RUSSIAN_ONLY = Layout("ru-only", "ru")
AZERTY = Layout("fr", "fr")
QWERTZ = Layout("de", "de")
CAPS_LOCK = Layout("caps-lock", "us", caps_lock=True)
# Plain cn is US; this variant types tone marks as AltGr+1–4 dead keys.
PINYIN = Layout("cn-altgr-pinyin", "cn", variants="altgr-pinyin")


@contextmanager
def switched(connection: XTestConnection, layout: Layout) -> Iterator[None]:
    """Wait for each key's effect inside the block: GDK may read the keymap only
    when it handles the event, and by then a finished block has restored US.
    """

    try:
        variants = ("-variant", layout.variants) if layout.variants else ()
        _setxkbmap(connection, "-layout", layout.layouts, *variants)
        connection.lock_group(layout.group)
        if layout.caps_lock:
            connection.lock_modifiers(LOCK_MASK, LOCK_MASK)
        yield
    finally:
        # setxkbmap keeps locks, so release them before restoring the layout.
        connection.lock_group(0)
        connection.lock_modifiers(ALL_MODIFIERS, 0)
        # A new layout without -variant also clears the variants.
        _setxkbmap(connection, "-layout", DEFAULT_LAYOUT)
        restored = _query(connection)
        state = connection.keyboard_state()
        if (
            restored.get("layout") != DEFAULT_LAYOUT
            or restored.get("variant")
            or state != KeyboardState(0, 0, 0)
        ):
            raise LayoutError(
                f"the keyboard was not restored after {layout.name}: "
                f"layout {restored.get('layout')!r}, variant {restored.get('variant')!r}, {state}"
            )


def _query(connection: XTestConnection) -> dict[str, str]:
    output = _setxkbmap(connection, "-query")
    return {
        name.strip(): value.strip()
        for name, _, value in (line.partition(":") for line in output.splitlines())
    }


def _setxkbmap(connection: XTestConnection, *arguments: str) -> str:
    # The explicit display and the PATH-only environment keep this off the desktop.
    result = subprocess.run(
        ["setxkbmap", "-display", connection.display_name, *arguments],
        env=process_environment(),
        capture_output=True,
        text=True,
        timeout=SETXKBMAP_TIMEOUT,
    )
    if result.returncode != 0:
        raise LayoutError(f"setxkbmap {' '.join(arguments)} failed: {result.stderr.strip()}")
    return result.stdout
