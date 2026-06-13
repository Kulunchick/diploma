// Підзадача Б (провайдери) комбінованого методу — розділ 5.2 статті.
//
// Ймовірнісно-жадібний алгоритм, що максимізує сумарний дохід провайдерів
//     F_prov = ΣΣ p_ij · v_ij
// за спільним обмеженням на ресурс IT-компанії T та обмеженням (4). p_ij —
// дохід провайдера від кінцевих клієнтів; він НЕ залежить від знижки r
// IT-компанії (уточнення формули (2), див. docs/combined-method.md).
//
// На відміну від підзадачі А, евристика тут — дохід провайдера на одиницю
// ресурсу θ_ij = p_ij / β_ij. Пакети будуються по провайдерах
// (round-robin): на кожному кроці для поточного провайдера формується множина
// допустимих пар (вистачає спільного ресурсу AND виконується (4) при r_max) і
// одна обирається з імовірністю ∝ θ_ij. Знижки фіксовані на r_max.

use ndarray::Array2;
use rand::{distr::weighted::WeightedIndex, prelude::*};

use crate::combined_task::CombinedTask;
use crate::common::provider_objective;

/// θ_ij = p_ij / β_ij (0, якщо β_ij = 0). Дохід провайдера на одиницю ресурсу;
/// знижка IT-компанії у чисельник не входить (p — клієнтський дохід провайдера).
/// pub(crate): перевикористовується алгоритмом мурашиних колоній для підзадачі Б.
pub(crate) fn provider_heuristic(task: &CombinedTask) -> Array2<f64> {
    Array2::from_shape_fn((task.m, task.n), |(i, j)| {
        let b = task.b_ij[[i, j]];
        if b != 0 {
            task.p_ij[[i, j]] / b as f64
        } else {
            0.0
        }
    })
}

/// Будує один допустимий розв'язок, обходячи провайдерів по колу. Зупиняється,
/// коли жодному провайдеру не можна додати жодної допустимої пари.
fn construct_provider_solution(task: &CombinedTask, score: &Array2<f64>) -> Array2<i64> {
    let mut rng = rand::rng();
    let mut v = Array2::<i64>::zeros((task.m, task.n));
    let mut t_used: i64 = 0;

    loop {
        let mut progressed = false;

        for j in 0..task.n {
            // Допустимі для провайдера j пари «одиниця–провайдер».
            let mut allowed = Vec::with_capacity(task.m);
            let mut weights = Vec::with_capacity(task.m);
            for i in 0..task.m {
                if v[[i, j]] == 0
                    && t_used + task.b_ij[[i, j]] <= task.b_total
                    && task.admissible(i, j, task.omega_max[[i, j]])
                {
                    let w = score[[i, j]];
                    if w > 0.0 {
                        allowed.push(i);
                        weights.push(w);
                    }
                }
            }
            if allowed.is_empty() {
                continue;
            }
            if let Ok(dist) = WeightedIndex::new(&weights) {
                let i = allowed[dist.sample(&mut rng)];
                v[[i, j]] = 1;
                t_used += task.b_ij[[i, j]];
                progressed = true;
            }
        }

        if !progressed {
            break;
        }
    }

    v
}

/// Розв'язує підзадачу Б: повертає (v, F_prov) — найкращий із `kmax` побудов.
pub fn solve_subtask_b(task: &CombinedTask, kmax: usize) -> (Array2<i64>, f64) {
    let score = provider_heuristic(task);

    let mut v_best = Array2::<i64>::zeros((task.m, task.n));
    let mut f_best = 0.0_f64;

    for _ in 0..kmax {
        let v = construct_provider_solution(task, &score);
        let f = provider_objective(&v, &task.p_ij);
        if f > f_best {
            f_best = f;
            v_best.assign(&v);
        }
    }

    (v_best, f_best)
}
