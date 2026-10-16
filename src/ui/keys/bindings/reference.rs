// SPDX-License-Identifier: MIT

use gtk::gdk::Key;

use crate::ui::keys::Binding;

catalog! {
    listed {}
    unlisted {
        // The panel's own note lists these; they are not reference rows.
        REFERENCE_CATEGORIES: Binding = Binding::ctrl(Key::b);
        REFERENCE_SEARCH: Binding = Binding::ctrl(Key::f);
        REFERENCE_LIST: Binding = Binding::ctrl(Key::l);
    }
}
