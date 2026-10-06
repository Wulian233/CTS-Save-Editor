use serde::Deserialize;
use std::{
    collections::{HashMap, HashSet},
    sync::LazyLock,
};

#[derive(Deserialize)]
struct Category {
    name: String,
    note: String,
}

#[derive(Deserialize)]
struct Rule {
    tokens: Vec<String>,
    category: Category,
}

#[derive(Deserialize)]
struct Rules {
    exact: HashMap<String, Category>,
    prefix: Vec<Rule>,
    substring: Vec<Rule>,
    descriptions: HashSet<String>,
}

static RULES: LazyLock<Rules> = LazyLock::new(|| {
    serde_json::from_str(include_str!("categories.json")).expect("Invalid bundled categories")
});

pub fn classify(key: &str, numeric: bool) -> (String, String, String) {
    let lower = key.to_lowercase();
    let category = RULES
        .exact
        .get(key)
        .or_else(|| {
            RULES
                .prefix
                .iter()
                .find(|r| r.tokens.iter().any(|p| key.starts_with(p)))
                .map(|r| &r.category)
        })
        .or_else(|| {
            RULES
                .substring
                .iter()
                .find(|r| r.tokens.iter().any(|p| lower.contains(p)))
                .map(|r| &r.category)
        });
    let fallback = if numeric {
        ("category.numeric_item", "category_note.numeric_item_source")
    } else {
        ("category.custom_var", "category_note.custom_var_string")
    };
    let (name, note) = category
        .map(|c| (c.name.as_str(), c.note.as_str()))
        .unwrap_or(fallback);
    let description = format!("item_note.{key}");
    (
        name.into(),
        note.into(),
        if RULES.descriptions.contains(&description) {
            description
        } else {
            String::new()
        },
    )
}
