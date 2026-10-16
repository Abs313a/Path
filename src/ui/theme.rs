// SPDX-License-Identifier: MIT

use std::{
    cell::{Cell, RefCell},
    fs, io,
    path::PathBuf,
    rc::Rc,
    time::Duration,
};

use gtk::{gdk, gio, glib, prelude::*};
use serde::{Deserialize, Serialize};
use sourceview5::prelude::BufferExt as _;

use super::preferences::{
    DistroVariant, FileIconColors, PreferenceManager, TextSize, desktop_text_scale_factor,
    notify_live, snapped_root_font_px,
};

mod distro;

thread_local! {
    static SHARED_MANAGER: RefCell<Option<Rc<ThemeManager>>> = const { RefCell::new(None) };
    static SOURCE_STYLE_PATH_INSTALLED: Cell<bool> = const { Cell::new(false) };
    static SOURCE_BUFFERS: RefCell<Vec<glib::WeakRef<sourceview5::Buffer>>> = const { RefCell::new(Vec::new()) };
    static DOCUMENT_BUFFERS: RefCell<Vec<glib::WeakRef<gtk::TextBuffer>>> = const { RefCell::new(Vec::new()) };
    static DOCUMENT_VIEWS: RefCell<Vec<glib::WeakRef<super::document_view::DocumentTextView>>> = const { RefCell::new(Vec::new()) };
    /// Installed on the first source preview buffer, so startup performs no SourceView I/O.
    static PENDING_STYLE_TOKENS: RefCell<Option<(ThemeTokens, Option<SourcePalette>)>> = const { RefCell::new(None) };
    static STYLE_SCHEME_DIRTY: Cell<bool> = const { Cell::new(true) };
}

const THEME_CATALOG: &str = include_str!("../../data/themes/catalog.toml");

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct ThemeTokens {
    pub name: String,
    pub background: String,
    pub surface: String,
    pub text: String,
    pub accent: String,
    #[serde(default = "default_danger")]
    pub danger: String,
    pub muted: String,
    pub highlight: String,
    pub border: String,
    pub dim_text: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub syntax_keyword: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub syntax_string: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub syntax_constant: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub syntax_type: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub syntax_preprocessor: Option<String>,
}

#[derive(Clone)]
struct SourcePalette {
    statement: String,
    string: String,
    constant: String,
    type_color: String,
    preprocessor: String,
}

#[derive(Clone, Debug)]
pub struct Theme {
    pub id: String,
    pub tokens: ThemeTokens,
    pub custom: bool,
}

#[derive(Deserialize)]
struct ThemeCatalog {
    themes: Vec<CatalogTheme>,
}

#[derive(Deserialize)]
struct CatalogTheme {
    id: String,
    #[serde(flatten)]
    tokens: ThemeTokens,
}

/// Appearance preferences that change the shared CSS or icon rendering the manager applies.
#[derive(Clone, Debug, PartialEq)]
struct AppearancePreferences {
    mode: String,
    theme: String,
    distro_variant: DistroVariant,
    text_size: TextSize,
    element_glow: bool,
    file_icon_colors: FileIconColors,
}

type ThemeRefreshPreference = dyn Fn(&gtk::Widget, &ThemeManager);

struct ThemePreferenceListener {
    active: Cell<bool>,
    anchor: glib::WeakRef<gtk::Widget>,
    refresh: Box<ThemeRefreshPreference>,
}

#[derive(Default)]
struct ThemeListeners {
    notifying: Cell<bool>,
    listeners: Rc<RefCell<Vec<Rc<ThemePreferenceListener>>>>,
}

impl ThemeListeners {
    fn bind<T: PartialEq + Clone + 'static>(
        &self,
        manager: &ThemeManager,
        anchor: &impl IsA<gtk::Widget>,
        read: impl Fn(&ThemeManager) -> T + 'static,
        apply: impl Fn(&gtk::Widget, T) + 'static,
    ) {
        let previous = RefCell::new(None);
        let listener = Rc::new(ThemePreferenceListener {
            active: Cell::new(true),
            anchor: anchor.as_ref().downgrade(),
            refresh: Box::new(move |widget, manager| {
                let value = read(manager);
                if previous.borrow().as_ref() == Some(&value) {
                    return;
                }
                previous.replace(Some(value.clone()));
                apply(widget, value);
            }),
        });
        self.listeners.borrow_mut().push(listener.clone());
        let weak_listeners = Rc::downgrade(&self.listeners);
        let weak_listener = Rc::downgrade(&listener);
        anchor.connect_destroy(move |_| {
            if let Some(listener) = weak_listener.upgrade() {
                listener.active.set(false);
            }
            if let Some(listeners) = weak_listeners.upgrade() {
                listeners.borrow_mut().retain(|candidate| {
                    !std::rc::Weak::ptr_eq(&Rc::downgrade(candidate), &weak_listener)
                });
            }
        });
        (listener.refresh)(anchor.as_ref(), manager);
    }

    fn notify(&self, manager: &ThemeManager) {
        if self.notifying.replace(true) {
            return;
        }
        notify_live(
            &self.listeners,
            |listener| listener.active.get() && listener.anchor.upgrade().is_some(),
            |listener| {
                if listener.active.get()
                    && let Some(anchor) = listener.anchor.upgrade()
                {
                    (listener.refresh)(&anchor, manager);
                }
            },
        );
        self.notifying.set(false);
    }
}

pub struct ThemeManager {
    provider: gtk::CssProvider,
    themes: RefCell<Vec<Theme>>,
    preferences: Rc<PreferenceManager>,
    distro_available: Cell<bool>,
    distro_monitors: RefCell<Vec<gio::FileMonitor>>,
    pending_distro_refresh: RefCell<Option<glib::SourceId>>,
    preview: RefCell<Option<ThemeTokens>>,
    preview_generation: Cell<u64>,
    /// Distro state can be unreadable mid-switch while the window keeps these colors.
    applied_distro_tokens: RefCell<Option<ThemeTokens>>,
    appearance: RefCell<AppearancePreferences>,
    theme_listeners: ThemeListeners,
    active_model_palette: Cell<crate::services::ModelPalette>,
}

impl ThemeManager {
    pub fn shared() -> Rc<Self> {
        let existing = SHARED_MANAGER.with(|shared| shared.borrow().clone());
        if let Some(manager) = existing {
            return manager;
        }
        let manager = Self::load();
        SHARED_MANAGER.with(|shared| shared.replace(Some(manager.clone())));
        manager
    }

    fn load() -> Rc<Self> {
        let preferences = PreferenceManager::shared();
        let themes = merge_builtin_and_custom_themes(builtins(), load_custom_themes());
        let distro_available = load_distro_theme(DistroVariant::Original).is_some();
        preferences.normalize_loaded_theme_selection(
            |id| themes.iter().any(|theme| theme.id == id),
            distro_available,
        );
        let appearance = AppearancePreferences {
            mode: preferences.theme_mode(),
            theme: preferences.selected_theme_id(),
            distro_variant: preferences.distro_variant(),
            text_size: preferences.text_size(),
            element_glow: preferences.element_glow(),
            file_icon_colors: preferences.file_icon_colors(),
        };

        let manager = Rc::new(Self {
            provider: gtk::CssProvider::new(),
            themes: RefCell::new(themes),
            preferences: preferences.clone(),
            distro_available: Cell::new(distro_available),
            distro_monitors: RefCell::new(Vec::new()),
            pending_distro_refresh: RefCell::new(None),
            preview: RefCell::new(None),
            preview_generation: Cell::new(0),
            applied_distro_tokens: RefCell::new(None),
            appearance: RefCell::new(appearance),
            theme_listeners: ThemeListeners::default(),
            active_model_palette: Cell::new(crate::services::ModelPalette {
                accent: 0,
                surface: 0,
            }),
        });
        let weak = Rc::downgrade(&manager);
        preferences.observe(Rc::new(move || {
            if let Some(manager) = weak.upgrade() {
                manager.on_preferences_changed();
            }
        }));
        pin_manual_font_rendering();
        manager.install_provider();
        manager.apply_selected();
        manager.monitor_text_scaling();
        manager.monitor_distro();
        manager
    }

    pub fn themes(&self) -> Vec<Theme> {
        self.themes.borrow().clone()
    }

    pub fn is_distro_available(&self) -> bool {
        self.distro_available.get()
    }

    pub fn follows_distro(&self) -> bool {
        self.preferences.theme_mode() == "distro"
    }

    pub fn selected_id(&self) -> String {
        self.preferences.selected_theme_id()
    }

    pub(crate) fn active_model_palette(&self) -> crate::services::ModelPalette {
        self.active_model_palette.get()
    }

    /// Applies the current value immediately, then only changes to that value.
    /// Capture weak references to owned widgets/state; the anchor owns the binding's lifetime.
    pub(crate) fn bind_theme_preference<T: PartialEq + Clone + 'static>(
        &self,
        anchor: &impl IsA<gtk::Widget>,
        read: impl Fn(&Self) -> T + 'static,
        apply: impl Fn(&gtk::Widget, T) + 'static,
    ) {
        self.theme_listeners.bind(self, anchor, read, apply);
    }

    pub fn select_theme(&self, id: &str) {
        if !self.themes.borrow().iter().any(|theme| theme.id == id) {
            return;
        }
        self.preview.take();
        let changed = self.follows_distro() || self.selected_id() != id;
        self.preferences.set_theme_selection("theme", Some(id));
        if !changed {
            // Re-selecting the current theme restores it after a live preview.
            self.apply_selected();
        }
    }

    pub fn set_follow_distro(&self, enabled: bool) {
        if enabled && !self.is_distro_available() {
            return;
        }
        self.preview.take();
        let changed = self.follows_distro() != enabled;
        let mode = if enabled { "distro" } else { "theme" };
        self.preferences.set_theme_selection(mode, None);
        if !changed {
            self.apply_selected();
        }
    }

    /// Applies `tokens` until [`Self::cancel_preview`] or a theme selection; appearance
    /// changes in the meantime re-apply the preview rather than the saved theme.
    /// Returns the preview's generation for [`Self::cancel_preview_from`].
    pub fn preview(&self, tokens: &ThemeTokens) -> Option<u64> {
        validate_tokens(tokens).ok()?;
        self.preview.replace(Some(tokens.clone()));
        self.preview_generation
            .set(self.preview_generation.get().wrapping_add(1));
        self.apply_tokens(tokens, None);
        Some(self.preview_generation.get())
    }

    pub fn cancel_preview(&self) {
        if self.preview.take().is_some() {
            self.apply_selected();
        }
    }

    /// Cancels the preview only if no later one has replaced it.
    pub fn cancel_preview_from(&self, generation: u64) {
        if self.preview_generation.get() == generation {
            self.cancel_preview();
        }
    }

    #[cfg(test)]
    pub(crate) fn is_previewing(&self) -> bool {
        self.preview.borrow().is_some()
    }

    pub fn save_custom_theme(&self, tokens: ThemeTokens) -> io::Result<String> {
        validate_tokens(&tokens)
            .map_err(|message| io::Error::new(io::ErrorKind::InvalidInput, message))?;
        let directory = themes_directory();
        fs::create_dir_all(&directory)?;
        // Never replace a file already there, even one that did not load: it may be
        // a broken or newly linked dotfile the user still wants.
        let id = custom_theme_id(&tokens.name, |candidate| {
            self.themes
                .borrow()
                .iter()
                .any(|theme| theme.id == candidate)
                || fs::symlink_metadata(directory.join(format!("{candidate}.toml"))).is_ok()
        });
        let path = directory.join(format!("{id}.toml"));
        let value = toml::to_string_pretty(&tokens).map_err(io::Error::other)?;
        crate::storage::atomic_write_config(&path, value.as_bytes())?;

        self.themes.borrow_mut().push(Theme {
            id: id.clone(),
            tokens,
            custom: true,
        });
        self.select_theme(&id);
        Ok(id)
    }

    pub fn appearance_tokens(&self) -> ThemeTokens {
        if self.follows_distro()
            && let Some(tokens) = load_distro_theme(self.preferences.distro_variant())
                .or_else(|| self.applied_distro_tokens.borrow().clone())
        {
            return tokens;
        }
        self.starter_tokens()
    }

    pub fn starter_tokens(&self) -> ThemeTokens {
        self.current_tokens().unwrap_or_else(azure_tokens)
    }

    fn install_provider(&self) {
        if let Some(display) = gdk::Display::default() {
            gtk::style_context_add_provider_for_display(
                &display,
                &self.provider,
                gtk::STYLE_PROVIDER_PRIORITY_APPLICATION + 1,
            );
        }
    }

    fn apply_selected(&self) {
        let preview = self.preview.borrow().clone();
        if let Some(tokens) = preview {
            self.apply_tokens(&tokens, None);
            return;
        }
        if self.follows_distro() {
            if let Some(tokens) = load_distro_theme(self.preferences.distro_variant()) {
                self.applied_distro_tokens.replace(Some(tokens.clone()));
                let palette = load_distro_source_palette();
                self.apply_tokens(&tokens, palette.as_ref());
            }
            return;
        }
        self.applied_distro_tokens.take();
        if let Some(tokens) = self.current_tokens() {
            self.apply_tokens(&tokens, None);
        }
    }

    pub(in crate::ui) fn current_tokens(&self) -> Option<ThemeTokens> {
        let id = self.preferences.selected_theme_id();
        self.themes
            .borrow()
            .iter()
            .find(|theme| theme.id == id)
            .map(|theme| theme.tokens.clone())
    }

    fn apply_tokens(&self, tokens: &ThemeTokens, source_palette: Option<&SourcePalette>) {
        let color = |value: &str| {
            let [red, green, blue] = parse_rgb_channels(value).unwrap_or_default();
            (u32::from(red) << 16) | (u32::from(green) << 8) | u32::from(blue)
        };
        self.active_model_palette
            .set(crate::services::ModelPalette {
                accent: color(&tokens.accent),
                surface: color(&tokens.surface),
            });
        super::document_media::apply_theme(tokens);
        super::browser::find::apply_theme(&tokens.accent, &tokens.background);
        super::preview::audio::apply_theme(tokens);
        let root_font_px = snapped_root_font_px(
            self.preferences.text_size().root_font_px(),
            desktop_text_scale_factor(),
        );
        let glow = if self.preferences.element_glow() {
            "@pathfm_accent"
        } else {
            "transparent"
        };
        self.provider.load_from_string(&format!(
            "{}\n@define-color pathfm_glow {glow};\n",
            tokens_css(tokens, root_font_px)
        ));
        apply_interface_font(root_font_px);
        crate::assets::set_interface_icon_scale(root_font_px / 13.0);
        let dark_background =
            parse_rgb_channels(&tokens.background).is_none_or(|[red, green, blue]| {
                u32::from(red) * 299 + u32::from(green) * 587 + u32::from(blue) * 114 < 128_000
            });
        crate::assets::set_catppuccin_flavor(crate::assets::CatppuccinFlavor::for_dark_background(
            dark_background,
        ));
        crate::assets::set_catppuccin_theme_colors(
            self.preferences.file_icon_colors() == FileIconColors::Theme,
        );
        // SVG strokes accept fewer color forms than GTK does.
        crate::assets::set_primary_icon_color(&color_to_hex(&tokens.accent));
        crate::assets::set_text_icon_color(&color_to_hex(&tokens.text));
        crate::assets::set_danger_icon_color(&color_to_hex(&tokens.danger));
        super::thumbnail::refresh_all_customized_icons();
        stage_source_style_scheme(tokens, source_palette);
        style_document_buffers(tokens);
        style_document_views(tokens);
        self.theme_listeners.notify(self);
    }

    fn on_preferences_changed(&self) {
        let appearance = AppearancePreferences {
            mode: self.preferences.theme_mode(),
            theme: self.preferences.selected_theme_id(),
            distro_variant: self.preferences.distro_variant(),
            text_size: self.preferences.text_size(),
            element_glow: self.preferences.element_glow(),
            file_icon_colors: self.preferences.file_icon_colors(),
        };
        if *self.appearance.borrow() != appearance {
            self.appearance.replace(appearance);
            self.apply_selected();
        }
        self.theme_listeners.notify(self);
    }

    fn monitor_text_scaling(self: &Rc<Self>) {
        let Some(settings) = gtk::Settings::default() else {
            return;
        };
        let weak = Rc::downgrade(self);
        settings.connect_gtk_xft_dpi_notify(move |_| {
            let Some(manager) = weak.upgrade() else {
                return;
            };
            manager.apply_selected();
        });
    }

    fn monitor_distro(self: &Rc<Self>) {
        for monitor in self.distro_monitors.take() {
            monitor.cancel();
        }
        let state = distro_state_dir();
        let home = glib::home_dir();
        // Ancestor watches survive moving away or replacing the current state tree.
        let theme = state.join("theme");
        for path in std::iter::once(theme.as_path())
            .chain(state.ancestors().take_while(|path| path.starts_with(&home)))
        {
            if !path.is_dir() {
                continue;
            }
            let file = gio::File::for_path(path);
            let Ok(monitor) =
                file.monitor_directory(gio::FileMonitorFlags::NONE, gio::Cancellable::NONE)
            else {
                continue;
            };
            let weak = Rc::downgrade(self);
            monitor.connect_changed(move |_, file, other_file, _| {
                if !is_distro_theme_event(file)
                    && !other_file
                        .as_ref()
                        .is_some_and(|file| is_distro_theme_event(file))
                {
                    return;
                }
                let Some(manager) = weak.upgrade() else {
                    return;
                };
                if let Some(pending) = manager.pending_distro_refresh.borrow_mut().take() {
                    pending.remove();
                }
                let weak = weak.clone();
                let refresh = glib::timeout_add_local_once(Duration::from_millis(75), move || {
                    let Some(manager) = weak.upgrade() else {
                        return;
                    };
                    manager.pending_distro_refresh.borrow_mut().take();
                    manager.refresh_distro_state();
                });
                manager.pending_distro_refresh.replace(Some(refresh));
            });
            self.distro_monitors.borrow_mut().push(monitor);
        }
    }

    pub(in crate::ui) fn refresh_distro_state(self: &Rc<Self>) {
        self.monitor_distro();
        let available = load_distro_theme(DistroVariant::Original).is_some()
            || (self.is_distro_available() && distro_state_dir().join("theme.name").is_file());
        let availability_changed = self.distro_available.replace(available) != available;
        if !available && self.follows_distro() {
            self.preview.take();
            self.preferences.set_theme_selection("theme", None);
            return;
        }
        if availability_changed {
            self.preferences.notify_changes();
            return;
        }
        if self.follows_distro() {
            self.apply_selected();
            self.preferences.notify_changes();
        }
    }
}

fn is_distro_theme_event(file: &gio::File) -> bool {
    file.path().is_some_and(|path| {
        let state = distro_state_dir();
        state.starts_with(&path)
            || path == state.join("theme")
            || path == state.join("theme.name")
            || path == state.join("theme/colors.toml")
    })
}

fn builtins() -> Vec<Theme> {
    let mut themes: Vec<_> = toml::from_str::<ThemeCatalog>(THEME_CATALOG)
        .map(|catalog| {
            catalog
                .themes
                .into_iter()
                .map(|theme| Theme {
                    id: theme.id,
                    tokens: theme.tokens,
                    custom: false,
                })
                .collect()
        })
        .unwrap_or_default();
    themes.sort_by_key(|theme| theme.tokens.name.to_lowercase());
    themes
}

fn merge_builtin_and_custom_themes(mut builtins: Vec<Theme>, custom: Vec<Theme>) -> Vec<Theme> {
    builtins.retain(|builtin| !custom.iter().any(|theme| theme.id == builtin.id));
    builtins.extend(custom);
    builtins
}

fn azure_tokens() -> ThemeTokens {
    builtins()
        .into_iter()
        .find(|theme| theme.id == "azure-glow")
        .map(|theme| theme.tokens)
        .unwrap_or_else(|| ThemeTokens {
            name: "Azure Glow".to_owned(),
            background: "#0c1a2b".to_owned(),
            surface: "#122438".to_owned(),
            text: "#c9deed".to_owned(),
            accent: "#4fd6ff".to_owned(),
            danger: default_danger(),
            muted: "#1e3a52".to_owned(),
            highlight: "#244d68".to_owned(),
            border: "#315b75".to_owned(),
            dim_text: "#6f8da3".to_owned(),
            syntax_keyword: None,
            syntax_string: None,
            syntax_constant: None,
            syntax_type: None,
            syntax_preprocessor: None,
        })
}

fn load_custom_themes() -> Vec<Theme> {
    let Ok(entries) = fs::read_dir(themes_directory()) else {
        return Vec::new();
    };
    let mut themes: Vec<_> = entries
        .filter_map(Result::ok)
        .filter(|entry| {
            entry
                .path()
                .extension()
                .is_some_and(|extension| extension == "toml")
        })
        .filter_map(|entry| {
            let id = entry.path().file_stem()?.to_string_lossy().into_owned();
            let source = fs::read_to_string(entry.path()).ok()?;
            let mut tokens: ThemeTokens = toml::from_str(&source).ok()?;
            validate_tokens(&tokens).ok()?;
            // Canonical in memory only; the user's file stays as written.
            for color in tokens.color_fields_mut() {
                *color = canonical_color(color)?;
            }
            Some(Theme {
                id,
                tokens,
                custom: true,
            })
        })
        .collect();
    themes.sort_by(|left, right| left.tokens.name.cmp(&right.tokens.name));
    themes
}

fn load_distro_theme(variant: DistroVariant) -> Option<ThemeTokens> {
    let state = distro_state_dir();
    let name = fs::read_to_string(state.join("theme.name")).ok()?;
    let colors = fs::read_to_string(state.join("theme/colors.toml")).ok()?;
    tokens_from_quattro(name.trim(), &colors, variant)
}

fn load_distro_source_palette() -> Option<SourcePalette> {
    let colors = fs::read_to_string(distro_state_dir().join("theme/colors.toml")).ok()?;
    source_palette_from_quattro(&colors)
}

fn tokens_from_quattro(name: &str, source: &str, variant: DistroVariant) -> Option<ThemeTokens> {
    let values: toml::Value = toml::from_str(source).ok()?;
    let get = |key: &str| quattro_color(&values, key);
    let source_background = get("background")?;
    let text = get("foreground")?;
    let accent = get("accent")?;
    let selection = get("selection").unwrap_or_else(|| accent.clone());
    let shadow = get("color8").unwrap_or_else(|| source_background.clone());
    let mut tokens = ThemeTokens {
        name: title_case_slug(name),
        background: blend(&source_background, &shadow, 0.35),
        surface: blend(&source_background, &shadow, 0.65),
        muted: blend(&shadow, &text, 0.10),
        highlight: selection,
        border: blend(&shadow, &text, 0.36),
        dim_text: blend(&source_background, &text, 0.62),
        text,
        accent,
        danger: get("color1").unwrap_or_else(default_danger),
        syntax_keyword: get("magenta").or_else(|| get("color5")),
        syntax_string: get("green").or_else(|| get("color2")),
        syntax_constant: get("orange").or_else(|| get("color9")),
        syntax_type: get("cyan").or_else(|| get("color3")),
        syntax_preprocessor: get("yellow"),
    };
    if variant != DistroVariant::Original {
        let palette = source_palette_from_quattro(source);
        distro::apply_variant(&mut tokens, &source_background, variant, palette.as_ref());
    }
    Some(tokens)
}

fn source_palette_from_quattro(source: &str) -> Option<SourcePalette> {
    let values: toml::Value = toml::from_str(source).ok()?;
    let get = |key: &str| quattro_color(&values, key);
    Some(SourcePalette {
        statement: get("magenta").or_else(|| get("blue"))?,
        string: get("green")?,
        constant: get("orange").or_else(|| get("yellow"))?,
        type_color: get("cyan").or_else(|| get("blue"))?,
        preprocessor: get("yellow")?,
    })
}

/// Quattro values reach GTK CSS, GtkSourceView XML and SVG strokes, so a value GTK
/// cannot parse is treated as missing; callers decide whether that is fatal.
fn quattro_color(values: &toml::Value, key: &str) -> Option<String> {
    canonical_color(values.get(key)?.as_str()?)
}

fn default_danger() -> String {
    "#e5484d".to_owned()
}

fn validate_tokens(tokens: &ThemeTokens) -> Result<(), &'static str> {
    if tokens.name.trim().is_empty() {
        return Err("Enter a theme name");
    }
    if tokens
        .color_fields()
        .any(|color| gdk::RGBA::parse(color).is_err())
    {
        return Err("Every color must be a valid CSS color");
    }
    Ok(())
}

fn source_style_scheme() -> Option<sourceview5::StyleScheme> {
    sourceview5::StyleSchemeManager::default().scheme("pathfm-current")
}

pub(super) fn register_source_buffer(buffer: &sourceview5::Buffer) {
    ensure_source_style_scheme_installed();
    buffer.set_style_scheme(source_style_scheme().as_ref());
    SOURCE_BUFFERS.with(|buffers| {
        let mut buffers = buffers.borrow_mut();
        buffers.retain(|buffer| buffer.upgrade().is_some());
        let weak = glib::WeakRef::new();
        weak.set(Some(buffer));
        buffers.push(weak);
    });
}

pub(super) fn register_document_buffer(buffer: &gtk::TextBuffer) {
    let tokens = ThemeManager::shared().appearance_tokens();
    style_document_buffer(buffer, &tokens);
    DOCUMENT_BUFFERS.with(|buffers| {
        let mut buffers = buffers.borrow_mut();
        buffers.retain(|buffer| buffer.upgrade().is_some());
        let weak = glib::WeakRef::new();
        weak.set(Some(buffer));
        buffers.push(weak);
    });
}

pub(super) fn register_document_view(view: &super::document_view::DocumentTextView) {
    let tokens = ThemeManager::shared().appearance_tokens();
    style_document_view(view, &tokens);
    DOCUMENT_VIEWS.with(|views| {
        let mut views = views.borrow_mut();
        views.retain(|view| view.upgrade().is_some());
        let weak = glib::WeakRef::new();
        weak.set(Some(view));
        views.push(weak);
    });
}

fn style_document_buffers(tokens: &ThemeTokens) {
    DOCUMENT_BUFFERS.with(|buffers| {
        buffers.borrow_mut().retain(|buffer| {
            let Some(buffer) = buffer.upgrade() else {
                return false;
            };
            style_document_buffer(&buffer, tokens);
            true
        });
    });
}

fn style_document_views(tokens: &ThemeTokens) {
    DOCUMENT_VIEWS.with(|views| {
        views.borrow_mut().retain(|view| {
            let Some(view) = view.upgrade() else {
                return false;
            };
            style_document_view(&view, tokens);
            true
        });
    });
}

fn style_document_view(view: &super::document_view::DocumentTextView, tokens: &ThemeTokens) {
    if let (Ok(fill), Ok(border), Ok(selection)) = (
        gdk::RGBA::parse(blend(&tokens.surface, &tokens.muted, 0.54)),
        gdk::RGBA::parse(blend(&tokens.surface, &tokens.border, 0.5)),
        gdk::RGBA::parse(&tokens.accent),
    ) {
        view.set_colors(fill, border, selection);
    }
}

fn style_document_buffer(buffer: &gtk::TextBuffer, tokens: &ThemeTokens) {
    let parse = |value: &str| gdk::RGBA::parse(value).ok();
    let table = buffer.tag_table();
    if let Some(color) = parse(&tokens.accent) {
        for name in ["document-accent", "document-link"] {
            if let Some(tag) = table.lookup(name) {
                tag.set_foreground_rgba(Some(&color));
            }
        }
    }
    if let Some(color) = parse(&tokens.dim_text)
        && let Some(tag) = table.lookup("document-dim")
    {
        tag.set_foreground_rgba(Some(&color));
    }
    if let Some(color) = parse(&tokens.text)
        && let Some(tag) = table.lookup("document-link-hover")
    {
        tag.set_foreground_rgba(Some(&color));
    }
    if let Some(color) = parse(&tokens.background)
        && let Some(tag) = table.lookup("document-selection")
    {
        tag.set_foreground_rgba(Some(&color));
    }
    if let Some(mut color) = parse(&tokens.highlight) {
        color.set_alpha(0.36);
        if let Some(tag) = table.lookup("document-quote") {
            tag.set_paragraph_background_rgba(Some(&color));
        }
        color.set_alpha(0.5);
        if let Some(tag) = table.lookup("document-link-hover") {
            tag.set_background_rgba(Some(&color));
        }
    }
}

fn stage_source_style_scheme(tokens: &ThemeTokens, source_palette: Option<&SourcePalette>) {
    PENDING_STYLE_TOKENS
        .with(|pending| pending.replace(Some((tokens.clone(), source_palette.cloned()))));
    STYLE_SCHEME_DIRTY.with(|dirty| dirty.set(true));
    let live = SOURCE_BUFFERS.with(|buffers| {
        buffers
            .borrow_mut()
            .retain(|buffer| buffer.upgrade().is_some());
        !buffers.borrow().is_empty()
    });
    if live {
        ensure_source_style_scheme_installed();
    }
}

/// Writes the staged scheme and rescans the style manager, once per staged token set.
fn ensure_source_style_scheme_installed() {
    if !STYLE_SCHEME_DIRTY.with(|dirty| dirty.get()) {
        return;
    }
    let pending = PENDING_STYLE_TOKENS.with(|pending| pending.borrow().clone());
    let Some((tokens, palette)) = pending else {
        return;
    };
    let directory = glib::user_cache_dir().join("pathfm").join("source-styles");
    if let Err(error) = fs::create_dir_all(&directory).and_then(|()| {
        let value = source_style_scheme_xml(&tokens, palette.as_ref());
        crate::storage::atomic_write(&directory.join("pathfm-current.xml"), value.as_bytes())
    }) {
        tracing::warn!(%error, "unable to write preview syntax style");
        return;
    }

    let manager = sourceview5::StyleSchemeManager::default();
    SOURCE_STYLE_PATH_INSTALLED.with(|installed| {
        if !installed.replace(true) {
            manager.append_search_path(&directory.to_string_lossy());
        }
    });
    manager.force_rescan();
    STYLE_SCHEME_DIRTY.with(|dirty| dirty.set(false));
    let scheme = manager.scheme("pathfm-current");
    SOURCE_BUFFERS.with(|buffers| {
        buffers.borrow_mut().retain(|buffer| {
            let Some(buffer) = buffer.upgrade() else {
                return false;
            };
            buffer.set_style_scheme(scheme.as_ref());
            true
        });
    });
}

fn resolved_source_palette(tokens: &ThemeTokens, palette: Option<&SourcePalette>) -> SourcePalette {
    let fallback = SourcePalette {
        statement: tokens.accent.clone(),
        string: blend(&tokens.accent, &tokens.text, 0.48),
        constant: blend(&tokens.accent, &tokens.text, 0.18),
        type_color: blend(&tokens.accent, &tokens.text, 0.24),
        preprocessor: blend(&tokens.accent, &tokens.text, 0.32),
    };
    let palette = palette.unwrap_or(&fallback);
    let resolve = |token: &Option<String>, fallback: &str| {
        token
            .as_deref()
            .filter(|value| gdk::RGBA::parse(*value).is_ok())
            .unwrap_or(fallback)
            .to_owned()
    };
    SourcePalette {
        statement: resolve(&tokens.syntax_keyword, &palette.statement),
        string: resolve(&tokens.syntax_string, &palette.string),
        constant: resolve(&tokens.syntax_constant, &palette.constant),
        type_color: resolve(&tokens.syntax_type, &palette.type_color),
        preprocessor: resolve(&tokens.syntax_preprocessor, &palette.preprocessor),
    }
}

impl ThemeTokens {
    // Exhaustive destructuring makes a new field fail to compile until it is classified.
    fn color_fields(&self) -> impl Iterator<Item = &String> {
        let Self {
            name: _,
            background,
            surface,
            text,
            accent,
            danger,
            muted,
            highlight,
            border,
            dim_text,
            syntax_keyword,
            syntax_string,
            syntax_constant,
            syntax_type,
            syntax_preprocessor,
        } = self;
        [
            background, surface, text, accent, danger, muted, highlight, border, dim_text,
        ]
        .into_iter()
        .chain(
            [
                syntax_keyword,
                syntax_string,
                syntax_constant,
                syntax_type,
                syntax_preprocessor,
            ]
            .into_iter()
            .flatten(),
        )
    }

    fn color_fields_mut(&mut self) -> impl Iterator<Item = &mut String> {
        let Self {
            name: _,
            background,
            surface,
            text,
            accent,
            danger,
            muted,
            highlight,
            border,
            dim_text,
            syntax_keyword,
            syntax_string,
            syntax_constant,
            syntax_type,
            syntax_preprocessor,
        } = self;
        [
            background, surface, text, accent, danger, muted, highlight, border, dim_text,
        ]
        .into_iter()
        .chain(
            [
                syntax_keyword,
                syntax_string,
                syntax_constant,
                syntax_type,
                syntax_preprocessor,
            ]
            .into_iter()
            .flatten(),
        )
    }

    pub(super) fn initialize_syntax_colors(&mut self) {
        let palette = resolved_source_palette(self, None);
        self.syntax_keyword = Some(palette.statement);
        self.syntax_string = Some(palette.string);
        self.syntax_constant = Some(palette.constant);
        self.syntax_type = Some(palette.type_color);
        self.syntax_preprocessor = Some(palette.preprocessor);
    }
}

fn source_style_scheme_xml(tokens: &ThemeTokens, palette: Option<&SourcePalette>) -> String {
    let palette = resolved_source_palette(tokens, palette);
    format!(
        r#"<?xml version="1.0" encoding="UTF-8"?>
<style-scheme id="pathfm-current" _name="Path Current Theme" version="1.0">
  <color name="background" value="{}"/>
  <color name="surface" value="{}"/>
  <color name="text" value="{}"/>
  <color name="accent" value="{}"/>
  <color name="danger" value="{}"/>
  <color name="selection" value="{}"/>
  <color name="dim" value="{}"/>
  <color name="string" value="{}"/>
  <color name="constant" value="{}"/>
  <color name="type" value="{}"/>
  <color name="statement" value="{}"/>
  <color name="preprocessor" value="{}"/>
  <style name="text" foreground="text" background="surface"/>
  <style name="selection" foreground="background" background="accent"/>
  <style name="cursor" foreground="accent"/>
  <style name="current-line" background="background"/>
  <style name="line-numbers" foreground="dim" background="background"/>
  <style name="def:comment" foreground="dim" italic="true"/>
  <style name="def:shebang" foreground="dim" bold="true"/>
  <style name="def:string" foreground="string"/>
  <style name="def:constant" foreground="constant"/>
  <style name="def:special-char" foreground="constant"/>
  <style name="def:identifier" foreground="text"/>
  <style name="def:statement" foreground="statement" bold="true"/>
  <style name="def:type" foreground="type" bold="true"/>
  <style name="def:preprocessor" foreground="preprocessor"/>
  <style name="def:heading" foreground="accent" bold="true"/>
  <style name="def:link-destination" foreground="string" underline="single"/>
  <style name="def:error" foreground="background" background="danger" bold="true"/>
</style-scheme>
"#,
        color_to_hex(&tokens.background),
        color_to_hex(&tokens.surface),
        color_to_hex(&tokens.text),
        color_to_hex(&tokens.accent),
        color_to_hex(&tokens.danger),
        color_to_hex(&tokens.highlight),
        color_to_hex(&tokens.dim_text),
        color_to_hex(&palette.string),
        color_to_hex(&palette.constant),
        color_to_hex(&palette.type_color),
        color_to_hex(&palette.statement),
        color_to_hex(&palette.preprocessor),
    )
}

const INTERFACE_FONT_FAMILY: &str = "JetBrains Mono";

fn interface_font_name(root_font_px: f64) -> String {
    format!("{INTERFACE_FONT_FAMILY} {root_font_px:.6}px")
}

/// GTK's automatic font rendering hints glyph outlines but not their metrics,
/// so GPU glyph atlas slots are sized from unhinted extents and lose the top
/// pixel row at some sizes (GNOME/gtk#8395). Manual rendering hints metrics
/// too and follows the desktop's hinting settings. Application values outrank
/// the settings portal, so this holds for the whole process.
fn pin_manual_font_rendering() {
    let Some(settings) = gtk::Settings::default() else {
        return;
    };
    let Some(property) = settings.find_property("gtk-font-rendering") else {
        return;
    };
    let Some(manual) = glib::EnumClass::with_type(property.value_type())
        .and_then(|class| class.to_value_by_nick("manual"))
    else {
        return;
    };
    settings.set_property("gtk-font-rendering", manual);
}

fn apply_interface_font(root_font_px: f64) {
    if let Some(settings) = gtk::Settings::default() {
        settings.set_gtk_font_name(Some(&interface_font_name(root_font_px)));
    }
}

fn tokens_css(tokens: &ThemeTokens, root_font_px: f64) -> String {
    let scale = root_font_px / 13.0;
    let header = (40.0 * scale).round();
    // Column headers add six pixels of padding and three extra border pixels.
    let column_header = header - 9.0;
    let control = (24.0 * scale).round();
    let browser_header = (control + 8.0).max(36.0);
    // Miller headers keep their three-pixel indicator, bottom border and balancing inset.
    let browser_column_header = browser_header - 6.0;
    let sizing = format!(
        "headerbar, headerbar > windowhandle > box, .mode-pane-header, .preview-header {{ min-height: {header}px; }}\n.column-header {{ min-height: {column_header}px; }}\nheaderbar .sidebar-toggle, button.header-action, headerbar menubutton.header-action > button, .preview-header-action, button.column-header-action, menubutton.column-header-action > button {{ min-width: {control}px; min-height: {control}px; }}\n.file-operation-card button.progress-card-action {{ min-width: 0; min-height: 0; }}\n.tab-strip, headerbar.browser-header, headerbar.browser-header > windowhandle > box, .mode-pane-header, .preview-header {{ min-height: {browser_header}px; }}\n.directory-column .column-header {{ min-height: {browser_column_header}px; }}\n.mode-pane-header .list-navigation-button, .sidebar-row > box > image, .sidebar-device-action {{ min-width: {control}px; min-height: {control}px; }}\n"
    );
    let colors = format!(
        "@define-color pathfm_bg {};\n@define-color pathfm_surface {};\n@define-color pathfm_text {};\n@define-color pathfm_accent {};\n@define-color pathfm_danger {};\n@define-color pathfm_muted {};\n@define-color pathfm_highlight {};\n@define-color pathfm_border {};\n@define-color pathfm_dim_text {};\nwindow, popover, popover.background {{ font-size: {root_font_px:.6}px; }}\n",
        tokens.background,
        tokens.surface,
        tokens.text,
        tokens.accent,
        tokens.danger,
        tokens.muted,
        tokens.highlight,
        tokens.border,
        tokens.dim_text,
    );
    colors + &sizing
}

/// Parses colours GTK accepts (`#rgb`, `#rrggbb`, `rgb(...)`, names) into 8-bit
/// channels. Path emits these channels as `#rrggbb` in GtkSourceView schemes.
pub(crate) fn parse_rgb_channels(value: &str) -> Option<[u8; 3]> {
    parse_rgba_channels(value).map(|[red, green, blue, _]| [red, green, blue])
}

fn parse_rgba_channels(value: &str) -> Option<[u8; 4]> {
    let color = gdk::RGBA::parse(value).ok()?;
    let channel = |component: f32| (f64::from(component).clamp(0.0, 1.0) * 255.0).round() as u8;
    Some([
        channel(color.red()),
        channel(color.green()),
        channel(color.blue()),
        channel(color.alpha()),
    ])
}

/// Rewrites a color GTK can parse as `#rrggbb`, or `#rrggbbaa` when translucent.
/// `gdk::RGBA::parse` also accepts 9-, 12- and 16-digit hex, which GTK CSS rejects.
fn canonical_color(value: &str) -> Option<String> {
    let [red, green, blue, alpha] = parse_rgba_channels(value)?;
    let rgb = hex_from_channels([red, green, blue]);
    Some(if alpha == u8::MAX {
        rgb
    } else {
        format!("{rgb}{alpha:02x}")
    })
}

fn hex_from_channels(channels: [u8; 3]) -> String {
    format!("#{:02x}{:02x}{:02x}", channels[0], channels[1], channels[2])
}

/// Canonicalizes a colour token to Path's `#rrggbb` scheme representation.
pub(crate) fn color_to_hex(value: &str) -> String {
    parse_rgb_channels(value)
        .map(hex_from_channels)
        .unwrap_or_else(|| value.to_owned())
}

fn blend(left: &str, right: &str, amount: f64) -> String {
    let (Some(left), Some(right)) = (parse_rgb_channels(left), parse_rgb_channels(right)) else {
        return right.to_owned();
    };
    let channel = |index: usize| {
        let a = f64::from(left[index]);
        let b = f64::from(right[index]);
        (a + (b - a) * amount).round() as u32
    };
    format!("#{:02x}{:02x}{:02x}", channel(0), channel(1), channel(2))
}

fn slugify(name: &str) -> String {
    name.trim()
        .to_lowercase()
        .chars()
        .fold(String::new(), |mut slug, character| {
            if character.is_ascii_alphanumeric() {
                slug.push(character);
            } else if !slug.is_empty() && !slug.ends_with('-') {
                slug.push('-');
            }
            slug
        })
        .trim_end_matches('-')
        .to_owned()
}

const FALLBACK_CUSTOM_THEME_ID: &str = "custom-theme";

/// File id for a new custom theme: the ASCII slug of `name`, or a generic id when the
/// name has no ASCII letters or digits, suffixed until `taken` no longer matches.
fn custom_theme_id(name: &str, taken: impl Fn(&str) -> bool) -> String {
    let slug = slugify(name);
    let base = if slug.is_empty() {
        FALLBACK_CUSTOM_THEME_ID
    } else {
        slug.as_str()
    };
    let mut id = base.to_owned();
    let mut suffix = 2;
    while taken(&id) {
        id = format!("{base}-{suffix}");
        suffix += 1;
    }
    id
}

fn title_case_slug(slug: &str) -> String {
    slug.split('-')
        .filter(|part| !part.is_empty())
        .map(|part| {
            let mut chars = part.chars();
            chars
                .next()
                .map(|first| first.to_uppercase().collect::<String>() + chars.as_str())
                .unwrap_or_default()
        })
        .collect::<Vec<_>>()
        .join(" ")
}

fn themes_directory() -> PathBuf {
    super::preferences::config_directory().join("themes")
}

pub(in crate::ui) fn distro_state_dir() -> PathBuf {
    gtk::glib::home_dir().join(".local/state/distro/current")
}

#[cfg(test)]
mod tests;
