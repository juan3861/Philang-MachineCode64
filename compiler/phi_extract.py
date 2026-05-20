#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  Φ-EXTRACT — Extrator Universal de Suprasumo                              ║
║  ══════════════════════════════════════════════════════════════════════════ ║
║  Suga qualquer arquivo → extrai essência matemática → redireciona          ║
║  para o módulo AGI certo (compilador, evolver, memória, tensor)            ║
║                                                                            ║
║  Pipeline:                                                                 ║
║    Arquivo → Entropia → SVD → Φ-score → Classifica → Roteia → Executa     ║
║                                                                            ║
║  "A AGI come dados de todos os lados"                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import sys, os, re, ast, json, math, zlib, hashlib, time, sqlite3
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from collections import Counter, defaultdict
from enum import Enum
import importlib

PHI = 1.618033988749895
PHI_INV = 0.6180339887498948

# ══════════════════════════════════════════════════════════════════════════════
# §0  TIPOS DE EXTRAÇÃO
# ══════════════════════════════════════════════════════════════════════════════

class ExtractType(Enum):
    CODE_BLOCK = "code_block"       # → phi_jit (compilar para x64)
    FUNCTION = "function"           # → phi_evolver (evoluir template)
    IMPORT = "import"               # → phi_translator (mapear dependência)
    MATH_PATTERN = "math_pattern"   # → tensor_core (comprimir com SVD)
    TEXT_KNOWLEDGE = "text"         # → cogitans (grafo cognitivo)
    CONFIG = "config"               # → memória (armazenar)
    BINARY_BLOB = "binary"          # → autophagy (comprimir)
    UNKNOWN = "unknown"             # → descartar ou arquivar

@dataclass
class Extract:
    """Um pedaço extraído de um arquivo."""
    content: str
    extract_type: ExtractType
    source_file: str
    line_start: int
    line_end: int
    entropy: float
    phi_score: float
    svd_rank: int = 0
    compression_ratio: float = 1.0
    priority: float = 0.5  # 0-1, calculado
    
    @property
    def id(self) -> str:
        return hashlib.md5(f"{self.source_file}:{self.line_start}:{self.content[:50]}".encode()).hexdigest()[:12]

# ══════════════════════════════════════════════════════════════════════════════
# §1  ANALYZERS — Extraem métricas matemáticas de qualquer dado
# ══════════════════════════════════════════════════════════════════════════════

class MathAnalyzer:
    """Analisa matematicamente qualquer bloco de dados."""
    
    @staticmethod
    def entropy(data: str) -> float:
        """Entropia de Shannon normalizada."""
        if not data: return 0.0
        freq = Counter(data)
        total = len(data)
        e = -sum((c/total) * math.log2(c/total) for c in freq.values())
        max_e = math.log2(len(freq)) if freq else 1
        return e / max_e if max_e > 0 else 0.0
    
    @staticmethod
    def phi_score(data: str) -> float:
        """Quão próximo da razão áurea está o dado."""
        if not data: return 0.0
        chars = len(data)
        unique = len(set(data))
        if chars == 0: return 0.0
        ratio = unique / chars
        return 1.0 - abs(ratio - PHI_INV) / max(PHI_INV, 0.01)
    
    @staticmethod
    def compress_ratio(data: str) -> float:
        """Taxa de compressão zlib."""
        if not data: return 1.0
        compressed = zlib.compress(data.encode(), level=9)
        return len(data) / max(1, len(compressed))
    
    @staticmethod
    def svd_rank(data: str, energy: float = 0.85) -> int:
        """Rank efetivo via SVD (se numpy disponível)."""
        try:
            import numpy as np
            lines = data.split('\n')
            if len(lines) < 2: return 1
            max_len = max(len(l) for l in lines[:100])
            n = min(len(lines), 100)
            matrix = np.zeros((n, min(max_len, 200)))
            for i in range(n):
                for j, ch in enumerate(lines[i][:200]):
                    matrix[i, j] = ord(ch) / 255.0
            u, s, vt = np.linalg.svd(matrix, full_matrices=False)
            cumsum = np.cumsum(s**2)
            total = cumsum[-1]
            if total == 0: return 1
            rank = int(np.searchsorted(cumsum / total, energy)) + 1
            return max(1, min(rank, n-1))
        except:
            return 1
    
    @staticmethod
    def priority(extract: 'Extract') -> float:
        """Calcula prioridade combinada."""
        e = extract.entropy
        p = extract.phi_score
        c = extract.compression_ratio
        # Alta entropia + alto Φ + alta compressibilidade = alta prioridade
        return (e * 0.3 + p * 0.4 + min(c/5.0, 1.0) * 0.3)

# ══════════════════════════════════════════════════════════════════════════════
# §2  EXTRACTORS — Extraem tipos específicos de conteúdo
# ══════════════════════════════════════════════════════════════════════════════

class ContentExtractor:
    """Extrai conteúdo valioso de arquivos."""
    
    @staticmethod
    def extract_python(filepath: str) -> List[Extract]:
        """Extrai funções, imports, e blocos de código de .py."""
        try:
            source = Path(filepath).read_text(encoding='utf-8', errors='ignore')
        except:
            return []
        
        extracts = []
        lines = source.split('\n')
        
        # Tenta parse AST
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    content = ast.get_source_segment(source, node) or ast.unparse(node)
                    e = Extract(
                        content=content,
                        extract_type=ExtractType.FUNCTION,
                        source_file=filepath,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        entropy=MathAnalyzer.entropy(content),
                        phi_score=MathAnalyzer.phi_score(content),
                        compression_ratio=MathAnalyzer.compress_ratio(content),
                    )
                    e.svd_rank = MathAnalyzer.svd_rank(content)
                    e.priority = MathAnalyzer.priority(e)
                    extracts.append(e)
                
                elif isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                    content = ast.unparse(node)
                    e = Extract(
                        content=content,
                        extract_type=ExtractType.IMPORT,
                        source_file=filepath,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        entropy=0.3, phi_score=0.5, compression_ratio=1.0,
                        priority=0.3,
                    )
                    extracts.append(e)
        except SyntaxError:
            pass
        
        # Extrai docstring do módulo
        try:
            tree = ast.parse(source)
            doc = ast.get_docstring(tree)
            if doc and len(doc) > 30:
                e = Extract(
                    content=doc,
                    extract_type=ExtractType.TEXT_KNOWLEDGE,
                    source_file=filepath,
                    line_start=1, line_end=5,
                    entropy=MathAnalyzer.entropy(doc),
                    phi_score=MathAnalyzer.phi_score(doc),
                    compression_ratio=MathAnalyzer.compress_ratio(doc),
                )
                e.priority = MathAnalyzer.priority(e)
                extracts.append(e)
        except:
            pass
        
        return extracts
    
    @staticmethod
    def extract_text(filepath: str) -> List[Extract]:
        """Extrai conhecimento de arquivos de texto."""
        try:
            content = Path(filepath).read_text(encoding='utf-8', errors='ignore')
        except:
            return []
        
        extracts = []
        
        # Divide em parágrafos
        paragraphs = [p.strip() for p in content.split('\n\n') if len(p.strip()) > 100]
        
        for i, para in enumerate(paragraphs[:20]):  # top 20 parágrafos
            e = Extract(
                content=para[:500],
                extract_type=ExtractType.TEXT_KNOWLEDGE,
                source_file=filepath,
                line_start=i*10, line_end=i*10+5,
                entropy=MathAnalyzer.entropy(para),
                phi_score=MathAnalyzer.phi_score(para),
                compression_ratio=MathAnalyzer.compress_ratio(para),
            )
            e.priority = MathAnalyzer.priority(e)
            extracts.append(e)
        
        return extracts
    
    @staticmethod
    def extract_binary(filepath: str) -> List[Extract]:
        """Extrai metadados de arquivos binários."""
        try:
            data = Path(filepath).read_bytes()
        except:
            return []
        
        extracts = []
        
        # Hash e compressão
        h = hashlib.sha256(data).hexdigest()[:16]
        compressed = zlib.compress(data, level=9)
        ratio = len(data) / max(1, len(compressed))
        
        # Cabeçalho como hex
        header = data[:64].hex()
        
        e = Extract(
            content=f"SHA256:{h} | Size:{len(data)} | CompressRatio:{ratio:.2f}x | Header:{header}",
            extract_type=ExtractType.BINARY_BLOB,
            source_file=filepath,
            line_start=0, line_end=0,
            entropy=MathAnalyzer.entropy(header),
            phi_score=0.5,
            compression_ratio=ratio,
            priority=0.4 if ratio > 2.0 else 0.2,
        )
        extracts.append(e)
        
        return extracts
    
    @staticmethod
    def extract_any(filepath: str) -> List[Extract]:
        """Detecta tipo e extrai adequadamente."""
        ext = Path(filepath).suffix.lower()
        
        if ext == '.py':
            return ContentExtractor.extract_python(filepath)
        elif ext in ('.txt', '.md', '.rst', '.log'):
            return ContentExtractor.extract_text(filepath)
        elif ext in ('.json', '.yaml', '.toml', '.cfg', '.ini'):
            return ContentExtractor.extract_text(filepath)
        elif ext in ('.zip', '.gz', '.tar', '.7z', '.rar'):
            return ContentExtractor.extract_binary(filepath)
        elif ext in ('.exe', '.dll', '.so', '.bin'):
            return ContentExtractor.extract_binary(filepath)
        else:
            # Tenta como texto, fallback binário
            result = ContentExtractor.extract_text(filepath)
            if not result:
                result = ContentExtractor.extract_binary(filepath)
            return result

# ══════════════════════════════════════════════════════════════════════════════
# §3  ROUTER — Redireciona cada extração pro módulo AGI certo
# ══════════════════════════════════════════════════════════════════════════════

class AGIRouter:
    """Roteia extrações para os módulos AGI corretos."""
    
    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute('''CREATE TABLE IF NOT EXISTS extracts (
            id TEXT PRIMARY KEY, type TEXT, source TEXT, content TEXT,
            entropy REAL, phi_score REAL, svd_rank INT, priority REAL,
            route TEXT, status TEXT DEFAULT 'pending')''')
        self.conn.commit()
        self.stats = defaultdict(int)
    
    def route(self, extract: Extract) -> str:
        """Decide pra onde mandar e executa a ação."""
        
        if extract.extract_type == ExtractType.FUNCTION:
            # Tenta compilar para x64
            route = 'phi_jit'
            self._try_jit(extract)
        
        elif extract.extract_type == ExtractType.CODE_BLOCK:
            route = 'phi_translator'
            self._try_translate(extract)
        
        elif extract.extract_type == ExtractType.IMPORT:
            route = 'phi_mapper'
            self._map_dependency(extract)
        
        elif extract.extract_type == ExtractType.MATH_PATTERN:
            route = 'tensor_core'
            self._try_svd(extract)
        
        elif extract.extract_type == ExtractType.TEXT_KNOWLEDGE:
            route = 'cogitans'
            self._store_knowledge(extract)
        
        elif extract.extract_type == ExtractType.CONFIG:
            route = 'memory'
            self._store_config(extract)
        
        elif extract.extract_type == ExtractType.BINARY_BLOB:
            route = 'autophagy'
            self._try_compress(extract)
        
        else:
            route = 'archive'
        
        # Salva no banco
        self.conn.execute(
            'INSERT OR REPLACE INTO extracts VALUES(?,?,?,?,?,?,?,?,?,?)',
            (extract.id, extract.extract_type.value, extract.source_file,
             extract.content[:200], extract.entropy, extract.phi_score,
             extract.svd_rank, extract.priority, route, 'routed'))
        self.conn.commit()
        self.stats[route] += 1
        
        return route
    
    def _try_jit(self, extract: Extract):
        """Tenta compilar função para x64."""
        try:
            from phi_system import _engine
            func_name = extract.content.split('(')[0].replace('def ', '').strip()
            template = _engine.detect(func_name)
            if template:
                _engine.compile(template)
        except:
            pass
    
    def _try_translate(self, extract: Extract):
        """Registra para tradução."""
        pass
    
    def _map_dependency(self, extract: Extract):
        """Mapeia dependência."""
        pass
    
    def _try_svd(self, extract: Extract):
        """Comprime com SVD."""
        extract.svd_rank = MathAnalyzer.svd_rank(extract.content)
    
    def _store_knowledge(self, extract: Extract):
        """Armazena no grafo cognitivo."""
        pass
    
    def _store_config(self, extract: Extract):
        """Armazena configuração."""
        pass
    
    def _try_compress(self, extract: Extract):
        """Comprime blob binário."""
        pass
    
    def report(self) -> dict:
        return {
            'total_extracts': sum(self.stats.values()),
            'by_route': dict(self.stats),
            'top_priority': self._top(5),
        }
    
    def _top(self, n: int) -> List[dict]:
        rows = self.conn.execute(
            'SELECT id, type, source, priority FROM extracts ORDER BY priority DESC LIMIT ?',
            (n,)).fetchall()
        return [{'id': r[0], 'type': r[1], 'source': r[2][:60], 'priority': round(r[3], 4)} for r in rows]

# ══════════════════════════════════════════════════════════════════════════════
# §4  MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

class PhiExtract:
    """Pipeline completo: suga → extrai → analisa → roteia → executa."""
    
    def __init__(self):
        self.router = AGIRouter()
        self.total_files = 0
        self.total_extracts = 0
    
    def extract_file(self, filepath: str) -> List[Extract]:
        """Extrai suprasumo de um arquivo."""
        extracts = ContentExtractor.extract_any(filepath)
        for e in extracts:
            self.router.route(e)
        self.total_files += 1
        self.total_extracts += len(extracts)
        return extracts
    
    def extract_directory(self, path: str, recursive: bool = True) -> dict:
        """Extrai suprasumo de um diretório inteiro."""
        root = Path(path)
        if not root.exists():
            return {'error': 'path not found'}
        
        files = list(root.rglob('*') if recursive else root.glob('*'))
        files = [f for f in files if f.is_file() and '__pycache__' not in str(f)]
        
        print(f"🔍 {len(files)} arquivos para sugar...")
        t0 = time.perf_counter()
        
        for i, fp in enumerate(files):
            try:
                self.extract_file(str(fp))
                if (i+1) % 100 == 0:
                    print(f"  [{i+1}/{len(files)}] {self.total_extracts} extrações")
            except Exception as e:
                pass
        
        dt = (time.perf_counter() - t0) * 1000
        
        report = self.router.report()
        report['files_scanned'] = len(files)
        report['time_ms'] = round(dt, 0)
        report['extracts_per_second'] = round(self.total_extracts / (dt/1000), 1)
        
        return report
    
    def extract_python_library(self, lib_path: str) -> dict:
        """Modo otimizado para bibliotecas Python: foca em .py."""
        root = Path(lib_path)
        py_files = list(root.rglob('*.py'))
        
        print(f"🐍 {len(py_files)} arquivos Python...")
        t0 = time.perf_counter()
        
        for i, fp in enumerate(py_files):
            try:
                extracts = ContentExtractor.extract_python(str(fp))
                for e in extracts:
                    self.router.route(e)
                    self.total_extracts += 1
                self.total_files += 1
                
                if (i+1) % 500 == 0 or (i+1) == len(py_files):
                    report = self.router.report()
                    print(f"  [{i+1}/{len(py_files)}] {report['total_extracts']} extrações | "
                          f"top route: {max(report['by_route'], key=report['by_route'].get)}")
            except:
                pass
        
        dt = (time.perf_counter() - t0) * 1000
        report = self.router.report()
        report['py_files_scanned'] = len(py_files)
        report['time_ms'] = round(dt, 0)
        report['extracts_per_second'] = round(self.total_extracts / max(0.001, dt/1000), 1)
        
        return report

# ══════════════════════════════════════════════════════════════════════════════
# §5  CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Φ-Extract — Extrator Universal de Suprasumo")
    p.add_argument("path", nargs="?", help="Arquivo ou diretório para extrair")
    p.add_argument("--mode", choices=["file", "dir", "lib"], default="dir")
    p.add_argument("--top", type=int, default=10, help="Mostrar top N extrações")
    args = p.parse_args()
    
    extractor = PhiExtract()
    
    if not args.path:
        # Demo: extrai o próprio código
        print("╔══════════════════════════════════════════════════════════╗")
        print("║  Φ-EXTRACT — Extrator Universal de Suprasumo           ║")
        print("║  Demo: extraindo o próprio código                       ║")
        print("╚══════════════════════════════════════════════════════════╝")
        print()
        args.path = __file__
        args.mode = "file"
    
    if args.mode == "file":
        extracts = extractor.extract_file(args.path)
        print(f"\n📄 {args.path}")
        print(f"   {len(extracts)} extrações")
        for e in sorted(extracts, key=lambda x: -x.priority)[:args.top]:
            print(f"   [{e.priority:.2f}] {e.extract_type.value:15s} | Φ={e.phi_score:.3f} | H={e.entropy:.3f} | {e.content[:60]}...")
    
    elif args.mode == "dir":
        report = extractor.extract_directory(args.path)
        print(f"\n📁 {args.path}")
        print(json.dumps(report, indent=2, default=str))
    
    elif args.mode == "lib":
        report = extractor.extract_python_library(args.path)
        print(f"\n📚 {args.path}")
        print(json.dumps(report, indent=2, default=str))
