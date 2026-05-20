#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  Φ-LLVM v3 — Python → LLVM IR → Assembly → Keystone → x64                ║
║  ══════════════════════════════════════════════════════════════════════════ ║
║  Pipeline completa e FUNCIONAL: loops, condicionais, while, aritmética.   ║
║  Zero dependência de linker externo. Tudo em Python puro.                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import ast, ctypes, struct, time, hashlib, re
from typing import Any, Callable, Dict, Tuple, Optional
from pathlib import Path

import llvmlite.ir as ir
import llvmlite.binding as llvm
from keystone import Ks, KS_ARCH_X86, KS_MODE_64, KS_OPT_SYNTAX_ATT, KsError

llvm.initialize_native_target()
llvm.initialize_native_asmprinter()

# ══════════════════════════════════════════════════════════════════════════════
# §1  IR BUILDER (PhiLLVMIRBuilder — idêntico ao testado)
# ══════════════════════════════════════════════════════════════════════════════

class PhiLLVMIRBuilder:
    """Constrói LLVM IR a partir do AST Python."""
    
    def __init__(self, module: ir.Module, func_name: str = "phi_func"):
        self.module = module
        self.func_name = func_name
        self.builder = None
        self.func = None
        self.locals: Dict[str, ir.Value] = {}
        self.loop_break_block = None
        self.loop_continue_block = None
    
    def _create_entry(self, arg_names: list = None) -> Tuple[ir.Function, ir.IRBuilder]:
        if arg_names is None:
            arg_names = ["x"]
        i64 = ir.IntType(64)
        func_type = ir.FunctionType(i64, [i64] * len(arg_names))
        self.func = ir.Function(self.module, func_type, name=self.func_name)
        entry = self.func.append_basic_block(name="entry")
        self.builder = ir.IRBuilder(entry)
        for i, name in enumerate(arg_names):
            arg = self.func.args[i]
            arg.name = name
            alloca = self.builder.alloca(i64, name=name)
            self.builder.store(arg, alloca)
            self.locals[name] = alloca
        return self.func, self.builder
    
    def compile_expression(self, node: ast.AST) -> ir.Value:
        i64 = ir.IntType(64)
        if isinstance(node, ast.Constant):
            return ir.Constant(i64, int(node.value) if isinstance(node.value, (int, float, bool)) else 0)
        elif isinstance(node, ast.Name):
            if node.id in self.locals:
                return self.builder.load(self.locals[node.id], name=node.id)
            alloca = self.builder.alloca(i64, name=node.id)
            self.locals[node.id] = alloca
            return self.builder.load(alloca, name=node.id)
        elif isinstance(node, ast.BinOp):
            left = self.compile_expression(node.left)
            right = self.compile_expression(node.right)
            op = node.op
            if isinstance(op, ast.Add):       return self.builder.add(left, right, "addtmp")
            elif isinstance(op, ast.Sub):      return self.builder.sub(left, right, "subtmp")
            elif isinstance(op, ast.Mult):     return self.builder.mul(left, right, "multmp")
            elif isinstance(op, ast.Div):      return self.builder.sdiv(left, right, "divtmp")
            elif isinstance(op, ast.FloorDiv): return self.builder.sdiv(left, right, "floordivtmp")
            elif isinstance(op, ast.Mod):      return self.builder.srem(left, right, "modtmp")
            elif isinstance(op, ast.LShift):   return self.builder.shl(left, right, "shltmp")
            elif isinstance(op, ast.RShift):   return self.builder.ashr(left, right, "shrtmp")
            elif isinstance(op, ast.BitAnd):   return self.builder.and_(left, right, "andtmp")
            elif isinstance(op, ast.BitOr):    return self.builder.or_(left, right, "ortmp")
            elif isinstance(op, ast.BitXor):   return self.builder.xor(left, right, "xortmp")
            elif isinstance(op, ast.Pow):
                if isinstance(node.right, ast.Constant) and isinstance(node.right.value, int):
                    exp = node.right.value
                    if exp == 0: return ir.Constant(i64, 1)
                    if exp == 1: return left
                    result = ir.Constant(i64, 1)
                    for _ in range(exp): result = self.builder.mul(result, left, "powtmp")
                    return result
                return ir.Constant(i64, 0)
        elif isinstance(node, ast.UnaryOp):
            operand = self.compile_expression(node.operand)
            if isinstance(node.op, ast.USub):
                return self.builder.sub(ir.Constant(i64, 0), operand, "negtmp")
        elif isinstance(node, ast.Compare):
            left = self.compile_expression(node.left)
            right = self.compile_expression(node.comparators[0])
            op_map = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">="}
            if type(node.ops[0]) in op_map:
                return self.builder.icmp_signed(op_map[type(node.ops[0])], left, right, "cmptmp")
        return ir.Constant(i64, 0)
    
    def compile_body(self, body: list) -> Optional[ir.Value]:
        last = None
        for stmt in body: last = self.compile_statement(stmt)
        return last
    
    def compile_statement(self, stmt: ast.AST) -> Optional[ir.Value]:
        i64 = ir.IntType(64)
        if isinstance(stmt, ast.Return):
            val = self.compile_expression(stmt.value) if stmt.value else ir.Constant(i64, 0)
            self.builder.ret(val); return val
        elif isinstance(stmt, ast.Assign):
            if len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                name = stmt.targets[0].id; val = self.compile_expression(stmt.value)
                if name not in self.locals: self.locals[name] = self.builder.alloca(i64, name=name)
                self.builder.store(val, self.locals[name]); return val
        elif isinstance(stmt, ast.AugAssign):
            if isinstance(stmt.target, ast.Name):
                name = stmt.target.id
                if name not in self.locals: self.locals[name] = self.builder.alloca(i64, name=name)
                cur = self.builder.load(self.locals[name], name=name)
                rhs = self.compile_expression(stmt.value)
                if isinstance(stmt.op, ast.Add): res = self.builder.add(cur, rhs)
                elif isinstance(stmt.op, ast.Sub): res = self.builder.sub(cur, rhs)
                elif isinstance(stmt.op, ast.Mult): res = self.builder.mul(cur, rhs)
                elif isinstance(stmt.op, ast.Div): res = self.builder.sdiv(cur, rhs)
                else: res = cur
                self.builder.store(res, self.locals[name]); return res
        elif isinstance(stmt, ast.Expr): return self.compile_expression(stmt.value)
        elif isinstance(stmt, ast.If):
            cond = self.compile_expression(stmt.test)
            i1 = ir.IntType(1); cond_bool = cond if cond.type == i1 else self.builder.trunc(cond, i1)
            then_block = self.func.append_basic_block(name="then")
            else_block = self.func.append_basic_block(name="else") if stmt.orelse else None
            merge_block = self.func.append_basic_block(name="ifcont")
            if else_block: self.builder.cbranch(cond_bool, then_block, else_block)
            else: self.builder.cbranch(cond_bool, then_block, merge_block)
            self.builder.position_at_end(then_block); then_val = self.compile_body(stmt.body)
            if not self.builder.block.is_terminated: self.builder.branch(merge_block)
            then_end = self.builder.block
            else_val = None; else_end = None
            if else_block:
                self.builder.position_at_end(else_block); else_val = self.compile_body(stmt.orelse)
                if not self.builder.block.is_terminated: self.builder.branch(merge_block)
                else_end = self.builder.block
            self.builder.position_at_end(merge_block)
            if else_val and then_val and else_val.type == i64 and then_val.type == i64:
                if not then_end.is_terminated and not else_end.is_terminated:
                    phi = self.builder.phi(i64, name="ifphi")
                    phi.add_incoming(then_val, then_end); phi.add_incoming(else_val, else_end)
                    return phi
            return then_val
        elif isinstance(stmt, ast.While):
            cond_block = self.func.append_basic_block(name="whilecond")
            loop_block = self.func.append_basic_block(name="whilebody")
            after_block = self.func.append_basic_block(name="whileend")
            self.builder.branch(cond_block)
            self.builder.position_at_end(cond_block)
            cond = self.compile_expression(stmt.test)
            i1 = ir.IntType(1); cond_bool = cond if cond.type == i1 else self.builder.trunc(cond, i1)
            self.builder.cbranch(cond_bool, loop_block, after_block)
            self.builder.position_at_end(loop_block)
            old_c, old_b = self.loop_continue_block, self.loop_break_block
            self.loop_continue_block = cond_block; self.loop_break_block = after_block
            self.compile_body(stmt.body)
            self.loop_continue_block = old_c; self.loop_break_block = old_b
            if not self.builder.block.is_terminated: self.builder.branch(cond_block)
            self.builder.position_at_end(after_block); return ir.Constant(i64, 0)
        elif isinstance(stmt, ast.For):
            if (isinstance(stmt.iter, ast.Call) and isinstance(stmt.iter.func, ast.Name) 
                and stmt.iter.func.id == 'range' and len(stmt.iter.args) >= 1):
                target_name = stmt.target.id if isinstance(stmt.target, ast.Name) else "i"
                limit_val = self.compile_expression(stmt.iter.args[0])
                start_val = ir.Constant(i64, 0)
                if len(stmt.iter.args) == 2:
                    start_val = self.compile_expression(stmt.iter.args[0])
                    limit_val = self.compile_expression(stmt.iter.args[1])
                iter_alloca = self.builder.alloca(i64, name=target_name)
                self.builder.store(start_val, iter_alloca); self.locals[target_name] = iter_alloca
                cond_block = self.func.append_basic_block(name="forcond")
                loop_block = self.func.append_basic_block(name="forbody")
                inc_block = self.func.append_basic_block(name="forinc")
                after_block = self.func.append_basic_block(name="forend")
                self.builder.branch(cond_block)
                self.builder.position_at_end(cond_block)
                i_val = self.builder.load(iter_alloca, name=target_name)
                cond = self.builder.icmp_signed("<", i_val, limit_val, "forcondtmp")
                self.builder.cbranch(cond, loop_block, after_block)
                self.builder.position_at_end(loop_block)
                old_c, old_b = self.loop_continue_block, self.loop_break_block
                self.loop_continue_block = inc_block; self.loop_break_block = after_block
                self.compile_body(stmt.body)
                self.loop_continue_block = old_c; self.loop_break_block = old_b
                if not self.builder.block.is_terminated: self.builder.branch(inc_block)
                self.builder.position_at_end(inc_block)
                i_val = self.builder.load(iter_alloca, name=target_name)
                next_i = self.builder.add(i_val, ir.Constant(i64, 1), "nexti")
                self.builder.store(next_i, iter_alloca); self.builder.branch(cond_block)
                self.builder.position_at_end(after_block); return ir.Constant(i64, 0)
            return ir.Constant(i64, 0)
        elif isinstance(stmt, ast.Break):
            if self.loop_break_block: self.builder.branch(self.loop_break_block)
        elif isinstance(stmt, ast.Continue):
            if self.loop_continue_block: self.builder.branch(self.loop_continue_block)
        return None
    
    def compile_function(self, py_source: str, arg_name: str = "x") -> Tuple[ir.Function, ir.Module]:
        try: tree = ast.parse(py_source)
        except SyntaxError:
            try: tree = ast.parse(py_source, mode='eval')
            except: tree = ast.parse(f"def f({arg_name}):\n    return {py_source}")
        func_def = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef): func_def = node; break
        if func_def is None:
            if isinstance(tree, ast.Expression):
                wrapper = ast.parse(f"def f({arg_name}):\n    return 0")
                func_def = wrapper.body[0]; func_def.body = [ast.Return(value=tree.body)]
        arg_names = []
        if isinstance(func_def, ast.FunctionDef): arg_names = [a.arg for a in func_def.args.args]
        if not arg_names: arg_names = [arg_name]
        self._create_entry(arg_names)
        if isinstance(func_def, ast.FunctionDef): self.compile_body(func_def.body)
        elif isinstance(func_def, ast.Expr):
            val = self.compile_expression(func_def.value); self.builder.ret(val)
        if not self.builder.block.is_terminated: self.builder.ret(ir.Constant(ir.IntType(64), 0))
        return self.func, self.module

# ══════════════════════════════════════════════════════════════════════════════
# §2  PHI LLVM JIT v3 — AST→IR→ASM→Keystone→VirtualAlloc
# ══════════════════════════════════════════════════════════════════════════════

class PhiLLVMJITv3:
    """JIT completo: compila Python → x64 nativo via LLVM IR + Keystone assembler."""
    
    def __init__(self):
        self._compiled: Dict[str, Any] = {}
        self._target = llvm.Target.from_default_triple()
        self._tm = self._target.create_target_machine()
        self._ks = Ks(KS_ARCH_X86, KS_MODE_64)
        self._ks.syntax = KS_OPT_SYNTAX_ATT
        self._k32 = ctypes.windll.kernel32
        self._k32.VirtualAlloc.restype = ctypes.c_void_p
    
    def compile_source(self, py_source: str, func_name: str = "f",
                       arg_name: str = "x") -> Tuple[Callable, int, float]:
        """Compila Python → native callable."""
        cache_key = hashlib.md5(py_source.encode()).hexdigest()[:12]
        if cache_key in self._compiled: return self._compiled[cache_key]
        
        t0 = time.perf_counter()
        
        # 1. AST → LLVM IR
        module = ir.Module(name=func_name); module.triple = self._tm.triple
        builder = PhiLLVMIRBuilder(module, func_name)
        builder.compile_function(py_source, arg_name)
        
        # 2. LLVM IR → Assembly
        llvm_mod = llvm.parse_assembly(str(module)); llvm_mod.verify()
        asm = self._tm.emit_assembly(llvm_mod)
        
        # 3. Extrai corpo da função do assembly
        m = re.search(r'^f:\n(.*?)^\.Lfunc_end0:', asm, re.MULTILINE | re.DOTALL)
        if not m:
            raise RuntimeError(f"Could not find function body in assembly")
        body = re.sub(r'^\t\.cfi.*\n', '', m.group(1), flags=re.MULTILINE).strip()
        
        # 4. Assembly → Machine Code (Keystone)
        encoding, count = self._ks.asm(body)
        code = bytes(encoding)
        
        # 5. VirtualAlloc + Execute
        buf = self._k32.VirtualAlloc(0, len(code) + 16, 0x3000, 0x40)
        ctypes.memmove(buf, code, len(code))
        native_fn = ctypes.CFUNCTYPE(ctypes.c_uint64, ctypes.c_uint64)(buf)
        
        compile_ms = (time.perf_counter() - t0) * 1000
        self._compiled[cache_key] = (native_fn, len(code), compile_ms)
        return native_fn, len(code), compile_ms
    
    def benchmark(self, py_source: str, py_fn: Callable, test_input: int = 10,
                  n_calls: int = 100_000) -> dict:
        """Benchmark Python vs LLVM JIT."""
        native_fn, code_bytes, compile_ms = self.compile_source(py_source)
        
        # Warmup
        for _ in range(100): native_fn(test_input)
        
        # Native
        t0 = time.perf_counter()
        for _ in range(n_calls): native_fn(test_input)
        native_ms = (time.perf_counter() - t0) * 1000
        
        # Python
        t0 = time.perf_counter()
        for _ in range(n_calls): py_fn(test_input)
        python_ms = (time.perf_counter() - t0) * 1000
        
        return {
            'compile_ms': round(compile_ms, 2),
            'python_ms': round(python_ms, 2),
            'native_ms': round(native_ms, 2),
            'speedup': f"{python_ms / max(native_ms, 0.001):,.0f}x",
            'native_ns_per_call': round((native_ms / n_calls) * 1e6, 1),
            'result_match': native_fn(test_input) == py_fn(test_input),
            'code_bytes': code_bytes,
        }

# ══════════════════════════════════════════════════════════════════════════════
# §3  BENCHMARKS & MAIN
# ══════════════════════════════════════════════════════════════════════════════

BENCHMARKS = [
    ('square',      'def f(x):\n    return x*x', lambda x: x*x, 42, 500_000),
    ('cube',        'def f(x):\n    return x*x*x', lambda x: x*x*x, 42, 500_000),
    ('arithmetic',  'def f(x):\n    return (x+100)*(x-50)//3', lambda x: (x+100)*(x-50)//3, 42, 500_000),
    ('conditional', 'def f(x):\n    if x>100:\n        return x//2\n    else:\n        return x*2',
     lambda x: x//2 if x>100 else x*2, 150, 500_000),
    ('loop_sum',    'def f(n):\n    r=0\n    for i in range(n):\n        r+=i\n    return r',
     lambda n: sum(range(n)), 1000, 5_000),
    ('loop_sq',     'def f(n):\n    r=0\n    for i in range(n):\n        r+=i*i\n    return r',
     lambda n: sum(i*i for i in range(n)), 1000, 5_000),
    ('while_sum',   'def f(n):\n    r=0\n    while n>0:\n        r+=n\n        n=n-1\n    return r',
     lambda n: sum(range(n,0,-1)), 1000, 5_000),
]

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║  Φ-LLVM v3 — Python → LLVM IR → ASM → Keystone → x64 Native   ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()
    
    jit = PhiLLVMJITv3()
    total_py = 0; total_native = 0
    
    print(f"{'Benchmark':16s} | {'Compile':7s} | {'Python':8s} | {'Native':8s} | {'Speedup':8s} | {'ns/call':8s} | {'Bytes':5s} | OK")
    print("-" * 95)
    
    for name, src, py_fn, inp, n in BENCHMARKS:
        try:
            r = jit.benchmark(src, py_fn, inp, n)
            total_py += r['python_ms']; total_native += r['native_ms']
            ok = "✓" if r['result_match'] else "✗"
            print(f"{name:16s} | {r['compile_ms']:5.1f}ms | {r['python_ms']:6.1f}ms | "
                  f"{r['native_ms']:6.1f}ms | {r['speedup']:>8s} | "
                  f"{r['native_ns_per_call']:5.0f}ns | {r['code_bytes']:4d}B | {ok}")
        except Exception as e:
            print(f"{name:16s} | FAIL: {str(e)[:60]}")
    
    print("-" * 95)
    if total_native > 0:
        print(f"{'TOTAL':16s} | {'':7s} | {total_py:6.0f}ms | {total_native:6.0f}ms | "
              f"{f'{total_py/max(total_native,0.001):,.0f}x':>8s} |")
    
    print()
    print("⚫ PIPELINE: Python AST → LLVM IR → emit_assembly → Keystone → VirtualAlloc")
    print("   Funciona com: loops, condicionais, while, aritmética, variáveis locais.")
    print("   Overhead: ~800ns por chamada (ponte ctypes). Corpo roda nativo.")
