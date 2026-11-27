from copy import deepcopy
import json
from pathlib import Path
import random
import subprocess
import tempfile
import unittest
from exchange.bridge import Bridge
from exchange.reference import Reference, flow
from scripts.build import build

def order(n, side='buy', price=100, quantity=5, **kw):
    return dict(type='order',request_id=f'r{n}',order_id=f'o{n}',participant=f'p{n}',
                side=side,price=price,quantity=quantity,**kw)

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.core=Bridge()
    def tearDown(self):
        self.core.close()

    def test_price_priority_fifo_partial_and_ioc(self):
        for c in [order(1,'sell',102,3),order(2,'sell',101,2),order(3,'sell',101,4)]:
            self.core.submit(c)
        result=self.core.submit(order(4,'buy',101,5))
        self.assertEqual([(t['maker'],t['price'],t['quantity']) for t in result['trades']],[('o2',101,2),('o3',101,3)])
        self.assertEqual(self.core.state()['orders'][-1]['quantity'],1)
        result=self.core.submit(order(5,'buy',103,10,tif='IOC'))
        self.assertEqual((result['filled'],result['cancelled'],result['resting']),(4,6,0))

    def test_cancel_owner_and_reuse(self):
        self.core.submit(order(1))
        cancel=dict(type='cancel',request_id='cancel',order_id='o1',participant='wrong')
        with self.assertRaises(ValueError):self.core.submit(cancel)
        result=self.core.submit({**cancel,'participant':'p1'})
        self.assertEqual((result['cancelled'],result['resting']),(5,0))
        with self.assertRaises(ValueError):self.core.submit({**order(1),'request_id':'new'})
        self.assertEqual(self.core.state()['sequence'],2)

    def test_dedup_and_conflicting_request(self):
        c=order(1); first=self.core.submit(c)
        self.assertEqual(self.core.submit(c),first)
        with self.assertRaises(ValueError):self.core.submit({**c,'price':101})
        self.assertEqual(self.core.state()['sequence'],1)

    def test_invalid_protocol_and_python_types(self):
        for line in ['O\tr\to\tp\tB\t-1\t5\tGTC','O\tr\to\tp\tX\t100\t5\tGTC','garbage','O\tr\to\tp\tB\t100\t1.5\tGTC']:
            with self.assertRaises(ValueError):self.core.raw(line)
        for q in [0,-1,True,1.5,'5',100001]:
            with self.assertRaises(ValueError):self.core.submit(order(1,quantity=q))
        with self.assertRaises(ValueError):self.core.submit({**order(1),'participant':'tab\tinjection'})
        self.assertEqual(self.core.state()['sequence'],0)

    def test_reference_generated_stream_and_invariants(self):
        ref=Reference()
        for i,c in enumerate(flow(1200,17)):
            expected=ref.submit(c);self.assertEqual(self.core.submit(c),expected)
            if i%31==0:
                state=self.core.state();self.assertEqual(state,ref.state())
                self.assertEqual(sum(int(b['cash']) for b in state['balances'].values()),0)
                self.assertEqual(sum(b['inventory'] for b in state['balances'].values()),0)
                self.assertTrue(all(o['quantity']>0 for o in state['orders']))
                if state['bids'] and state['asks']:self.assertLess(state['bids'][0]['price'],state['asks'][0]['price'])
        self.assertEqual(self.core.state(),ref.state())

    def test_self_trade_conserves_balances_and_large_integer_cash(self):
        self.core.submit({**order(1,'sell',100000000,100000),'participant':'a'})
        self.core.submit({**order(2,'buy',100000000,100000),'participant':'b'})
        self.assertEqual(self.core.state()['balances']['b']['cash'],'-10000000000000')
        self.core.submit({**order(3,'sell'),'participant':'a'})
        self.core.submit({**order(4,'buy'),'participant':'a'})
        self.assertEqual(sum(int(b['cash']) for b in self.core.state()['balances'].values()),0)

class PersistenceTests(unittest.TestCase):
    def test_snapshot_tail_replay_and_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            x=Bridge(tmp)
            try:
                for c in flow(100):x.submit(c)
                x.snapshot()
                for n in range(100,110):x.submit(order(n))
                before=x.state()
                self.assertTrue(x.recover()['identical'])
            finally:x.close()
            with Path(tmp,'commands.log').open('ab') as f:f.write(b'111\tO\ttorn')
            y=Bridge(tmp)
            try:
                self.assertEqual(y.state(),before)
                self.assertEqual(y.submit(order(109))['sequence'],110)
                y.submit(order(110))
            finally:y.close()
            z=Bridge(tmp)
            try:self.assertEqual(z.state()['sequence'],111)
            finally:z.close()

    def test_failpoints_around_acknowledgment(self):
        for failpoint,sequence in [('before_journal',0),('after_journal',1)]:
            with self.subTest(failpoint=failpoint), tempfile.TemporaryDirectory() as tmp:
                x=Bridge(tmp,failpoint)
                with self.assertRaises(RuntimeError):x.submit(order(1))
                x.close()
                y=Bridge(tmp)
                try:
                    self.assertEqual(y.state()['sequence'],sequence)
                    self.assertEqual(y.submit(order(1))['sequence'],1)
                    self.assertEqual(len(y.state()['orders']),1)
                finally:y.close()

    def test_snapshot_failure_preserves_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            x=Bridge(tmp,'snapshot_before_rename');x.submit(order(1))
            with self.assertRaises(RuntimeError):x.snapshot()
            x.close()
            y=Bridge(tmp)
            try:self.assertEqual(y.state()['sequence'],1)
            finally:y.close()

    def test_corruption_fails_closed(self):
        for target in ['commands.log','snapshot.dat']:
            with self.subTest(target=target),tempfile.TemporaryDirectory() as tmp:
                x=Bridge(tmp);x.submit(order(1));x.snapshot();x.close()
                p=Path(tmp,target);data=p.read_bytes();p.write_bytes(data.replace(b'100',b'101',1))
                with self.assertRaises(RuntimeError):Bridge(tmp)

    def test_single_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            x=Bridge(tmp)
            try:
                with self.assertRaises(RuntimeError):Bridge(tmp)
                self.assertEqual(x.state()['sequence'],0)
            finally:x.close()

if __name__=='__main__':unittest.main()
