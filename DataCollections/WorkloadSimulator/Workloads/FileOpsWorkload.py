"""
FileOpsWorkload.py
==================
Kịch bản mô phỏng các thao tác quản lý tệp tin người dùng (File Explorer Operations):
- Sao chép tệp tin ngẫu nhiên giữa các thư mục (Copy).
- Đổi tên tệp tin lẻ tẻ có chọn lọc (Rename) mà vẫn giữ nguyên đuôi mở rộng gốc.
- Xóa tệp tin bản sao tạm thời (Delete).
"""

import shutil
import random
from pathlib import Path
from typing import List, Dict, Optional, Any
from faker import Faker
from .BaseWorkload import BaseWorkload


class FileOpsWorkload(BaseWorkload):
    """
    Kịch bản thực hiện các thao tác quản lý tệp tin ngẫu nhiên:
    Copy, Rename và Delete trên các thư mục mồi DecoyDocs.
    """

    def __init__(
        self,
        target_dirs: Optional[List[Path]] = None,
        locale: str = "vi_VN"
    ) -> None:
        super().__init__(target_dirs=target_dirs, name="FileOpsWorkload")
        try:
            self.faker = Faker(locale)
        except Exception:
            self.faker = Faker("en_US")

    def _perform_copy(self, files: List[Path], dest_dir: Path) -> List[Path]:
        """
        Sao chép danh sách file sang thư mục đích khác kèm tiền tố mới.
        Bắt sự kiện: ReadFile (file nguồn) và CreateFile + WriteFile (file đích).
        """
        copied_paths: List[Path] = []
        dest_dir.mkdir(parents=True, exist_ok=True)

        for src_file in files:
            try:
                # Tiền tố tên bản sao: copy_xxx_tenfilegoc.ext
                clean_word = "".join(c for c in self.faker.word() if c.isalnum())
                dest_file = dest_dir / f"copy_{clean_word}_{src_file.name}"
                shutil.copy2(str(src_file), str(dest_file))
                copied_paths.append(dest_file)
            except Exception:
                pass

        return copied_paths

    def _perform_rename(self, files: List[Path]) -> int:
        """
        Đổi tên một số tệp tin nhưng GIỮ NGUYÊN ĐUÔI FILE GỐC.
        """
        renamed_count = 0
        prefixes = ["draft", "final", "reviewed", "backup", "old", "updated"]

        for file_path in files:
            try:
                chosen_prefix = random.choice(prefixes)
                # Đổi tên phần stem nhưng giữ nguyên đuôi mở rộng .docx, .pdf...
                new_filename = f"{chosen_prefix}_{file_path.name}"
                new_path = file_path.parent / new_filename

                if not new_path.exists():
                    file_path.rename(new_path)
                    renamed_count += 1
            except Exception:
                pass

        return renamed_count

    def _perform_delete(self, files: List[Path]) -> int:
        """
        Xóa một số tệp tin tạm thời không dùng đến.
       
        """
        deleted_count = 0
        for file_path in files:
            try:
                if file_path.exists():
                    file_path.unlink()
                    deleted_count += 1
            except Exception:
                pass
        return deleted_count

    def execute(self) -> Dict[str, Any]:
        """
        Thực thi kịch bản quản lý file với số lượng n biến thiên ngẫu nhiên.
        """
        available_files = self.find_files()
        if not available_files:
            print("[!] Không tìm thấy file mồi nào trong DecoyDocs.")
            return {"workload": self.name, "status": "skipped", "message": "Không có file mồi"}

        # 1. Sinh ngẫu nhiên số lượng n file cho từng thao tác
        n_copy = random.randint(3, min(len(available_files), 8))
        n_rename = random.randint(1, min(len(available_files), 4))
        n_delete = random.randint(1, 3)

        random.shuffle(available_files)
        files_for_copy = available_files[:n_copy]

        # Chọn thư mục đích khác với thư mục nguồn để copy
        dest_dir = self.target_dirs[1] if len(self.target_dirs) > 1 else self.target_dirs[0]

        # Thao tác 1: Copy n_copy file
        print(f"[*] [{self.name}] Đang sao chép ngẫu nhiên {n_copy} file...")
        copied_files = self._perform_copy(files_for_copy, dest_dir)

        # Nghỉ tự nhiên mô phỏng người dùng
        self.random_delay(0.3, 0.6)

        # Thao tác 2: Đổi tên n_rename file lẻ tẻ (giữ nguyên đuôi)
        remaining_files = [f for f in available_files if f not in files_for_copy]
        files_for_rename = remaining_files[:n_rename] if remaining_files else available_files[:n_rename]

        print(f"[*] [{self.name}] Đang đổi tên ngẫu nhiên {n_rename} file...")
        renamed_count = self._perform_rename(files_for_rename)

        # Nghỉ tự nhiên
        self.random_delay(0.2, 0.5)

        # Thao tác 3: Xóa n_delete file tạm (ưu tiên xóa chính các bản copy vừa tạo để giữ sạch đĩa)
        files_for_delete = copied_files[:n_delete] if copied_files else []
        deleted_count = 0
        if files_for_delete:
            print(f"[*] [{self.name}] Đang xóa dọn dẹp {len(files_for_delete)} bản copy tạm...")
            deleted_count = self._perform_delete(files_for_delete)

        print(
            f"[+] [{self.name}] Hoàn thành: "
            f"Copy={len(copied_files)}, Rename={renamed_count}, Delete={deleted_count} files."
        )

        return {
            "workload": self.name,
            "status": "success",
            "files_copied": len(copied_files),
            "files_renamed": renamed_count,
            "files_deleted": deleted_count
        }
