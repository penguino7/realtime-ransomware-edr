import random
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .BaseWorkload import BaseWorkload


# Kịch bản nén và giải nén tệp theo cụm thư mục bằng 7-Zip hoặc WinRAR (hỗ trợ cả mật khẩu AES-256)
class CompressionWorkload(BaseWorkload):

    # Khởi tạo công cụ nén và cấu hình quy mô nén/giải nén theo lô
    def __init__(
        self,
        target_dirs: Optional[List[Path]] = None,
        custom_tool_path: Optional[str] = None,
        min_files: int = 120,
        max_files: int = 300,
        batch_size: int = 40,
        cleanup_after: bool = True,
    ) -> None:
        super().__init__(target_dirs=target_dirs, name="CompressionWorkload")
        self.seven_zip_bin: Optional[Path] = self._locate_binary(
            custom_tool_path,
            keyword="7z",
            candidates=[
                shutil.which("7z.exe"),
                shutil.which("7z"),
                r"C:\Program Files\7-Zip\7z.exe",
                r"C:\Program Files (x86)\7-Zip\7z.exe",
            ],
        )
        self.winrar_bin: Optional[Path] = self._locate_binary(
            custom_tool_path,
            keyword="rar",
            candidates=[
                shutil.which("Rar.exe"),
                shutil.which("WinRAR.exe"),
                r"C:\Program Files\WinRAR\Rar.exe",
                r"C:\Program Files\WinRAR\WinRAR.exe",
                r"C:\Program Files (x86)\WinRAR\Rar.exe",
                r"C:\Program Files (x86)\WinRAR\WinRAR.exe",
            ],
        )

        self.available_engines: List[str] = []
        if self.seven_zip_bin:
            self.available_engines.append("7zip")
        if self.winrar_bin:
            self.available_engines.append("winrar")

        self.min_files: int = max(1, int(min_files))
        self.max_files: int = max(self.min_files, int(max_files))
        self.batch_size: int = max(10, int(batch_size))
        self.cleanup_after: bool = bool(cleanup_after)

    # Tìm đường dẫn tệp thực thi công cụ nén trên hệ thống
    @staticmethod
    def _locate_binary(
        custom_path: Optional[str],
        keyword: str,
        candidates: List[Optional[str]],
    ) -> Optional[Path]:
        for path_str in [custom_path, *candidates]:
            if not path_str:
                continue
            p = Path(path_str)
            if p.exists() and p.is_file() and keyword in p.name.lower():
                return p
        return None

    # Thực thi nén danh sách file thành tệp archive bằng engine đã chọn
    def _compress_batch(
        self,
        engine: str,
        files: List[Path],
        output_archive: Path,
        password: Optional[str] = None,
    ) -> bool:
        list_file = output_archive.parent / f"{engine}_filelist_{output_archive.stem}.tmp"
        try:
            with open(list_file, "w", encoding="utf-8") as f:
                for file_path in files:
                    f.write(f"{file_path}\n")

            if engine == "7zip":
                cmd = [str(self.seven_zip_bin), "a", "-t7z", "-mx=5"]
                if password:
                    cmd.append(f"-p{password}")
                cmd.extend([str(output_archive), f"@{list_file}", "-y"])
            else:
                cmd = [str(self.winrar_bin), "a", "-ibck", "-inul", "-y"]
                if password:
                    cmd.append(f"-p{password}")
                cmd.extend([str(output_archive), f"@{list_file}"])

            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            return process.returncode == 0
        finally:
            if list_file.exists():
                try:
                    list_file.unlink()
                except Exception:
                    pass

    # Giải nén tệp archive ra thư mục tạm để mô phỏng chu trình đọc/ghi thực tế
    def _extract_batch(
        self,
        engine: str,
        archive_path: Path,
        extract_dir: Path,
        password: Optional[str] = None,
    ) -> bool:
        if engine == "7zip":
            cmd = [str(self.seven_zip_bin), "x", str(archive_path), f"-o{extract_dir}"]
            if password:
                cmd.append(f"-p{password}")
            cmd.append("-y")
        else:
            target_dest = str(extract_dir)
            if not target_dest.endswith("\\"):
                target_dest += "\\"
            cmd = [str(self.winrar_bin), "x", "-ibck", "-inul", "-y"]
            if password:
                cmd.append(f"-p{password}")
            cmd.extend([str(archive_path), target_dest])

        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        return process.returncode == 0

    # Dọn dẹp các tệp archive và thư mục giải nén tạm sau khi hoàn tất phiên
    @staticmethod
    def _cleanup_artifacts(archives: List[Path], extract_dirs: List[Path]) -> None:
        for archive in archives:
            if archive.exists():
                try:
                    archive.unlink()
                except Exception:
                    pass
        for extract_dir in extract_dirs:
            if extract_dir.exists():
                shutil.rmtree(extract_dir, ignore_errors=True)

    # Thực thi kịch bản nén và giải nén theo cụm thư mục với nhiều lô liên tiếp
    def execute(self) -> Dict[str, Any]:
        if not self.available_engines:
            print("[!] Không tìm thấy công cụ 7-Zip hoặc WinRAR trên hệ thống.")
            return {"workload": self.name, "status": "failed", "message": "Thiếu công cụ 7-Zip/WinRAR"}

        files = self.find_files()
        if not files:
            print("[!] Không tìm thấy file mồi nào trong DecoyDocs.")
            return {"workload": self.name, "status": "skipped", "message": "Không có file mồi"}

        target_count = (
            random.randint(self.min_files, min(len(files), self.max_files))
            if len(files) >= self.min_files
            else len(files)
        )
        selected_files = self.select_files_clustered(files, target_count=target_count, locality_ratio=0.85)
        batches = [selected_files[i : i + self.batch_size] for i in range(0, len(selected_files), self.batch_size)]

        engine = random.choice(self.available_engines)
        dest_dir = next((d for d in self.target_dirs if d.exists()), self.target_dirs[0])
        dest_dir.mkdir(parents=True, exist_ok=True)
        timestamp = int(time.time())

        created_archives: List[Path] = []
        created_extract_dirs: List[Path] = []
        compressed_total = 0
        encrypted_batches = 0

        try:
            for batch_idx, batch_files in enumerate(batches):
                is_encrypted = random.choice([True, False])
                password = "SecurePass2026!" if is_encrypted else None
                ext = "7z" if engine == "7zip" else "rar"
                archive = dest_dir / f"workload_{engine}_{timestamp}_{batch_idx + 1}.{ext}"
                enc_label = "MẬT KHẨU" if is_encrypted else "thông thường"

                print(f"[*] Lô {batch_idx + 1}/{len(batches)}: nén {len(batch_files)} files bằng {engine} [{enc_label}]...")
                ok = self._compress_batch(engine, batch_files, archive, password=password)
                if not ok or not archive.exists():
                    continue

                created_archives.append(archive)
                compressed_total += len(batch_files)
                if is_encrypted:
                    encrypted_batches += 1

                # Giải nén sang thư mục con riêng cho từng lô và giữ nguyên nhịp burst/pause tự nhiên
                extract_dir = dest_dir / f"Temp_Extracted_{timestamp}_{batch_idx + 1}"
                extract_dir.mkdir(parents=True, exist_ok=True)
                created_extract_dirs.append(extract_dir)
                self._extract_batch(engine, archive, extract_dir, password=password)

                if batch_idx < len(batches) - 1:
                    self.burst_or_pause(batch_idx, burst_size=2, burst_delay=(0.15, 0.4), pause_range=(1.5, 3.0))
        finally:
            if self.cleanup_after:
                self.random_delay(0.3, 0.6)
                self._cleanup_artifacts(created_archives, created_extract_dirs)

        status = "success" if created_archives else "failed"
        print(f"[+] Hoàn thành {len(created_archives)}/{len(batches)} lô nén & giải nén ({compressed_total} files, {engine}).")
        return {
            "workload": self.name,
            "status": status,
            "engine": engine,
            "batches_completed": len(created_archives),
            "files_compressed": compressed_total,
            "encrypted_batches": encrypted_batches,
        }
