// Модель задачі для комбінованого методу формування пакетів сервісів
// (розділи 3–5 статті). На відміну від `Task` (лише підзадача А), несе також
// дані провайдерів: дохід p_ij, верхню межу знижок r_max_ij та пороги
// відносної цінності s_ij для обмеження (4).
//
// Матриці вже агреговані за «логічними одиницями» (групи → одиниці) на боці
// Python, тому m — кількість одиниць, n — кількість провайдерів.

use ndarray::Array2;
use numpy::{PyArrayMethods, PyReadonlyArray2};
use pyo3::{exceptions::PyValueError, prelude::*};

#[pyclass]
pub struct CombinedTask {
    /// Кількість логічних одиниць (сервісів/груп) IT-компанії.
    pub m: usize,
    /// Кількість провайдерів інфокомунікацій.
    pub n: usize,
    /// Преференційні ціни d_ij (вже зведені до int на боці Python).
    pub c: Array2<i64>,
    /// Обсяг ресурсу IT-компанії β_ij для пари «одиниця–провайдер».
    pub b_ij: Array2<i64>,
    /// Дохід провайдера p_ij від надання сервісу своїм клієнтам.
    pub p_ij: Array2<i64>,
    /// Верхня межа знижки r_max_ij ∈ [0, 1) для кожної пари.
    pub omega_max: Array2<f64>,
    /// Пороги відносної цінності s_ij ≥ 0 (обмеження (4)).
    pub s_ij: Array2<f64>,
    /// Загальний ресурс IT-компанії T (єдиний ресурс, розділ 5.1).
    pub b_total: i64,
}

#[pymethods]
impl CombinedTask {
    #[new]
    pub fn new(
        m: usize,
        n: usize,
        c: PyReadonlyArray2<i64>,
        b_ij: PyReadonlyArray2<i64>,
        p_ij: PyReadonlyArray2<i64>,
        omega_max: PyReadonlyArray2<f64>,
        s_ij: PyReadonlyArray2<f64>,
        b_total: i64,
    ) -> PyResult<Self> {
        let task = CombinedTask {
            m,
            n,
            c: c.to_owned_array(),
            b_ij: b_ij.to_owned_array(),
            p_ij: p_ij.to_owned_array(),
            omega_max: omega_max.to_owned_array(),
            s_ij: s_ij.to_owned_array(),
            b_total,
        };
        task.validate()?;
        Ok(task)
    }

    pub fn validate(&self) -> PyResult<bool> {
        let dims = [
            ("преференційних цін", self.c.shape()),
            ("обсягів ресурсу", self.b_ij.shape()),
            ("доходу провайдера", self.p_ij.shape()),
            ("верхньої межі знижок", self.omega_max.shape()),
            ("порогів відносної цінності", self.s_ij.shape()),
        ];
        for (label, shape) in dims {
            if shape[0] != self.m || shape[1] != self.n {
                return Err(PyValueError::new_err(format!(
                    "Некоректні розміри матриці {label}"
                )));
            }
        }
        if self.omega_max.iter().any(|&x| x < 0.0 || x >= 1.0) {
            return Err(PyValueError::new_err(
                "Верхня межа знижок r_max_ij повинна бути в діапазоні [0, 1)",
            ));
        }
        if self.s_ij.iter().any(|&x| x < 0.0) {
            return Err(PyValueError::new_err(
                "Пороги відносної цінності s_ij повинні бути невід'ємними",
            ));
        }
        if self.b_total <= 0 {
            return Err(PyValueError::new_err(
                "Загальний ресурс IT-компанії повинен бути додатнім",
            ));
        }
        Ok(true)
    }
}

impl CombinedTask {
    /// Обмеження (4) — відносна цінність сервісу для провайдера.
    ///
    /// Стаття: s_ij ≤ p_ij / b_ij, де b_ij — вартість надання сервісу провайдером.
    /// У нашій моделі вартість провайдера = ціна, яку він платить IT-компанії,
    /// тобто преференційна ціна після знижки: b_ij = (1 − r_ij) · d_ij. Звідси
    ///
    ///     s_ij ≤ p_ij / ((1 − r_ij) · d_ij)   ⇔   s_ij · (1 − r_ij) · d_ij ≤ p_ij
    ///
    /// «дохід провайдера p_ij має бути щонайменше у s_ij разів більший за те, що
    /// він заплатив IT-компанії». s_ij = 0 → завжди допустимо. Знижка входить
    /// через знаменник (вартість): більша r_ij знижує вартість і полегшує
    /// допустимість — це й є важіль поступок стадії 3. Множникову форму обрано,
    /// щоб коректно обробити d_ij = 0 (безкоштовний сервіс): 0 ≤ p_ij — істина.
    pub fn admissible(&self, i: usize, j: usize, r: f64) -> bool {
        self.s_ij[[i, j]] * (1.0 - r) * self.c[[i, j]] as f64 <= self.p_ij[[i, j]] as f64
    }

    /// Використаний ресурс ΣΣ β_ij · v_ij для розв'язку v.
    pub fn resource_used(&self, v: &Array2<i64>) -> i64 {
        let mut total = 0_i64;
        for i in 0..self.m {
            for j in 0..self.n {
                if v[[i, j]] == 1 {
                    total += self.b_ij[[i, j]];
                }
            }
        }
        total
    }
}
