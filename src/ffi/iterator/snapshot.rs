// SPDX-License-Identifier: MPL-2.0
// Copyright ijl (2026)

use pyo3_ffi::{PyCriticalSection, PyCriticalSection_Begin, PyCriticalSection_End, PyObject};

// Only pointer copies, INCREFs, and Rust allocations may run in this section.
// Calling Python can suspend a critical section, invalidating borrowed values.
#[inline]
pub(super) fn with_critical_section<T>(object: *mut PyObject, snapshot: impl FnOnce() -> T) -> T {
    struct Guard(*mut PyCriticalSection);
    impl Drop for Guard {
        fn drop(&mut self) {
            unsafe { PyCriticalSection_End(self.0) };
        }
    }

    // Keep the section at a stable stack address until its guard has ended it.
    let mut section = core::mem::MaybeUninit::<PyCriticalSection>::uninit();
    unsafe { PyCriticalSection_Begin(section.as_mut_ptr(), object) };
    let _guard = Guard(section.as_mut_ptr());
    snapshot()
}

pub(super) struct OwnedPyRef(*mut PyObject);

impl OwnedPyRef {
    // The caller must hold the container's critical section while acquiring
    // ownership of a borrowed item. INCREF after releasing the lock is too late.
    #[inline]
    pub(super) fn from_borrowed(ptr: *mut PyObject) -> Self {
        unsafe { pyo3_ffi::Py_INCREF(ptr) };
        Self(ptr)
    }

    #[inline]
    pub(super) fn as_ptr(&self) -> *mut PyObject {
        self.0
    }
}

impl Drop for OwnedPyRef {
    fn drop(&mut self) {
        unsafe { pyo3_ffi::Py_DECREF(self.0) };
    }
}
