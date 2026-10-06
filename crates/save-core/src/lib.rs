pub mod binary;
mod categories;
pub mod files;
pub mod numbers;

use serde::Serialize;
use std::{
    collections::{BTreeMap, HashMap},
    ops::Range,
};

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Entry {
    pub id: usize,
    pub section: String,
    pub key: String,
    pub value: String,
    pub category: String,
    pub note: String,
    pub description: String,
    #[serde(skip)]
    pub start: usize,
    #[serde(skip)]
    pub end: usize,
}

#[derive(Clone, Debug)]
pub struct Editor {
    pub data: Vec<u8>,
    undo: Vec<Patch>,
    redo: Vec<Patch>,
}

#[derive(Clone, Debug)]
struct Patch {
    start: usize,
    before: Vec<u8>,
    after: Vec<u8>,
}

impl Editor {
    pub fn new(data: Vec<u8>) -> Self {
        Self {
            data,
            undo: Vec::new(),
            redo: Vec::new(),
        }
    }

    pub fn parse(&self) -> Vec<Entry> {
        binary::parse(&self.data)
    }

    pub fn edit(&mut self, id: usize, value: &str) -> Result<(), String> {
        // Always reparse offsets: a UTF-8 edit can move every subsequent record.
        let entry = self
            .parse()
            .into_iter()
            .find(|e| e.id == id)
            .ok_or("Variable no longer exists")?;
        if value.trim().is_empty() {
            return Err("Value cannot be empty".into());
        }
        let payload = if entry.section == "custom" {
            let mut payload = binary::encode_length(value.len());
            payload.extend_from_slice(value.as_bytes());
            payload
        } else {
            let (owned, exp) = numbers::normalize(value)?;
            [owned.to_le_bytes(), exp.to_le_bytes()].concat()
        };
        self.replace(entry.start..entry.end, payload);
        Ok(())
    }

    fn replace(&mut self, range: Range<usize>, after: Vec<u8>) {
        let before = self.data[range.clone()].to_vec();
        if before == after {
            return;
        }
        self.data.splice(range.clone(), after.iter().copied());
        self.undo.push(Patch {
            start: range.start,
            before,
            after,
        });
        self.redo.clear();
    }

    pub fn restore(&mut self, entry: &Entry, original: &[u8]) {
        self.replace(entry.start..entry.end, original.to_vec());
    }

    pub fn apply_changes_to(&self, baseline: &[u8], target: &[u8]) -> Result<Vec<u8>, String> {
        let before = binary::parse(baseline);
        let after = self.parse();
        if before.len() != after.len()
            || before
                .iter()
                .zip(&after)
                .any(|(a, b)| a.section != b.section || a.key != b.key)
        {
            return Err("Save structure changed. Reload the original save before editing.".into());
        }
        let target_entries = binary::parse(target);
        let mut groups = HashMap::<(&str, &str), Vec<&Entry>>::new();
        for entry in &target_entries {
            groups
                .entry((&entry.section, &entry.key))
                .or_default()
                .push(entry);
        }
        let mut counts = HashMap::<(&str, &str), usize>::new();
        for entry in &before {
            *counts.entry((&entry.section, &entry.key)).or_default() += 1;
        }
        let mut occurrences = HashMap::<(&str, &str), usize>::new();
        let mut patches = BTreeMap::new();
        for (original, current) in before.iter().zip(&after) {
            let key = (original.section.as_str(), original.key.as_str());
            let occurrence = occurrences.entry(key).or_default();
            let index = *occurrence;
            *occurrence += 1;
            let payload = &self.data[current.start..current.end];
            if payload == &baseline[original.start..original.end] {
                continue;
            }
            let matches = groups
                .get(&key)
                .filter(|entries| entries.len() == counts[&key])
                .ok_or_else(|| {
                    format!(
                        "Cannot match modified variable in companion save: {}",
                        original.key
                    )
                })?;
            let entry = matches[index];
            patches.insert(entry.start, (entry.end, payload));
        }
        // Write from the end so changed UTF-8 lengths never invalidate later offsets.
        let mut result = target.to_vec();
        for (start, (end, payload)) in patches.into_iter().rev() {
            result.splice(start..end, payload.iter().copied());
        }
        Ok(result)
    }

    pub fn can_undo(&self) -> bool {
        !self.undo.is_empty()
    }
    pub fn can_redo(&self) -> bool {
        !self.redo.is_empty()
    }

    pub fn undo(&mut self) {
        if let Some(patch) = self.undo.pop() {
            self.data.splice(
                patch.start..patch.start + patch.after.len(),
                patch.before.iter().copied(),
            );
            self.redo.push(patch);
        }
    }

    pub fn redo(&mut self) {
        if let Some(patch) = self.redo.pop() {
            self.data.splice(
                patch.start..patch.start + patch.before.len(),
                patch.after.iter().copied(),
            );
            self.undo.push(patch);
        }
    }
}
