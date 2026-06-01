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

/// Будує один допустимий розв'язок — пакети сервісів для провайдерів. На кожному
/// кроці формує множину дозволених пар (i, j): сервіс ще не включений у пакет
/// провайдера, вистачає ресурсу IT-компанії (β_ij ≤ залишок T) **і** `admissible(i, j)`
/// істинне (обмеження (4) — відносна цінність). Обирає одну пару з ймовірністю
/// ∝ `score[i,j]`. Спільна процедура для всіх трьох алгоритмів; при s = 0
/// `admissible` завжди true і поведінка така ж, як без обмеження (4).
pub fn construct_solution_with<F>(
    b_ij: &Array2<i64>,
    b_total: i64,
    score: &Array2<f64>,
    admissible: F,
) -> Array2<i64>
where
    F: Fn(usize, usize) -> bool,
{
    let (m, n) = (b_ij.shape()[0], b_ij.shape()[1]);
    let mut rng = rand::rng();
    let mut x = Array2::<i64>::zeros((m, n));
    let mut t_used: i64 = 0;

    loop {
        let mut allowed_indices = Vec::with_capacity(m * n);
        let mut weights = Vec::with_capacity(m * n);

        for i in 0..m {
            for j in 0..n {
                if x[[i, j]] == 0
                    && t_used + b_ij[[i, j]] <= b_total
                    && admissible(i, j)
                {
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

/// Зважена цільова функція IT-компанії: ΣΣ (1 − r_ij) · value_ij · v_ij.
///
/// Використовується для доходу IT-компанії F_IT (value = d_ij): знижка r_ij
/// зменшує ціну, яку провайдер сплачує IT-компанії, тож множник (1 − r) тут
/// доречний. Для доходу провайдерів F_prov використовуйте `provider_objective`
/// (сирий p_ij без знижки) — див. пояснення там.
pub fn weighted_objective(v: &Array2<i64>, value: &Array2<i64>, r: &Array2<f64>) -> f64 {
    Zip::from(v)
        .and(value)
        .and(r)
        .fold(0.0, |acc, &v_val, &val, &r_val| {
            if v_val == 1 {
                acc + (1.0 - r_val) * val as f64
            } else {
                acc
            }
        })
}

/// Дохід провайдерів — сума СИРИХ p_ij без множника знижки: F_prov = ΣΣ p_ij · v_ij.
///
/// p_ij — дохід провайдера від його КІНЦЕВИХ КЛІЄНТІВ за перепродаж сервісу S_i.
/// Знижка r_ij — це поступка IT-компанії на ціну сервісу; вона впливає на те,
/// скільки провайдер ПЛАТИТЬ IT-компанії ((1 − r)·d), а не на те, скільки він
/// ЗАРОБЛЯЄ на клієнтах (p). Це дві різні транзакції в ланцюзі цінності, тож
/// знижка IT-компанії не зменшує клієнтський дохід провайдера. Уточнення
/// формули (2) статті (там Σ(1−r)·p·v) — задокументовано в docs/combined-method.md.
pub fn provider_objective(v: &Array2<i64>, p: &Array2<i64>) -> f64 {
    Zip::from(v).and(p).fold(0.0, |acc, &v_val, &p_val| {
        if v_val == 1 {
            acc + p_val as f64
        } else {
            acc
        }
    })
}

/// Обмеження (4) — відносна цінність сервісу для провайдера. Єдине джерело
/// істини для всіх трьох алгоритмів (ймовірнісно-жадібного, мурашиних колоній і
/// комбінованого):
///
///     s_ij · (1 − r_ij) · d_ij ≤ p_ij
///
/// «дохід провайдера p має бути щонайменше у s разів більший за те, що він
/// заплатив IT-компанії, (1−r)·d». s = 0 → завжди допустимо. Множникова форма
/// коректно обробляє d = 0 (безкоштовний сервіс): 0 ≤ p — істина.
pub fn is_admissible(s: f64, r: f64, d: i64, p: i64) -> bool {
    s * (1.0 - r) * d as f64 <= p as f64
}
