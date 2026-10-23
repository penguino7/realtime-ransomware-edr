"""
Chuyên trách tạo các tài liệu PDF 

"""

from pathlib import Path
from faker import Faker
from reportlab.pdfgen import canvas
from .Base import BaseFileGenerator


class PDFDocumentGenerator(BaseFileGenerator):

    def generate(self, file_path: Path) -> None:
        """
        Vẽ và xuất ra file PDF gồm tiêu đề, metadata và các khối văn bản ngẫu nhiên.
        """
        pdf_canvas = canvas.Canvas(str(file_path))
        pdf_canvas.setTitle(f"Document - {file_path.stem}")

        # 1. Vẽ tiêu đề tài liệu
        pdf_canvas.setFont("Helvetica-Bold", 14)
        pdf_canvas.drawString(72, 750, self.faker.sentence(nb_words=5))

        # 2. Vẽ thông tin metadata tài liệu
        pdf_canvas.setFont("Helvetica", 9)
        pdf_canvas.drawString(
            72, 732,
            f"Báo cáo mật | Tác giả: {self.faker.name()} | Ngày tạo: {self.faker.date()}"
        )

        # Kẻ đường phân cách mỏng
        pdf_canvas.setLineWidth(0.5)
        pdf_canvas.line(72, 722, 540, 722)

        # 3. Vẽ các khối đoạn văn bản tự nhiên
        text_object = pdf_canvas.beginText(72, 700)
        text_object.setFont("Helvetica", 10)
        text_object.setLeading(14)  # Khoảng cách giữa các dòng

        paragraphs = self.faker.paragraphs(nb=4)
        for paragraph in paragraphs:
            # Ngắt dòng tự động để văn bản không bị tràn lề trang PDF
            words = paragraph.split()
            current_line = []

            for word in words:
                current_line.append(word)
                if len(" ".join(current_line)) > 75:
                    text_object.textLine(" ".join(current_line))
                    current_line = []

            if current_line:
                text_object.textLine(" ".join(current_line))

            text_object.textLine("")  # Thêm dòng trống giữa các đoạn

        pdf_canvas.drawText(text_object)
        pdf_canvas.showPage()
        pdf_canvas.save()
