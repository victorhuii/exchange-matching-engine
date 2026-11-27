"""Small loopback HTTP workbench for the C++ engine; standard library only."""
import argparse
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import random
import threading
import time
from urllib.parse import urlsplit

from exchange.bridge import Bridge
from exchange.reference import Reference, flow
from scripts.build import ROOT

def trace(count=60):
    core=Bridge()
    events=[]
    try:
        for command in flow(count):
            result=core.submit(command)
            events.append(dict(command=command,result=result,state=core.state()))
    finally:
        core.close()
    return events

def journal_commands(directory):
    path=directory/'commands.log'
    commands=[]
    if not path.exists():return commands
    for line in path.read_text().splitlines():
        v=line.split('\t')[1:-1]
        if len(v)==4 and v[0]=='C':
            c=dict(type='cancel',request_id=v[1],order_id=v[2],participant=v[3])
        elif len(v)==8 and v[0]=='O':
            c=dict(type='order',request_id=v[1],order_id=v[2],participant=v[3],side='buy' if v[4]=='B' else 'sell',price=int(v[5]),quantity=int(v[6]),tif=v[7])
        else:
            raise RuntimeError('journal format cannot be exported; restart to verify recovery')
        commands.append(c)
    return commands

class Application:
    def __init__(self,directory):
        self.directory=Path(directory)
        self.core=Bridge(self.directory)
        self.lock=threading.RLock()
        try:
            self.replay=trace()
            self.known_requests={c['request_id'] for c in journal_commands(self.directory)}
            self.benchmark=json.loads((ROOT/'docs/benchmark.json').read_text()) if (ROOT/'docs/benchmark.json').exists() else None
        except Exception:
            self.core.close()
            raise

    def close(self):
        self.core.close()

    def command(self,c):
        if self.core.state()['sequence']>=5000 and c.get('request_id') not in self.known_requests:
            raise ValueError('workbench limit reached (5000 commands); use a new --data directory')
        start=time.perf_counter_ns()
        result=self.core.submit(c)
        elapsed=(time.perf_counter_ns()-start)/1000
        self.known_requests.add(c['request_id'])
        return dict(result=result,state=self.core.state(),bridge_roundtrip_us=elapsed)

    def demo(self):
        state=self.core.state()
        if state['sequence']+100>5000:
            raise ValueError('not enough capacity for a 100-command demo')
        ref=Reference()
        ref.sequence=state['sequence'];ref.orders=deepcopy(state['orders']);ref.trades=deepcopy(state['trades'])
        for owner,b in state['balances'].items():ref.balances[owner]=dict(cash=int(b['cash']),inventory=b['inventory'])
        rng=random.Random(42);prefix=f"sim-{state['sequence']+1}"
        for i in range(100):
            key=f'{prefix}-{i+1}'
            eligible=[o for o in ref.orders if o['participant'].startswith('agent-')]
            if eligible and rng.random()<.15:
                maker=rng.choice(eligible)
                c=dict(type='cancel',request_id=key,order_id=maker['order_id'],participant=maker['participant'])
            else:
                c=dict(type='order',request_id=key,order_id=key,participant=f'agent-{rng.randrange(4)}',
                       side=rng.choice(['buy','sell']),price=rng.randint(9995,10005),quantity=rng.randint(1,8),
                       tif='IOC' if rng.random()<.35 else 'GTC')
            actual=self.core.submit(c); expected=ref.submit(c)
            if actual!=expected:raise RuntimeError('reference mismatch; stop the workbench for investigation')
            self.known_requests.add(c['request_id'])
        return dict(commands=100,state=self.core.state(),reference_match=True)

    def action(self,path,body):
        with self.lock:
            if path=='/api/command':return self.command(body)
            if path=='/api/demo':return self.demo()
            if path=='/api/snapshot':return self.core.snapshot()
            if path=='/api/recover':return self.core.recover()
            raise ValueError('unknown API route')

def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass

        def send(self,status,data,kind='application/json; charset=utf-8',download=None):
            payload=json.dumps(data,allow_nan=False).encode() if kind.startswith('application/json') else data
            self.send_response(status)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(payload)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            if download:self.send_header('Content-Disposition',f'attachment; filename="{download}"')
            self.end_headers();self.wfile.write(payload)

        def local(self):
            return self.headers.get('Host','') in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')

        def do_GET(self):
            if not self.local():return self.send(403,dict(error='loopback host required'))
            path=urlsplit(self.path).path
            try:
                with app.lock:
                    if path=='/api/state':return self.send(200,app.core.state())
                    if path=='/api/replay':return self.send(200,app.replay)
                    if path=='/api/benchmark':return self.send(200,app.benchmark)
                    if path=='/api/export':
                        return self.send(200,dict(state=app.core.state(),commands=journal_commands(app.directory),benchmark=app.benchmark),download='exchange-session.json')
                assets={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
                if path in assets:
                    name,kind=assets[path];return self.send(200,(ROOT/'web'/name).read_bytes(),kind)
                return self.send(404,dict(error='not found'))
            except (RuntimeError,ValueError,OSError):
                return self.send(503,dict(error='local engine or storage unavailable; restart and retain request IDs'))

        def do_POST(self):
            if not self.local():return self.send(403,dict(error='loopback host required'))
            origin=self.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):
                return self.send(403,dict(error='same-origin requests only'))
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                return self.send(415,dict(error='application/json required'))
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=1000000:return self.send(413,dict(error='body must be between 1 byte and 1 MB'))
                body=json.loads(self.rfile.read(size))
                if not isinstance(body,dict):raise ValueError('request must be an object')
                return self.send(200,app.action(urlsplit(self.path).path,body))
            except (ValueError,TypeError,UnicodeError) as exc:
                return self.send(400,dict(error=str(exc)))
            except (RuntimeError,OSError):
                return self.send(503,dict(error='engine or storage failed; restart and retry the original request ID'))
    return Handler

def main():
    parser=argparse.ArgumentParser(description='Start the exchange engine workbench')
    parser.add_argument('--port',type=int,default=8766)
    parser.add_argument('--data',type=Path,default=Path('runtime/exchange'))
    args=parser.parse_args()
    app=Application(args.data)
    try:
        server=ThreadingHTTPServer(('127.0.0.1',args.port),handler_for(app))
    except OSError:
        app.close();raise
    print(f'Exchange Matching Engine: http://127.0.0.1:{server.server_port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close();app.close()

if __name__=='__main__':main()
