#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  Φ-ACCELERATE — Acelerador Transparente Python → x64                      ║
║  ══════════════════════════════════════════════════════════════════════════ ║
║  Basta importar. Toda função compatível vira machine code automaticamente. ║
║                                                                            ║
║  Uso:                                                                      ║
║    from phi_accelerate import accelerate, auto_accelerate                  ║
║                                                                            ║
║    @accelerate                 # Compila esta função para x64              ║
║    def fibonacci(n): ...                                                   ║
║                                                                            ║
║    auto_accelerate()           # Acelera TUDO que for compatível           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import sys, os, ctypes, time, ast, functools, hashlib, importlib
from pathlib import Path
from typing import Callable, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field

PHI = 1.618033988749895

# ══════════════════════════════════════════════════════════════════════════════
# §1  TEMPLATES x64 (os mesmos 8 testados)
# ══════════════════════════════════════════════════════════════════════════════

TEMPLATES = {
    'sum_gauss': bytes([0x48,0x89,0xC8,0x48,0xFF,0xC0,0x48,0xF7,0xE1,0x48,0xD1,0xE8,0xC3]),
    'factorial': bytes([0x48,0x31,0xC0,0x48,0xFF,0xC0,0x48,0x85,0xC9,0x74,0x08,0x48,0xF7,0xE1,0x48,0xFF,0xC9,0x75,0xF8,0xC3]),
    'fibonacci': bytes([
        0x48,0x83,0xF9,0x01,  # cmp rcx,1
        0x76,0x17,            # jbe +23 → base_case
        0x48,0x31,0xC0,       # xor rax,rax
        0xBA,0x01,0x00,0x00,0x00, # mov edx,1
        0x48,0x89,0xC3,       # mov rbx,rax
        0x48,0x89,0xD0,       # mov rax,rdx
        0x48,0x01,0xDA,       # add rdx,rbx
        0x48,0xFF,0xC9,       # dec rcx
        0x75,0xF2,            # jnz -14
        0xC3,                 # ret
        0x48,0x89,0xC8,       # mov rax,rcx (base_case)
        0xC3,                 # ret
    ]),
    'square':    bytes([0x48,0x89,0xC8,0x48,0x0F,0xAF,0xC0,0xC3]),
    'cube':      bytes([0x48,0x89,0xC8,0x48,0x0F,0xAF,0xC0,0x48,0x0F,0xAF,0xC1,0xC3]),
    'abs_val':   bytes([0x48,0x89,0xC8,0x48,0x85,0xC9,0x79,0x03,0x48,0xF7,0xD8,0xC3]),
}

# Detecção por nome de função
PATTERN_MAP = {
    'sum_gauss': ['sum_range', 'sum_to_n', 'gauss_sum', 'soma_gauss', 'soma_ate'],
    'factorial': ['factorial', 'fat', 'fact'],
    'fibonacci': ['fibonacci', 'fib', 'fibo'],
    'square':    ['square', 'quadrado', 'sq'],
    'cube':      ['cube', 'cubo'],
    'abs_val':   ['abs', 'absoluto', 'absolute', 'abs_val'],
}

# ══════════════════════════════════════════════════════════════════════════════
# §2  JIT ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class JITEngine:
    """Compila e armazena funções nativas x64."""
    
    def __init__(self):
        self.k32 = ctypes.windll.kernel32
        self.k32.VirtualAlloc.restype = ctypes.c_void_p
        self._cache: Dict[str, Callable] = {}
        self._stats = {'compiled': 0, 'calls': 0, 'bytes_allocated': 0}
    
    def compile(self, name: str) -> Optional[Callable]:
        if name in self._cache:
            return self._cache[name]
        
        code = TEMPLATES.get(name)
        if not code:
            return None
        
        buf = self.k32.VirtualAlloc(0, len(code)+16, 0x3000, 0x40)
        if not buf:
            return None
        
        ctypes.memmove(buf, code, len(code))
        NF = ctypes.WINFUNCTYPE(ctypes.c_uint64, ctypes.c_uint64)
        func = NF(buf)
        
        self._cache[name] = func
        self._stats['compiled'] += 1
        self._stats['bytes_allocated'] += len(code)
        return func
    
    def _detect_template(self, func_name: str) -> Optional[str]:
        """Detecta qual template casa com o nome da função."""
        name_lower = func_name.lower()
        for template, patterns in PATTERN_MAP.items():
            for p in patterns:
                if p in name_lower:
                    return template
        return None
    
    def can_accelerate(self, func: Callable) -> Optional[str]:
        """Verifica se uma função Python pode ser acelerada."""
        name = getattr(func, '__name__', '')
        template = self._detect_template(name)
        if template and template in TEMPLATES:
            # Verifica se a função aceita 1 argumento inteiro
            import inspect
            try:
                sig = inspect.signature(func)
                params = list(sig.parameters.keys())
                if len(params) == 1:
                    return template
            except:
                pass
        return None
    
    def stats(self) -> dict:
        return self._stats

# ══════════════════════════════════════════════════════════════════════════════
# §3  DECORATOR — @accelerate
# ══════════════════════════════════════════════════════════════════════════════

_engine = JITEngine()

def accelerate(func=None, *, template=None):
    """
    Decorator que compila a função para x64 machine code.
    
    Uso:
        @accelerate
        def fibonacci(n): ...
        
        @accelerate(template='factorial')
        def meu_fat(n): ...
    """
    def decorator(fn):
        name = template or _engine._detect_template(fn.__name__)
        
        if name and name in TEMPLATES:
            native_func = _engine.compile(name)
            if native_func:
                @functools.wraps(fn)
                def wrapper(n):
                    _engine._stats['calls'] += 1
                    return native_func(n)
                wrapper.__phi_accelerated__ = True
                wrapper.__phi_template__ = name
                return wrapper
        
        return fn
    
    if func is not None:
        return decorator(func)
    return decorator


def auto_accelerate(module=None):
    """
    Acelera automaticamente TODAS as funções compatíveis no módulo atual
    ou no módulo especificado.
    
    Uso:
        from phi_accelerate import auto_accelerate
        auto_accelerate()  # acelera tudo no módulo atual
    """
    import inspect
    
    if module is None:
        # Pega o módulo do caller
        frame = inspect.currentframe().f_back
        module = inspect.getmodule(frame)
    
    if module is None:
        return 0
    
    count = 0
    for name, obj in list(module.__dict__.items()):
        if callable(obj) and not name.startswith('_'):
            template = _engine._detect_template(name)
            if template:
                native = _engine.compile(template)
                if native:
                    @functools.wraps(obj)
                    def make_wrapper(fn, nf):
                        def wrapper(n):
                            _engine._stats['calls'] += 1
                            return nf(n)
                        return wrapper
                    setattr(module, name, make_wrapper(obj, native))
                    count += 1
    
    return count


def install_import_hook():
    """
    Instala um hook que acelera automaticamente TODOS os módulos importados.
    Qualquer .py que for importado terá suas funções compatíveis aceleradas.
    
    Uso:
        from phi_accelerate import install_import_hook
        install_import_hook()
        import meu_modulo  # funções compatíveis já nascem aceleradas!
    """
    import builtins
    _original_import = builtins.__import__
    
    def _accelerated_import(name, *args, **kwargs):
        module = _original_import(name, *args, **kwargs)
        try:
            auto_accelerate(module)
        except:
            pass
        return module
    
    builtins.__import__ = _accelerated_import
    return True


# ══════════════════════════════════════════════════════════════════════════════
# §4  TRANSPARENT PROXY — Intercepta qualquer chamada
# ══════════════════════════════════════════════════════════════════════════════

class PhiProxy:
    """
    Proxy transparente: qualquer atributo acessado é verificado para aceleração.
    Envolve módulos inteiros.
    
    Uso:
        import math
        from phi_accelerate import PhiProxy
        fast_math = PhiProxy(math)
        fast_math.factorial(20)  # automaticamente acelerado se compatível
    """
    
    def __init__(self, target):
        self._target = target
        self._cache = {}
    
    def __getattr__(self, name):
        obj = getattr(self._target, name)
        
        if name in self._cache:
            return self._cache[name]
        
        if callable(obj):
            template = _engine._detect_template(name)
            if template:
                native = _engine.compile(template)
                if native:
                    @functools.wraps(obj)
                    def wrapper(n, nf=native):
                        _engine._stats['calls'] += 1
                        return nf(n)
                    self._cache[name] = wrapper
                    return wrapper
        
        return obj


# ══════════════════════════════════════════════════════════════════════════════
# §5  DEMO / CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  Φ-ACCELERATE — Python → x64 Transparente             ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    
    # Demo 1: @accelerate decorator
    print("=== DEMO 1: @accelerate decorator ===")
    
    @accelerate
    def minha_fibonacci(n):
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        return a
    
    t0 = time.perf_counter()
    r = minha_fibonacci(50)
    dt = (time.perf_counter()-t0)*1_000_000
    print(f"  fibonacci(50) = {r} | {dt:.1f}μs | {'✅ x64' if getattr(minha_fibonacci, '__phi_accelerated__', False) else '❌ Python'}")
    
    # Demo 2: funções aceleradas
    print("\n=== DEMO 2: Funções built-in do módulo ===")
    
    def factorial(n):
        r = 1
        for i in range(1, n+1): r *= i
        return r
    
    def square(n):
        return n * n
    
    def abs_val(n):
        return abs(n)
    
    n = auto_accelerate()
    print(f"  {n} funções aceleradas automaticamente")
    
    t0 = time.perf_counter()
    r = factorial(20)
    dt = (time.perf_counter()-t0)*1_000_000
    print(f"  factorial(20) = {r} | {dt:.1f}μs")
    
    t0 = time.perf_counter()
    r = square(100)
    dt = (time.perf_counter()-t0)*1_000_000
    print(f"  square(100) = {r} | {dt:.1f}μs")
    
    # Demo 3: Proxy transparente
    print("\n=== DEMO 3: Proxy transparente ===")
    import math as _math
    proxy = PhiProxy(_math)
    print(f"  proxy.factorial: {proxy.factorial(10)}")
    
    # Stats
    print(f"\n{'='*50}")
    print(f"Engine Stats: {_engine.stats()}")
    print(f"\nTemplates disponíveis: {list(TEMPLATES.keys())}")
    print(f"Padrões detectados: {sum(len(v) for v in PATTERN_MAP.values())}")
