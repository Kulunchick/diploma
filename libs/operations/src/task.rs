use ndarray::Array2;
use numpy::{PyArrayMethods, PyReadonlyArray2};
use pyo3::{exceptions::PyValueError, prelude::*};

#[pyclass]
pub struct Task {
    pub m: usize,
    pub n: usize,
    pub c: Array2<i64>,
    pub b_ij: Array2<i64>,
    pub b_total: i64,
    pub omega: Array2<f64>,
}

#[pymethods]
impl Task {
    #[new]
    pub fn new(
        m: usize,
        n: usize,
        c: PyReadonlyArray2<i64>,
        b_ij: PyReadonlyArray2<i64>,
        b_total: i64,
        omega: PyReadonlyArray2<f64>,
    ) -> PyResult<Self> {
        let c = c.to_owned_array();
        let b_ij = b_ij.to_owned_array();
        let omega = omega.to_owned_array();

        let task = Task { m, n, c, b_ij, b_total, omega };
        task.validate()?;
        Ok(task)
    }

    pub fn validate(&self) -> PyResult<bool> {
        if self.c.shape()[0] != self.m || self.c.shape()[1] != self.n {
            return Err(PyValueError::new_err("Некоректні розміри матриці вартості"));
        }
        if self.b_ij.shape()[0] != self.m || self.b_ij.shape()[1] != self.n {
            return Err(PyValueError::new_err("Некоректні розміри матриці витрат ресурсу"));
        }
        if self.omega.shape()[0] != self.m || self.omega.shape()[1] != self.n {
            return Err(PyValueError::new_err("Некоректні розміри матриці знижок"));
        }
        if self.omega.iter().any(|&x| x < 0.0 || x > 1.0) {
            return Err(PyValueError::new_err("Знижки повинні бути в діапазоні [0, 1]"));
        }
        if self.b_total <= 0 {
            return Err(PyValueError::new_err("Загальний ресурс повинен бути додатнім"));
        }
        Ok(true)
    }
}
