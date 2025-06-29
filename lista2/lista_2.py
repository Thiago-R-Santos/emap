# Parte 1: Biblioteca math
import math
from itertools import combinations, islice
from typing import List
import random
import urllib.request
import os

# 1. Valor Futuro (Juros Compostos)
def future_value(pv: float, r: float, n: int, t: float) -> float:
    """
    Calcula o valor futuro (FV) com base no valor presente (PV), taxa de juros anual (r),
    número de períodos por ano (n) e tempo em anos (t).
    Fórmula: FV = PV * (1 + r/n)^(n*t)
    """
    return pv * (1 + r / n) ** (n * t)

# 2. Desvio Padrão de Retornos
def standard_deviation(returns: List[float]) -> float:
    """
    Calcula o desvio padrão de uma lista de retornos.
    Fórmula: sqrt(1/N * sum((xi - media)^2))
    """
    mean = sum(returns) / len(returns)
    variance = sum((x - mean) ** 2 for x in returns) / len(returns)
    return math.sqrt(variance)

# 3. Tempo para Dobrar (Capitalização Contínua)
def time_to_double(r: float) -> float:
    """
    Calcula o tempo necessário para dobrar um investimento com capitalização contínua.
    Fórmula: t = ln(2) / ln(1 + r)
    """
    return math.log(2) / math.log(1 + r)

# Parte 2: Biblioteca itertools
# 1. Combinações de Ativos
def portfolio_combinations(assets: List[str], k: int) -> List[tuple]:
    """
    Retorna todas as combinações possíveis de ativos de tamanho k.
    """
    return list(combinations(assets, k))

# 2. Média Móvel
def moving_average(prices: List[float], window: int) -> List[float]:
    """
    Retorna a média móvel de uma lista de preços, com janela deslizante.
    """
    result = []
    for i in range(len(prices) - window + 1):
        win = list(islice(prices, i, i + window))
        result.append(sum(win) / window)
    return result

# Parte 3: Biblioteca random
# 1. Simulação de Preço de Ação
def simulate_stock_price(initial_price: float, mu: float, sigma: float, days: int) -> List[float]:
    """
    Simula o preço de uma ação por um número de dias usando variações gaussianas.
    """
    prices = [initial_price]
    for _ in range(days):
        variation = random.gauss(mu, sigma)
        new_price = prices[-1] + variation
        prices.append(new_price)
    return prices

# Parte 4: Bibliotecas urllib e os
# 1. Download e Concatenação de Dados do BLS QCEW
def download_and_merge(years_quarters: List[tuple], output_file: str):
    """
    Baixa e concatena arquivos CSV do BLS QCEW com base em anos e trimestres fornecidos.
    """
    os.makedirs("data", exist_ok=True)

    for year, quarter in years_quarters:
        url = f"https://data.bls.gov/cew/data/api/{year}/{quarter}/industry/10.csv"
        filepath = f"data/{year}_q{quarter}.csv"
        urllib.request.urlretrieve(url, filepath)

    csv_files = sorted([f for f in os.listdir("data") if f.endswith(".csv")])
    
    with open(output_file, 'w', encoding='utf-8') as outfile:
        wrote_header = False
        for fname in csv_files:
            with open(os.path.join("data", fname), 'r', encoding='utf-8') as infile:
                lines = infile.readlines()
                if not wrote_header:
                    outfile.write(lines[0])  # Escreve cabeçalho
                    wrote_header = True
                outfile.writelines(lines[1:])  # Escreve dados (sem cabeçalho)

