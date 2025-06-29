"""
Módulo para simulação de séries de preços e análise de retornos financeiros.

Regras:
- Apenas bibliotecas padrão e NumPy são utilizadas.
- Todas as funções possuem type hints e docstrings estilo PEP 257.
"""
import numpy as np
def simular_precos(S0: float, sigma: float, days: int) -> np.ndarray:
    """
    Simula uma série de preços com ruído gaussiano.

    A fórmula usada é: St+1 = St + εt, onde εt ∼ N(0, σ²)

    Parameters:
    S0 (float): Preço inicial positivo.
    sigma (float): Desvio padrão do ruído (volatilidade).
    days (int): Número de dias a simular.

    Returns:
    np.ndarray: Vetor de preços simulados com tamanho days + 1.
    """
    if S0 <= 0:
        raise ValueError("S0 deve ser positivo.")
    if sigma < 0:
        raise ValueError("sigma deve ser não-negativo.")
    if days <= 0:
        raise ValueError("days deve ser maior que 0.")

    precos = np.empty(days + 1)
    precos[0] = S0

    # Geração dos ruídos normais com média 0 e desvio padrão sigma
    ruidos = np.random.normal(loc=0.0, scale=sigma, size=days)

    # Preenchimento dos preços
    for t in range(1, days + 1):
        precos[t] = precos[t - 1] + ruidos[t - 1]

    return precos



def calc_retornos_simples(prices: np.ndarray) -> np.ndarray:
    """
    Calcula os retornos simples de uma série de preços.

    rt = (Pt - Pt-1) / Pt-1

    Parameters:
    prices (np.ndarray): Vetor de preços com dimensão (n+1,).

    Returns:
    np.ndarray: Vetor de retornos simples de dimensão (n,).
    """
    if len(prices) < 2:
        raise ValueError("O vetor de preços deve conter pelo menos dois valores.")

    return (prices[1:] - prices[:-1]) / prices[:-1]


def calc_retornos_log(prices: np.ndarray) -> np.ndarray:
    """
    Calcula os log-retornos de uma série de preços.

    rlog_t = ln(Pt / Pt-1)

    Parameters:
    prices (np.ndarray): Vetor de preços com dimensão (n+1,).

    Returns:
    np.ndarray: Vetor de log-retornos de dimensão (n,).
    """
    if len(prices) < 2:
        raise ValueError("O vetor de preços deve conter pelo menos dois valores.")
    if np.any(prices <= 0):
        raise ValueError("Todos os preços devem ser positivos para o logaritmo.")

    return np.log(prices[1:] / prices[:-1])


def sma(returns: np.ndarray, window: int) -> np.ndarray:
    """
    Calcula a média móvel simples (SMA) de um vetor de retornos.

    Parameters:
    returns (np.ndarray): Vetor de retornos.
    window (int): Tamanho da janela de cálculo.

    Returns:
    np.ndarray: Vetor de médias móveis com dimensão (n - window + 1,).
    """
    if window <= 0:
        raise ValueError("A janela deve ser maior que 0.")
    if len(returns) < window:
        raise ValueError("O vetor de retornos deve ter tamanho >= janela.")

    return np.array([
        np.mean(returns[i - window + 1:i + 1])
        for i in range(window - 1, len(returns))
    ])


def rolling_std(returns: np.ndarray, window: int, days_size: int = 0) -> np.ndarray:
    """
    Calcula o desvio padrão móvel de um vetor de retornos.

    σ_t = sqrt(1 / (window - days_size) * sum((r_i - r̄_t)^2))

    Parameters:
    returns (np.ndarray): Vetor de retornos.
    window (int): Tamanho da janela de cálculo.
    days_size (int): Quantidade de graus de liberdade (ex: 1 para variância amostral).

    Returns:
    np.ndarray: Vetor de desvios padrões móveis com dimensão (n - window + 1,).
    """
    if window <= days_size:
        raise ValueError("window deve ser maior que days_size.")
    if len(returns) < window:
        raise ValueError("O vetor de retornos deve ter tamanho >= janela.")

    stds = []
    for i in range(window - 1, len(returns)):
        window_data = returns[i - window + 1:i + 1]
        mean = np.mean(window_data)
        variance = np.sum((window_data - mean) ** 2) / (window - days_size)
        stds.append(np.sqrt(variance))
    return np.array(stds)
