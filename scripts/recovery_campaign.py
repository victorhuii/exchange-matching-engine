"""Bounded process-interruption and torn-tail recovery against an independent book."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import platform
import random
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from exchange.bridge import Bridge
from exchange.reference import Reference,flow


def check(condition,message):
    if not condition:raise AssertionError(message)


def mixed_campaign(seeds=(3,17,29,43,71),count=180,interruptions=8):
    check(count>=30 and 1<=interruptions<=count-10,'invalid campaign dimensions')
    evidence=dict(seeds=list(seeds),commands_per_seed=count,interruptions_per_seed=interruptions,commands=0,before_journal_exits=0,after_journal_exits=0,post_ack_kills=0,snapshots=0,duplicate_retries=0,restarts=0,reference_checks=0)
    for seed in seeds:
        rng=random.Random(seed);boundaries=set(rng.sample(range(5,count-5),interruptions));commands=flow(count,seed);reference=Reference()
        with tempfile.TemporaryDirectory() as tmp:
            core=Bridge(tmp)
            try:
                for index,command in enumerate(commands):
                    if index in boundaries:
                        core.close();failpoint='before_journal' if rng.randrange(2)==0 else 'after_journal';crashed=Bridge(tmp,failpoint)
                        try:
                            try:crashed.submit(command)
                            except RuntimeError:pass
                            else:raise AssertionError('failpoint did not terminate the process')
                            crashed.process.wait(timeout=5);check(crashed.process.returncode==(85 if failpoint=='before_journal' else 86),'unexpected injected exit')
                        finally:crashed.close()
                        evidence[failpoint+'_exits']+=1
                        expected=reference.submit(command) if failpoint=='after_journal' else None
                        core=Bridge(tmp);evidence['restarts']+=1
                        check(core.state()==reference.state(),'recovered state differs before retry');evidence['reference_checks']+=1
                        if expected is None:expected=reference.submit(command)
                        check(core.submit(command)==expected,'original-ID retry differs')
                        for _ in range(3):check(core.submit(command)==expected,'deduplicated response differs');evidence['duplicate_retries']+=1
                    else:check(core.submit(command)==reference.submit(command),'command response differs')
                    evidence['commands']+=1
                    if index%23==7:core.snapshot();evidence['snapshots']+=1
                    if index%19==11:
                        # The command was acknowledged; kill rather than orderly EOF.
                        core.process.kill();core.process.wait(timeout=5);core.close();core=Bridge(tmp);evidence['post_ack_kills']+=1;evidence['restarts']+=1
                    check(core.state()==reference.state(),'post-command/restart state differs');evidence['reference_checks']+=1
                    state=core.state();check(sum(int(b['cash']) for b in state['balances'].values())==0,'cash not conserved');check(sum(b['inventory'] for b in state['balances'].values())==0,'inventory not conserved')
                core.close();core=Bridge(tmp);evidence['restarts']+=1;check(core.state()==reference.state(),'final cold reopen differs');evidence['reference_checks']+=1
            finally:core.close()
    return evidence


def torn_tail_campaign():
    # Build one complete final record to obtain canonical bytes. Every prefix is
    # then treated as an unacknowledged candidate tail, not as lost acknowledged
    # durable data or a physical-storage power-failure simulation.
    commands=flow(30,97);prefix_reference=Reference();full_reference=Reference()
    for c in commands[:-1]:prefix_reference.submit(c)
    for c in commands:full_reference.submit(c)
    with tempfile.TemporaryDirectory() as baseline:
        core=Bridge(baseline)
        try:
            for c in commands:core.submit(c)
        finally:core.close()
        lines=(Path(baseline)/'commands.log').read_bytes().splitlines(keepends=True);prefix=b''.join(lines[:-1]);last=lines[-1]
    cases=0
    for cut in range(len(last)+1):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'commands.log';path.write_bytes(prefix+last[:cut]);core=Bridge(tmp)
            try:
                expected=full_reference.state() if cut==len(last) else prefix_reference.state()
                check(core.state()==expected,'tail repair recovered the wrong committed prefix')
                check(path.read_bytes()==(prefix+last if cut==len(last) else prefix),'tail repair left extra bytes')
                check(core.submit(commands[-1])==full_reference.requests[commands[-1]['request_id']][1],'tail retry response differs')
                check(core.state()==full_reference.state(),'tail retry changed final book');cases+=1
            finally:core.close()
    return dict(final_record_bytes=len(last),prefix_cuts_tested=cases,all_repaired_or_deduplicated=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'docs/recovery-campaign.json');args=p.parse_args()
    report=dict(created_at=datetime.now(timezone.utc).isoformat(),environment=dict(python=platform.python_version(),platform=platform.platform()),source_sha256=hashlib.sha256((ROOT/'src/engine.cpp').read_bytes()).hexdigest(),synthetic=True,mixed=mixed_campaign(),torn_tail=torn_tail_campaign(),limits=['Bounded seeded process-exit/kill and synthetic byte-prefix tests; not exhaustive fault exploration.','No power-loss, disk-cache, device failure, short-write/fsync syscall injection, network or live-trading validation.','A lost acknowledgment can mean a command persisted; retries must use the original request ID.'])
    args.output.parent.mkdir(exist_ok=True,parents=True);args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
