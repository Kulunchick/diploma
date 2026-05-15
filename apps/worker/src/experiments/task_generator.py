"""
Task model and TaskGenerator, extracted from apps/api/src/coursework_operations/.
Used exclusively by experiment specs to generate random problem instances.
"""
from typing import List

import numpy as np


class Task:
    def __init__(
        self,
        m: int,
        n: int,
        c: List[List[int]],
        B_ij: List[List[int]],
        B_total: int,
        omega: List[List[float]],
    ):
        self.m = m
        self.n = n
        self.c = np.array(c, dtype=np.int64)
        self.B_ij = np.array(B_ij, dtype=np.int64)
        self.B_total = B_total
        self.omega = np.array(omega, dtype=np.float64)


class TaskGenerator:
    def __init__(self, c_min, c_max, b_min, b_max, omega_min, omega_max):
        self.c_min = c_min
        self.c_max = c_max
        self.b_min = b_min
        self.b_max = b_max
        self.omega_min = omega_min
        self.omega_max = omega_max

    def generate_task(self, m: int, n: int) -> Task:
        c = np.random.uniform(self.c_min, self.c_max, (m, n)).tolist()
        B_ij = np.random.uniform(self.b_min, self.b_max, (m, n)).tolist()
        omega = np.random.uniform(self.omega_min, self.omega_max, (m, n)).tolist()
        B = np.random.randint(np.min(B_ij), np.sum(B_ij))
        return Task(m=m, n=n, c=c, B_ij=B_ij, B_total=B, omega=omega)
