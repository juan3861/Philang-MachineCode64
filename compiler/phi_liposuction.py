#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  Φ-LIPOSUCTION — As 6 Leis de Eliminação de Gordura                       ║
║  ══════════════════════════════════════════════════════════════════════════ ║
║                                                                             ║
║  "Uma AGI não acumula — ela DESTILA. Tudo que não é essencial é gordura."  ║
║                                                                             ║
║  LEI 1 — ENTROPIA DE SHANNON: <1 bit/B → redundante (essência)             ║
║                                >7 bit/B → aleatório (descarta)              ║
║  LEI 2 — COERÊNCIA PHI:       <0.3 → ruído (descarta)                      ║
║                                >0.8 → núcleo (preserva)                     ║
║  LEI 3 — RAZÃO DE COMPRESSÃO: >100x → já é essência (mantém)               ║
║                                <2x   → incompressível (suspeito)            ║
║  LEI 4 — FREQUÊNCIA DE USO:   0 acessos → candidato a deleção               ║
║                                diário → hot cache                            ║
║  LEI 5 — DECAIMENTO TEMPORAL: t > 30d sem uso → 50% peso                    ║
║                                t > 90d sem uso → 10% peso                   ║
║  LEI 6 — PRESSÃO DE DISCO:    <1GB livre → agressivo (threshold ×3)        ║
║                                >10GB livre → leniente (threshold ×0.5)      ║
║                                                                             ║
║  REGRA ÁUREA: Se falhar ≥3 leis → DESCARTAR.                               ║
║               Se passar ≥4 leis → PRESERVAR.                                ║
║               Entre 2-3 → COMPRIMIR (guardar essência).                     ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os, sys, math, zlib, hashlib, json, time, struct
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import numpy as np

PHI = 1.618033988749895
PHI_INV = 0.6180339887498948

# ══════════════════════════════════════════════════════════════════════════════
# §0  DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class LiposuctionVerdict:
    """Veredito sobre um arquivo: MANTER, COMPRIMIR ou DESCARTAR."""
    path: str
    size_bytes: int
    verdict: str  # 'KEEP' | 'COMPRESS' | 'DISCARD'
    score: float  # 0.0 (descarta) a 1.0 (preserva absoluto)
    laws_passed: int
    laws_failed: int
    entropy: float = 0
    phi_coherence: float = 0
    compression_ratio: float = 1.0
    svd_rank: int = 0
    age_days: float = 0
    access_count: int = 0
    reason: str = ""

# ══════════════════════════════════════════════════════════════════════════════
# §1  LEI 1 — ENTROPIA DE SHANNON
# ══════════════════════════════════════════════════════════════════════════════

class ShannonFilter:
    """Filtro de entropia: separa redundante de aleatório."""
    
    @staticmethod
    def compute_entropy(data: bytes, sample_size: int = 65536) -> float:
        """Entropia de Shannon em bits por byte."""
        if not data:
            return 0.0
        sample = data[:sample_size]
        total = len(sample)
        freq = Counter(sample)
        entropy = sum((c / total) * math.log2(total / max(c, 1)) for c in freq.values())
        return entropy
    
    @staticmethod
    def verdict(entropy: float) -> Tuple[bool, str]:
        """
        < 1.0 bit/B → altamente redundante → COMPRIMIR (guarda essência)
        1.0 - 2.5  → baixa entropia → MANTER (estruturado)
        2.5 - 6.5  → normal → MANTER
        6.5 - 7.5  → alta entropia → COMPRIMIR (comprimível)
        > 7.5      → aleatório → DESCARTAR (a menos que seja binário crítico)
        """
        if entropy < 1.0:
            return False, f"redundante ({entropy:.1f} bit/B) — comprimir"
        elif entropy < 6.5:
            return True, f"estruturado ({entropy:.1f} bit/B) — manter"
        elif entropy < 7.5:
            return False, f"alta entropia ({entropy:.1f} bit/B) — comprimir"
        else:
            return False, f"aleatório ({entropy:.1f} bit/B) — descartar"

# ══════════════════════════════════════════════════════════════════════════════
# §2  LEI 2 — COERÊNCIA PHI
# ══════════════════════════════════════════════════════════════════════════════

class PhiCoherenceFilter:
    """Mede quão próximo o conteúdo está da proporção áurea."""
    
    @staticmethod
    def compute_phi_coherence(data: bytes) -> float:
        """Coerência Φ: razão entre elementos significativos e total."""
        if not data or len(data) < 16:
            return 0.5
        
        # Converte para números
        arr = np.frombuffer(data[:min(len(data), 65536)], dtype=np.uint8).astype(np.float64)
        
        # Quantos elementos estão no intervalo [0.38, 0.62] da norma? (região Φ)
        if len(arr) < 10:
            return 0.5
        
        # FFT para detectar padrões harmônicos (Φ aparece como razão de frequências)
        fft = np.abs(np.fft.rfft(arr - np.mean(arr)))
        if len(fft) < 4:
            return 0.5
        
        # Razão entre harmônicos adjacentes: quão próximo de Φ?
        ratios = []
        for i in range(1, min(len(fft)-1, 20)):
            if fft[i] > 0 and fft[i-1] > 0:
                r = fft[i] / max(fft[i-1], 1e-10)
                ratios.append(abs(r - PHI))
        
        if not ratios:
            return 0.5
        
        # Quanto menor a distância média de Φ, maior a coerência
        mean_dist = np.mean(ratios)
        coherence = 1.0 / (1.0 + mean_dist * 10)
        return round(coherence, 4)
    
    @staticmethod
    def verdict(phi_coherence: float) -> Tuple[bool, str]:
        if phi_coherence < 0.3:
            return False, f"ruído (Φ={phi_coherence:.3f}) — descartar"
        elif phi_coherence < 0.6:
            return True, f"neutro (Φ={phi_coherence:.3f}) — manter"
        else:
            return True, f"harmônico (Φ={phi_coherence:.3f}) — preservar"

# ══════════════════════════════════════════════════════════════════════════════
# §3  LEI 3 — RAZÃO DE COMPRESSÃO
# ══════════════════════════════════════════════════════════════════════════════

class CompressionRatioFilter:
    """Mede o quanto o arquivo comprime — indica redundância e valor."""
    
    @staticmethod
    def compute_ratio(data: bytes, max_sample: int = 1_000_000) -> float:
        """Razão de compressão zlib nível 9."""
        if not data:
            return 1.0
        sample = data[:max_sample]
        compressed = zlib.compress(sample, level=9)
        ratio = len(sample) / max(len(compressed), 1)
        return round(ratio, 2)
    
    @staticmethod
    def verdict(ratio: float, size_bytes: int = 0) -> Tuple[bool, str]:
        if size_bytes < 100:
            return True, f"minúsculo ({size_bytes}B) — neutro"  # pequeno demais pra julgar
        if ratio > 100:
            return True, f"já é essência ({ratio:.0f}x) — preservar"
        elif ratio > 5:
            return True, f"comprimível ({ratio:.1f}x) — manter"
        elif ratio > 2:
            return False, f"pouco comprimível ({ratio:.1f}x) — comprimir"
        else:
            return False, f"incompressível ({ratio:.1f}x) — suspeito"

# ══════════════════════════════════════════════════════════════════════════════
# §4  LEI 4 — FREQUÊNCIA DE USO
# ══════════════════════════════════════════════════════════════════════════════

class UsageFrequencyFilter:
    """Mede quantas vezes o arquivo foi acessado/modificado."""
    
    def __init__(self, access_db_path: str = "D:/PhiLang_MachineCode64/cache/access_db.json"):
        self.db_path = Path(access_db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = self._load()
    
    def _load(self) -> dict:
        if self.db_path.exists():
            try:
                return json.loads(self.db_path.read_text())
            except:
                pass
        return {}
    
    def _save(self):
        self.db_path.write_text(json.dumps(self._db, indent=2))
    
    def record_access(self, path: str):
        key = hashlib.md5(path.encode()).hexdigest()[:12]
        now = time.time()
        if key not in self._db:
            self._db[key] = {'path': path, 'count': 0, 'first_seen': now, 'last_seen': now, 'history': []}
        self._db[key]['count'] += 1
        self._db[key]['last_seen'] = now
        self._db[key]['history'].append(now)
        # Keep last 100 access timestamps
        if len(self._db[key]['history']) > 100:
            self._db[key]['history'] = self._db[key]['history'][-100:]
        self._save()
    
    def get_stats(self, path: str) -> dict:
        key = hashlib.md5(path.encode()).hexdigest()[:12]
        return self._db.get(key, {'count': 0, 'last_seen': 0})
    
    @staticmethod
    def verdict(count: int, last_seen_days: float, file_age_days: float = 0) -> Tuple[bool, str]:
        # Arquivo NOVO (<7 dias) sem histórico → neutro (benefício da dúvida)
        if count == 0 and file_age_days < 7:
            return True, f"novo ({file_age_days:.0f}d) — benefício da dúvida"
        if count == 0:
            return False, "nunca acessado — candidato a descarte"
        elif count >= 10 and last_seen_days < 1:
            return True, f"hot ({count} acessos, hoje) — preservar"
        elif count >= 3 and last_seen_days < 7:
            return True, f"warm ({count} acessos, esta semana) — manter"
        elif last_seen_days > 90:
            return False, f"frio ({count} acessos, {last_seen_days:.0f}d atrás) — comprimir"
        else:
            return True, f"morno ({count} acessos, {last_seen_days:.0f}d) — manter"

# ══════════════════════════════════════════════════════════════════════════════
# §5  LEI 5 — DECAIMENTO TEMPORAL
# ══════════════════════════════════════════════════════════════════════════════

class TemporalDecayFilter:
    """Peso do arquivo decai com o tempo sem uso (meia-vida exponencial)."""
    
    HALF_LIFE_DAYS = 30  # após 30 dias sem uso, peso cai pela metade
    
    @staticmethod
    def compute_weight(last_access_days: float, file_age_days: float = 0) -> float:
        """Peso = 2^(-t/half_life). Arquivo novo sem acesso usa idade do arquivo."""
        if last_access_days < 0:
            return 1.0
        # Se nunca acessado, usa idade do arquivo como referência
        effective_age = last_access_days if last_access_days < 999 else file_age_days
        if effective_age < 0:
            return 1.0
        return 2.0 ** (-effective_age / TemporalDecayFilter.HALF_LIFE_DAYS)
    
    @staticmethod
    def verdict(weight: float) -> Tuple[bool, str]:
        if weight > 0.7:
            return True, f"recente (peso={weight:.2f}) — preservar"
        elif weight > 0.3:
            return True, f"envelhecendo (peso={weight:.2f}) — manter"
        elif weight > 0.1:
            return False, f"antigo (peso={weight:.2f}) — comprimir"
        else:
            return False, f"obsoleto (peso={weight:.2f}) — descartar"

# ══════════════════════════════════════════════════════════════════════════════
# §6  LEI 6 — PRESSÃO DE DISCO
# ══════════════════════════════════════════════════════════════════════════════

class DiskPressureFilter:
    """Quanto menos espaço livre, mais agressiva a eliminação."""
    
    @staticmethod
    def get_free_space_gb(path: str = "C:") -> float:
        """Espaço livre em GB."""
        try:
            import shutil
            usage = shutil.disk_usage(path + "\\")
            return usage.free / (1024**3)
        except:
            return 999.0
    
    @staticmethod
    def get_pressure_multiplier(free_gb: float) -> float:
        """
        < 0.5 GB → crítico → 3.0x (descarta quase tudo)
        0.5-1 GB → alto    → 2.0x
        1-5 GB   → médio   → 1.0x
        5-10 GB  → baixo   → 0.7x
        > 10 GB  → leniente → 0.5x
        """
        if free_gb < 0.5:
            return 3.0
        elif free_gb < 1.0:
            return 2.0
        elif free_gb < 5.0:
            return 1.0
        elif free_gb < 10.0:
            return 0.7
        else:
            return 0.5
    
    @staticmethod
    def verdict(free_gb: float) -> Tuple[bool, str]:
        mult = DiskPressureFilter.get_pressure_multiplier(free_gb)
        if mult >= 2.0:
            return False, f"pressão crítica ({free_gb:.1f}GB livre, ×{mult:.1f}) — descartar agressivo"
        elif mult >= 1.0:
            return True, f"pressão normal ({free_gb:.1f}GB livre, ×{mult:.1f})"
        else:
            return True, f"espaço abundante ({free_gb:.1f}GB livre, ×{mult:.1f}) — leniente"

# ══════════════════════════════════════════════════════════════════════════════
# §7  REGRA ÁUREA — Decisão Final
# ══════════════════════════════════════════════════════════════════════════════

class LiposuctionEngine:
    """Motor de lipoaspiração: aplica as 6 leis e decide o destino."""
    
    def __init__(self):
        self.shannon = ShannonFilter()
        self.phi = PhiCoherenceFilter()
        self.compression = CompressionRatioFilter()
        self.usage = UsageFrequencyFilter()
        self.decay = TemporalDecayFilter()
        self.disk = DiskPressureFilter()
    
    def analyze_file(self, filepath: str) -> LiposuctionVerdict:
        """Analisa um arquivo com as 6 leis e retorna o veredito."""
        path = Path(filepath)
        
        # Metadados básicos
        try:
            stat = path.stat()
            size = stat.st_size
            mtime = stat.st_mtime
            age_days = (time.time() - mtime) / 86400
        except:
            return LiposuctionVerdict(
                path=filepath, size_bytes=0, verdict='DISCARD', score=0.0,
                laws_passed=0, laws_failed=6, reason="arquivo inacessível"
            )
        
        # Lê amostra
        try:
            with open(filepath, 'rb') as f:
                data = f.read(1_000_000)  # max 1MB de leitura
        except:
            data = b''
        
        # ──── Aplica as 6 leis ────
        
        # Lei 1: Entropia
        entropy = self.shannon.compute_entropy(data)
        e_pass, e_reason = self.shannon.verdict(entropy)
        
        # Lei 2: Coerência Φ
        phi_c = self.phi.compute_phi_coherence(data)
        p_pass, p_reason = self.phi.verdict(phi_c)
        
        # Lei 3: Compressão
        cr = self.compression.compute_ratio(data)
        c_pass, c_reason = self.compression.verdict(cr, size)
        
        # Lei 4: Frequência de uso
        usage_stats = self.usage.get_stats(filepath)
        access_count = usage_stats['count']
        last_seen_days = (time.time() - usage_stats['last_seen']) / 86400 if usage_stats['last_seen'] else 999
        u_pass, u_reason = self.usage.verdict(access_count, last_seen_days, age_days)
        
        # Lei 5: Decaimento temporal
        weight = self.decay.compute_weight(last_seen_days, age_days)
        d_pass, d_reason = self.decay.verdict(weight)
        
        # Lei 6: Pressão de disco
        free_gb = min(
            self.disk.get_free_space_gb("C:"),
            self.disk.get_free_space_gb("D:"),
            self.disk.get_free_space_gb("E:"),
        )
        disk_pass, disk_reason = self.disk.verdict(free_gb)
        
        # ──── REGRA ÁUREA ────
        laws = [e_pass, p_pass, c_pass, u_pass, d_pass, disk_pass]
        laws_reasons = [e_reason, p_reason, c_reason, u_reason, d_reason, disk_reason]
        laws_passed = sum(laws)
        laws_failed = len(laws) - laws_passed
        
        # Pressão de disco modifica o threshold
        pressure_mult = self.disk.get_pressure_multiplier(free_gb)
        
        # Threshold ajustado por pressão: mais pressão = mais leis pra preservar
        # leniente (×0.5): precisa 2-3 leis | agressivo (×3.0): precisa 5-6 leis
        threshold_keep = min(6, 2 + int(pressure_mult))  # 2.5-5.0 → 2-5 leis
        threshold_discard = max(1, int(pressure_mult * 0.7))  # 0.35-2.1 → 1-2 leis
        
        if laws_passed >= threshold_keep:
            verdict = 'KEEP'
            score = laws_passed / 6.0
            reason = f"passou {laws_passed}/6 leis (threshold={threshold_keep})"
        elif laws_failed >= 4:  # falhou 4+ leis → descartar
            verdict = 'DISCARD'
            score = laws_passed / 6.0
            reason = f"falhou {laws_failed}/6 leis — gordura confirmada"
        else:
            verdict = 'COMPRESS'
            score = laws_passed / 6.0
            reason = f"zona cinzenta ({laws_passed}/6) — comprimir essência"
        
        return LiposuctionVerdict(
            path=filepath,
            size_bytes=size,
            verdict=verdict,
            score=round(score, 2),
            laws_passed=laws_passed,
            laws_failed=laws_failed,
            entropy=round(entropy, 4),
            phi_coherence=round(phi_c, 3),
            compression_ratio=cr,
            age_days=round(age_days, 1),
            access_count=access_count,
            reason=reason
        )
    
    def scan_directory(self, directory: str, file_pattern: str = "*") -> List[LiposuctionVerdict]:
        """Escaneia diretório e classifica TODOS os arquivos."""
        results = []
        root = Path(directory)
        files = list(root.rglob(file_pattern))
        
        for fp in files:
            if fp.is_file():
                v = self.analyze_file(str(fp))
                results.append(v)
        
        return results
    
    def summary(self, verdicts: List[LiposuctionVerdict]) -> dict:
        """Resumo estatístico da lipoaspiração."""
        keep = [v for v in verdicts if v.verdict == 'KEEP']
        compress = [v for v in verdicts if v.verdict == 'COMPRESS']
        discard = [v for v in verdicts if v.verdict == 'DISCARD']
        
        total_keep_size = sum(v.size_bytes for v in keep)
        total_compress_size = sum(v.size_bytes for v in compress)
        total_discard_size = sum(v.size_bytes for v in discard)
        total = total_keep_size + total_compress_size + total_discard_size
        
        return {
            'total_files': len(verdicts),
            'total_gb': round(total / (1024**3), 2),
            'keep': {'files': len(keep), 'gb': round(total_keep_size / (1024**3), 2),
                     'pct': round(total_keep_size / max(total, 1) * 100, 1)},
            'compress': {'files': len(compress), 'gb': round(total_compress_size / (1024**3), 2),
                         'pct': round(total_compress_size / max(total, 1) * 100, 1)},
            'discard': {'files': len(discard), 'gb': round(total_discard_size / (1024**3), 2),
                        'pct': round(total_discard_size / max(total, 1) * 100, 1)},
            'avg_score': round(sum(v.score for v in verdicts) / max(len(verdicts), 1), 2),
            'avg_entropy': round(sum(v.entropy for v in verdicts) / max(len(verdicts), 1), 2),
        }

# ══════════════════════════════════════════════════════════════════════════════
# §8  MAIN — Demonstração
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import shutil
    
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  Φ-LIPOSUCTION — Eliminação de Gordura                  ║")
    print("║  As 6 Leis + Regra Áurea                                 ║")
    print("╚══════════════════════════════════════════════════════════╝")
    
    engine = LiposuctionEngine()
    
    # ═══ DEMO 1: Arquivos sintéticos ═══
    print("\n─── DEMO 1: Arquivos sintéticos ───")
    
    test_files = {}
    
    # Arquivo redundante (zeros)
    test_files['test_zeros.bin'] = b'\x00' * 10000
    
    # Arquivo estruturado (código Python)
    with open(__file__, 'rb') as f:
        test_files['test_code.py'] = f.read(5000)
    
    # Arquivo aleatório
    test_files['test_random.bin'] = os.urandom(10000)
    
    # Arquivo comprimido (zlib)
    test_files['test_compressed.zlib'] = zlib.compress(b'Hello World ' * 500, level=9)
    
    # Arquivo pequeno (cabeçalho)
    test_files['test_tiny.txt'] = b'PHI=1.618'
    
    temp_dir = Path("D:/PhiLang_MachineCode64/cache/lipo_demo")
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    for name, data in test_files.items():
        (temp_dir / name).write_bytes(data)
    
    for name in test_files:
        v = engine.analyze_file(str(temp_dir / name))
        icon = {'KEEP': '✅', 'COMPRESS': '🗜️', 'DISCARD': '🗑️'}[v.verdict]
        print(f"  {icon} {name:25s} | {v.verdict:8s} | score={v.score:.2f} | "
              f"entropy={v.entropy:.1f} | Φ={v.phi_coherence:.3f} | "
              f"ratio={v.compression_ratio:.1f}x | {v.laws_passed}/6 leis")
        print(f"    {v.reason}")
    
    # ═══ DEMO 2: Scan de diretório real ═══
    print(f"\n─── DEMO 2: Scan da biblioteca extraída ───")
    
    if Path("E:/aethermind_library_extracted").exists():
        # Scan rápido (só 200 arquivos)
        verdicts = engine.scan_directory("E:/aethermind_library_extracted")
        verdicts = verdicts[:200]
        summary = engine.summary(verdicts)
        
        print(f"  Total: {summary['total_files']} arquivos, {summary['total_gb']}GB")
        print(f"  ✅ KEEP:     {summary['keep']['files']:4d} ({summary['keep']['gb']:.1f}GB, {summary['keep']['pct']}%)")
        print(f"  🗜️ COMPRESS: {summary['compress']['files']:4d} ({summary['compress']['gb']:.1f}GB, {summary['compress']['pct']}%)")
        print(f"  🗑️ DISCARD:  {summary['discard']['files']:4d} ({summary['discard']['gb']:.1f}GB, {summary['discard']['pct']}%)")
        print(f"  Score médio: {summary['avg_score']:.2f} | Entropia média: {summary['avg_entropy']:.1f}")
        
        # Top 5 piores (mais gordos)
        worst = sorted(verdicts, key=lambda v: v.score)[:5]
        print(f"\n  Top 5 MAIS GORDOS (candidatos a descarte):")
        for v in worst:
            print(f"    🗑️ {Path(v.path).name[:40]:40s} | score={v.score:.2f} | {v.size_bytes:>8d}B | {v.reason}")
        
        # Top 5 melhores
        best = sorted(verdicts, key=lambda v: -v.score)[:5]
        print(f"\n  Top 5 MAIS VALIOSOS (preservar):")
        for v in best:
            print(f"    ✅ {Path(v.path).name[:40]:40s} | score={v.score:.2f} | {v.size_bytes:>8d}B | {v.reason}")
    
    # ═══ REGRAS ═══
    print(f"""
{'='*60}
⚖️  AS 6 LEIS DE ELIMINAÇÃO DE GORDURA

  LEI 1 (Entropia):    <1 bit/B → redundante | >7.5 → aleatório
  LEI 2 (Coerência Φ): <0.3 → ruído         | >0.8 → harmônico
  LEI 3 (Compressão):  >100x → essência     | <2x → incompressível
  LEI 4 (Uso):         0 acessos → descarte  | diário → hot
  LEI 5 (Tempo):       >90d sem uso → 10% peso | <7d → peso total
  LEI 6 (Disco):       <1GB → agressivo ×3  | >10GB → leniente ×0.5

  REGRA ÁUREA:
  ├─ Passou ≥4 leis → PRESERVAR (KEEP)
  ├─ Passou 2-3 leis → COMPRIMIR essência (COMPRESS)
  └─ Falhou ≥4 leis → DESCARTAR (DISCARD)

  A pressão de disco ajusta automaticamente os thresholds.
  Quanto menos espaço, mais agressiva a lipoaspiração.
{'='*60}
""")
    
    # Limpeza
    shutil.rmtree(temp_dir, ignore_errors=True)
