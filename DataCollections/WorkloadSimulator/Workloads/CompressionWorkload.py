
import sys
import shutil
import random
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Optional, Any
from .BaseWorkload import BaseWorkload


class CompressionWorkload(BaseWorkload):
    """
    Kịch bản nén và giải nén tệp tin mồi sử dụng trực tiếp các phần mềm
    7-Zip (7z.exe) hoặc WinRAR (WinRAR.exe / Rar.exe).
    """

    def __init__(
        self,
        target_dirs: Optional[List[Path]] = None,
        custom_tool_path: Optional[str] = None
    ) -> None:
       
        super().__init__(target_dirs=target_dirs, name="CompressionWorkload")
        self.seven_zip_bin: Optional[Path] = self._locate_7zip(custom_tool_path)
        self.winrar_bin: Optional[Path] = self._locate_winrar(custom_tool_path)

        # Danh sách các công cụ nén khả dụng trên máy
        self.available_engines: List[str] = []
        if self.seven_zip_bin:
            self.available_engines.append("7zip")
        if self.winrar_bin:
            self.available_engines.append("winrar")

    def _locate_7zip(self, custom_path: Optional[str] = None) -> Optional[Path]:
        """Tự động tìm kiếm file thực thi 7z.exe trên hệ thống."""
        candidates = [
            custom_path,
            shutil.which("7z.exe"),
            shutil.which("7z"),
            r"C:\Program Files\7-Zip\7z.exe",
            r"C:\Program Files (x86)\7-Zip\7z.exe",
        ]
        for path_str in candidates:
            if path_str:
                p = Path(path_str)
                if p.exists() and p.is_file() and "7z" in p.name.lower():
                    return p
        return None

    def _locate_winrar(self, custom_path: Optional[str] = None) -> Optional[Path]:
        """Tự động tìm kiếm file thực thi WinRAR.exe hoặc Rar.exe trên hệ thống."""
        candidates = [
            custom_path,
            shutil.which("Rar.exe"),
            shutil.which("WinRAR.exe"),
            r"C:\Program Files\WinRAR\Rar.exe",
            r"C:\Program Files\WinRAR\WinRAR.exe",
            r"C:\Program Files (x86)\WinRAR\Rar.exe",
            r"C:\Program Files (x86)\WinRAR\WinRAR.exe",
        ]
        for path_str in candidates:
            if path_str:
                p = Path(path_str)
                if p.exists() and p.is_file() and ("winrar" in p.name.lower() or "rar" in p.name.lower()):
                    return p
        return None

    def _compress_with_7zip(self, files: List[Path], output_archive: Path) -> bool:
        """Kích hoạt tiến trình 7z.exe nén danh sách file thành archive .7z."""
        list_file = output_archive.parent / "7z_filelist.tmp"
        try:
            with open(list_file, "w", encoding="utf-8") as f:
                for file_path in files:
                    f.write(f"{file_path}\n")

            # Lệnh: 7z.exe a -t7z -mx=5 <output_archive> @<list_file> -y
            cmd = [
                str(self.seven_zip_bin),
                "a",
                "-t7z",
                "-mx=5",
                str(output_archive),
                f"@{list_file}",
                "-y"
            ]
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            return process.returncode == 0
        finally:
            if list_file.exists():
                try:
                    list_file.unlink()
                except Exception:
                    pass

    def _extract_with_7zip(self, archive_path: Path, extract_dir: Path) -> bool:
        """Kích hoạt tiến trình 7z.exe giải nén file .7z."""
        cmd = [
            str(self.seven_zip_bin),
            "x",
            str(archive_path),
            f"-o{extract_dir}",
            "-y"
        ]
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        return process.returncode == 0

    def _compress_with_winrar(self, files: List[Path], output_archive: Path) -> bool:
        """
        Kích hoạt tiến trình WinRAR.exe (hoặc Rar.exe) nén danh sách file thành archive .rar.
        """
        list_file = output_archive.parent / "winrar_filelist.tmp"
        try:
            with open(list_file, "w", encoding="utf-8") as f:
                for file_path in files:
                    f.write(f"{file_path}\n")

            # Cú pháp WinRAR CLI: WinRAR.exe a -ibck -inul -y <archive.rar> @<filelist.tmp>
            cmd = [
                str(self.winrar_bin),
                "a",
                "-ibck",
                "-inul",
                "-y",
                str(output_archive),
                f"@{list_file}"
            ]
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            return process.returncode == 0
        finally:
            if list_file.exists():
                try:
                    list_file.unlink()
                except Exception:
                    pass

    def _extract_with_winrar(self, archive_path: Path, extract_dir: Path) -> bool:
        """Kích hoạt tiến trình WinRAR.exe giải nén file .rar."""
        # WinRAR yêu cầu đường dẫn thư mục giải nén phải kết thúc bằng dấu gạch chéo '\'
        target_dest = str(extract_dir)
        if not target_dest.endswith("\\"):
            target_dest += "\\"

        cmd = [
            str(self.winrar_bin),
            "x",
            "-ibck",
            "-inul",
            "-y",
            str(archive_path),
            target_dest
        ]
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        return process.returncode == 0

    def execute(self) -> Dict[str, Any]:
        """
        Thực thi kịch bản nén và giải nén bằng 7-Zip hoặc WinRAR.
        """
        if not self.available_engines:
            print("[!] Không tìm thấy công cụ 7-Zip hoặc WinRAR trên hệ thống.")
            return {"workload": self.name, "status": "failed", "message": "Thiếu công cụ 7-Zip/WinRAR"}

        files = self.find_files()
        if not files:
            print("[!] Không tìm thấy file mồi nào trong DecoyDocs.")
            return {"workload": self.name, "status": "skipped", "message": "Không có file mồi"}

        engine = random.choice(self.available_engines)
        selected_files = files[:min(len(files), 35)]
        dest_dir = self.target_dirs[0]
        timestamp = int(time.time())

        # Chọn công cụ nén và thực hiện nén
        if engine == "7zip":
            archive = dest_dir / f"workload_7zip_{timestamp}.7z"
            print(f"[*] Nén {len(selected_files)} files bằng 7-Zip...")
            ok = self._compress_with_7zip(selected_files, archive)
        else:
            archive = dest_dir / f"workload_winrar_{timestamp}.rar"
            print(f"[*] Nén {len(selected_files)} files bằng WinRAR...")
            ok = self._compress_with_winrar(selected_files, archive)

        if not ok or not archive.exists():
            return {"workload": self.name, "status": "failed", "message": "Nén thất bại"}

        # Giải nén thử nghiệm
        self.random_delay(0.4, 0.8)
        extract_dir = dest_dir / "Temp_Extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)
        print(f"[*] Giải nén thử nghiệm ra {extract_dir.name}...")

        if engine == "7zip":
            self._extract_with_7zip(archive, extract_dir)
        else:
            self._extract_with_winrar(archive, extract_dir)

        # Dọn dẹp tệp tin nén và thư mục giải nén tạm
        self.random_delay(0.2, 0.4)
        if archive.exists():
            archive.unlink()
        if extract_dir.exists():
            shutil.rmtree(extract_dir, ignore_errors=True)

        print(f"[+] Hoàn thành chu trình nén & giải nén ({engine}).")
        return {
            "workload": self.name,
            "status": "success",
            "engine": engine,
            "files_compressed": len(selected_files)
        }
