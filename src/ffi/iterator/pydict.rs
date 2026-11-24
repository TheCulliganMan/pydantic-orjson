// SPDX-License-Identifier: MPL-2.0
// Copyright ijl (2026)

#[cfg(Py_GIL_DISABLED)]
use super::snapshot::{OwnedPyRef, with_critical_section};
#[cfg(not(Py_GIL_DISABLED))]
use crate::ffi::PyObject;
use crate::ffi::{BorrowedPyRef, PyDictRef};

pub(crate) struct PyDictIterator {
    #[cfg(not(Py_GIL_DISABLED))]
    ob: PyDictRef,
    idx: usize,
    #[cfg(not(Py_GIL_DISABLED))]
    len: usize,
    #[cfg(not(Py_GIL_DISABLED))]
    pos: isize,
    #[cfg(not(Py_GIL_DISABLED))]
    next_key: *mut PyObject,
    #[cfg(not(Py_GIL_DISABLED))]
    next_value: *mut PyObject,
    #[cfg(Py_GIL_DISABLED)]
    items: Vec<(OwnedPyRef, OwnedPyRef)>,
}

impl PyDictIterator {
    #[inline]
    pub fn from_dict(ob: PyDictRef) -> Self {
        #[cfg(not(Py_GIL_DISABLED))]
        {
            let len = ob.len();
            Self {
                ob: ob,
                idx: 0,
                len: len,
                pos: 0,
                next_key: core::ptr::null_mut(),
                next_value: core::ptr::null_mut(),
            }
        }
        #[cfg(Py_GIL_DISABLED)]
        {
            let items = with_critical_section(ob.as_ptr(), || {
                let mut items = Vec::with_capacity(ob.len());
                let mut pos = 0;
                let mut key = core::ptr::null_mut();
                let mut value = core::ptr::null_mut();
                while unsafe {
                    crate::ffi::PyDict_Next(ob.as_ptr(), &raw mut pos, &raw mut key, &raw mut value)
                } != 0
                {
                    items.push((
                        OwnedPyRef::from_borrowed(key),
                        OwnedPyRef::from_borrowed(value),
                    ));
                }
                items
            });
            Self { idx: 0, items }
        }
    }

    pub fn len(&self) -> usize {
        #[cfg(not(Py_GIL_DISABLED))]
        {
            self.len
        }
        #[cfg(Py_GIL_DISABLED)]
        {
            self.items.len() - self.idx
        }
    }
}

impl Iterator for PyDictIterator {
    type Item = (BorrowedPyRef, BorrowedPyRef);

    #[inline(always)]
    fn next(&mut self) -> Option<Self::Item> {
        #[cfg(not(Py_GIL_DISABLED))]
        {
            if self.idx == self.len() {
                return None;
            }

            unsafe {
                crate::ffi::PyDict_Next(
                    self.ob.as_ptr(),
                    &raw mut self.pos,
                    &raw mut self.next_key,
                    &raw mut self.next_value,
                );
            }

            self.idx += 1;
            Some((
                BorrowedPyRef::from_ptr(self.next_key),
                BorrowedPyRef::from_ptr(self.next_value),
            ))
        }
        #[cfg(Py_GIL_DISABLED)]
        {
            let (key, value) = self.items.get(self.idx)?;
            self.idx += 1;
            Some((
                BorrowedPyRef::from_ptr(key.as_ptr()),
                BorrowedPyRef::from_ptr(value.as_ptr()),
            ))
        }
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        let len = self.len();
        (len, Some(len))
    }
}

impl ExactSizeIterator for PyDictIterator {
    fn len(&self) -> usize {
        self.len()
    }
}

impl core::iter::FusedIterator for PyDictIterator {}

#[cfg(feature = "trusted_len")]
unsafe impl core::iter::TrustedLen for PyDictIterator {}
