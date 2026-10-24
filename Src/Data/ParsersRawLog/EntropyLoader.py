

import csv
import os
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Union

try:
    from .LogFormatters import LogFormatters
except (ImportError, ValueError):
    from Src.Data.ParsersRawLog.LogFormatters import LogFormatters


class EntropyLoader:
    """
    Chịu trách nhiệm nạp, chuẩn hóa đường dẫn và tổ chức bộ đệm tra cứu
    cho Baseline Entropy Snapshot và Realtime Entropy Logs.
    """

    def __init__(
        self,
        baseline_path: Union[str, Path],
        realtime_path: Union[str, Path]
    ) -> None:
        """
        Khởi tạo EntropyLoader với đường dẫn 2 file log entropy.

        """
        self.baseline_path = Path(baseline_path)
        self.realtime_path = Path(realtime_path)

        self._baseline_map: Dict[str, float] = {}
        self._realtime_map: Dict[str, List[Tuple[float, float, int]]] = defaultdict(list)
        self._is_loaded = False

    @property
    def baseline_map(self) -> Dict[str, float]:
        
        if not self._is_loaded:
            self.load_all()
        return self._baseline_map

    @property
    def realtime_map(self) -> Dict[str, List[Tuple[float, float, int]]]:
        
        if not self._is_loaded:
            self.load_all()
        return self._realtime_map

    def load_all(self) -> None:
        """Nạp đồng thời cả baseline và realtime entropy vào bộ nhớ đệm."""
        self.load_baseline()
        self.load_realtime()
        self._is_loaded = True

    def load_baseline(self) -> Dict[str, float]:
        """
        Đọc file baseline snapshot, tạo bảng tra cứu nhanh O(1).
        """
        if not self.baseline_path.exists():
            raise FileNotFoundError(f"Không tìm thấy baseline snapshot: {self.baseline_path}")

        self._baseline_map.clear()
        with open(self.baseline_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if len(row) >= 5 and row[2].strip():
                    norm_path = os.path.normpath(row[2].strip()).lower()
                    try:
                        self._baseline_map[norm_path] = float(row[4])
                    except ValueError:
                        continue
        return self._baseline_map

    def load_realtime(self) -> Dict[str, List[Tuple[float, float, int]]]:
        
        if not self.realtime_path.exists():
            raise FileNotFoundError(f"Không tìm thấy realtime entropy: {self.realtime_path}")

        self._realtime_map.clear()
        with open(self.realtime_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if len(row) >= 6 and row[2].strip():
                    norm_path = os.path.normpath(row[2].strip()).lower()
                    ts_sec = LogFormatters.parse_realtime_timestamp(row[0])
                    try:
                        entropy = float(row[4])
                        file_size = int(row[5]) if row[5].strip() else 0
                        self._realtime_map[norm_path].append((ts_sec, entropy, file_size))
                    except ValueError:
                        continue

        # Sắp xếp tăng dần theo mốc thời gian để tối ưu tra cứu
        for path_key in self._realtime_map:
            self._realtime_map[path_key].sort(key=lambda item: item[0])

        return self._realtime_map
