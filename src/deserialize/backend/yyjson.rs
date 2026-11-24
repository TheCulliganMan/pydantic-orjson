// SPDX-License-Identifier: (Apache-2.0 OR MIT)
// Copyright ijl (2022-2026), Anders Kaseorg (2023)

use super::ffi::{
    YYJSON_READ_SUCCESS, yyjson_alc, yyjson_doc, yyjson_read_err, yyjson_read_opts, yyjson_val,
};
use crate::deserialize::DeserializeError;
use crate::deserialize::pyobject::get_unicode_key;
use crate::ffi::{
    PyBoolRef, PyDictRef, PyFloatRef, PyIntRef, PyListRef, PyMem_Free, PyMem_Malloc, PyNoneRef,
    PyStrRef,
};
use core::ffi::{c_char, c_void};
use core::mem::MaybeUninit;
use core::ptr::{NonNull, null, null_mut};
use std::borrow::Cow;

const YYJSON_TAG_BIT: u8 = 8;

const YYJSON_VAL_SIZE: usize = core::mem::size_of::<yyjson_val>();

const TAG_ARRAY: u8 = 0b00000110;
const TAG_DOUBLE: u8 = 0b00010100;
const TAG_FALSE: u8 = 0b00000011;
const TAG_INT64: u8 = 0b00001100;
const TAG_NULL: u8 = 0b00000010;
const TAG_OBJECT: u8 = 0b00000111;
const TAG_STRING: u8 = 0b00000101;
const TAG_TRUE: u8 = 0b00001011;
const TAG_UINT64: u8 = 0b00000100;

fn yyjson_doc_get_root(doc: *mut yyjson_doc) -> *mut yyjson_val {
    unsafe { (*doc).root }
}

fn unsafe_yyjson_get_len(val: *mut yyjson_val) -> usize {
    unsafe { ((*val).tag >> YYJSON_TAG_BIT) as usize }
}

fn unsafe_yyjson_get_first(ctn: *mut yyjson_val) -> *mut yyjson_val {
    unsafe { ctn.add(1) }
}

const MINIMUM_BUFFER_CAPACITY: usize = 8192;

const fn buffer_capacity_to_allocate(len: usize) -> Option<usize> {
    // At most len / 2 + 1 values, 16 bytes each, with less than 1.5x
    // geometric tape growth. The input copy needs len additional bytes.
    // 256 covers the document header, tape padding and allocation alignment.
    // Omitting the copy from this bound rejects some valid pretty documents.
    let Some(capacity) = len.checked_mul(13) else {
        return None;
    };
    let Some(capacity) = capacity.checked_add(256) else {
        return None;
    };
    if capacity <= MINIMUM_BUFFER_CAPACITY {
        return Some(MINIMUM_BUFFER_CAPACITY);
    }
    // The stack threshold is independent of heap allocation granularity.
    // Preserve yyjson's bound without rounding medium inputs up by 8 KiB.
    let Some(capacity) = capacity.checked_add(ARENA_ALIGNMENT - 1) else {
        return None;
    };
    Some(capacity & !(ARENA_ALIGNMENT - 1))
}

const ARENA_ALIGNMENT: usize = 16;

// yyjson's nonincremental reader allocates the input copy, then the document
// and value tape. Only that final allocation grows, so it can expand in place.
// Error cleanup frees the tape and input; the caller releases the entire arena.
// All state belongs to this invocation, including during reentrant GC callbacks.
struct Arena {
    ptr: *mut u8,
    capacity: usize,
    used: usize,
}

impl Arena {
    fn new(ptr: *mut c_void, capacity: usize) -> Self {
        Self {
            ptr: ptr.cast(),
            capacity,
            used: (ptr as usize).wrapping_neg() & (ARENA_ALIGNMENT - 1),
        }
    }

    fn aligned_size(size: usize) -> Option<usize> {
        size.checked_add(ARENA_ALIGNMENT - 1)
            .map(|size| size & !(ARENA_ALIGNMENT - 1))
    }

    unsafe extern "C" fn malloc(ctx: *mut c_void, size: usize) -> *mut c_void {
        let arena = unsafe { &mut *ctx.cast::<Self>() };
        let Some(size) = Self::aligned_size(size) else {
            return null_mut();
        };
        let Some(end) = arena.used.checked_add(size) else {
            return null_mut();
        };
        if end > arena.capacity {
            return null_mut();
        }
        let ptr = unsafe { arena.ptr.add(arena.used) };
        arena.used = end;
        ptr.cast()
    }

    unsafe extern "C" fn realloc(
        ctx: *mut c_void,
        ptr: *mut c_void,
        old_size: usize,
        size: usize,
    ) -> *mut c_void {
        let arena = unsafe { &mut *ctx.cast::<Self>() };
        let Some(start) = (ptr as usize).checked_sub(arena.ptr as usize) else {
            return null_mut();
        };
        let Some(old_size) = Self::aligned_size(old_size) else {
            return null_mut();
        };
        if start.checked_add(old_size) != Some(arena.used) {
            return null_mut();
        }
        let Some(size) = Self::aligned_size(size) else {
            return null_mut();
        };
        let Some(end) = start.checked_add(size) else {
            return null_mut();
        };
        if end > arena.capacity {
            return null_mut();
        }
        arena.used = end;
        ptr
    }

    unsafe extern "C" fn free(_ctx: *mut c_void, _ptr: *mut c_void) {}
}

#[allow(clippy::cast_ptr_alignment)]
fn unsafe_yyjson_get_next_container(val: *mut yyjson_val) -> *mut yyjson_val {
    unsafe { (val.cast::<u8>().add((*val).uni.ofs)).cast::<yyjson_val>() }
}

#[allow(clippy::cast_ptr_alignment)]
fn unsafe_yyjson_get_next_non_container(val: *mut yyjson_val) -> *mut yyjson_val {
    unsafe { (val.cast::<u8>().add(YYJSON_VAL_SIZE)).cast::<yyjson_val>() }
}

pub(crate) fn deserialize(
    data: &'static str,
) -> Result<NonNull<crate::ffi::PyObject>, DeserializeError<'static>> {
    assume!(!data.is_empty());
    let Some(buffer_capacity) = buffer_capacity_to_allocate(data.len()) else {
        return Err(DeserializeError::from_yyjson(
            Cow::Borrowed("Not enough memory to allocate buffer for parsing"),
            0,
            data,
        ));
    };
    if buffer_capacity == MINIMUM_BUFFER_CAPACITY {
        return deserialize_small(data);
    }
    let buffer_ptr = unsafe { PyMem_Malloc(buffer_capacity) };
    if buffer_ptr.is_null() {
        return Err(DeserializeError::from_yyjson(
            Cow::Borrowed("Not enough memory to allocate buffer for parsing"),
            0,
            data,
        ));
    }
    let result = deserialize_with_buffer(data, buffer_ptr, buffer_capacity);
    unsafe {
        PyMem_Free(buffer_ptr);
    }
    result
}

// yyjson's arena needs pointer alignment, but not initialized contents. Keep the
// small-message arena in a separate frame so larger documents do not reserve it.
#[repr(C, align(16))]
struct SmallBuffer([MaybeUninit<u8>; MINIMUM_BUFFER_CAPACITY]);

#[inline(never)]
fn deserialize_small(
    data: &'static str,
) -> Result<NonNull<crate::ffi::PyObject>, DeserializeError<'static>> {
    let mut buffer = SmallBuffer([MaybeUninit::uninit(); MINIMUM_BUFFER_CAPACITY]);
    deserialize_with_buffer(data, buffer.0.as_mut_ptr().cast(), MINIMUM_BUFFER_CAPACITY)
}

fn deserialize_with_buffer(
    data: &'static str,
    buffer_ptr: *mut core::ffi::c_void,
    buffer_capacity: usize,
) -> Result<NonNull<crate::ffi::PyObject>, DeserializeError<'static>> {
    let mut arena = Arena::new(buffer_ptr, buffer_capacity);
    let alloc = yyjson_alc {
        malloc: Some(Arena::malloc),
        realloc: Some(Arena::realloc),
        free: Some(Arena::free),
        ctx: (&raw mut arena).cast(),
    };

    let mut err = yyjson_read_err {
        code: YYJSON_READ_SUCCESS,
        msg: null(),
        pos: 0,
    };

    let doc = unsafe {
        yyjson_read_opts(
            data.as_ptr().cast::<c_char>().cast_mut(),
            data.len(),
            &raw const alloc,
            &raw mut err,
        )
    };
    if doc.is_null() {
        let msg: Cow<str> = unsafe { core::ffi::CStr::from_ptr(err.msg).to_string_lossy() };
        #[allow(clippy::cast_possible_wrap)]
        let pos = err.pos as i64;
        return Err(DeserializeError::from_yyjson(msg, pos, data));
    }
    Ok(deserialize_tape(yyjson_doc_get_root(doc)))
}

enum ElementType {
    String,
    Uint64,
    Int64,
    Double,
    Null,
    True,
    False,
    Array,
    Object,
}

impl ElementType {
    fn from_tag(elem: *mut yyjson_val) -> Self {
        match unsafe { (*elem).tag as u8 } {
            TAG_STRING => Self::String,
            TAG_UINT64 => Self::Uint64,
            TAG_INT64 => Self::Int64,
            TAG_DOUBLE => Self::Double,
            TAG_NULL => Self::Null,
            TAG_TRUE => Self::True,
            TAG_FALSE => Self::False,
            TAG_ARRAY => Self::Array,
            TAG_OBJECT => Self::Object,
            _ => unreachable_unchecked!(),
        }
    }
}

#[inline(always)]
fn parse_yy_string(elem: *mut yyjson_val, len: usize) -> NonNull<crate::ffi::PyObject> {
    PyStrRef::from_str(str_from_slice!((*elem).uni.str_.cast::<u8>(), len)).as_non_null_ptr()
}

#[inline(always)]
fn parse_yy_u64(elem: *mut yyjson_val) -> NonNull<crate::ffi::PyObject> {
    PyIntRef::from_u64(unsafe { (*elem).uni.u64_ }).as_non_null_ptr()
}

#[inline(always)]
fn parse_yy_i64(elem: *mut yyjson_val) -> NonNull<crate::ffi::PyObject> {
    PyIntRef::from_i64(unsafe { (*elem).uni.i64_ }).as_non_null_ptr()
}

#[inline(always)]
fn parse_yy_f64(elem: *mut yyjson_val) -> NonNull<crate::ffi::PyObject> {
    PyFloatRef::from_f64(unsafe { (*elem).uni.f64_ }).as_non_null_ptr()
}

#[inline(never)]
fn deserialize_tape(val: *mut yyjson_val) -> NonNull<crate::ffi::PyObject> {
    match ElementType::from_tag(val) {
        ElementType::String => parse_yy_string(val, unsafe_yyjson_get_len(val)),
        ElementType::Uint64 => parse_yy_u64(val),
        ElementType::Int64 => parse_yy_i64(val),
        ElementType::Double => parse_yy_f64(val),
        ElementType::Null => PyNoneRef::none().as_non_null_ptr(),
        ElementType::True => PyBoolRef::pytrue().as_non_null_ptr(),
        ElementType::False => PyBoolRef::pyfalse().as_non_null_ptr(),
        ElementType::Array => {
            let len = unsafe_yyjson_get_len(val);
            let pyval = PyListRef::with_capacity(len);
            if len > 0 {
                populate_yy_array(pyval.clone(), val);
            }
            pyval.as_non_null_ptr()
        }
        ElementType::Object => {
            let len = unsafe_yyjson_get_len(val);
            let pyval = PyDictRef::with_capacity(len);
            if len > 0 {
                populate_yy_object(pyval.clone(), val);
            }
            pyval.as_non_null_ptr()
        }
    }
}

#[inline(never)]
fn populate_yy_array(mut list: PyListRef, elem: *mut yyjson_val) {
    unsafe {
        let len = unsafe_yyjson_get_len(elem);
        assume!(len >= 1);
        let mut next = unsafe_yyjson_get_first(elem);
        let mut i = 0;

        // Every primitive occupies one tape slot. Consume only an exact-double
        // prefix; the first differing tag resumes generic container traversal.
        // No Python object borrows the tape, and the list is private to this call.
        if len >= 16 && (*next).tag as u8 == TAG_DOUBLE {
            loop {
                list.set(i, parse_yy_f64(next).as_ptr());
                i += 1;
                next = next.add(1);
                if i == len || (*next).tag as u8 != TAG_DOUBLE {
                    break;
                }
            }
        }

        for i in i..len {
            let val = next;
            let len = unsafe_yyjson_get_len(val);
            next = unsafe_yyjson_get_next_non_container(val);

            match ElementType::from_tag(val) {
                ElementType::String => list.set(i, parse_yy_string(val, len).as_ptr()),
                ElementType::Uint64 => list.set(i, parse_yy_u64(val).as_ptr()),
                ElementType::Int64 => list.set(i, parse_yy_i64(val).as_ptr()),
                ElementType::Double => list.set(i, parse_yy_f64(val).as_ptr()),
                ElementType::Null => list.set(i, PyNoneRef::none().as_ptr()),
                ElementType::True => list.set(i, PyBoolRef::pytrue().as_ptr()),
                ElementType::False => list.set(i, PyBoolRef::pyfalse().as_ptr()),
                ElementType::Array => {
                    next = unsafe_yyjson_get_next_container(val);
                    let pyval = PyListRef::with_capacity(len);
                    list.set(i, pyval.as_ptr());
                    if len > 0 {
                        populate_yy_array(pyval, val);
                    }
                }
                ElementType::Object => {
                    next = unsafe_yyjson_get_next_container(val);
                    let pyval = PyDictRef::with_capacity(len);
                    list.set(i, pyval.as_ptr());
                    if len > 0 {
                        populate_yy_object(pyval.clone(), val);
                    }
                }
            }
        }
    }
}

#[inline(never)]
fn populate_yy_object(mut dict: PyDictRef, elem: *mut yyjson_val) {
    unsafe {
        let list_len = unsafe_yyjson_get_len(elem);
        assume!(list_len >= 1);
        let mut next_key = unsafe_yyjson_get_first(elem);
        let mut next_val = next_key.add(1);
        for _ in 0..list_len {
            let val = next_val;
            let len = unsafe_yyjson_get_len(val);
            let pykey = {
                let key_str = str_from_slice!(
                    (*next_key).uni.str_.cast::<u8>(),
                    unsafe_yyjson_get_len(next_key)
                );
                get_unicode_key(key_str)
            };
            next_key = unsafe_yyjson_get_next_non_container(val);
            next_val = next_key.add(1);
            match ElementType::from_tag(val) {
                ElementType::String => dict.set(pykey, parse_yy_string(val, len).as_ptr()),
                ElementType::Uint64 => dict.set(pykey, parse_yy_u64(val).as_ptr()),
                ElementType::Int64 => dict.set(pykey, parse_yy_i64(val).as_ptr()),
                ElementType::Double => dict.set(pykey, parse_yy_f64(val).as_ptr()),
                ElementType::Null => dict.set(pykey, PyNoneRef::none().as_ptr()),
                ElementType::True => dict.set(pykey, PyBoolRef::pytrue().as_ptr()),
                ElementType::False => dict.set(pykey, PyBoolRef::pyfalse().as_ptr()),
                ElementType::Array => {
                    next_key = unsafe_yyjson_get_next_container(val);
                    next_val = next_key.add(1);
                    let pyval = PyListRef::with_capacity(len);
                    dict.set(pykey, pyval.as_ptr());
                    if len > 0 {
                        populate_yy_array(pyval, val);
                    }
                }
                ElementType::Object => {
                    next_key = unsafe_yyjson_get_next_container(val);
                    next_val = next_key.add(1);
                    let pyval = PyDictRef::with_capacity(len);
                    dict.set(pykey, pyval.as_ptr());
                    if len > 0 {
                        populate_yy_object(pyval.clone(), val);
                    }
                }
            }
        }
    }
}
