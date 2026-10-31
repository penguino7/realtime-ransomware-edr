

"""
Lớp cơ sở trừu tượng (Abstract Base Class) định nghĩa cấu trúc chuẩn cho mọi Workload giả lập:
- Quản lý danh sách thư mục mục tiêu chiến lược tập trung qua Config.get_monitored_directories().
- Cung cấp tiện ích quét tệp tin đệ quy đa tầng (Recursive rglob) hỗ trợ cây thư mục phân cấp.
- Cung cấp cơ chế tạo khoảng trễ tự nhiên (Natural Delay) ngẫu nhiên giữa các thao tác I/O.
- Bắt buộc mọi kịch bản con phải triển khai phương thức thực thi execute().
"""

import sys
import time
import random
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Optional, Any

# Đảm bảo Project Root có trong sys.path để nạp Src.Core.Config
_project_root = Path(__file__).resolve().parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from Src.Core.Config import Config
except (ImportError, ValueError):
    from Core.Config import Config


class BaseWorkload(ABC):

    def __init__(self, target_dirs: Optional[List[Path]] = None, name: str = "BaseWorkload") -> None:
       
        self.name = name
        self.target_dirs: List[Path] = target_dirs or self._default_directories()

    def _default_directories(self) -> List[Path]:
        return Config.get_monitored_directories()

    def find_files(self, extensions: Optional[List[str]] = None, recursive: bool = True) -> List[Path]:
        """
        Quét và thu thập danh sách tất cả các tệp tin hiện có trong các thư mục mục tiêu:
        """
        found_files: List[Path] = []
        ext_set = (
            {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
            if extensions
            else None
        )

        for directory in self.target_dirs:
            if directory.exists() and directory.is_dir():
                pattern_iter = directory.rglob("*") if recursive else directory.glob("*")
                for file_path in pattern_iter:
                    if file_path.is_file():
                        # Bỏ qua file tạm và file sổ hộ khẩu hệ thống
                        if file_path.suffix.lower() == ".tmp" or file_path.name == "decoy_registry.json":
                            continue

                        if ext_set is None or file_path.suffix.lower() in ext_set:
                            found_files.append(file_path)

        return found_files

    def random_delay(self, min_sec: float = 0.2, max_sec: float = 0.8) -> None:
        """
        Tạm dừng tiến trình trong một khoảng thời gian ngẫu nhiên để mô phỏng nhịp điệu người dùng thật.
        """
        if max_sec > 0:
            time.sleep(random.uniform(min_sec, max_sec))

    @abstractmethod
    def execute(self) -> Dict[str, Any]:
        pass
