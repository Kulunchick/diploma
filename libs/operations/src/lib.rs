use ndarray::{Array2, Ix2, Zip};
use numpy::{PyArray, PyArrayMethods, PyReadonlyArray2, ToPyArray};
use pyo3::{
    exceptions::PyValueError,
    prelude::*
};
use rand::{distr::weighted::WeightedIndex, prelude::*, rng};
use rayon::prelude::*;

#[pyclass]
pub struct Task {
    m: usize,
    n: usize,
    c: Array2<i64>,
    b_ij: Array2<i64>,
    b_total: i64,
    omega: Array2<f64>,
}

#[pymethods]
impl Task {
    #[new]
    fn new(
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

        let task = Task {
            m,
            n,
            c,
            b_ij,
            b_total,
            omega,
        };

        task.validate()?;
        Ok(task)
    }

    fn validate(&self) -> PyResult<bool> {
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

#[pyclass]
struct AntColonyAssignmentSolver {
    num_ants: usize,
    kmax: usize,
    alpha: f64,
    beta: f64,
    rho: f64,
    initial_pheromone: f64,
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
    fn new(
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
        }
    }

    pub fn solve<'py>(&self, py: Python<'py>, task: &'py Task) -> PyResult<(Bound<'py, PyArray<i64, Ix2>>, f64)> {
        let mut pheromone = Array2::<f64>::from_elem((task.m, task.n), self.initial_pheromone);

        // Попередньо обчислюємо евристику
        let heuristic = Array2::from_shape_fn((task.m, task.n), |(i, j)| {
            if task.b_ij[[i, j]] != 0 {
                (task.c[[i, j]] as f64 * (1.0 - task.omega[[i, j]])) / task.b_ij[[i, j]] as f64
            } else {
                0.0
            }
        });

        let q = {
            let avg_b = task.b_ij.sum() as f64 / (task.m * task.n) as f64;
            task.b_total as f64 / avg_b * task.c.iter().fold(0_i64, |max, &x| max.max(x)) as f64
        };

        let mut f_best = 0.0;
        let mut x_best = Array2::<i64>::zeros((task.m, task.n));

        // Паралельні ітерації по колоніях
        for _ in 0..self.kmax {
            let ant_solutions: Vec<_> = (0..self.num_ants)
                .into_par_iter() // Паралельна ітерація
                .map(|_| {
                    let mut local_rng = rng();
                    let mut x = Array2::<i64>::zeros((task.m, task.n));
                    let mut t_used = 0;

                    // Побудова рішення для однієї мурахи
                    'ant_loop: loop {
                        let mut allowed_indices = Vec::with_capacity(task.m * task.n);
                        let mut weights = Vec::with_capacity(task.m * task.n);

                        // Оптимізований пошук дозволених позицій
                        for i in 0..task.m {
                            for j in 0..task.n {
                                if x[[i, j]] == 0 && t_used + task.b_ij[[i, j]] <= task.b_total {
                                    let val = pheromone[[i, j]].powf(self.alpha) *
                                        heuristic[[i, j]].powf(self.beta);
                                    if val > 0.0 {
                                        allowed_indices.push((i, j));
                                        weights.push(val);
                                    }
                                }
                            }
                        }

                        if allowed_indices.is_empty() {
                            break 'ant_loop;
                        }

                        // Вибір наступної позиції
                        if let Ok(dist) = WeightedIndex::new(&weights) {
                            let choice = dist.sample(&mut local_rng);
                            let (i, j) = allowed_indices[choice];
                            x[[i, j]] = 1;
                            t_used += task.b_ij[[i, j]];
                        } else {
                            break 'ant_loop;
                        }
                    }

                    // Обчислення вартості рішення
                    let f = Zip::from(&x)
                        .and(&task.c)
                        .and(&task.omega)
                        .fold(0.0, |acc, &x_val, &c_val, &w_val| {
                            if x_val == 1 {
                                acc + ((1.0 - w_val) * c_val as f64)
                            } else {
                                acc
                            }
                        });

                    (x, f)
                })
                .collect();

            // Оновлення найкращого рішення
            for (x, f) in &ant_solutions {
                if *f > f_best {
                    f_best = *f;
                    x_best.assign(x);
                }
            }

            // Оновлення феромонів
            pheromone.mapv_inplace(|p| p * (1.0 - self.rho));

            for (x, f) in ant_solutions {
                Zip::from(&mut pheromone)
                    .and(&x)
                    .for_each(|p, &x_val| {
                        if x_val == 1 {
                            *p += f / q;
                        }
                    });
            }
        }

        Ok((x_best.to_pyarray(py).to_owned(), f_best))
    }
}

#[pyclass]
struct ProbabilisticAssignmentSolver {
    kmax: usize,
}

#[pymethods]
impl ProbabilisticAssignmentSolver {
    #[new]
    #[pyo3(signature = (kmax = 100))]
    fn new(kmax: usize) -> Self {
        ProbabilisticAssignmentSolver { kmax }
    }

    pub fn solve<'py>(&self, py: Python<'py>, task: &'py Task) -> PyResult<(Bound<'py, PyArray<i64, Ix2>>, f64)> {
        let v = Array2::from_shape_fn((task.m, task.n), |(i, j)| {
            if task.b_ij[[i, j]] != 0 {
                task.c[[i, j]] as f64 * (1.0 - task.omega[[i, j]]) / task.b_ij[[i, j]] as f64
            } else {
                0.0
            }
        });

        let mut f_best = 0.0;
        let mut x_best = Array2::<i64>::zeros((task.m, task.n));

        // Паралельна генерація рішень
        let solutions: Vec<_> = (0..self.kmax)
            .into_par_iter()
            .map(|_| {
                let mut local_rng = rng();
                let mut x = Array2::<i64>::zeros((task.m, task.n));
                let mut t_used = 0;

                'solution_loop: loop {
                    let mut allowed_indices = Vec::with_capacity(task.m * task.n);
                    let mut weights = Vec::with_capacity(task.m * task.n);

                    for i in 0..task.m {
                        for j in 0..task.n {
                            if x[[i, j]] == 0 && t_used + task.b_ij[[i, j]] <= task.b_total {
                                let weight = v[[i, j]];
                                if weight > 0.0 {
                                    allowed_indices.push((i, j));
                                    weights.push(weight);
                                }
                            }
                        }
                    }

                    if allowed_indices.is_empty() {
                        break 'solution_loop;
                    }

                    if let Ok(dist) = WeightedIndex::new(&weights) {
                        let choice = dist.sample(&mut local_rng);
                        let (i, j) = allowed_indices[choice];
                        x[[i, j]] = 1;
                        t_used += task.b_ij[[i, j]];
                    } else {
                        break 'solution_loop;
                    }
                }

                let f = Zip::from(&x)
                    .and(&task.c)
                    .and(&task.omega)
                    .fold(0.0, |acc, &x_val, &c_val, &w_val| {
                        if x_val == 1 {
                            acc + ((1.0 - w_val) * c_val as f64)
                        } else {
                            acc
                        }
                    });

                (x, f)
            })
            .collect();

        // Знаходимо найкраще рішення
        for (x, f) in solutions {
            if f > f_best {
                f_best = f;
                x_best.assign(&x);
            }
        }

        Ok((x_best.to_pyarray(py).to_owned(), f_best))
    }
}

#[pymodule]
fn assignment_solver(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Task>()?;
    m.add_class::<AntColonyAssignmentSolver>()?;
    m.add_class::<ProbabilisticAssignmentSolver>()?;
    Ok(())
}
