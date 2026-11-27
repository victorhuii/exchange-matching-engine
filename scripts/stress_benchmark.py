"""Repeated independent-process profiles; retain every measurement and identity."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import tempfile
from scripts.build import ROOT,build

PROFILES=['mixed','deep','cancel-burst','sweep']
DESCRIPTIONS={
'mixed':'Existing seed-42 four-participant mixed limit/IOC/cancel flow.',
'deep':'All GTC bids at distinct increasing prices; one new price level per command.',
'cancel-burst':'Build ceil(N/2) GTC bids across 32 levels, then cancel in reverse insertion order.',
'sweep':'Build ceil(N/2) unit GTC asks across groups of eight per price, then send crossing 8-unit IOC buys.'}

def measure(count=10000,repeats=3):
    binary=build();samples=[]
    with tempfile.TemporaryDirectory() as tmp:
        for profile in PROFILES:
            identities=set()
            for repeat in range(repeats):
                for mode in ['memory','durable']:
                    args=[str(binary),'--benchmark',str(count),'--profile',profile]
                    if mode=='durable':args+=['--data',str(Path(tmp)/f'{profile}-{repeat}')]
                    result=json.loads(subprocess.check_output(args,text=True))
                    samples.append(dict(mode=mode,repeat=repeat+1,**result));identities.add((result['workload_fnv64'],result['final_state_fnv64']))
            if len(identities)!=1:raise RuntimeError('workload or final state changed between measurements')
    summaries=[]
    for profile in PROFILES:
        for mode in ['memory','durable']:
            rows=[r for r in samples if r['profile']==profile and r['mode']==mode]
            def stats(values):return dict(median=statistics.median(values),minimum=min(values),maximum=max(values))
            summaries.append(dict(profile=profile,mode=mode,runs=len(rows),commands_per_second=stats([r['commands_per_second'] for r in rows]),latency_us={p:stats([r['latency_us'][p] for r in rows]) for p in ['p50','p95','p99']},max_resting_orders=rows[0]['max_resting_orders'],final_price_levels=rows[0]['final_price_levels']))
    compiler=os.environ.get('CXX') or shutil.which('clang++') or shutil.which('g++')
    return dict(captured_at=datetime.now(timezone.utc).isoformat(),source_sha256=hashlib.sha256((ROOT/'src/engine.cpp').read_bytes()).hexdigest(),machine=platform.platform(),architecture=platform.machine(),compiler=subprocess.check_output([compiler,'--version'],text=True).splitlines()[0],build_flags='-std=c++20 -O3 -DNDEBUG -Wall -Wextra -Wpedantic',commands_per_run=count,repeats=repeats,profiles=DESCRIPTIONS,
                timing='Per-command steady_clock service time includes validation, matching, response JSON and dedup storage. Throughput includes loop instrumentation. Durable mode additionally checksums, opens/appends, fsyncs and closes journal. Excludes generation, TSV parsing, Python, IPC, HTTP, final hashes and conservation checks. Fresh process/store per run, no warmup or CPU affinity. FNV-64 identities are deterministic checksums, not cryptographic proofs.',
                limitations=['Synthetic workload; results depend on compiler, machine, OS and background load.','Three runs summarize variability, not a confidence interval or cross-machine scalability claim.','Retained responses/trades grow with accepted commands; no constant-memory claim.','Memory and durable runs alternate within each repetition; order effects remain possible.'],summaries=summaries,samples=samples)

def main():
    p=argparse.ArgumentParser();p.add_argument('--count',type=int,default=10000);p.add_argument('--repeats',type=int,default=3);p.add_argument('--output',type=Path,default=ROOT/'docs/stress-benchmark.json');a=p.parse_args()
    if not 1<=a.count<=100000 or not 1<=a.repeats<=10:p.error('count 1–100000; repeats 1–10')
    result=measure(a.count,a.repeats);a.output.parent.mkdir(exist_ok=True,parents=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(a.output)
if __name__=='__main__':main()
