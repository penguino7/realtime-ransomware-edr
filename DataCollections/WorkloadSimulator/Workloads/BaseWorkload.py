

import time
import random
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Optional, Any


class BaseWorkload(ABC):

    def __init__(self, target_dirs: Optional[List[Path]] = None, name: str = "BaseWorkload") -> None:
       
        self.name = name
        self.target_dirs: List[Path] = target_dirs or self._default_directories()

    def _default_directories(self) -> List[Path]:
        
        home = Path.home()
        return [
            home / "Desktop" / "DecoyDocs",
            home / "Documents" / "DecoyDocs",
            home / "Downloads" / "DecoyDocs",
        ]

    def find_files(self, extensions: Optional[List[str]] = None) -> List[Path]:
        """
        Quét và thu thập danh sách tất cả các tệp tin hiện có trong các thư mục 
        """
        found_files: List[Path] = []
        ext_set = {e.lower() for e in extensions} if extensions else None

        for directory in self.target_dirs:
            if directory.exists() and directory.is_dir():
                for file_path in directory.glob("*"):
                    if file_path.is_file():
                        if ext_set is None or file_path.suffix.lower() in ext_set:
                            found_files.append(file_path)

        return found_files

    def random_delay(self, min_sec: float = 0.2, max_sec: float = 0.8) -> None:
        """
        Tạm dừng tiến trình trong một khoảng thời gian ngẫu nhiên
        """
        time.sleep(random.uniform(min_sec, max_sec))

    @abstractmethod
    def execute(self) -> Dict[str, Any]:
        """
        """
        pass
