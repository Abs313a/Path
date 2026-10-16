// SPDX-License-Identifier: MIT

use gtk::gdk::{Key, ModifierType as Modifiers};

use crate::ui::keys::{Binding, SHORTCUT_MODIFIERS};

catalog! {
    listed {
        UP: Binding = Binding::plain(Key::Up);
        DOWN: Binding = Binding::plain(Key::Down);
        LEFT: Binding = Binding::plain(Key::Left);
        RIGHT: Binding = Binding::plain(Key::Right);
        VIM_UP: Binding = Binding::plain(Key::k);
        VIM_DOWN: Binding = Binding::plain(Key::j);
        VIM_LEFT: Binding = Binding::plain(Key::h);
        VIM_RIGHT: Binding = Binding::plain(Key::l);
        FIRST_ITEM: Binding = Binding::plain(Key::Home);
        LAST_ITEM: Binding = Binding::plain(Key::End);
        FIRST_ITEM_UP: Binding = Binding::ctrl(Key::Up);
        LAST_ITEM_DOWN: Binding = Binding::ctrl(Key::Down);
        PAGE_UP: Binding = Binding::plain(Key::Page_Up);
        PAGE_DOWN: Binding = Binding::plain(Key::Page_Down);

        ENTER: Binding = Binding::plain(Key::Return);
        ESCAPE: Binding = Binding::plain(Key::Escape);
        SPACE: Binding = Binding::plain(Key::space);
        BACKSPACE: Binding = Binding::plain(Key::BackSpace);
        DELETE: Binding = Binding::plain(Key::Delete);
        DELETE_PERMANENTLY: Binding = Binding::shift(Key::Delete);
        FOCUS_NEXT: Binding = Binding::plain(Key::Tab);
        FOCUS_PREVIOUS: Binding = Binding::shift(Key::Tab);

        HISTORY_BACK: Binding = Binding::alt(Key::Left);
        HISTORY_FORWARD: Binding = Binding::alt(Key::Right);
        PARENT_FOLDER: Binding = Binding::alt(Key::Up);
        HOME_FOLDER: Binding = Binding::alt(Key::Home);
        OPEN_IN_NEW_TAB: Binding = Binding::ctrl(Key::Return);
        OPEN_IN_NEW_WINDOW: Binding = Binding::shift(Key::Return);
    }
    default_only {
        EXTEND_UP: Binding = Binding::shift(Key::Up);
        EXTEND_DOWN: Binding = Binding::shift(Key::Down);
        EXTEND_PAGE_UP: Binding = Binding::shift(Key::Page_Up);
        EXTEND_PAGE_DOWN: Binding = Binding::shift(Key::Page_Down);
        /// GTK's list views handle it; the reference names it.
        SELECTION_TOGGLE: Binding = Binding::ctrl(Key::space);
    }
    tenxer_only {
        /// Tab where it completes a path rather than moving focus.
        COMPLETE: Binding = Binding::plain(Key::Tab);
    }
    unlisted {
        // Range selection that GTK performs once the dispatcher passes the key on.
        EXTEND_LEFT: Binding = Binding::shift(Key::Left);
        EXTEND_RIGHT: Binding = Binding::shift(Key::Right);
        EXTEND_TO_FIRST: Binding = Binding::shift(Key::Home);
        EXTEND_TO_LAST: Binding = Binding::shift(Key::End);

        /// Escape with any modifiers, as dialogs and inline edits accept it.
        ESCAPE_ANY: Binding = ESCAPE.ignoring(SHORTCUT_MODIFIERS);
        /// Escape with or without Shift, as the listing, prompts and popovers accept it.
        ESCAPE_ANY_SHIFT: Binding = ESCAPE.ignoring(Modifiers::SHIFT_MASK);
        /// Enter with any modifiers, as confirmation dialogs accept it.
        ENTER_ANY: Binding = ENTER.ignoring(SHORTCUT_MODIFIERS);
        /// Enter with or without Shift, as the listing, prompts and popovers accept it.
        ENTER_ANY_SHIFT: Binding = ENTER.ignoring(Modifiers::SHIFT_MASK);
    }
}
