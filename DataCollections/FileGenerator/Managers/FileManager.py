
import sys
import json
import random
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Any
from faker import Faker

try:
    from Src.Core.Config import Config
except (ImportError, ValueError):
    from Core.Config import Config

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

try:
    from ..Generators import (
        BaseFileGenerator,
        TextDocumentGenerator,
        StructuredDataGenerator,
        OfficeDocumentGenerator,
        PDFDocumentGenerator,
        ImageFileGenerator,
        SourceCodeGenerator,
        DatabaseConfigFileGenerator,
        ArchiveFileGenerator,
    )
except (ImportError, ValueError):
    from Generators import (
        BaseFileGenerator,
        TextDocumentGenerator,
        StructuredDataGenerator,
        OfficeDocumentGenerator,
        PDFDocumentGenerator,
        ImageFileGenerator,
        SourceCodeGenerator,
        DatabaseConfigFileGenerator,
        ArchiveFileGenerator,
    )


class FileEnvironmentManager:
    """
    Bộ điều phối môi trường mồi nhử tự động phục vụ thử nghiệm và đánh chặn Ransomware.
    """

    REGISTRY_FILENAME = "decoy_registry.json"

    def __init__(self, base_dirs: Optional[List[Path]] = None, locale: str = "vi_VN") -> None:
        try:
            self.faker = Faker(locale)
        except Exception:
            self.faker = Faker("en_US")

        self.target_dirs: List[Path] = base_dirs or self._default_directories()
        self.created_files: List[Path] = []
        self.registry_path = Path(__file__).resolve().parent.parent / self.REGISTRY_FILENAME

        # Đăng ký toàn bộ 19 định dạng chiến lược từ 7 Generator chuyên biệt
        self.generators: Dict[str, BaseFileGenerator] = {
            # 1. Văn bản & Dữ liệu có cấu trúc
            ".txt": TextDocumentGenerator(self.faker),
            ".json": StructuredDataGenerator(self.faker, file_type="json"),
            ".csv": StructuredDataGenerator(self.faker, file_type="csv"),
            ".pdf": PDFDocumentGenerator(self.faker),
            # 2. Văn phòng Office
            ".docx": OfficeDocumentGenerator(self.faker, doc_type="docx"),
            ".xlsx": OfficeDocumentGenerator(self.faker, doc_type="xlsx"),
            # 3. Mã nguồn & Kịch bản lập trình (Entropy thấp: 4.5 - 5.5)
            ".py": SourceCodeGenerator(self.faker, lang="py"),
            ".sql": SourceCodeGenerator(self.faker, lang="sql"),
            ".html": SourceCodeGenerator(self.faker, lang="html"),
            ".xml": SourceCodeGenerator(self.faker, lang="xml"),
            ".cpp": SourceCodeGenerator(self.faker, lang="cpp"),
            # 4. Cơ sở dữ liệu & Cấu hình máy chủ
            ".db": DatabaseConfigFileGenerator(self.faker, file_type="db"),
            ".sqlite": DatabaseConfigFileGenerator(self.faker, file_type="sqlite"),
            ".ini": DatabaseConfigFileGenerator(self.faker, file_type="ini"),
            ".yaml": DatabaseConfigFileGenerator(self.faker, file_type="yaml"),
            ".log": DatabaseConfigFileGenerator(self.faker, file_type="log"),
            # 5. Đồ họa hình ảnh
            ".jpg": ImageFileGenerator(self.faker, image_format="JPEG"),
            ".png": ImageFileGenerator(self.faker, image_format="PNG"),
            # 6. Tệp nén lưu trữ (Entropy tự nhiên cao: 7.0 - 7.5)
            ".zip": ArchiveFileGenerator(self.faker, archive_type="zip"),
        }

    def _default_directories(self) -> List[Path]:
        return Config.get_monitored_directories()

    def prepare_environment(self) -> None:
        """
        Tự động tạo các thư mục mục tiêu trên đĩa cứng và xây dựng cây thư mục phân cấp (Subdirectories).
        """
        sub_folder_names = [
            "Project_Source",
            "Financial_Reports",
            "HR_Contracts",
            "Personal_Photos",
            "Backup_Data",
            "Config_Prod",
        ]

        active_dirs: List[Path] = []
        for directory in self.target_dirs:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                active_dirs.append(directory)
                # Tạo thêm thư mục con ngẫu nhiên để kích thích hành vi duyệt thư mục (Directory Traversal)
                for sub in sub_folder_names:
                    if random.random() > 0.4:
                        sub_path = directory / sub
                        sub_path.mkdir(parents=True, exist_ok=True)
            except (PermissionError, OSError) as e:
                print(f"[!] Bỏ qua thư mục không có quyền truy cập {directory}: {e}", file=sys.stderr)

        if active_dirs:
            self.target_dirs = active_dirs
        else:
            local_fallback = Path.cwd() / "DecoyDocs"
            local_fallback.mkdir(parents=True, exist_ok=True)
            self.target_dirs = [local_fallback]

    def _get_target_leaves(self) -> List[Path]:
        """Lấy danh sách tất cả các thư mục gốc và thư mục con để phân bổ file."""
        all_destinations: List[Path] = []
        for directory in self.target_dirs:
            if directory.exists():
                all_destinations.append(directory)
                for sub in directory.iterdir():
                    if sub.is_dir():
                        all_destinations.append(sub)
        return all_destinations or self.target_dirs

    def populate(self, total_files: int = 300) -> List[Path]:
        """
        Sinh và phân phối số lượng tệp tin mồi ngẫu nhiên vào các thư mục mục tiêu đa tầng:
        - Sử dụng bẫy Canary: Tiền tố ký tự đặc biệt (!00_, 000_, $_, aaa_) để nằm ở đầu bảng chữ cái.
        - Tên file gợi cảm giác tài liệu nghiệp vụ quan trọng (Confidential, Accounting, Backup, Payroll).
        - Ghi nhận vào file registry để truy vết và rollback sạch sẽ 100%.
        """
        self.prepare_environment()
        destinations = self._get_target_leaves()
        extensions = list(self.generators.keys())

        # Danh sách tiền tố bẫy Canary ưu tiên thứ tự duyệt A -> Z của ransomware
        canary_prefixes = ["!00_", "000_", "$_", "aaa_", "decoy_"]
        business_topics = [
            "Confidential",
            "Accounting",
            "Financial_Report",
            "Backup_Admin",
            "Client_Database",
            "Payroll_2026",
            "Contract_Master",
        ]

        print(f"[*] Đang sinh {total_files} file vào {len(destinations)} thư mục mục tiêu đa tầng...")

        registry_entries = self._load_registry()

        for i in range(1, total_files + 1):
            target_dir = random.choice(destinations)
            ext = random.choice(extensions)

            prefix = random.choice(canary_prefixes)
            topic = random.choice(business_topics)
            clean_word = "".join(c for c in self.faker.word() if c.isalnum())
            filename = f"{prefix}{topic}_{clean_word}_{i:03d}{ext}"
            file_path = target_dir / filename

            try:
                # Ủy quyền cho Generator chuyên biệt xử lý nội dung và Magic Bytes chuẩn
                self.generators[ext].generate(file_path)
                self.created_files.append(file_path)
                registry_entries.append(str(file_path.resolve()))
            except Exception as error:
                print(f"[!] Lỗi khi tạo file {file_path}: {error}", file=sys.stderr)

        # Lưu sổ hộ khẩu các file đã tạo vào registry JSON
        self._save_registry(registry_entries)

        print(f"[+] Hoàn tất! Đã tạo thành công {len(self.created_files)}/{total_files} file mồi.")
        return self.created_files

    # Xóa cưỡng bức một cây thư mục, tự động gỡ cờ read-only nếu tệp tin bị khóa
    @staticmethod
    def _force_remove_tree(dir_path: Path) -> None:
        import os
        import stat

        def _handle_remove_readonly(func, path, exc_info):
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception:
                pass

        try:
            shutil.rmtree(dir_path, onerror=_handle_remove_readonly)
        except Exception:
            shutil.rmtree(dir_path, ignore_errors=True)

    # Dọn dẹp môi trường: Xóa sạch tận gốc các thư mục DecoyDocs (gồm cả file mồi, file mã hóa, tệp rác và registry)
    def cleanup(self) -> int:
        print("[*] Đang tiến hành dọn dẹp sạch tận gốc các thư mục mồi (DecoyDocs)...")
        deleted_count = 0

        # Quét và xóa tận gốc từng thư mục mồi mục tiêu
        for directory in self.target_dirs:
            dir_path = Path(directory)
            if not dir_path.exists():
                continue

            # Kiểm tra an toàn nghiêm ngặt: chỉ xóa nếu tên thư mục là DecoyDocs hoặc chứa từ khóa decoy
            # Tránh tuyệt đối việc xóa nhầm thư mục người dùng (Desktop, Documents, Downloads, root drive)
            dir_name = dir_path.name.lower()
            if "decoy" not in dir_name and dir_path != (Path.cwd() / "DecoyDocs"):
                print(f"[!] Bỏ qua thư mục không an toàn: {dir_path}", file=sys.stderr)
                continue

            try:
                # Đếm tổng số tệp bên trong trước khi xóa để báo cáo chính xác
                file_count = sum(1 for p in dir_path.rglob("*") if p.is_file())
                self._force_remove_tree(dir_path)
                deleted_count += file_count
                print(f"[+] Đã xóa sạch toàn bộ thư mục: {dir_path} ({file_count} tệp tin)")
            except Exception as error:
                print(f"[!] Lỗi khi xóa thư mục {dir_path}: {error}", file=sys.stderr)

        self.created_files.clear()
        self._clear_registry()

        print(f"[+] Dọn dẹp hoàn tất. Đã xóa sạch {deleted_count} file và toàn bộ các thư mục DecoyDocs.")
        return deleted_count

    def _save_registry(self, entries: List[str]) -> None:
        """Lưu danh sách đường dẫn file mồi vào tệp registry JSON."""
        try:
            self.registry_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"[!] Cảnh báo: Không thể lưu registry: {e}", file=sys.stderr)

    def _load_registry(self) -> List[str]:
        """Đọc danh sách đường dẫn file mồi từ tệp registry JSON."""
        if not self.registry_path.exists():
            return []
        try:
            return json.loads(self.registry_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _clear_registry(self) -> None:
        """Xóa tệp registry sau khi dọn dẹp hoàn tất."""
        if self.registry_path.exists():
            try:
                self.registry_path.unlink()
            except Exception:
                pass

    def get_summary_report(self) -> Dict[str, Any]:
        """
        Thống kê tổng số lượng file, phân bổ theo 19 định dạng và tổng dung lượng chiếm dụng.
        """
        breakdown: Dict[str, int] = {}
        total_size_bytes = 0

        for file_path in self.created_files:
            if file_path.exists():
                ext = file_path.suffix.lower()
                breakdown[ext] = breakdown.get(ext, 0) + 1
                total_size_bytes += file_path.stat().st_size

        return {
            "total_files": len(self.created_files),
            "breakdown_by_extension": breakdown,
            "total_size_bytes": total_size_bytes,
            "total_size_mb": round(total_size_bytes / (1024 * 1024), 2),
            "target_directories": [str(d) for d in self.target_dirs]
        }
