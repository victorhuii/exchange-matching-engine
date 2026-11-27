"""Stress workloads cross-checked against the independent matching reference."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from exchange.bridge import Bridge
from exchange.reference import Reference
from scripts.build import build

def decode(line):
    v=line.split('\t');c=dict(type='order' if v[0]=='O' else 'cancel',request_id=v[1],order_id=v[2],participant=v[3])
    if v[0]=='O':c.update(side='buy' if v[4]=='B' else 'sell',price=int(v[5]),quantity=int(v[6]),tif=v[7])
    return c

class WorkloadTests(unittest.TestCase):
    def test_profiles_match_independent_reference(self):
        for profile in ['deep','cancel-burst','sweep']:
            with self.subTest(profile=profile):
                stream=subprocess.check_output([str(build()),'--benchmark','127','--profile',profile,'--emit-workload'],text=True).splitlines()
                reference=Reference();core=Bridge()
                try:
                    for line in stream:
                        command=decode(line);self.assertEqual(core.submit(command),reference.submit(command))
                    self.assertEqual(core.state(),reference.state())
                finally:core.close()
    def test_profile_depth_conservation_and_durable_identity(self):
        for profile in ['deep','cancel-burst','sweep']:
            with self.subTest(profile=profile),tempfile.TemporaryDirectory() as d:
                args=[str(build()),'--benchmark','128','--profile',profile]
                memory=json.loads(subprocess.check_output(args,text=True));durable=json.loads(subprocess.check_output([*args,'--data',d],text=True))
                self.assertEqual(memory['workload_fnv64'],durable['workload_fnv64']);self.assertEqual(memory['final_state_fnv64'],durable['final_state_fnv64'])
                self.assertTrue(memory['cash_conserved'] and memory['inventory_conserved'])
                self.assertEqual(memory['max_resting_orders'],128 if profile=='deep' else 64)
                self.assertEqual(memory['final_resting_orders'],128 if profile=='deep' else 0)
                if profile=='deep':self.assertEqual(memory['final_price_levels'],128)
                if profile=='cancel-burst':self.assertEqual(memory['cancels'],64)
                if profile=='sweep':self.assertEqual(memory['trades'],64)
    def test_minimal_and_invalid_profiles(self):
        for profile in ['deep','cancel-burst','sweep']:
            out=json.loads(subprocess.check_output([str(build()),'--benchmark','1','--profile',profile],text=True));self.assertEqual(out['commands'],1)
        invalid=subprocess.run([str(build()),'--benchmark','1','--profile','unknown'],capture_output=True,text=True)
        self.assertNotEqual(invalid.returncode,0);self.assertIn('profile must be',invalid.stderr)

if __name__=='__main__':unittest.main()
