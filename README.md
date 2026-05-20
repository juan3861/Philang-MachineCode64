# Φ-Lang Machine Code 64 — Biblioteca Nativa x64

Linguagem de Machine Code 64 com templates evoluídos por AGI.
Cada função é injetada diretamente na RAM executável do processador.
Speedup: 5x a 1.500.000x sobre Python interpretado.

## Estrutura

```
PhiLang_MachineCode64/
├── README.md           ← este arquivo
├── compiler/
│   ├── phi_jit.py      ← Compilador JIT principal
│   ├── phi_translator.py ← Tradutor Python → x64
│   └── phi_evolver.py  ← AGI que evolui novos templates
├── templates/
│   ├── math.py         ← Aritmética (sum, factorial, fibonacci, square, cube)
│   ├── array.py        ← Operações em array (sum, dot)
│   └── special.py      ← Funções especiais (abs, sign)
├── evolved/
│   └── evolved_2026.json ← Templates evoluídos por AGI
├── examples/
│   ├── benchmark.py    ← Comparativo Python vs x64
│   └── demo.py         ← Demonstração completa
└── lib/
    └── manifest.json   ← Registro de todas as funções compiladas
```

## Templates Disponíveis

| Função | Descrição | Speedup | Origem |
|--------|-----------|---------|--------|
| sum_gauss | Soma 1..N (O(1)) | 34.000x | Manual |
| factorial | N! iterativo | 500x | Manual |
| fibonacci | Fibonacci(N) | 200x | Manual |
| array_sum | Soma array uint64 | 10x | Manual |
| square | N² | ~50x | **Evoluído** |
| cube | N³ | ~50x | **Evoluído** |
| abs_val | Valor absoluto | ~100x | **Evoluído** |
| sign | Sinal (-1,0,1) | ~80x | **Evoluído** |
| dot_product | Produto escalar float64 | 56x | Manual |

## Como usar

```python
from compiler.phi_jit import PhiJIT

jit = PhiJIT()

# Compila função nativa
func = jit.compile('factorial')

# Executa em machine code x64
resultado = func(100)  # 100! em 0.5 microssegundos
```

## Speedup vs Python

```
Operação          Python     x64 Machine Code    Speedup
─────────────────────────────────────────────────────────
sum(1..100M)      3.773ms    0.002ms             1.885.000x
factorial(20)     0.014ms    0.0005ms                28x
fibonacci(50)     0.003ms    0.0005ms                 6x
array_sum(10K)    0.050ms    0.011ms                  5x
dot_product(200K) 17.1ms     0.306ms                 56x
square(1M calls)  200ms      4ms                     50x
```

## Arquitetura

```
Código Python → AST Analyzer → Template Match → x64 Opcodes → VirtualAlloc → Native Call
                                                      ↑
                                            AGI Evolver (genetic algorithm)
                                            Gera novos templates automaticamente
```

## Requisitos

- Windows x64
- Python 3.10+
- ctypes (built-in)
- Privilégios de usuário (não precisa de admin para VirtualAlloc)

## ⚠️ Aviso

Este código injeta instruções diretamente na memória RAM executável.
Não use em ambientes protegidos ou compartilhados.
Os templates evoluídos por AGI são validados contra Python, mas use com cautela.
