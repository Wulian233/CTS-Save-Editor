use crate::{Entry, categories, numbers};
use std::collections::HashMap;

#[derive(Debug)]
struct Record {
    end: usize,
    id: u32,
    text: String,
    length_pos: usize,
}

pub fn decode_length(data: &[u8], pos: usize) -> Option<(usize, usize)> {
    let mut value = 0usize;
    for count in 0..5 {
        let b = *data.get(pos.checked_add(count)?)?;
        value |= usize::from(b & 0x7f) << (7 * count);
        if b & 0x80 == 0 {
            return Some((value, count + 1));
        }
    }
    None
}

pub fn encode_length(mut value: usize) -> Vec<u8> {
    let mut out = Vec::new();
    while value >= 128 {
        out.push((value as u8 & 0x7f) | 0x80);
        value >>= 7;
    }
    out.push(value as u8);
    out
}

fn scan(data: &[u8]) -> Vec<Record> {
    let mut records = Vec::new();
    let mut i = 0;
    while i + 6 <= data.len() {
        if data[i] != 6 {
            i += 1;
            continue;
        }
        let id = u32::from_le_bytes(data[i + 1..i + 5].try_into().unwrap());
        let Some((length, size)) = decode_length(data, i + 5) else {
            i += 1;
            continue;
        };
        let start = i + 5 + size;
        let Some(end) = start.checked_add(length).filter(|end| *end <= data.len()) else {
            i += 1;
            continue;
        };
        let Ok(text) = std::str::from_utf8(&data[start..end]) else {
            i += 1;
            continue;
        };
        records.push(Record {
            end,
            id,
            text: text.into(),
            length_pos: i + 5,
        });
        i = end;
    }
    records
}

pub fn parse(data: &[u8]) -> Vec<Entry> {
    let records = scan(data);
    let positions: HashMap<usize, &Record> =
        records.iter().map(|r| (r.length_pos - 5, r)).collect();
    let mut items = HashMap::new();
    for i in 0..data.len().saturating_sub(24) {
        if data[i] == 1 && data[i + 5] == 0x25 {
            let id = u32::from_le_bytes(data[i + 1..i + 5].try_into().unwrap());
            items.entry(id).or_insert(i);
        }
    }
    let mut entries = Vec::new();
    for key in &records {
        if key.text.is_empty() {
            continue;
        }
        if let Some(value) = positions.get(&key.end)
            && key.id.checked_add(1) == Some(value.id)
        {
            entries.push(entry(
                "custom",
                key,
                value.text.clone(),
                value.length_pos,
                value.end,
            ));
        }
    }
    for key in &records {
        let p = key.end;
        if key.text.is_empty() || p + 5 > data.len() || data[p] != 9 {
            continue;
        }
        let id = u32::from_le_bytes(data[p + 1..p + 5].try_into().unwrap());
        if let Some(&i) = items.get(&id) {
            let owned = f64::from_le_bytes(data[i + 9..i + 17].try_into().unwrap());
            let exp = i64::from_le_bytes(data[i + 17..i + 25].try_into().unwrap());
            entries.push(entry(
                "meta",
                key,
                numbers::display(owned, exp),
                i + 9,
                i + 25,
            ));
        }
    }
    for (id, entry) in entries.iter_mut().enumerate() {
        entry.id = id;
    }
    entries
}

fn entry(section: &str, key: &Record, value: String, start: usize, end: usize) -> Entry {
    let (category, note, description) = categories::classify(&key.text, section == "meta");
    Entry {
        id: 0,
        section: section.into(),
        key: key.text.clone(),
        value,
        category,
        note,
        description,
        start,
        end,
    }
}
