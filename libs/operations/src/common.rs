// Спільні функції для алгоритмів формування пакетів сервісів:
//   - heuristic        — обчислення цінності одиниці ресурсу θ_ij для пар «сервіс–провайдер»;
//   - objective        — обчислення сумарного доходу IT-компанії від наданих сервісів (цільова функція (1));
//   - construct_solution — побудова одного допустимого розв'язку шляхом ймовірнісного вибору
//                         дозволених пар «сервіс S_i — провайдер P_j».

use ndarray::{Array2, Zip};
use rand::{distr::weighted::WeightedIndex, prelude::*};

/// Цінність одиниці ресурсу для пари «сервіс S_i — провайдер P_j»:
///
///     θ_ij = d_ij · (1 − r_ij) / β_ij
///
/// де d_ij — преференційна ціна, r_ij — знижка, β_ij — обсяг ресурсу
/// IT-компанії для надання сервісу. Якщо β_ij = 0, повертається 0
/// (пара недоступна для вибору).
pub fn heuristic(c: &Array2<i64>, b_ij: &Array2<i64>, omega: &Array2<f64>) -> Array2<f64> {
    Array2::from_shape_fn(c.raw_dim(), |(i, j)| {
        if b_ij[[i, j]] != 0 {
            (c[[i, j]] as f64 * (1.0 - omega[[i, j]])) / b_ij[[i, j]] as f64
        } else {
            0.0
        }
    })
}

/// Цільова функція IT-компанії — сумарний дохід від наданих провайдерам сервісів
/// з урахуванням знижок (формула (1) у статті):
///
///     F = Σ_i Σ_j (1 − r_ij) · d_ij · v_ij
///
/// де v_ij ∈ {0, 1} — булева змінна включення сервісу S_i у пакет провайдера P_j.
pub fn objective(x: &Array2<i64>, c: &Array2<i64>, omega: &Array2<f64>) -> f64 {
    Zip::from(x)
        .and(c)
        .and(omega)
        .fold(0.0, |acc, &x_val, &c_val, &w_val| {
            if x_val == 1 {
                acc + (1.0 - w_val) * c_val as f64
            } else {
                acc
            }
        })
}

/// Будує один допустимий розв'язок — пакети сервісів для провайдерів,
/// що відповідає обмеженню на ресурс IT-компанії.
///
/// На кожному кроці:
///   - формує множину дозволених пар (i, j): сервіс S_i ще не включений у
///     пакет провайдера P_j, і залишкового ресурсу IT-компанії достатньо
///     для його надання (β_ij ≤ T_used_max);
///   - випадково обирає одну пару з ймовірністю, пропорційною її цінності
///     `score[i,j]` (для ймовірнісного алгоритму — θ_ij, для АМК —
///     τ_ij^α · θ_ij^β).
///
/// Повертає бінарну матрицю v ∈ {0, 1}^(m×n) — структуру сформованих пакетів.
pub fn construct_solution(
    b_ij: &Array2<i64>,
    b_total: i64,
    score: &Array2<f64>,
) -> Array2<i64> {
    let (m, n) = (b_ij.shape()[0], b_ij.shape()[1]);
    let mut rng = rand::rng();
    let mut x = Array2::<i64>::zeros((m, n));
    let mut t_used: i64 = 0;

    loop {
        let mut allowed_indices = Vec::with_capacity(m * n);
        let mut weights = Vec::with_capacity(m * n);

        for i in 0..m {
            for j in 0..n {
                // Дозволені пари: сервіс ще не включений до пакету
                // цього провайдера і вистачає ресурсу IT-компанії.
                if x[[i, j]] == 0 && t_used + b_ij[[i, j]] <= b_total {
                    let w = score[[i, j]];
                    if w > 0.0 {
                        allowed_indices.push((i, j));
                        weights.push(w);
                    }
                }
            }
        }

        if allowed_indices.is_empty() {
            break;
        }

        if let Ok(dist) = WeightedIndex::new(&weights) {
            let choice = dist.sample(&mut rng);
            let (i, j) = allowed_indices[choice];
            x[[i, j]] = 1;
            t_used += b_ij[[i, j]];
        } else {
            break;
        }
    }

    x
}
