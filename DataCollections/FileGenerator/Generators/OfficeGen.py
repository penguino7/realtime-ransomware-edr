"""
Tạo các tài liệu văn phòng chuẩn Microsoft Office (.docx, .xlsx).
"""

import random
from pathlib import Path
from faker import Faker
import docx
import openpyxl
from .Base import BaseFileGenerator


class OfficeDocumentGenerator(BaseFileGenerator):
    """
    Tạo các tệp tin tài liệu Word (.docx) và bảng tính Excel (.xlsx)
    """

    def __init__(self, faker: Faker, doc_type: str = "docx") -> None:
        super().__init__(faker)
        self.doc_type = doc_type.lower()
        if self.doc_type not in ("docx", "xlsx"):
            raise ValueError(f"Định dạng Office không hợp lệ: {self.doc_type}. Chỉ hỗ trợ 'docx' hoặc 'xlsx'.")

    def generate(self, file_path: Path) -> None:
    
        if self.doc_type == "docx":
            self._generate_docx(file_path)
        elif self.doc_type == "xlsx":
            self._generate_xlsx(file_path)

    def _generate_docx(self, file_path: Path) -> None:
        """
        Tạo tệp Word .docx chứa tiêu đề, thông tin tác giả và các đoạn văn bản giả lập.
        """
        doc = docx.Document()

        # Thêm tiêu đề chính và metadata
        doc.add_heading(self.faker.sentence(nb_words=6), level=1)
        doc.add_paragraph(f"Tác giả: {self.faker.name()} | Ngày tạo: {self.faker.date()}")

        # Thêm các đoạn văn bản với khoảng cách dòng chuẩn
        for _ in range(random.randint(3, 7)):
            p = doc.add_paragraph(self.faker.paragraph(nb_sentences=random.randint(4, 8)))
            p.paragraph_format.space_after = docx.shared.Pt(10)

        doc.save(str(file_path))

    def _generate_xlsx(self, file_path: Path) -> None:
        """
        Tạo tệp Excel .xlsx chứa bảng tính tài chính với số liệu và trạng thái giao dịch.
        """
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = "Financial_Summary"

        # Định nghĩa dòng tiêu đề cột
        headers = ["Mã giao dịch", "Khách hàng", "Thành phố", "Số tiền (USD)", "Trạng thái"]
        worksheet.append(headers)

        # Bơm các dòng dữ liệu mẫu
        statuses = ["Completed", "Pending", "Approved", "Audited"]
        row_count = random.randint(20, 50)

        for i in range(1, row_count + 1):
            worksheet.append([
                f"TXN-{1000 + i}",
                self.faker.name(),
                self.faker.city(),
                round(random.uniform(100.0, 5000.0), 2),
                random.choice(statuses)
            ])

        workbook.save(str(file_path))
