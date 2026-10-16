// SPDX-License-Identifier: MIT

//! The one reader of key events. Handlers install through [`on_press`] and
//! [`on_release`], which normalize each event once into a [`KeyPress`]. See
//! `docs/keyboard-shortcuts.md`.

use gtk::{
    gdk::{self, Key, ModifierType as Modifiers},
    glib::{self, Propagation, translate::IntoGlib},
    prelude::*,
};

pub(crate) mod bindings;
mod composition;
mod label;

#[cfg(test)]
mod tests;

pub(crate) use label::{
    Digits, Keys, digit_label, label, label_in, modifiers_label, modifiers_label_in, search_text,
};

/// The modifiers shortcuts compare. Locks, AltGr, Hyper and Meta never count.
pub(crate) const SHORTCUT_MODIFIERS: Modifiers = Modifiers::CONTROL_MASK
    .union(Modifiers::ALT_MASK)
    .union(Modifiers::SHIFT_MASK)
    .union(Modifiers::SUPER_MASK);

/// Editing shortcuts of `gtk::Text` and `gtk::TextView`, with the widget action
/// each runs.
pub(crate) const TEXT_EDITING: [(Binding, &str); 7] = [
    (bindings::COPY, "clipboard.copy"),
    (bindings::CUT, "clipboard.cut"),
    (bindings::PASTE, "clipboard.paste"),
    (bindings::SELECT_ALL, "selection.select-all"),
    (bindings::UNDO, "text.undo"),
    (bindings::REDO, "text.redo"),
    (bindings::REDO_Y, "text.redo"),
];

/// A canonical key and its exact modifiers. Letters are lowercase with Shift
/// explicit, a symbol names the symbol, and a digit means its digit-row position.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct Binding {
    key: Key,
    modifiers: Modifiers,
    ignored: Modifiers,
}

impl Binding {
    pub(crate) const fn new(key: Key, modifiers: Modifiers) -> Self {
        Self {
            key,
            modifiers,
            ignored: Modifiers::empty(),
        }
    }

    pub(crate) const fn plain(key: Key) -> Self {
        Self::new(key, Modifiers::empty())
    }

    pub(crate) const fn shift(key: Key) -> Self {
        Self::new(key, Modifiers::SHIFT_MASK)
    }

    pub(crate) const fn ctrl(key: Key) -> Self {
        Self::new(key, Modifiers::CONTROL_MASK)
    }

    pub(crate) const fn ctrl_shift(key: Key) -> Self {
        Self::new(key, Modifiers::CONTROL_MASK.union(Modifiers::SHIFT_MASK))
    }

    pub(crate) const fn alt(key: Key) -> Self {
        Self::new(key, Modifiers::ALT_MASK)
    }

    pub(crate) const fn ctrl_alt(key: Key) -> Self {
        Self::new(key, Modifiers::CONTROL_MASK.union(Modifiers::ALT_MASK))
    }

    /// Also matches while any of `modifiers` is held. Only navigation and
    /// dismiss keys use this, where a handler accepts those modifiers.
    pub(crate) const fn ignoring(self, modifiers: Modifiers) -> Self {
        Self {
            ignored: self.ignored.union(modifiers),
            ..self
        }
    }

    pub(crate) const fn key(self) -> Key {
        self.key
    }

    pub(crate) const fn modifiers(self) -> Modifiers {
        self.modifiers
    }

    /// The string for a menu item's `accel` attribute.
    pub(crate) fn accelerator(self) -> glib::GString {
        gtk::accelerator_name(self.key, self.modifiers)
    }
}

/// One key event, normalized once for every handler that sees it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct KeyPress {
    key: Key,
    shortcut_modifiers: Modifiers,
    state: Modifiers,
    typed: Key,
    digit: Option<u8>,
    fallback: bool,
    modifier: bool,
}

impl KeyPress {
    /// Whether the press is `binding`, comparing modifiers exactly apart from
    /// those the binding ignores.
    pub(crate) fn is(&self, binding: Binding) -> bool {
        let compared = SHORTCUT_MODIFIERS.difference(binding.ignored);
        match digit_value(binding.key) {
            Some(digit) => {
                self.digit == Some(digit) && self.state & compared == binding.modifiers & compared
            }
            None => {
                self.key == binding.key
                    && self.shortcut_modifiers & compared == binding.modifiers & compared
            }
        }
    }

    pub(crate) fn is_any(&self, bindings: &[Binding]) -> bool {
        bindings.iter().any(|binding| self.is(*binding))
    }

    /// The digit-row position (1–9, 0) or keypad digit when the press is in
    /// `digits`. Held modifiers, Shift included, must match apart from those
    /// the range ignores.
    pub(crate) fn digit_in(&self, digits: Digits) -> Option<u8> {
        let compared = SHORTCUT_MODIFIERS.difference(digits.ignored());
        self.digit.filter(|digit| {
            self.state & compared == digits.modifiers() & compared && digits.contains(*digit)
        })
    }

    /// The typed character, for typing consumers only. Nothing is typed while
    /// Ctrl, Alt or Super is held.
    pub(crate) fn text(&self) -> Option<char> {
        if self
            .state
            .intersects(Modifiers::CONTROL_MASK | Modifiers::ALT_MASK | Modifiers::SUPER_MASK)
        {
            return None;
        }
        self.typed
            .to_unicode()
            .filter(|character| !character.is_control())
    }

    pub(crate) fn is_modifier(&self) -> bool {
        self.modifier
    }

    /// The held Ctrl, Alt, Shift and Super, including Shift that typed a symbol.
    /// For policies that depend on what is held rather than on a binding.
    pub(crate) fn modifiers(&self) -> Modifiers {
        self.state
    }

    /// The modifier this key itself holds, empty for other keys. GDK reports
    /// the state from before the event, without it.
    pub(crate) fn modifier_key(&self) -> Modifiers {
        modifier_of(self.typed)
    }

    /// Whether the key came from another layout or the US-QWERTY table, which
    /// GTK's own bindings may not recognize.
    pub(crate) fn used_fallback(&self) -> bool {
        self.fallback
    }

    /// The same press read as `binding`, for keys that stand in for others,
    /// such as h/j/k/l for arrows.
    pub(crate) fn read_as(self, binding: Binding) -> Self {
        Self {
            key: binding.key,
            shortcut_modifiers: binding.modifiers,
            ..self
        }
    }

    /// A press from signal arguments alone, as emitted without a GDK event. It
    /// reads as a US-QWERTY press; tests build presses this way.
    pub(crate) fn from_signal(keyval: Key, keycode: u32, state: Modifiers) -> Self {
        normalize(&Event::synthetic(keyval, keycode, state), |_| {
            None::<(u32, u32, Key)>
        })
    }
}

/// While the focused field is composing, the input method sees each key first;
/// the handler gets only keys it passes back, like Escape after a Korean commit.
pub(crate) fn on_press(
    controller: &gtk::EventControllerKey,
    handler: impl Fn(&gtk::EventControllerKey, &KeyPress) -> Propagation + 'static,
) -> glib::SignalHandlerId {
    composition::follow();
    let forwarded = std::rc::Rc::new(composition::Forwarded::default());
    let releases = forwarded.clone();
    signals::released(controller, move |controller, keyval, _, _| {
        releases.release(controller, keyval);
    });
    signals::pressed(controller, move |controller, keyval, keycode, state| {
        if let Some(field) = composition::composing_field(controller) {
            // Forwarding needs a real event, and forwarding from the field's own
            // controller would run that controller again.
            if controller.current_event().is_none() || controller.widget().as_ref() == Some(&field)
            {
                return Propagation::Proceed;
            }
            if controller.forward(&field) {
                forwarded.press(keyval, &field);
                return Propagation::Stop;
            }
        }
        handler(controller, &read(controller, keyval, keycode, state))
    })
}

pub(crate) fn on_release(
    controller: &gtk::EventControllerKey,
    handler: impl Fn(&gtk::EventControllerKey, &KeyPress) + 'static,
) -> glib::SignalHandlerId {
    signals::released(controller, move |controller, keyval, keycode, state| {
        handler(controller, &read(controller, keyval, keycode, state));
    })
}

/// Reads a key event that reached a non-key controller, such as
/// `EventControllerLegacy`. Other events give `None`.
pub(crate) fn read_event(event: &gdk::Event) -> Option<KeyPress> {
    let event = event.downcast_ref::<gdk::KeyEvent>()?;
    Some(normalize_event(event))
}

#[expect(
    clippy::disallowed_methods,
    reason = "ui::keys is the only module that reads raw key signals"
)]
mod signals {
    use gtk::{
        gdk::{Key, ModifierType},
        glib::{Propagation, SignalHandlerId},
    };

    pub(super) fn pressed(
        controller: &gtk::EventControllerKey,
        handler: impl Fn(&gtk::EventControllerKey, Key, u32, ModifierType) -> Propagation + 'static,
    ) -> SignalHandlerId {
        controller.connect_key_pressed(handler)
    }

    pub(super) fn released(
        controller: &gtk::EventControllerKey,
        handler: impl Fn(&gtk::EventControllerKey, Key, u32, ModifierType) + 'static,
    ) -> SignalHandlerId {
        controller.connect_key_released(handler)
    }
}

fn read(
    controller: &gtk::EventControllerKey,
    keyval: Key,
    keycode: u32,
    state: Modifiers,
) -> KeyPress {
    match controller
        .current_event()
        .and_then(|event| event.downcast::<gdk::KeyEvent>().ok())
    {
        Some(event) => normalize_event(&event),
        None => KeyPress::from_signal(keyval, keycode, state),
    }
}

fn normalize_event(event: &gdk::KeyEvent) -> KeyPress {
    normalize(&Event::read(event), |keycode| {
        event
            .display()
            .and_then(|display| display.map_keycode(keycode))
            .into_iter()
            .flatten()
            .map(|(entry, key)| (entry.group() as u32, entry.level() as u32, key))
    })
}

#[derive(Clone, Copy, Debug)]
struct Event {
    /// `KeyEvent::match_()`: Caps Lock ignored, consumed modifiers removed,
    /// letters lowercase with Shift.
    matched: (Key, Modifiers),
    typed: Key,
    state: Modifiers,
    keycode: u32,
    layout: u32,
    level: u32,
    modifier: bool,
}

impl Event {
    fn read(event: &gdk::KeyEvent) -> Self {
        let typed = event.keyval();
        let state = event.modifier_state();
        Self {
            matched: event.match_().unwrap_or((typed.to_lower(), state)),
            typed,
            state,
            keycode: event.keycode(),
            layout: event.layout(),
            level: event.level(),
            modifier: event.is_modifier(),
        }
    }

    fn synthetic(typed: Key, keycode: u32, state: Modifiers) -> Self {
        let position = us_position(typed);
        let key = if typed == Key::ISO_Left_Tab {
            Key::Tab
        } else {
            typed.to_lower()
        };
        let mut modifiers = state;
        if key != typed {
            // Caps Lock alone types uppercase and never changes a shortcut.
            if !state.contains(Modifiers::LOCK_MASK) || state.contains(Modifiers::SHIFT_MASK) {
                modifiers.insert(Modifiers::SHIFT_MASK);
            }
        } else if position.is_some() && typed.to_upper() == typed {
            // GDK reports the Shift that typed a digit or symbol as consumed.
            modifiers.remove(Modifiers::SHIFT_MASK);
        }
        Self {
            matched: (key, modifiers),
            typed,
            state,
            keycode: match position {
                Some((position, _)) if keycode == 0 => position,
                _ => keycode,
            },
            layout: 0,
            level: position.map_or(0, |(_, level)| level),
            modifier: MODIFIER_KEYS.contains(&typed),
        }
    }
}

const MODIFIER_KEYS: [Key; 12] = [
    Key::Shift_L,
    Key::Shift_R,
    Key::Control_L,
    Key::Control_R,
    Key::Alt_L,
    Key::Alt_R,
    Key::Super_L,
    Key::Super_R,
    Key::Meta_L,
    Key::Meta_R,
    Key::ISO_Level3_Shift,
    Key::Caps_Lock,
];

fn modifier_of(key: Key) -> Modifiers {
    match key {
        Key::Control_L | Key::Control_R => Modifiers::CONTROL_MASK,
        Key::Shift_L | Key::Shift_R => Modifiers::SHIFT_MASK,
        Key::Alt_L | Key::Alt_R | Key::Meta_L | Key::Meta_R => Modifiers::ALT_MASK,
        Key::Super_L | Key::Super_R => Modifiers::SUPER_MASK,
        _ => Modifiers::empty(),
    }
}

fn normalize<Entries>(event: &Event, keymap: impl FnOnce(u32) -> Entries) -> KeyPress
where
    Entries: IntoIterator<Item = (u32, u32, Key)>,
{
    let (mut key, mut modifiers) = event.matched;
    modifiers &= SHORTCUT_MODIFIERS;
    let state = event.state & SHORTCUT_MODIFIERS;
    // Levels 2 and 3 are AltGr text. Caps Lock can raise the event's level, so
    // the fallback reads the level Shift selects.
    let latin = (event.level <= 1 && types_beyond_ascii(key))
        .then(|| {
            let level = u32::from(state.contains(Modifiers::SHIFT_MASK));
            keymap(event.keycode)
                .into_iter()
                .find(|&(layout, entry_level, entry)| {
                    layout != event.layout && entry_level == level && printable_ascii(entry)
                })
                .map(|(_, _, entry)| entry)
                .or_else(|| us_qwerty(event.keycode).map(|keys| keys[level as usize]))
        })
        .flatten();
    if let Some(latin) = latin {
        key = latin.to_lower();
        modifiers.set(Modifiers::SHIFT_MASK, key != latin);
    }
    KeyPress {
        key: main_key(key),
        shortcut_modifiers: modifiers,
        state,
        typed: event.typed,
        digit: position_digit(event.keycode, event.typed, event.level),
        fallback: latin.is_some(),
        modifier: event.modifier,
    }
}

fn printable_ascii(key: Key) -> bool {
    (0x20..=0x7e).contains(&key.into_glib())
}

fn types_beyond_ascii(key: Key) -> bool {
    !printable_ascii(key)
        && key
            .to_unicode()
            .is_some_and(|character| !character.is_ascii() && !character.is_control())
}

/// Keypad keys act as the main keys they share a label with. Num Lock digits
/// stay keypad keys and count through `digit_in()`.
fn main_key(key: Key) -> Key {
    match key {
        Key::KP_Enter => Key::Return,
        Key::KP_Up => Key::Up,
        Key::KP_Down => Key::Down,
        Key::KP_Left => Key::Left,
        Key::KP_Right => Key::Right,
        Key::KP_Home => Key::Home,
        Key::KP_End => Key::End,
        Key::KP_Page_Up => Key::Page_Up,
        Key::KP_Page_Down => Key::Page_Down,
        Key::KP_Insert => Key::Insert,
        Key::KP_Delete => Key::Delete,
        Key::KP_Tab => Key::Tab,
        Key::KP_Space => Key::space,
        Key::KP_Add => Key::plus,
        Key::KP_Subtract => Key::minus,
        Key::KP_Multiply => Key::asterisk,
        Key::KP_Divide => Key::slash,
        Key::KP_Equal => Key::equal,
        _ => key,
    }
}

const DIGITS: [Key; 10] = [
    Key::_0,
    Key::_1,
    Key::_2,
    Key::_3,
    Key::_4,
    Key::_5,
    Key::_6,
    Key::_7,
    Key::_8,
    Key::_9,
];

const KEYPAD_DIGITS: [Key; 10] = [
    Key::KP_0,
    Key::KP_1,
    Key::KP_2,
    Key::KP_3,
    Key::KP_4,
    Key::KP_5,
    Key::KP_6,
    Key::KP_7,
    Key::KP_8,
    Key::KP_9,
];

fn digit_value(key: Key) -> Option<u8> {
    DIGITS
        .iter()
        .position(|digit| *digit == key)
        .map(|digit| digit as u8)
}

/// GDK keycodes are evdev codes plus 8 on X11 and Wayland; 10–19 are the digit
/// row, which counts by position at level 0 or 1. GDK reports no AltGr
/// modifier, so at a higher level the row counts only a digit it types.
/// Elsewhere a key counts as the digit it types at level 0 or 1, such as the
/// Hungarian 0 left of 1.
fn position_digit(keycode: u32, typed: Key, level: u32) -> Option<u8> {
    match keycode {
        10..=19 if level <= 1 => Some(((keycode - 9) % 10) as u8),
        10..=19 => digit_value(typed),
        _ => KEYPAD_DIGITS
            .iter()
            .position(|digit| *digit == typed)
            .map(|digit| digit as u8)
            .or_else(|| digit_value(typed).filter(|_| level <= 1)),
    }
}

/// The US-QWERTY characters at levels 0 and 1, by keycode.
fn us_qwerty(keycode: u32) -> Option<[Key; 2]> {
    Some(match keycode {
        10 => [Key::_1, Key::exclam],
        11 => [Key::_2, Key::at],
        12 => [Key::_3, Key::numbersign],
        13 => [Key::_4, Key::dollar],
        14 => [Key::_5, Key::percent],
        15 => [Key::_6, Key::asciicircum],
        16 => [Key::_7, Key::ampersand],
        17 => [Key::_8, Key::asterisk],
        18 => [Key::_9, Key::parenleft],
        19 => [Key::_0, Key::parenright],
        20 => [Key::minus, Key::underscore],
        21 => [Key::equal, Key::plus],
        24 => [Key::q, Key::Q],
        25 => [Key::w, Key::W],
        26 => [Key::e, Key::E],
        27 => [Key::r, Key::R],
        28 => [Key::t, Key::T],
        29 => [Key::y, Key::Y],
        30 => [Key::u, Key::U],
        31 => [Key::i, Key::I],
        32 => [Key::o, Key::O],
        33 => [Key::p, Key::P],
        34 => [Key::bracketleft, Key::braceleft],
        35 => [Key::bracketright, Key::braceright],
        38 => [Key::a, Key::A],
        39 => [Key::s, Key::S],
        40 => [Key::d, Key::D],
        41 => [Key::f, Key::F],
        42 => [Key::g, Key::G],
        43 => [Key::h, Key::H],
        44 => [Key::j, Key::J],
        45 => [Key::k, Key::K],
        46 => [Key::l, Key::L],
        47 => [Key::semicolon, Key::colon],
        48 => [Key::apostrophe, Key::quotedbl],
        49 => [Key::grave, Key::asciitilde],
        51 => [Key::backslash, Key::bar],
        52 => [Key::z, Key::Z],
        53 => [Key::x, Key::X],
        54 => [Key::c, Key::C],
        55 => [Key::v, Key::V],
        56 => [Key::b, Key::B],
        57 => [Key::n, Key::N],
        58 => [Key::m, Key::M],
        59 => [Key::comma, Key::less],
        60 => [Key::period, Key::greater],
        61 => [Key::slash, Key::question],
        _ => return None,
    })
}

fn us_position(key: Key) -> Option<(u32, u32)> {
    (10..=61).find_map(|keycode| {
        us_qwerty(keycode)?
            .iter()
            .position(|level| *level == key)
            .map(|level| (keycode, level as u32))
    })
}
