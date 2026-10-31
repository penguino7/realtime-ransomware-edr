import sys
import shutil
import random
from pathlib import Path
from typing import List, Dict, Optional, Any
from faker import Faker
from .BaseWorkload import BaseWorkload

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


class FileOpsWorkload(BaseWorkload):

    AVAILABLE_MODES = ["copy", "rename", "delete", "read", "mixed"]

    def __init__(
        self,
        target_dirs: Optional[List[Path]] = None,
        mode: str = "mixed",
        min_files: int = 30,
        max_files: int = 50,
        locale: str = "vi_VN"
    ) -> None:
        super().__init__(target_dirs=target_dirs, name="FileOpsWorkload")
        self.mode = mode.lower().strip()
        self.min_files = max(10, min_files)
        self.max_files = max(self.min_files, max_files)

        try:
            self.faker = Faker(locale)
        except Exception:
            self.faker = Faker("en_US")

    def _execute_copy(self, files: List[Path], dest_dir: Path) -> List[Path]:
        """
        Sao chép hàng loạt 30-50 tệp tin sang thư mục đích khác với tiền tố mới.
        """
        copied_paths: List[Path] = []
        dest_dir.mkdir(parents=True, exist_ok=True)

        print(f"[*] [{self.name}:COPY] Bắt đầu sao chép {len(files)} tệp tin sang '{dest_dir.name}'...")

        for idx, src_file in enumerate(files, 1):
            try:
                clean_word = "".join(c for c in self.faker.word() if c.isalnum())
                dest_file = dest_dir / f"copy_{clean_word}_{src_file.name}"
                shutil.copy2(str(src_file), str(dest_file))
                copied_paths.append(dest_file)
                print(f"  [{idx:02d}/COPY] {src_file.name} -> {dest_file.name}")
            except Exception as e:
                print(f"  [!] Lỗi sao chép {src_file.name}: {e}", file=sys.stderr)

            # Tạm nghỉ ngắn tự nhiên (0.05s - 0.15s) mô phỏng tốc độ I/O đĩa
            self.random_delay(0.05, 0.15)

        return copied_paths

    def _execute_rename(self, files: List[Path]) -> int:
        renamed_count = 0
        prefixes = [
            "draft", "final", "reviewed", "backup",
            "old", "updated", "archived", "v2", "approved"
        ]

        print(f"[*] [{self.name}:RENAME] Bắt đầu đổi tên {len(files)} tệp tin (giữ nguyên đuôi mở rộng)...")

        for idx, file_path in enumerate(files, 1):
            try:
                chosen_prefix = random.choice(prefixes)
                clean_word = "".join(c for c in self.faker.word() if c.isalnum())
                # Giữ nguyên phần đuôi mở rộng .docx, .xlsx, .py, .pdf...
                new_filename = f"{chosen_prefix}_{clean_word}_{file_path.name}"
                new_path = file_path.parent / new_filename

                if not new_path.exists():
                    file_path.rename(new_path)
                    renamed_count += 1
                    print(f"  [{idx:02d}/RENAME] {file_path.name}  ==>  {new_filename}")
            except Exception as e:
                print(f"  [!] Lỗi đổi tên {file_path.name}: {e}", file=sys.stderr)

            self.random_delay(0.05, 0.15)

        return renamed_count

    def _execute_delete(self, files: List[Path]) -> int:
        """
        Xóa hàng loạt 30-50 tệp tin (SetDispositionInformationFile).
        Ưu tiên xóa các bản sao tạm (copy_*), nếu không đủ sẽ xóa file mồi, ghi rõ nguồn gốc trong log.
        """
        deleted_count = 0
        print(f"[*] [{self.name}:DELETE] Bắt đầu xóa dọn dẹp {len(files)} tệp tin...")

        for idx, file_path in enumerate(files, 1):
            try:
                if file_path.exists():
                    is_copy = file_path.name.lower().startswith("copy_")
                    file_tag = "BẢN SAO (Copy)" if is_copy else "FILE MỒI (Decoy)"
                    file_path.unlink()
                    deleted_count += 1
                    print(f"  [{idx:02d}/DELETE - {file_tag}] Đã xóa: {file_path.name} ({file_path.parent.name})")
            except Exception as e:
                print(f"  [!] Lỗi xóa file {file_path.name}: {e}", file=sys.stderr)

            self.random_delay(0.05, 0.15)

        return deleted_count

    def _execute_read(self, files: List[Path]) -> int:
        read_count = 0
        total_bytes = 0
        print(f"[*] [{self.name}:READ] Bắt đầu đọc tuần tự {len(files)} tệp tin...")

        for idx, file_path in enumerate(files, 1):
            try:
                if file_path.exists() and file_path.is_file():
                    with open(file_path, "rb") as f:
                        # Đọc khối dữ liệu 64KB đầu tiên hoặc toàn bộ file nếu nhỏ hơn 64KB
                        chunk = f.read(65536)
                        total_bytes += len(chunk)
                        read_count += 1
                        print(f"  [{idx:02d}/READ] Đọc {len(chunk):,} bytes từ: {file_path.name}")
            except Exception as e:
                print(f"  [!] Lỗi đọc file {file_path.name}: {e}", file=sys.stderr)

            self.random_delay(0.03, 0.10)

        print(f"[+] [{self.name}:READ] Hoàn thành đọc {read_count} files (Tổng: {total_bytes:,} bytes).")
        return read_count

    def execute(self, mode: Optional[str] = None) -> Dict[str, Any]:
        """
        Thực thi kịch bản quản lý file quy mô lớn theo chế độ chỉ định hoặc ngẫu nhiên.
        """
        active_mode = (mode or self.mode).lower().strip()
        if active_mode not in self.AVAILABLE_MODES:
            print(f"[!] Chế độ '{active_mode}' không hợp lệ. Chọn 1 trong: {self.AVAILABLE_MODES}")
            active_mode = "mixed"

        if active_mode == "mixed":
            active_mode = random.choice(["copy", "rename", "delete", "read"])

        available_files = self.find_files()
        if not available_files:
            print("[!] Không tìm thấy file mồi nào trong các thư mục giám sát.")
            return {"workload": self.name, "mode": active_mode, "status": "skipped", "message": "Không có file"}

        # Xác định số lượng file mục tiêu (tối thiểu 30, tối đa 50 file để đạt từ 3 - 5 Ticks)
        target_count = random.randint(self.min_files, min(len(available_files), self.max_files))
        random.shuffle(available_files)

        result_payload: Dict[str, Any] = {
            "workload": self.name,
            "mode": active_mode,
            "status": "success",
            "target_count": target_count,
        }

        # -------------------------------------------------------------
        # 1. Chế độ COPY (30 - 50 files)
        # -------------------------------------------------------------
        if active_mode == "copy":
            files_to_copy = available_files[:target_count]
            # Chọn thư mục đích khác thư mục hiện tại
            dest_dir = self.target_dirs[1] if len(self.target_dirs) > 1 else self.target_dirs[0]
            # Thêm thư mục con Backup_Data nếu có
            backup_sub = dest_dir / "Backup_Data"
            if backup_sub.exists():
                dest_dir = backup_sub

            copied_files = self._execute_copy(files_to_copy, dest_dir)
            result_payload["files_copied"] = len(copied_files)
            print(f"[+] [{self.name}:COPY] Hoàn thành sao chép {len(copied_files)}/{target_count} tệp tin.")

        # -------------------------------------------------------------
        # 2. Chế độ RENAME (30 - 50 files)
        # -------------------------------------------------------------
        elif active_mode == "rename":
            files_to_rename = available_files[:target_count]
            renamed_count = self._execute_rename(files_to_rename)
            result_payload["files_renamed"] = renamed_count
            print(f"[+] [{self.name}:RENAME] Hoàn thành đổi tên {renamed_count}/{target_count} tệp tin (Giữ nguyên đuôi).")

        # -------------------------------------------------------------
        # 3. Chế độ DELETE (30 - 50 files)
        # -------------------------------------------------------------
        elif active_mode == "delete":
            # Ưu tiên tìm các file bản sao trước (bắt đầu bằng copy_)
            copy_files = [f for f in available_files if f.name.lower().startswith("copy_")]
            other_files = [f for f in available_files if not f.name.lower().startswith("copy_")]

            # Gom đủ số lượng target_count
            files_to_delete = copy_files[:target_count]
            if len(files_to_delete) < target_count:
                needed = target_count - len(files_to_delete)
                files_to_delete.extend(other_files[:needed])

            deleted_count = self._execute_delete(files_to_delete)
            result_payload["files_deleted"] = deleted_count
            print(f"[+] [{self.name}:DELETE] Hoàn thành xóa {deleted_count}/{len(files_to_delete)} tệp tin.")

        # -------------------------------------------------------------
        # 4. Chế độ READ (30 - 50 files)
        # -------------------------------------------------------------
        elif active_mode == "read":
            files_to_read = available_files[:target_count]
            read_count = self._execute_read(files_to_read)
            result_payload["files_read"] = read_count
            print(f"[+] [{self.name}:READ] Hoàn thành đọc {read_count}/{target_count} tệp tin.")

        return result_payload
