// Алгоритм мурашиних колоній (АМК) розв'язання підзадачі А
// (для IT-компанії) у задачі формування пакетів сервісів для провайдерів
// інфокомунікацій.
//
// Підзадача А:
//   критерій  — максимізація сумарного доходу IT-компанії:
//                   F = Σ Σ (1 − r_ij) · d_ij · v_ij → max
//   обмеження — на ресурс IT-компанії: Σ Σ β_ij · v_ij ≤ T
//
// На відміну від ймовірнісно-жадібного алгоритму, де цінність пар
// «сервіс S_i — провайдер P_j» статична, в АМК кожна пара має ще й рівень
// феромону τ_ij, який змінюється у часі. На k-й ітерації L мурашок незалежно
// будують свої пакети сервісів, обираючи на кожному кроці допустиму пару (i, j)
// з ймовірністю:
//
//     p_ij ∝ τ_ij^α · θ_ij^β,
//
// де θ_ij = d_ij(1 − r_ij) / β_ij — цінність одиниці ресурсу,
// α — відносна важливість феромонного сліду, β — відносна привабливість пари.
//
// Після завершення ітерації виконується випаровування феромонів
//   τ_ij := (1 − ρ) · τ_ij
// та підсилення:
//   τ_ij := τ_ij + F_l / Q  для всіх пар, включених у розв'язок l-ї мурашки,
// де Q — нормуючий коефіцієнт, що оцінюється як T · d_max / β̄.

use ndarray::{Array2, Zip};
use numpy::{PyArray, Ix2, ToPyArray};
use pyo3::{prelude::*, types::PyDict};
use rayon::prelude::*;

use crate::combined_task::CombinedTask;
use crate::common::{
    construct_solution_with, heuristic, objective, provider_objective, weighted_objective,
};

#[pyclass]
pub struct AntColonyAssignmentSolver {
    /// L — кількість мурашок у колонії на кожній ітерації.
    num_ants: usize,
    /// K_max — кількість ітерацій алгоритму.
    kmax: usize,
    /// α — відносна важливість феромонного сліду при виборі пари.
    alpha: f64,
    /// β — відносна важливість «привабливості» пари (цінності θ_ij).
    beta: f64,
    /// ρ ∈ [0, 1] — коефіцієнт випаровування феромонів.
    rho: f64,
    /// τ_0 — початковий рівень феромону на парах «сервіс–провайдер».
    initial_pheromone: f64,
    /// Опціональний callback для трансляції прогресу клієнту після ітерації.
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

    /// Розв'язує підзадачу А — формує пакети сервісів для всіх провайдерів,
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
        // θ_ij — цінність одиниці ресурсу для пари «сервіс S_i — провайдер P_j».
        // r = планова знижка (omega_max).
        let heuristic_value = heuristic(&task.c, &task.b_ij, &task.omega_max);
        // Обмеження (4): недопустимі пари виключаються з вибору кожною мурашкою.
        // При s = 0 допустимі всі — поведінка як до введення (4). Феромон
        // підсилюється лише на парах, що увійшли в розв'язок (тобто допустимих).
        let admissible = |i: usize, j: usize| task.admissible(i, j, task.omega_max[[i, j]]);

        // Q — коефіцієнт підсилення феромонів: T · d_max / β̄, де
        //   T     — загальний ресурс IT-компанії,
        //   β̄    — середній обсяг ресурсу для надання сервісу,
        //   d_max — максимальна преференційна ціна.
        let q = {
            let avg_b = task.b_ij.sum() as f64 / (task.m * task.n) as f64;
            task.b_total as f64 / avg_b
                * task.c.iter().fold(0_i64, |m, &x| m.max(x)) as f64
        };

        // Початкові рівні феромонів τ_ij := τ_0.
        let mut pheromone =
            Array2::<f64>::from_elem((task.m, task.n), self.initial_pheromone);
        let mut f_best = 0.0_f64;
        let mut x_best = Array2::<i64>::zeros((task.m, task.n));

        for k in 0..self.kmax {
            // На початку ітерації одноразово обчислюємо вагу для вибору пар:
            //   score_ij = τ_ij^α · θ_ij^β.
            // Усі L мурашок цієї ітерації використовують один і той самий score.
            let score = Zip::from(&pheromone)
                .and(&heuristic_value)
                .map_collect(|&p, &h| p.powf(self.alpha) * h.powf(self.beta));

            // L мурашок незалежно будують свої пакети сервісів — паралельно.
            let ant_solutions: Vec<(Array2<i64>, f64)> = (0..self.num_ants)
                .into_par_iter()
                .map(|_| {
                    let x = construct_solution_with(&task.b_ij, task.b_total, &score, admissible);
                    let f = objective(&x, &task.c, &task.omega_max);
                    (x, f)
                })
                .collect();

            // Оновлюємо рекордний розв'язок (найвигідніший пакет сервісів,
            // знайдений з початку роботи алгоритму).
            for (x, f) in &ant_solutions {
                if *f > f_best {
                    f_best = *f;
                    x_best.assign(x);
                }
            }

            // Випаровування феромонів: τ_ij := (1 − ρ) · τ_ij.
            pheromone.mapv_inplace(|p| p * (1.0 - self.rho));

            // Підсилення феромонів за розв'язками всіх мурашок:
            // на пари, включені у розв'язок l-ї мурашки, додається F_l / Q.
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

// ---------------------------------------------------------------------------
// Чистий Rust-варіант АМК для Стадії 1 комбінованого методу (без Python-хендла).
// Узагальнений на обидві підзадачі: A (дохід IT-компанії, θ = d(1−r)/β,
// F_IT = ΣΣ(1−r)d·v) і Б (дохід провайдерів, θ = p/β, F_prov = ΣΣ p·v).
// Механіка феромонів та сама, що й у standalone-розв'язувачі (score = τ^α·θ^β,
// випаровування ρ, підсилення F_l/Q); різняться лише евристика, цільова функція
// та нормуючий коефіцієнт Q. Внутрішнє використання — НЕ окремий публічний метод.
// ---------------------------------------------------------------------------

/// Нормуючий коефіцієнт підсилення феромонів Q = T · value_max / β̄
/// (value_max = d_max для підзадачі А, p_max для підзадачі Б).
fn ant_q(task: &CombinedTask, value_max: f64) -> f64 {
    let avg_b = task.b_ij.sum() as f64 / (task.m * task.n) as f64;
    task.b_total as f64 / avg_b * value_max
}

/// Ядро АМК: повертає (v_best, f_best) для заданих евристики θ, цільової
/// функції та Q. Допустимість пар — за обмеженням (4) при r = r_max.
fn ant_colony_optimize<O>(
    task: &CombinedTask,
    heuristic_value: &Array2<f64>,
    objective_fn: O,
    q: f64,
    num_ants: usize,
    kmax: usize,
    alpha: f64,
    beta: f64,
    rho: f64,
    tau0: f64,
) -> (Array2<i64>, f64)
where
    O: Fn(&Array2<i64>) -> f64 + Sync,
{
    let admissible = |i: usize, j: usize| task.admissible(i, j, task.omega_max[[i, j]]);
    let mut pheromone = Array2::<f64>::from_elem((task.m, task.n), tau0);
    let mut f_best = 0.0_f64;
    let mut x_best = Array2::<i64>::zeros((task.m, task.n));

    for _ in 0..kmax {
        let score = Zip::from(&pheromone)
            .and(heuristic_value)
            .map_collect(|&p, &h| p.powf(alpha) * h.powf(beta));

        let ant_solutions: Vec<(Array2<i64>, f64)> = (0..num_ants)
            .into_par_iter()
            .map(|_| {
                let x = construct_solution_with(&task.b_ij, task.b_total, &score, admissible);
                let f = objective_fn(&x);
                (x, f)
            })
            .collect();

        for (x, f) in &ant_solutions {
            if *f > f_best {
                f_best = *f;
                x_best.assign(x);
            }
        }

        pheromone.mapv_inplace(|p| p * (1.0 - rho));
        for (x, f) in &ant_solutions {
            Zip::from(&mut pheromone).and(x).for_each(|p, &x_val| {
                if x_val == 1 {
                    *p += f / q;
                }
            });
        }
    }

    (x_best, f_best)
}

/// АМК для підзадачі А (дохід IT-компанії). θ = d(1−r)/β, F_IT = ΣΣ(1−r)d·v.
pub(crate) fn ant_colony_subtask_a(
    task: &CombinedTask,
    num_ants: usize,
    kmax: usize,
    alpha: f64,
    beta: f64,
    rho: f64,
    tau0: f64,
) -> (Array2<i64>, f64) {
    let h = heuristic(&task.c, &task.b_ij, &task.omega_max);
    let d_max = task.c.iter().fold(0_i64, |m, &x| m.max(x)) as f64;
    let q = ant_q(task, d_max);
    ant_colony_optimize(
        task,
        &h,
        |v| weighted_objective(v, &task.c, &task.omega_max),
        q,
        num_ants,
        kmax,
        alpha,
        beta,
        rho,
        tau0,
    )
}

/// АМК для підзадачі Б (дохід провайдерів). θ = p/β, F_prov = ΣΣ p·v.
/// (Та сама модель та обмеження (4) при r_max — лише інша цільова функція.)
pub(crate) fn ant_colony_subtask_b(
    task: &CombinedTask,
    num_ants: usize,
    kmax: usize,
    alpha: f64,
    beta: f64,
    rho: f64,
    tau0: f64,
) -> (Array2<i64>, f64) {
    let h = crate::solvers::subtask_b::provider_heuristic(task);
    let p_max = task.p_ij.iter().cloned().fold(0.0_f64, f64::max);
    let q = ant_q(task, p_max);
    ant_colony_optimize(
        task,
        &h,
        |v| provider_objective(v, &task.p_ij),
        q,
        num_ants,
        kmax,
        alpha,
        beta,
        rho,
        tau0,
    )
}
