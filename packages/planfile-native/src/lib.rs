//! planfile-native: the storage hot path of planfile in Rust.
//!
//! Exposed as `planfile_native._native`. Every function either produces exactly what the
//! pure-Python implementation produces or raises [`Unsupported`] before touching the filesystem,
//! so callers can always fall back to PyYAML without observable differences.

mod json;
mod node;
mod yaml;

use node::{Extractor, Node, NodeError};
use pyo3::exceptions::{PyException, PyOSError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyFloat, PyList, PyLong, PyString, PyTuple};
use std::path::Path;

pyo3::create_exception!(
    _native,
    Unsupported,
    PyException,
    "Raised when a value needs behavior only PyYAML implements; the caller must fall back."
);

fn to_py_err(err: NodeError) -> PyErr {
    match err {
        NodeError::Unsupported(reason) => Unsupported::new_err(reason),
        NodeError::Py(err) => err,
    }
}

fn extract_root(py: Python<'_>, data: &Bound<'_, PyAny>) -> PyResult<Node> {
    Extractor::new(py)?.extract(data).map_err(to_py_err)
}

fn render_yaml(node: &Node, allow_unicode: bool) -> PyResult<String> {
    // Sprint files are mostly string payload; one allocation of about the JSON size avoids
    // repeated growth of the output buffer.
    yaml::Emitter::dump(node, allow_unicode, 1 << 16)
        .map_err(|yaml::EmitError::Unsupported(reason)| Unsupported::new_err(reason))
}

/// `yaml.dump(data, default_flow_style=False, allow_unicode=..., Dumper=CSafeDumper)`.
#[pyfunction]
#[pyo3(signature = (data, allow_unicode=false))]
fn dump_yaml(py: Python<'_>, data: &Bound<'_, PyAny>, allow_unicode: bool) -> PyResult<String> {
    let node = extract_root(py, data)?;
    render_yaml(&node, allow_unicode)
}

/// `json.dumps(_json_safe(data), ensure_ascii=False)`.
#[pyfunction]
fn dump_json(py: Python<'_>, data: &Bound<'_, PyAny>) -> PyResult<String> {
    let node = extract_root(py, data)?;
    let mut out = String::new();
    json::write_node(&mut out, &node);
    Ok(out)
}

/// Writes `path` (YAML) and its JSON mirror in one call.
///
/// Both documents are rendered before any file is touched. Returns
/// `(yaml_mtime_ns, mirror_error)`; a failing mirror write is reported, not raised, because the
/// mirror is only an optimization.
#[pyfunction]
#[pyo3(signature = (path, data, allow_unicode, mirror_version, mirror_suffix, fsync=true))]
fn write_sprint(
    py: Python<'_>,
    path: &str,
    data: &Bound<'_, PyAny>,
    allow_unicode: bool,
    mirror_version: i64,
    mirror_suffix: &str,
    fsync: bool,
) -> PyResult<(i64, Option<String>)> {
    let node = extract_root(py, data)?;
    let yaml_text = render_yaml(&node, allow_unicode)?;
    let mut data_json = String::with_capacity(yaml_text.len());
    json::write_node(&mut data_json, &node);
    drop(node);

    let target = Path::new(path).to_path_buf();
    let mirror_target = format!("{path}{mirror_suffix}");

    py.allow_threads(move || {
        fsio::atomic_write(&target, yaml_text.as_bytes(), fsync)
            .map_err(|err| PyOSError::new_err(format!("{}: {err}", target.display())))?;
        // Stat right after our own rename, mirroring the Python writer, so the mirror is stamped
        // with the mtime of exactly the file this call produced.
        let mtime = fsio::mtime_ns(&target)
            .map_err(|err| PyOSError::new_err(format!("{}: {err}", target.display())))?;
        let mirror = format!(
            "{{\"version\": {mirror_version}, \"yaml_mtime_ns\": {mtime}, \"data\": {data_json}}}"
        );
        let mirror_error = fsio::atomic_write(Path::new(&mirror_target), mirror.as_bytes(), fsync)
            .err()
            .map(|err| format!("{err}"));
        Ok((mtime as i64, mirror_error))
    })
}

/// Atomically replaces `path` with `text` (UTF-8). Same contract as `_atomic_write_text`.
#[pyfunction]
#[pyo3(signature = (path, text, fsync=true))]
fn atomic_write_text(py: Python<'_>, path: &str, text: &str, fsync: bool) -> PyResult<()> {
    let target = Path::new(path).to_path_buf();
    let bytes = text.as_bytes().to_vec();
    py.allow_threads(move || {
        fsio::atomic_write(&target, &bytes, fsync)
            .map_err(|err| PyOSError::new_err(format!("{}: {err}", target.display())))
    })
}

/// `fastio._json_safe`: dates become ISO strings, tuples become lists, containers are copied.
#[pyfunction]
fn normalize(py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let module = py.import_bound("datetime")?;
    let temporal = PyTuple::new_bound(
        py,
        [
            module.getattr("datetime")?,
            module.getattr("date")?,
            module.getattr("time")?,
        ],
    );
    normalize_inner(py, value, &temporal)
}

fn normalize_inner(
    py: Python<'_>,
    value: &Bound<'_, PyAny>,
    temporal: &Bound<'_, PyTuple>,
) -> PyResult<PyObject> {
    if value.is_none()
        || value.is_exact_instance_of::<PyString>()
        || value.is_exact_instance_of::<PyLong>()
        || value.is_exact_instance_of::<PyFloat>()
    {
        return Ok(value.clone().unbind());
    }
    if let Ok(dict) = value.downcast::<PyDict>() {
        let out = PyDict::new_bound(py);
        for (key, item) in dict.iter() {
            out.set_item(
                normalize_inner(py, &key, temporal)?,
                normalize_inner(py, &item, temporal)?,
            )?;
        }
        return Ok(out.into_any().unbind());
    }
    if value.downcast::<PyList>().is_ok() || value.downcast::<PyTuple>().is_ok() {
        let out = PyList::empty_bound(py);
        for item in value.iter()? {
            out.append(normalize_inner(py, &item?, temporal)?)?;
        }
        return Ok(out.into_any().unbind());
    }
    if value.is_instance(temporal)? {
        return Ok(value.call_method0("isoformat")?.unbind());
    }
    Ok(value.clone().unbind())
}

#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("Unsupported", m.py().get_type_bound::<Unsupported>())?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(dump_yaml, m)?)?;
    m.add_function(wrap_pyfunction!(dump_json, m)?)?;
    m.add_function(wrap_pyfunction!(write_sprint, m)?)?;
    m.add_function(wrap_pyfunction!(atomic_write_text, m)?)?;
    m.add_function(wrap_pyfunction!(normalize, m)?)?;
    Ok(())
}

/// Crash-safe file replacement: temp file in the target directory, optional fsync, rename.
mod fsio {
    use std::fs::{self, OpenOptions};
    use std::io::Write;
    use std::path::{Path, PathBuf};
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::time::{SystemTime, UNIX_EPOCH};

    static COUNTER: AtomicU64 = AtomicU64::new(0);

    fn temp_path(target: &Path) -> PathBuf {
        let name = target
            .file_name()
            .map(|n| n.to_string_lossy().into_owned())
            .unwrap_or_default();
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or(0);
        let unique = COUNTER.fetch_add(1, Ordering::Relaxed);
        let dir = target
            .parent()
            .filter(|p| !p.as_os_str().is_empty())
            .unwrap_or_else(|| Path::new("."));
        dir.join(format!(
            ".{name}.{:x}{:x}{:x}.tmp",
            std::process::id(),
            nanos,
            unique
        ))
    }

    /// Writes `content` to `target` atomically. The new file is `0600` like `tempfile.mkstemp`,
    /// which is what the previous Python implementation produced.
    pub fn atomic_write(target: &Path, content: &[u8], fsync: bool) -> std::io::Result<()> {
        if let Some(parent) = target.parent() {
            if !parent.as_os_str().is_empty() {
                fs::create_dir_all(parent)?;
            }
        }
        let tmp = temp_path(target);
        let mut options = OpenOptions::new();
        options.write(true).create_new(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            options.mode(0o600);
        }
        let result = (|| {
            let mut file = options.open(&tmp)?;
            file.write_all(content)?;
            file.flush()?;
            if fsync {
                file.sync_all()?;
            }
            drop(file);
            fs::rename(&tmp, target)
        })();
        if result.is_err() {
            let _ = fs::remove_file(&tmp);
        }
        result
    }

    /// `st_mtime_ns` of `path` as an unsigned nanosecond count (matches `os.stat`).
    pub fn mtime_ns(path: &Path) -> std::io::Result<i128> {
        use std::os::unix::fs::MetadataExt;
        let meta = fs::metadata(path)?;
        Ok(meta.mtime() as i128 * 1_000_000_000 + meta.mtime_nsec() as i128)
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        #[test]
        fn replaces_file_and_leaves_no_temp() {
            let dir = std::env::temp_dir().join(format!("pfn-atomic-{}", std::process::id()));
            let target = dir.join("nested").join("a.yaml");
            atomic_write(&target, b"one", true).unwrap();
            atomic_write(&target, b"two", false).unwrap();
            assert_eq!(fs::read(&target).unwrap(), b"two");
            let leftovers = fs::read_dir(target.parent().unwrap()).unwrap().count();
            assert_eq!(leftovers, 1);
            fs::remove_dir_all(dir).unwrap();
        }
    }
}
