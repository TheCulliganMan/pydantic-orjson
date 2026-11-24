// SPDX-License-Identifier: MPL-2.0
// Copyright ijl (2024-2026)

use super::pyunicode_new::{
    pyunicode_ascii, pyunicode_fourbyte, pyunicode_onebyte, pyunicode_twobyte,
};

#[inline(never)]
pub(crate) unsafe fn str_impl_kind_scalar(buf: &str) -> *mut crate::ffi::PyObject {
    #[cfg(all(target_arch = "aarch64", target_endian = "little"))]
    if buf.len() >= 128 && buf.as_bytes()[0] <= 239 {
        return unsafe { str_impl_kind_neon(buf) };
    }
    let num_chars = bytecount::num_chars(buf.as_bytes());
    if buf.len() == num_chars {
        return pyunicode_ascii(buf.as_ptr(), num_chars);
    }
    unsafe {
        let len = buf.len();
        assume!(len > 0);

        if *(buf.as_bytes().as_ptr()) > 239 {
            cold_path!();
            return pyunicode_fourbyte(buf, num_chars);
        }

        let sptr = buf.as_bytes().as_ptr();

        let mut is_four = false;
        let mut not_latin = false;
        for i in 0..len {
            is_four |= *sptr.add(i) > 239;
            not_latin |= *sptr.add(i) > 195;
        }
        if is_four {
            pyunicode_fourbyte(buf, num_chars)
        } else if not_latin {
            pyunicode_twobyte(buf, num_chars)
        } else {
            pyunicode_onebyte(buf, num_chars)
        }
    }
}

// Keep short strings and an initial four-byte code point on the existing path.
// For long strings, skip ASCII prefixes without character-count arithmetic,
// then fuse UTF-8 continuation counting and maximum-byte classification.
#[cfg(all(target_arch = "aarch64", target_endian = "little"))]
#[inline]
#[target_feature(enable = "neon")]
unsafe fn str_impl_kind_neon(buf: &str) -> *mut crate::ffi::PyObject {
    use core::arch::aarch64::{
        uint8x16x4_t, vaddlvq_u8, vcltq_s8, vdupq_n_s8, vdupq_n_u8, vld1q_u8, vld1q_u8_x4,
        vmaxq_u8, vmaxvq_u8, vreinterpretq_s8_u8, vsubq_u8,
    };

    unsafe {
        let bytes = buf.as_bytes();
        let len = bytes.len();
        let ptr = bytes.as_ptr();
        let mut offset = 0;

        while len - offset >= 64 {
            let uint8x16x4_t(first, second, third, fourth) = vld1q_u8_x4(ptr.add(offset));
            let maximum = vmaxq_u8(vmaxq_u8(first, second), vmaxq_u8(third, fourth));
            if vmaxvq_u8(maximum) >= 128 {
                break;
            }
            offset += 64;
        }
        if len - offset < 64 && bytes[offset..].is_ascii() {
            return pyunicode_ascii(ptr, len);
        }

        let mut maximum = vdupq_n_u8(0);
        let mut continuations = 0usize;
        // UTF-8 continuation bytes 0x80..=0xbf are signed bytes below -64.
        let continuation_limit = vdupq_n_s8(-64);
        while len - offset >= 64 {
            let blocks = ((len - offset) / 64).min(255);
            let mut first_counts = vdupq_n_u8(0);
            let mut second_counts = vdupq_n_u8(0);
            let mut third_counts = vdupq_n_u8(0);
            let mut fourth_counts = vdupq_n_u8(0);
            for _ in 0..blocks {
                let uint8x16x4_t(first, second, third, fourth) = vld1q_u8_x4(ptr.add(offset));
                maximum = vmaxq_u8(
                    maximum,
                    vmaxq_u8(vmaxq_u8(first, second), vmaxq_u8(third, fourth)),
                );
                first_counts = vsubq_u8(
                    first_counts,
                    vcltq_s8(vreinterpretq_s8_u8(first), continuation_limit),
                );
                second_counts = vsubq_u8(
                    second_counts,
                    vcltq_s8(vreinterpretq_s8_u8(second), continuation_limit),
                );
                third_counts = vsubq_u8(
                    third_counts,
                    vcltq_s8(vreinterpretq_s8_u8(third), continuation_limit),
                );
                fourth_counts = vsubq_u8(
                    fourth_counts,
                    vcltq_s8(vreinterpretq_s8_u8(fourth), continuation_limit),
                );
                offset += 64;
            }
            // Each lane holds at most 255. Widen before horizontally summing:
            // vaddvq_u8 would wrap when the sixteen lane totals exceed 255.
            continuations += usize::from(vaddlvq_u8(first_counts))
                + usize::from(vaddlvq_u8(second_counts))
                + usize::from(vaddlvq_u8(third_counts))
                + usize::from(vaddlvq_u8(fourth_counts));
        }

        let mut tail_counts = vdupq_n_u8(0);
        while len - offset >= 16 {
            let chunk = vld1q_u8(ptr.add(offset));
            maximum = vmaxq_u8(maximum, chunk);
            tail_counts = vsubq_u8(
                tail_counts,
                vcltq_s8(vreinterpretq_s8_u8(chunk), continuation_limit),
            );
            offset += 16;
        }
        continuations += usize::from(vaddlvq_u8(tail_counts));
        let mut max_byte = vmaxvq_u8(maximum);
        for &byte in &bytes[offset..] {
            max_byte = max_byte.max(byte);
            continuations += usize::from(byte & 0xc0 == 0x80);
        }
        let num_chars = len - continuations;
        if max_byte < 128 {
            pyunicode_ascii(ptr, num_chars)
        } else if max_byte <= 195 {
            pyunicode_onebyte(buf, num_chars)
        } else if max_byte <= 239 {
            pyunicode_twobyte(buf, num_chars)
        } else {
            pyunicode_fourbyte(buf, num_chars)
        }
    }
}
