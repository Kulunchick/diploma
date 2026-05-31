// Rust-бібліотека `assignment_solver` для задачі формування пакетів сервісів
// для провайдерів інфокомунікацій.
//
// Експортує в Python:
//   - Task                              — модель задачі (підзадача А для IT-компанії);
//   - ProbabilisticAssignmentSolver     — ймовірнісно-жадібний алгоритм;
//   - AntColonyAssignmentSolver         — алгоритм мурашиних колоній.
//
// Комбінований метод формування пакетів сервісів (зі статті) у цій збірці
// не реалізовано — він буде доданий в наступних версіях інформаційної системи.

mod common;
mod solvers;
mod task;

use pyo3::prelude::*;
use solvers::ant_colony::AntColonyAssignmentSolver;
use solvers::probabilistic::ProbabilisticAssignmentSolver;
use task::Task;

#[pymodule]
fn assignment_solver(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Task>()?;
    m.add_class::<AntColonyAssignmentSolver>()?;
    m.add_class::<ProbabilisticAssignmentSolver>()?;
    Ok(())
}
