use serde::Serialize;
use serde_json::Value;
use std::time::Duration;

#[derive(Serialize)]
pub struct Update {
    version: String,
    title: String,
    url: String,
    changelog: String,
}

fn text(data: &Value, keys: &[&str]) -> String {
    keys.iter()
        .find_map(|k| data[*k].as_str().map(str::trim).filter(|s| !s.is_empty()))
        .unwrap_or("")
        .into()
}

fn parts(v: &str) -> Vec<u64> {
    v.trim_start_matches(['v', 'V'])
        .replace('-', ".")
        .split('.')
        .map(|p| {
            p.chars()
                .filter(char::is_ascii_digit)
                .collect::<String>()
                .parse()
                .unwrap_or(0)
        })
        .collect()
}

fn newer(left: &str, right: &str) -> bool {
    let mut l = parts(left);
    let mut r = parts(right);
    let n = l.len().max(r.len());
    l.resize(n, 0);
    r.resize(n, 0);
    l > r
}

fn parse(data: &Value, locale: &str) -> Option<Update> {
    let version = text(data, &["version", "latest_version", "tag_name"])
        .trim_start_matches(['v', 'V'])
        .to_owned();
    let url = text(data, &["download_url", "download", "url", "html_url"]);
    let parsed = reqwest::Url::parse(&url).ok()?;
    if !["http", "https"].contains(&parsed.scheme()) || !newer(&version, env!("CARGO_PKG_VERSION"))
    {
        return None;
    }
    let notes = ["changelog", "release_notes", "notes", "body"]
        .iter()
        .find_map(|k| data.get(k).filter(|v| !v.is_null()));
    let changelog = match notes {
        Some(Value::String(s)) => s.trim().into(),
        Some(Value::Array(a)) => a
            .iter()
            .map(|v| {
                v.as_str()
                    .map(str::to_owned)
                    .unwrap_or_else(|| v.to_string())
            })
            .collect::<Vec<_>>()
            .join("\n"),
        Some(v @ Value::Object(_)) => text(
            v,
            &[
                locale,
                if locale == "zh-CN" { "zh" } else { "en" },
                "zh-CN",
                "zh",
                "en-US",
                "en",
                "default",
            ],
        ),
        _ => String::new(),
    };
    Some(Update {
        version,
        title: text(data, &["title", "name"]),
        url,
        changelog,
    })
}

#[tauri::command]
pub async fn check_update(locale: String) -> Option<Update> {
    let url = std::env::var("CTS_UPDATE_JSON_URL")
        .unwrap_or_else(|_| "http://cdn.maxing.site/update/app/cts_save_editor.json".into());
    if url.trim().is_empty() {
        return None;
    }
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(6))
        .user_agent(concat!("CTS-Save-Editor/", env!("CARGO_PKG_VERSION")))
        .build()
        .ok()?;
    let mut response = client
        .get(url.trim())
        .header("Accept", "application/json")
        .send()
        .await
        .ok()?
        .error_for_status()
        .ok()?;
    let mut bytes = Vec::new();
    while let Some(chunk) = response.chunk().await.ok()? {
        if bytes.len() + chunk.len() > 65536 {
            return None;
        }
        bytes.extend_from_slice(&chunk);
    }
    parse(&serde_json::from_slice::<Value>(&bytes).ok()?, &locale)
}
