"""Compile the C++ core without downloaded build dependencies."""
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def build():
    compiler = os.environ.get('CXX') or shutil.which('clang++') or shutil.which('g++')
    if not compiler:
        raise SystemExit('Install a C++20 compiler (Xcode Command Line Tools on macOS, g++/clang on Linux).')
    source = ROOT / 'src/engine.cpp'
    target = ROOT / 'build/engine'
    target.parent.mkdir(exist_ok=True)
    if not target.exists() or source.stat().st_mtime > target.stat().st_mtime:
        subprocess.run([compiler, '-std=c++20', '-O3', '-DNDEBUG', '-Wall', '-Wextra', '-Wpedantic', str(source), '-o', str(target)], check=True)
    return target

if __name__ == '__main__':
    print(build())
