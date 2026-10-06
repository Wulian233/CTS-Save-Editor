pub mod binary;
mod categories;
pub mod files;
pub mod numbers;

use serde::Serialize;
use std::ops::Range;

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
