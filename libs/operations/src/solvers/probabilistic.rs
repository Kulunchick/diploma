// Ймовірнісно-жадібний алгоритм розв'язання підзадачі А (для IT-компанії)
// у задачі формування пакетів сервісів для провайдерів інфокомунікацій.
//
// Підзадача А (розділ 5.1 статті):
//   критерій  — максимізація сумарного доходу IT-компанії від наданих сервісів:
//                   F = Σ Σ (1 − r_ij) · d_ij · v_ij  → max
//   обмеження — на ресурс IT-компанії: Σ Σ β_ij · v_ij ≤ T
//
// Алгоритм поєднує жадібний (пріоритетність призначень з високою ефективністю
// використання ресурсу θ_ij = d_ij(1 − r_ij) / β_ij) та ймовірнісний підходи
// (випадковий вибір пари з ймовірністю, пропорційною θ_ij), що дозволяє
// уникати локальних екстремумів. Алгоритм запускається K_max разів, серед
// усіх отриманих розв'язків обирається найкращий.

use ndarray::Array2;
use numpy::{PyArray, Ix2, ToPyArray};
use pyo3::{prelude::*, types::PyDict};
use rayon::prelude::*;

use crate::combined_task::CombinedTask;
use crate::common::{construct_solution_with, heuristic, objective};

#[pyclass]
pub struct ProbabilisticAssignmentSolver {
    /// Кількість випадкових побудов розв'язку (ітерацій алгоритму).
    kmax: usize,
    /// Опціональний callback, що викликається після кожної ітерації
    /// у послідовному режимі (для трансляції прогресу клієнту).
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

    /// Розв'язує підзадачу А — формує пакет сервісів для всіх провайдерів,
    /// максимізуючи сумарний дохід IT-компанії з урахуванням знижок.
    ///
    /// Повертає (v, F):
    ///   v — бінарну матрицю v_ij включення сервісу S_i у пакет провайдера P_j;
    ///   F — досягнуте значення цільової функції.
    pub fn solve<'py>(
        &self,
        py: Python<'py>,
        task: &'py CombinedTask,
    ) -> PyResult<(Bound<'py, PyArray<i64, Ix2>>, f64)> {
        // Цінність одиниці ресурсу θ_ij для кожної пари «сервіс–провайдер»
        // обчислюється один раз — у ймовірнісно-жадібному алгоритмі вона
        // не змінюється від ітерації до ітерації. r = планова знижка (omega_max).
        let score = heuristic(&task.c, &task.b_ij, &task.omega_max);
        // Обмеження (4): недопустимі пари (s·(1−r)·d > p) виключаються з вибору на
        // кожному кроці. При s = 0 допустимі всі — поведінка як до введення (4).
        let admissible = |i: usize, j: usize| task.admissible(i, j, task.omega_max[[i, j]]);

        let mut f_best = 0.0_f64;
        let mut x_best = Array2::<i64>::zeros((task.m, task.n));

        if self.iteration_callback.is_some() {
            // Послідовний режим: викликаємо callback з поточним рекордом
            // після кожної ітерації, щоб клієнт міг відображати прогрес.
            for k in 0..self.kmax {
                let x = construct_solution_with(&task.b_ij, task.b_total, &score, admissible);
                let f = objective(&x, &task.c, &task.omega_max);

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
            // Паралельний режим: побудови розв'язків незалежні між собою,
            // тому виконуємо їх паралельно для максимальної продуктивності.
            let solutions: Vec<(Array2<i64>, f64)> = (0..self.kmax)
                .into_par_iter()
                .map(|_| {
                    let x = construct_solution_with(&task.b_ij, task.b_total, &score, admissible);
                    let f = objective(&x, &task.c, &task.omega_max);
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
