"""
EntropyInspector Subsystem
==========================
Phân hệ giám định và đo đạc Shannon Entropy phục vụ thu thập dữ liệu huấn luyện ML phát hiện Ransomware:
- Calculators: ShannonEntropyCalculator tính toán entropy 64KB đầu buffer với Exponential Backoff.
- Inspectors: SnapshotInspector (quét tĩnh) và RealtimeWatcher (giám sát động thời gian thực).
- Managers: EntropyManager điều phối toàn bộ chu trình giám sát và xuất kết quả vào Data/Raw/.
"""

from .Calculators import ShannonEntropyCalculator, EntropyResult
from .Inspectors import (
    BaseInspector,
    EntropyEvent,
    SnapshotInspector,
    RealtimeWatcher,
)
from .Managers import EntropyManager

__all__ = [
    "ShannonEntropyCalculator",
    "EntropyResult",
    "BaseInspector",
    "EntropyEvent",
    "SnapshotInspector",
    "RealtimeWatcher",
    "EntropyManager",
]
