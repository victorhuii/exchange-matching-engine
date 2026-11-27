import http.client
from http.server import ThreadingHTTPServer
import json
import tempfile
import threading
import unittest
from exchange.server import Application,handler_for

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.app=Application(self.tmp.name)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(self.app))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        self.app.close();self.tmp.cleanup()
    def request(self,method,path,body=None,headers=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        connection.request(method,path,json.dumps(body) if body is not None else None,headers or {'Content-Type':'application/json'})
        response=connection.getresponse();status=response.status;payload=response.read();connection.close()
        return status,payload

    def test_assets_and_routes(self):
        for path in ['/','/app.js','/style.css','/api/state','/api/replay','/api/export','/api/benchmark']:
            self.assertEqual(self.request('GET',path)[0],200,path)
        self.assertEqual(self.request('GET','/../../etc/passwd')[0],404)
        self.assertEqual(len(json.loads(self.request('GET','/api/replay')[1])),60)
        self.assertEqual(json.loads(self.request('GET','/api/state')[1])['sequence'],0)

    def test_command_replay_snapshot_and_export(self):
        command=dict(type='order',request_id='r',order_id='o',participant='alice',side='buy',price=10000,quantity=5)
        first=json.loads(self.request('POST','/api/command',command)[1])
        self.assertEqual(first['result']['resting'],5)
        self.assertEqual(json.loads(self.request('POST','/api/command',command)[1])['result'],first['result'])
        self.assertEqual(self.request('POST','/api/snapshot',{})[0],200)
        self.assertTrue(json.loads(self.request('POST','/api/recover',{})[1])['identical'])
        exported=json.loads(self.request('GET','/api/export')[1])
        self.assertEqual(exported['commands'],[{**command,'tif':'GTC'}])
        self.assertEqual(exported['state']['sequence'],1)

    def test_flow_matches_reference_with_existing_manual_orders(self):
        command=dict(type='order',request_id='manual',order_id='manual',participant='alice',side='sell',price=9996,quantity=500)
        self.request('POST','/api/command',command)
        for sequence in [101,201]:
            status,payload=self.request('POST','/api/demo',{})
            self.assertEqual(status,200)
            result=json.loads(payload)
            self.assertTrue(result['reference_match'])
            self.assertEqual(result['state']['sequence'],sequence)
        self.assertTrue(json.loads(self.request('POST','/api/recover',{})[1])['identical'])

    def test_input_validation_and_origin(self):
        self.assertEqual(self.request('POST','/api/command',{'type':'order'})[0],400)
        self.assertEqual(self.request('POST','/api/command',[])[0],400)
        self.assertEqual(self.request('POST','/api/snapshot',{}, {'Content-Type':'text/plain'})[0],415)
        self.assertEqual(self.request('POST','/api/snapshot',{}, {'Content-Type':'application/json','Origin':'https://example.com'})[0],403)
        self.assertEqual(self.request('GET','/',headers={'Host':'example.com'})[0],403)

if __name__=='__main__':unittest.main()
