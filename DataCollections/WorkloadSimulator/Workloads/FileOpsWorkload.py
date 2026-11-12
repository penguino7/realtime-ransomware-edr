import random
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

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


# Kịch bản giả lập thao tác tệp hàng loạt theo cụm thư mục (Copy, Rename, Delete, Read)
class FileOpsWorkload(BaseWorkload):

    AVAILABLE_MODES = ["copy", "rename", "delete", "read", "mixed"]

    # Hằng số kích thước cụm burst và khối đọc 64KB
    BURST_SIZE = 25
    READ_CHUNK_SIZE = 64 * 1024

    RENAME_PREFIXES = [
        "draft", "final", "reviewed", "backup",
        "old", "updated", "archived", "v2", "approved"
    ]

    # Bảng ánh xạ chế độ thực thi tới phương thức xử lý
    _HANDLERS = {
        "copy": "_handle_copy_mode",
        "rename": "_handle_rename_mode",
        "delete": "_handle_delete_mode",
        "read": "_handle_read_mode",
    }

    # Khởi tạo workload thao tác file với chế độ và dải số lượng file mục tiêu
    def __init__(
        self,
        target_dirs: Optional[List[Path]] = None,
        mode: str = "mixed",
        min_files: int = 80,
        max_files: int = 200,
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

    # Sao chép hàng loạt tệp theo cụm sang thư mục đích với nhịp burst/pause
    def _execute_copy(self, files: List[Path], dest_dir: Path) -> List[Path]:
        copied_paths: List[Path] = []
        dest_dir.mkdir(parents=True, exist_ok=True)
        print(f"[*] [{self.name}:COPY] Bắt đầu sao chép {len(files)} tệp tin sang '{dest_dir.name}'...")

        for idx, src_file in enumerate(files):
            try:
                clean_word = "".join(c for c in self.faker.word() if c.isalnum())
                dest_file = dest_dir / f"copy_{clean_word}_{src_file.name}"
                shutil.copy2(str(src_file), str(dest_file))
                copied_paths.append(dest_file)
                print(f"  [{idx + 1:02d}/COPY] {src_file.name} -> {dest_file.name}")
            except Exception as e:
                print(f"  [!] Lỗi sao chép {src_file.name}: {e}", file=sys.stderr)

            self.burst_or_pause(idx, burst_size=self.BURST_SIZE, burst_delay=(0.0, 0.015), pause_range=(1.0, 2.5))

        return copied_paths

    # Đổi tên hàng loạt tệp trong cụm thư mục (giữ nguyên phần mở rộng)
    def _execute_rename(self, files: List[Path]) -> int:
        renamed_count = 0
        print(f"[*] [{self.name}:RENAME] Bắt đầu đổi tên {len(files)} tệp tin (giữ nguyên đuôi mở rộng)...")

        for idx, file_path in enumerate(files):
            try:
                chosen_prefix = random.choice(self.RENAME_PREFIXES)
                clean_word = "".join(c for c in self.faker.word() if c.isalnum())
                new_filename = f"{chosen_prefix}_{clean_word}_{file_path.name}"
                new_path = file_path.parent / new_filename

                if not new_path.exists():
                    file_path.rename(new_path)
                    renamed_count += 1
                    print(f"  [{idx + 1:02d}/RENAME] {file_path.name}  ==>  {new_filename}")
            except Exception as e:
                print(f"  [!] Lỗi đổi tên {file_path.name}: {e}", file=sys.stderr)

            self.burst_or_pause(idx, burst_size=self.BURST_SIZE, burst_delay=(0.0, 0.015), pause_range=(1.0, 2.5))

        return renamed_count

    # Xóa hàng loạt tệp (ưu tiên bản sao tạm copy_* trước file mồi)
    def _execute_delete(self, files: List[Path]) -> int:
        deleted_count = 0
        print(f"[*] [{self.name}:DELETE] Bắt đầu xóa dọn dẹp {len(files)} tệp tin...")

        for idx, file_path in enumerate(files):
            try:
                if file_path.exists():
                    is_copy = file_path.name.lower().startswith("copy_")
                    file_tag = "BẢN SAO (Copy)" if is_copy else "FILE MỒI (Decoy)"
                    file_path.unlink()
                    deleted_count += 1
                    print(f"  [{idx + 1:02d}/DELETE - {file_tag}] Đã xóa: {file_path.name} ({file_path.parent.name})")
            except Exception as e:
                print(f"  [!] Lỗi xóa file {file_path.name}: {e}", file=sys.stderr)

            self.burst_or_pause(idx, burst_size=self.BURST_SIZE, burst_delay=(0.0, 0.015), pause_range=(1.0, 2.5))

        return deleted_count

    # Đọc tuần tự 64KB đầu của từng tệp theo cụm thư mục
    def _execute_read(self, files: List[Path]) -> int:
        read_count = 0
        total_bytes = 0
        print(f"[*] [{self.name}:READ] Bắt đầu đọc tuần tự {len(files)} tệp tin...")

        for idx, file_path in enumerate(files):
            try:
                if file_path.exists() and file_path.is_file():
                    with open(file_path, "rb") as f:
                        chunk = f.read(self.READ_CHUNK_SIZE)
                        total_bytes += len(chunk)
                        read_count += 1
                        print(f"  [{idx + 1:02d}/READ] Đọc {len(chunk):,} bytes từ: {file_path.name}")
            except Exception as e:
                print(f"  [!] Lỗi đọc file {file_path.name}: {e}", file=sys.stderr)

            self.burst_or_pause(idx, burst_size=self.BURST_SIZE, burst_delay=(0.0, 0.01), pause_range=(0.8, 2.0))

        print(f"[+] [{self.name}:READ] Hoàn thành đọc {read_count} files (Tổng: {total_bytes:,} bytes).")
        return read_count

    # Chuẩn hóa và chọn chế độ thực thi
    def _resolve_mode(self, mode: Optional[str]) -> str:
        active_mode = (mode or self.mode).lower().strip()
        if active_mode not in self.AVAILABLE_MODES:
            print(f"[!] Chế độ '{active_mode}' không hợp lệ. Chọn 1 trong: {self.AVAILABLE_MODES}")
            active_mode = "mixed"

        if active_mode == "mixed":
            active_mode = random.choice(["copy", "rename", "delete", "read"])
        return active_mode

    # Xác định thư mục đích cho thao tác sao chép (ưu tiên Backup_Data)
    def _get_destination_dir(self) -> Path:
        for d in self.target_dirs:
            if "documents" in d.name.lower():
                backup_sub = d / "Backup_Data"
                return backup_sub if backup_sub.exists() else d
        dest = self.target_dirs[1] if len(self.target_dirs) > 1 else self.target_dirs[0]
        backup_sub = dest / "Backup_Data"
        return backup_sub if backup_sub.exists() else dest

    # Xử lý chế độ sao chép theo cụm thư mục
    def _handle_copy_mode(self, files: List[Path], target_count: int) -> Dict[str, Any]:
        files_to_copy = self.select_files_clustered(files, target_count, locality_ratio=0.85)
        dest_dir = self._get_destination_dir()
        copied_files = self._execute_copy(files_to_copy, dest_dir)
        print(f"[+] [{self.name}:COPY] Hoàn thành sao chép {len(copied_files)}/{len(files_to_copy)} tệp tin.")
        return {"files_copied": len(copied_files)}

    # Xử lý chế độ đổi tên theo cụm thư mục
    def _handle_rename_mode(self, files: List[Path], target_count: int) -> Dict[str, Any]:
        files_to_rename = self.select_files_clustered(files, target_count, locality_ratio=0.85)
        renamed_count = self._execute_rename(files_to_rename)
        print(f"[+] [{self.name}:RENAME] Hoàn thành đổi tên {renamed_count}/{len(files_to_rename)} tệp tin (Giữ nguyên đuôi).")
        return {"files_renamed": renamed_count}

    # Xử lý chế độ xóa (ưu tiên bản sao copy_* theo cụm trước file mồi)
    def _handle_delete_mode(self, files: List[Path], target_count: int) -> Dict[str, Any]:
        copy_files = [f for f in files if f.name.lower().startswith("copy_")]
        other_files = [f for f in files if not f.name.lower().startswith("copy_")]

        files_to_delete = self.select_files_clustered(copy_files, target_count, locality_ratio=0.85)
        if len(files_to_delete) < target_count:
            needed = target_count - len(files_to_delete)
            files_to_delete.extend(self.select_files_clustered(other_files, needed, locality_ratio=0.85))

        deleted_count = self._execute_delete(files_to_delete)
        print(f"[+] [{self.name}:DELETE] Hoàn thành xóa {deleted_count}/{len(files_to_delete)} tệp tin.")
        return {"files_deleted": deleted_count}

    # Xử lý chế độ đọc tuần tự theo cụm thư mục
    def _handle_read_mode(self, files: List[Path], target_count: int) -> Dict[str, Any]:
        files_to_read = self.select_files_clustered(files, target_count, locality_ratio=0.85)
        read_count = self._execute_read(files_to_read)
        print(f"[+] [{self.name}:READ] Hoàn thành đọc {read_count}/{len(files_to_read)} tệp tin.")
        return {"files_read": read_count}

    # Thực thi kịch bản quản lý file qua bảng điều phối chế độ
    def execute(self, mode: Optional[str] = None) -> Dict[str, Any]:
        active_mode = self._resolve_mode(mode)
        available_files = self.find_files()
        if not available_files:
            print("[!] Không tìm thấy file mồi nào trong các thư mục giám sát.")
            return {"workload": self.name, "mode": active_mode, "status": "skipped", "message": "Không có file"}

        if len(available_files) < self.min_files:
            target_count = len(available_files)
        else:
            target_count = random.randint(self.min_files, min(len(available_files), self.max_files))

        result_payload: Dict[str, Any] = {
            "workload": self.name,
            "mode": active_mode,
            "status": "success",
            "target_count": target_count,
        }

        handler_name = self._HANDLERS.get(active_mode)
        if handler_name:
            handler = getattr(self, handler_name)
            result_payload.update(handler(available_files, target_count))

        return result_payload
