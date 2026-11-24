// SPDX-License-Identifier: MPL-2.0

use core::arch::aarch64::{
    vceqq_u8, vcltq_u8, vdupq_n_u8, vld1q_u8, vmaxvq_u8, vorrq_u8, vst1q_u8,
};

/// Escape strings in 64-byte and 16-byte chunks on stable AArch64 builds.
///
/// Full vector loads are restricted to the input length. Chunks containing an
/// escape and the final partial chunk use the existing scalar encoder, keeping
/// identical escaping and avoiding scratch-buffer reads beyond the string.
#[target_feature(enable = "neon")]
pub(crate) unsafe fn format_escaped_str_impl_neon_128(
    odst: *mut u8,
    value_ptr: *const u8,
    value_len: usize,
) -> usize {
    unsafe {
        const STRIDE: usize = 16;

        let mut dst = odst;
        let mut src = value_ptr;
        let mut remaining = value_len;

        core::ptr::write(dst, b'"');
        dst = dst.add(1);

        if remaining >= STRIDE {
            let backslash = vdupq_n_u8(b'\\');
            let quote = vdupq_n_u8(b'"');
            let control = vdupq_n_u8(32);

            macro_rules! escape_mask {
                ($chunk:expr) => {
                    vorrq_u8(
                        vorrq_u8(vceqq_u8($chunk, backslash), vceqq_u8($chunk, quote)),
                        vcltq_u8($chunk, control),
                    )
                };
            }

            // Amortize the horizontal reduction and branch over four vectors
            // for the common unescaped prefix. Stop this loop at the first
            // escape so dense inputs are not repeatedly scanned in 64-byte
            // windows before the scalar escape path processes their bytes.
            while remaining >= STRIDE * 4 {
                let first = vld1q_u8(src);
                let second = vld1q_u8(src.add(STRIDE));
                let third = vld1q_u8(src.add(STRIDE * 2));
                let fourth = vld1q_u8(src.add(STRIDE * 3));
                let escaped = vorrq_u8(
                    vorrq_u8(escape_mask!(first), escape_mask!(second)),
                    vorrq_u8(escape_mask!(third), escape_mask!(fourth)),
                );
                if vmaxvq_u8(escaped) != 0 {
                    break;
                }
                vst1q_u8(dst, first);
                vst1q_u8(dst.add(STRIDE), second);
                vst1q_u8(dst.add(STRIDE * 2), third);
                vst1q_u8(dst.add(STRIDE * 3), fourth);
                src = src.add(STRIDE * 4);
                dst = dst.add(STRIDE * 4);
                remaining -= STRIDE * 4;
            }

            while remaining >= STRIDE {
                let chunk = vld1q_u8(src);
                let escaped = escape_mask!(chunk);
                if vmaxvq_u8(escaped) == 0 {
                    vst1q_u8(dst, chunk);
                    dst = dst.add(STRIDE);
                    src = src.add(STRIDE);
                } else {
                    impl_format_scalar!(dst, src, STRIDE);
                }
                remaining -= STRIDE;
            }
        }

        impl_format_scalar!(dst, src, remaining);

        core::ptr::write(dst, b'"');
        dst = dst.add(1);

        dst as usize - odst as usize
    }
}
