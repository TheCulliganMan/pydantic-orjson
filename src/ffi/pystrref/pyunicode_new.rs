// SPDX-License-Identifier: MPL-2.0
// Copyright ijl (2023-2026)

use crate::ffi::{PyASCIIObject, PyCompactUnicodeObject, PyObject, PyUnicode_New};
use crate::util::usize_to_isize;

macro_rules! validate_str {
    ($ptr:expr) => {
        #[cfg(all(CPython, not(Py_LIMITED_ABI)))]
        debug_assert!(crate::ffi::_PyUnicode_CheckConsistency($ptr.cast::<PyObject>(), 1) == 1)
    };
}

// ASCII spans in an otherwise wide string can be widened a lane at a time.
// The fixed-size loop is vectorizable on baseline NEON/SSE2. Keep short strings
// and strings beginning with non-ASCII on the original scalar path.
#[inline(always)]
unsafe fn write_unicode<T>(buf: &str, mut data_ptr: *mut T, convert: impl Fn(char) -> T) -> *mut T {
    unsafe {
        let mut chars = buf.chars();
        if buf.len() >= 64 && buf.as_bytes()[0].is_ascii() {
            const WIDTH: usize = 16;
            const HIGH_BITS: u64 = 0x8080_8080_8080_8080;
            while chars.as_str().len() >= WIDTH {
                let remaining = chars.as_str();
                let src = remaining.as_ptr();
                // Both reads stay within the remaining, validated UTF-8 slice.
                let ascii = *src < 128
                    && (src.cast::<u64>().read_unaligned()
                        | src.add(8).cast::<u64>().read_unaligned())
                        & HIGH_BITS
                        == 0;
                if ascii {
                    for lane in 0..WIDTH {
                        core::ptr::write(data_ptr.add(lane), convert(*src.add(lane) as char));
                    }
                    data_ptr = data_ptr.add(WIDTH);
                    // Every consumed byte is ASCII, so this is a char boundary.
                    chars = remaining.get_unchecked(WIDTH..).chars();
                } else {
                    // Consume a whole failed window before checking again. This
                    // avoids rescanning each byte of a short ASCII prefix.
                    let stop = remaining.len() - WIDTH;
                    while chars.as_str().len() > stop {
                        core::ptr::write(data_ptr, convert(chars.next().unwrap_unchecked()));
                        data_ptr = data_ptr.add(1);
                    }
                }
            }
        }
        for each in chars {
            core::ptr::write(data_ptr, convert(each));
            data_ptr = data_ptr.add(1);
        }
        data_ptr
    }
}

#[inline(never)]
pub(crate) fn pyunicode_ascii(buf: *const u8, num_chars: usize) -> *mut PyObject {
    unsafe {
        let ptr = PyUnicode_New(usize_to_isize(num_chars), 127);
        let data_ptr = ptr.cast::<PyASCIIObject>().add(1).cast::<u8>();
        core::ptr::copy_nonoverlapping(buf, data_ptr, num_chars);
        core::ptr::write(data_ptr.add(num_chars), 0);
        validate_str!(ptr);
        ptr.cast::<PyObject>()
    }
}

#[cold]
#[inline(never)]
pub(crate) fn pyunicode_onebyte(buf: &str, num_chars: usize) -> *mut PyObject {
    unsafe {
        let ptr = PyUnicode_New(usize_to_isize(num_chars), 255);
        let mut data_ptr = ptr.cast::<PyCompactUnicodeObject>().add(1).cast::<u8>();
        for each in buf.chars().fuse() {
            core::ptr::write(data_ptr, each as u8);
            data_ptr = data_ptr.add(1);
        }
        core::ptr::write(data_ptr, 0);
        validate_str!(ptr);
        ptr.cast::<PyObject>()
    }
}

#[inline(never)]
pub(crate) fn pyunicode_twobyte(buf: &str, num_chars: usize) -> *mut PyObject {
    unsafe {
        let ptr = PyUnicode_New(usize_to_isize(num_chars), 65535);
        let data_ptr = ptr.cast::<PyCompactUnicodeObject>().add(1).cast::<u16>();
        let data_ptr = write_unicode(buf, data_ptr, |each| each as u16);
        core::ptr::write(data_ptr, 0);
        validate_str!(ptr);
        ptr.cast::<PyObject>()
    }
}

#[inline(never)]
pub(crate) fn pyunicode_fourbyte(buf: &str, num_chars: usize) -> *mut PyObject {
    unsafe {
        let ptr = PyUnicode_New(usize_to_isize(num_chars), 1114111);
        let data_ptr = ptr.cast::<PyCompactUnicodeObject>().add(1).cast::<u32>();
        let data_ptr = write_unicode(buf, data_ptr, |each| each as u32);
        core::ptr::write(data_ptr, 0);
        validate_str!(ptr);
        ptr.cast::<PyObject>()
    }
}
