// SPDX-License-Identifier: MIT

use gtk::gdk::{Key, ModifierType as Modifiers};

use crate::ui::keys::{Binding, Digits};

catalog! {
    listed {
        COPY: Binding = Binding::ctrl(Key::c);
        CUT: Binding = Binding::ctrl(Key::x);
        PASTE: Binding = Binding::ctrl(Key::v);
        SELECT_ALL: Binding = Binding::ctrl(Key::a);
        UNDO: Binding = Binding::ctrl(Key::z);
        REDO: Binding = Binding::ctrl_shift(Key::z);
        REDO_Y: Binding = Binding::ctrl(Key::y);

        NEW_FOLDER: Binding = Binding::ctrl_shift(Key::n);
        NEW_FOLDER_WITH_SELECTION: Binding = Binding::ctrl_alt(Key::n);
        RENAME: Binding = Binding::plain(Key::F2);
        PROPERTIES: Binding = Binding::alt(Key::Return);
        CONTEXT_MENU: Binding = Binding::plain(Key::Menu);
        CONTEXT_MENU_F10: Binding = Binding::shift(Key::F10);

        SEARCH: Binding = Binding::ctrl(Key::k);
        LOCATION: Binding = Binding::ctrl(Key::l);
        REFRESH: Binding = Binding::plain(Key::F5);
        HIDDEN_FILES: Binding = Binding::ctrl(Key::h);
        HIDDEN_FILES_PERIOD: Binding = Binding::ctrl(Key::period);

        VIEW_COLUMNS: Binding = Binding::ctrl(Key::_1);
        VIEW_ICONS: Binding = Binding::ctrl(Key::_2);
        VIEW_LIST: Binding = Binding::ctrl(Key::_3);
        TEXT_LARGER: Binding = Binding::ctrl(Key::plus);
        TEXT_SMALLER: Binding = Binding::ctrl(Key::minus);
        TEXT_RESET: Binding = Binding::ctrl(Key::_0);
        SIDEBAR_FOCUS: Binding = Binding::ctrl_shift(Key::b);

        SETTINGS: Binding = Binding::ctrl(Key::comma);
        REFERENCE: Binding = Binding::plain(Key::F1);
        TENXER_MODE: Binding = Binding::ctrl_shift(Key::m);

        TAB_NEW: Binding = Binding::ctrl(Key::t);
        TAB_CLOSE: Binding = Binding::ctrl(Key::w);
        TAB_NEXT: Binding = Binding::ctrl(Key::Tab);
        TAB_PREVIOUS: Binding = Binding::ctrl_shift(Key::Tab);
        TAB_PREVIOUS_PAGE_UP: Binding = Binding::ctrl(Key::Page_Up);
        TAB_NEXT_PAGE_DOWN: Binding = Binding::ctrl(Key::Page_Down);
        TAB_MOVE_LEFT: Binding = Binding::ctrl_shift(Key::Page_Up);
        TAB_MOVE_RIGHT: Binding = Binding::ctrl_shift(Key::Page_Down);
        TAB_NUMBERS: Digits = Digits::new(
            Modifiers::CONTROL_MASK.union(Modifiers::SHIFT_MASK),
            9,
            true,
        );
    }
    default_only {
        // The 10xer map gives these keys to other commands or leaves them out.
        DUPLICATE: Binding = Binding::ctrl(Key::d);
        COPY_PATH: Binding = Binding::plain(Key::y);
        PIN: Binding = Binding::plain(Key::p);
        RENAME_R: Binding = Binding::ctrl(Key::r);
        JUMP_TO_FOLDER: Binding = Binding::ctrl_shift(Key::k);
        FILTER: Binding = Binding::ctrl(Key::f);
        TERMINAL: Binding = Binding::ctrl_alt(Key::t);
        ARROW_SCOPE: Binding = Binding::ctrl(Key::backslash);
        SIDEBAR: Binding = Binding::ctrl(Key::b);
    }
    unlisted {
        /// While type-to-search is on, **/** opens the filter without typing.
        FILTER_SLASH: Binding = Binding::plain(Key::slash);
        /// US keyboards type **+** with Shift+=; the reference shows only Ctrl++.
        TEXT_LARGER_EQUAL: Binding = Binding::ctrl(Key::equal);
    }
}
