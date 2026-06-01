// Комбінований метод формування пакетів сервісів — розділи 4–5 статті.
//
// Чотири стадії інтегрують однокритеріальні підзадачі IT-компанії (А) і
// провайдерів (Б), знаходять їх спільну частину і покращують її евристикою
// поступок із системою знижок. Результат — взаємовигідний пакет: не
// оптимальний для жодної сторони окремо, але максимальний за сумарною вигодою
// F_IT + F_prov.
//
// Стадія 1: розв'язати А (v_a, F_IT) і Б (v_b, F_prov) при r = r_max.
// Стадія 2: крос-оцінити — порахувати другий критерій для кожного розв'язку.
// Стадія 3: локальний пошук (hill climbing, best-improvement, Парето-критерій)
//           над парою (v, r), де знижки r стають змінними рішення.
// Стадія 4: обрати з двох покращених кандидатів той, що має більшу сумарну
//           вигоду F_IT + F_prov.

use ndarray::Array2;
use numpy::ToPyArray;
use pyo3::{prelude::*, types::PyDict};

use crate::combined_task::CombinedTask;
use crate::common::{provider_objective, weighted_objective};
use crate::solvers::subtask_a::solve_subtask_a;
use crate::solvers::subtask_b::solve_subtask_b;

/// Епсилон прийняття ходу. Guard проти float-cycling: знижки змінюються кроком
/// discount_step, тож суто арифметичні «покращення» близько нуля
/// (≤ 1e-9) ігноруються, щоб r не дрижала через округлення. Це НЕ алгоритмічна
/// межа якості — лише захист від нескінченних циклів на рівних значеннях.
const ACCEPT_EPS: f64 = 1e-9;

/// Верхня межа кроків hill-climb. Guard проти float-cycling — у нормі пошук
/// сходиться набагато раніше (кожен прийнятий хід строго підвищує суму вигод).
/// При досягненні логуємо попередження. Це НЕ алгоритмічне обмеження глибини.
const MAX_HILL_CLIMB_STEPS: usize = 1000;

/// Внутрішній стан кандидата комбінованого методу.
#[derive(Clone)]
struct State {
    v: Array2<i64>,
    r: Array2<f64>,
    f_it: f64,
    f_prov: f64,
}

#[pyclass]
pub struct CombinedSolver {
    kmax_subproblem: usize,
    discount_step: f64,
    local_search_restarts: usize,
    iteration_callback: Option<PyObject>,
}

#[pymethods]
impl CombinedSolver {
    #[new]
    #[pyo3(signature = (kmax_subproblem = 100, discount_step = 0.05, local_search_restarts = 0))]
    pub fn new(kmax_subproblem: usize, discount_step: f64, local_search_restarts: usize) -> Self {
        CombinedSolver {
            kmax_subproblem,
            discount_step,
            local_search_restarts,
            iteration_callback: None,
        }
    }

    pub fn set_iteration_callback(&mut self, callback: PyObject) {
        self.iteration_callback = Some(callback);
    }

    /// Запускає комбінований метод. Повертає dict:
    ///   v_final  — бінарна матриця v_ij (numpy int64, m×n);
    ///   r_final  — матриця узгоджених знижок (numpy float64, m×n; для невключених
    ///              пар повертається r_max_ij як нейтральний placeholder);
    ///   f_it     — F_IT фінального розв'язку (float);
    ///   f_prov   — F_prov фінального розв'язку (float);
    ///   source   — "subtask_a_improved" | "subtask_b_improved": який покращений
    ///              кандидат переміг на стадії 4.
    pub fn solve<'py>(&self, py: Python<'py>, task: &CombinedTask) -> PyResult<Bound<'py, PyDict>> {
        let (best, source, ticks) = self.solve_core(task);

        // current_best_value = F_IT + F_prov (графік збіжності показує сумарну
        // вигоду). Викликаємо callback послідовно — той самий патерн, що й у
        // ймовірнісному / АМК розв'язувачах.
        if let Some(ref cb) = self.iteration_callback {
            for (i, value) in ticks.iter().enumerate() {
                let data = PyDict::new(py);
                data.set_item("iteration", i + 1)?;
                data.set_item("current_best_value", *value)?;
                cb.call1(py, (data,))?;
            }
        }

        let out = PyDict::new(py);
        out.set_item("v_final", best.v.to_pyarray(py).to_owned())?;
        out.set_item("r_final", best.r.to_pyarray(py).to_owned())?;
        out.set_item("f_it", best.f_it)?;
        out.set_item("f_prov", best.f_prov)?;
        out.set_item("source", source)?;
        Ok(out)
    }
}

impl CombinedSolver {
    /// Pure-Rust четырьохстадійне ядро комбінованого методу — без Python-хендла,
    /// щоб гарячий шлях і юніт-тести не залежали від інтерпретатора. Повертає
    /// (фінальний стан, source, тіки сумарної вигоди для callback).
    fn solve_core(&self, task: &CombinedTask) -> (State, &'static str, Vec<f64>) {
        let mut ticks: Vec<f64> = Vec::new();

        // --- Стадія 1: однокритеріальні підзадачі при r = r_max ---
        let (v_a, f_it_a) = solve_subtask_a(task, self.kmax_subproblem);
        let (v_b, f_prov_b) = solve_subtask_b(task, self.kmax_subproblem);

        // --- Стадія 2: крос-оцінка обох розв'язків у двох критеріях ---
        let state_a = State {
            f_it: f_it_a,
            f_prov: provider_objective(&v_a, &task.p_ij),
            v: v_a,
            r: task.omega_max.clone(),
        };
        let state_b = State {
            f_it: weighted_objective(&v_b, &task.c, &task.omega_max),
            f_prov: f_prov_b,
            v: v_b,
            r: task.omega_max.clone(),
        };
        ticks.push(combined(&state_a));
        ticks.push(combined(&state_b));

        // --- Стадія 3: локальний пошук над кожним кандидатом ---
        let (improved_a, ticks_a) = self.improve_with_restarts(task, &state_a);
        let (improved_b, ticks_b) = self.improve_with_restarts(task, &state_b);
        ticks.extend(ticks_a);
        ticks.extend(ticks_b);

        // --- Стадія 4: обрати кандидата з більшою сумарною вигодою ---
        let (best, source) = if combined(&improved_a) >= combined(&improved_b) {
            (improved_a, "subtask_a_improved")
        } else {
            (improved_b, "subtask_b_improved")
        };

        // Графік збіжності: best-so-far. `ticks` досі містить «сирі» значення
        // сумарної вигоди з 5 НЕЗАЛЕЖНИХ прогонів (стартів А/Б + збурених
        // рестартів), конкатеновані в один вектор. Як єдина монотонна крива вони
        // дають фізично неможливі падіння (кожен рестарт стартує з гіршої точки).
        // Перетворюємо на накопичувальний максимум: крива не спадає і завершується
        // рівно на сумарній вигоді переможця. Counter ітерацій у solve() — єдиний
        // наскрізний (i+1), тож вісь X суцільна.
        let mut running = f64::NEG_INFINITY;
        for t in ticks.iter_mut() {
            running = running.max(*t);
            *t = running;
        }
        // Запобіжник: остання точка точно дорівнює збереженій сумарній вигоді.
        let final_benefit = combined(&best);
        match ticks.last_mut() {
            Some(last) => *last = final_benefit,
            None => ticks.push(final_benefit),
        }

        (best, source, ticks)
    }
}

fn combined(s: &State) -> f64 {
    s.f_it + s.f_prov
}

impl CombinedSolver {
    /// Локальний пошук зі структурного старту + опційні збурені рестарти.
    /// Повертає найкращий стан і список тіків (сумарна вигода після кожного
    /// прийнятого ходу), які `solve` потім транслює у callback.
    fn improve_with_restarts(&self, task: &CombinedTask, start: &State) -> (State, Vec<f64>) {
        let (mut best, mut ticks) = self.improve(task, start.clone());

        for seed in 0..self.local_search_restarts {
            let perturbed = perturb(task, start, seed);
            let (candidate, cand_ticks) = self.improve(task, perturbed);
            ticks.extend(cand_ticks);
            // Збурені рестарти можуть давати Парето-незрівнянні розв'язки —
            // обираємо за більшою сумарною вигодою (узгоджено зі стадією 4).
            if combined(&candidate) > combined(&best) {
                best = candidate;
            }
        }
        (best, ticks)
    }

    /// Hill climbing з best-improvement та Парето-прийняттям.
    ///
    /// Сусідство поточного стану (v, r) — об'єднання ходів:
    ///   (1) додати пару (v=0→1), якщо вистачає ресурсу і пара допустима при r;
    ///   (2) прибрати пару (v=1→0), звільнивши ресурс;
    ///   (3) знижка −step на включеній парі: r_ij ← max(0, r_ij − step).
    ///       Менша r ⇒ більший (1 − r) ⇒ зростає F_IT цієї пари (IT-компанія дає
    ///       меншу знижку — чистий приріст доходу IT). F_prov не залежить від r
    ///       (сирий p), тож лишається незмінним → хід Парето-кращий (F_IT↑,
    ///       F_prov=). Допустимість (4) лише покращується;
    ///   (4) знижка +step на включеній парі: r_ij ← min(r_max_ij, r_ij + step).
    ///       Більша r знижує F_IT пари (F_prov незмінний), АЛЕ може зробити
    ///       допустимою раніше недопустиму пару — тому має сенс лише у складеному
    ///       ході глибини 2: «підняти r на (i,j) ТА додати (k,l), що стала
    ///       допустимою» (додавання (k,l) дає +p_kl до F_prov і +(1−r)d_kl до F_IT).
    ///
    /// Прийняття (Парето): хід до (v', r') приймається лише якщо
    /// f_it' ≥ f_it AND f_prov' ≥ f_prov, хоча б один строго більший
    /// (на ACCEPT_EPS), ресурс ≤ T і всі включені пари допустимі при r'.
    /// Серед прийнятих обираємо хід з найбільшим приростом (f_it' + f_prov').
    fn improve(&self, task: &CombinedTask, start: State) -> (State, Vec<f64>) {
        let mut current = start;
        let mut ticks: Vec<f64> = Vec::new();

        for step in 0..MAX_HILL_CLIMB_STEPS {
            let neighbours = self.neighbourhood(task, &current);

            // Best-improvement: максимальний приріст сумарної вигоди серед
            // прийнятних (Парето + допустимість) сусідів.
            let mut best_gain = ACCEPT_EPS;
            let mut best_next: Option<State> = None;
            let base = combined(&current);
            for cand in neighbours {
                // Feasibility (resource ≤ T AND every included pair admissible
                // at r') is checked here, not in the neighbourhood generator,
                // because the depth-2 "+step" move raises r on a pair and may
                // push that pair below its own threshold (4).
                if !feasible(task, &cand) || !pareto_accept(&current, &cand) {
                    continue;
                }
                let gain = combined(&cand) - base;
                if gain > best_gain {
                    best_gain = gain;
                    best_next = Some(cand);
                }
            }

            match best_next {
                Some(next) => {
                    current = next;
                    ticks.push(combined(&current));
                }
                None => break, // локальний оптимум
            }

            if step + 1 == MAX_HILL_CLIMB_STEPS {
                eprintln!(
                    "[combined] hill-climb hit MAX_HILL_CLIMB_STEPS ({MAX_HILL_CLIMB_STEPS}) — \
                     float-cycling guard, stopping"
                );
            }
        }

        (current, ticks)
    }

    /// Генерує всі сусідні стани поточного (v, r). Повна енумерація — інстанси
    /// малі (одиниці × провайдери), а обрізання ризикує відсікти саме нетривіальні
    /// поступки. Складені ходи обмежені глибиною 2.
    fn neighbourhood(&self, task: &CombinedTask, s: &State) -> Vec<State> {
        let (m, n) = (task.m, task.n);
        let used = task.resource_used(&s.v);
        let mut out = Vec::new();

        for i in 0..m {
            for j in 0..n {
                if s.v[[i, j]] == 0 {
                    // (1) додати пару
                    if used + task.b_ij[[i, j]] <= task.b_total
                        && task.admissible(i, j, s.r[[i, j]])
                    {
                        let mut v = s.v.clone();
                        v[[i, j]] = 1;
                        out.push(rebuild(task, v, s.r.clone()));
                    }
                } else {
                    // (2) прибрати пару
                    let mut v = s.v.clone();
                    v[[i, j]] = 0;
                    out.push(rebuild(task, v, s.r.clone()));

                    // (3) знижка −step (менша r): піднімає обидва доходи
                    let down = (s.r[[i, j]] - self.discount_step).max(0.0);
                    if down < s.r[[i, j]] - ACCEPT_EPS {
                        let mut r = s.r.clone();
                        r[[i, j]] = down;
                        out.push(rebuild(task, s.v.clone(), r));
                    }

                    // (4) знижка +step, лише у складеному ході глибини 2:
                    // підняти r на (i,j) ТА додати (k,l), що стає допустимою.
                    let up = (s.r[[i, j]] + self.discount_step).min(task.omega_max[[i, j]]);
                    if up > s.r[[i, j]] + ACCEPT_EPS {
                        let mut r = s.r.clone();
                        r[[i, j]] = up;
                        // Підняття r на включеній парі зменшує дохід, тож сам по
                        // собі цей хід не Парето-кращий — додаємо парний add.
                        for k in 0..m {
                            for l in 0..n {
                                if s.v[[k, l]] == 0
                                    && used + task.b_ij[[k, l]] <= task.b_total
                                    && !task.admissible(k, l, s.r[[k, l]])
                                    && task.admissible(k, l, r[[k, l]])
                                {
                                    let mut v = s.v.clone();
                                    v[[k, l]] = 1;
                                    out.push(rebuild(task, v, r.clone()));
                                }
                            }
                        }
                    }
                }
            }
        }

        out
    }
}

/// Перераховує цільові функції для (v, r) і пакує у State. F_IT залежить від r
/// (множник (1−r) на ціні), F_prov — НІ (сирий Σp·v, клієнтський дохід).
fn rebuild(task: &CombinedTask, v: Array2<i64>, r: Array2<f64>) -> State {
    State {
        f_it: weighted_objective(&v, &task.c, &r),
        f_prov: provider_objective(&v, &task.p_ij),
        v,
        r,
    }
}

/// Чи допустимий стан: ресурс ≤ T і всі включені пари допустимі при поточному r.
fn feasible(task: &CombinedTask, s: &State) -> bool {
    if task.resource_used(&s.v) > task.b_total {
        return false;
    }
    for i in 0..task.m {
        for j in 0..task.n {
            if s.v[[i, j]] == 1 && !task.admissible(i, j, s.r[[i, j]]) {
                return false;
            }
        }
    }
    true
}

/// Парето-критерій прийняття: cand слабо домінує current в обох критеріях,
/// строго хоча б в одному (на ACCEPT_EPS). Допустимість (feasible) перевіряється
/// окремо у виклику improve(), бо складений «+step» хід може порушити (4).
fn pareto_accept(current: &State, cand: &State) -> bool {
    let it_ge = cand.f_it >= current.f_it - ACCEPT_EPS;
    let prov_ge = cand.f_prov >= current.f_prov - ACCEPT_EPS;
    let strict = cand.f_it > current.f_it + ACCEPT_EPS
        || cand.f_prov > current.f_prov + ACCEPT_EPS;
    it_ge && prov_ge && strict
}

/// Збурення для рестарту: випадково перемкнути ~10% пар, тоді відновити
/// допустимість за ресурсом, жадібно прибираючи включені пари з найменшою
/// цінністю θ, доки ресурс не вкладеться у T.
fn perturb(task: &CombinedTask, start: &State, seed: usize) -> State {
    use rand::{rngs::StdRng, Rng, SeedableRng};
    let mut rng = StdRng::seed_from_u64(seed as u64 + 1);
    let (m, n) = (task.m, task.n);
    let mut v = start.v.clone();

    for i in 0..m {
        for j in 0..n {
            if rng.random::<f64>() < 0.10 {
                v[[i, j]] = 1 - v[[i, j]];
            }
        }
    }

    // Відновлення допустимості за ресурсом і обмеженням (4).
    for i in 0..m {
        for j in 0..n {
            if v[[i, j]] == 1 && !task.admissible(i, j, start.r[[i, j]]) {
                v[[i, j]] = 0;
            }
        }
    }
    while task.resource_used(&v) > task.b_total {
        // Прибираємо включену пару з найменшим θ = (1−r)·d / β.
        let mut worst: Option<(usize, usize)> = None;
        let mut worst_theta = f64::INFINITY;
        for i in 0..m {
            for j in 0..n {
                if v[[i, j]] == 1 {
                    let b = task.b_ij[[i, j]];
                    let theta = if b != 0 {
                        (1.0 - start.r[[i, j]]) * task.c[[i, j]] as f64 / b as f64
                    } else {
                        f64::INFINITY
                    };
                    if theta < worst_theta {
                        worst_theta = theta;
                        worst = Some((i, j));
                    }
                }
            }
        }
        match worst {
            Some((i, j)) => v[[i, j]] = 0,
            None => break,
        }
    }

    rebuild(task, v, start.r.clone())
}

#[cfg(test)]
mod tests {
    use super::*;
    use ndarray::array;

    /// Будує крихітну задачу, де А і Б розходяться: одиниця 0 цінна для
    /// IT-компанії (висока d, низька p), одиниця 1 — для провайдера (навпаки).
    fn tiny_task() -> CombinedTask {
        CombinedTask {
            m: 2,
            n: 1,
            c: array![[100], [10]],
            b_ij: array![[5], [5]],
            p_ij: array![[10], [100]],
            omega_max: array![[0.2], [0.2]],
            s_ij: array![[0.0], [0.0]],
            b_total: 5, // вистачає рівно на одну одиницю
        }
    }

    /// Та сама задача, але з нульовими знижками — дає істинні однокритеріальні
    /// верхні межі F_IT і F_prov. Оскільки в комбінованому методі знижки є
    /// змінними і їх зменшення підвищує ОБИДВА доходи (рух (3)), коректною межею
    /// для інваріантів (1)–(2) є оптимум при r = 0, а НЕ розв'язок підзадачі при
    /// r_max (останній занижений множником (1 − r_max) і може бути перевищений).
    fn tiny_task_zero_discount() -> CombinedTask {
        let mut t = tiny_task();
        t.omega_max = array![[0.0], [0.0]];
        t
    }

    #[test]
    fn combined_invariants_hold() {
        // Pure-Rust core → no Python interpreter needed in the unit test.
        let task = tiny_task();
        let zero = tiny_task_zero_discount();

        // Стартові кандидати при r_max (вони ж — точки старту стадії 3).
        let (v_a, f_it_a) = solve_subtask_a(&task, 200);
        let (v_b, f_prov_b) = solve_subtask_b(&task, 200);
        let combined_a = f_it_a + provider_objective(&v_a, &task.p_ij);
        let combined_b = weighted_objective(&v_b, &task.c, &task.omega_max) + f_prov_b;

        // Істинна верхня межа F_IT (знижки оптимізовані до 0).
        let (_, f_it_upper) = solve_subtask_a(&zero, 200);

        let solver = CombinedSolver::new(200, 0.05, 0);
        let (best, _source, _ticks) = solver.solve_core(&task);

        // Інваріант 3 (головний): сумарна вигода не гірша за найкращу
        // однокритеріальну стартову — стадія 3 лише Парето-покращує, тож сума
        // F_IT + F_prov ніколи не спадає нижче точок старту.
        assert!(best.f_it + best.f_prov >= combined_a.max(combined_b) - 1e-6);
        // Інваріант 1: F_IT не перевищує свого істинного оптимуму (при r = 0).
        assert!(best.f_it <= f_it_upper + 1e-6);
        // Інваріант 2: F_prov = Σp·v не залежить від r, тож межа — призначити всі
        // пари: F_prov ≤ Σ p_ij.
        assert!(best.f_prov <= task.p_ij.sum() as f64 + 1e-6);
    }
}
