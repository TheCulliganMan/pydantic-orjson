// SPDX-License-Identifier: MPL-2.0
// Copyright ijl (2022-2026)

pub(crate) mod datetime;
mod error;
mod fragment;
mod non_str;
mod num;
mod numpy;
mod obtype;
mod state;
mod uuid;
pub(crate) mod writer;

use crate::ffi::{PyBytes_FromStringAndSize, PyFloatRef, PyIntRef, PyObject, PyStrRef, PyTypeRef};
use crate::opt::{APPEND_NEWLINE, INDENT_2, Opt, STRICT_INTEGER};
use crate::util::usize_to_isize;
use core::ptr::NonNull;
pub(crate) use error::SerializeError;
use state::SerializerState;
pub(crate) use writer::{
    CompactFormatter, ContainerSerializer, IndentFormatter, set_str_formatter_fn,
};
use writer::{JsonWriter, SmallFixedBuffer, format_escaped_str_to};

const SHORT_STRING_BUFFER_LENGTH: usize = 256;
// Each UTF-8 byte can expand to a six-byte escape. The opening quote and
// largest trailing SIMD store require 33 extra bytes, including when the AVX
// remainder is empty. The closing quote and optional newline need less space.
const SHORT_STRING_MAX_BYTES: usize = (SHORT_STRING_BUFFER_LENGTH - 33) / 6;

pub(crate) fn serialize(
    ptr: *mut PyObject,
    default: Option<NonNull<PyObject>>,
    opts: Opt,
) -> Result<NonNull<PyObject>, SerializeError> {
    // Exact primitive types never use default callbacks or container-specific
    // options. Allocate their finished bytes directly, avoiding the general
    // writer's initial allocation, growth bookkeeping and final resize.
    {
        let ob_type = PyTypeRef::from_pyobject(ptr);
        unsafe {
            if ob_type.as_ptr() == crate::typeref::INT_TYPE {
                return serialize_number::<false>(ptr, opts);
            }
            if ob_type.as_ptr() == crate::typeref::FLOAT_TYPE {
                return serialize_number::<true>(ptr, opts);
            }
            if ob_type.as_ptr() == crate::typeref::STR_TYPE {
                let value = PyStrRef::from_ptr_unchecked(ptr)
                    .as_str()
                    .ok_or(SerializeError::InvalidStr)?;
                if value.len() <= SHORT_STRING_MAX_BYTES {
                    return Ok(serialize_short_string(value, opts));
                }
                // A scalar string has no indentation or callback behavior.
                // Reuse its validated UTF-8 instead of dispatching the Python
                // object and acquiring its UTF-8 view a second time.
                return Ok(ContainerSerializer::new(
                    CompactFormatter,
                    SerializerState::new(opts),
                    None,
                )
                .write_str(value));
            }
            let literal: &[u8] = if ob_type.as_ptr() == crate::typeref::NONE_TYPE {
                b"null\n"
            } else if ob_type.as_ptr() == crate::typeref::BOOL_TYPE {
                if ptr == crate::typeref::TRUE {
                    b"true\n"
                } else {
                    b"false\n"
                }
            } else {
                &[]
            };
            if !literal.is_empty() {
                let len = literal.len() - usize::from(opt_disabled!(opts, APPEND_NEWLINE));
                return Ok(nonnull!(PyBytes_FromStringAndSize(
                    literal.as_ptr().cast::<core::ffi::c_char>(),
                    usize_to_isize(len),
                )));
            }
        }
    }
    let state = SerializerState::new(opts);
    if opt_disabled!(opts, INDENT_2) {
        ContainerSerializer::new(CompactFormatter, state, default).write(ptr)
    } else {
        ContainerSerializer::new(IndentFormatter, state, default).write(ptr)
    }
}

// Keep the stack buffer out of the container path's frame. The same numeric
// conversion functions handle strict integer errors, nonfinite floats and
// exponent formatting in both this path and nested container serialization.
#[inline(never)]
fn serialize_number<const FLOAT: bool>(
    ptr: *mut PyObject,
    opts: Opt,
) -> Result<NonNull<PyObject>, SerializeError> {
    let mut buffer = SmallFixedBuffer::new();
    if FLOAT {
        num::serialize_float(&mut buffer, unsafe { PyFloatRef::from_ptr_unchecked(ptr) });
    } else {
        num::serialize_int(
            &mut buffer,
            unsafe { PyIntRef::from_ptr_unchecked(ptr) },
            opt_enabled!(opts, STRICT_INTEGER),
        )?;
    }
    if opt_enabled!(opts, APPEND_NEWLINE) {
        buffer.put_u8(b'\n');
    }
    Ok(nonnull!(unsafe {
        PyBytes_FromStringAndSize(
            buffer.as_ptr().cast::<core::ffi::c_char>(),
            usize_to_isize(buffer.len()),
        )
    }))
}

// Keep this scratch allocation off the frame used by containers and long
// strings. The caller holds the original Python argument alive throughout;
// exact str and its UTF-8 cache are immutable, including on free-threaded Python.
#[inline(never)]
fn serialize_short_string(value: &str, opts: Opt) -> NonNull<PyObject> {
    debug_assert!(value.len() <= SHORT_STRING_MAX_BYTES);
    let mut buffer = [core::mem::MaybeUninit::<u8>::uninit(); SHORT_STRING_BUFFER_LENGTH];
    let dst = buffer.as_mut_ptr().cast::<u8>();
    unsafe {
        // The capacity-derived cutoff proves the dispatcher's writable range.
        // Every architecture uses the same existing escape implementation.
        let mut len = format_escaped_str_to(dst, value);
        if opt_enabled!(opts, APPEND_NEWLINE) {
            core::ptr::write(dst.add(len), b'\n');
            len += 1;
        }
        nonnull!(PyBytes_FromStringAndSize(
            dst.cast::<core::ffi::c_char>(),
            usize_to_isize(len),
        ))
    }
}
