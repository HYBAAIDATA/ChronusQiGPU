"""Exact finite torus chain-complex certificate, not operational error recovery."""
from __future__ import annotations

from fractions import Fraction
from itertools import combinations


def torus7():
    """Two oriented translation orbits of triangles on Z/7Z."""
    edges = list(combinations(range(7), 2))
    faces = [(i,(i+1)%7,(i+3)%7) for i in range(7)]
    faces += [(i,(i+3)%7,(i+2)%7) for i in range(7)]
    if len({frozenset(f) for f in faces}) != 14:
        raise ValueError("duplicate face")
    d1 = [[0]*21 for _ in range(7)]
    d2 = [[0]*14 for _ in range(21)]
    for index,(u,v) in enumerate(edges):
        d1[u][index], d1[v][index] = -1, 1
    for index,(u,v,w) in enumerate(faces):
        for a,b in ((u,v),(v,w),(w,u)):
            d2[edges.index(tuple(sorted((a,b))))][index] = 1 if a<b else -1
    if any(sum(x != 0 for x in row) != 2 or sum(row) != 0 for row in d2):
        raise ValueError("edge incidence or orientation invalid")
    for vertex in range(7):
        link = {u:set() for u in range(7) if u != vertex}
        for face in faces:
            if vertex in face:
                x,y = [v for v in face if v != vertex]
                link[x].add(y)
                link[y].add(x)
        if any(len(v) != 2 for v in link.values()):
            raise ValueError("vertex link is not a cycle")
        pending = [next(iter(link))]
        seen = set()
        while pending:
            u = pending.pop()
            if u not in seen:
                seen.add(u)
                pending.extend(link[u]-seen)
        if seen != set(link):
            raise ValueError("disconnected vertex link")
    if any(sum(d1[i][k]*d2[k][j] for k in range(21)) for i in range(7) for j in range(14)):
        raise ValueError("boundary composition is nonzero")
    return d1,d2


def rational_rank(rows) -> int:
    matrix = [[Fraction(v) for v in row] for row in rows]
    if not matrix:
        return 0
    rank = 0
    for column in range(len(matrix[0])):
        pivot = next((i for i in range(rank,len(matrix)) if matrix[i][column]),None)
        if pivot is None:
            continue
        matrix[pivot],matrix[rank] = matrix[rank],matrix[pivot]
        for i in range(rank+1,len(matrix)):
            factor = matrix[i][column]/matrix[rank][column]
            matrix[i] = [x-factor*y for x,y in zip(matrix[i],matrix[rank])]
        rank += 1
        if rank == len(matrix):
            break
    return rank


def _mask(row):
    return sum((v%2)<<i for i,v in enumerate(row))


def _basis(rows):
    pivots = {}
    for value in rows:
        while value:
            pos = value.bit_length()-1
            if pos not in pivots:
                pivots[pos] = value
                break
            value ^= pivots[pos]
    return pivots


def _member(value,pivots):
    while value:
        pos = value.bit_length()-1
        if pos not in pivots:
            return False
        value ^= pivots[pos]
    return True


def _distance(checks, stabilizers, edges):
    span = _basis(stabilizers)
    for weight in range(1,edges+1):
        for support in combinations(range(edges),weight):
            word = sum(1<<i for i in support)
            if all((word & check).bit_count()%2 == 0 for check in checks) and not _member(word,span):
                return weight,support
    raise ValueError("no nontrivial logical operator")


def torus_certificate():
    d1,d2 = torus7()
    r1,r2 = rational_rank(d1),rational_rank(d2)
    x,z = [_mask(row) for row in d1],[_mask(row) for row in zip(*d2)]
    rx,rz = len(_basis(x)),len(_basis(z))
    dz,zw = _distance(x,z,21)
    dx,xw = _distance(z,x,21)
    return {"betti_q": (7-r1,21-r1-r2,14-r2), "betti_f2": (7-rx,21-rx-rz,14-rz),
            "n":21, "k":21-rx-rz, "d_x":dx, "d_z":dz, "distance":min(dx,dz),
            "x_witness":xw, "z_witness":zw}
