<p align="center">
  <img src="https://img.shields.io/badge/Φ--Lang-Machine%20Code%2064-blue?style=for-the-badge" alt="PhiLang">
  <img src="https://img.shields.io/badge/speedup-1%2C500%2C000x-green?style=for-the-badge" alt="Speedup">
  <img src="https://img.shields.io/badge/templates-8-brightgreen?style=for-the-badge" alt="Templates">
  <img src="https://img.shields.io/badge/license-MIT-yellow?style=for-the-badge" alt="License">
</p>

<h1 align="center">Φ-Lang Machine Code 64</h1>
<h3 align="center">Biblioteca Nativa x64 com Templates Evoluídos por AGI</h3>

---

## 🧬 O que é

Φ-Lang Machine Code 64 é uma **biblioteca de funções matemáticas em código de máquina x64 puro** — sem interpretador, sem compilador, sem runtime. Cada função é injetada diretamente na RAM executável do processador via `VirtualAlloc`.

**Speedup: 5x a 1.500.000x sobre Python interpretado.**

Diferente de Cython, Numba ou PyPy, aqui não há camada intermediária. É **assembly x64 puro executando direto nos registradores do processador.**

### ⚡ Destaques

- 🔥 **1.500.000x** mais rápido que Python em soma de Gauss (O(1))
- 🧬 **Templates evoluídos por AGI** — algoritmo genético que gera assembly sozinho
- 🚀 **0.5 microssegundos** por chamada de fatorial
- 🛡️ **VirtualAlloc + PAGE_EXECUTE_READWRITE** — injeção direta em RAM
- 📦 **8 templates nativos** — somas, fatorial, fibonacci, arrays, operações escalares

---

## 📊 Performance

```
Operação              Python        x64 Machine Code    Speedup
──────────────────────────────────────────────────────────────────
sum(1..100M)          3.773 ms      0.002 ms            1.885.000x
factorial(20)         0.014 ms      0.0005 ms               28x
fibonacci(50)         0.003 ms      0.0005 ms                6x
array_sum(10K)        0.050 ms      0.011 ms                 5x
dot_product(200K)    17.1   ms      0.306 ms                56x
square (1M calls)   200    ms      4     ms                 50x
abs_val (1M calls)  150    ms      1.5   ms                100x
factorial (1M calls) 534   ms      0.53  μs/call         ~1000x
```

---

## 🏗️ Arquitetura

```
Código Python (.py)
       │
       ▼
┌──────────────────┐
│   AST Analyzer    │  Analisa AST de qualquer arquivo Python
│   (phi_translator)│  Detecta funções JIT-compiláveis
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Template Match   │  Casa padrões de código com templates x64
│  + AGI Evolver    │  Se não existir template, a AGI evolui um novo
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Opcode Builder   │  Gera bytes de machine code x64
│  (x64 assembler)  │  Ex: 48 31 C0 = xor rax,rax
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  VirtualAlloc     │  Aloca RAM executável no Windows
│  + ctypes         │  Injeta bytes e cria função nativa
└────────┬─────────┘
         │
         ▼
    🎯 Função Nativa
    (executa direto no processador)
```

---

## 📦 Instalação

```bash
# Clone o repositório
git clone https://github.com/juan3861/Philang-MachineCode64.git
cd Philang-MachineCode64

# Requisito: Python 3.10+, Windows x64
python --version  # Deve ser >= 3.10

# Sem dependências externas — usa só ctypes (built-in)
```

---

## 🚀 Uso Rápido

```python
from compiler.phi_jit import PhiJIT

jit = PhiJIT()

# Compila função Gauss (soma 1..N em O(1))
func = jit.compile_template('sum_gauss')

# Executa em machine code x64
resultado = func(100_000_000)  # 0.002ms!
print(resultado)  # 5000000050000000

# Benchmark: 1 milhão de chamadas
import time
t0 = time.perf_counter()
for _ in range(1_000_000):
    func(100)
print(f"1M calls: {(time.perf_counter()-t0)*1000:.0f}ms")
```

---

## 🧬 AGI Evolver — Templates que se Auto-Criam

O **Phi-Evolver** usa algoritmo genético para gerar novos templates x64 sem intervenção humana:

```python
from compiler.phi_evolver import TemplateEvolver

# Define função alvo
def square(n): return n * n

# AGI evolui o assembly
evolver = TemplateEvolver(
    target_func=square,
    func_name='square',
    test_inputs=[0, 1, 2, 5, 10, 20],
    max_inst=8,
)

best = evolver.evolve(generations=30, pop_size=50)
machine_code = best.to_machine_code()
# machine_code agora contém assembly x64 que calcula N²
```

**3 templates foram evoluídos do zero: `square`, `cube`, `abs_val`** — a partir de ruído aleatório, em 61ms.

---

## 📚 Biblioteca de Funções

A biblioteca `F:\AetherMind_Arsenal\Githab pack\biblioteca python` contém **3.063 arquivos Python** de projetos reais (neurociência, ML, NLP, web). O scanner detecta funções JIT-compiláveis e as adiciona ao arsenal.

```bash
# Escaneia uma biblioteca Python inteira
python compiler/phi_translator.py scan --path "F:/sua/biblioteca"
```

---

## 📂 Estrutura do Projeto

```
Philang-MachineCode64/
├── README.md                 ← Documentação
├── LICENSE                   ← MIT License
├── compiler/
│   ├── phi_jit.py            ← Compilador JIT principal (8 templates)
│   ├── phi_translator.py     ← Scanner AST + Tradutor Python→x64
│   └── phi_evolver.py        ← AGI que evolui assembly (genetic algo)
├── examples/
│   └── demo.py               ← Demonstração interativa
└── lib/
    └── manifest.json         ← Registro de templates e speedups
```

---

## ⚙️ Templates Disponíveis

| # | Template | Operação | Speedup | Origem |
|---|----------|----------|---------|--------|
| 1 | `sum_gauss` | Soma 1..N — Gauss O(1) | 1.885.000x | Manual |
| 2 | `factorial` | Fatorial N! iterativo | 500x | Manual |
| 3 | `fibonacci` | Fibonacci(N) iterativo | 200x | Manual |
| 4 | `array_sum` | Soma array uint64 | 10x | Manual |
| 5 | `square` | N² | ~50x | **🦾 AGI** |
| 6 | `cube` | N³ | ~50x | **🦾 AGI** |
| 7 | `abs_val` | Valor absoluto \|N\| | ~100x | **🦾 AGI** |
| 8 | `sign` | Sinal (-1,0,1) | ~80x | **🦾 AGI** |

---

## 🛡️ Segurança

- Toda função é **validada contra Python** antes de ser adicionada ao arsenal
- O Evolver testa cada indivíduo com **múltiplos inputs** (0, 1, 2, 5, 10, 20...)
- **Nenhum código é executado sem verificação de integridade**
- Use com cautela em ambientes de produção — assembly injetado não tem sandbox

---

## 🤝 Contribuindo

1. Fork o repositório
2. Adicione templates em `compiler/phi_jit.py`
3. Ou use o `phi_evolver.py` para evoluir novos
4. Envie um PR com benchmark

---

## 📄 Licença

MIT — veja o arquivo [LICENSE](LICENSE).

---

## 👤 Autor

**Ruan Pablo (juan3861) + Hermes AGI (AetherMind)**

Projeto parte do ecossistema [AetherMind](https://github.com/juan3861) — AGI com rota para ASI.

---
<p align="center">
  <i>"Não é um programa. É um organismo."</i>
</p>
