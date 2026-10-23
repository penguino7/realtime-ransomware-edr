"""
Lớp điều phối việc tạo các file
"""

import sys
import random
from pathlib import Path
from typing import List, Dict, Optional, Any
from faker import Faker


try:
    from ..Generators import (
        BaseFileGenerator,
        TextDocumentGenerator,
        StructuredDataGenerator,
        OfficeDocumentGenerator,
        PDFDocumentGenerator,
        ImageFileGenerator,
    )
except (ImportError, ValueError):
    from Generators import (
        BaseFileGenerator,
        TextDocumentGenerator,
        StructuredDataGenerator,
        OfficeDocumentGenerator,
        PDFDocumentGenerator,
        ImageFileGenerator,
    )


class FileEnvironmentManager:

    def __init__(self, base_dirs: Optional[List[Path]] = None, locale: str = "vi_VN") -> None:
       
        try:
            self.faker = Faker(locale)
        except Exception:
            self.faker = Faker("en_US")

        self.target_dirs: List[Path] = base_dirs or self._default_directories()
        self.created_files: List[Path] = []

        self.generators: Dict[str, BaseFileGenerator] = {
            ".txt": TextDocumentGenerator(self.faker),
            ".json": StructuredDataGenerator(self.faker, file_type="json"),
            ".csv": StructuredDataGenerator(self.faker, file_type="csv"),
            ".docx": OfficeDocumentGenerator(self.faker, doc_type="docx"),
            ".xlsx": OfficeDocumentGenerator(self.faker, doc_type="xlsx"),
            ".pdf": PDFDocumentGenerator(self.faker),
            ".jpg": ImageFileGenerator(self.faker, image_format="JPEG"),
            ".png": ImageFileGenerator(self.faker, image_format="PNG"),
        }

    def _default_directories(self) -> List[Path]:
        """
        Xác định 3 thư mục nhạy cảm mục tiêu chuẩn của người dùng trên Windows:
        - C:\\Users\\<User>\\Desktop\\DecoyDocs
        - C:\\Users\\<User>\\Documents\\DecoyDocs
        - C:\\Users\\<User>\\Downloads\\DecoyDocs
        """
        home = Path.home()
        return [
            home / "Desktop" / "DecoyDocs",
            home / "Documents" / "DecoyDocs",
            home / "Downloads" / "DecoyDocs",
        ]

    def prepare_environment(self) -> None:
        """Tự động tạo các thư mục mục tiêu trên đĩa cứng nếu chưa tồn tại."""
        for directory in self.target_dirs:
            directory.mkdir(parents=True, exist_ok=True)

    def populate(self, total_files: int = 300) -> List[Path]:
        """
        Sinh và phân phối số lượng tệp tin mồi ngẫu nhiên vào các thư mục mục tiêu.
        """
        self.prepare_environment()
        extensions = list(self.generators.keys())

        print(f"[*] Đang sinh {total_files} file vào {len(self.target_dirs)} thư mục mục tiêu...")

        for i in range(1, total_files + 1):
            target_dir = random.choice(self.target_dirs)
            ext = random.choice(extensions)

            # Lấy từ ngẫu nhiên không dấu, loại bỏ ký tự đặc biệt trong tên file
            clean_word = "".join(c for c in self.faker.word() if c.isalnum())
            filename = f"decoy_{clean_word}_{i:04d}{ext}"
            file_path = target_dir / filename

            try:
                # Ủy quyền cho Generator chuyên biệt xử lý nội dung
                self.generators[ext].generate(file_path)
                self.created_files.append(file_path)
            except Exception as error:
                print(f"[!] Lỗi khi tạo file {file_path}: {error}", file=sys.stderr)

        print(f"[+] Hoàn tất! Đã tạo thành công {len(self.created_files)}/{total_files} file mồi.")
        return self.created_files

    def cleanup(self) -> int:
        """
        Dọn dẹp môi trường (Rollback): Xóa toàn bộ file mồi đã tạo và các thư mục DecoyDocs rỗng.

        :return: Số lượng file đã được xóa sạch.
        """
        print("[*] Đang tiến hành dọn dẹp môi trường tệp tin mồi...")
        deleted_count = 0

        # Xóa các file trong danh sách đã tạo
        for file_path in list(self.created_files):
            try:
                if file_path.exists():
                    file_path.unlink()
                    deleted_count += 1
            except Exception as error:
                print(f"[!] Không thể xóa file {file_path}: {error}", file=sys.stderr)

        self.created_files.clear()

        # Quét dọn các file còn sót trong thư mục và gỡ bỏ thư mục rỗng
        for directory in self.target_dirs:
            if directory.exists():
                for remaining_file in directory.glob("*"):
                    try:
                        remaining_file.unlink()
                        deleted_count += 1
                    except Exception:
                        pass
                try:
                    directory.rmdir()
                except Exception:
                    pass

        print(f"[+] Dọn dẹp hoàn tất. Đã xóa sạch {deleted_count} file mồi.")
        return deleted_count

    def get_summary_report(self) -> Dict[str, Any]:
        """
        Thống kê tổng số lượng file, phân bổ theo định dạng và tổng dung lượng chiếm dụng.

        :return: Báo cáo dạng từ điển (Dictionary).
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

