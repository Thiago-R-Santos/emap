"""
Módulo de filtragem e detecção de sinais em vetores e séries temporais.
"""

import numpy as np
from typing import Tuple


def replace_negatives(v: np.ndarray, new_value: float) -> np.ndarray:
    """
    Substitui valores negativos em um vetor por um novo valor.

    A operação é feita por indexação booleana (sem usar np.where).

    Parameters:
    v (np.ndarray): Vetor de entrada (dimensão n).
    new_value (float): Valor escalar para substituir elementos negativos.

    Returns:
    np.ndarray: Vetor resultante com os negativos substituídos.
    """
    if v.ndim != 1:
        raise ValueError("O vetor v deve ser unidimensional.")

    v_copy = v.copy()
    mask = v_copy < 0
    v_copy[mask] = new_value
    return v_copy


def local_peaks(series: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Identifica os máximos locais de uma série temporal unidimensional.

    Um ponto xi é um pico local se: xi-1 < xi > xi+1.

    Parameters:
    series (np.ndarray): Série temporal com N >= 3 elementos.

    Returns:
    Tuple[np.ndarray, np.ndarray]:
        - indices: posições dos picos locais.
        - peaks: valores correspondentes aos picos.
    """
    if series.ndim != 1:
        raise ValueError("A série deve ser unidimensional.")
    if len(series) < 3:
        raise ValueError("A série deve ter pelo menos 3 elementos.")

    indices = []
    peaks = []

    for i in range(1, len(series) - 1):
        if series[i - 1] < series[i] > series[i + 1]:
            indices.append(i)
            peaks.append(series[i])

    return np.array(indices), np.array(peaks)
