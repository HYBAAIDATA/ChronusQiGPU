"""AL HARAS orbital mesh model (HYBA Security): link-loss resilience on an exactly certified expander.

What is computed
----------------
* Topology. ``n`` satellites occupy vertices ``0 .. n-1`` of the Paley graph
  ``P(q)``, where ``q`` is the smallest prime with ``q = 1 (mod 4)`` and
  ``q >= n``; the other ``q - n`` vertices stay vacant. Two satellites share a
  laser link iff their labels differ by a non-zero square mod ``q``.
  ``expander.certify_paley(q)`` certifies ``P(q)`` exactly (strongly regular,
  Ramanujan, spectral gap ``(q - sqrt(q))/2``). When ``n < q`` the mesh is an
  induced subgraph of ``P(q)``: its degrees, connectivity and edge connectivity
  are computed on the mesh itself, and the certificate describes the host
  graph only. Consecutive labels differ by the square 1, so the mesh is always
  connected.
* Link loss. Jammed links are chosen deterministically (SHA-256 order, or a
  targeted cut around the lowest-degree satellite). Components, reachable
  pairs and hop counts are recomputed by breadth-first search. The exact edge
  connectivity ``lambda`` (Stoer-Wagner minimum cut) gives the worst-case
  statement: fewer than ``lambda`` jammed links can never disconnect the mesh;
  from ``lambda`` on, the outcome depends on which links are lost.
* Upsets. Synthetic telemetry frames are protected with Reed-Solomon
  RS(48, 32) over GF(257). The drill injects ``floor(flux * cross_section)``
  byte upsets per frame (an explicit drill assumption, not a device model) and
  reports what decoding corrected, verified by SHA-256.
* Packets. Bytes are written as a braid word over sigma_1, sigma_2 and their
  inverses (two bits per generator) that decodes exactly; the receiver checks
  the SHA-256 of what it decodes. For short packets the word is also compiled
  to its exact Z[zeta_5] matrix (``braids.py``) as an algebraic invariant;
  braid invariants neither prevent nor correct upsets.

Not implemented (named in older notes): an LPS Cayley graph on PSL_2(F_257) of
degree 258, delivery guarantees under a fixed share of lost links, radiation
immunity, Hecke-operator re-routing and instanton re-keying.
``LPSCayleyGraph``, ``LPSCayleyHop`` and ``construct_lps_cayley_graph`` are kept
as aliases for existing imports.
"""

import hashlib
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from chronus.security.al_haras import braids, expander, reed_solomon
from chronus.security.al_haras.cyclotomic import CyclotomicZ5
from chronus.security.al_haras.exact import display_number, fraction_str, sqrt_upper_bound, to_fraction

DEFAULT_PALEY_ORDER = 17
MAX_GRAPH_SATELLITES = 257
MAX_SIMULATED_SATELLITES = 128
MAX_DRILL_FRAMES = 8
MAX_FRAME_BYTES = 4096
MAX_INVARIANT_BYTES = 64
BRAID_SYMBOLS = ("sigma_1", "sigma_1^-1", "sigma_2", "sigma_2^-1")
_SYMBOL_VALUE = {g: i for i, g in enumerate(BRAID_SYMBOLS)}


def _elapsed_ms(start_ns: int) -> Any:
    """Measured wall-clock milliseconds since ``start_ns`` (``time.perf_counter_ns``)."""
    return display_number(Fraction(time.perf_counter_ns() - start_ns, 1_000_000))


def _floor(value: Fraction) -> int:
    return value.numerator // value.denominator


def is_paley_order(q: Any) -> bool:
    """True iff ``q`` is a prime with ``q = 1 (mod 4)`` (and ``q >= 5``)."""
    return isinstance(q, int) and not isinstance(q, bool) and q >= 5 and q % 4 == 1 and expander.is_prime(q)


def smallest_paley_order(n: int) -> int:
    """Smallest valid Paley order ``q >= max(n, 5)``."""
    q = max(5, n)
    while not is_paley_order(q):
        q += 1
    return q


# ------------------------------------------------------------------------------
# exact graph computations (adjacency as dict of sets)
# ------------------------------------------------------------------------------


def _components(nodes: Sequence[str], adj: Dict[str, Set[str]]) -> List[List[str]]:
    seen: Set[str] = set()
    comps: List[List[str]] = []
    for start in nodes:
        if start in seen:
            continue
        comp = [start]
        seen.add(start)
        queue = deque([start])
        while queue:
            u = queue.popleft()
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    comp.append(v)
                    queue.append(v)
        comps.append(comp)
    return comps


def _hop_statistics(nodes: Sequence[str], adj: Dict[str, Set[str]]) -> Dict[str, Any]:
    """All-pairs breadth-first search: reachable pairs, diameter and exact mean hop count."""
    total_hops = 0
    ordered_pairs = 0
    diameter = 0
    for s in nodes:
        dist = {s: 0}
        queue = deque([s])
        while queue:
            u = queue.popleft()
            for v in adj[u]:
                if v not in dist:
                    dist[v] = dist[u] + 1
                    queue.append(v)
        for t, d in dist.items():
            if t != s:
                total_hops += d
                ordered_pairs += 1
                diameter = max(diameter, d)
    return {
        "reachable_pairs": ordered_pairs // 2,
        "diameter_of_reachable_pairs": diameter,
        "mean_hops": Fraction(total_hops, ordered_pairs) if ordered_pairs else Fraction(0),
    }


def edge_connectivity(nodes: Sequence[str], adj: Dict[str, Set[str]]) -> int:
    """Exact global minimum edge cut (Stoer-Wagner) of a simple undirected graph; 0 if disconnected."""
    if len(nodes) < 2 or len(_components(nodes, adj)) > 1:
        return 0
    weights: Dict[str, Dict[str, int]] = {u: {v: 1 for v in adj[u]} for u in nodes}
    active = list(nodes)
    best: Optional[int] = None
    while len(active) > 1:
        start = active[0]
        order = [start]
        attach = {v: weights[start].get(v, 0) for v in active if v != start}
        cut_of_phase = 0
        while attach:
            nxt = max(attach, key=lambda v: attach[v])
            cut_of_phase = attach.pop(nxt)
            order.append(nxt)
            for v, w in weights[nxt].items():
                if v in attach:
                    attach[v] += w
        s, t = order[-2], order[-1]
        best = cut_of_phase if best is None else min(best, cut_of_phase)
        for v, w in weights[t].items():
            if v == s:
                continue
            weights[s][v] = weights[s].get(v, 0) + w
            weights[v][s] = weights[v].get(s, 0) + w
            del weights[v][t]
        weights[s].pop(t, None)
        del weights[t]
        active.remove(t)
    return best if best is not None else 0


def _paley_certificate(q: int) -> Dict[str, Any]:
    cert = expander.certify_paley(q)
    gap_lower = (Fraction(q) - sqrt_upper_bound(Fraction(q))) / 2
    return {
        "graph": cert["graph"],
        "order_q": q,
        "degree": cert["degree"],
        "srg_parameters": cert["srg_parameters"],
        "strongly_regular": cert["strongly_regular"],
        "is_ramanujan": cert["is_ramanujan"],
        "spectral_gap_exact": cert["spectral_gap_exact"],
        "spectral_gap_decimal": cert["spectral_gap_decimal"],
        "spectral_gap_lower_bound": gap_lower,
    }


# ------------------------------------------------------------------------------
# constellation model
# ------------------------------------------------------------------------------


class SatelliteOrbitClass(str, Enum):
    """Orbit labels; no orbit is propagated by this module."""

    LEO_TACTICAL = "LEO_TACTICAL"
    MEO_NAVIGATION = "MEO_NAVIGATION"
    GEO_STRATEGIC = "GEO_STRATEGIC"
    DEEP_SPACE_LUNAR = "DEEP_SPACE_LUNAR"


@dataclass
class SatelliteNode:
    """A satellite of the modelled constellation.

    ``position_km`` is optional and unused by the computations (no orbital
    mechanics are modelled). ``braid_state`` is kept for existing callers and
    is not used by the resilience computation.
    """

    sat_id: str
    orbit: SatelliteOrbitClass = SatelliteOrbitClass.LEO_TACTICAL
    position_km: Optional[Tuple[Any, Any, Any]] = None
    braid_state: CyclotomicZ5 = field(default_factory=lambda: CyclotomicZ5(1, 0, 0, 0))
    laser_cross_links: List[str] = field(default_factory=list)
    seu_events_detected: int = 0
    jamming_detected: bool = False
    active: bool = True


class OrbitalConstellationMesh:
    """Satellites and laser links, with exact link-loss and upset-drill analysis."""

    def __init__(self, constellation_name: str = "REFERENCE_CONSTELLATION") -> None:
        self.constellation_name = constellation_name
        self.satellites: Dict[str, SatelliteNode] = {}
        self.links: List[Tuple[str, str]] = []
        self.host_paley_order: Optional[int] = None
        self._total_telemetry_cycles = 0

    def add_satellite(self, node: SatelliteNode) -> None:
        self.satellites[node.sat_id] = node

    def add_laser_link(self, sat_a: str, sat_b: str) -> bool:
        """Add an undirected link; unknown satellites, self-links and duplicates are ignored."""
        if sat_a not in self.satellites or sat_b not in self.satellites or sat_a == sat_b:
            return False
        if sat_b in self.satellites[sat_a].laser_cross_links:
            return False
        self.links.append((sat_a, sat_b))
        self.satellites[sat_a].laser_cross_links.append(sat_b)
        self.satellites[sat_b].laser_cross_links.append(sat_a)
        return True

    @classmethod
    def create_reference_constellation(cls, num_satellites: int = 16) -> "OrbitalConstellationMesh":
        """``num_satellites`` satellites on the first vertices of the smallest fitting Paley graph."""
        if isinstance(num_satellites, bool) or not isinstance(num_satellites, int):
            raise ValueError("num_satellites must be an integer")
        if not 2 <= num_satellites <= MAX_SIMULATED_SATELLITES:
            raise ValueError(f"num_satellites must be between 2 and {MAX_SIMULATED_SATELLITES}")
        q = smallest_paley_order(num_satellites)
        mesh = cls(constellation_name=f"REFERENCE_CONSTELLATION_{num_satellites}_ON_PALEY_{q}")
        mesh.host_paley_order = q
        names = [f"SAT_{i:02d}" for i in range(num_satellites)]
        for name in names:
            mesh.add_satellite(SatelliteNode(sat_id=name))
        nbrs = expander.paley_neighbours(q)
        for i in range(num_satellites):
            for j in sorted(nbrs[i]):
                if i < j < num_satellites:
                    mesh.add_laser_link(names[i], names[j])
        return mesh

    # -------------------------------------------------------------- analysis
    def _adjacency(self) -> Tuple[List[str], Dict[str, Set[str]], List[Tuple[str, str]]]:
        names = list(self.satellites)
        adj: Dict[str, Set[str]] = {name: set() for name in names}
        links: List[Tuple[str, str]] = []
        for a, b in self.links:
            if a in adj and b in adj and a != b and b not in adj[a]:
                adj[a].add(b)
                adj[b].add(a)
                links.append((a, b))
        return names, adj, links

    @staticmethod
    def _jam_order(
        names: List[str], adj: Dict[str, Set[str]], links: List[Tuple[str, str]], strategy: str, seed: bytes
    ) -> List[Tuple[str, str]]:
        hashed = sorted(links, key=lambda link: hashlib.sha256(seed + f"{link[0]}|{link[1]}".encode("utf-8")).digest())
        if strategy == "hashed":
            return hashed
        position = {name: i for i, name in enumerate(names)}
        target = min(names, key=lambda name: (len(adj[name]), position[name]))
        return [link for link in hashed if target in link] + [link for link in hashed if target not in link]

    def _seu_drill(self, names: List[str], upsets: int, frame_bytes: int, seed: bytes) -> Dict[str, Any]:
        drilled = names[:MAX_DRILL_FRAMES]
        per_frame = []
        recovered = 0
        corrected_total = 0
        for sat in drilled:
            label = f"{self.constellation_name}|{sat}|cycle={self._total_telemetry_cycles}".encode("utf-8")
            frame = hashlib.shake_256(seed + label).digest(frame_bytes)
            envelope = reed_solomon.protect(frame)
            positions = reed_solomon.deterministic_fault_positions(frame, upsets)
            outcome = reed_solomon.heal(reed_solomon.inject_faults(frame, positions), envelope)
            corrected = len(outcome["corrected_data_positions"])
            self.satellites[sat].seu_events_detected += corrected
            corrected_total += corrected
            recovered += int(outcome["integrity_verified"])
            per_frame.append(
                {
                    "satellite": sat,
                    "upsets_injected": len(positions),
                    "symbols_corrected": corrected,
                    "uncorrectable_blocks": outcome["uncorrectable_blocks"],
                    "sha256_verified": outcome["integrity_verified"],
                }
            )
        return {
            "code": f"Reed-Solomon RS({reed_solomon.DEFAULT_N}, {reed_solomon.DEFAULT_K}) over GF(257)",
            "correctable_symbols_per_block": (reed_solomon.DEFAULT_N - reed_solomon.DEFAULT_K) // 2,
            "frame_bytes": frame_bytes,
            "frames_drilled": len(drilled),
            "frames_in_constellation": len(names),
            "upsets_per_frame": upsets,
            "upsets_injected": sum(item["upsets_injected"] for item in per_frame),
            "symbols_corrected": corrected_total,
            "frames_recovered": recovered,
            "frames_unrecovered": len(drilled) - recovered,
            "per_frame": per_frame,
        }

    def simulate_space_weather_and_jamming(
        self,
        radiation_flux_particles_cm2: Any = 10**5,
        anti_satellite_rf_jamming: bool = True,
        jammed_link_ratio: Any = Fraction(1, 4),
        seu_cross_section_cm2: Any = Fraction(1, 10**4),
        jamming_strategy: str = "hashed",
        seed: bytes = b"al-haras-orbital",
        frame_bytes: int = 64,
    ) -> Dict[str, Any]:
        """Jam a share of the links and run an upset drill; every result is recomputed from the mesh.

        ``jammed_link_ratio`` in [0, 1] selects ``floor(ratio * links)`` links
        (``jamming_strategy`` ``"hashed"`` or ``"targeted"``). The upset drill
        injects ``floor(radiation_flux_particles_cm2 * seu_cross_section_cm2)``
        byte upsets into each drilled frame (at most ``MAX_DRILL_FRAMES``
        satellites); the cross-section is a drill parameter, not a device value.
        """
        t0 = time.perf_counter_ns()
        flux = to_fraction(radiation_flux_particles_cm2)
        cross_section = to_fraction(seu_cross_section_cm2)
        ratio = to_fraction(jammed_link_ratio)
        if flux < 0 or cross_section < 0:
            raise ValueError("radiation flux and cross-section must be non-negative")
        if not 0 <= ratio <= 1:
            raise ValueError("jammed_link_ratio must be between 0 and 1")
        if jamming_strategy not in ("hashed", "targeted"):
            raise ValueError("jamming_strategy must be 'hashed' or 'targeted'")
        if isinstance(frame_bytes, bool) or not isinstance(frame_bytes, int) or not 1 <= frame_bytes <= MAX_FRAME_BYTES:
            raise ValueError(f"frame_bytes must be between 1 and {MAX_FRAME_BYTES}")
        names, adj, links = self._adjacency()
        if not 2 <= len(names) <= MAX_SIMULATED_SATELLITES:
            raise ValueError(f"the mesh must have between 2 and {MAX_SIMULATED_SATELLITES} satellites")
        self._total_telemetry_cycles += 1
        n = len(names)
        total_pairs = n * (n - 1) // 2

        degrees = [len(adj[name]) for name in names]
        lam = edge_connectivity(names, adj)
        before = _hop_statistics(names, adj)

        jam_count = _floor(ratio * len(links)) if anti_satellite_rf_jamming else 0
        jammed = self._jam_order(names, adj, links, jamming_strategy, seed)[:jam_count]
        surviving: Dict[str, Set[str]] = {name: set(adj[name]) for name in names}
        for a, b in jammed:
            surviving[a].discard(b)
            surviving[b].discard(a)
        touched = {sat for link in jammed for sat in link}
        for name in names:
            self.satellites[name].jamming_detected = name in touched
        comps = _components(names, surviving)
        after = _hop_statistics(names, surviving)
        connected = len(comps) == 1

        upsets = min(_floor(flux * cross_section), frame_bytes)
        drill = self._seu_drill(names, upsets, frame_bytes, seed)

        topology: Dict[str, Any] = {
            "model": "Paley-graph mesh" if self.host_paley_order else "caller-defined links",
            "satellites": n,
            "laser_links": len(links),
            "degree_min": min(degrees),
            "degree_max": max(degrees),
            "connected": before["reachable_pairs"] == total_pairs,
            "diameter": before["diameter_of_reachable_pairs"],
            "mean_hops": fraction_str(before["mean_hops"]),
            "edge_connectivity": lam,
            "edge_connectivity_method": "Stoer-Wagner minimum cut (exact, integer weights)",
        }
        if self.host_paley_order:
            cert = _paley_certificate(self.host_paley_order)
            topology["host_graph"] = {k: v for k, v in cert.items() if k != "spectral_gap_lower_bound"}
            topology["vacant_host_vertices"] = self.host_paley_order - n
            topology["certificate_scope"] = (
                "the spectrum certified is that of the host P(q); with vacant vertices the mesh is an "
                "induced subgraph whose properties are the computed values above"
            )

        guaranteed = jam_count < lam
        return {
            "constellation": self.constellation_name,
            "total_satellites": n,
            "total_laser_links": len(links),
            "severed_jammed_links": len(jammed),
            "active_laser_links": len(links) - len(jammed),
            "topology": topology,
            "jamming": {
                "enabled": bool(anti_satellite_rf_jamming),
                "ratio": fraction_str(ratio),
                "strategy": jamming_strategy,
                "seed_sha256": hashlib.sha256(seed).hexdigest(),
                "jammed_links": [list(link) for link in jammed],
            },
            "after_jamming": {
                "connected": connected,
                "components": len(comps),
                "largest_component": max(len(c) for c in comps),
                "isolated_satellites": [name for name in names if not surviving[name]],
                "reachable_pairs": after["reachable_pairs"],
                "total_pairs": total_pairs,
                "diameter_of_reachable_pairs": after["diameter_of_reachable_pairs"],
                "mean_hops_of_reachable_pairs": fraction_str(after["mean_hops"]),
            },
            "worst_case_guarantee": {
                "edge_connectivity": lam,
                "jammed_links": len(jammed),
                "connected_for_every_choice_of_this_many_links": guaranteed,
                "statement": f"any {lam - 1} or fewer jammed links leave the mesh connected; "
                f"{lam} well-chosen links can isolate a satellite",
            },
            "seu_drill": drill,
            "all_pairs_reachable_after_jamming": connected,
            "constellation_resilience_status": "ALL_SATELLITES_REACHABLE" if connected else "PARTITIONED",
            "simulation_latency_ms": _elapsed_ms(t0),
            "not_modelled": [
                "orbital mechanics, link budgets and radio-frequency propagation",
                "physical upset rates (the cross-section is a drill parameter)",
            ],
        }


# ==============================================================================
# PACKET ENCODING AND DELIVERY OVER THE PALEY MESH
# ==============================================================================


class Status(str, Enum):
    DELIVERED = "DELIVERED"  # planned shortest route had no jammed or occluded hop
    ZERO_STALL_DELIVERED = "DELIVERED"  # legacy alias of DELIVERED; no queueing or stall model exists
    JAMMED_RE_ROUTED = "JAMMED_RE_ROUTED"  # planned route blocked; delivered on a shortest surviving route
    UNREACHABLE = "UNREACHABLE"  # no surviving route; nothing delivered
    DEGRADED = "DEGRADED"  # delivered, but the receiver's SHA-256 check failed


@dataclass
class CyclotomicBraidKnot:
    """A packet written as a braid word.

    ``z5_phase`` holds the trace of the compiled Z[zeta_5] braid matrix (a
    conjugation invariant of the braid) when the packet is at most
    ``MAX_INVARIANT_BYTES`` long, else ``None``; the field name is kept for
    existing callers. ``invariants_coherent`` records the exact checks run at
    encoding time (braid relations and decode round trip).
    """

    braid_word: List[str]
    z5_phase: Optional[CyclotomicZ5]
    payload_hash: str
    invariants_coherent: bool = True
    payload_length: int = 0
    matrix_z5: Optional[List[List[List[int]]]] = None


_RELATIONS_OK: Optional[bool] = None


def _braid_relations_hold() -> bool:
    global _RELATIONS_OK
    if _RELATIONS_OK is None:
        _RELATIONS_OK = all(braids.verify_relations().values())
    return _RELATIONS_OK


def _trace(matrix: List[List[List[int]]]) -> CyclotomicZ5:
    return CyclotomicZ5.from_coeffs(matrix[0][0]) + CyclotomicZ5.from_coeffs(matrix[1][1])


def decode_cyclotomic_braid(knot: Any) -> bytes:
    """Exact inverse of ``encode_cyclotomic_braid`` (accepts a knot or a braid word)."""
    word = knot.braid_word if isinstance(knot, CyclotomicBraidKnot) else list(knot)
    if len(word) % 4:
        raise ValueError("braid word length must be a multiple of 4 (four generators per byte)")
    out = bytearray()
    for i in range(0, len(word), 4):
        value = 0
        for generator in word[i:i + 4]:
            if generator not in _SYMBOL_VALUE:
                raise ValueError(f"unknown braid generator {generator!r}")
            value = (value << 2) | _SYMBOL_VALUE[generator]
        out.append(value)
    return bytes(out)


def encode_cyclotomic_braid(packet_bytes: bytes) -> CyclotomicBraidKnot:
    """Write ``packet_bytes`` as a braid word, two bits per generator (most significant pair first)."""
    data = bytes(packet_bytes)
    word = [BRAID_SYMBOLS[(byte >> shift) & 3] for byte in data for shift in (6, 4, 2, 0)]
    matrix = None
    trace = None
    if len(data) <= MAX_INVARIANT_BYTES:
        matrix = braids.compile_braid_word(word)["matrix_z5"]
        trace = _trace(matrix)
    knot = CyclotomicBraidKnot(
        braid_word=word,
        z5_phase=trace,
        payload_hash=hashlib.sha256(data).hexdigest(),
        payload_length=len(data),
        matrix_z5=matrix,
    )
    knot.invariants_coherent = _braid_relations_hold() and decode_cyclotomic_braid(knot) == data
    return knot


def verify_mac_lane_coherence(braid_state: CyclotomicBraidKnot) -> bool:
    """Exact checks on an encoded packet (name kept for existing callers).

    True iff (1) the braid representation satisfies its relations
    (``braids.verify_relations``), (2) the word decodes, has the recorded
    length, and its bytes hash to ``payload_hash``, and (3) when a compiled
    matrix is stored, recompiling the word reproduces it and its trace equals
    ``z5_phase``. The Mac Lane pentagon axiom is not checked.
    """
    if not _braid_relations_hold():
        return False
    try:
        data = decode_cyclotomic_braid(braid_state)
    except ValueError:
        return False
    if len(data) != braid_state.payload_length or hashlib.sha256(data).hexdigest() != braid_state.payload_hash:
        return False
    if braid_state.matrix_z5 is not None:
        recompiled = braids.compile_braid_word(braid_state.braid_word)["matrix_z5"]
        if recompiled != braid_state.matrix_z5 or braid_state.z5_phase != _trace(recompiled):
            return False
    return True


@dataclass
class LaserLinkHop:
    """One direction of a laser link; ``jammed`` / ``occluded`` make it unusable."""

    source: str
    target: str
    link_id: str
    jammed: bool = False
    occluded: bool = False
    transmitted_packets: List[str] = field(default_factory=list)

    def is_jammed_or_occluded(self) -> bool:
        return self.jammed or self.occluded

    def transmit(self, braid_state: CyclotomicBraidKnot) -> CyclotomicBraidKnot:
        """Record the packet hash and forward the packet unchanged."""
        self.transmitted_packets.append(braid_state.payload_hash)
        return braid_state


LPSCayleyHop = LaserLinkHop


class PaleyConstellationGraph:
    """Satellites on the vertices ``0 .. n-1`` of the Paley graph ``P(q)``.

    With ``nodes=None`` the graph is all of ``P(p)`` (default ``p = 17``). With
    ``nodes`` given, ``q`` is ``p`` if supplied, else the smallest valid order
    ``>= len(nodes)``. ``degree`` and ``spectral_gap`` describe the host ``P(q)``
    (``spectral_gap`` is a rational lower bound of ``(q - sqrt(q))/2`` within
    1e-9, shown as a number); ``degree_min`` / ``degree_max`` describe the mesh.
    """

    def __init__(self, p: Optional[int] = None, nodes: Optional[Sequence[str]] = None) -> None:
        if nodes is None:
            q = DEFAULT_PALEY_ORDER if p is None else p
            if not is_paley_order(q):
                raise ValueError("the Paley order must be a prime q = 1 (mod 4)")
            names = [f"SAT_{i:02d}" for i in range(q)]
        else:
            names = [str(name) for name in nodes]
            if not names:
                raise ValueError("at least one satellite is required")
            if len(set(names)) != len(names):
                raise ValueError("satellite names must be unique")
            q = smallest_paley_order(len(names)) if p is None else p
            if not is_paley_order(q) or q < len(names):
                raise ValueError("the Paley order must be a prime q = 1 (mod 4) with q >= the number of satellites")
        if len(names) > MAX_GRAPH_SATELLITES:
            raise ValueError(f"at most {MAX_GRAPH_SATELLITES} satellites are supported")
        self.q = q
        self.p = q
        self.nodes = names
        self.index = {name: i for i, name in enumerate(names)}
        n = len(names)
        nbrs = expander.paley_neighbours(q)
        self.adjacency: Dict[str, List[str]] = {
            names[i]: [names[j] for j in sorted(nbrs[i]) if j < n] for i in range(n)
        }
        self.links: List[Tuple[str, str]] = [
            (names[i], names[j]) for i in range(n) for j in sorted(nbrs[i]) if i < j < n
        ]
        self.hops: Dict[Tuple[str, str], LaserLinkHop] = {}
        for a, b in self.links:
            self.hops[(a, b)] = LaserLinkHop(source=a, target=b, link_id=f"laser_{a}_{b}")
            self.hops[(b, a)] = LaserLinkHop(source=b, target=a, link_id=f"laser_{b}_{a}")
        cert = _paley_certificate(q)
        self.certificate = {k: v for k, v in cert.items() if k != "spectral_gap_lower_bound"}
        self.degree = cert["degree"]
        self.spectral_gap_exact = cert["spectral_gap_exact"]
        self.spectral_gap_lower_bound: Fraction = cert["spectral_gap_lower_bound"]
        self.spectral_gap = display_number(self.spectral_gap_lower_bound)
        degrees = [len(self.adjacency[name]) for name in names]
        self.degree_min = min(degrees)
        self.degree_max = max(degrees)
        self.vacant_vertices = q - n

    def _require(self, *sats: str) -> None:
        for sat in sats:
            if sat not in self.index:
                raise ValueError(f"unknown satellite {sat!r}")

    def _route(self, source: str, target: str, avoid_unavailable: bool) -> Optional[List[LaserLinkHop]]:
        prev: Dict[str, Optional[str]] = {source: None}
        queue = deque([source])
        while queue and target not in prev:
            u = queue.popleft()
            for v in self.adjacency[u]:
                if v in prev:
                    continue
                if avoid_unavailable and self.hops[(u, v)].is_jammed_or_occluded():
                    continue
                prev[v] = u
                queue.append(v)
        if target not in prev:
            return None
        path = [target]
        while prev[path[-1]] is not None:
            path.append(prev[path[-1]])
        path.reverse()
        return [self.hops[(path[i], path[i + 1])] for i in range(len(path) - 1)]

    def compute_cayley_path(self, source_sat: str, target_sat: str) -> List[LaserLinkHop]:
        """Planned route: a shortest path of the full mesh, ignoring jamming (legacy name)."""
        self._require(source_sat, target_sat)
        route = self._route(source_sat, target_sat, avoid_unavailable=False)
        if route is None:
            raise ValueError("satellites are not connected")
        return route

    def shortest_path(self, source_sat: str, target_sat: str, avoid_unavailable: bool = True) -> Optional[List[LaserLinkHop]]:
        """Shortest route over usable hops, or ``None`` if the target is cut off."""
        self._require(source_sat, target_sat)
        return self._route(source_sat, target_sat, avoid_unavailable)


LPSCayleyGraph = PaleyConstellationGraph


def construct_lps_cayley_graph(p: Optional[int] = 257, nodes: Optional[List[str]] = None) -> PaleyConstellationGraph:
    """Build the Paley mesh (legacy name: no LPS Cayley graph is constructed)."""
    return PaleyConstellationGraph(p=p, nodes=nodes)


class OrbitalSatelliteDefenseMesh:
    """Packet delivery over a Paley-graph laser mesh (see the module docstring)."""

    def __init__(self, constellation_nodes: List[str]) -> None:
        self.nodes = list(constellation_nodes)
        self.expander_graph = PaleyConstellationGraph(p=None, nodes=self.nodes)
        self.last_transmission: Optional[Dict[str, Any]] = None

    def transmit_telemetry_packet(self, packet_bytes: bytes, source_sat: str, target_sat: str) -> Status:
        """Encode, route and deliver one packet; the returned status is computed from the routes taken.

        The details of the last call are kept in ``last_transmission``.
        """
        t0 = time.perf_counter_ns()
        graph = self.expander_graph
        graph._require(source_sat, target_sat)
        knot = encode_cyclotomic_braid(packet_bytes)
        if not verify_mac_lane_coherence(knot):
            raise RuntimeError("braid encoding failed its exact self-check")
        planned = graph.compute_cayley_path(source_sat, target_sat)
        blocked = [hop.link_id for hop in planned if hop.is_jammed_or_occluded()]
        if not blocked:
            route: Optional[List[LaserLinkHop]] = planned
            status = Status.DELIVERED
        else:
            route = graph.shortest_path(source_sat, target_sat, avoid_unavailable=True)
            status = Status.JAMMED_RE_ROUTED if route is not None else Status.UNREACHABLE
        receiver_ok: Optional[bool] = None
        if route is not None:
            in_flight = knot
            for hop in route:
                forwarded = hop.transmit(in_flight)
                in_flight = forwarded if forwarded is not None else in_flight
            try:
                received = decode_cyclotomic_braid(in_flight)
                receiver_ok = len(received) == knot.payload_length and (
                    hashlib.sha256(received).hexdigest() == knot.payload_hash
                )
            except ValueError:
                receiver_ok = False
            if not receiver_ok:
                status = Status.DEGRADED
        self.last_transmission = {
            "status": status.value,
            "source_sat": source_sat,
            "target_sat": target_sat,
            "packet_sha256": knot.payload_hash,
            "packet_bytes": knot.payload_length,
            "braid_word_length": len(knot.braid_word),
            "braid_trace_z5": list(knot.z5_phase.coeffs()) if knot.z5_phase is not None else None,
            "planned_route": [source_sat] + [hop.target for hop in planned],
            "jammed_or_occluded_on_planned_route": blocked,
            "route_taken": None if route is None else [source_sat] + [hop.target for hop in route],
            "hops": None if route is None else len(route),
            "receiver_sha256_verified": receiver_ok,
            "host_graph": f"P({graph.q})",
            "latency_ms": _elapsed_ms(t0),
        }
        return status


def link_summary(mesh: OrbitalSatelliteDefenseMesh) -> Dict[str, Any]:
    """JSON-friendly description of a transmit mesh (for API responses)."""
    graph = mesh.expander_graph
    return {
        "host_graph": graph.certificate,
        "satellites": len(graph.nodes),
        "laser_links": len(graph.links),
        "vacant_host_vertices": graph.vacant_vertices,
        "degree_min": graph.degree_min,
        "degree_max": graph.degree_max,
        "spectral_gap_lower_bound": fraction_str(graph.spectral_gap_lower_bound),
    }
