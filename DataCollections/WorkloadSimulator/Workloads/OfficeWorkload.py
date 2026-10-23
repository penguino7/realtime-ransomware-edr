
import time
import random
from pathlib import Path
from typing import List, Dict, Optional, Any
from faker import Faker
import docx
import openpyxl
from .BaseWorkload import BaseWorkload


class OfficeWorkload(BaseWorkload):
    """
    Kịch bản mở đọc và chỉnh sửa các tệp tin Word (.docx), Excel (.xlsx)
    và Text (.txt) có sẵn
    """

    def __init__(
        self,
        target_dirs: Optional[List[Path]] = None,
        locale: str = "vi_VN"
    ) -> None:
        
        super().__init__(target_dirs=target_dirs, name="OfficeWorkload")
        try:
            self.faker = Faker(locale)
        except Exception:
            self.faker = Faker("en_US")

    def _modify_docx(self, file_path: Path) -> bool:
        """Mở file Word .docx, chèn thêm đoạn văn mới và lưu đè lại."""
        try:
            doc = docx.Document(str(file_path))
            p = doc.add_paragraph(self.faker.paragraph(nb_sentences=random.randint(3, 6)))
            p.paragraph_format.space_after = docx.shared.Pt(8)
            doc.save(str(file_path))
            return True
        except Exception:
            return False

    def _modify_xlsx(self, file_path: Path) -> bool:
        """Mở file Excel .xlsx, thêm 2-4 dòng giao dịch mới và lưu đè lại."""
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

    def _modify_txt(self, file_path: Path) -> bool:
        """Mở file Text .txt và nối thêm đoạn văn bản mới vào cuối file."""
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

    def execute(self) -> Dict[str, Any]:
        """
        Thực thi kịch bản mở đọc và chỉnh sửa tài liệu văn phòng.
        """
        target_extensions = [".docx", ".xlsx", ".txt"]
        files = self.find_files(extensions=target_extensions)

        if not files:
            print("[!] Không tìm thấy file tài liệu Word/Excel/Text nào trong DecoyDocs.")
            return {"workload": self.name, "status": "skipped", "message": "Không có file văn bản"}

        # Chọn ngẫu nhiên từ 8 đến 15 file để chỉnh sửa
        random.shuffle(files)
        selected_files = files[:min(len(files), 15)]

        print(f"[*] [{self.name}] Bắt đầu mở và chỉnh sửa {len(selected_files)} tài liệu văn phòng...")
        modified_count = 0

        for file_path in selected_files:
            ext = file_path.suffix.lower()
            success = False

            if ext == ".docx":
                success = self._modify_docx(file_path)
            elif ext == ".xlsx":
                success = self._modify_xlsx(file_path)
            elif ext == ".txt":
                success = self._modify_txt(file_path)

            if success:
                modified_count += 1

            # Tạm nghỉ tự nhiên (0.2s - 0.6s) mô phỏng nhịp điệu thao tác người dùng
            self.random_delay(0.2, 0.6)

        print(f"[+] [{self.name}] Đã chỉnh sửa thành công {modified_count}/{len(selected_files)} tài liệu.")

        return {
            "workload": self.name,
            "status": "success",
            "files_modified": modified_count,
            "total_targeted": len(selected_files)
        }
