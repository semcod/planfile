//! Plain-Rust value tree extracted from Python objects.
//!
//! Only types that `yaml.SafeDumper` (and `json.dumps`) represent without special handling are
//! accepted, and only by *exact* type, mirroring `Representer.yaml_representers` lookup. Anything
//! else, an object referenced twice (PyYAML would emit anchors) or a cycle yields
//! [`NodeError::Unsupported`], and the Python caller falls back to PyYAML so behavior (including
//! errors) stays identical.

use pyo3::prelude::*;
use pyo3::sync::GILOnceCell;
use pyo3::types::{PyBool, PyDict, PyFloat, PyList, PyLong, PyString, PyTuple};
use std::collections::HashSet;

/// Containers nested deeper than this are left to PyYAML instead of risking native stack use.
const MAX_DEPTH: usize = 256;

#[derive(Debug)]
pub enum Node {
    Null,
    Bool(bool),
    Int(String),
    /// `repr(float)` exactly as Python prints it.
    Float(String),
    Str(String),
    Timestamp {
        yaml: String,
        json: String,
    },
    Seq(Vec<Node>),
    /// Insertion-ordered; the YAML emitter sorts, the JSON writer does not.
    Map(Vec<(String, Node)>),
}

#[derive(Debug)]
pub enum NodeError {
    Unsupported(String),
    Py(PyErr),
}

impl From<PyErr> for NodeError {
    fn from(err: PyErr) -> Self {
        NodeError::Py(err)
    }
}

impl From<pyo3::DowncastError<'_, '_>> for NodeError {
    fn from(err: pyo3::DowncastError<'_, '_>) -> Self {
        NodeError::Py(err.into())
    }
}

fn unsupported<T>(reason: impl Into<String>) -> Result<T, NodeError> {
    Err(NodeError::Unsupported(reason.into()))
}

struct DateTypes {
    datetime: Py<PyAny>,
    date: Py<PyAny>,
}

fn date_types(py: Python<'_>) -> PyResult<&DateTypes> {
    static CELL: GILOnceCell<DateTypes> = GILOnceCell::new();
    CELL.get_or_try_init(py, || {
        let module = py.import_bound("datetime")?;
        Ok(DateTypes {
            datetime: module.getattr("datetime")?.unbind(),
            date: module.getattr("date")?.unbind(),
        })
    })
}

pub struct Extractor<'py> {
    py: Python<'py>,
    seen: HashSet<usize>,
    dates: &'py DateTypes,
}

impl<'py> Extractor<'py> {
    pub fn new(py: Python<'py>) -> PyResult<Self> {
        Ok(Self {
            py,
            seen: HashSet::new(),
            dates: date_types(py)?,
        })
    }

    pub fn extract(&mut self, obj: &Bound<'py, PyAny>) -> Result<Node, NodeError> {
        self.visit(obj, 0)
    }

    fn visit(&mut self, obj: &Bound<'py, PyAny>, depth: usize) -> Result<Node, NodeError> {
        if obj.is_none() {
            return Ok(Node::Null);
        }
        if obj.is_exact_instance_of::<PyBool>() {
            return Ok(Node::Bool(obj.is_truthy()?));
        }
        if obj.is_exact_instance_of::<PyString>() {
            let text = obj.downcast::<PyString>()?.to_str().map_err(|_| {
                NodeError::Unsupported("string is not valid UTF-8 (lone surrogate)".into())
            })?;
            return Ok(Node::Str(text.to_owned()));
        }
        if obj.is_exact_instance_of::<PyLong>() {
            return Ok(Node::Int(obj.str()?.to_string_lossy().into_owned()));
        }
        if obj.is_exact_instance_of::<PyFloat>() {
            return Ok(Node::Float(obj.repr()?.to_string_lossy().into_owned()));
        }
        if obj.is_exact_instance_of::<PyDict>() {
            return self.visit_dict(obj, depth);
        }
        if obj.is_exact_instance_of::<PyList>() || obj.is_exact_instance_of::<PyTuple>() {
            return self.visit_seq(obj, depth);
        }
        let ty = obj.get_type();
        if ty.is(self.dates.datetime.bind(self.py)) {
            let yaml = obj.call_method1("isoformat", (" ",))?.extract::<String>()?;
            let json = obj.call_method0("isoformat")?.extract::<String>()?;
            return Ok(Node::Timestamp { yaml, json });
        }
        if ty.is(self.dates.date.bind(self.py)) {
            let text = obj.call_method0("isoformat")?.extract::<String>()?;
            return Ok(Node::Timestamp {
                yaml: text.clone(),
                json: text,
            });
        }
        unsupported(format!("unsupported type {}", ty.name()?))
    }

    /// Registers a container. PyYAML anchors any container reached twice, so the identity stays
    /// in `seen` for the whole walk.
    fn enter(&mut self, obj: &Bound<'py, PyAny>, depth: usize) -> Result<(), NodeError> {
        if depth >= MAX_DEPTH {
            return unsupported("maximum nesting depth exceeded");
        }
        let id = obj.as_ptr() as usize;
        if !self.seen.insert(id) {
            return unsupported("container referenced more than once (YAML anchors required)");
        }
        Ok(())
    }

    fn visit_dict(&mut self, obj: &Bound<'py, PyAny>, depth: usize) -> Result<Node, NodeError> {
        self.enter(obj, depth)?;
        let dict = obj.downcast::<PyDict>()?;
        let mut entries = Vec::with_capacity(dict.len());
        for (key, value) in dict.iter() {
            if !key.is_exact_instance_of::<PyString>() {
                return unsupported("non-string mapping key");
            }
            let key = key
                .downcast::<PyString>()?
                .to_str()
                .map_err(|_| NodeError::Unsupported("mapping key is not valid UTF-8".into()))?;
            entries.push((key.to_owned(), self.visit(&value, depth + 1)?));
        }
        Ok(Node::Map(entries))
    }

    fn visit_seq(&mut self, obj: &Bound<'py, PyAny>, depth: usize) -> Result<Node, NodeError> {
        self.enter(obj, depth)?;
        let mut items = Vec::new();
        for item in obj.iter()? {
            items.push(self.visit(&item?, depth + 1)?);
        }
        Ok(Node::Seq(items))
    }
}
