// SPDX-License-Identifier: MIT

use gtk::gdk::Key;

use crate::ui::keys::Binding;

catalog! {
    tenxer_only {
        CHOOSE_FOLDER: Binding = Binding::ctrl(Key::Return);
    }
}
