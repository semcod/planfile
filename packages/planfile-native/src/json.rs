//! `json.dumps(value, ensure_ascii=False)` for [`Node`] trees, byte-compatible with CPython's
//! encoder (default `", "` / `": "` separators, `NaN`/`Infinity` literals).
//!
//! The planfile JSON mirror only has to round-trip through `json.loads`, but keeping the exact
//! encoder format means a mirror written natively and one written by the Python fallback are
//! indistinguishable on disk.

use crate::node::Node;
use std::fmt::Write;

pub fn write_node(out: &mut String, node: &Node) {
    match node {
        Node::Null => out.push_str("null"),
        Node::Bool(true) => out.push_str("true"),
        Node::Bool(false) => out.push_str("false"),
        Node::Int(text) => out.push_str(text),
        Node::Float(repr) => out.push_str(match repr.as_str() {
            "nan" => "NaN",
            "inf" => "Infinity",
            "-inf" => "-Infinity",
            other => other,
        }),
        Node::Str(text) => write_string(out, text),
        Node::Timestamp { json, .. } => write_string(out, json),
        Node::Seq(items) => {
            out.push('[');
            for (index, item) in items.iter().enumerate() {
                if index > 0 {
                    out.push_str(", ");
                }
                write_node(out, item);
            }
            out.push(']');
        }
        Node::Map(entries) => {
            out.push('{');
            for (index, (key, value)) in entries.iter().enumerate() {
                if index > 0 {
                    out.push_str(", ");
                }
                write_string(out, key);
                out.push_str(": ");
                write_node(out, value);
            }
            out.push('}');
        }
    }
}

fn write_string(out: &mut String, text: &str) {
    out.push('"');
    let mut run_start = 0;
    for (index, c) in text.char_indices() {
        let escape: Option<&str> = match c {
            '"' => Some("\\\""),
            '\\' => Some("\\\\"),
            '\n' => Some("\\n"),
            '\r' => Some("\\r"),
            '\t' => Some("\\t"),
            '\u{8}' => Some("\\b"),
            '\u{c}' => Some("\\f"),
            c if (c as u32) < 0x20 => None,
            _ => continue,
        };
        out.push_str(&text[run_start..index]);
        match escape {
            Some(sequence) => out.push_str(sequence),
            None => {
                let _ = write!(out, "\\u{:04x}", c as u32);
            }
        }
        run_start = index + c.len_utf8();
    }
    out.push_str(&text[run_start..]);
    out.push('"');
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matches_cpython_formatting() {
        let node = Node::Map(vec![
            (
                "a".into(),
                Node::Seq(vec![
                    Node::Int("1".into()),
                    Node::Null,
                    Node::Float("nan".into()),
                ]),
            ),
            ("b\"".into(), Node::Str("line\n\u{1}ż".into())),
        ]);
        let mut out = String::new();
        write_node(&mut out, &node);
        assert_eq!(
            out,
            "{\"a\": [1, null, NaN], \"b\\\"\": \"line\\n\\u0001ż\"}"
        );
    }
}
