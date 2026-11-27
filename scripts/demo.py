"""Save deterministic evidence from the actual C++ core."""
import json
from pathlib import Path
import tempfile
from exchange.bridge import Bridge
from exchange.server import trace
from scripts.build import ROOT

def generate():
    commands=[
        dict(type='order',request_id='a',order_id='alice-ask',participant='alice',side='sell',price=10001,quantity=5),
        dict(type='order',request_id='b',order_id='bob-ask',participant='bob',side='sell',price=10001,quantity=4),
        dict(type='order',request_id='c',order_id='carol-bid',participant='carol',side='buy',price=10001,quantity=7),
        dict(type='order',request_id='d',order_id='dave-ioc',participant='dave',side='buy',price=10000,quantity=3,tif='IOC'),
        dict(type='order',request_id='e',order_id='erin-bid',participant='erin',side='buy',price=9999,quantity=6),
        dict(type='cancel',request_id='f',order_id='bob-ask',participant='bob')]
    events=[]
    with tempfile.TemporaryDirectory() as tmp:
        core=Bridge(tmp)
        try:
            for c in commands[:5]:
                result=core.submit(c);events.append(dict(command=c,result=result,state=core.state()))
            snapshot=core.snapshot()
            result=core.submit(commands[5]);events.append(dict(command=commands[5],result=result,state=core.state()))
            before=core.state()
        finally:core.close()
        recovered=Bridge(tmp)
        try:
            after=recovered.state()
            identical=before==after
            assert identical
        finally:recovered.close()
    output=ROOT/'docs/demo';output.mkdir(exist_ok=True)
    (output/'session.json').write_text(json.dumps(dict(synthetic=True,events=events,snapshot_sequence=snapshot['sequence'],recovered_sequence=after['sequence'],recovery_identical=identical),indent=2))
    (output/'replay.json').write_text(json.dumps(trace(),indent=2))
    print(output)

if __name__=='__main__':generate()
