// SPDX-License-Identifier: MPL-2.0
// Copyright ijl (2024-2026)

use super::DeserializeError;
use super::input::Utf8Buffer;
use crate::ffi::{PyBoolRef, PyDictRef, PyListRef, PyNoneRef, PyStrRef};
use core::ptr::NonNull;

#[repr(transparent)]
pub struct Deserializer {
    buffer: Utf8Buffer,
}

impl Deserializer {
    #[inline]
    pub fn from_pyobject(
        ptr: *mut crate::ffi::PyObject,
    ) -> Result<Self, DeserializeError<'static>> {
        let buffer = Utf8Buffer::from_pyobject(ptr)?;
        debug_assert!(!buffer.as_str().is_empty());
        Ok(Self { buffer: buffer })
    }

    #[inline]
    pub fn deserialize(&self) -> Result<NonNull<crate::ffi::PyObject>, DeserializeError<'static>> {
        let bytes = self.buffer.as_bytes();
        match bytes.len() {
            2 => match bytes {
                b"[]" => return Ok(PyListRef::with_capacity(0).as_non_null_ptr()),
                b"{}" => return Ok(PyDictRef::new().as_non_null_ptr()),
                b"\"\"" => return Ok(PyStrRef::empty().as_non_null_ptr()),
                _ => {}
            },
            4 => match bytes {
                b"null" => return Ok(PyNoneRef::none().as_non_null_ptr()),
                b"true" => return Ok(PyBoolRef::pytrue().as_non_null_ptr()),
                _ => {}
            },
            5 if bytes == b"false" => return Ok(PyBoolRef::pyfalse().as_non_null_ptr()),
            _ => {}
        }
        // UTF-8 has already been validated by Utf8Buffer. Small unescaped
        // strings can construct their Python value without an input copy and
        // parser tape; all escapes, controls and extra JSON syntax use yyjson.
        if (3..=64).contains(&bytes.len())
            && bytes[0] == b'"'
            && bytes[bytes.len() - 1] == b'"'
            && bytes[1..bytes.len() - 1]
                .iter()
                .all(|byte| *byte >= 32 && *byte != b'"' && *byte != b'\\')
        {
            return Ok(
                PyStrRef::from_str(&self.buffer.as_str()[1..bytes.len() - 1]).as_non_null_ptr(),
            );
        }
        crate::deserialize::backend::deserialize(self.buffer.as_str())
    }
}

pub(crate) fn deserialize(
    ptr: *mut crate::ffi::PyObject,
) -> Result<NonNull<crate::ffi::PyObject>, DeserializeError<'static>> {
    let deserializer = Deserializer::from_pyobject(ptr)?;
    deserializer.deserialize()
}
