"""Measure a deterministic synthetic 4 KiB database-page-like sample."""
import hashlib,json,math,os,platform,sys,tempfile,time,zlib
from pathlib import Path
from chronus.quantum.ring_codec import encode,decode


def percentile(x,p): return sorted(x)[math.ceil(len(x)*p/100)-1]


def sample_page():
    # 64 fixed-width records of 64 bytes, synthetic, not an actual database page.
    return b''.join((f'row={i:04d};tenant={i%7:02d};balance={i*13:010d};'.encode()).ljust(64,b' ') for i in range(64))


def main():
    data=sample_page(); assert len(data)==4096
    start=time.perf_counter_ns(); encoded=encode(data); enc_ns=time.perf_counter_ns()-start
    assert decode(encoded)==data
    baseline=zlib.compress(data); assert zlib.decompress(baseline)==data
    for _ in range(3): decode(encoded)
    samples=[]
    for _ in range(100):
        start=time.perf_counter_ns(); out=decode(encoded); samples.append(time.perf_counter_ns()-start)
        assert out==data
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'page.bin'
        with p.open('wb') as f:
            written=f.write(encoded); f.flush(); os.fsync(f.fileno())
        start=time.perf_counter_ns(); reopened=decode(p.read_bytes()); reopen_ns=time.perf_counter_ns()-start
        assert reopened==data
    artifact={'system':'synthetic database-page-like record sample; not a real page store','data_class':'64 fixed-width textual records in one 4096-byte page','input_sha256':hashlib.sha256(data).hexdigest(), 'input_bytes':len(data),'encoded_bytes':len(encoded),'encoded_sha256':hashlib.sha256(encoded).hexdigest(),'ratio_definition':'input bytes / encoded bytes','ratio':len(data)/len(encoded),'logical_write_amplification':written/len(data),'logical_write_definition':'encoded bytes written by application / input bytes; excludes later storage effects','physical_write_amplification':None,'recovery_ns':None,'recovery_note':'no crash/corruption recovery implementation; clean reopen only','clean_reopen_decode_ns':reopen_ns,'encode_ns':enc_ns,'decode_ns':{'samples':samples,'p50':percentile(samples,50),'p95':percentile(samples,95),'p99':percentile(samples,99),'method':'nearest rank; 100 serial in-memory calls after 3 warmups'},'roundtrip_bit_for_bit':out==data,'clean_reopen_roundtrip':reopened==data,'baseline':{'name':'zlib default on identical input','encoded_bytes':len(baseline),'ratio':len(data)/len(baseline),'roundtrip_bit_for_bit':zlib.decompress(baseline)==data},'next_candidate':'binary database pages from an approved representative dataset, reported separately','python':sys.version,'platform':platform.platform()}
    print(json.dumps(artifact,indent=2,sort_keys=True))


if __name__=='__main__': main()
