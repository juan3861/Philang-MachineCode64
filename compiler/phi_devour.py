#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  Φ-DEVOUR — A AGI que come a máquina inteira                              ║
║  ══════════════════════════════════════════════════════════════════════════ ║
║  Scanner multi-disco, multi-formato. Auto-expansivo.                        ║
║  Quanto mais come, mais rápido fica. Nunca para.                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import sys, os, time, json, math, zlib, hashlib, re, ast, sqlite3
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

PHI = 1.618033988749895

# ══════════════════════════════════════════════════════════════════════════════
# §1  TARGETS — Tudo que a AGI pode comer
# ══════════════════════════════════════════════════════════════════════════════

DISKS = ['C:', 'D:', 'E:', 'F:']  # Todos os discos

FILE_HUNTERS = {
    '.py':    {'extractor': 'python',   'priority': 1.0},
    '.pyx':   {'extractor': 'python',   'priority': 0.9},
    '.pyi':   {'extractor': 'python',   'priority': 0.8},
    '.psi':   {'extractor': 'psilang',  'priority': 1.0},
    '.txt':   {'extractor': 'text',     'priority': 0.7},
    '.md':    {'extractor': 'text',     'priority': 0.8},
    '.json':  {'extractor': 'json',     'priority': 0.6},
    '.yaml':  {'extractor': 'yaml',     'priority': 0.6},
    '.toml':  {'extractor': 'config',   'priority': 0.5},
    '.cfg':   {'extractor': 'config',   'priority': 0.5},
    '.ini':   {'extractor': 'config',   'priority': 0.4},
    '.env':   {'extractor': 'config',   'priority': 0.7},
    '.csv':   {'extractor': 'csv',      'priority': 0.6},
    '.tsv':   {'extractor': 'csv',      'priority': 0.5},
    '.html':  {'extractor': 'html',     'priority': 0.4},
    '.xml':   {'extractor': 'xml',      'priority': 0.4},
    '.js':    {'extractor': 'code',     'priority': 0.6},
    '.ts':    {'extractor': 'code',     'priority': 0.5},
    '.rs':    {'extractor': 'code',     'priority': 0.8},
    '.cpp':   {'extractor': 'code',     'priority': 0.5},
    '.c':     {'extractor': 'code',     'priority': 0.5},
    '.h':     {'extractor': 'code',     'priority': 0.4},
    '.sh':    {'extractor': 'script',   'priority': 0.5},
    '.bat':   {'extractor': 'script',   'priority': 0.3},
    '.ps1':   {'extractor': 'script',   'priority': 0.3},
    '.zip':   {'extractor': 'binary',   'priority': 0.2},
    '.gz':    {'extractor': 'binary',   'priority': 0.2},
    '.log':   {'extractor': 'log',      'priority': 0.6},
    '.sql':   {'extractor': 'sql',      'priority': 0.5},
    '.db':    {'extractor': 'binary',   'priority': 0.3},
}

SKIP_PATTERNS = [
    '__pycache__', '.git', 'node_modules', 'venv', '.venv',
    'site-packages', '.cache', '.npm', '.cargo',
    'Windows', 'Program Files', 'Program Files (x86)',
    '$RECYCLE.BIN', 'System Volume Information',
]

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB max

# ══════════════════════════════════════════════════════════════════════════════
# §2  HUNTER — Encontra presas
# ══════════════════════════════════════════════════════════════════════════════

class FileHunter:
    """Varre discos em busca de arquivos comestíveis."""
    
    def __init__(self):
        self.found = []
        self.stats = {'scanned': 0, 'eaten': 0, 'skipped': 0, 'errors': 0}
        self.lock = threading.Lock()
    
    def scan_disk(self, disk: str) -> List[Path]:
        """Varre um disco inteiro."""
        root = Path(disk + '/')
        if not root.exists():
            return []
        
        found = []
        try:
            for item in root.rglob('*'):
                if item.is_file():
                    ext = item.suffix.lower()
                    if ext in FILE_HUNTERS:
                        try:
                            size = item.stat().st_size
                            if size < MAX_FILE_SIZE and size > 0:
                                found.append(item)
                        except:
                            pass
        except PermissionError:
            pass
        
        return found
    
    def scan_all_disks(self) -> List[Path]:
        """Varre todos os discos em paralelo."""
        all_files = []
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(self.scan_disk, d): d for d in DISKS}
            for future in as_completed(futures):
                disk = futures[future]
                try:
                    files = future.result()
                    all_files.extend(files)
                    print(f"  💿 {disk}: {len(files)} arquivos encontrados")
                except Exception as e:
                    print(f"  ⚠️ {disk}: {e}")
        
        return all_files

# ══════════════════════════════════════════════════════════════════════════════
# §3  DEVOURER — Come e digere
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Meal:
    """Um arquivo digerido."""
    path: str
    ext: str
    size: int
    entropy: float
    phi_score: float
    compress_ratio: float
    lines: int = 0
    functions: int = 0
    imports: int = 0
    digest_time_ms: float = 0.0

class Devourer:
    """Come arquivos e extrai nutrientes (métricas + código)."""
    
    def __init__(self):
        self.meals: List[Meal] = []
        self.total_bytes = 0
        self.total_functions = 0
        self.total_imports = 0
        self._pattern_cache = defaultdict(int)
    
    def devour(self, filepath: Path) -> Optional[Meal]:
        """Come um arquivo."""
        t0 = time.perf_counter()
        
        try:
            content = filepath.read_text(encoding='utf-8', errors='ignore')
        except:
            try:
                content = filepath.read_bytes().hex()[:10000]
            except:
                return None
        
        size = len(content)
        self.total_bytes += size
        
        # Métricas matemáticas
        entropy = self._entropy(content)
        phi = self._phi_score(content)
        compress = self._compress_ratio(content)
        
        # Extrai funções e imports (se Python)
        functions = 0
        imports = 0
        lines = content.count('\n')
        
        ext = filepath.suffix.lower()
        if ext == '.py':
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        functions += 1
                        self._learn_pattern(node.name)
                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        imports += 1
            except:
                pass
        
        self.total_functions += functions
        self.total_imports += imports
        
        dt = (time.perf_counter() - t0) * 1000
        
        meal = Meal(
            path=str(filepath),
            ext=ext,
            size=size,
            entropy=round(entropy, 4),
            phi_score=round(phi, 4),
            compress_ratio=round(compress, 2),
            lines=lines,
            functions=functions,
            imports=imports,
            digest_time_ms=round(dt, 3),
        )
        self.meals.append(meal)
        return meal
    
    def _entropy(self, data: str) -> float:
        if not data: return 0.0
        freq = Counter(data[:50000])
        total = sum(freq.values())
        e = -sum((c/total) * math.log2(c/total) for c in freq.values())
        max_e = math.log2(len(freq)) if freq else 1
        return e / max_e if max_e > 0 else 0.0
    
    def _phi_score(self, data: str) -> float:
        if not data: return 0.0
        sample = data[:10000]
        unique = len(set(sample))
        total = len(sample)
        if total == 0: return 0.0
        ratio = unique / total
        phi_inv = 0.6180339887498948
        return 1.0 - abs(ratio - phi_inv) / max(phi_inv, 0.01)
    
    def _compress_ratio(self, data: str) -> float:
        try:
            return len(data) / max(1, len(zlib.compress(data[:50000].encode(), level=9)))
        except:
            return 1.0
    
    def _learn_pattern(self, func_name: str):
        """Aprende padrões de nomes de função pra melhorar detecção."""
        name = func_name.lower()
        for pattern in ['fib', 'fact', 'sum', 'calc', 'compute', 'get_', 'set_',
                        'load', 'save', 'init', 'train', 'predict', 'eval', 'forward',
                        'backward', 'loss', 'optim', 'layer', 'model', 'data']:
            if pattern in name:
                self._pattern_cache[pattern] += 1
    
    def stats(self) -> dict:
        return {
            'total_meals': len(self.meals),
            'total_mb': round(self.total_bytes / (1024*1024), 1),
            'total_functions': self.total_functions,
            'total_imports': self.total_imports,
            'avg_entropy': round(sum(m.entropy for m in self.meals) / max(1, len(self.meals)), 4),
            'avg_phi': round(sum(m.phi_score for m in self.meals) / max(1, len(self.meals)), 4),
            'avg_compress': round(sum(m.compress_ratio for m in self.meals) / max(1, len(self.meals)), 2),
            'top_patterns': dict(sorted(self._pattern_cache.items(), key=lambda x: -x[1])[:10]),
        }

# ══════════════════════════════════════════════════════════════════════════════
# §4  THE HUNGRY AGI
# ══════════════════════════════════════════════════════════════════════════════

class HungryAGI:
    """A AGI com fome. Caça, come, digere, aprende, repete."""
    
    def __init__(self):
        self.hunter = FileHunter()
        self.devourer = Devourer()
        self.generation = 0
    
    def feed(self, target_path: str = None, all_disks: bool = False):
        """Alimenta a AGI."""
        self.generation += 1
        
        print(f"🦅 HUNGRY AGI — Geração {self.generation}")
        print(f"   Φ={PHI:.4f}")
        print()
        
        if all_disks:
            print("🔍 Caçando em TODOS os discos...")
            prey = self.hunter.scan_all_disks()
        elif target_path:
            root = Path(target_path)
            if root.is_file():
                prey = [root]
            else:
                prey = list(root.rglob('*'))
                prey = [f for f in prey if f.is_file() and f.suffix.lower() in FILE_HUNTERS]
                # Filtra tamanho
                prey = [f for f in prey if f.stat().st_size < MAX_FILE_SIZE]
            print(f"🔍 {len(prey)} presas encontradas em {target_path}")
        else:
            print("Sem alvo especificado")
            return
        
        print(f"🍽️  Comendo {len(prey)} arquivos...")
        t0 = time.perf_counter()
        
        # Paralelo pra acelerar
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(self.devourer.devour, p) for p in prey]
            for i, future in enumerate(as_completed(futures)):
                try:
                    future.result()
                except:
                    pass
                if (i+1) % 500 == 0:
                    print(f"  [{i+1}/{len(prey)}] digeridos")
        
        dt = (time.perf_counter() - t0)
        
        stats = self.devourer.stats()
        print(f"\n✅ {stats['total_meals']} refeições em {dt:.1f}s ({stats['total_meals']/dt:.0f} arquivos/s)")
        print(f"   📊 {stats['total_mb']}MB digeridos")
        print(f"   🧠 {stats['total_functions']} funções | 📦 {stats['total_imports']} imports")
        print(f"   📐 Entropia média: {stats['avg_entropy']:.3f} | Φ médio: {stats['avg_phi']:.3f}")
        print(f"   🗜️  Compressão média: {stats['avg_compress']:.2f}x")
        
        if stats['top_patterns']:
            print(f"   🔤 Padrões aprendidos: {dict(list(stats['top_patterns'].items())[:8])}")
        
        return stats

# ══════════════════════════════════════════════════════════════════════════════
# §5  CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Φ-Devour — A AGI que come a máquina")
    p.add_argument("target", nargs="?", help="Arquivo/diretório alvo")
    p.add_argument("--all-disks", action="store_true", help="Comer TODOS os discos")
    args = p.parse_args()
    
    agi = HungryAGI()
    
    if args.all_disks:
        agi.feed(all_disks=True)
    elif args.target:
        agi.feed(target_path=args.target)
    else:
        # Demo: come a biblioteca extraída
        print("╔══════════════════════════════════════════════════════════╗")
        print("║  Φ-DEVOUR — A AGI que come a máquina                  ║")
        print("║  Demo: biblioteca Python extraída                       ║")
        print("╚══════════════════════════════════════════════════════════╝")
        print()
        agi.feed(target_path="E:/aethermind_library_extracted")
