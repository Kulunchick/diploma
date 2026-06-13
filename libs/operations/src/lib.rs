// Rust-бібліотека `assignment_solver` для задачі формування пакетів сервісів
// для провайдерів інфокомунікацій.
//
// Експортує в Python:
//   - CombinedTask                      — єдина модель задачі (несе p_ij, s_ij,
//                                         r_max), яку споживають усі три алгоритми;
//   - ProbabilisticAssignmentSolver     — ймовірнісно-жадібний алгоритм;
//   - AntColonyAssignmentSolver         — алгоритм мурашиних колоній;
//   - CombinedSolver                    — комбінований метод (розділи 4–5 статті).
//
// Усі три алгоритми застосовують обмеження (4) (відносна цінність s_ij) через
// спільний предикат `common::is_admissible`.

mod combined_task;
mod common;
mod solvers;

use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
use combined_task::CombinedTask;
use solvers::ant_colony::{ant_colony_subtask_b, AntColonyAssignmentSolver};
use solvers::combined::CombinedSolver;
use solvers::probabilistic::ProbabilisticAssignmentSolver;
use solvers::subtask_b::solve_subtask_b;

/// Допоміжна функція для перевірки нового АМК-розв'язувача підзадачі Б ізольовано
/// від комбінованого методу: повертає (F_prov greedy, F_prov АМК, використаний
/// ресурс АМК, T, чи всі включені пари АМК допустимі при r_max). Не використовується
/// застосунком — лише для перевірки коректності/якості підзадачі Б.
#[pyfunction]
fn verify_subtask_b(task: &CombinedTask, kmax: usize) -> (f64, f64, i64, i64, bool) {
    let (_vg, f_greedy) = solve_subtask_b(task, kmax);
    let (v_ant, f_ant) = ant_colony_subtask_b(task, 20, kmax, 1.0, 2.0, 0.1, 1.0);
    let resource = task.resource_used(&v_ant);
    let mut all_admissible = true;
    for i in 0..task.m {
        for j in 0..task.n {
            if v_ant[[i, j]] == 1 && !task.admissible(i, j, task.omega_max[[i, j]]) {
                all_admissible = false;
            }
        }
    }
    (f_greedy, f_ant, resource, task.b_total, all_admissible)
}

#[pymodule]
fn assignment_solver(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<AntColonyAssignmentSolver>()?;
    m.add_class::<ProbabilisticAssignmentSolver>()?;
    m.add_class::<CombinedTask>()?;
    m.add_class::<CombinedSolver>()?;
    m.add_function(wrap_pyfunction!(verify_subtask_b, m)?)?;
    Ok(())
}
