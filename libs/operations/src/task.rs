// Модель задачі формування пакетів сервісів для провайдерів інфокомунікацій
// (підзадача А — з точки зору ІТ-компанії).
//
// Позначення (відповідають формальній постановці задачі):
//   m       — кількість сервісів IT-компанії (у статті — k)
//   n       — кількість провайдерів інфокомунікацій (у статті — m)
//   c[i,j]  — преференційна (базова) ціна d_ij надання сервісу S_i провайдеру P_j
//   b_ij    — обсяг ресурсу IT-компанії β_ij, потрібного для надання сервісу S_i
//             провайдеру P_j (вважаємо, що лімітує один ресурс ІТ-компанії,
//             див. розділ 5.1 статті)
//   b_total — загальний обсяг доступного ресурсу IT-компанії T_l за плановий період
//   omega   — матриця знижок r_ij ∈ [0, 1), які ІТ-компанія надає провайдеру
//             на преференційну ціну сервісу
//
// Обмеження (4) на відносну цінність сервісу та (5) на показники SLA вважаються
// виконаними (див. передумови в розділі 5.1 статті). Обмеження міжсервісної
// залежності (6) у цій моделі не враховуються, бо реалізується лише підзадача А
// без процедур комбінованого методу.

use ndarray::Array2;
use numpy::{PyArrayMethods, PyReadonlyArray2};
use pyo3::{exceptions::PyValueError, prelude::*};

#[pyclass]
pub struct Task {
    /// Кількість сервісів IT-компанії.
    pub m: usize,
    /// Кількість провайдерів інфокомунікацій.
    pub n: usize,
    /// Матриця преференційних цін d_ij надання сервісу S_i провайдеру P_j.
    pub c: Array2<i64>,
    /// Матриця обсягів ресурсу IT-компанії β_ij для надання сервісу S_i провайдеру P_j.
    pub b_ij: Array2<i64>,
    /// Загальний обсяг доступного ресурсу IT-компанії T за плановий період.
    pub b_total: i64,
    /// Матриця знижок r_ij ∈ [0, 1) до преференційної ціни.
    pub omega: Array2<f64>,
}

#[pymethods]
impl Task {
    #[new]
    pub fn new(
        m: usize,
        n: usize,
        c: PyReadonlyArray2<i64>,
        b_ij: PyReadonlyArray2<i64>,
        b_total: i64,
        omega: PyReadonlyArray2<f64>,
    ) -> PyResult<Self> {
        let c = c.to_owned_array();
        let b_ij = b_ij.to_owned_array();
        let omega = omega.to_owned_array();

        let task = Task { m, n, c, b_ij, b_total, omega };
        task.validate()?;
        Ok(task)
    }

    pub fn validate(&self) -> PyResult<bool> {
        if self.c.shape()[0] != self.m || self.c.shape()[1] != self.n {
            return Err(PyValueError::new_err(
                "Некоректні розміри матриці преференційних цін",
            ));
        }
        if self.b_ij.shape()[0] != self.m || self.b_ij.shape()[1] != self.n {
            return Err(PyValueError::new_err(
                "Некоректні розміри матриці обсягів ресурсу IT-компанії",
            ));
        }
        if self.omega.shape()[0] != self.m || self.omega.shape()[1] != self.n {
            return Err(PyValueError::new_err(
                "Некоректні розміри матриці знижок",
            ));
        }
        if self.omega.iter().any(|&x| x < 0.0 || x > 1.0) {
            return Err(PyValueError::new_err(
                "Знижки r_ij повинні бути в діапазоні [0, 1)",
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
