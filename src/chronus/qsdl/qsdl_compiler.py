# qsdl_compiler.py
# Chronos GPU -- QSDL Compiler v3.0 (production pass, 4 Aug 2026)
#
# History:
#   v2.0 (3 Aug 2026, audit fix): fixed a hard SyntaxError and a missing
#   numpy import that had prevented the whole demo pipeline from even
#   importing, but compile() still ignored its qsdl_source argument
#   entirely and returned a fixed hardcoded demo scene regardless of input
#   -- explicitly documented at the time as "a real BNF-grammar parser is
#   future scope, not something this audit pass added."
#   v3.0 (this pass) adds that real parser. qsdl_parser.py tokenizes and
#   parses the full QSDL v1.0 BNF grammar (scene/manifold_decl/object_decl/
#   geometry_decl/material_decl/quantum_state_decl/transform_decl/
#   animation_decl/light_decl/camera_decl/readout_spec/quality_decl) from
#   the formal spec, and this module compiles the resulting AST into a real
#   QScene: geometry/material fields evaluated from parsed values, resonance
#   weights and hamiltonian/coupling terms evaluated from the quantum block,
#   transform blocks composed into real 4x4 matrices (translation, scale,
#   and Rodrigues-formula rotation), and camera/quality settings read
#   directly from the source.
#
# Backward-compatibility note (stated plainly, not hidden): two existing
# internal callers -- ChronosEngine.render(scene="default") and
# phi_scaling.py's `compiler.compile(f"phi_tier_{power}")` -- pass an
# opaque scene *label*, not QSDL source (these are pre-existing call sites,
# unchanged by this pass). Real QSDL source always starts with the `scene`
# keyword per the grammar; anything else is treated as a legacy label and
# resolved to the same fixed canonical scene the old stub always returned,
# so previously-measured/validated pipeline outputs (chronos_gpu_demo.py's
# baseline energy, the phi-power scaling benchmark) are reproduced exactly,
# byte-for-byte, rather than silently changing. Genuine `scene NAME { ... }`
# QSDL source (as chronos_gpu_demo.py now uses) is fully, really parsed.

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from .manifold import M32Manifold
from .qsdl_parser import (
    AnimationDecl,
    CameraDecl,
    Expr,
    LightDecl,
    ManifoldDecl,
    ObjectDecl,
    QSDLSyntaxError,
    QualityDecl,
    SceneAST,
    TransformOp,
    parse_qsdl,
)

_SCENE_KEYWORD_RE = re.compile(r"^\s*scene\b")

_MANIFOLD_TYPE_N_FACES = {"M32": 32, "M64": 64, "M128": 128, "M256": 256}

_DEFAULT_ADJACENCY_THRESHOLD = 0.70

_KNOWN_MATRIX_FUNCS = ("zero", "diagonal", "identity", "uniform")


class QSDLCompileError(Exception):
    pass


@dataclass
class ManifoldConfig:
    name: str = "M32"
    n_faces: int = 32
    adjacency_threshold: float = _DEFAULT_ADJACENCY_THRESHOLD


@dataclass
class QScene:
    manifold: ManifoldConfig
    objects: List[Dict] = field(default_factory=list)
    lights: List[Dict] = field(default_factory=list)
    camera: Dict = field(default_factory=dict)
    hamiltonian_terms: List[np.ndarray] = field(default_factory=list)
    readout_observables: List[str] = field(default_factory=list)
    quality: Dict = field(default_factory=dict)


class QSDLCompiler:
    def __init__(self, manifold: Optional[ManifoldConfig] = None):
        self.default_manifold = manifold or ManifoldConfig()

    def compile(self, qsdl_source: str) -> QScene:
        if not _SCENE_KEYWORD_RE.match(qsdl_source):
            # Legacy/non-QSDL label -- see module docstring.
            return self._default_scene()
        ast = parse_qsdl(qsdl_source)
        return self._compile_ast(ast)

    # -- default/legacy scene -------------------------------------------------
    def _default_scene(self) -> QScene:
        """Numerically identical, field for field, to the v1.0/v2.0 hardcoded
        stub scene, so existing callers that never passed real QSDL syntax
        keep getting the same validated numbers."""
        n = self.default_manifold.n_faces
        scene = QScene(manifold=self.default_manifold)
        scene.objects.append(
            {
                "name": "sphere_0",
                "geometry": {"type": "sphere", "radius": 1.0, "center": (0, 0, 0)},
                "material": {
                    "dielectric": 1.5,
                    "absorption": 0.001,
                    "resonance_weights": np.full(n, 0.5),
                },
                "transform": np.eye(4),
            }
        )
        scene.lights.append(
            {
                "name": "sun",
                "type": "directional",
                "direction": (1, 1, 1),
                "position": (1, 1, 1),
                "intensity": 1.0,
                "driving_term": np.zeros((n, n)),
            }
        )
        scene.camera = {
            "resolution": (7680, 4320),
            "fov": 60.0,
            "position": (0, 0, 5),
            "readout": ["intensity", "depth", "normal"],
        }
        scene.readout_observables = ["intensity", "depth", "normal"]
        scene.quality = {
            "layers": 4,
            "steps": 80,
            "learning_rate": 0.08,
            "damping": 1e-2,
            "seed": 0,
        }
        scene.hamiltonian_terms = self._build_initial_hamiltonian(scene)
        return scene

    # -- real QSDL AST -> QScene -----------------------------------------------
    def _compile_ast(self, ast: SceneAST) -> QScene:
        manifold_cfg = self._compile_manifold(ast.manifold)
        base_manifold = M32Manifold(n=manifold_cfg.n_faces)
        adjacency = base_manifold.adjacency
        if abs(manifold_cfg.adjacency_threshold - _DEFAULT_ADJACENCY_THRESHOLD) > 1e-12:
            sims = base_manifold.face_positions @ base_manifold.face_positions.T
            adjacency = (sims >= manifold_cfg.adjacency_threshold).astype(np.float64)
            np.fill_diagonal(adjacency, 0.0)

        scene = QScene(manifold=manifold_cfg)
        for obj_ast in ast.objects:
            scene.objects.append(
                self._compile_object(obj_ast, manifold_cfg.n_faces, adjacency)
            )
        for light_ast in ast.lights:
            scene.lights.append(
                self._compile_light(light_ast, manifold_cfg.n_faces, adjacency)
            )

        if ast.camera is not None:
            scene.camera = self._compile_camera(ast.camera)
            scene.readout_observables = list(scene.camera.get("readout", []))
        else:
            # The grammar's camera_decl is not bracketed as optional, but a
            # missing camera on an otherwise-valid scene is tolerated here
            # (rather than hard-failing) using the same default camera the
            # canonical scene uses.
            scene.camera = {
                "resolution": (7680, 4320),
                "fov": 60.0,
                "position": (0, 0, 5),
                "readout": ["intensity", "depth", "normal"],
            }
            scene.readout_observables = ["intensity", "depth", "normal"]

        scene.quality = (
            self._compile_quality(ast.quality)
            if ast.quality is not None
            else {
                "layers": 4,
                "steps": 60,
                "learning_rate": 0.1,
                "damping": 1e-2,
                "seed": 0,
            }
        )
        scene.hamiltonian_terms = self._build_initial_hamiltonian(scene)
        return scene

    def _compile_manifold(self, decl: Optional[ManifoldDecl]) -> ManifoldConfig:
        if decl is None:
            return ManifoldConfig(
                name=self.default_manifold.name,
                n_faces=self.default_manifold.n_faces,
                adjacency_threshold=self.default_manifold.adjacency_threshold,
            )
        if decl.manifold_type == "custom":
            name = decl.custom_name or "custom"
            n_faces = (
                int(self._eval_number(decl.params["n_faces"]))
                if "n_faces" in decl.params
                else self.default_manifold.n_faces
            )
        else:
            name = decl.manifold_type
            n_faces = _MANIFOLD_TYPE_N_FACES[decl.manifold_type]
        threshold = (
            self._eval_number(decl.params["adjacency_threshold"])
            if "adjacency_threshold" in decl.params
            else _DEFAULT_ADJACENCY_THRESHOLD
        )
        return ManifoldConfig(name=name, n_faces=n_faces, adjacency_threshold=threshold)

    def _compile_object(
        self, obj_ast: ObjectDecl, n_faces: int, adjacency: np.ndarray
    ) -> Dict:
        assert (
            obj_ast.geometry is not None and obj_ast.material is not None
        )  # enforced by the parser

        geometry: Dict = {"type": obj_ast.geometry.geometry_type}
        for key, val_expr in obj_ast.geometry.params.items():
            geometry[key] = self._eval_value(val_expr)

        material: Dict = {"name": obj_ast.material.name}
        for key, val_expr in obj_ast.material.properties.items():
            material[key] = self._eval_value(val_expr)
        material.setdefault("dielectric", 1.5)
        material.setdefault("absorption", 0.001)

        if obj_ast.material.quantum is not None:
            q = obj_ast.material.quantum
            material["resonance_weights"] = (
                self._eval_resonance_list(q.resonance, n_faces)
                if q.resonance is not None
                else np.full(n_faces, 0.5)
            )
            if q.hamiltonian is not None:
                material["hamiltonian_term"] = self._eval_matrix_expr(
                    q.hamiltonian, n_faces, adjacency
                )
            if q.coupling is not None:
                material["coupling_term"] = self._eval_matrix_expr(
                    q.coupling, n_faces, adjacency
                )
        else:
            material["resonance_weights"] = np.full(n_faces, 0.5)

        transform = np.eye(4)
        for op in obj_ast.transform:
            transform = self._transform_op_matrix(op) @ transform

        result: Dict = {
            "name": obj_ast.name,
            "geometry": geometry,
            "material": material,
            "transform": transform,
        }
        if obj_ast.animation is not None:
            result["animation"] = self._compile_animation(obj_ast.animation)
        return result

    def _compile_animation(self, anim: AnimationDecl) -> Dict:
        return {
            "property": anim.property_name,
            "keyframes": [
                (self._eval_number(t), self._eval_number(v)) for t, v in anim.keyframes
            ],
        }

    def _transform_op_matrix(self, op: TransformOp) -> np.ndarray:
        """Composes one transform_op into a real 4x4 homogeneous matrix.

        Concrete-syntax note: the grammar writes `translate '(' vec3 ')'`
        and `vec3 ::= '(' v ',' v ',' v ')'`, which read literally would
        require doubled parens (`translate((x,y,z))`). Every real 3D scene
        language instead writes `translate(x, y, z)` with the vec3's three
        components as the call's flat argument list, which is what this
        compiler (and qsdl_parser's transform_op parsing) accepts. `rotate`
        keeps the vec3 axis visually distinct from the scalar angle, so it
        is written `rotate((x,y,z), angle)` with the axis genuinely
        parenthesized as its own vec3.
        """
        m = np.eye(4)
        if op.op == "translate":
            tx, ty, tz = [self._eval_number(a) for a in op.args]
            m[0, 3], m[1, 3], m[2, 3] = tx, ty, tz
        elif op.op == "scale":
            sx, sy, sz = [self._eval_number(a) for a in op.args]
            m[0, 0], m[1, 1], m[2, 2] = sx, sy, sz
        elif op.op == "rotate":
            if len(op.args) != 2:
                raise QSDLCompileError(
                    "rotate(...) requires exactly (axis vec3, angle_degrees)"
                )
            axis_expr, angle_expr = op.args
            axis = np.array(self._eval_value(axis_expr), dtype=np.float64)
            norm = float(np.linalg.norm(axis))
            if norm < 1e-12:
                raise QSDLCompileError("rotate(...) axis must be non-zero")
            axis = axis / norm
            angle = math.radians(self._eval_number(angle_expr))
            kx, ky, kz = axis
            k_cross = np.array([[0.0, -kz, ky], [kz, 0.0, -kx], [-ky, kx, 0.0]])
            # Rodrigues' rotation formula: R = I + sin(t) K + (1-cos(t)) K^2
            rot3 = (
                np.eye(3)
                + math.sin(angle) * k_cross
                + (1.0 - math.cos(angle)) * (k_cross @ k_cross)
            )
            m[:3, :3] = rot3
        else:
            raise QSDLCompileError(f"Unknown transform op {op.op!r}")
        return m

    def _compile_light(
        self, light_ast: LightDecl, n_faces: int, adjacency: np.ndarray
    ) -> Dict:
        light_type = light_ast.light_type or "directional"
        position = (
            tuple(float(v) for v in self._eval_value(light_ast.position))
            if light_ast.position is not None
            else (1.0, 1.0, 1.0)
        )
        intensity = (
            self._eval_number(light_ast.intensity)
            if light_ast.intensity is not None
            else 1.0
        )
        result: Dict = {
            "name": light_ast.name,
            "type": light_type,
            # HamiltonianLibrary.light_to_driving reads "direction"; for a
            # directional light the grammar's `position` vec3 *is* the
            # direction (a directional light has no meaningful position).
            "direction": position,
            "position": position,
            "intensity": intensity,
        }
        if light_ast.spectrum is not None:
            result["spectrum"] = self._eval_value(light_ast.spectrum)
        result["driving_term"] = (
            self._eval_matrix_expr(light_ast.driving, n_faces, adjacency)
            if light_ast.driving is not None
            else np.zeros((n_faces, n_faces))
        )
        return result

    def _compile_camera(self, cam_ast: CameraDecl) -> Dict:
        result: Dict = {}
        if cam_ast.resolution is not None:
            w, h = self._eval_value(cam_ast.resolution)
            result["resolution"] = (int(w), int(h))
        else:
            result["resolution"] = (7680, 4320)
        result["fov"] = (
            self._eval_number(cam_ast.fov) if cam_ast.fov is not None else 60.0
        )
        result["position"] = (
            tuple(float(v) for v in self._eval_value(cam_ast.position))
            if cam_ast.position is not None
            else (0.0, 0.0, 5.0)
        )
        if cam_ast.look_at is not None:
            result["look_at"] = tuple(
                float(v) for v in self._eval_value(cam_ast.look_at)
            )
        if cam_ast.up is not None:
            result["up"] = tuple(float(v) for v in self._eval_value(cam_ast.up))
        if cam_ast.readout is not None:
            result["readout"] = list(cam_ast.readout.observables) or [
                "intensity",
                "depth",
                "normal",
            ]
            if cam_ast.readout.supersampling is not None:
                result["supersampling"] = self._eval_number(
                    cam_ast.readout.supersampling
                )
            if cam_ast.readout.tone_map is not None:
                result["tone_map"] = cam_ast.readout.tone_map
        else:
            result["readout"] = ["intensity", "depth", "normal"]
        return result

    def _compile_quality(self, q_ast: QualityDecl) -> Dict:
        result = {
            "layers": q_ast.layers if q_ast.layers is not None else 4,
            "steps": q_ast.evolution_steps if q_ast.evolution_steps is not None else 60,
            "learning_rate": (
                q_ast.learning_rate if q_ast.learning_rate is not None else 0.1
            ),
            "damping": q_ast.damping if q_ast.damping is not None else 1e-2,
            "seed": q_ast.seed if q_ast.seed is not None else 0,
        }
        if q_ast.reconstruction_threshold is not None:
            result["reconstruction_threshold"] = q_ast.reconstruction_threshold
        return result

    # -- expression evaluation --------------------------------------------------
    def _eval_number(self, expr: Expr) -> float:
        if expr.kind == "number":
            return float(expr.number)
        raise QSDLCompileError(
            f"Expected a numeric value, got expression of kind {expr.kind!r}"
        )

    def _eval_value(self, expr: Expr):
        """Evaluates a general `value`/`expression` node to a plain Python
        value: float, str (bare IDENT), tuple (vec), list (value_list), or
        {"function": name, "args": [...]} for an unevaluated function call
        (e.g. a procedural geometry or custom spectrum expression that has
        no fixed numeric meaning at the QSDL layer)."""
        if expr.kind == "number":
            return expr.number
        if expr.kind == "ident":
            return expr.ident
        if expr.kind == "vec":
            return tuple(self._eval_value(it) for it in expr.items)
        if expr.kind == "list":
            return [self._eval_value(it) for it in expr.items]
        if expr.kind == "call":
            return {
                "function": expr.call_name,
                "args": [self._eval_value(a) for a in expr.call_args],
            }
        raise QSDLCompileError(f"Cannot evaluate expression of kind {expr.kind!r}")

    def _eval_resonance_list(self, expr: Expr, n_faces: int) -> np.ndarray:
        values = [self._eval_number(it) for it in expr.items]
        if len(values) == 1:
            return np.full(n_faces, values[0])
        if len(values) == n_faces:
            return np.array(values, dtype=np.float64)
        raise QSDLCompileError(
            f"resonance value_list must have length 1 (broadcast to every face) or exactly "
            f"n_faces={n_faces}, got {len(values)}"
        )

    def _eval_matrix_expr(
        self, expr: Expr, n_faces: int, adjacency: np.ndarray
    ) -> np.ndarray:
        """Evaluates a hamiltonian_expr/coupling_expr/driving expression into
        a real (n_faces, n_faces) matrix. The grammar leaves these
        productions open-ended (no further BNF given); this compiler
        recognizes a small, fixed, documented vocabulary of function names
        and raises a clear QSDLCompileError for anything else, rather than
        silently ignoring unrecognized expressions."""
        if expr.kind == "number":
            return float(expr.number) * np.eye(n_faces)
        if expr.kind == "call":
            name = expr.call_name
            args = [self._eval_number(a) for a in expr.call_args]
            if name == "zero":
                return np.zeros((n_faces, n_faces))
            if name in ("diagonal", "identity"):
                value = args[0] if args else 1.0
                return value * np.eye(n_faces)
            if name == "uniform":
                # Design principle #3 of the spec: "Spectral adjacency
                # determines coupling structure" -- so a uniform coupling
                # value is applied over the manifold's real spectral
                # adjacency graph, not a dense all-to-all matrix.
                value = args[0] if args else 1.0
                return value * adjacency
            raise QSDLCompileError(
                f"Unknown quantum expression function {name!r}(...); this compiler recognizes "
                f"{_KNOWN_MATRIX_FUNCS} for hamiltonian/coupling/driving fields."
            )
        raise QSDLCompileError(
            f"Expected a hamiltonian/coupling-style expression (number or function call), got {expr.kind!r}"
        )

    # -- optional aggregate Hamiltonian (not consumed by the main render
    # pipeline, which builds its own real Hamiltonian in hamiltonian.py from
    # scene.objects/scene.lights directly; kept for callers that want the
    # quantum-block-derived terms specifically) --------------------------------
    def _build_initial_hamiltonian(self, scene: QScene) -> List[np.ndarray]:
        terms: List[np.ndarray] = []
        for obj in scene.objects:
            mat = obj["material"]
            res = mat.get("resonance_weights")
            if res is not None:
                terms.append(-np.diag(res))
            if "hamiltonian_term" in mat:
                terms.append(mat["hamiltonian_term"])
            if "coupling_term" in mat:
                terms.append(mat["coupling_term"])
        n = scene.manifold.n_faces
        for light in scene.lights:
            terms.append(light.get("driving_term", np.zeros((n, n))))
        return terms


def _self_test() -> str:
    # 1. Legacy/non-QSDL labels must keep returning the exact canonical scene.
    legacy = QSDLCompiler().compile("default")
    assert legacy.manifold.n_faces == 32
    assert legacy.objects[0]["material"]["dielectric"] == 1.5
    assert legacy.quality["steps"] == 80

    legacy64 = QSDLCompiler(ManifoldConfig(n_faces=64)).compile("phi_tier_12")
    assert legacy64.manifold.n_faces == 64
    assert legacy64.objects[0]["material"]["resonance_weights"].shape == (64,)

    # 2. Real QSDL parsing of a full scene exercising every declaration kind.
    source = """
    scene demo {
        manifold M32
        object sphere_0 {
            geometry sphere(radius=1.0, center=(0,0,0))
            material glass {
                dielectric = 1.5
                absorption = 0.001
                quantum { resonance = [0.5] }
            }
            transform { translate(0,0,-2) scale(2,2,2) }
        }
        light sun {
            type = directional
            position = (1,1,1)
            intensity = 1.0
        }
        camera {
            resolution = (7680,4320)
            fov = 60.0
            position = (0,0,5)
            readout = { observables = [intensity, depth, normal] }
        }
        quality { layers = 4 evolution_steps = 80 learning_rate = 0.08 damping = 0.01 seed = 0 }
    }
    """
    scene = QSDLCompiler().compile(source)
    assert scene.manifold.n_faces == 32
    obj = scene.objects[0]
    assert obj["geometry"]["radius"] == 1.0
    assert np.allclose(obj["material"]["resonance_weights"], 0.5)
    assert obj["transform"].shape == (4, 4)
    assert not np.allclose(obj["transform"], np.eye(4))
    assert scene.lights[0]["direction"] == (1.0, 1.0, 1.0)
    assert scene.camera["resolution"] == (7680, 4320)
    assert isinstance(scene.camera["resolution"][0], int)
    assert scene.quality["steps"] == 80

    # 3. Real rotate() transform must actually rotate (Rodrigues formula).
    rot_source = """
    scene rot_test {
        object o {
            geometry sphere(radius=1.0)
            material m { dielectric = 1.5 }
            transform { rotate((0,0,1), 90) }
        }
        camera { resolution = (100,100) }
    }
    """
    rot_scene = QSDLCompiler().compile(rot_source)
    rot_m = rot_scene.objects[0]["transform"]
    v = rot_m @ np.array([1.0, 0.0, 0.0, 1.0])
    assert np.allclose(
        v[:3], [0.0, 1.0, 0.0], atol=1e-9
    ), f"90deg rotation about z of (1,0,0) should be (0,1,0), got {v[:3]}"

    # 4. The new chronos_gpu_demo.py QSDL source must compile to numerically
    #    identical objects/materials/camera/quality as the legacy canonical
    #    scene, so the demo's baseline numbers are reproduced exactly.
    demo_source = (
        "scene sunset {"
        "  manifold M32"
        "  object sphere { geometry sphere(radius=1.0, center=(0,0,0)) "
        "    material glass { dielectric=1.5 absorption=0.001 quantum { resonance=[0.5] } } }"
        "  light sun { type=directional position=(1,1,1) intensity=1.0 driving=zero() }"
        "  camera { resolution=(7680,4320) fov=60.0 position=(0,0,5) readout = { observables=[intensity,depth,normal] } }"
        "  quality { layers=4 evolution_steps=80 learning_rate=0.08 damping=0.01 seed=0 }"
        "}"
    )
    demo_scene = QSDLCompiler().compile(demo_source)
    assert demo_scene.manifold.n_faces == legacy.manifold.n_faces == 32
    assert np.array_equal(
        demo_scene.objects[0]["material"]["resonance_weights"],
        legacy.objects[0]["material"]["resonance_weights"],
    )
    assert (
        demo_scene.objects[0]["material"]["dielectric"]
        == legacy.objects[0]["material"]["dielectric"]
    )
    assert (
        demo_scene.objects[0]["material"]["absorption"]
        == legacy.objects[0]["material"]["absorption"]
    )
    assert demo_scene.objects[0]["geometry"] == legacy.objects[0]["geometry"]
    assert demo_scene.camera["resolution"] == legacy.camera["resolution"]
    assert demo_scene.quality["steps"] == legacy.quality["steps"]
    assert np.array_equal(
        demo_scene.lights[0]["driving_term"], legacy.lights[0]["driving_term"]
    )

    # 5. Malformed/incomplete QSDL must raise, not silently fall back.
    try:
        QSDLCompiler().compile("scene bad { object o { geometry sphere(radius=1.0) } }")
        raise AssertionError(
            "expected a parse error for an object missing its required material"
        )
    except (QSDLSyntaxError, QSDLCompileError):
        pass

    try:
        QSDLCompiler().compile(
            "scene bad2 { object o { geometry sphere(radius=1.0) material m { quantum { hamiltonian = not_a_real_function(1.0) } } } camera {} }"
        )
        raise AssertionError(
            "expected a compile error for an unrecognized hamiltonian function"
        )
    except QSDLCompileError:
        pass

    return "qsdl_compiler._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
