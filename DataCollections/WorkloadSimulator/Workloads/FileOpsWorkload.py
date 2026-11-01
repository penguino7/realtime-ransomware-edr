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

    # Hằng số điều khiển độ trễ I/O tự nhiên (giây) và kích thước khối đọc
    DELAY_MIN_SEC = 0.05
    DELAY_MAX_SEC = 0.15
    READ_DELAY_MIN_SEC = 0.03
    READ_DELAY_MAX_SEC = 0.10
    READ_CHUNK_SIZE = 64 * 1024  # 64KB (khớp với kích thước buffer phân tích Shannon Entropy)

    RENAME_PREFIXES = [
        "draft", "final", "reviewed", "backup",
        "old", "updated", "archived", "v2", "approved"
    ]

    # Bảng ánh xạ chế độ thực thi tới phương thức xử lý (Dispatch Table Pattern)
    _HANDLERS = {
        "copy": "_handle_copy_mode",
        "rename": "_handle_rename_mode",
        "delete": "_handle_delete_mode",
        "read": "_handle_read_mode",
    }

    def __init__(
        self,
        target_dirs: Optional[List[Path]] = None,
        mode: str = "mixed",
        min_files: int = 50,
        max_files: int = 100,
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

            # Tạm nghỉ ngắn tự nhiên mô phỏng tốc độ I/O đĩa
            self.random_delay(self.DELAY_MIN_SEC, self.DELAY_MAX_SEC)

        return copied_paths

    def _execute_rename(self, files: List[Path]) -> int:
        renamed_count = 0
        print(f"[*] [{self.name}:RENAME] Bắt đầu đổi tên {len(files)} tệp tin (giữ nguyên đuôi mở rộng)...")

        for idx, file_path in enumerate(files, 1):
            try:
                chosen_prefix = random.choice(self.RENAME_PREFIXES)
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

            self.random_delay(self.DELAY_MIN_SEC, self.DELAY_MAX_SEC)

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

            self.random_delay(self.DELAY_MIN_SEC, self.DELAY_MAX_SEC)

        return deleted_count

    def _execute_read(self, files: List[Path]) -> int:
        read_count = 0
        total_bytes = 0
        print(f"[*] [{self.name}:READ] Bắt đầu đọc tuần tự {len(files)} tệp tin...")

        for idx, file_path in enumerate(files, 1):
            try:
                if file_path.exists() and file_path.is_file():
                    with open(file_path, "rb") as f:
                        chunk = f.read(self.READ_CHUNK_SIZE)
                        total_bytes += len(chunk)
                        read_count += 1
                        print(f"  [{idx:02d}/READ] Đọc {len(chunk):,} bytes từ: {file_path.name}")
            except Exception as e:
                print(f"  [!] Lỗi đọc file {file_path.name}: {e}", file=sys.stderr)

            self.random_delay(self.READ_DELAY_MIN_SEC, self.READ_DELAY_MAX_SEC)

        print(f"[+] [{self.name}:READ] Hoàn thành đọc {read_count} files (Tổng: {total_bytes:,} bytes).")
        return read_count

    def _resolve_mode(self, mode: Optional[str]) -> str:
        """Chuẩn hóa và lựa chọn chế độ thực thi."""
        active_mode = (mode or self.mode).lower().strip()
        if active_mode not in self.AVAILABLE_MODES:
            print(f"[!] Chế độ '{active_mode}' không hợp lệ. Chọn 1 trong: {self.AVAILABLE_MODES}")
            active_mode = "mixed"

        if active_mode == "mixed":
            active_mode = random.choice(["copy", "rename", "delete", "read"])
        return active_mode

    def _get_destination_dir(self) -> Path:
        """Xác định thư mục đích cho thao tác sao chép (ưu tiên Documents hoặc Backup_Data)."""
        for d in self.target_dirs:
            if "documents" in d.name.lower():
                backup_sub = d / "Backup_Data"
                return backup_sub if backup_sub.exists() else d
        dest = self.target_dirs[1] if len(self.target_dirs) > 1 else self.target_dirs[0]
        backup_sub = dest / "Backup_Data"
        return backup_sub if backup_sub.exists() else dest

    def _handle_copy_mode(self, files: List[Path], target_count: int) -> Dict[str, Any]:
        """Xử lý kịch bản sao chép tệp tin hàng loạt."""
        files_to_copy = files[:target_count]
        dest_dir = self._get_destination_dir()
        copied_files = self._execute_copy(files_to_copy, dest_dir)
        print(f"[+] [{self.name}:COPY] Hoàn thành sao chép {len(copied_files)}/{target_count} tệp tin.")
        return {"files_copied": len(copied_files)}

    def _handle_rename_mode(self, files: List[Path], target_count: int) -> Dict[str, Any]:
        """Xử lý kịch bản đổi tên tệp tin hàng loạt (giữ nguyên extension)."""
        files_to_rename = files[:target_count]
        renamed_count = self._execute_rename(files_to_rename)
        print(f"[+] [{self.name}:RENAME] Hoàn thành đổi tên {renamed_count}/{target_count} tệp tin (Giữ nguyên đuôi).")
        return {"files_renamed": renamed_count}

    def _handle_delete_mode(self, files: List[Path], target_count: int) -> Dict[str, Any]:
        """Xử lý kịch bản xóa tệp tin (ưu tiên file tạm copy_* trước, sau đó file mồi)."""
        copy_files = [f for f in files if f.name.lower().startswith("copy_")]
        other_files = [f for f in files if not f.name.lower().startswith("copy_")]

        files_to_delete = copy_files[:target_count]
        if len(files_to_delete) < target_count:
            needed = target_count - len(files_to_delete)
            files_to_delete.extend(other_files[:needed])

        deleted_count = self._execute_delete(files_to_delete)
        print(f"[+] [{self.name}:DELETE] Hoàn thành xóa {deleted_count}/{len(files_to_delete)} tệp tin.")
        return {"files_deleted": deleted_count}

    def _handle_read_mode(self, files: List[Path], target_count: int) -> Dict[str, Any]:
        """Xử lý kịch bản đọc tuần tự tệp tin."""
        files_to_read = files[:target_count]
        read_count = self._execute_read(files_to_read)
        print(f"[+] [{self.name}:READ] Hoàn thành đọc {read_count}/{target_count} tệp tin.")
        return {"files_read": read_count}

    def execute(self, mode: Optional[str] = None) -> Dict[str, Any]:
        """
        Thực thi kịch bản quản lý file quy mô lớn qua Dispatch Table Pattern.
        """
        active_mode = self._resolve_mode(mode)

        available_files = self.find_files()
        if not available_files:
            print("[!] Không tìm thấy file mồi nào trong các thư mục giám sát.")
            return {"workload": self.name, "mode": active_mode, "status": "skipped", "message": "Không có file"}

        # Phòng vệ: Nếu số file khả dụng ít hơn min_files thì lấy toàn bộ
        if len(available_files) < self.min_files:
            target_count = len(available_files)
        else:
            target_count = random.randint(self.min_files, min(len(available_files), self.max_files))

        random.shuffle(available_files)

        result_payload: Dict[str, Any] = {
            "workload": self.name,
            "mode": active_mode,
            "status": "success",
            "target_count": target_count,
        }

        handler_name = self._HANDLERS.get(active_mode)
        if handler_name:
            handler = getattr(self, handler_name)
            mode_metrics = handler(available_files, target_count)
            result_payload.update(mode_metrics)

        return result_payload
