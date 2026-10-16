// SPDX-License-Identifier: MIT

use gtk::gdk::Key;

use crate::ui::keys::Binding;

catalog! {
    listed {
        OPEN_CONTAINING_FOLDER: Binding = Binding::alt(Key::Return);
    }
    tenxer_only {
        /// The second **d** of **d d**: confirms the 10xer Move to Trash dialog.
        TENXER_DELETE_CONFIRM: Binding = Binding::plain(Key::d), after super::TENXER_DELETE;
    }
}
