// SPDX-License-Identifier: MPL-2.0
// Copyright ijl (2026)

use crate::deserialize::DeserializeError;
#[cfg(all(CPython, not(Py_GIL_DISABLED)))]
use crate::ffi::{PyByteArrayRef, PyMemoryViewRef};
use crate::ffi::{PyBytesRef, PyStrRef};
use std::borrow::Cow;

const INVALID_STR: &str = "str is not valid UTF-8: surrogates not allowed";

#[cfg(CPython)]
const INPUT_TYPE_MESSAGE: &str = "Input must be bytes, bytearray, memoryview, or str";

#[cfg(not(CPython))]
const INPUT_TYPE_MESSAGE: &str = "Input must be bytes, bytearray, or str";

#[cfg_attr(not(Py_GIL_DISABLED), repr(transparent))]
pub struct Utf8Buffer {
    buffer: &'static str,
    #[cfg(Py_GIL_DISABLED)]
    owner: Option<core::ptr::NonNull<crate::ffi::PyObject>>,
}

impl Utf8Buffer {
    #[cfg(all(CPython, not(Py_GIL_DISABLED)))]
    fn buffer_from_ptr(
        ptr: *mut crate::ffi::PyObject,
    ) -> Result<Option<&'static str>, DeserializeError<'static>> {
        if let Ok(ob) = PyBytesRef::from_ptr(ptr) {
            Ok(ob.as_str())
        } else if let Ok(ob) = PyStrRef::from_ptr(ptr) {
            Ok(ob.as_str())
        } else if let Ok(ob) = PyByteArrayRef::from_ptr(ptr) {
            Ok(ob.as_str())
        } else if let Ok(ob) = PyMemoryViewRef::from_ptr(ptr) {
            Ok(ob.as_str())
        } else {
            Err(DeserializeError::invalid(Cow::Borrowed(INPUT_TYPE_MESSAGE)))
        }
    }

    #[cfg(any(not(CPython), Py_GIL_DISABLED))]
    fn buffer_from_ptr(
        ptr: *mut crate::ffi::PyObject,
    ) -> Result<Option<&'static str>, DeserializeError<'static>> {
        if let Ok(ob) = PyBytesRef::from_ptr(ptr) {
            Ok(ob.as_str())
        } else if let Ok(ob) = PyStrRef::from_ptr(ptr) {
            Ok(ob.as_str())
        } else {
            Err(DeserializeError::invalid(Cow::Borrowed(INPUT_TYPE_MESSAGE)))
        }
    }

    pub fn from_pyobject(
        ptr: *mut crate::ffi::PyObject,
    ) -> Result<Self, DeserializeError<'static>> {
        debug_assert!(!ptr.is_null());
        #[cfg(Py_GIL_DISABLED)]
        unsafe {
            let kind = crate::ffi::PyObject_Type(ptr);
            if kind == &raw mut pyo3_ffi::PyByteArray_Type
                || kind == &raw mut pyo3_ffi::PyMemoryView_Type
            {
                return Self::from_mutable_buffer(ptr);
            }
        }
        match Utf8Buffer::buffer_from_ptr(ptr) {
            Ok(Some(as_str)) => {
                if as_str.is_empty() {
                    cold_path!();
                    Err(DeserializeError::invalid(Cow::Borrowed(
                        "Input is a zero-length, empty document",
                    )))
                } else {
                    Ok(Self {
                        buffer: as_str,
                        #[cfg(Py_GIL_DISABLED)]
                        owner: None,
                    })
                }
            }
            Ok(None) => {
                cold_path!();
                Err(DeserializeError::invalid(Cow::Borrowed(INVALID_STR)))
            }
            Err(_) => Err(DeserializeError::invalid(Cow::Borrowed(INPUT_TYPE_MESSAGE))),
        }
    }

    pub fn as_str(&self) -> &'static str {
        self.buffer
    }

    pub fn as_bytes(&self) -> &'static [u8] {
        self.buffer.as_bytes()
    }
}

// Mutable input needs an immutable snapshot before parsing without the GIL.
// A live buffer export pins storage. On 3.14+ the exporter lock also excludes
// bytearray's synchronized writes during copying. 3.13 bytearray writes do not
// acquire that lock, so callers must synchronize all mutable-buffer access.
// On every version, memoryview aliases and external writers require caller
// synchronization with decoding; not every buffer writer locks its exporter.
#[cfg(Py_GIL_DISABLED)]
impl Utf8Buffer {
    unsafe fn from_mutable_buffer(
        ptr: *mut crate::ffi::PyObject,
    ) -> Result<Self, DeserializeError<'static>> {
        unsafe {
            let mut view = core::mem::MaybeUninit::<pyo3_ffi::Py_buffer>::uninit();
            // 3.13 uses plain export counters for bytearray and memoryview.
            // Serialize our own acquisitions/releases even for read-only data.
            #[cfg(not(Py_3_14))]
            let mut export_section =
                core::mem::MaybeUninit::<pyo3_ffi::PyCriticalSection>::uninit();
            #[cfg(not(Py_3_14))]
            pyo3_ffi::PyCriticalSection_Begin(export_section.as_mut_ptr(), ptr);
            let status =
                pyo3_ffi::PyObject_GetBuffer(ptr, view.as_mut_ptr(), pyo3_ffi::PyBUF_C_CONTIGUOUS);
            #[cfg(not(Py_3_14))]
            pyo3_ffi::PyCriticalSection_End(export_section.as_mut_ptr());
            if status != 0 {
                pyo3_ffi::PyErr_Clear();
                return Err(DeserializeError::invalid(Cow::Borrowed(INPUT_TYPE_MESSAGE)));
            }
            let mut view = view.assume_init();
            let exporter = if crate::ffi::PyObject_Type(ptr) == &raw mut pyo3_ffi::PyMemoryView_Type
            {
                pyo3_ffi::PyObject_GetAttrString(ptr, c"obj".as_ptr())
            } else {
                pyo3_ffi::Py_INCREF(ptr);
                ptr
            };
            if exporter.is_null() {
                release_buffer(ptr, &raw mut view);
                pyo3_ffi::PyErr_Clear();
                return Err(DeserializeError::invalid(Cow::Borrowed(INPUT_TYPE_MESSAGE)));
            }
            let mut section = core::mem::MaybeUninit::<pyo3_ffi::PyCriticalSection>::uninit();
            pyo3_ffi::PyCriticalSection_Begin(section.as_mut_ptr(), exporter);
            let copied = pyo3_ffi::PyBytes_FromStringAndSize(view.buf.cast(), view.len);
            pyo3_ffi::PyCriticalSection_End(section.as_mut_ptr());
            pyo3_ffi::Py_DECREF(exporter);
            release_buffer(ptr, &raw mut view);
            if copied.is_null() {
                pyo3_ffi::PyErr_Clear();
                return Err(DeserializeError::invalid(Cow::Borrowed(
                    "Not enough memory to allocate buffer",
                )));
            }
            match Self::from_pyobject(copied) {
                Ok(mut buffer) => {
                    buffer.owner = core::ptr::NonNull::new(copied);
                    Ok(buffer)
                }
                Err(error) => {
                    pyo3_ffi::Py_DECREF(copied);
                    Err(error)
                }
            }
        }
    }
}

#[cfg(Py_GIL_DISABLED)]
unsafe fn release_buffer(_ptr: *mut crate::ffi::PyObject, view: *mut pyo3_ffi::Py_buffer) {
    unsafe {
        #[cfg(not(Py_3_14))]
        let mut section = core::mem::MaybeUninit::<pyo3_ffi::PyCriticalSection>::uninit();
        #[cfg(not(Py_3_14))]
        pyo3_ffi::PyCriticalSection_Begin(section.as_mut_ptr(), _ptr);
        pyo3_ffi::PyBuffer_Release(view);
        #[cfg(not(Py_3_14))]
        pyo3_ffi::PyCriticalSection_End(section.as_mut_ptr());
    }
}

#[cfg(Py_GIL_DISABLED)]
impl Drop for Utf8Buffer {
    fn drop(&mut self) {
        if let Some(owner) = self.owner {
            unsafe { pyo3_ffi::Py_DECREF(owner.as_ptr()) };
        }
    }
}
