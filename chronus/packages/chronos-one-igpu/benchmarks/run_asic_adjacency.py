"""Adjacency benchmark: prepared work reuse, compact result movement, lane pipeline."""
import argparse,json,hashlib,random,time,statistics,platform,math
from pathlib import Path
from chronos import OneIGPU
from chronos.igpu import MiningJob,PreparedSHA256d,MiningFarm
from chronos.golden_quantum import NonceLease,GoldenRatioMining,AdvancedMathematicalOracles as Oracle
GENESIS=bytes.fromhex('01000000'+'00'*32+'3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a'+'29ab5f49'+'ffff001d'+'1dac2b7c')

def run(size=4096,runs=7):
    if type(size)is not int or not 1<=size<=4096 or type(runs)is not int or not 3<=runs<=30:raise ValueError('bounded benchmark sizes required')
    expected='000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f';assert Oracle.nonce_digest(GENESIS[:76],2083236893)[::-1].hex()==expected
    prefix=GENESIS[:76];nonces=list(range(size));reference=tuple(Oracle.nonce_digest(prefix,n)for n in nonces)
    engines={'hashlib_prepared':PreparedSHA256d(prefer_native=False),'native_prepared':PreparedSHA256d(require_native=True)}
    measurements=[]
    for repeat in range(runs):
        names=['hashlib_full_header','hashlib_prepared','native_prepared','hashlib_full_scan'];random.Random(20261007+repeat).shuffle(names)
        for name in names:
            before=engines[name].stats()if name in engines else None;started=time.perf_counter()
            if name=='hashlib_full_scan':
                out=GoldenRatioMining().scan(prefix,0,NonceLease(0,size),max_evaluations=size);outputs=();assert out.sha256d_evaluations==size and not out.verified
            else:outputs=tuple(Oracle.nonce_digest(prefix,n)for n in nonces)if name=='hashlib_full_header'else engines[name].execute_sha256d(prefix,nonces)
            elapsed=time.perf_counter()-started
            if name!='hashlib_full_scan':assert outputs==reference
            measurements.append({'repeat':repeat,'case':name,'completed_sha256d':size,'elapsed_seconds':elapsed,'output_bytes':len(outputs)*32,'cache_before':before,'cache_after':engines[name].stats()if name in engines else None})
    # Compact output and farm claims concern the actual negative-control digest predicate,
    # not predictions or extrapolated dimensions. Same header, target, work count.
    compact=PreparedSHA256d(require_native=True);job=MiningJob(prefix,0,'adjacency',1);lease=NonceLease(0,size,'adjacency',1)
    for repeat in range(runs):
        started=time.perf_counter();out=compact.scan_span(job,lease,size);duration=time.perf_counter()-started
        assert out['sha256d_evaluations']==size and out['nonce']is None
        measurements.append({'repeat':repeat,'case':'native_compact_scan','completed_sha256d':size,'elapsed_seconds':duration,'output_bytes':out['output_bytes'],'compression_blocks_executed':out['compression_blocks_executed']})
    pipelines=[]
    for lanes in (1,2,4):
        farm=MiningFarm(engine=PreparedSHA256d(require_native=True),lanes=lanes,batch_size=256,max_inflight=2*lanes);farm.ledger.activate(job)
        out=farm.scan(job,lease,max_evaluations=size);MiningFarm.verify_receipt(out);assert out['scan_sha256d_evaluations']==size
        pipelines.append({'lanes':lanes,'completed_sha256d':out['scan_sha256d_evaluations'],'elapsed_seconds':out['elapsed_seconds'],'measured_hashrate':out['measured_hashrate'],'peak_inflight':out['peak_inflight'],'receipts_verified':True})
    end_to_end=[]
    owners={'original_solve_first':OneIGPU(),'prepared_solve_first':OneIGPU()}
    owners['prepared_solve_first'].configure_asic_like(require_native=True)
    for repeat in range(runs):
        order=list(owners);random.Random(1492+repeat).shuffle(order)
        for name in order:
            result=owners[name].mine(prefix,0,lease,max_evaluations=size,current_epoch=1)
            assert result.sha256d_evaluations==size and not result.verified
            end_to_end.append({'repeat':repeat,'case':name,'completed_sha256d':result.sha256d_evaluations,'elapsed_seconds':result.elapsed_seconds,'backend':result.backend,'path':list(result.path)})
    for owner in owners.values():owner.close()
    end_to_end_summary=[]
    for name in owners:
        rows=[x for x in end_to_end if x['case']==name];total=sum(x['completed_sha256d']for x in rows);seconds=sum(x['elapsed_seconds']for x in rows)
        end_to_end_summary.append({'case':name,'completed_sha256d':total,'elapsed_seconds':seconds,'aggregate_hashrate':total/seconds,'samples':len(rows),'median_seconds':statistics.median(x['elapsed_seconds']for x in rows)})
    whole_baseline=end_to_end_summary[0]['aggregate_hashrate']
    for row in end_to_end_summary:row['measured_ratio_to_original']=row['aggregate_hashrate']/whole_baseline
    summary=[]
    for name in ('hashlib_full_header','hashlib_prepared','native_prepared','hashlib_full_scan','native_compact_scan'):
        samples=[x for x in measurements if x['case']==name];hashes=sum(x['completed_sha256d']for x in samples);secs=sum(x['elapsed_seconds']for x in samples)
        summary.append({'case':name,'completed_sha256d':hashes,'elapsed_seconds':secs,'aggregate_hashrate':hashes/secs,'median_batch_seconds':statistics.median(x['elapsed_seconds']for x in samples),'output_bytes':sum(x['output_bytes']for x in samples)})
    baseline=summary[0]['aggregate_hashrate']
    scan_baseline=next(row['aggregate_hashrate']for row in summary if row['case']=='hashlib_full_scan')
    for row in summary:
        row['output_contract']='candidate_scan'if row['case']in('hashlib_full_scan','native_compact_scan')else'complete_digest_batch'
        row['reference_case']='hashlib_full_scan'if row['output_contract']=='candidate_scan'else'hashlib_full_header'
        row['measured_rate_ratio_to_reference']=row['aggregate_hashrate']/(scan_baseline if row['output_contract']=='candidate_scan'else baseline)
    # Adjacency: first block shared across tail/time changes; different first block invalidates.
    probe=PreparedSHA256d(require_native=True)
    for k in range(16):
        changed=prefix[:68]+(int.from_bytes(prefix[68:72],'little')+k).to_bytes(4,'little')+prefix[72:]
        outputs=probe.execute_sha256d(changed,[0,1]);assert outputs==tuple(Oracle.nonce_digest(changed,n)for n in[0,1])
    after_tail=probe.stats();assert after_tail['first_blocks_prepared']==1
    changed=bytes([prefix[0]^1])+prefix[1:];probe.execute_sha256d(changed,[0]);after_first=probe.stats();assert after_first['first_blocks_prepared']==2
    return {'schema':'chronos_asic_adjacency_v1','scope':'One Linux CPU host; no physical ASIC, GPU or competitor deployment measured','date':'2026-10-07','environment':{'python':platform.python_version(),'platform':platform.platform(),'native_implementation':engines['native_prepared'].native.implementation()},'corpus':{'genesis_header_hex':GENESIS.hex(),'known_hash':expected,'nonce_count':size,'runs':runs,'randomized_batch_order':True,'zero_target_negative_control':True},'measurements':measurements,'summary':summary,'end_to_end':end_to_end,'end_to_end_summary':end_to_end_summary,'lane_pipeline':pipelines,'adjacency_checks':{'same_first_block_tail_rolling':after_tail,'first_block_change_invalidates':after_first,'full_batch_output_bytes':32*size,'compact_no_winner_digest_bytes':0,'protocol_sha256d_unchanged':True,'retained_midstate_reduces_per_nonce_compressions_from':3,'retained_midstate_per_nonce_compressions':2,'candidate_space_multiplier_used':False},'negative_results':[row['case']for row in summary[1:]if row['case']not in('hashlib_full_header','hashlib_full_scan')and row['measured_rate_ratio_to_reference']<=1], 'claims':{'competitors_benchmarked':False,'physical_asic_measured':False,'pool_accepted':None,'power_measured':False,'dominance_claimed':False}}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--size',type=int,default=4096);p.add_argument('--runs',type=int,default=7);p.add_argument('--output',default='benchmarks/asic-adjacency-results.json');a=p.parse_args();data=run(a.size,a.runs);Path(a.output).write_text(json.dumps(data,indent=2)+'\n');print(json.dumps({'output':a.output,'end_to_end_summary':data['end_to_end_summary'],'summary':data['summary'],'negative_results':data['negative_results']}))
