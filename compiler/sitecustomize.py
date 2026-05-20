# Φ-SYSTEM — Sitecustomize (carregado automaticamente por qualquer Python)
# Coloque este arquivo em: Python/Lib/site-packages/
# Ou na raiz do projeto.
# 
# Toda execução Python na máquina terá funções matemáticas
# automaticamente convertidas para machine code x64.

try:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from phi_system import activate, status
    stats = activate()
    if stats.get('accelerated', 0) > 0:
        print(f"[Φ-SYSTEM] {stats['accelerated']} funções aceleradas para x64 | {stats['compiled']} templates")
except Exception:
    pass  # Falha silenciosa — não quebra o Python do usuário
