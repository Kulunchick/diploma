use ndarray::{Array2, Zip};
use numpy::{PyArray, Ix2, ToPyArray};
use pyo3::{prelude::*, types::PyDict};
use rayon::prelude::*;

use crate::common::{construct_solution, heuristic, objective};
use crate::task::Task;

#[pyclass]
pub struct AntColonyAssignmentSolver {
    num_ants: usize,
    kmax: usize,
    alpha: f64,
    beta: f64,
    rho: f64,
    initial_pheromone: f64,
    iteration_callback: Option<PyObject>,
}

#[pymethods]
impl AntColonyAssignmentSolver {
    #[new]
    #[pyo3(
        signature = (
            num_ants = 20,
            kmax = 100,
            alpha = 1.0,
            beta = 2.0,
            rho = 0.1,
            initial_pheromone = 1.0
        )
    )]
    pub fn new(
        num_ants: usize,
        kmax: usize,
        alpha: f64,
        beta: f64,
        rho: f64,
        initial_pheromone: f64,
    ) -> Self {
        AntColonyAssignmentSolver {
            num_ants,
            kmax,
            alpha,
            beta,
            rho,
            initial_pheromone,
            iteration_callback: None,
        }
    }

    pub fn set_iteration_callback(&mut self, callback: PyObject) {
        self.iteration_callback = Some(callback);
    }

    pub fn solve<'py>(
        &self,
        py: Python<'py>,
        task: &'py Task,
    ) -> PyResult<(Bound<'py, PyArray<i64, Ix2>>, f64)> {
        let h = heuristic(&task.c, &task.b_ij, &task.omega);

        let q = {
            let avg_b = task.b_ij.sum() as f64 / (task.m * task.n) as f64;
            task.b_total as f64 / avg_b * task.c.iter().fold(0_i64, |m, &x| m.max(x)) as f64
        };

        let mut pheromone = Array2::<f64>::from_elem((task.m, task.n), self.initial_pheromone);
        let mut f_best = 0.0_f64;
        let mut x_best = Array2::<i64>::zeros((task.m, task.n));

        for k in 0..self.kmax {
            // Score is shared across all ants in this iteration — pheromone is fixed mid-iteration
            let score = Zip::from(&pheromone)
                .and(&h)
                .map_collect(|&p, &hi| p.powf(self.alpha) * hi.powf(self.beta));

            let ant_solutions: Vec<(Array2<i64>, f64)> = (0..self.num_ants)
                .into_par_iter()
                .map(|_| {
                    let x = construct_solution(&task.b_ij, task.b_total, &score);
                    let f = objective(&x, &task.c, &task.omega);
                    (x, f)
                })
                .collect();

            for (x, f) in &ant_solutions {
                if *f > f_best {
                    f_best = *f;
                    x_best.assign(x);
                }
            }

            pheromone.mapv_inplace(|p| p * (1.0 - self.rho));
            for (x, f) in &ant_solutions {
                Zip::from(&mut pheromone).and(x).for_each(|p, &x_val| {
                    if x_val == 1 {
                        *p += f / q;
                    }
                });
            }

            if let Some(ref cb) = self.iteration_callback {
                let data = PyDict::new(py);
                data.set_item("iteration", k + 1)?;
                data.set_item("current_best_value", f_best)?;
                cb.call1(py, (data,))?;
            }
        }

        Ok((x_best.to_pyarray(py).to_owned(), f_best))
    }
}
