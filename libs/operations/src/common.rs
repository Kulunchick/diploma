use ndarray::{Array2, Zip};
use rand::{distr::weighted::WeightedIndex, prelude::*};

/// c_ij * (1 - omega_ij) / b_ij  (0 where b_ij == 0)
pub fn heuristic(c: &Array2<i64>, b_ij: &Array2<i64>, omega: &Array2<f64>) -> Array2<f64> {
    Array2::from_shape_fn(c.raw_dim(), |(i, j)| {
        if b_ij[[i, j]] != 0 {
            (c[[i, j]] as f64 * (1.0 - omega[[i, j]])) / b_ij[[i, j]] as f64
        } else {
            0.0
        }
    })
}

/// sum_ij( x_ij * c_ij * (1 - omega_ij) )
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

/// Builds one feasible solution from pre-computed per-cell scores.
/// Repeatedly samples via WeightedIndex, respecting the budget.
/// Returns the binary assignment matrix x.
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
