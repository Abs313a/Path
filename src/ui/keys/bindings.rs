// SPDX-License-Identifier: MIT

//! Every shortcut as a named constant, grouped by area. Handlers match these
//! constants, and the F1 reference, hints and labels show the same ones.

#[cfg(test)]
use super::{Binding, Digits};

/// Declares an area's constants and lists them for the catalog tests. The F1
/// reference shows `listed` constants in both maps, `default_only` and
/// `tenxer_only` ones in that map alone, and `unlisted` ones in neither. A
/// chord's second key names its first with `after`.
macro_rules! catalog {
    (@after) => { None };
    (@after $prefix:path) => { Some($prefix) };
    (
        $(listed {
            $($(#[$meta:meta])* $name:ident: $kind:ident = $value:expr
                $(, after $prefix:path)?;)*
        })?
        $(default_only {
            $($(#[$dmeta:meta])* $dname:ident: $dkind:ident = $dvalue:expr
                $(, after $dprefix:path)?;)*
        })?
        $(tenxer_only {
            $($(#[$tmeta:meta])* $tname:ident: $tkind:ident = $tvalue:expr
                $(, after $tprefix:path)?;)*
        })?
        $(unlisted {
            $($(#[$umeta:meta])* $uname:ident: $ukind:ident = $uvalue:expr;)*
        })?
    ) => {
        $($($(#[$meta])* pub(crate) const $name: $kind = $value;)*)?
        $($($(#[$dmeta])* pub(crate) const $dname: $dkind = $dvalue;)*)?
        $($($(#[$tmeta])* pub(crate) const $tname: $tkind = $tvalue;)*)?
        $($($(#[$umeta])* pub(crate) const $uname: $ukind = $uvalue;)*)?

        #[cfg(test)]
        pub(super) const LISTED: &[super::Listed] = &[
            $($(super::Listed {
                name: stringify!($name),
                entry: super::Entry::$kind($name),
                after: catalog!(@after $($prefix)?),
                maps: super::Maps::Both,
            },)*)?
            $($(super::Listed {
                name: stringify!($dname),
                entry: super::Entry::$dkind($dname),
                after: catalog!(@after $($dprefix)?),
                maps: super::Maps::Default,
            },)*)?
            $($(super::Listed {
                name: stringify!($tname),
                entry: super::Entry::$tkind($tname),
                after: catalog!(@after $($tprefix)?),
                maps: super::Maps::Tenxer,
            },)*)?
        ];
        #[cfg(test)]
        pub(super) const UNLISTED: &[(&str, super::Entry)] =
            &[$($((stringify!($uname), super::Entry::$ukind($uname)),)*)?];
    };
}

mod chooser;
mod dialogs;
mod navigation;
mod preview;
mod reference;
mod tenxer;
mod widgets;
mod window;

pub(crate) use chooser::*;
pub(crate) use dialogs::*;
pub(crate) use navigation::*;
pub(crate) use preview::*;
pub(crate) use reference::*;
pub(crate) use tenxer::*;
pub(crate) use widgets::*;
pub(crate) use window::*;

#[cfg(test)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum Entry {
    Binding(Binding),
    Digits(Digits),
}

#[cfg(test)]
#[derive(Clone, Copy, Debug)]
pub(super) struct Listed {
    pub(super) name: &'static str,
    pub(super) entry: Entry,
    /// The chord key this one follows.
    pub(super) after: Option<Binding>,
    pub(super) maps: Maps,
}

#[cfg(test)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum Maps {
    Both,
    Default,
    Tenxer,
}

#[cfg(test)]
impl Maps {
    pub(super) fn include(self, tenxer: bool) -> bool {
        match self {
            Self::Both => true,
            Self::Default => !tenxer,
            Self::Tenxer => tenxer,
        }
    }
}

#[cfg(test)]
pub(super) fn listed() -> impl Iterator<Item = Listed> {
    [
        chooser::LISTED,
        dialogs::LISTED,
        navigation::LISTED,
        preview::LISTED,
        reference::LISTED,
        tenxer::LISTED,
        widgets::LISTED,
        window::LISTED,
    ]
    .into_iter()
    .flatten()
    .copied()
}

#[cfg(test)]
pub(super) fn unlisted() -> impl Iterator<Item = (&'static str, Entry)> {
    [
        chooser::UNLISTED,
        dialogs::UNLISTED,
        navigation::UNLISTED,
        preview::UNLISTED,
        reference::UNLISTED,
        tenxer::UNLISTED,
        widgets::UNLISTED,
        window::UNLISTED,
    ]
    .into_iter()
    .flatten()
    .copied()
}
