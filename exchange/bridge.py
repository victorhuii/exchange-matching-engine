"""Typed Python-to-C++ line protocol. One child process, one caller at a time."""
from pathlib import Path
import re
import select
import subprocess
import threading
from scripts.build import build

import json

ID = re.compile(r'[A-Za-z0-9_.:-]{1,100}\Z')

def identity(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError('identifiers require 1–100 ASCII letters, digits, dots, underscores, colons or hyphens')
    return value

def positive(value, maximum):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f'value must be an integer from 1 to {maximum}')
    return value

def encode(c):
    if not isinstance(c, dict):
        raise ValueError('command must be an object')
    kind = c.get('type')
    common = [identity(c.get(key)) for key in ('request_id', 'order_id', 'participant')]
    if kind == 'cancel':
        return '\t'.join(['C', *common])
    if kind != 'order':
        raise ValueError('type must be order or cancel')
    side, tif = c.get('side'), c.get('tif', 'GTC')
    if side not in ('buy','sell') or tif not in ('GTC','IOC'):
        raise ValueError('invalid side or time in force')
    return '\t'.join(['O', *common, 'B' if side == 'buy' else 'S',
                      str(positive(c.get('price'),100000000)), str(positive(c.get('quantity'),100000)), tif])

class Bridge:
    def __init__(self, directory=None, failpoint=None):
        command = [str(build())]
        if directory is not None:
            command += ['--data', str(directory)]
        if failpoint:
            command += ['--failpoint', failpoint]
        self.lock = threading.RLock()
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, bufsize=1)
        try:
            self.state()
        except Exception:
            self.close()
            raise

    def raw(self, line):
        with self.lock:
            if self.process.poll() is not None:
                raise RuntimeError('matching process stopped; restart and retry with the original request ID')
            try:
                self.process.stdin.write(line+'\n')
                self.process.stdin.flush()
                if not select.select([self.process.stdout], [], [], 15)[0]:
                    self.process.kill()
                    self.process.wait()
                    raise RuntimeError('matching process timed out; restart before retrying')
                response = self.process.stdout.readline()
            except (BrokenPipeError, OSError):
                raise RuntimeError('matching process disconnected; command may have persisted') from None
            if not response:
                raise RuntimeError('matching process disconnected; command may have persisted')
            result = json.loads(response)
            if not result.get('ok'):
                if result.get('kind') == 'storage':
                    raise RuntimeError(result.get('error','local storage failed'))
                raise ValueError(result.get('error','matching command failed'))
            return result

    def submit(self, command):
        return self.raw(encode(command))['result']

    def state(self):
        return self.raw('STATE')['state']

    def snapshot(self):
        return self.raw('SNAPSHOT')

    def recover(self):
        return self.raw('RECOVER')

    def close(self):
        if getattr(self, 'process', None):
            if self.process.poll() is None:
                self.process.stdin.close()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            for stream in (self.process.stdin,self.process.stdout,self.process.stderr):
                if not stream.closed:
                    stream.close()
