

from pathlib import Path
from typing import List, Dict, Optional, Any

try:
    from .BaseInspector import BaseInspector, EntropyEvent
    from ..Calculators import ShannonEntropyCalculator, EntropyResult
except (ImportError, ValueError):
    from DataCollections.EntropyInspector.Inspectors.BaseInspector import (
        BaseInspector,
        EntropyEvent,
    )
    from DataCollections.EntropyInspector.Calculators import (
        ShannonEntropyCalculator,
        EntropyResult,
    )


class SnapshotInspector(BaseInspector):
    """
     (Snapshot) toàn bộ các tệp tin trong thư mục mồi.
    """

    def __init__(
        self,
        target_dirs: Optional[List[Path]] = None,
        calculator: Optional[ShannonEntropyCalculator] = None,
    ) -> None:
        super().__init__(target_dirs=target_dirs, calculator=calculator)

    def scan(self, recursive: bool = True) -> List[EntropyEvent]:
        """
        Quét toàn bộ các tệp tin trong các thư mục mục tiêu và tính Entropy.
        """
        snapshot_events: List[EntropyEvent] = []

        for directory in self.target_dirs:
            if not directory.exists() or not directory.is_dir():
                continue

            file_iterator = directory.rglob("*") if recursive else directory.glob("*")

            for file_path in file_iterator:
                # Bỏ qua thư mục và các tệp tin ẩn của hệ điều hành
                if not file_path.is_file() or file_path.name.startswith("."):
                    continue

                timestamp = self.get_current_timestamp()
                res: EntropyResult = self.calculator.inspect_file(str(file_path))

                event = EntropyEvent(
                    timestamp=timestamp,
                    event_type="SNAPSHOT",
                    file_path=str(file_path),
                    old_path=None,
                    entropy=res.entropy,
                    file_size=res.file_size,
                    status=res.status,
                    read_time_ms=res.read_time_ms,
                )
                snapshot_events.append(event)

        self.events = snapshot_events
        return snapshot_events

    def start(self) -> None:
        """Kích hoạt quét toàn bộ thư mục mồi ."""
        self.scan()

    def stop(self) -> List[EntropyEvent]:
        """Dừng và trả về toàn bộ danh sách sự kiện đã quét ."""
        return self.events

    def get_summary(
        self,
        events: Optional[List[EntropyEvent]] = None
    ) -> Dict[str, Any]:
        """
        Tổng hợp thống kê nhanh về các chỉ số Entropy trong đợt quét.
        """
        target_events = events if events is not None else self.events
        total_files = len(target_events)

        if total_files == 0:
            return {
                "total_files": 0,
                "mean_entropy": 0.0,
                "max_entropy": 0.0,
                "high_entropy_count": 0,
                "total_size_bytes": 0,
                "success_count": 0,
            }

        entropies = [e.entropy for e in target_events]
        mean_entropy = sum(entropies) / total_files
        max_entropy = max(entropies)
        high_entropy_count = sum(1 for h in entropies if h >= 7.0)
        total_size = sum(e.file_size for e in target_events)
        success_count = sum(1 for e in target_events if e.status == self.calculator.STATUS_SUCCESS)

        return {
            "total_files": total_files,
            "mean_entropy": round(mean_entropy, 4),
            "max_entropy": round(max_entropy, 4),
            "high_entropy_count": high_entropy_count,
            "high_entropy_ratio": round(high_entropy_count / total_files, 4),
            "total_size_bytes": total_size,
            "success_count": success_count,
        }

