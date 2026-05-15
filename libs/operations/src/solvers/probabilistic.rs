use ndarray::Array2;
use numpy::{PyArray, Ix2, ToPyArray};
use pyo3::{prelude::*, types::PyDict};
use rayon::prelude::*;

use crate::common::{construct_solution, heuristic, objective};
use crate::task::Task;

#[pyclass]
pub struct ProbabilisticAssignmentSolver {
    kmax: usize,
    iteration_callback: Option<PyObject>,
}

#[pymethods]
impl ProbabilisticAssignmentSolver {
    #[new]
    #[pyo3(signature = (kmax = 100))]
    pub fn new(kmax: usize) -> Self {
        ProbabilisticAssignmentSolver { kmax, iteration_callback: None }
    }

    pub fn set_iteration_callback(&mut self, callback: PyObject) {
        self.iteration_callback = Some(callback);
    }

    pub fn solve<'py>(
        &self,
        py: Python<'py>,
        task: &'py Task,
    ) -> PyResult<(Bound<'py, PyArray<i64, Ix2>>, f64)> {
        let score = heuristic(&task.c, &task.b_ij, &task.omega);

        let mut f_best = 0.0_f64;
        let mut x_best = Array2::<i64>::zeros((task.m, task.n));

        if self.iteration_callback.is_some() {
            // Sequential mode: fire callback after each iteration
            for k in 0..self.kmax {
                let x = construct_solution(&task.b_ij, task.b_total, &score);
                let f = objective(&x, &task.c, &task.omega);

                if f > f_best {
                    f_best = f;
                    x_best.assign(&x);
                }

                if let Some(ref cb) = self.iteration_callback {
                    let data = PyDict::new(py);
                    data.set_item("iteration", k + 1)?;
                    data.set_item("current_best_value", f_best)?;
                    cb.call1(py, (data,))?;
                }
            }
        } else {
            // Parallel mode: use par_iter for maximum performance
            let solutions: Vec<(Array2<i64>, f64)> = (0..self.kmax)
                .into_par_iter()
                .map(|_| {
                    let x = construct_solution(&task.b_ij, task.b_total, &score);
                    let f = objective(&x, &task.c, &task.omega);
                    (x, f)
                })
                .collect();

            for (x, f) in solutions {
                if f > f_best {
                    f_best = f;
                    x_best.assign(&x);
                }
            }
        }

        Ok((x_best.to_pyarray(py).to_owned(), f_best))
    }
}
