"""Streaming EOF and lifecycle tests for lossless GL2 frames."""
import pytest

from chronus.kernels.gl2_transform import FoldStream, UnfoldStream, fold, unfold, from_wire

pytestmark = pytest.mark.real


@pytest.mark.parametrize('data', [b'', b'\x00', b'\xff', b'abc', bytes(range(32))])
def test_stream_matches_batch_with_empty_updates_and_terminal_state(data):
    encoder = FoldStream()
    parts = []
    for byte in data:
        assert encoder.update(b'') == b''
        parts.append(encoder.update(bytes([byte])))
    tail, trailer = encoder.finalize()
    wire = encoder.header(len(data)) + b''.join(parts) + tail + trailer
    assert encoder.bytes_processed == len(data)
    assert wire == fold(data).to_wire()
    assert unfold(from_wire(wire)) == data
    decoder = UnfoldStream()
    decoded = b''.join(decoder.update(bytes([byte])) for byte in wire)
    decoder.finalize()
    assert decoded == data
    assert decoder.original_length == len(data)
    for stream in (encoder, decoder):
        with pytest.raises(RuntimeError, match='finalized'):
            stream.update(b'')
        with pytest.raises(RuntimeError, match='finalized'):
            stream.finalize()


@pytest.mark.parametrize('missing', [1, 2, 4, 5, 8, 20, 24])
def test_truncated_frame_fails_at_eof_and_cannot_resume(missing):
    wire = fold(b'abc').to_wire()
    decoder = UnfoldStream()
    decoder.update(wire[:-missing])
    with pytest.raises(ValueError, match='incomplete|truncated|trailer'):
        decoder.finalize()
    with pytest.raises(RuntimeError, match='finalized'):
        decoder.update(wire[-missing:])


@pytest.mark.parametrize('data', [b'', b'x', b'xy', b'xyz'])
def test_stream_and_batch_enforce_same_exact_length_limit(data):
    wire = fold(data).to_wire()
    decoder = UnfoldStream(max_length=len(data))
    assert decoder.update(wire) == data
    decoder.finalize()
    assert unfold(from_wire(wire, max_length=len(data))) == data
    if data:
        with pytest.raises(ValueError, match='max_length'):
            from_wire(wire, max_length=len(data) - 1)
        with pytest.raises(ValueError, match='max_length'):
            UnfoldStream(max_length=len(data) - 1).update(wire)


@pytest.mark.parametrize('split', range(25))
def test_crc_corruption_rejected_across_chunk_boundaries(split):
    wire = bytearray(fold(b'abc').to_wire())
    wire[-1] ^= 1
    decoder = UnfoldStream()
    decoder.update(wire[:split])
    decoder.update(wire[split:])
    with pytest.raises(ValueError, match='CRC-32C mismatch'):
        decoder.finalize()
    with pytest.raises(RuntimeError, match='finalized'):
        decoder.finalize()
    with pytest.raises(ValueError, match='CRC-32C mismatch'):
        from_wire(wire)
