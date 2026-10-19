//! Port of the libyaml 0.2.5 block emitter, restricted to what `yaml.CSafeDumper` produces for
//! `default_flow_style=False, sort_keys=True` over JSON-like data.
//!
//! The goal is byte-identical output: sprint files are tracked in users' repositories, so a
//! different serializer would show up as whole-file git diffs. The function names follow libyaml
//! (`write_indent`, `write_indicator`, `analyze_scalar`, ...) so the port can be audited against
//! `emitter.c`. Differential tests against PyYAML live in `tests/test_parity.py`.

use crate::node::Node;
use regex::Regex;
use std::sync::OnceLock;

// ---- PyYAML implicit resolver (YAML 1.1) ----
// PyYAML 6 implicit scalar resolver (YAML 1.1 rules).
//
// `yaml.resolver.Resolver` decides, per plain scalar, whether the text would be read back as a
// non-string (bool, int, float, null, timestamp, merge, value). The emitter quotes a string when
// that happens, so these patterns must stay identical to PyYAML's. Dispatch is on the first
// character exactly as `BaseResolver.resolve` does.

struct Patterns {
    boolean: Regex,
    float: Regex,
    int: Regex,
    null: Regex,
    timestamp: Regex,
}

fn patterns() -> &'static Patterns {
    static CELL: OnceLock<Patterns> = OnceLock::new();
    CELL.get_or_init(|| Patterns {
        boolean: Regex::new(
            r"^(?:yes|Yes|YES|no|No|NO|true|True|TRUE|false|False|FALSE|on|On|ON|off|Off|OFF)$",
        )
        .expect("bool pattern"),
        float: Regex::new(concat!(
            r"^(?:[-+]?(?:[0-9][0-9_]*)\.[0-9_]*(?:[eE][-+][0-9]+)?",
            r"|\.[0-9][0-9_]*(?:[eE][-+][0-9]+)?",
            r"|[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\.[0-9_]*",
            r"|[-+]?\.(?:inf|Inf|INF)",
            r"|\.(?:nan|NaN|NAN))$"
        ))
        .expect("float pattern"),
        int: Regex::new(concat!(
            r"^(?:[-+]?0b[0-1_]+",
            r"|[-+]?0[0-7_]+",
            r"|[-+]?(?:0|[1-9][0-9_]*)",
            r"|[-+]?0x[0-9a-fA-F_]+",
            r"|[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+)$"
        ))
        .expect("int pattern"),
        null: Regex::new(r"^(?:~|null|Null|NULL|)$").expect("null pattern"),
        timestamp: Regex::new(concat!(
            r"^(?:[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]",
            r"|[0-9][0-9][0-9][0-9]-[0-9][0-9]?-[0-9][0-9]?",
            r"(?:[Tt]|[ \t]+)[0-9][0-9]?",
            r":[0-9][0-9]:[0-9][0-9](?:\.[0-9]*)?",
            r"(?:[ \t]*(?:Z|[-+][0-9][0-9]?(?::[0-9][0-9])?))?)$"
        ))
        .expect("timestamp pattern"),
    })
}

/// True when PyYAML's implicit resolver would assign a non-`str` tag to `value`.
///
/// Python's `$` also matches before one trailing newline, the `regex` crate's does not, so a
/// single trailing `\n` is stripped before matching.
fn resolves_to_non_str(value: &str) -> bool {
    let first = match value.chars().next() {
        None => return true, // '' resolves to null
        Some(c) => c,
    };
    let text = value.strip_suffix('\n').unwrap_or(value);
    let p = patterns();
    match first {
        '-' | '+' => p.float.is_match(text) || p.int.is_match(text),
        '.' => p.float.is_match(text),
        '0'..='9' => p.float.is_match(text) || p.int.is_match(text) || p.timestamp.is_match(text),
        'y' | 'Y' | 'f' | 'F' | 'o' | 'O' | 't' | 'T' => p.boolean.is_match(text),
        'n' | 'N' => p.boolean.is_match(text) || p.null.is_match(text),
        '~' => p.null.is_match(text),
        '<' => text == "<<",
        '=' => text == "=",
        '!' | '&' | '*' => text.chars().count() == 1,
        _ => false,
    }
}

/// libyaml `best_width` after `yaml_emitter_emit_stream_start` normalisation (`width=None`).
const BEST_WIDTH: usize = 80;
const BEST_INDENT: i32 = 2;
/// `yaml_emitter_check_simple_key` refuses keys longer than this many bytes.
const MAX_SIMPLE_KEY_BYTES: usize = 128;

#[derive(Debug)]
pub enum EmitError {
    /// The value needs tags or anchors the port does not reproduce; PyYAML must handle it.
    Unsupported(String),
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Style {
    Plain,
    Single,
    Double,
}

struct Analysis {
    multiline: bool,
    flow_plain_allowed: bool,
    block_plain_allowed: bool,
    single_quoted_allowed: bool,
}

fn is_break(c: char) -> bool {
    matches!(c, '\r' | '\n' | '\u{85}' | '\u{2028}' | '\u{2029}')
}

fn is_blankz(c: Option<char>) -> bool {
    match c {
        None => true,
        Some(c) => c == ' ' || c == '\t' || c == '\0' || is_break(c),
    }
}

/// libyaml `IS_PRINTABLE` expressed on code points (it is defined on UTF-8 lead bytes, which
/// makes every supplementary-plane character "unprintable").
fn is_printable(c: char) -> bool {
    let v = c as u32;
    v == 0x0A
        || (0x20..=0x7E).contains(&v)
        || (0xA0..=0xD7FF).contains(&v)
        || ((0xE000..=0xFFFD).contains(&v) && v != 0xFEFF)
}

fn analyze_scalar(value: &str, unicode: bool) -> Analysis {
    if value.is_ascii() {
        return analyze_ascii(value.as_bytes());
    }
    analyze_general(value, unicode)
}

/// Byte-wise twin of [`analyze_general`] for ASCII text (the overwhelmingly common case). Kept
/// in lock-step by `ascii_analysis_equals_general_analysis`.
fn analyze_ascii(bytes: &[u8]) -> Analysis {
    let n = bytes.len();
    if n == 0 {
        return Analysis {
            multiline: false,
            flow_plain_allowed: false,
            block_plain_allowed: true,
            single_quoted_allowed: true,
        };
    }
    let blankz = |b: u8| matches!(b, b' ' | b'\t' | b'\n' | b'\r' | 0);
    let mut block_indicators = false;
    let mut flow_indicators = false;
    let mut line_breaks = false;
    let mut special_characters = false;
    let (mut leading_space, mut leading_break, mut trailing_space, mut trailing_break) =
        (false, false, false, false);
    let (mut break_space, mut space_break) = (false, false);
    let (mut previous_space, mut previous_break) = (false, false);
    if bytes.starts_with(b"---") || bytes.starts_with(b"...") {
        block_indicators = true;
        flow_indicators = true;
    }
    let mut preceded_by_whitespace = true;
    for (i, &c) in bytes.iter().enumerate() {
        let first = i == 0;
        let last = i + 1 == n;
        let followed_by_whitespace = last || blankz(bytes[i + 1]);
        if first {
            if matches!(
                c,
                b'#' | b','
                    | b'['
                    | b']'
                    | b'{'
                    | b'}'
                    | b'&'
                    | b'*'
                    | b'!'
                    | b'|'
                    | b'>'
                    | b'\''
                    | b'"'
                    | b'%'
                    | b'@'
                    | b'`'
            ) {
                flow_indicators = true;
                block_indicators = true;
            }
            if c == b'?' || c == b':' {
                flow_indicators = true;
                if followed_by_whitespace {
                    block_indicators = true;
                }
            }
            if c == b'-' && followed_by_whitespace {
                flow_indicators = true;
                block_indicators = true;
            }
        } else {
            if matches!(c, b',' | b'?' | b'[' | b']' | b'{' | b'}') {
                flow_indicators = true;
            }
            if c == b':' {
                flow_indicators = true;
                if followed_by_whitespace {
                    block_indicators = true;
                }
            }
            if c == b'#' && preceded_by_whitespace {
                flow_indicators = true;
                block_indicators = true;
            }
        }
        if !(c == b'\n' || (0x20..=0x7E).contains(&c)) {
            special_characters = true;
        }
        let is_brk = c == b'\n' || c == b'\r';
        if is_brk {
            line_breaks = true;
        }
        if c == b' ' {
            leading_space |= first;
            trailing_space |= last;
            break_space |= previous_break;
            previous_space = true;
            previous_break = false;
        } else if is_brk {
            leading_break |= first;
            trailing_break |= last;
            space_break |= previous_space;
            previous_space = false;
            previous_break = true;
        } else {
            previous_space = false;
            previous_break = false;
        }
        preceded_by_whitespace = blankz(c);
    }
    finish_analysis(
        line_breaks,
        flow_indicators,
        block_indicators,
        special_characters,
        leading_space || leading_break || trailing_space || trailing_break,
        break_space,
        space_break,
    )
}

fn analyze_general(value: &str, unicode: bool) -> Analysis {
    if value.is_empty() {
        return Analysis {
            multiline: false,
            flow_plain_allowed: false,
            block_plain_allowed: true,
            single_quoted_allowed: true,
        };
    }

    let mut block_indicators = false;
    let mut flow_indicators = false;
    let mut line_breaks = false;
    let mut special_characters = false;
    let mut leading_space = false;
    let mut leading_break = false;
    let mut trailing_space = false;
    let mut trailing_break = false;
    let mut break_space = false;
    let mut space_break = false;
    let mut previous_space = false;
    let mut previous_break = false;

    if value.starts_with("---") || value.starts_with("...") {
        block_indicators = true;
        flow_indicators = true;
    }

    let mut preceded_by_whitespace = true;
    let mut iter = value.char_indices().peekable();
    let mut followed_by_whitespace = {
        let mut look = value.chars();
        look.next();
        is_blankz(look.next())
    };
    let mut first = true;

    while let Some((index, c)) = iter.next() {
        let last = iter.peek().is_none();
        if first {
            if matches!(
                c,
                '#' | ','
                    | '['
                    | ']'
                    | '{'
                    | '}'
                    | '&'
                    | '*'
                    | '!'
                    | '|'
                    | '>'
                    | '\''
                    | '"'
                    | '%'
                    | '@'
                    | '`'
            ) {
                flow_indicators = true;
                block_indicators = true;
            }
            if c == '?' || c == ':' {
                flow_indicators = true;
                if followed_by_whitespace {
                    block_indicators = true;
                }
            }
            if c == '-' && followed_by_whitespace {
                flow_indicators = true;
                block_indicators = true;
            }
        } else {
            if matches!(c, ',' | '?' | '[' | ']' | '{' | '}') {
                flow_indicators = true;
            }
            if c == ':' {
                flow_indicators = true;
                if followed_by_whitespace {
                    block_indicators = true;
                }
            }
            if c == '#' && preceded_by_whitespace {
                flow_indicators = true;
                block_indicators = true;
            }
        }

        if !is_printable(c) || (!c.is_ascii() && !unicode) {
            special_characters = true;
        }
        if is_break(c) {
            line_breaks = true;
        }

        if c == ' ' {
            if first {
                leading_space = true;
            }
            if last {
                trailing_space = true;
            }
            if previous_break {
                break_space = true;
            }
            previous_space = true;
            previous_break = false;
        } else if is_break(c) {
            if first {
                leading_break = true;
            }
            if last {
                trailing_break = true;
            }
            if previous_space {
                space_break = true;
            }
            previous_space = false;
            previous_break = true;
        } else {
            previous_space = false;
            previous_break = false;
        }

        preceded_by_whitespace = is_blankz(Some(c));
        if !last {
            let rest = &value[index + c.len_utf8()..];
            let mut look = rest.chars();
            look.next();
            followed_by_whitespace = is_blankz(look.next());
        }
        first = false;
    }

    finish_analysis(
        line_breaks,
        flow_indicators,
        block_indicators,
        special_characters,
        leading_space || leading_break || trailing_space || trailing_break,
        break_space,
        space_break,
    )
}

fn finish_analysis(
    line_breaks: bool,
    flow_indicators: bool,
    block_indicators: bool,
    special_characters: bool,
    edge_whitespace: bool,
    break_space: bool,
    space_break: bool,
) -> Analysis {
    let mut analysis = Analysis {
        multiline: line_breaks,
        flow_plain_allowed: true,
        block_plain_allowed: true,
        single_quoted_allowed: true,
    };
    if edge_whitespace {
        analysis.flow_plain_allowed = false;
        analysis.block_plain_allowed = false;
    }
    if break_space {
        analysis.flow_plain_allowed = false;
        analysis.block_plain_allowed = false;
        analysis.single_quoted_allowed = false;
    }
    if space_break || special_characters {
        analysis.flow_plain_allowed = false;
        analysis.block_plain_allowed = false;
        analysis.single_quoted_allowed = false;
    }
    if line_breaks {
        analysis.flow_plain_allowed = false;
        analysis.block_plain_allowed = false;
    }
    if flow_indicators {
        analysis.flow_plain_allowed = false;
    }
    if block_indicators {
        analysis.block_plain_allowed = false;
    }
    analysis
}

pub struct Emitter {
    out: String,
    column: usize,
    indent: i32,
    indents: Vec<i32>,
    whitespace: bool,
    indention: bool,
    flow_level: usize,
    mapping_context: bool,
    simple_key_context: bool,
    unicode: bool,
}

/// How a scalar's text relates to its tag, i.e. `plain_implicit` / `quoted_implicit` of the
/// libyaml scalar event.
struct ScalarEvent<'a> {
    text: &'a str,
    plain_implicit: bool,
    /// Non-strings carry a non-`str` tag; only plain style can omit it.
    is_str: bool,
}

impl Emitter {
    pub fn new(unicode: bool, capacity: usize) -> Self {
        Emitter {
            out: String::with_capacity(capacity),
            column: 0,
            indent: -1,
            indents: Vec::new(),
            whitespace: true,
            indention: true,
            flow_level: 0,
            mapping_context: false,
            simple_key_context: false,
            unicode,
        }
    }

    /// Serializes one document; the root must be a mapping or a sequence.
    pub fn dump(root: &Node, unicode: bool, capacity_hint: usize) -> Result<String, EmitError> {
        if !matches!(root, Node::Map(_) | Node::Seq(_)) {
            return Err(EmitError::Unsupported(
                "root must be a mapping or sequence".into(),
            ));
        }
        let mut emitter = Emitter::new(unicode, capacity_hint);
        emitter.emit_node(root, false, false)?;
        // yaml_emitter_emit_document_end: write_indent terminates the last line.
        emitter.write_indent();
        Ok(emitter.out)
    }

    // ---- low level writers (emitter.c: PUT, PUT_BREAK, write_indent, write_indicator) ----

    fn put(&mut self, c: char) {
        self.out.push(c);
        self.column += 1;
    }

    fn put_break(&mut self) {
        self.out.push('\n');
        self.column = 0;
    }

    fn write_indent(&mut self) {
        let indent = if self.indent >= 0 {
            self.indent as usize
        } else {
            0
        };
        if !self.indention || self.column > indent || (self.column == indent && !self.whitespace) {
            self.put_break();
        }
        while self.column < indent {
            self.put(' ');
        }
        self.whitespace = true;
        self.indention = true;
    }

    fn write_indicator(
        &mut self,
        indicator: &str,
        need_whitespace: bool,
        is_whitespace: bool,
        is_indention: bool,
    ) {
        if need_whitespace && !self.whitespace {
            self.put(' ');
        }
        self.out.push_str(indicator);
        self.column += indicator.chars().count();
        self.whitespace = is_whitespace;
        self.indention = self.indention && is_indention;
    }

    fn increase_indent(&mut self, flow: bool, indentless: bool) {
        self.indents.push(self.indent);
        if self.indent < 0 {
            self.indent = if flow { BEST_INDENT } else { 0 };
        } else if !indentless {
            self.indent += BEST_INDENT;
        }
    }

    fn pop_indent(&mut self) {
        self.indent = self.indents.pop().unwrap_or(-1);
    }

    // ---- node dispatch (emit_node and the block collection states) ----

    fn emit_node(&mut self, node: &Node, mapping: bool, simple_key: bool) -> Result<(), EmitError> {
        self.mapping_context = mapping;
        self.simple_key_context = simple_key;
        match node {
            Node::Seq(items) => {
                self.emit_sequence(items)?;
                Ok(())
            }
            Node::Map(entries) => self.emit_mapping(entries),
            Node::Null => self.emit_non_str("null"),
            Node::Bool(true) => self.emit_non_str("true"),
            Node::Bool(false) => self.emit_non_str("false"),
            Node::Int(text) => self.emit_non_str(text),
            Node::Float(repr) => {
                let text = float_text(repr);
                self.emit_non_str(&text)
            }
            Node::Timestamp { yaml, .. } => self.emit_non_str(yaml),
            Node::Str(text) => self.emit_scalar(&ScalarEvent {
                text,
                plain_implicit: !resolves_to_non_str(text),
                is_str: true,
            }),
        }
    }

    fn emit_non_str(&mut self, text: &str) -> Result<(), EmitError> {
        let plain_implicit = true; // the representer's own text always resolves to its tag
        self.emit_scalar(&ScalarEvent {
            text,
            plain_implicit,
            is_str: false,
        })
    }

    fn emit_sequence(&mut self, items: &[Node]) -> Result<(), EmitError> {
        if self.flow_level > 0 || items.is_empty() {
            self.write_indicator("[", true, true, false);
            self.increase_indent(true, false);
            self.flow_level += 1;
            self.flow_level -= 1;
            self.pop_indent();
            self.write_indicator("]", false, false, false);
            return Ok(());
        }
        let indentless = self.mapping_context && !self.indention;
        self.increase_indent(false, indentless);
        for item in items {
            self.write_indent();
            self.write_indicator("-", true, false, true);
            self.emit_node(item, false, false)?;
        }
        self.pop_indent();
        Ok(())
    }

    fn emit_mapping(&mut self, entries: &[(String, Node)]) -> Result<(), EmitError> {
        if self.flow_level > 0 || entries.is_empty() {
            self.write_indicator("{", true, true, false);
            self.increase_indent(true, false);
            self.flow_level += 1;
            self.flow_level -= 1;
            self.pop_indent();
            self.write_indicator("}", false, false, false);
            return Ok(());
        }
        // PyYAML sorts items before representing them (sort_keys=True).
        let mut order: Vec<&(String, Node)> = entries.iter().collect();
        order.sort_by(|a, b| a.0.cmp(&b.0));

        self.increase_indent(false, false);
        for (key, value) in order.iter().map(|e| (&e.0, &e.1)) {
            self.write_indent();
            let key_analysis = analyze_scalar(key, self.unicode);
            let simple = !key_analysis.multiline && key.len() <= MAX_SIMPLE_KEY_BYTES;
            let key_event = ScalarEvent {
                text: key,
                plain_implicit: !resolves_to_non_str(key),
                is_str: true,
            };
            if simple {
                self.mapping_context = true;
                self.simple_key_context = true;
                self.emit_analyzed_scalar(&key_event, &key_analysis)?;
                self.write_indicator(":", false, false, false);
            } else {
                self.write_indicator("?", true, false, true);
                self.mapping_context = true;
                self.simple_key_context = false;
                self.emit_analyzed_scalar(&key_event, &key_analysis)?;
                self.write_indent();
                self.write_indicator(":", true, false, true);
            }
            self.emit_node(value, true, false)?;
        }
        self.pop_indent();
        Ok(())
    }

    // ---- scalars (select_scalar_style, process_scalar, write_*_scalar) ----

    fn emit_scalar(&mut self, event: &ScalarEvent<'_>) -> Result<(), EmitError> {
        let analysis = analyze_scalar(event.text, self.unicode);
        self.emit_analyzed_scalar(event, &analysis)
    }

    fn emit_analyzed_scalar(
        &mut self,
        event: &ScalarEvent<'_>,
        analysis: &Analysis,
    ) -> Result<(), EmitError> {
        let style = self.select_style(event, analysis);
        if !event.is_str && style != Style::Plain {
            return Err(EmitError::Unsupported(
                "non-string scalar needs an explicit tag".into(),
            ));
        }
        self.increase_indent(false, false);
        let allow_breaks = !self.simple_key_context;
        match style {
            Style::Plain => self.write_plain(event.text, allow_breaks),
            Style::Single => self.write_single_quoted(event.text, allow_breaks),
            Style::Double => self.write_double_quoted(event.text, allow_breaks),
        }
        self.pop_indent();
        Ok(())
    }

    fn select_style(&self, event: &ScalarEvent<'_>, analysis: &Analysis) -> Style {
        let mut style = Style::Plain;
        if self.simple_key_context && analysis.multiline {
            style = Style::Double;
        }
        if style == Style::Plain {
            let plain_allowed = if self.flow_level > 0 {
                analysis.flow_plain_allowed
            } else {
                analysis.block_plain_allowed
            };
            if !plain_allowed {
                style = Style::Single;
            }
            if event.text.is_empty() && (self.flow_level > 0 || self.simple_key_context) {
                style = Style::Single;
            }
            if !event.plain_implicit {
                style = Style::Single;
            }
        }
        if style == Style::Single && !analysis.single_quoted_allowed {
            style = Style::Double;
        }
        style
    }

    /// Appends a run of characters that need no per-character decision.
    fn put_run(&mut self, run: &str) {
        if run.is_empty() {
            return;
        }
        // The per-character writers clear `indention` after every ordinary character.
        self.indention = false;
        self.out.push_str(run);
        self.column += if run.is_ascii() {
            run.len()
        } else {
            run.chars().count()
        };
    }

    fn write_plain(&mut self, value: &str, allow_breaks: bool) {
        if !self.whitespace && (!value.is_empty() || self.flow_level > 0) {
            self.put(' ');
        }
        // Plain style is only selected for scalars without line breaks (analyze_scalar), so the
        // only decision points are spaces; everything between them is copied as one run.
        let mut spaces = false;
        let mut run_start = 0;
        for (index, c) in value.char_indices() {
            if c != ' ' {
                spaces = false;
                continue;
            }
            self.put_run(&value[run_start..index]);
            run_start = index + 1;
            let next_is_space = value[index + 1..].starts_with(' ');
            if allow_breaks && !spaces && self.column > BEST_WIDTH && !next_is_space {
                self.write_indent();
            } else {
                self.put(' ');
            }
            spaces = true;
        }
        self.put_run(&value[run_start..]);
        self.whitespace = false;
        self.indention = false;
    }

    fn write_break(&mut self, c: char) {
        if c == '\n' {
            self.put_break();
        } else {
            self.out.push(c);
            self.column = 0;
        }
    }

    fn write_single_quoted(&mut self, value: &str, allow_breaks: bool) {
        self.write_indicator("'", true, false, false);
        let mut spaces = false;
        let mut breaks = false;
        let mut run_start = 0;
        let mut run_open = false; // a pending plain run begins at run_start
        for (index, c) in value.char_indices() {
            let special = c == ' ' || c == '\'' || is_break(c);
            if !special {
                if !run_open {
                    run_start = index;
                    run_open = true;
                    if breaks {
                        self.write_indent();
                    }
                }
                spaces = false;
                breaks = false;
                continue;
            }
            if run_open {
                self.put_run(&value[run_start..index]);
                run_open = false;
                self.indention = false;
            }
            if c == ' ' {
                let is_first = index == 0;
                let is_last = index + 1 == value.len();
                let next_is_space = value[index + 1..].starts_with(' ');
                if allow_breaks
                    && !spaces
                    && self.column > BEST_WIDTH
                    && !is_first
                    && !is_last
                    && !next_is_space
                {
                    self.write_indent();
                } else {
                    self.put(c);
                }
                spaces = true;
            } else if is_break(c) {
                if !breaks && c == '\n' {
                    self.put_break();
                }
                self.write_break(c);
                self.indention = true;
                breaks = true;
            } else {
                // a quote: written as two quotes, and it ends any break run like a plain char
                if breaks {
                    self.write_indent();
                }
                self.put('\'');
                self.put('\'');
                self.indention = false;
                spaces = false;
                breaks = false;
            }
        }
        if run_open {
            self.put_run(&value[run_start..]);
            self.indention = false;
        }
        if breaks {
            self.write_indent();
        }
        self.write_indicator("'", false, false, false);
        self.whitespace = false;
        self.indention = false;
    }

    fn needs_escape(&self, c: char) -> bool {
        !is_printable(c)
            || (!self.unicode && !c.is_ascii())
            || c == '\u{FEFF}'
            || is_break(c)
            || c == '"'
            || c == '\\'
    }

    fn write_double_quoted(&mut self, value: &str, allow_breaks: bool) {
        self.write_indicator("\"", true, false, false);
        let mut spaces = false;
        let mut run_start = 0;
        for (index, c) in value.char_indices() {
            let escape = self.needs_escape(c);
            if !escape && c != ' ' {
                spaces = false;
                continue;
            }
            self.put_run(&value[run_start..index]);
            run_start = index + c.len_utf8();
            if escape {
                self.write_escape(c);
                spaces = false;
            } else {
                let is_first = index == 0;
                let is_last = index + 1 == value.len();
                if allow_breaks && !spaces && self.column > BEST_WIDTH && !is_first && !is_last {
                    self.write_indent();
                    if value[index + 1..].starts_with(' ') {
                        self.put('\\');
                    }
                } else {
                    self.put(c);
                }
                spaces = true;
            }
        }
        self.put_run(&value[run_start..]);
        self.write_indicator("\"", false, false, false);
        self.whitespace = false;
        self.indention = false;
    }

    fn write_escape(&mut self, c: char) {
        self.put('\\');
        let v = c as u32;
        match v {
            0x00 => self.put('0'),
            0x07 => self.put('a'),
            0x08 => self.put('b'),
            0x09 => self.put('t'),
            0x0A => self.put('n'),
            0x0B => self.put('v'),
            0x0C => self.put('f'),
            0x0D => self.put('r'),
            0x1B => self.put('e'),
            0x22 => self.put('"'),
            0x5C => self.put('\\'),
            0x85 => self.put('N'),
            0xA0 => self.put('_'),
            0x2028 => self.put('L'),
            0x2029 => self.put('P'),
            _ => {
                let (marker, width) = if v <= 0xFF {
                    ('x', 2)
                } else if v <= 0xFFFF {
                    ('u', 4)
                } else {
                    ('U', 8)
                };
                self.put(marker);
                for shift in (0..width).rev() {
                    let digit = (v >> (shift * 4)) & 0x0F;
                    self.put(char::from_digit(digit, 16).unwrap().to_ascii_uppercase());
                }
            }
        }
    }
}

/// `SafeRepresenter.represent_float` text for a Python `repr(float)`.
fn float_text(repr: &str) -> String {
    match repr {
        "nan" => ".nan".to_string(),
        "inf" => ".inf".to_string(),
        "-inf" => "-.inf".to_string(),
        _ => {
            let mut value = repr.to_lowercase();
            if !value.contains('.') && value.contains('e') {
                value = value.replacen('e', ".0e", 1);
            }
            value
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn map(entries: Vec<(&str, Node)>) -> Node {
        Node::Map(
            entries
                .into_iter()
                .map(|(k, v)| (k.to_string(), v))
                .collect(),
        )
    }

    #[test]
    fn sorts_keys_and_uses_indentless_sequences() {
        let root = map(vec![
            (
                "b",
                Node::Seq(vec![Node::Int("1".into()), Node::Str("x".into())]),
            ),
            ("a", map(vec![("k", Node::Bool(true))])),
        ]);
        let text = Emitter::dump(&root, false, 0).unwrap();
        assert_eq!(text, "a:\n  k: true\nb:\n- 1\n- x\n");
    }

    #[test]
    fn quotes_lookalike_strings_and_empty_collections() {
        let root = map(vec![
            ("s", Node::Str("true".into())),
            ("e", Node::Str(String::new())),
            ("l", Node::Seq(vec![])),
            ("m", Node::Map(vec![])),
        ]);
        let text = Emitter::dump(&root, false, 0).unwrap();
        assert_eq!(text, "e: ''\nl: []\nm: {}\ns: 'true'\n");
    }

    #[test]
    fn escapes_non_ascii_unless_unicode_allowed() {
        let root = map(vec![("k", Node::Str("zażółć".into()))]);
        assert_eq!(
            Emitter::dump(&root, false, 0).unwrap(),
            "k: \"za\\u017C\\xF3\\u0142\\u0107\"\n"
        );
        assert_eq!(Emitter::dump(&root, true, 0).unwrap(), "k: zażółć\n");
    }

    #[test]
    fn detects_non_string_lookalikes() {
        for v in [
            "",
            "true",
            "No",
            "null",
            "~",
            "12",
            "-3.5",
            "0x1F",
            "2026-10-19",
            "=",
            "<<",
            "1.0e+3",
            ".inf",
        ] {
            assert!(resolves_to_non_str(v), "{v:?} must be quoted");
        }
        for v in [
            "hello", "PLF-001", "1.2.3", "nope", "tru", "10-19", "a b", "1e3",
        ] {
            assert!(!resolves_to_non_str(v), "{v:?} must stay plain");
        }
    }

    #[test]
    fn ascii_analysis_equals_general_analysis() {
        let alphabet: Vec<char> = " \n\r\t-?:#,[]{}&*!|>%@`'\"a.0=\u{7f}\u{1}"
            .chars()
            .collect();
        let mut stack: Vec<String> = vec![String::new()];
        for _ in 0..4 {
            let mut next = Vec::new();
            for prefix in &stack {
                for c in &alphabet {
                    let mut candidate = prefix.clone();
                    candidate.push(*c);
                    let a = analyze_ascii(candidate.as_bytes());
                    let g = analyze_general(&candidate, false);
                    assert_eq!(
                        (
                            a.multiline,
                            a.flow_plain_allowed,
                            a.block_plain_allowed,
                            a.single_quoted_allowed
                        ),
                        (
                            g.multiline,
                            g.flow_plain_allowed,
                            g.block_plain_allowed,
                            g.single_quoted_allowed
                        ),
                        "{candidate:?}"
                    );
                    next.push(candidate);
                }
            }
            stack = next;
        }
    }
}
