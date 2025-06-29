# Lista 1 - Introdução à Programação e Ciência de Dados
############# Parte 1: Listas e Tuplas #############
# Questão 1 - Fução pares e impares (nums)
## Verificar se é par ou ímpar
## Após categoriza-lo, adicionar a sua respectiva lista
## retornar / printar ambas as listas no final

def pares_e_impares(nums):
    """
    Function split in two lists if its odd or even.

    Parameters:
    argument "nums" (list): list of integer

    Returns:
    list: Two new list containing odds and even separately

    """
    par_lista = []
    impar_lista = []
    for num in nums:
        if num % 2 == 0:
            par_lista.append(num)
        else:
            impar_lista.append(num)
    
    return par_lista, impar_lista

# Questão 2 - Função filtrar por Comprimento
# Verificar se um item da lista é maior do que o parâmetro especificado, caso seja:
# Adicionar a uma nova lista que será printada no final
def filtrar_por_tamanho(lista, k):
    """
    Function filters a list based on strings length. 

    Parameters:
    argument "lista" (list): list of strings to be filtered
    argument "k" (int): interger input to filter strings length

    Returns:
    list: A new list containing only strings with length higher than parameter K.
    In case none items match the requriment, a messaged is printed.

    """
    new_lista =[]
    for item in lista:
        if len(item)>k:
            new_lista.append(item)

    if not new_lista:
        print(f"Não há nenhum item na lista inserida que possua tamanho maior do que {k}")
        return new_lista
    else:
        print(f"A lista retornada é: {new_lista}")
        return new_lista


# Questão 3 - Rotação Tupla
# Tuplas, uma vez criadas, não podem ser alteradas
# Preciso criar uma nova tupla que comece a partir do novo número indicado
# Primeiro preciso reogarnizar baseado na posição indicada e armazenar numa lista
# Apartir da lsita converter para Tuplas
def rotate_tuple(tpl, n):
    """
    Function creates a new tuple with the same items, but starting in a different position 

    Parameters:
    argument "tpl" (list): list of strings to be filtered
    argument "n" (int): interger input to filter strings length

    Returns:
    tuple: A new tuple rotated

    """
    # lim máximo que o contador pode assumir é o tamanho da tupla -1, uma vez que o índice começa em zero.
    lim_tpl = len(tpl) -1
    # nova lista pra armazenar os itens da tupla de forma ajustada
    new_list = []
    # A reordenação começa a partir do último item - n. Essa relação foi especificada no problema da lista.
    counter = len(tpl) - n
    # realizando um for sei que as iterações são limitadas ao número de itens que contém na tupla. Logo, garanto que a reordenação só vai ser realizada uma vez porque é baseado em len(tpl)
    for item in tpl:
        new_list.append(tpl[counter])

        counter = counter + 1

        if counter>lim_tpl:
            counter = 0
   
    new_tpl = tuple(new_list)
    return new_tpl

# Questão 4 - Transposta da Matriz
# Matrix transposta = Se A = (aij)m x n, então At = (a'ji) n x m
# Preciso conseguir identificar o que é linha e coluna numa lista e loopar até reordenar todas.
# Precisamos assumir que cada colunar tem o mesmo número de linhas, para realizar a transposta. 

def transpose(matrix):
    """
    Function creates a new transposed matrix

    Parameters:
    argument "matrix" (list): list of list containing a matrix

    Returns:
    tuple: A new matrix with original values transposed

    """

    # lista de suporte para armazenar a matriz
    new_matrix = []
    # matrix boundaries
    col_matrix = len(matrix) - 1
    lin_matrix = len(matrix[0]) -1
    counter_lin = 0
    
    while counter_lin <= lin_matrix:
        counter_col = 0
        new_sub_lista_linha = []
        # pra cada primeiro item da coluna, vamos adicionar a uma nova lista sequencialmente
        while counter_col <= col_matrix:
            new_sub_lista_linha.append(matrix[counter_col][counter_lin])
            counter_col = counter_col + 1
        
        new_matrix.append(new_sub_lista_linha)
        counter_lin = counter_lin + 1
    
    return new_matrix


# Questão 5 - Alisamento de Lista Aninhada
# Utilizar princípios da questão anterior. 
# Primeiro preciso criar uma lsita vazia onde os items serão append um a um. 
# Depois preciso realizar um loop por cada coluna da minha "matrix". 
# Ao entrar na primeira coluna, preciso "flatten" todos os itens que estão nessa coluna na minha nova lista.
def flatten(lst):
    """
    Function creates a new list with all items flattened

    Parameters:
    argument "lst" (list): list of lists

    Returns:
    list: A new list without sub-lists

    """
    new_flatten = []
    col_lista = len(lst)-1
    counter_col = 0 
    # looping cada coluna da lista
    while counter_col <= col_lista:
        # para cada coluna acessamos os subitens
        for item in lst[counter_col]:
            # adicionamos um a um subitem numa nova lista
            new_flatten.append(item)
        counter_col = counter_col+1
    # armazenamos o resultado na função
    return new_flatten


############# Parte 2 - Dicionário #############

# Questão 1 - Agrupamento por Chave
# Passará uma LISTA de TUPLA pela função que será desmembrada em chave e valor.
# Cada chave poderá ter 1 ou mais valores associados
def group_by(pairs):

    new_dic = {}
    for tuplas in pairs:
        if not tuplas[0] in new_dic.keys():
            new_dic[tuplas[0]]= [tuplas[1]]
        else:
            new_dic[tuplas[0]]=new_dic[tuplas[0]]+[tuplas[1]]
    return new_dic


# Questão 2 - Inversão de Mapeamento
# Objetivo é passar um dicionário com chaves e valores que será invertido, isto é valores:chaves
# Podemos loopar por cada item e facilmente obteremos esse resultado. Contudo, pretendo testar os argumentos keys() e values() como uma alternativa matricial
def invert_map(d):
    inverted_dic ={}
    for keys in d:
        inverted_dic[keys] = d[keys]
    return inverted_dic

    

# Questão 3 - Índices por Valor
# O objetivo é usar os valores da lista como keys e o index como values
def indices_of(lst):
    dicionario={}
    for item in lst:
        dicionario[item] = lst.index(item)
    return dicionario

# Questão 4 - Fusão com Resolução de Conflitos
# Fará a junção de mais de um dicionário em um único dicionário apenas
def merge_dicts(dicts):
    dicionario={}
    for item in dicts:
        for key in item:
            if not key in dicionario.keys():
                dicionario[key]=item[key]
            else:
                dicionario[key]+=item[key]
    return dicionario


# Questão 5 - Contador de Dígitos
# Retorna um dicionario que é contador
# transformar o numero em string, loopar a string e contar itens 
def conta_digitos(n):
    dic_counter={}
    text = str(n)
    for i in range(len(text)):
        if not text[i] in dic_counter.keys():
            dic_counter[text[i]]=1
        else:
            dic_counter[text[i]]+=1
    return dic_counter

############# Parte 3 - Desafios de Funções #############

# Questão 1 - Contador de Anagramas
def count_anagrams(words):
    dic_anagrams = {}
    for item in words:
        alphabetic = ''.join(sorted(item))
        if not alphabetic in dic_anagrams.keys():
            dic_anagrams[alphabetic] = [item]
        else:
            lst = dic_anagrams[alphabetic]
            lst.append(item)
            dic_anagrams[alphabetic] = lst
    
    return dic_anagrams


# Questão 2 - Parser de CSV
def parse_csv(text, sep=','):
    data = {}
    data_split= text.split("\n")[1:]
    header_split= (text.split("\n")[0]).split(sep)

    for item in header_split:
        data[item.strip()] =[]

    for item in data_split:
        list_helper = item.split(sep)
        counter = 0
        for key in data:
            data[key]=data[key]+[list_helper[counter].strip()]
            counter = counter +1 
    return data



# Questão 3 - Validação de Sudoku
# Deve buscar a validação de Arrays em 3 etapas, e garantir que não há erros em cada uma delas.
# Lembrar que deve tratar os zeros
def validar_sudoku(tabuleiro):
    check_linha = True
    check_coluna = True
    check_bloco = True
    # Loopando as linhas
    for linha in tabuleiro:
        armazena = []
        for number in linha:
            if number not in armazena and number!=0:
                armazena.append(number)
            elif number in armazena:
                check_linha = False
    
    #Loopando as colunas
    for i in range(8):
        armazena = []
        for  j in range(8):
            number = tabuleiro[j][i]
            if number not in armazena and number!=0:
                armazena.append(number)
            elif number in armazena:
                check_coluna = False
    #Loopando blocos de 3x3
    for bj in range(2):
        for bi in range(2):
            for i in range(2):
                armazena = []
                for  j in range(2):
                    number = tabuleiro[bj*3+j][bi*3+i]
                    if number not in armazena and number!=0:
                        armazena.append(number)
                    elif number in armazena:
                        check_bloco = False

    if check_linha == check_coluna == check_bloco == False:
        check_final=False


    return check_linha





