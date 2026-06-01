// Підзадача А (IT-компанія) у контексті комбінованого методу.
//
// Той самий ймовірнісно-жадібний підхід, що й `ProbabilisticAssignmentSolver`,
// але працює на `CombinedTask` і застосовує обмеження (4) (відносна цінність
// сервісу для провайдера) при відборі допустимих пар, із фіксованими знижками
// на рівні верхньої межі r_max. Винесено окремою вільною функцією, щоб не
// змінювати публічний клас, який обслуговує звичайні двоалгоритмні формування.

use ndarray::Array2;

use crate::combined_task::CombinedTask;
use crate::common::{construct_solution_with, heuristic, weighted_objective};

/// Розв'язує підзадачу А: максимізує дохід IT-компанії
///     F_IT = ΣΣ (1 − r_max_ij) · d_ij · v_ij
/// за обмеженням на ресурс і обмеженням (4) при r = r_max.
///
/// Повертає (v, F_IT) — найкращий із `kmax` випадкових побудов.
pub fn solve_subtask_a(task: &CombinedTask, kmax: usize) -> (Array2<i64>, f64) {
    // θ_ij = d_ij·(1 − r_max_ij) / β_ij — цінність одиниці ресурсу для IT-компанії.
    let score = heuristic(&task.c, &task.b_ij, &task.omega_max);

    let mut v_best = Array2::<i64>::zeros((task.m, task.n));
    let mut f_best = 0.0_f64;

    for _ in 0..kmax {
        let v = construct_solution_with(&task.b_ij, task.b_total, &score, |i, j| {
            task.admissible(i, j, task.omega_max[[i, j]])
        });
        let f = weighted_objective(&v, &task.c, &task.omega_max);
        if f > f_best {
            f_best = f;
            v_best.assign(&v);
        }
    }

    (v_best, f_best)
}
