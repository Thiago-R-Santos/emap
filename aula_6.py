

def gen1():
    print("Inicío do Gerador 1")
    yield 1
    yield 2
    yield 3
    print("Fim do Gerador 1")


def gen2(func_geradora=None):
    print("Inicio do gerador 2")
    if func_geradora is not None:
        yield from func_geradora
    yield 4
    yield 5
    yield 6
    print("Fim do Gerador 2")

gerador_1 = gen2(gen1())
gerador_2 = gen2()

for numero in gerador_1:
    print(numero)

for numero in gerador_2:
    print(numero)


print(40*'#')

import numpy as np
"""
#Método para usar 10% da memória quando temos muito dado
def gerar_blocos(tamanho_total, tamanho_bloco):
    for inicio in range(0, tamanho_total, tamanho_bloco):
        fim = min(inicio + tamanho_bloco, tamanho_total)
        yield np.arange(inicio, fim)

for cada_bloco in gerar_blocos(1_000_000, 100_000):
    print(f'Forma Bloco - {cada_bloco.shape}. Início do Bloco - {cada_bloco[0]}')
"""

def gerar_blocos_filtrados(tamanho_total, tamanho_bloco, filtro_func):
    for cada_bloco_gerado in gerar_blocos(tamanho_total, tamanho_bloco):

# Trabalhando com filtro
def multiplos_de_7(valor):
    return valor % 7 == 0

for cada_bloco_filtrado in gerar_blocos_filtrados(1_000_000, 100_000)