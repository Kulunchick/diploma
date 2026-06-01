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
use combined_task::CombinedTask;
use solvers::ant_colony::AntColonyAssignmentSolver;
use solvers::combined::CombinedSolver;
use solvers::probabilistic::ProbabilisticAssignmentSolver;

#[pymodule]
fn assignment_solver(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<AntColonyAssignmentSolver>()?;
    m.add_class::<ProbabilisticAssignmentSolver>()?;
    m.add_class::<CombinedTask>()?;
    m.add_class::<CombinedSolver>()?;
    Ok(())
}
