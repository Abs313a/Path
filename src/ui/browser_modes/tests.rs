// SPDX-License-Identifier: MIT

use super::*;

fn item_name(item: &glib::Object) -> String {
    item.downcast_ref::<gtk::StringObject>()
        .map(|item| item.string().into())
        .unwrap_or_default()
}

#[test]
fn view_positions_map_to_the_source_items_they_show() {
    crate::test_support::gtk_test(
        "ui::browser_modes::tests::view_positions_map_to_the_source_items_they_show",
        || {
            let source = gtk::StringList::new(&["alpha", ".hidden", "bravo", "charlie"]);
            let source_index = SourceIndexMap::watch(&source);
            let show_hidden = Rc::new(Cell::new(false));
            let filter = gtk::CustomFilter::new({
                let show_hidden = show_hidden.clone();
                move |item| show_hidden.get() || !item_name(item).starts_with('.')
            });
            let filtered = gtk::FilterListModel::new(Some(source.clone()), Some(filter.clone()));
            let descending =
                gtk::CustomSorter::new(|left, right| item_name(right).cmp(&item_name(left)).into());
            let view = gtk::SortListModel::new(Some(filtered), Some(descending))
                .upcast::<gio::ListModel>();
            let view_index = SourceIndexMap::watch(&view);
            let shown = |positions: std::ops::Range<u32>| -> Vec<String> {
                view_index
                    .sources_of(&source_index, &view, positions)
                    .into_iter()
                    .map(|position| {
                        let position = position.expect("every shown item has a source");
                        source.string(position as u32).unwrap_or_default().into()
                    })
                    .collect()
            };

            assert_eq!(shown(0..3), ["charlie", "bravo", "alpha"]);
            // A filtered-out arrival moves source positions without touching the view.
            source.splice(0, 0, &[".cache"]);
            assert_eq!(shown(0..3), ["charlie", "bravo", "alpha"]);
            source.append("delta");
            assert_eq!(shown(0..4), ["delta", "charlie", "bravo", "alpha"]);
            show_hidden.set(true);
            filter.changed(gtk::FilterChange::LessStrict);
            assert_eq!(
                shown(0..6),
                ["delta", "charlie", "bravo", "alpha", ".hidden", ".cache"]
            );
        },
    );
}
