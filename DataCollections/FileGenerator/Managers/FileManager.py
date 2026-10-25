
import sys
import json
import random
from pathlib import Path
from typing import List, Dict, Optional, Any
from faker import Faker

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
        """
        Xác định các thư mục mục tiêu chiến lược của người dùng trên Windows:
        - 8 thư mục người dùng: Desktop, Documents, Downloads, Pictures, Contacts, Favorites, Music, Videos.
        - Các ổ đĩa hệ thống: C:\\DecoyDocs, D:\\DecoyDocs (nếu cho phép ghi).
        """
        home = Path.home()
        standard_user_folders = [
            "Desktop",
            "Documents",
            "Downloads",
            "Pictures",
            "Contacts",
            "Favorites",
            "Music",
            "Videos",
        ]

        directories: List[Path] = []
        for folder_name in standard_user_folders:
            folder_path = home / folder_name / "DecoyDocs"
            directories.append(folder_path)

        # Thêm thư mục gốc trên các phân vùng ổ đĩa (nếu môi trường cho phép)
        for drive in ["C:\\", "D:\\"]:
            drive_path = Path(drive)
            if drive_path.exists():
                decoy_drive_folder = drive_path / "DecoyDocs"
                try:
                    # Kiểm tra quyền ghi nhanh
                    test_dir = decoy_drive_folder / ".test_write"
                    test_dir.mkdir(parents=True, exist_ok=True)
                    test_dir.rmdir()
                    directories.append(decoy_drive_folder)
                except (PermissionError, OSError):
                    pass

        # Nếu không có thư mục nào truy cập được, mặc định dùng thư mục làm việc hiện tại
        if not directories:
            directories.append(Path.cwd() / "DecoyDocs")

        return directories

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

    def cleanup(self) -> int:
        """
        Dọn dẹp môi trường (Rollback): Xóa toàn bộ file mồi đã tạo và các thư mục Decoy rỗng.
        Truy vết qua decoy_registry.json để đảm bảo an toàn tuyệt đối, không xóa nhầm file cá nhân.
        """
        print("[*] Đang tiến hành dọn dẹp môi trường tệp tin mồi an toàn...")
        deleted_count = 0

        # Lấy danh sách file cần xóa từ bộ nhớ hoặc nạp từ file sổ hộ khẩu registry
        files_to_delete = [str(f.resolve()) for f in self.created_files]
        if not files_to_delete:
            files_to_delete = self._load_registry()

        for f_str in files_to_delete:
            try:
                f_path = Path(f_str)
                if f_path.exists():
                    f_path.unlink()
                    deleted_count += 1
            except Exception as error:
                print(f"[!] Không thể xóa file {f_str}: {error}", file=sys.stderr)

        self.created_files.clear()
        self._clear_registry()

        # Quét dọn các thư mục Decoy rỗng
        for directory in self.target_dirs:
            if directory.exists():
                for remaining_file in directory.rglob("*"):
                    if remaining_file.is_file():
                        fname = remaining_file.name.lower()
                        if fname.startswith("decoy_") or fname.startswith("!00_") or fname.startswith("000_"):
                            try:
                                remaining_file.unlink()
                                deleted_count += 1
                            except Exception:
                                pass
                for sub in sorted(directory.rglob("*"), reverse=True):
                    if sub.is_dir():
                        try:
                            sub.rmdir()
                        except Exception:
                            pass
                try:
                    directory.rmdir()
                except Exception:
                    pass

        print(f"[+] Dọn dẹp hoàn tất. Đã xóa sạch {deleted_count} file mồi.")
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
