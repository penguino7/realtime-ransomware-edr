import sys
import time
import random
import json
from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple

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


# Lớp cơ sở trừu tượng định nghĩa khung chuẩn cho mọi kịch bản giả lập Workload
class BaseWorkload(ABC):

    def __init__(self, target_dirs: Optional[List[Path]] = None, name: str = "BaseWorkload") -> None:
       
        self.name = name
        self.target_dirs: List[Path] = target_dirs or self._default_directories()

    def _default_directories(self) -> List[Path]:
        return Config.get_monitored_directories()

    # Tìm đường dẫn tệp decoy_registry.json để tải nhanh danh sách file mồi
    def _find_registry_path(self) -> Optional[Path]:
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

    # Thu thập danh sách tệp trong mục tiêu (ưu tiên đọc từ decoy_registry.json)
    def find_files(self, extensions: Optional[List[str]] = None, recursive: bool = True) -> List[Path]:
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

    # Chọn tệp ưu tiên gom cụm theo từng thư mục (Folder-Locality)
    def select_files_clustered(
        self,
        files: List[Path],
        target_count: int,
        locality_ratio: float = 0.75
    ) -> List[Path]:
        if not files or target_count <= 0:
            return []

        clamped_ratio = max(0.0, min(1.0, float(locality_ratio)))
        capped_count = min(target_count, len(files))

        by_folder: Dict[Path, List[Path]] = defaultdict(list)
        for f in files:
            by_folder[f.parent].append(f)

        folder_keys = list(by_folder.keys())
        random.shuffle(folder_keys)

        local_quota = round(capped_count * clamped_ratio)
        selected: List[Path] = []
        selected_set = set()

        # Ưu tiên lấy trọn hoặc phần lớn file trong từng thư mục trước khi chuyển sang thư mục khác
        for folder in folder_keys:
            if len(selected) >= local_quota:
                break
            folder_files = list(by_folder[folder])
            random.shuffle(folder_files)
            for f in folder_files:
                if len(selected) >= local_quota:
                    break
                selected.append(f)
                selected_set.add(f)

        # Phần còn lại lấy rải rác ở các thư mục khác để giữ độ đa dạng tự nhiên
        if len(selected) < capped_count:
            remaining = [f for f in files if f not in selected_set]
            random.shuffle(remaining)
            selected.extend(remaining[: capped_count - len(selected)])

        return selected

    # Tạm dừng ngẫu nhiên mô phỏng nhịp thao tác người dùng
    def random_delay(self, min_sec: float = 0.2, max_sec: float = 0.8) -> None:
        if max_sec > 0:
            time.sleep(random.uniform(min_sec, max_sec))

    # Mô phỏng nhịp I/O Burst + Pause theo cụm tác vụ thực tế
    def burst_or_pause(
        self,
        step_index: int,
        burst_size: int = 20,
        burst_delay: Tuple[float, float] = (0.0, 0.02),
        pause_range: Tuple[float, float] = (1.5, 3.5)
    ) -> None:
        effective_burst = max(1, int(burst_size))
        if (step_index + 1) % effective_burst == 0:
            if pause_range[1] > 0:
                time.sleep(random.uniform(pause_range[0], pause_range[1]))
        elif burst_delay[1] > 0:
            delay = random.uniform(burst_delay[0], burst_delay[1])
            if delay > 0:
                time.sleep(delay)

    @abstractmethod
    def execute(self) -> Dict[str, Any]:
        pass
