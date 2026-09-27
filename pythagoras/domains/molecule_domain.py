"""
PYTHAGORAS — MOLECULE DOMAIN
Molecular/protein structure evolution domain.

- Representation: PDB-subset source / parsed atom records.
- Coherence: folding coherence — compactness balance (radius of gyration
  vs extent, φ-targeted), residue size consistency, and bond density.
- CGP primitives: mutate_residue, rotate_bond, swap_residue, delete_residue.
- Mutation primitives: ADD:Atom, ADD:Residue, REFACTOR:Relax,
  REFACTOR:Renumber, ADVERSARIAL:Perturb.
- Tests: verify_energy — steric sanity (no atomic clashes below 0.8 Å),
  finite coordinates, non-empty structure.
- Features: the abstract 8-dimensional basis instantiated on molecules.

Coordinates are ångströms. Bonds are inferred geometrically (< 1.9 Å).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..domain import Domain, MutationPrimitive, WeightedPrimitive
from ..phi_resonance import PHI


_BOND_THRESHOLD = 1.9
_CLASH_THRESHOLD = 0.8

_RESIDUE_CYCLE = ["ALA", "GLY", "SER", "VAL", "LEU"]


def _dist(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    return math.sqrt(
        (a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 + (a["z"] - b["z"]) ** 2
    )


def _bonds(atoms: List[Dict[str, Any]]) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    for i in range(len(atoms)):
        for j in range(i + 1, len(atoms)):
            if _dist(atoms[i], atoms[j]) < _BOND_THRESHOLD:
                out.append((i, j))
    return out


def _residue_groups(atoms: List[Dict[str, Any]]) -> List[List[int]]:
    """Group atom indices by (chain, resseq) preserving order."""
    groups: List[List[int]] = []
    seen: Dict[Tuple[str, int], int] = {}
    for i, a in enumerate(atoms):
        key = (a["chain"], a["resseq"])
        if key not in seen:
            seen[key] = len(groups)
            groups.append([])
        groups[seen[key]].append(i)
    return groups


def _radius_of_gyration(atoms: List[Dict[str, Any]]) -> float:
    if not atoms:
        return 0.0
    pts = np.array([[a["x"], a["y"], a["z"]] for a in atoms], dtype=float)
    centroid = pts.mean(axis=0)
    return float(np.sqrt(((pts - centroid) ** 2).sum(axis=1).mean()))


def _max_extent(atoms: List[Dict[str, Any]]) -> float:
    if len(atoms) < 2:
        return 0.0
    pts = np.array([[a["x"], a["y"], a["z"]] for a in atoms], dtype=float)
    diff = pts[:, None, :] - pts[None, :, :]
    return float(np.sqrt((diff**2).sum(axis=-1)).max())


# =============================================================================
# Parsing / serialization (PDB subset)
# =============================================================================

def _parse_pdb(source: str) -> Dict[str, Any]:
    atoms: List[Dict[str, Any]] = []
    for raw in source.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        rec = line.split()[0] if line.split() else ""
        if rec not in ("ATOM", "HETATM"):
            continue  # TER/END/REMARK headers are tolerated and dropped
        parts = line.split()
        if len(parts) < 9:
            raise ValueError(f"malformed record: {line}")
        atoms.append(
            {
                "serial": int(parts[1]),
                "name": parts[2],
                "resname": parts[3],
                "chain": parts[4],
                "resseq": int(parts[5]),
                "x": float(parts[6]),
                "y": float(parts[7]),
                "z": float(parts[8]),
                "element": parts[-1] if len(parts) > 11 else parts[2][0],
            }
        )
    if not atoms:
        raise ValueError("structure contains no atoms")
    for a in atoms:
        if not (math.isfinite(a["x"]) and math.isfinite(a["y"]) and math.isfinite(a["z"])):
            raise ValueError("non-finite coordinate")
    return {"atoms": atoms}


def _unparse_pdb(rep: Dict[str, Any]) -> str:
    lines = []
    for a in rep["atoms"]:
        lines.append(
            "ATOM  {serial:>5} {name:<4} {resname:<3} {chain}{resseq:>4}    "
            "{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {element:>2}".format(
                serial=a["serial"],
                name=a["name"],
                resname=a["resname"],
                chain=a["chain"],
                resseq=a["resseq"],
                x=a["x"],
                y=a["y"],
                z=a["z"],
                element=a["element"],
            )
        )
    lines.append("END")
    return "\n".join(lines) + "\n"


def _transform(source: str, fn) -> str:
    try:
        rep = _parse_pdb(source)
        rep = fn(rep)
        return _unparse_pdb(rep)
    except Exception:
        return source


def _renumber(rep: Dict[str, Any]) -> Dict[str, Any]:
    for i, a in enumerate(rep["atoms"], start=1):
        a["serial"] = i
    for gi, group in enumerate(_residue_groups(rep["atoms"]), start=1):
        for i in group:
            rep["atoms"][i]["resseq"] = gi
    return rep


# =============================================================================
# CGP-layer primitives
# =============================================================================

def prim_mutate_residue(source: str, weight: float) -> str:
    """mutate_residue: cycle the first residue's identity (ALA->GLY->SER->...)."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        groups = _residue_groups(rep["atoms"])
        if not groups:
            return rep
        first = rep["atoms"][groups[0][0]]
        idx = _RESIDUE_CYCLE.index(first["resname"]) if first["resname"] in _RESIDUE_CYCLE else -1
        new_res = _RESIDUE_CYCLE[(idx + 1) % len(_RESIDUE_CYCLE)]
        for i in groups[0]:
            rep["atoms"][i]["resname"] = new_res
        return rep

    return _transform(source, go)


def prim_rotate_bond(source: str, weight: float) -> str:
    """rotate_bond: rotate all downstream atoms around the first bond axis
    by theta = weight * pi/8 (Rodrigues rotation about the bond pivot)."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        atoms = rep["atoms"]
        bonds = _bonds(atoms)
        if not bonds:
            return rep
        i, j = bonds[0]
        pivot = np.array([atoms[i]["x"], atoms[i]["y"], atoms[i]["z"]], dtype=float)
        axis = np.array(
            [atoms[j]["x"] - pivot[0], atoms[j]["y"] - pivot[1], atoms[j]["z"] - pivot[2]],
            dtype=float,
        )
        norm = np.linalg.norm(axis)
        if norm < 1e-9:
            return rep
        k = axis / norm
        theta = float(weight) * math.pi / 8.0
        c, s = math.cos(theta), math.sin(theta)
        for a in atoms[j:]:
            v = np.array([a["x"], a["y"], a["z"]], dtype=float) - pivot
            v_rot = v * c + np.cross(k, v) * s + k * np.dot(k, v) * (1.0 - c)
            a["x"], a["y"], a["z"] = (v_rot + pivot).tolist()
        return rep

    return _transform(source, go)


def prim_swap_residue(source: str, weight: float) -> str:
    """swap_residue: exchange the coordinate blocks of the first two residues."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        groups = _residue_groups(rep["atoms"])
        if len(groups) < 2:
            return rep
        g0, g1 = groups[0], groups[1]
        if len(g0) != len(g1):
            return rep
        for a, b in zip(g0, g1):
            pa = (rep["atoms"][a]["x"], rep["atoms"][a]["y"], rep["atoms"][a]["z"])
            pb = (rep["atoms"][b]["x"], rep["atoms"][b]["y"], rep["atoms"][b]["z"])
            rep["atoms"][a]["x"], rep["atoms"][a]["y"], rep["atoms"][a]["z"] = pb
            rep["atoms"][b]["x"], rep["atoms"][b]["y"], rep["atoms"][b]["z"] = pa
        return rep

    return _transform(source, go)


def prim_delete_residue(source: str, weight: float) -> str:
    """delete_residue: remove the last residue (keeping at least one)."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        groups = _residue_groups(rep["atoms"])
        if len(groups) < 2:
            return rep
        drop = set(groups[-1])
        rep["atoms"] = [a for i, a in enumerate(rep["atoms"]) if i not in drop]
        return _renumber(rep)

    return _transform(source, go)


# =============================================================================
# Mutation-layer primitives
# =============================================================================

def mut_add_atom(source: str) -> str:
    """ADD:Atom — append a hydrogen 0.9 Å from the last atom."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        last = rep["atoms"][-1]
        rep["atoms"].append(
            {
                "serial": last["serial"] + 1,
                "name": "H",
                "resname": last["resname"],
                "chain": last["chain"],
                "resseq": last["resseq"],
                "x": last["x"] + _BOND_THRESHOLD / 2.0,
                "y": last["y"],
                "z": last["z"],
                "element": "H",
            }
        )
        return rep

    return _transform(source, go)


def mut_add_residue(source: str) -> str:
    """ADD:Residue — append a GLY residue (N, CA, C, O) 3.8 Å past the tail."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        last = rep["atoms"][-1]
        resseq = last["resseq"] + 1
        serial = last["serial"]
        base_x = last["x"] + 3.8
        backbone = [
            ("N", "N", base_x, last["y"], last["z"]),
            ("CA", "C", base_x + 1.45, last["y"], last["z"]),
            ("C", "C", base_x + 2.78, last["y"] + 0.5, last["z"]),
            ("O", "O", base_x + 3.98, last["y"] + 0.5, last["z"]),
        ]
        for k, (name, elem, x, y, z) in enumerate(backbone, start=1):
            rep["atoms"].append(
                {
                    "serial": serial + k,
                    "name": name,
                    "resname": "GLY",
                    "chain": last["chain"],
                    "resseq": resseq,
                    "x": x,
                    "y": y,
                    "z": z,
                    "element": elem,
                }
            )
        return rep

    return _transform(source, go)


def mut_relax(source: str) -> str:
    """REFACTOR:Relax — separate the worst steric clash to 1.4 Å."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        atoms = rep["atoms"]
        worst: Optional[Tuple[int, int, float]] = None
        for i in range(len(atoms)):
            for j in range(i + 1, len(atoms)):
                d = _dist(atoms[i], atoms[j])
                if d < 1.2 and (worst is None or d < worst[2]):
                    worst = (i, j, d)
        if worst is None:
            return rep
        i, j, d = worst
        pi = np.array([atoms[i]["x"], atoms[i]["y"], atoms[i]["z"]], dtype=float)
        pj = np.array([atoms[j]["x"], atoms[j]["y"], atoms[j]["z"]], dtype=float)
        direction = pj - pi
        norm = np.linalg.norm(direction)
        if norm < 1e-9:
            direction = np.array([1.0, 0.0, 0.0])
            norm = 1.0
        direction /= norm
        pj_new = pi + direction * 1.4
        atoms[j]["x"], atoms[j]["y"], atoms[j]["z"] = pj_new.tolist()
        return rep

    return _transform(source, go)


def mut_renumber(source: str) -> str:
    """REFACTOR:Renumber — canonical serial/resseq numbering."""
    return _transform(source, _renumber)


def mut_adversarial(source: str) -> str:
    """ADVERSARIAL:Perturb — collapse the last atom onto the first (clash)."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        if len(rep["atoms"]) < 2:
            return rep
        first, last = rep["atoms"][0], rep["atoms"][-1]
        last["x"], last["y"], last["z"] = first["x"], first["y"], first["z"]
        return rep

    return _transform(source, go)


# =============================================================================
# The Molecule Domain
# =============================================================================

class MoleculeDomain(Domain):
    """
    MoleculeDomain: molecular structure evolution.

    Optimizes folding coherence — compactness balance, residue size
    consistency, and bond density of an atomic structure.
    """

    name = "molecule"
    file_extensions = (".pdb", ".ent")

    def __init__(self):
        self._primitives: Dict[str, WeightedPrimitive] = {
            "mutate_residue": prim_mutate_residue,
            "rotate_bond": prim_rotate_bond,
            "swap_residue": prim_swap_residue,
            "delete_residue": prim_delete_residue,
        }
        self._mutation_primitives: Dict[str, MutationPrimitive] = {
            "ADD:Atom": mut_add_atom,
            "ADD:Residue": mut_add_residue,
            "REFACTOR:Relax": mut_relax,
            "REFACTOR:Renumber": mut_renumber,
            "ADVERSARIAL:Perturb": mut_adversarial,
        }
        self._mutation_weights: Dict[str, float] = {
            "ADD:Atom": 0.450,
            "ADD:Residue": 0.500,
            "REFACTOR:Relax": 0.650,
            "REFACTOR:Renumber": 0.300,
            "ADVERSARIAL:Perturb": 0.100,
        }

    # -- representation -----------------------------------------------------

    def parse(self, source: str) -> Dict[str, Any]:
        return _parse_pdb(source)

    def unparse(self, rep: Dict[str, Any]) -> str:
        return _unparse_pdb(rep)

    def is_valid(self, source: str) -> bool:
        try:
            _parse_pdb(source)
            return True
        except Exception:
            return False

    # -- coherence ----------------------------------------------------------

    def coherence(self, source: str) -> float:
        return self.compute_components(source)["composite"]

    def compute_components(self, source: str) -> Dict[str, float]:
        try:
            rep = _parse_pdb(source)
        except Exception:
            return {
                "compactness_balance": 0.0,
                "residue_consistency": 0.0,
                "bond_density": 0.0,
                "composite": 0.0,
            }

        atoms = rep["atoms"]
        n = len(atoms)

        # Component 1: compactness balance — Rg/max_extent vs 1 - φ.
        if n >= 2:
            rg = _radius_of_gyration(atoms)
            extent = _max_extent(atoms)
            ratio = rg / extent if extent > 1e-9 else 0.0
            target = 1.0 - PHI
            compactness = max(0.0, 1.0 - abs(ratio - target) / target)
        else:
            compactness = 0.5

        # Component 2: residue size consistency — 1 / (1 + variance).
        groups = _residue_groups(atoms)
        sizes = [len(g) for g in groups]
        consistency = 1.0 / (1.0 + float(np.var(sizes))) if len(sizes) > 1 else 1.0

        # Component 3: bond density — bonds per atom, saturated at 1.0.
        density = min(1.0, len(_bonds(atoms)) / max(1, n))

        composite = float(
            np.clip((compactness + consistency + density) / 3.0, 0.0, 1.0)
        )
        return {
            "compactness_balance": float(compactness),
            "residue_consistency": float(consistency),
            "bond_density": float(density),
            "composite": composite,
        }

    # -- primitives ---------------------------------------------------------

    def primitives(self) -> Dict[str, WeightedPrimitive]:
        return self._primitives

    def mutation_primitives(self) -> Dict[str, MutationPrimitive]:
        return self._mutation_primitives

    def mutation_weights(self) -> Dict[str, float]:
        return dict(self._mutation_weights)

    # -- tests --------------------------------------------------------------

    def tests(self, source: str) -> bool:
        """
        verify_energy: steric sanity — at least one atom, finite
        coordinates, and no atomic clashes below the 0.8 Å threshold.
        """
        try:
            rep = _parse_pdb(source)
        except Exception:
            return False
        atoms = rep["atoms"]
        for i in range(len(atoms)):
            for j in range(i + 1, len(atoms)):
                if _dist(atoms[i], atoms[j]) < _CLASH_THRESHOLD:
                    return False
        return True

    # -- features -----------------------------------------------------------

    def features(self, source: str) -> np.ndarray:
        """
        8-dimensional molecular feature basis:
        log atom count, max chain depth (residues), residue count, chain
        count, bond count, bond density, hetero-atom ratio, coherence.
        """
        try:
            rep = _parse_pdb(source)
            atoms = rep["atoms"]
            groups = _residue_groups(atoms)
            chains = {a["chain"] for a in atoms}
            bonds = _bonds(atoms)
            n = len(atoms)
            hetero = sum(1 for a in atoms if a["element"] not in ("C", "N", "O", "H"))
            return np.array(
                [
                    math.log1p(n),
                    float(len(groups)),
                    float(len(groups)),
                    float(len(chains)),
                    float(len(bonds)),
                    min(1.0, len(bonds) / max(1, n)),
                    hetero / max(1, n),
                    self.coherence(source),
                ],
                dtype=float,
            )
        except Exception:
            return np.zeros(8, dtype=float)

    # -- hooks --------------------------------------------------------------

    def normalize(self, source: str) -> str:
        try:
            rep = _parse_pdb(source)
            return _unparse_pdb(rep)
        except Exception:
            return source

    def sample_source(self) -> str:
        # Two compact tetra-atomic residues with a clean inter-residue bond.
        atoms = [
            (1, "N", "ALA", "A", 1, 0.0, 0.0, 0.0, "N"),
            (2, "CA", "ALA", "A", 1, 1.45, 0.0, 0.0, "C"),
            (3, "C", "ALA", "A", 1, 2.10, 1.30, 0.0, "C"),
            (4, "O", "ALA", "A", 1, 1.50, 2.40, 0.0, "O"),
            (5, "N", "GLY", "A", 2, 3.40, 1.35, 0.0, "N"),
            (6, "CA", "GLY", "A", 2, 4.15, 2.55, 0.0, "C"),
            (7, "C", "GLY", "A", 2, 5.60, 2.30, 0.0, "C"),
            (8, "O", "GLY", "A", 2, 6.20, 3.30, 0.0, "O"),
        ]
        lines = [
            "ATOM  {s:>5} {n:<4} {r:<3} {c}{rs:>4}    "
            "{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {e:>2}".format(
                s=s, n=n, r=r, c=c, rs=rs, x=x, y=y, z=z, e=e
            )
            for (s, n, r, c, rs, x, y, z, e) in atoms
        ]
        return "\n".join(lines) + "\nEND\n"
