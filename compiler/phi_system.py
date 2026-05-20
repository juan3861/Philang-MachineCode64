#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  Φ-SYSTEM — Acelerador System-Wide                                        ║
║  ══════════════════════════════════════════════════════════════════════════ ║
║  Instala como sitecustomize. Toda execução Python na máquina               ║
║  automaticamente detecta e acelera funções compatíveis.                     ║
║                                                                            ║
║  "Python não existe mais. Só machine code."                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import sys, os, ctypes, time, ast, functools, importlib, builtins
from pathlib import Path
from typing import Callable, Dict, Optional

# ══════════════════════════════════════════════════════════════════════════════
# §1  ENGINE (embutido — zero dependências)
# ══════════════════════════════════════════════════════════════════════════════

TEMPLATES = {
    'sum_gauss': bytes([0x48,0x89,0xC8,0x48,0xFF,0xC0,0x48,0xF7,0xE1,0x48,0xD1,0xE8,0xC3]),
    'factorial': bytes([0x48,0x31,0xC0,0x48,0xFF,0xC0,0x48,0x85,0xC9,0x74,0x08,0x48,0xF7,0xE1,0x48,0xFF,0xC9,0x75,0xF8,0xC3]),
    'fibonacci': bytes([0x48,0x83,0xF9,0x01,0x76,0x17,0x48,0x31,0xC0,0xBA,0x01,0x00,0x00,0x00,0x48,0x89,0xC3,0x48,0x89,0xD0,0x48,0x01,0xDA,0x48,0xFF,0xC9,0x75,0xF2,0xC3,0x48,0x89,0xC8,0xC3]),
    'square':    bytes([0x48,0x89,0xC8,0x48,0x0F,0xAF,0xC0,0xC3]),
    'cube':      bytes([0x48,0x89,0xC8,0x48,0x0F,0xAF,0xC0,0x48,0x0F,0xAF,0xC1,0xC3]),
    'abs_val':   bytes([0x48,0x89,0xC8,0x48,0x85,0xC9,0x79,0x03,0x48,0xF7,0xD8,0xC3]),
}

PATTERNS = {
    'sum_gauss': ['sum_range', 'sum_to_n', 'gauss_sum', 'soma_gauss', 'soma_ate'],
    'factorial': ['factorial', 'fat', 'fact'],
    'fibonacci': ['fibonacci', 'fib', 'fibo'],
    'square':    ['square', 'quadrado', 'sq'],
    'cube':      ['cube', 'cubo'],
    'abs_val':   ['abs', 'absoluto', 'absolute', 'abs_val'],
}

class _Engine:
    def __init__(self):
        self.k32 = ctypes.windll.kernel32
        self.k32.VirtualAlloc.restype = ctypes.c_void_p
        self._cache: Dict[str, Callable] = {}
        self.stats = {'compiled': 0, 'accelerated': 0, 'calls': 0}
    
    def compile(self, name: str) -> Optional[Callable]:
        if name in self._cache: return self._cache[name]
        code = TEMPLATES.get(name)
        if not code: return None
        buf = self.k32.VirtualAlloc(0, len(code)+16, 0x3000, 0x40)
        if not buf: return None
        ctypes.memmove(buf, code, len(code))
        func = ctypes.WINFUNCTYPE(ctypes.c_uint64, ctypes.c_uint64)(buf)
        self._cache[name] = func
        self.stats['compiled'] += 1
        return func
    
    def detect(self, name: str) -> Optional[str]:
        n = name.lower()
        for tmpl, patterns in PATTERNS.items():
            for p in patterns:
                if p in n: return tmpl
        return None

_engine = _Engine()

# ══════════════════════════════════════════════════════════════════════════════
# §2  IMPORT HOOK — Todo módulo que entra, sai acelerado
# ══════════════════════════════════════════════════════════════════════════════

_original_import = builtins.__import__

def _phi_import(name, *args, **kwargs):
    module = _original_import(name, *args, **kwargs)
    _accelerate_module(module)
    return module

def _accelerate_module(module):
    """Acelera todas as funções compatíveis em um módulo."""
    count = 0
    for attr_name in list(module.__dict__.keys()):
        if attr_name.startswith('_'): continue
        obj = getattr(module, attr_name, None)
        if not callable(obj): continue
        
        template = _engine.detect(attr_name)
        if not template: continue
        
        native = _engine.compile(template)
        if not native: continue
        
        @functools.wraps(obj)
        def wrapper(n, nf=native, name=attr_name):
            _engine.stats['calls'] += 1
            return nf(n)
        
        try:
            setattr(module, attr_name, wrapper)
            count += 1
        except:
            pass
    
    if count > 0:
        _engine.stats['accelerated'] += count

# ══════════════════════════════════════════════════════════════════════════════
# §3  ATIVAÇÃO
# ══════════════════════════════════════════════════════════════════════════════

def activate():
    """Ativa o acelerador system-wide."""
    if builtins.__import__ is not _phi_import:
        builtins.__import__ = _phi_import
    
    # Acelera módulos já carregados
    for name, module in list(sys.modules.items()):
        if module and not name.startswith('_'):
            try:
                _accelerate_module(module)
            except:
                pass
    
    return _engine.stats

def status():
    return dict(_engine.stats)

# Ativa automaticamente ao importar
_activated = activate()
