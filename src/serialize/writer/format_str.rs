// SPDX-License-Identifier: MPL-2.0
// Copyright ijl (2024-2026)

use crate::serialize::writer::{BytesWriter, JsonWriter};

// Preserve the existing writer API and inline through the architecture-selected
// dispatcher. The caller reserves space before invoking the string formatter.
#[inline(always)]
pub(crate) fn format_escaped_str(writer: &mut BytesWriter, value: &str) -> usize {
    unsafe { format_escaped_str_to(writer.as_mut_buffer_ptr(), value) }
}

#[cfg(all(
    target_arch = "x86_64",
    feature = "avx512",
    not(target_feature = "avx512vl")
))]
type StrFormatter = unsafe fn(*mut u8, *const u8, usize) -> usize;

pub(crate) fn set_str_formatter_fn() {
    unsafe {
        #[cfg(all(
            target_arch = "x86_64",
            feature = "avx512",
            not(target_feature = "avx512vl")
        ))]
        if std::is_x86_feature_detected!("avx512vl") {
            STR_FORMATTER_FN = crate::serialize::writer::str::format_escaped_str_impl_512vl;
        }
    }
}

#[cfg(all(
    target_arch = "x86_64",
    feature = "avx512",
    not(target_feature = "avx512vl")
))]
static mut STR_FORMATTER_FN: StrFormatter =
    crate::serialize::writer::str::format_escaped_str_impl_sse2_128;

#[cfg(all(target_arch = "x86_64", not(feature = "avx512")))]
#[inline(always)]
/// # Safety
/// `dst` must point to at least `6 * value.len() + 33` writable bytes. This
/// includes the largest escape expansion and the trailing 32-byte SIMD store.
/// The destination must not overlap the input string.
pub(crate) unsafe fn format_escaped_str_to(dst: *mut u8, value: &str) -> usize {
    unsafe {
        crate::serialize::writer::str::format_escaped_str_impl_sse2_128(
            dst,
            value.as_bytes().as_ptr(),
            value.len(),
        )
    }
}

#[cfg(all(
    target_arch = "x86_64",
    feature = "avx512",
    not(target_feature = "avx512vl")
))]
#[inline(always)]
/// # Safety
/// `dst` must point to at least `6 * value.len() + 33` writable bytes. This
/// includes the largest escape expansion and the trailing 32-byte SIMD store.
/// The destination must not overlap the input string.
pub(crate) unsafe fn format_escaped_str_to(dst: *mut u8, value: &str) -> usize {
    unsafe { STR_FORMATTER_FN(dst, value.as_bytes().as_ptr(), value.len()) }
}

#[cfg(all(
    target_arch = "x86_64",
    feature = "avx512",
    target_feature = "avx512vl"
))]
#[inline(always)]
/// # Safety
/// `dst` must point to at least `6 * value.len() + 33` writable bytes. This
/// includes the largest escape expansion and the trailing 32-byte SIMD store.
/// The destination must not overlap the input string.
pub(crate) unsafe fn format_escaped_str_to(dst: *mut u8, value: &str) -> usize {
    unsafe {
        crate::serialize::writer::str::format_escaped_str_impl_512vl(
            dst,
            value.as_bytes().as_ptr(),
            value.len(),
        )
    }
}

#[cfg(all(not(target_arch = "x86_64"), feature = "generic_simd"))]
#[inline(always)]
/// # Safety
/// `dst` must point to at least `6 * value.len() + 33` writable bytes. This
/// includes the largest escape expansion and the trailing 32-byte SIMD store.
/// The destination must not overlap the input string.
pub(crate) unsafe fn format_escaped_str_to(dst: *mut u8, value: &str) -> usize {
    unsafe {
        crate::serialize::writer::str::format_escaped_str_impl_generic_128(
            dst,
            value.as_bytes().as_ptr(),
            value.len(),
        )
    }
}

#[cfg(all(target_arch = "aarch64", not(feature = "generic_simd")))]
#[inline(always)]
/// # Safety
/// `dst` must point to at least `6 * value.len() + 33` writable bytes. This
/// includes the largest escape expansion and the trailing 32-byte SIMD store.
/// The destination must not overlap the input string.
pub(crate) unsafe fn format_escaped_str_to(dst: *mut u8, value: &str) -> usize {
    unsafe {
        crate::serialize::writer::str::format_escaped_str_impl_neon_128(
            dst,
            value.as_bytes().as_ptr(),
            value.len(),
        )
    }
}

#[cfg(all(
    not(any(target_arch = "x86_64", target_arch = "aarch64")),
    not(feature = "generic_simd")
))]
#[inline(always)]
/// # Safety
/// `dst` must point to at least `6 * value.len() + 33` writable bytes. This
/// includes the largest escape expansion and the trailing 32-byte SIMD store.
/// The destination must not overlap the input string.
pub(crate) unsafe fn format_escaped_str_to(dst: *mut u8, value: &str) -> usize {
    unsafe {
        crate::serialize::writer::str::format_escaped_str_scalar(
            dst,
            value.as_bytes().as_ptr(),
            value.len(),
        )
    }
}
