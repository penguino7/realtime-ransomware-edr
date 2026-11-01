
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
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Optional, Any

# Thiết lập encoding UTF-8 cho console Windows tránh UnicodeEncodeError (cp1252)
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

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

    def _find_registry_path(self) -> Optional[Path]:
        """
        Tìm đường dẫn tới tệp sổ hộ khẩu mồi (decoy_registry.json) để tải nhanh danh sách file trong RAM.
        """
        candidates = [
            Config.PROJECT_ROOT / "DataCollections" / "FileGenerator" / "decoy_registry.json",
            Path(__file__).resolve().parents[2] / "FileGenerator" / "decoy_registry.json",
        ]
        for cand in candidates:
            try:
                if cand.is_file():
                    return cand
            except (OSError, PermissionError):
                continue
        return None

    def find_files(self, extensions: Optional[List[str]] = None, recursive: bool = True) -> List[Path]:
        """
        Thu thập danh sách tất cả các tệp tin hiện có trong các thư mục mục tiêu:
        - Ưu tiên đọc trực tiếp từ decoy_registry.json trên RAM để triệt tiêu bão I/O quét đĩa (CREATE flood trên Procmon).
        - Tự động fallback quét đệ quy rglob(*) nếu registry không tồn tại (chạy trên thư mục tùy chỉnh ngoài decoy).
        """
        found_files: List[Path] = []
        ext_set = (
            {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
            if extensions
            else None
        )

        # 1. Fast-path: Đọc từ decoy_registry.json để tránh mọi hành vi quét thư mục gây nhiễu Procmon
        registry_path = self._find_registry_path()
        if registry_path:
            try:
                raw_entries = json.loads(registry_path.read_text(encoding="utf-8"))
                for entry in raw_entries:
                    file_path = Path(entry)
                    # Lọc nhanh đuôi file trên bộ nhớ RAM
                    if ext_set and file_path.suffix.lower() not in ext_set:
                        continue
                    # Chỉ kiểm tra tồn tại thực tế nếu đã vượt qua bộ lọc extension
                    try:
                        if file_path.is_file():
                            found_files.append(file_path)
                    except (OSError, PermissionError):
                        continue

                if found_files:
                    return found_files
            except Exception:
                # Nếu xảy ra bất kỳ sự cố nào khi đọc registry, chuyển sang fallback
                pass

        # 2. Fallback: Quét đĩa rglob truyền thống khi không có registry hoặc registry rỗng
        for directory in self.target_dirs:
            try:
                if directory.exists() and directory.is_dir():
                    pattern_iter = directory.rglob("*") if recursive else directory.glob("*")
                    for file_path in pattern_iter:
                        try:
                            if file_path.is_file():
                                # Bỏ qua file tạm và file sổ hộ khẩu hệ thống
                                if file_path.suffix.lower() == ".tmp" or file_path.name == "decoy_registry.json":
                                    continue

                                if ext_set is None or file_path.suffix.lower() in ext_set:
                                    found_files.append(file_path)
                        except (OSError, PermissionError):
                            continue
            except (OSError, PermissionError):
                continue

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
