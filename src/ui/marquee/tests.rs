// SPDX-License-Identifier: MIT

use super::*;

#[test]
fn custom_controls_and_artwork_do_not_start_marquees_from_chrome() {
    crate::test_support::gtk_test(
        "ui::marquee::tests::custom_controls_and_artwork_do_not_start_marquees_from_chrome",
        || {
            let surface = gtk::Box::new(gtk::Orientation::Vertical, 0);
            let blank = gtk::Box::new(gtk::Orientation::Vertical, 0);
            surface.append(&blank);
            assert!(is_inert_chrome(surface.upcast_ref(), blank.upcast_ref()));
            for role in [gtk::AccessibleRole::Slider, gtk::AccessibleRole::Img] {
                let control = glib::Object::builder::<gtk::DrawingArea>()
                    .property("accessible-role", role)
                    .build();
                blank.append(&control);
                assert!(
                    !is_inert_chrome(surface.upcast_ref(), control.upcast_ref()),
                    "{role:?} widgets handle their own presses"
                );
            }
            let handle = gtk::Box::new(gtk::Orientation::Horizontal, 8);
            handle.add_controller(gtk::DragSource::new());
            let gap = gtk::Box::new(gtk::Orientation::Horizontal, 0);
            handle.append(&gap);
            surface.append(&handle);
            assert!(
                !is_inert_chrome(surface.upcast_ref(), gap.upcast_ref()),
                "a press inside a drag handle keeps its file drag"
            );
        },
    );
}

/// The deadline only turns a hang into a deterministic failure.
fn pump_until(ready: impl Fn() -> bool) {
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(5);
    while !ready() && std::time::Instant::now() < deadline {
        glib::MainContext::default().iteration(false);
    }
}

fn shared_origin_gesture(surface: &gtk::Box) -> gtk::GestureDrag {
    surface
        .observe_controllers()
        .iter::<glib::Object>()
        .flatten()
        .find_map(|controller| controller.downcast::<gtk::GestureDrag>().ok())
        .expect("shared-origin drag gesture")
}

#[test]
fn chrome_origin_click_policy_decides_when_a_plain_click_clears() {
    crate::test_support::gtk_test(
        "ui::marquee::tests::chrome_origin_click_policy_decides_when_a_plain_click_clears",
        || {
            let scroll = gtk::ScrolledWindow::new();
            let clears = Rc::new(Cell::new(0u32));
            let counter = clears.clone();
            let marquee = install(MarqueeSetup {
                view: gtk::Box::new(gtk::Orientation::Vertical, 0).upcast(),
                surface: scroll.clone().upcast(),
                scroll: scroll.clone(),
                overlay: gtk::Overlay::new(),
                targets: Rc::new(RefCell::new(Vec::new())),
                is_item: Rc::new(|_, _, _| false),
                clear_selection: Rc::new(move || counter.set(counter.get() + 1)),
                allow_drag: Rc::new(Cell::new(true)),
            });
            let state = &marquee.state;
            // A detached gesture reports no modifiers, so each row sets them after `begin`.
            let gesture = gtk::GestureDrag::new();
            for (clear_on_click, modifiers, after_press, after_finish, label) in [
                (
                    true,
                    (false, false),
                    1,
                    1,
                    "clearing origin clears at press and not again on release",
                ),
                (
                    false,
                    (false, false),
                    0,
                    0,
                    "keeping origin never clears a plain click",
                ),
                (
                    true,
                    (true, false),
                    0,
                    0,
                    "modified press keeps the selection for a union drag",
                ),
            ] {
                clears.set(0);
                state.begin((0.0, 0.0), &gesture, clear_on_click);
                state.modifiers.set(modifiers);
                state.clear_at_press();
                assert_eq!(clears.get(), after_press, "{label} (press)");
                state.finish();
                assert_eq!(clears.get(), after_finish, "{label}");
            }
            clears.set(0);
            state.begin((0.0, 0.0), &gesture, false);
            state.dragging.set(true);
            state.finish();
            assert_eq!(
                clears.get(),
                0,
                "a drag from a keeping origin never calls clear; apply_selection owns the result"
            );
        },
    );
}

#[test]
fn keeping_origins_clear_only_outside_the_content_they_show() {
    crate::test_support::gtk_test(
        "ui::marquee::tests::keeping_origins_clear_only_outside_the_content_they_show",
        || {
            let slot = gtk::Box::new(gtk::Orientation::Horizontal, 0);
            let pane = gtk::Box::new(gtk::Orientation::Vertical, 0);
            let margin = gtk::Box::new(gtk::Orientation::Vertical, 0);
            pane.append(&margin);
            slot.append(&pane);
            let keeps = OriginClick::keeps_selection_within(&pane);
            for (click, picked, clears, label) in [
                (
                    &keeps,
                    margin.upcast_ref::<gtk::Widget>(),
                    false,
                    "blank chrome in the pane",
                ),
                (&keeps, pane.upcast_ref(), false, "the pane itself"),
                (
                    &keeps,
                    slot.upcast_ref(),
                    true,
                    "the empty slot around a hidden pane",
                ),
                (
                    &OriginClick::ClearsSelection,
                    margin.upcast_ref(),
                    true,
                    "a clearing origin",
                ),
            ] {
                assert_eq!(click.clears_at(picked), clears, "{label}");
            }
        },
    );
}

#[test]
fn disabled_controls_are_rejected_like_enabled_ones() {
    crate::test_support::gtk_test(
        "ui::marquee::tests::disabled_controls_are_rejected_like_enabled_ones",
        || {
            let surface = gtk::Box::new(gtk::Orientation::Vertical, 0);
            let button = gtk::Button::with_label("Next");
            button.set_sensitive(false);
            button.set_size_request(-1, 40);
            let blank = gtk::Box::new(gtk::Orientation::Vertical, 0);
            blank.set_vexpand(true);
            surface.append(&button);
            surface.append(&blank);
            let resolved = Rc::new(Cell::new(0u32));
            let counter = resolved.clone();
            install_shared_origin_surface(
                &surface,
                OriginClick::ClearsSelection,
                move |_, _, _, _| {
                    counter.set(counter.get() + 1);
                    None
                },
            );
            let gesture = shared_origin_gesture(&surface);
            let window = gtk::Window::builder()
                .child(&surface)
                .default_width(200)
                .default_height(200)
                .build();
            window.present();
            pump_until(|| surface.is_mapped() && blank.height() > 0);
            let press = |x: f64, y: f64| {
                resolved.set(0);
                gesture.emit_by_name::<()>("drag-begin", &[&x, &y]);
                resolved.get()
            };
            let bottom = f64::from(surface.height()) - 5.0;
            assert_eq!(press(10.0, 20.0), 0, "a disabled button is a control");
            assert_eq!(press(10.0, bottom), 1, "blank chrome below it is accepted");
            button.set_sensitive(true);
            assert_eq!(press(10.0, 20.0), 0, "an enabled button is a control");
            window.destroy();
        },
    );
}
