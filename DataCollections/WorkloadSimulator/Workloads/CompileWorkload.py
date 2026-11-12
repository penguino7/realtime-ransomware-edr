import marshal
import os
import py_compile
import random
import shutil
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from .BaseWorkload import BaseWorkload

# Thiết lập encoding UTF-8 cho console Windows tránh UnicodeEncodeError
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


# Kịch bản giả lập biên dịch mã nguồn (.py -> .pyc, .cpp -> .obj) tạo tệp nhị phân & đổi tên nguyên tử
class CompileWorkload(BaseWorkload):

    BURST_SIZE = 20

    # Khởi tạo workload biên dịch với dải số lượng tệp mục tiêu và tự dò trình biên dịch C++ nếu có
    def __init__(
        self,
        target_dirs: Optional[List[Path]] = None,
        min_files: int = 60,
        max_files: int = 150,
    ) -> None:
        super().__init__(target_dirs=target_dirs, name="CompileWorkload")
        self.min_files = max(5, min_files)
        self.max_files = max(self.min_files, max_files)
        self._cpp_compiler: Optional[str] = shutil.which("g++") or shutil.which("clang++")

    # Ghi dữ liệu nhị phân qua tệp tạm rồi đổi tên nguyên tử (mô phỏng hành vi linker/compiler thực tế)
    @staticmethod
    def _write_atomic_artifact(target_path: Path, payload: bytes) -> bool:
        tmp_path = target_path.with_name(f"{target_path.name}.{os.getpid()}.{random.randint(1000, 9999)}.tmp")
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp_path, "wb") as f:
                f.write(payload)
            os.replace(tmp_path, target_path)
            return True
        except Exception:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
            return False

    # Biên dịch tệp Python (.py) sang bytecode (.pyc) trong __pycache__ bằng py_compile
    def _compile_python(self, file_path: Path) -> bool:
        cache_dir = file_path.parent / "__pycache__"
        tag = sys.implementation.cache_tag or "cpython-311"
        cfile_path = cache_dir / f"{file_path.stem}.{tag}.pyc"
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            py_compile.compile(str(file_path), cfile=str(cfile_path), doraise=True)
            return cfile_path.exists()
        except py_compile.PyCompileError:
            # Nếu tệp mồi có cú pháp tự do, biên dịch module đại diện để giữ đúng luồng .pyc thực tế
            try:
                source_len = len(file_path.read_text(encoding="utf-8", errors="ignore"))
                code_obj = compile(f"__compiled_size__ = {source_len}\n", str(file_path), "exec")
                header = struct.pack("<IIII", 0x0A0D0D6F, 0, int(time.time()), source_len & 0xFFFFFFFF)
                payload = header + marshal.dumps(code_obj)
                return self._write_atomic_artifact(cfile_path, payload)
            except Exception:
                return False
        except Exception:
            return False

    # Biên dịch tệp C++ (.cpp) sang object (.obj) bằng trình biên dịch thật hoặc fallback mô phỏng object binary
    def _compile_cpp(self, file_path: Path) -> bool:
        build_dir = file_path.parent / "build"
        obj_path = build_dir / f"{file_path.stem}.obj"
        try:
            build_dir.mkdir(parents=True, exist_ok=True)
            if self._cpp_compiler:
                proc = subprocess.run(
                    [self._cpp_compiler, "-c", str(file_path), "-o", str(obj_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    check=False,
                )
                if proc.returncode == 0 and obj_path.exists():
                    return True

            # Fallback khi thiếu trình biên dịch hoặc tệp mồi thiếu header: đọc mã nguồn và xuất khối object nén
            source_bytes = file_path.read_bytes()
            compressed_obj = zlib.compress(source_bytes or b"// empty module\n", level=6)
            coff_stub = struct.pack("<HHIII", 0x8664, 1, int(time.time()), len(source_bytes), len(compressed_obj))
            return self._write_atomic_artifact(obj_path, coff_stub + compressed_obj)
        except Exception:
            return False

    # Dọn dẹp thư mục build artifact (__pycache__, build) sau khi kết thúc phiên thu thập
    def cleanup_artifacts(self) -> int:
        removed = 0
        for directory in self.target_dirs:
            dir_path = Path(directory)
            if not dir_path.exists():
                continue
            for folder_name in ("__pycache__", "build"):
                for artifact_dir in dir_path.rglob(folder_name):
                    if artifact_dir.is_dir():
                        try:
                            shutil.rmtree(artifact_dir)
                            removed += 1
                        except Exception:
                            pass
        return removed

    # Thực thi kịch bản biên dịch theo cụm thư mục
    def execute(self) -> Dict[str, Any]:
        files = self.find_files(extensions=[".py", ".cpp"])
        if not files:
            print("[!] Không tìm thấy tệp .py hoặc .cpp nào trong DecoyDocs để biên dịch.")
            return {"workload": self.name, "status": "skipped", "message": "Không có file mã nguồn (.py/.cpp)"}

        target_count = (
            random.randint(self.min_files, min(len(files), self.max_files))
            if len(files) >= self.min_files
            else len(files)
        )
        selected_files = self.select_files_clustered(files, target_count=target_count, locality_ratio=0.90)

        print(f"[*] [{self.name}] Bắt đầu biên dịch {len(selected_files)} tệp mã nguồn (.py/.cpp)...")
        compiled_count = 0

        for idx, file_path in enumerate(selected_files):
            ext = file_path.suffix.lower()
            ok = self._compile_python(file_path) if ext == ".py" else self._compile_cpp(file_path)
            if ok:
                compiled_count += 1

            self.burst_or_pause(idx, burst_size=self.BURST_SIZE, burst_delay=(0.01, 0.04), pause_range=(0.8, 2.0))

        print(f"[+] [{self.name}] Đã biên dịch thành công {compiled_count}/{len(selected_files)} tệp tin.")

        return {
            "workload": self.name,
            "status": "success",
            "files_compiled": compiled_count,
            "total_targeted": len(selected_files),
        }
