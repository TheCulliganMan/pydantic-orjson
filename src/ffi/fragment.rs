// SPDX-License-Identifier: MPL-2.0
// Copyright ijl (2020-2026)

use crate::ffi::{
    Py_DECREF, Py_INCREF, Py_TPFLAGS_DEFAULT, Py_TPFLAGS_IMMUTABLETYPE, Py_tp_dealloc, Py_tp_new,
    PyErr_SetObject, PyExc_TypeError, PyObject, PyObject_Type, PyTupleRef, PyType_FromSpec,
    PyType_Slot, PyType_Spec, PyTypeObject, PyUnicode_FromStringAndSize,
};
use crate::typeref::FRAGMENT_TYPE;
use core::ffi::{c_char, c_void};
use core::ptr::null_mut;

#[repr(C)]
pub(crate) struct Fragment {
    #[cfg(Py_GIL_DISABLED)]
    pub ob_base: PyObject,
    #[cfg(not(Py_GIL_DISABLED))]
    pub ob_refcnt: pyo3_ffi::Py_ssize_t,
    #[cfg(PyPy)]
    pub ob_pypy_link: pyo3_ffi::Py_ssize_t,
    #[cfg(not(Py_GIL_DISABLED))]
    pub ob_type: *mut pyo3_ffi::PyTypeObject,
    pub contents: *mut pyo3_ffi::PyObject,
}

#[cold]
#[inline(never)]
#[cfg_attr(feature = "optimize", optimize(size))]
fn raise_args_exception() {
    unsafe {
        let msg = "orjson.Fragment() takes exactly 1 positional argument";
        let err_msg =
            PyUnicode_FromStringAndSize(msg.as_ptr().cast::<c_char>(), msg.len().cast_signed());
        PyErr_SetObject(PyExc_TypeError, err_msg);
        Py_DECREF(err_msg);
    };
}

#[unsafe(no_mangle)]
#[cold]
#[cfg_attr(feature = "optimize", optimize(size))]
pub(crate) unsafe extern "C" fn orjson_fragment_tp_new(
    _subtype: *mut PyTypeObject,
    args: *mut PyObject,
    kwds: *mut PyObject,
) -> *mut PyObject {
    unsafe {
        let argsob = PyTupleRef::from_ptr_unchecked(args);
        if argsob.len() != 1 || !kwds.is_null() {
            raise_args_exception();
            null_mut()
        } else {
            let contents = argsob.get(0);
            #[cfg(Py_GIL_DISABLED)]
            {
                // Python objects must use the object allocator in a free-threaded
                // build. GenericAlloc also initializes the owning thread and
                // biased reference counts, and retains the heap type.
                let obj = pyo3_ffi::PyType_GenericAlloc(FRAGMENT_TYPE, 0);
                if obj.is_null() {
                    return null_mut();
                }
                Py_INCREF(contents);
                (*obj.cast::<Fragment>()).contents = contents;
                obj
            }
            #[cfg(not(Py_GIL_DISABLED))]
            {
                Py_INCREF(contents);
                Py_INCREF(FRAGMENT_TYPE.cast::<PyObject>());
                let obj = Box::new(Fragment {
                    ob_refcnt: 1,
                    #[cfg(PyPy)]
                    ob_pypy_link: 0,
                    ob_type: FRAGMENT_TYPE,
                    contents: contents,
                });
                Box::into_raw(obj).cast::<PyObject>()
            }
        }
    }
}

#[unsafe(no_mangle)]
#[cold]
#[cfg_attr(feature = "optimize", optimize(size))]
pub(crate) unsafe extern "C" fn orjson_fragment_dealloc(object: *mut PyObject) {
    unsafe {
        let object_type = PyObject_Type(object);
        Py_DECREF((*object.cast::<Fragment>()).contents);
        #[cfg(Py_GIL_DISABLED)]
        pyo3_ffi::PyObject_Free(object.cast::<core::ffi::c_void>());
        #[cfg(not(Py_GIL_DISABLED))]
        crate::ffi::PyMem_Free(object.cast::<core::ffi::c_void>());
        Py_DECREF(object_type.cast::<PyObject>());
    }
}

#[unsafe(no_mangle)]
#[cold]
#[cfg_attr(feature = "optimize", optimize(size))]
pub(crate) unsafe extern "C" fn orjson_fragmenttype_new() -> *mut PyTypeObject {
    unsafe {
        let mut slots = [
            PyType_Slot {
                slot: Py_tp_new,
                pfunc: orjson_fragment_tp_new as *mut c_void,
            },
            PyType_Slot {
                slot: Py_tp_dealloc,
                pfunc: orjson_fragment_dealloc as *mut c_void,
            },
            PyType_Slot {
                slot: 0,
                pfunc: null_mut(),
            },
        ];
        let mut spec = PyType_Spec {
            name: c"orjson.Fragment".as_ptr(),
            basicsize: core::mem::size_of::<Fragment>().cast_signed() as i32,
            itemsize: 0,
            flags: (Py_TPFLAGS_DEFAULT | Py_TPFLAGS_IMMUTABLETYPE) as u32,
            slots: &raw mut slots[0],
        };
        PyType_FromSpec(&raw mut spec).cast::<PyTypeObject>()
    }
}
