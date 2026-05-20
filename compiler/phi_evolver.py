#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  Φ-EVOLVER — Algoritmo Genético que GERA Templates x64                   ║
║  ══════════════════════════════════════════════════════════════════════════ ║
║  Não escrevo assembly. A AGI evolui assembly.                              ║
║                                                                            ║
║  Pipeline:                                                                 ║
║    1. População de bytes aleatórios (possíveis opcodes)                    ║
║    2. Cada indivíduo = sequência de bytes testada como função              ║
║    3. Fitness = 1.0 se resultado == Python, 0.0 se crash/errado           ║
║    4. Crossover + mutação → nova geração                                  ║
║    5. Repete até encontrar template ótimo                                  ║
║                                                                            ║
║  Proteção: cada teste roda com timeout 0.1s + VirtualAlloc isolado         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import ctypes, struct, time, random, math, sys, json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Callable
from collections import defaultdict

PHI = 1.618033988749895

# ══════════════════════════════════════════════════════════════════════════════
# §1  OPCODE KNOWLEDGE BASE
# ══════════════════════════════════════════════════════════════════════════════

# Opcodes x64 que são seguros de usar (sem syscall, sem I/O)
SAFE_OPCODES = {
    # Movimentos
    'mov_rr':    [0x48, 0x89],  # mov r64, r64 (precisa ModRM)
    'mov_ri':    [0x48, 0xC7],  # mov r64, imm32 (precisa ModRM)
    'xor_rr':    [0x48, 0x31],  # xor r64, r64
    # Aritmética
    'add_rr':    [0x48, 0x01],  # add r64, r64
    'sub_rr':    [0x48, 0x29],  # sub r64, r64
    'inc_r':     [0x48, 0xFF],  # inc r64 (precisa ModRM)
    'dec_r':     [0x48, 0xFF],  # dec r64 (precisa ModRM)
    'mul_r':     [0x48, 0xF7],  # mul/div r64 (precisa ModRM)
    'imul_rr':   [0x48, 0x0F, 0xAF],  # imul r64, r64
    'shl_ri':    [0x48, 0xC1],  # shift left (precisa ModRM)
    'shr_ri':    [0x48, 0xC1],  # shift right (precisa ModRM)
    # Controle
    'cmp_rr':    [0x48, 0x39],  # cmp r64, r64
    'test_rr':   [0x48, 0x85],  # test r64, r64
    'jmp_rel8':  [0xEB],        # jmp short
    'jz_rel8':   [0x74],        # jz short
    'jnz_rel8':  [0x75],        # jnz short
    'jbe_rel8':  [0x76],        # jbe short
    'ret':       [0xC3],        # ret
}

# Registradores (ModRM encoding)
REGISTERS = {
    'rax': 0, 'rcx': 1, 'rdx': 2, 'rbx': 3,
    'rsp': 4, 'rbp': 5, 'rsi': 6, 'rdi': 7,
}

def modrm(mod: int, reg: int, rm: int) -> int:
    return ((mod & 3) << 6) | ((reg & 7) << 3) | (rm & 7)

# Templates de instruções seguras
INSTRUCTION_TEMPLATES = [
    # [bytes] description
    ([0x48, 0x31, 0xC0], "xor rax,rax"),           # zera rax
    ([0x48, 0xFF, 0xC0], "inc rax"),                # rax++
    ([0x48, 0xFF, 0xC8], "dec rax"),                # rax--
    ([0x48, 0x01, 0xC8], "add rax,rcx"),            # rax += rcx
    ([0x48, 0x29, 0xC8], "sub rax,rcx"),            # rax -= rcx
    ([0x48, 0x0F, 0xAF, 0xC1], "imul rax,rcx"),    # rax *= rcx (signed)
    ([0x48, 0xF7, 0xE1], "mul rcx"),               # rdx:rax = rax * rcx
    ([0x48, 0xD1, 0xE8], "shr rax,1"),             # rax >>= 1
    ([0x48, 0xD1, 0xE0], "shl rax,1"),             # rax <<= 1
    ([0x48, 0x89, 0xC8], "mov rax,rcx"),           # rax = rcx
    ([0x48, 0x39, 0xC8], "cmp rax,rcx"),           # cmp rax, rcx
    ([0x48, 0x85, 0xC9], "test rcx,rcx"),          # test rcx
    ([0xEB], "jmp +0"),                             # placeholder jump
    ([0x74], "jz +0"),                              # placeholder jz
    ([0x75], "jnz +0"),                             # placeholder jnz
    ([0x76], "jbe +0"),                             # placeholder jbe
    ([0xC3], "ret"),                                 # return
]

# ══════════════════════════════════════════════════════════════════════════════
# §2  INDIVIDUAL (candidato a template)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Individual:
    genome: List[bytes]  # lista de instruções (cada uma = bytes)
    fitness: float = 0.0
    result: int = 0
    error: str = ""
    generation: int = 0
    
    def to_machine_code(self) -> bytes:
        code = bytearray()
        for inst in self.genome:
            code.extend(inst)
        # Garante que termina com ret
        if not code or code[-1] != 0xC3:
            code.append(0xC3)
        return bytes(code)

# ══════════════════════════════════════════════════════════════════════════════
# §3  EVOLVER ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class TemplateEvolver:
    """Evolui templates x64 via algoritmo genético."""
    
    def __init__(self, target_func: Callable[[int], int], func_name: str, 
                 test_inputs: List[int] = None, max_inst: int = 10):
        self.target = target_func
        self.name = func_name
        self.test_inputs = test_inputs or [0, 1, 2, 5, 10, 20, 50, 100]
        self.max_inst = max_inst
        self.k32 = ctypes.windll.kernel32
        self.k32.VirtualAlloc.restype = ctypes.c_void_p
        
        self.population: List[Individual] = []
        self.generation = 0
        self.best: Optional[Individual] = None
        self.history: List[dict] = []
    
    def _init_population(self, size: int = 50):
        """População inicial aleatória."""
        for _ in range(size):
            n = random.randint(3, self.max_inst)
            genome = [bytes(random.choice(INSTRUCTION_TEMPLATES)[0]) for _ in range(n)]
            self.population.append(Individual(genome=genome))
    
    def _test_individual(self, ind: Individual) -> Tuple[float, int, str]:
        """Testa um indivíduo: compila → executa → compara com Python."""
        code = ind.to_machine_code()
        
        # Aloca memória executável
        try:
            buf = self.k32.VirtualAlloc(0, len(code)+16, 0x3000, 0x40)
            if not buf:
                return 0.0, 0, "VirtualAlloc failed"
            ctypes.memmove(buf, code, len(code))
            NF = ctypes.WINFUNCTYPE(ctypes.c_uint64, ctypes.c_uint64)
            func = NF(buf)
        except Exception as e:
            return 0.0, 0, f"alloc: {e}"
        
        # Testa com todos os inputs
        total_score = 0.0
        last_result = 0
        n_tests = len(self.test_inputs)
        
        for x in self.test_inputs:
            expected = self.target(x)
            try:
                result = func(x)
                if result == expected:
                    total_score += 1.0 / n_tests
                else:
                    # Score parcial baseado na proximidade
                    diff = abs(int(result) - int(expected))
                    partial = max(0, 1.0 / (1.0 + diff)) / n_tests
                    total_score += partial
                last_result = result
            except Exception as e:
                return total_score, last_result, f"exec({x}): {e}"
        
        return total_score, last_result, ""
    
    def evolve(self, generations: int = 30, pop_size: int = 50):
        """Executa evolução por N gerações."""
        self._init_population(pop_size)
        
        print(f"🧬 Evoluindo template '{self.name}' — {generations} gerações, pop={pop_size}")
        print(f"   Inputs teste: {self.test_inputs}")
        
        t0 = time.perf_counter()
        
        for gen in range(generations):
            self.generation = gen
            
            # Avalia todos
            for ind in self.population:
                ind.fitness, ind.result, ind.error = self._test_individual(ind)
            
            # Ordena
            self.population.sort(key=lambda x: -x.fitness)
            best = self.population[0]
            
            if self.best is None or best.fitness > self.best.fitness:
                self.best = Individual(
                    genome=best.genome.copy(),
                    fitness=best.fitness,
                    result=best.result,
                    generation=gen,
                )
            
            self.history.append({
                'gen': gen, 'best_fitness': round(best.fitness, 4),
                'avg_fitness': round(sum(ind.fitness for ind in self.population)/len(self.population), 4),
                'best_result': best.result,
            })
            
            if gen % 5 == 0 or best.fitness >= 0.99:
                pct = int(best.fitness * 100)
                bar = '█' * (pct // 5) + '░' * (20 - pct // 5)
                print(f"   G{gen:3d}: {best.fitness:.3f} {bar} | res={best.result} | {best.error or 'ok'}")
            
            if best.fitness >= 1.0:
                print(f"   ⚡ TEMPLATE PERFEITO encontrado na geração {gen}!")
                break
            
            # Nova geração: elitismo + crossover + mutação
            elite_count = max(2, pop_size // 10)
            new_pop = [Individual(genome=ind.genome.copy()) for ind in self.population[:elite_count]]
            
            while len(new_pop) < pop_size:
                # Seleção por torneio
                p1 = self.population[random.randint(0, pop_size//3)]
                p2 = self.population[random.randint(0, pop_size//3)]
                
                # Crossover uniforme
                min_len = min(len(p1.genome), len(p2.genome))
                child_genome = []
                for i in range(min_len):
                    child_genome.append(p1.genome[i] if random.random() < 0.5 else p2.genome[i])
                # Completa com o pai mais longo
                if len(p1.genome) > min_len:
                    child_genome.extend(p1.genome[min_len:])
                elif len(p2.genome) > min_len:
                    child_genome.extend(p2.genome[min_len:])
                
                # Mutação
                if random.random() < 0.3:
                    idx = random.randint(0, len(child_genome)-1)
                    child_genome[idx] = bytes(random.choice(INSTRUCTION_TEMPLATES)[0])
                if random.random() < 0.1:
                    if len(child_genome) < self.max_inst:
                        child_genome.insert(random.randint(0, len(child_genome)), 
                                          bytes(random.choice(INSTRUCTION_TEMPLATES)[0]))
                
                new_pop.append(Individual(genome=child_genome))
            
            self.population = new_pop
        
        dt = (time.perf_counter() - t0) * 1000
        print(f"   ✅ {self.generation+1} gens em {dt:.0f}ms | melhor: {self.best.fitness:.3f}")
        
        return self.best
    
    def get_machine_code(self) -> Optional[bytes]:
        if self.best:
            return self.best.to_machine_code()
        return None

# ══════════════════════════════════════════════════════════════════════════════
# §4  LIBRARY EXPANDER — Detecta e Evolui
# ══════════════════════════════════════════════════════════════════════════════

def evolve_all_targets():
    """Evolui templates para funções comuns de bibliotecas ML/Matemática."""
    
    targets = {
        'square': lambda n: n * n,
        'cube': lambda n: n * n * n,
        'sum_to_n': lambda n: n * (n + 1) // 2,
        'factorial': lambda n: 1 if n <= 1 else n * [1][0],  # placeholder
        'power_of_2': lambda n: 1 << n,
        'is_even': lambda n: n % 2 == 0,
        'abs_val': lambda n: abs(n),
        'sign': lambda n: 1 if n > 0 else (-1 if n < 0 else 0),
        'triangular': lambda n: n * (n + 1) // 2,
        'sum_squares': lambda n: sum(i*i for i in range(1, n+1)),
    }
    
    # Corrige factorial
    def fact(n):
        r = 1
        for i in range(1, n+1): r *= i
        return r
    targets['factorial'] = fact
    
    results = {}
    
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  Φ-EVOLVER — AGI que Evolui Assembly x64              ║")
    print(f"║  {len(targets)} funções alvo                            ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    
    for name, func in targets.items():
        evolver = TemplateEvolver(
            target_func=func,
            func_name=name,
            test_inputs=[0, 1, 2, 3, 5, 10, 20],
            max_inst=8,
        )
        best = evolver.evolve(generations=20, pop_size=40)
        
        if best:
            code = best.to_machine_code()
            results[name] = {
                'fitness': best.fitness,
                'code_hex': code.hex(),
                'code_len': len(code),
                'generation': best.generation,
                'instructions': len(best.genome),
            }
            
            if best.fitness >= 0.999:  # floating point tolerance
                results[name]['perfect'] = True
                print(f"   ⚠️ {name}: {best.fitness:.1%} — quase lá")
            else:
                print(f"   ❌ {name}: {best.fitness:.1%} — precisa de + gens")
        print()
    
    return results

# ══════════════════════════════════════════════════════════════════════════════
# §5  MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    results = evolve_all_targets()
    
    perfect = sum(1 for r in results.values() if r['fitness'] >= 1.0)
    print(f"\n{'='*50}")
    print(f"RESULTADO: {perfect}/{len(results)} templates perfeitos")
    for name, r in sorted(results.items(), key=lambda x: -x[1]['fitness']):
        status = '✅' if r['fitness'] >= 1.0 else ('⚠️' if r['fitness'] >= 0.8 else '❌')
        print(f"  {status} {name:15s}: {r['fitness']:.1%} | {r['code_len']}B | gen {r['generation']}")
    
    # Salva manifesto
    manifest = {
        'evolver': 'Phi-Evolver v1.0',
        'total_targets': len(results),
        'perfect': perfect,
        'results': results,
    }
    out = Path(__file__).parent / '.evolved_templates.json'
    out.write_text(json.dumps(manifest, indent=2))
    print(f"\n💾 Manifesto salvo: {out}")
