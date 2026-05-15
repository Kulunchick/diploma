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
