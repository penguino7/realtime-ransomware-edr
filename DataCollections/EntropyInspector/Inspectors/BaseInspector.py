

import csv
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

try:
    from ..Calculators import ShannonEntropyCalculator, EntropyResult
except (ImportError, ValueError):
    from DataCollections.EntropyInspector.Calculators import (
        ShannonEntropyCalculator,
        EntropyResult,
    )


@dataclass(frozen=True)
class EntropyEvent:
    """
    Cấu trúc dữ liệu bất biến chuẩn hóa một sự kiện đo lường Entropy.
    """
    timestamp: str              # Mốc thời gian phát sinh sự kiện (HH:MM:SS.ffffff)
    event_type: str             # SNAPSHOT, MODIFIED, CREATED, RENAMED
    file_path: str              # Đường dẫn tệp tin hiện tại
    old_path: Optional[str] = None  # Đường dẫn cũ (chỉ có khi tệp bị đổi tên/di chuyển)
    entropy: float = 0.0        # Giá trị Shannon Entropy đo được (0.0000 - 8.0000)
    file_size: int = 0          # Kích thước tệp tin (bytes)
    status: str = "STATUS_SUCCESS"  # Trạng thái đo (STATUS_SUCCESS, STATUS_LOCKED, v.v.)
    read_time_ms: float = 0.0   # Thời gian đọc và tính toán (mili-giây)

    def to_dict(self) -> Dict[str, Any]:
        """Chuyển đổi đối tượng sang từ điển để xuất ra CSV/JSON."""
        return {
            "Timestamp": self.timestamp,
            "EventType": self.event_type,
            "FilePath": self.file_path,
            "OldPath": self.old_path or "",
            "Entropy": f"{self.entropy:.4f}",
            "FileSize": self.file_size,
            "Status": self.status,
            "ReadTimeMs": f"{self.read_time_ms:.3f}",
        }


class BaseInspector(ABC):
      

    def __init__(
        self,
        target_dirs: Optional[List[Path]] = None,
        calculator: Optional[ShannonEntropyCalculator] = None,
    ) -> None:

        self.target_dirs: List[Path] = target_dirs or self._default_directories()
        self.calculator: ShannonEntropyCalculator = calculator or ShannonEntropyCalculator()
        self.events: List[EntropyEvent] = []

    def _default_directories(self) -> List[Path]:
        """Xác định các thư mục mồi mặc định trên Windows Sandbox."""
        home = Path.home()
        return [
            home / "Desktop" / "DecoyDocs",
            home / "Documents" / "DecoyDocs",
            home / "Downloads" / "DecoyDocs",
        ]

    @staticmethod
    def get_current_timestamp() -> str:
        """Trả về chuỗi thời gian hiện tại chuẩn xác đến micro-giây khớp với log Procmon."""
        return datetime.now().strftime("%H:%M:%S.%f")

    @abstractmethod
    def start(self) -> None:
        """
        Bắt đầu quá trình giám sát / thu thập dữ liệu Entropy.
        """
        pass

    @abstractmethod
    def stop(self) -> List[EntropyEvent]:
        """
        Dừng quá trình giám sát và trả về danh sách toàn bộ các EntropyEvent đã thu thập.
        """
        pass

    def export_to_csv(
        self,
        output_path: Path,
        events: Optional[List[EntropyEvent]] = None
    ) -> Path:
        """
        Kết xuất danh sách sự kiện Entropy ra tệp tin CSV chuẩn.
        """
        target_events = events if events is not None else self.events
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "Timestamp",
            "EventType",
            "FilePath",
            "OldPath",
            "Entropy",
            "FileSize",
            "Status",
            "ReadTimeMs",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for ev in target_events:
                writer.writerow(ev.to_dict())

        return output_path
