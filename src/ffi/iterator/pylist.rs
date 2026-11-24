// SPDX-License-Identifier: MPL-2.0
// Copyright ijl (2026)

#[cfg(Py_GIL_DISABLED)]
use super::snapshot::{OwnedPyRef, with_critical_section};
use crate::ffi::{BorrowedPyRef, PyListRef};

pub(crate) struct PyListIterator {
    #[cfg(not(Py_GIL_DISABLED))]
    ob: PyListRef,
    idx: usize,
    #[cfg(not(Py_GIL_DISABLED))]
    len: usize,
    #[cfg(Py_GIL_DISABLED)]
    items: Vec<OwnedPyRef>,
}

impl PyListIterator {
    #[inline]
    pub fn from_list(ob: PyListRef) -> Self {
        #[cfg(not(Py_GIL_DISABLED))]
        {
            let len = ob.len();
            Self {
                ob: ob,
                idx: 0,
                len: len,
            }
        }
        #[cfg(Py_GIL_DISABLED)]
        {
            let items = with_critical_section(ob.as_ptr(), || {
                // Both the length and item storage are protected by this lock.
                let len = unsafe { crate::ffi::Py_SIZE(ob.as_ptr()) as usize };
                let mut items = Vec::with_capacity(len);
                for idx in 0..len {
                    let ptr = unsafe { *ob.data_ptr().add(idx) };
                    items.push(OwnedPyRef::from_borrowed(ptr));
                }
                items
            });
            Self { idx: 0, items }
        }
    }

    #[inline]
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

impl Iterator for PyListIterator {
    type Item = BorrowedPyRef;

    #[inline]
    fn next(&mut self) -> Option<Self::Item> {
        #[cfg(not(Py_GIL_DISABLED))]
        {
            if self.idx == self.len() {
                return None;
            }
            let value = self.ob.get(self.idx);
            self.idx += 1;
            Some(BorrowedPyRef::from_ptr(value))
        }
        #[cfg(Py_GIL_DISABLED)]
        {
            let value = self.items.get(self.idx)?.as_ptr();
            self.idx += 1;
            // Keep every owned item in the iterator through the loop body.
            Some(BorrowedPyRef::from_ptr(value))
        }
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        (self.len(), Some(self.len()))
    }
}

impl ExactSizeIterator for PyListIterator {
    fn len(&self) -> usize {
        self.len()
    }
}

impl core::iter::FusedIterator for PyListIterator {}

#[cfg(feature = "trusted_len")]
unsafe impl core::iter::TrustedLen for PyListIterator {}
