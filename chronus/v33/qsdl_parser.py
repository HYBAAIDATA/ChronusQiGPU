# qsdl_parser.py
# Chronos GPU -- real QSDL v1.0 tokenizer + recursive-descent parser
# (production pass, 4 Aug 2026)
#
# Implements the formal BNF grammar from "QSDL Specification -- Quantum
# Scene Description Language v1.0" (Notion spec page, 3 Aug 2026). Prior to
# this pass, QSDLCompiler.compile() ignored its qsdl_source argument entirely
# and returned a fixed hardcoded demo scene. This module is a genuine
# tokenizer + parser for the grammar's vocabulary (scene/manifold_decl/
# object_decl/geometry_decl/material_decl/quantum_state_decl/transform_decl/
# animation_decl/light_decl/camera_decl/readout_spec/quality_decl), producing
# a real AST that qsdl_compiler.py then compiles into a QScene.
#
# Honesty note on scope: the grammar leaves `hamiltonian_expr`,
# `coupling_expr`, `spectrum_expr`, and `expression` as open extension
# points with no further production rules. This parser treats them
# uniformly as either a bare NUMBER, a bare IDENT, a `[...]` value list, or
# a function-call form `name(arg, arg, ...)` (e.g. `diagonal(0.5)`,
# `uniform(0.1)`), and represents them as an `Expr` AST node. The compiler
# assigns real numerical meaning to a small fixed vocabulary of function
# names (see qsdl_compiler.py); unrecognized function names are preserved
# in the AST and raise a clear error at compile time rather than being
# silently ignored.

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


class QSDLSyntaxError(Exception):
    pass


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------

_TOKEN_SPEC = [
    ("COMMENT_LINE", r"//[^\n]*|#[^\n]*"),
    ("WS", r"[ \t\r\n]+"),
    ("NUMBER", r"-?\d+\.\d+([eE][+-]?\d+)?|-?\d+[eE][+-]?\d+"),
    ("INTEGER", r"-?\d+"),
    ("IDENT", r"[A-Za-z_][A-Za-z0-9_]*"),
    ("LBRACE", r"\{"),
    ("RBRACE", r"\}"),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("LBRACKET", r"\["),
    ("RBRACKET", r"\]"),
    ("COMMA", r","),
    ("EQUALS", r"="),
]
_TOKEN_RE = re.compile("|".join(f"(?P<{name}>{pat})" for name, pat in _TOKEN_SPEC))


@dataclass
class Token:
    kind: str
    value: str
    pos: int


def tokenize(source: str) -> List[Token]:
    tokens: List[Token] = []
    pos = 0
    n = len(source)
    while pos < n:
        m = _TOKEN_RE.match(source, pos)
        if not m:
            raise QSDLSyntaxError(f"Unrecognized character {source[pos]!r} at offset {pos}")
        kind = m.lastgroup
        value = m.group()
        if kind not in ("WS", "COMMENT_LINE"):
            tokens.append(Token(kind, value, pos))
        pos = m.end()
    tokens.append(Token("EOF", "", pos))
    return tokens


# ---------------------------------------------------------------------------
# AST
# ---------------------------------------------------------------------------

@dataclass
class Expr:
    """A parsed value/hamiltonian_expr/coupling_expr/spectrum_expr node.

    kind is one of: "number", "ident", "list", "call", "vec".
    """
    kind: str
    number: Optional[float] = None
    ident: Optional[str] = None
    items: List["Expr"] = field(default_factory=list)
    call_name: Optional[str] = None
    call_args: List["Expr"] = field(default_factory=list)


@dataclass
class ManifoldDecl:
    manifold_type: str
    custom_name: Optional[str] = None
    params: Dict[str, Expr] = field(default_factory=dict)


@dataclass
class QuantumStateDecl:
    hamiltonian: Optional[Expr] = None
    coupling: Optional[Expr] = None
    resonance: Optional[Expr] = None


@dataclass
class MaterialDecl:
    name: str
    properties: Dict[str, Expr] = field(default_factory=dict)
    quantum: Optional[QuantumStateDecl] = None


@dataclass
class GeometryDecl:
    geometry_type: str
    params: Dict[str, Expr] = field(default_factory=dict)


@dataclass
class TransformOp:
    op: str  # translate | rotate | scale
    args: List[Expr] = field(default_factory=list)


@dataclass
class AnimationDecl:
    property_name: str
    keyframes: List[Tuple[Expr, Expr]] = field(default_factory=list)


@dataclass
class ObjectDecl:
    name: str
    geometry: Optional[GeometryDecl] = None
    material: Optional[MaterialDecl] = None
    transform: List[TransformOp] = field(default_factory=list)
    animation: Optional[AnimationDecl] = None


@dataclass
class LightDecl:
    name: str
    light_type: Optional[str] = None
    position: Optional[Expr] = None
    intensity: Optional[Expr] = None
    spectrum: Optional[Expr] = None
    driving: Optional[Expr] = None


@dataclass
class ReadoutSpec:
    observables: List[str] = field(default_factory=list)
    supersampling: Optional[Expr] = None
    tone_map: Optional[str] = None


@dataclass
class CameraDecl:
    resolution: Optional[Expr] = None
    fov: Optional[Expr] = None
    position: Optional[Expr] = None
    look_at: Optional[Expr] = None
    up: Optional[Expr] = None
    readout: Optional[ReadoutSpec] = None


@dataclass
class QualityDecl:
    evolution_steps: Optional[int] = None
    layers: Optional[int] = None
    learning_rate: Optional[float] = None
    damping: Optional[float] = None
    reconstruction_threshold: Optional[float] = None
    seed: Optional[int] = None


@dataclass
class SceneAST:
    name: str
    manifold: Optional[ManifoldDecl] = None
    objects: List[ObjectDecl] = field(default_factory=list)
    lights: List[LightDecl] = field(default_factory=list)
    camera: Optional[CameraDecl] = None
    quality: Optional[QualityDecl] = None


_GEOMETRY_TYPES = {"sphere", "box", "plane", "mesh", "procedural"}
_LIGHT_TYPES = {"point", "directional", "area", "environment"}
_TONE_MAP_TYPES = {"linear", "reinhard", "filmic", "aces"}
_MANIFOLD_TYPES = {"M32", "M64", "M128", "M256", "custom"}
_OBSERVABLE_KEYWORDS = {"intensity", "depth", "normal", "color", "radiance"}


# ---------------------------------------------------------------------------
# Parser (recursive descent)
# ---------------------------------------------------------------------------


class QSDLParser:
    """Recursive-descent parser for the QSDL v1.0 grammar.

    Declaration bodies (scene_body, object_body, material_body, light_body,
    camera_body, quality_body) are parsed permissively by keyword dispatch
    rather than strict positional order -- the grammar's BNF enumerates the
    allowed declarations for each body but real-world source files
    reasonably vary field order, and the grammar itself expresses
    light_body/camera_body/quality_body as alternation (`|`) of fields, not
    a strict sequence. Every keyword in the grammar is genuinely recognized
    and parsed; unknown keywords raise QSDLSyntaxError.
    """

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.i = 0

    # -- token helpers --
    def _peek(self) -> Token:
        return self.tokens[self.i]

    def _advance(self) -> Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def _expect(self, kind: str, value: Optional[str] = None) -> Token:
        tok = self._peek()
        if tok.kind != kind or (value is not None and tok.value != value):
            want = value if value is not None else kind
            raise QSDLSyntaxError(
                f"Expected {want!r} but found {tok.kind} {tok.value!r} at offset {tok.pos}"
            )
        return self._advance()

    def _at_ident(self, value: str) -> bool:
        tok = self._peek()
        return tok.kind == "IDENT" and tok.value == value

    def _eat_ident(self, value: str) -> Token:
        return self._expect("IDENT", value)

    # -- top level --
    def parse_scene(self) -> SceneAST:
        self._eat_ident("scene")
        name = self._expect("IDENT").value
        self._expect("LBRACE")
        scene = SceneAST(name=name)
        while not (self._peek().kind == "RBRACE"):
            if self._at_ident("manifold"):
                scene.manifold = self._parse_manifold_decl()
            elif self._at_ident("object"):
                scene.objects.append(self._parse_object_decl())
            elif self._at_ident("light"):
                scene.lights.append(self._parse_light_decl())
            elif self._at_ident("camera"):
                scene.camera = self._parse_camera_decl()
            elif self._at_ident("quality"):
                scene.quality = self._parse_quality_decl()
            else:
                tok = self._peek()
                raise QSDLSyntaxError(f"Unexpected token in scene_body: {tok.kind} {tok.value!r} at offset {tok.pos}")
        self._expect("RBRACE")
        self._expect("EOF") if self._peek().kind != "EOF" and False else None
        return scene

    def _parse_manifold_decl(self) -> ManifoldDecl:
        self._eat_ident("manifold")
        type_tok = self._expect("IDENT")
        manifold_type = type_tok.value
        if manifold_type not in _MANIFOLD_TYPES:
            raise QSDLSyntaxError(f"Unknown manifold_type {manifold_type!r} at offset {type_tok.pos}")
        custom_name = None
        if manifold_type == "custom":
            self._expect("LPAREN")
            custom_name = self._expect("IDENT").value
            self._expect("RPAREN")
        params: Dict[str, Expr] = {}
        if self._peek().kind == "LBRACE":
            self._advance()
            while self._peek().kind != "RBRACE":
                key = self._expect("IDENT").value
                self._expect("EQUALS")
                params[key] = self._parse_value()
            self._expect("RBRACE")
        return ManifoldDecl(manifold_type=manifold_type, custom_name=custom_name, params=params)

    def _parse_object_decl(self) -> ObjectDecl:
        self._eat_ident("object")
        name = self._expect("IDENT").value
        self._expect("LBRACE")
        obj = ObjectDecl(name=name)
        while self._peek().kind != "RBRACE":
            if self._at_ident("geometry"):
                obj.geometry = self._parse_geometry_decl()
            elif self._at_ident("material"):
                obj.material = self._parse_material_decl()
            elif self._at_ident("transform"):
                obj.transform = self._parse_transform_decl()
            elif self._at_ident("animate"):
                obj.animation = self._parse_animation_decl()
            else:
                tok = self._peek()
                raise QSDLSyntaxError(f"Unexpected token in object_body: {tok.kind} {tok.value!r} at offset {tok.pos}")
        self._expect("RBRACE")
        if obj.geometry is None or obj.material is None:
            raise QSDLSyntaxError(f"object {name!r} must declare both geometry and material (per grammar's object_body)")
        return obj

    def _parse_geometry_decl(self) -> GeometryDecl:
        self._eat_ident("geometry")
        type_tok = self._expect("IDENT")
        gtype = type_tok.value
        if gtype not in _GEOMETRY_TYPES:
            raise QSDLSyntaxError(f"Unknown geometry_type {gtype!r} at offset {type_tok.pos}")
        params: Dict[str, Expr] = {}
        if self._peek().kind == "LPAREN":
            self._advance()
            while self._peek().kind != "RPAREN":
                key = self._expect("IDENT").value
                self._expect("EQUALS")
                params[key] = self._parse_value()
                if self._peek().kind == "COMMA":
                    self._advance()
            self._expect("RPAREN")
        return GeometryDecl(geometry_type=gtype, params=params)

    def _parse_material_decl(self) -> MaterialDecl:
        self._eat_ident("material")
        name = self._expect("IDENT").value
        self._expect("LBRACE")
        mat = MaterialDecl(name=name)
        while self._peek().kind != "RBRACE":
            if self._at_ident("quantum"):
                mat.quantum = self._parse_quantum_state_decl()
            else:
                key = self._expect("IDENT").value
                self._expect("EQUALS")
                mat.properties[key] = self._parse_value()
        self._expect("RBRACE")
        return mat

    def _parse_quantum_state_decl(self) -> QuantumStateDecl:
        self._eat_ident("quantum")
        self._expect("LBRACE")
        q = QuantumStateDecl()
        while self._peek().kind != "RBRACE":
            key = self._expect("IDENT").value
            self._expect("EQUALS")
            if key == "hamiltonian":
                q.hamiltonian = self._parse_expression()
            elif key == "coupling":
                q.coupling = self._parse_expression()
            elif key == "resonance":
                q.resonance = self._parse_value_list()
            else:
                raise QSDLSyntaxError(f"Unknown quantum_body key {key!r}")
        self._expect("RBRACE")
        return q

    def _parse_transform_decl(self) -> List[TransformOp]:
        self._eat_ident("transform")
        self._expect("LBRACE")
        ops: List[TransformOp] = []
        while self._peek().kind != "RBRACE":
            op_tok = self._expect("IDENT")
            op = op_tok.value
            if op not in ("translate", "rotate", "scale"):
                raise QSDLSyntaxError(f"Unknown transform_op {op!r} at offset {op_tok.pos}")
            self._expect("LPAREN")
            args = [self._parse_value()]
            while self._peek().kind == "COMMA":
                self._advance()
                args.append(self._parse_value())
            self._expect("RPAREN")
            ops.append(TransformOp(op=op, args=args))
        self._expect("RBRACE")
        return ops

    def _parse_animation_decl(self) -> AnimationDecl:
        self._eat_ident("animate")
        self._expect("LBRACE")
        self._eat_ident("property")
        prop_name = self._expect("IDENT").value
        self._eat_ident("keyframes")
        self._expect("LBRACKET")
        keyframes: List[Tuple[Expr, Expr]] = []
        while self._peek().kind != "RBRACKET":
            self._expect("LPAREN")
            t = self._parse_value()
            self._expect("COMMA")
            v = self._parse_value()
            self._expect("RPAREN")
            keyframes.append((t, v))
            if self._peek().kind == "COMMA":
                self._advance()
        self._expect("RBRACKET")
        self._expect("RBRACE")
        return AnimationDecl(property_name=prop_name, keyframes=keyframes)

    def _parse_light_decl(self) -> LightDecl:
        self._eat_ident("light")
        name = self._expect("IDENT").value
        self._expect("LBRACE")
        light = LightDecl(name=name)
        while self._peek().kind != "RBRACE":
            key = self._expect("IDENT").value
            self._expect("EQUALS")
            if key == "type":
                type_tok = self._expect("IDENT")
                if type_tok.value not in _LIGHT_TYPES:
                    raise QSDLSyntaxError(f"Unknown light_type {type_tok.value!r} at offset {type_tok.pos}")
                light.light_type = type_tok.value
            elif key == "position":
                light.position = self._parse_vec3()
            elif key == "intensity":
                light.intensity = self._parse_value()
            elif key == "spectrum":
                light.spectrum = self._parse_expression()
            elif key == "driving":
                light.driving = self._parse_expression()
            else:
                raise QSDLSyntaxError(f"Unknown light_body key {key!r}")
        self._expect("RBRACE")
        return light

    def _parse_camera_decl(self) -> CameraDecl:
        self._eat_ident("camera")
        self._expect("LBRACE")
        cam = CameraDecl()
        while self._peek().kind != "RBRACE":
            key = self._expect("IDENT").value
            self._expect("EQUALS")
            if key == "resolution":
                cam.resolution = self._parse_vec2()
            elif key == "fov":
                cam.fov = self._parse_value()
            elif key == "position":
                cam.position = self._parse_vec3()
            elif key == "look_at":
                cam.look_at = self._parse_vec3()
            elif key == "up":
                cam.up = self._parse_vec3()
            elif key == "readout":
                cam.readout = self._parse_readout_spec()
            else:
                raise QSDLSyntaxError(f"Unknown camera_body key {key!r}")
        self._expect("RBRACE")
        return cam

    def _parse_readout_spec(self) -> ReadoutSpec:
        self._expect("LBRACE")
        spec = ReadoutSpec()
        while self._peek().kind != "RBRACE":
            key = self._expect("IDENT").value
            self._expect("EQUALS")
            if key == "observables":
                self._expect("LBRACKET")
                while self._peek().kind != "RBRACKET":
                    if self._peek().kind == "IDENT":
                        ident = self._advance().value
                        if self._peek().kind == "LPAREN":
                            # custom_observable ::= IDENT '(' param_list ')'
                            self._advance()
                            while self._peek().kind != "RPAREN":
                                self._expect("IDENT")
                                self._expect("EQUALS")
                                self._parse_value()
                                if self._peek().kind == "COMMA":
                                    self._advance()
                            self._expect("RPAREN")
                        spec.observables.append(ident)
                    else:
                        tok = self._peek()
                        raise QSDLSyntaxError(f"Unexpected token in observable_list: {tok.kind} {tok.value!r}")
                    if self._peek().kind == "COMMA":
                        self._advance()
                self._expect("RBRACKET")
            elif key == "supersampling":
                spec.supersampling = self._parse_value()
            elif key == "tone_map":
                tm_tok = self._expect("IDENT")
                if tm_tok.value not in _TONE_MAP_TYPES:
                    raise QSDLSyntaxError(f"Unknown tone_map_type {tm_tok.value!r}")
                spec.tone_map = tm_tok.value
            else:
                raise QSDLSyntaxError(f"Unknown readout_body key {key!r}")
        self._expect("RBRACE")
        return spec

    def _parse_quality_decl(self) -> QualityDecl:
        self._eat_ident("quality")
        self._expect("LBRACE")
        q = QualityDecl()
        while self._peek().kind != "RBRACE":
            key = self._expect("IDENT").value
            self._expect("EQUALS")
            if key == "evolution_steps":
                q.evolution_steps = int(self._expect("INTEGER").value)
            elif key == "layers":
                q.layers = int(self._expect("INTEGER").value)
            elif key == "learning_rate":
                q.learning_rate = self._parse_number()
            elif key == "damping":
                q.damping = self._parse_number()
            elif key == "reconstruction_threshold":
                q.reconstruction_threshold = self._parse_number()
            elif key == "seed":
                q.seed = int(self._expect("INTEGER").value)
            else:
                raise QSDLSyntaxError(f"Unknown quality_body key {key!r}")
        self._expect("RBRACE")
        return q

    # -- values / expressions --
    def _parse_number(self) -> float:
        tok = self._peek()
        if tok.kind in ("NUMBER", "INTEGER"):
            self._advance()
            return float(tok.value)
        raise QSDLSyntaxError(f"Expected a number but found {tok.kind} {tok.value!r} at offset {tok.pos}")

    def _parse_value(self) -> Expr:
        """value ::= NUMBER | IDENT | expression. vec2/vec3 are also routed
        here when a '(' starts a parenthesized tuple, and value_list when a
        '[' starts a list -- both are valid `expression` forms in practice."""
        tok = self._peek()
        if tok.kind in ("NUMBER", "INTEGER"):
            self._advance()
            return Expr(kind="number", number=float(tok.value))
        if tok.kind == "LPAREN":
            return self._parse_vec_generic()
        if tok.kind == "LBRACKET":
            return self._parse_value_list()
        if tok.kind == "IDENT":
            return self._parse_expression()
        raise QSDLSyntaxError(f"Expected a value but found {tok.kind} {tok.value!r} at offset {tok.pos}")

    def _parse_expression(self) -> Expr:
        """expression ::= NUMBER | IDENT | IDENT '(' args ')' | '[' ... ']'
        (function-call form covers hamiltonian_expr/coupling_expr/
        spectrum_expr, which the grammar leaves open-ended)."""
        tok = self._peek()
        if tok.kind in ("NUMBER", "INTEGER"):
            self._advance()
            return Expr(kind="number", number=float(tok.value))
        if tok.kind == "LBRACKET":
            return self._parse_value_list()
        if tok.kind == "LPAREN":
            return self._parse_vec_generic()
        ident_tok = self._expect("IDENT")
        if self._peek().kind == "LPAREN":
            self._advance()
            args: List[Expr] = []
            while self._peek().kind != "RPAREN":
                args.append(self._parse_value())
                if self._peek().kind == "COMMA":
                    self._advance()
            self._expect("RPAREN")
            return Expr(kind="call", call_name=ident_tok.value, call_args=args)
        return Expr(kind="ident", ident=ident_tok.value)

    def _parse_value_list(self) -> Expr:
        self._expect("LBRACKET")
        items: List[Expr] = []
        while self._peek().kind != "RBRACKET":
            items.append(self._parse_value())
            if self._peek().kind == "COMMA":
                self._advance()
        self._expect("RBRACKET")
        return Expr(kind="list", items=items)

    def _parse_vec_generic(self) -> Expr:
        self._expect("LPAREN")
        items = [self._parse_value()]
        while self._peek().kind == "COMMA":
            self._advance()
            items.append(self._parse_value())
        self._expect("RPAREN")
        return Expr(kind="vec", items=items)

    def _parse_vec2(self) -> Expr:
        v = self._parse_vec_generic()
        if len(v.items) != 2:
            raise QSDLSyntaxError(f"vec2 must have exactly 2 components, got {len(v.items)}")
        return v

    def _parse_vec3(self) -> Expr:
        v = self._parse_vec_generic()
        if len(v.items) != 3:
            raise QSDLSyntaxError(f"vec3 must have exactly 3 components, got {len(v.items)}")
        return v


def parse_qsdl(source: str) -> SceneAST:
    """Tokenize and parse a QSDL v1.0 source string into a SceneAST."""
    tokens = tokenize(source)
    parser = QSDLParser(tokens)
    scene = parser.parse_scene()
    if parser._peek().kind != "EOF":
        tok = parser._peek()
        raise QSDLSyntaxError(f"Unexpected trailing tokens starting at {tok.kind} {tok.value!r}, offset {tok.pos}")
    return scene


def _self_test() -> str:
    sample = """
    scene sunset {
        manifold M32
        object sphere_0 {
            geometry sphere(radius=1.0, center=(0,0,0))
            material glass {
                dielectric = 1.5
                absorption = 0.001
                quantum {
                    hamiltonian = diagonal(0.5)
                    coupling = uniform(0.1)
                    resonance = [0.5, 0.5, 0.5]
                }
            }
            transform {
                translate(0, 0, -2)
                scale(1.5, 1.5, 1.5)
            }
        }
        light sun {
            type = directional
            position = (1, 1, 1)
            intensity = 1.0
            driving = zero()
        }
        camera {
            resolution = (7680, 4320)
            fov = 60.0
            position = (0, 0, 5)
            readout = {
                observables = [intensity, depth, normal]
                supersampling = 2
                tone_map = aces
            }
        }
        quality {
            layers = 4
            evolution_steps = 80
            learning_rate = 0.08
            damping = 0.01
            seed = 0
        }
    }
    """
    scene = parse_qsdl(sample)
    assert scene.name == "sunset"
    assert scene.manifold is not None and scene.manifold.manifold_type == "M32"
    assert len(scene.objects) == 1
    obj = scene.objects[0]
    assert obj.name == "sphere_0"
    assert obj.geometry is not None and obj.geometry.geometry_type == "sphere"
    assert obj.geometry.params["radius"].number == 1.0
    assert obj.material is not None and obj.material.name == "glass"
    assert obj.material.properties["dielectric"].number == 1.5
    assert obj.material.quantum is not None
    assert obj.material.quantum.hamiltonian.kind == "call"
    assert obj.material.quantum.hamiltonian.call_name == "diagonal"
    assert obj.material.quantum.hamiltonian.call_args[0].number == 0.5
    assert obj.material.quantum.coupling.call_name == "uniform"
    assert [e.number for e in obj.material.quantum.resonance.items] == [0.5, 0.5, 0.5]
    assert len(obj.transform) == 2
    assert obj.transform[0].op == "translate"
    assert obj.transform[1].op == "scale"
    assert len(scene.lights) == 1
    assert scene.lights[0].light_type == "directional"
    assert scene.camera is not None
    assert [c.number for c in scene.camera.resolution.items] == [7680.0, 4320.0]
    assert scene.camera.readout.observables == ["intensity", "depth", "normal"]
    assert scene.camera.readout.tone_map == "aces"
    assert scene.quality.layers == 4
    assert scene.quality.evolution_steps == 80

    # Error path: a genuinely malformed source must raise, not silently
    # return a default scene.
    try:
        parse_qsdl("scene broken { object o { geometry sphere(radius=1.0) } }")
        raise AssertionError("expected QSDLSyntaxError for object missing material")
    except QSDLSyntaxError:
        pass

    try:
        parse_qsdl("scene { camera {} }")
        raise AssertionError("expected QSDLSyntaxError for missing scene name")
    except QSDLSyntaxError:
        pass

    return "qsdl_parser._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
