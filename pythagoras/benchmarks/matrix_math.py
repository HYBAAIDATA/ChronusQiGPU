"""PYTHAGORAS v12 benchmark target: matrix multiplication."""


def multiply_matrices(a, b):
    rows_a = len(a)
    cols_a = len(a[0])
    cols_b = len(b[0])
    result = [[0.0 for _ in range(cols_b)] for _ in range(rows_a)]
    for row in range(rows_a):
        for column in range(cols_b):
            for inner in range(cols_a):
                result[row][column] += a[row][inner] * b[inner][column]
    return result
