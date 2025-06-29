import numpy as np
import threading
from typing import Dict


def calcular_medias_moveis(acoes: Dict[str, np.ndarray], janela: int) -> Dict[str, np.ndarray]:
    """
    Calcula médias móveis para várias ações em paralelo.

    Cada ação é processada em uma thread diferente.

    Parameters:
    acoes (Dict[str, np.ndarray]): Dicionário com preços por ação.
    janela (int): Tamanho da janela da média móvel.

    Returns:
    Dict[str, np.ndarray]: Médias móveis por ação.
    """
    resultado: Dict[str, np.ndarray] = {}
    lock = threading.Lock()

    def calcular_media(nome: str, precos: np.ndarray):
        if len(precos) < janela:
            medias = np.array([])
        else:
            medias = np.convolve(precos, np.ones(janela) / janela, mode='valid')
        with lock:
            resultado[nome] = medias

    threads = [
        threading.Thread(target=calcular_media, args=(nome, precos))
        for nome, precos in acoes.items()
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    return resultado


def calcular_volatilidade(retornos: np.ndarray, janela: int, num_threads: int) -> np.ndarray:
    """
    Calcula a volatilidade (desvio padrão) em janelas móveis usando múltiplas threads.

    Divide os retornos em blocos e processa cada bloco em uma thread.

    Parameters:
    retornos (np.ndarray): Série de retornos diários.
    janela (int): Tamanho da janela para cálculo da volatilidade.
    num_threads (int): Número de threads a serem utilizadas.

    Returns:
    np.ndarray: Vetor com as volatilidades por janela.
    """
    n = len(retornos)
    resultado = [None] * (n - janela + 1)
    lock = threading.Lock()

    def worker(inicio: int, fim: int):
        for i in range(inicio, min(fim, n - janela + 1)):
            janela_retorno = retornos[i:i + janela]
            std = np.std(janela_retorno, ddof=0)
            with lock:
                resultado[i] = std

    total_janelas = n - janela + 1
    chunk_size = (total_janelas + num_threads - 1) // num_threads
    threads = []

    for i in range(num_threads):
        start = i * chunk_size
        end = min(start + chunk_size, total_janelas)
        t = threading.Thread(target=worker, args=(start, end))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return np.array(resultado)
