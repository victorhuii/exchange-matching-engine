"""Record separate C++ memory and fsync-backed benchmark paths."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
from scripts.build import build, ROOT

def measure(count=2000):
    binary=build()
    results={}
    with tempfile.TemporaryDirectory() as tmp:
        for label,args in [('memory',[]),('durable',['--data',tmp])]:
            result=subprocess.run([str(binary),'--benchmark',str(count),*args],capture_output=True,text=True,check=True)
            results[label]=json.loads(result.stdout)
    compiler=os.environ.get('CXX') or shutil.which('clang++') or shutil.which('g++')
    return dict(machine=platform.platform(),architecture=platform.machine(),python=platform.python_version(),
                compiler=subprocess.check_output([compiler,'--version'],text=True).splitlines()[0],
                build_flags='-std=c++20 -O3 -DNDEBUG -Wall -Wextra -Wpedantic',
                workload='seed 42; four synthetic participants; limit prices 9995–10005 ticks; quantities 1–8; 35% IOC probability; 15% cancellation probability when resting orders exist; one matching thread',
                timing='C++ service time including validation, matching, response JSON serialization and dedup cache; durable path additionally checksums, opens/appends, fsyncs and closes journal. Excludes command generation, command parsing, Python, IPC and HTTP. Single recorded run, no warmup.',
                results=results)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--count',type=int,default=2000)
    parser.add_argument('--output',type=Path,default=ROOT/'docs/benchmark.json')
    args=parser.parse_args()
    if not 1<=args.count<=100000:parser.error('count must be 1–100000')
    result=measure(args.count)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2))
    print(args.output)

if __name__=='__main__':main()
