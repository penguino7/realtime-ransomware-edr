import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import docx
import openpyxl
from faker import Faker

from .BaseWorkload import BaseWorkload


# Kịch bản mở đọc và chỉnh sửa các tệp Word (.docx), Excel (.xlsx) và Text (.txt) theo cụm thư mục
class OfficeWorkload(BaseWorkload):

    BURST_SIZE = 15

    # Khởi tạo workload văn phòng với dải số lượng tài liệu mục tiêu
    def __init__(
        self,
        target_dirs: Optional[List[Path]] = None,
        min_files: int = 50,
        max_files: int = 120,
        locale: str = "vi_VN"
    ) -> None:
        super().__init__(target_dirs=target_dirs, name="OfficeWorkload")
        self.min_files = max(5, min_files)
        self.max_files = max(self.min_files, max_files)
        try:
            self.faker = Faker(locale)
        except Exception:
            self.faker = Faker("en_US")

    # Mở file Word .docx, chèn thêm đoạn văn mới và lưu đè
    def _modify_docx(self, file_path: Path) -> bool:
        try:
            doc = docx.Document(str(file_path))
            p = doc.add_paragraph(self.faker.paragraph(nb_sentences=random.randint(3, 6)))
            p.paragraph_format.space_after = docx.shared.Pt(8)
            doc.save(str(file_path))
            return True
        except Exception:
            return False

    # Mở file Excel .xlsx, thêm 2-5 dòng giao dịch mới và lưu đè
    def _modify_xlsx(self, file_path: Path) -> bool:
        try:
            wb = openpyxl.load_workbook(str(file_path))
            ws = wb.active

            statuses = ["Completed", "Pending", "Approved", "Audited"]
            current_rows = ws.max_row

            for i in range(1, random.randint(3, 6)):
                ws.append([
                    f"TXN-{current_rows + i}",
                    self.faker.name(),
                    self.faker.city(),
                    round(random.uniform(150.0, 7500.0), 2),
                    random.choice(statuses)
                ])

            wb.save(str(file_path))
            return True
        except Exception:
            return False

    # Mở file Text .txt và nối thêm đoạn văn bản mới vào cuối file
    def _modify_txt(self, file_path: Path) -> bool:
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            note_content = (
                f"\n\n--- Cập nhật ghi chú lúc {timestamp} bởi {self.faker.name()} ---\n"
                f"{self.faker.paragraph(nb_sentences=4)}"
            )
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(note_content)
            return True
        except Exception:
            return False

    # Thực thi kịch bản chỉnh sửa tài liệu văn phòng theo cụm thư mục và nhịp burst/pause
    def execute(self) -> Dict[str, Any]:
        target_extensions = [".docx", ".xlsx", ".txt"]
        files = self.find_files(extensions=target_extensions)

        if not files:
            print("[!] Không tìm thấy file tài liệu Word/Excel/Text nào trong DecoyDocs.")
            return {"workload": self.name, "status": "skipped", "message": "Không có file văn bản"}

        target_count = (
            random.randint(self.min_files, min(len(files), self.max_files))
            if len(files) >= self.min_files
            else len(files)
        )
        selected_files = self.select_files_clustered(files, target_count=target_count, locality_ratio=0.85)

        print(f"[*] [{self.name}] Bắt đầu mở và chỉnh sửa {len(selected_files)} tài liệu văn phòng...")
        handlers = {
            ".docx": self._modify_docx,
            ".xlsx": self._modify_xlsx,
            ".txt": self._modify_txt,
        }
        modified_count = 0

        for idx, file_path in enumerate(selected_files):
            handler = handlers.get(file_path.suffix.lower())
            if handler and handler(file_path):
                modified_count += 1

            self.burst_or_pause(idx, burst_size=self.BURST_SIZE, burst_delay=(0.02, 0.08), pause_range=(1.0, 2.5))

        print(f"[+] [{self.name}] Đã chỉnh sửa thành công {modified_count}/{len(selected_files)} tài liệu.")

        return {
            "workload": self.name,
            "status": "success",
            "files_modified": modified_count,
            "total_targeted": len(selected_files)
        }
