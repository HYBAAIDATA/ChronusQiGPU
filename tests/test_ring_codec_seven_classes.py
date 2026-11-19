import ast
from pathlib import Path
import struct
import pytest
from hypothesis import given, settings, strategies as st
from chronus.quantum.geometric_polychoron import Cyclotomic5 as C
from chronus.quantum.ring_codec import MAX_BYTES, encode, decode

pytestmark = pytest.mark.real


class TestInvariant:
    def test_exhaustive_octets(self):
        for i in range(256):
            b=bytes([i]); assert decode(encode(b))==b
            assert len(encode(b))==52


class TestProperty:
    @settings(max_examples=120, deadline=None, derandomize=True)
    @given(st.binary(max_size=256))
    def test_roundtrip_and_length(self, data):
        encoded=encode(data)
        assert decode(encoded)==data and len(encoded)==44+8*len(data)


class TestAdversarial:
    def test_bad_input_and_tampering(self):
        with pytest.raises(TypeError): encode('hi')
        with pytest.raises(TypeError): decode(bytearray())
        with pytest.raises(ValueError): decode(b'')
        blob=encode(b'A')
        with pytest.raises(ValueError): decode(b'NOPE'+blob[4:])
        with pytest.raises(ValueError): decode(blob+b'0')
        with pytest.raises(ValueError): decode(blob[:-1])
        with pytest.raises(ValueError): decode(blob[:4]+struct.pack('>Q', MAX_BYTES+1)+blob[12:])
        changed=bytearray(blob); changed[12]^=1
        with pytest.raises(ValueError,match='digest mismatch'): decode(bytes(changed))
        changed=bytearray(blob); changed[-1]^=1
        with pytest.raises(ValueError,match='ring symbol'): decode(bytes(changed))

    def test_no_inexact_numeric_literals(self):
        tree=ast.parse(Path('src/chronus/quantum/ring_codec.py').read_text())
        assert not any(isinstance(n,ast.Constant) and isinstance(n.value,(float,complex)) for n in ast.walk(tree))


class TestEdge:
    def test_empty_maximum_and_limit(self):
        assert decode(encode(b''))==b''
        data=bytes(range(256))*16; assert len(data)==MAX_BYTES
        assert decode(encode(data))==data
        with pytest.raises(ValueError): encode(data+b'x')


class TestUnit:
    def test_fixed_symbol_encoding(self):
        raw=encode(b'A')
        assert raw[:4]==b'RC01'
        phi=C(65,0,0,0)*C.phi()
        assert struct.unpack('>hhhh',raw[44:])==(phi.c0,phi.c1,phi.c2,phi.c3)
        assert decode(raw)==b'A'


class TestIntegration:
    def test_math_inverse(self):
        phi, inv=C.phi(), C.phi_inv()
        assert phi*inv == C.one()
        for b in range(256): assert C(b,0,0,0)*phi*inv==C(b,0,0,0)


class TestEndToEnd:
    def test_file_roundtrip(self,tmp_path):
        data=b'page header\x00records\xff'; path=tmp_path/'page'
        path.write_bytes(encode(data))
        assert decode(path.read_bytes())==data
