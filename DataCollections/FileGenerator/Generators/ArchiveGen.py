"""
Bộ sinh các tệp tin nén và lưu trữ nhị phân (.zip, .tar, .gz).
"""

import random
import zipfile
import tarfile
import io
from pathlib import Path
from typing import Optional
from faker import Faker

try:
    from .Base import BaseFileGenerator
except (ImportError, ValueError):
    from Base import BaseFileGenerator


class ArchiveFileGenerator(BaseFileGenerator):
    """
    Sinh các tệp tin nén chuẩn định dạng ZIP hoặc TAR.GZ
    chứa các tài liệu giả lập bên trong mà không tạo file tạm trên đĩa.
    """

    def __init__(self, faker: Faker, archive_type: Optional[str] = None) -> None:
        super().__init__(faker)
        self.archive_type = archive_type.lower().lstrip(".") if archive_type else None

    def generate(self, file_path: Path) -> None:
        """
        Tạo tệp nén và ghi ra đường dẫn mục tiêu.
        """
        ext = self.archive_type or file_path.suffix.lstrip(".").lower()
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if ext in ("tar", "gz", "tar.gz"):
            self._generate_tar_archive(file_path)
        else:
            self._generate_zip_archive(file_path)

    def _generate_zip_archive(self, file_path: Path) -> None:
        """
        Tạo file ZIP nén (Deflate) chứa từ 2 đến 5 file tài liệu giả lập bên trong.
        Sử dụng writestr() ghi thẳng vào file nén, không tạo rác trên ổ cứng.
        """
        theme = random.choice(["contracts", "source_code", "financial_data", "system_backup"])

        with zipfile.ZipFile(file_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            if theme == "contracts":
                # Nén các hợp đồng và điều khoản
                for i in range(1, random.randint(3, 6)):
                    doc_name = f"contract_appendix_{i:02d}.txt"
                    doc_content = f"HỢP ĐỒNG KINH TẾ #{self.faker.uuid4()[:8]}\n\n" + "\n\n".join(
                        self.faker.paragraphs(nb=random.randint(4, 8))
                    )
                    zf.writestr(f"contracts/{doc_name}", doc_content.encode("utf-8"))

            elif theme == "source_code":
                # Nén mã nguồn ứng dụng
                zf.writestr("src/main.py", f"# Tác giả: {self.faker.name()}\nimport sys\nprint('App Running')\n".encode("utf-8"))
                zf.writestr("src/config.ini", f"[app]\nversion = 1.0.{random.randint(1, 9)}\nenv = prod\n".encode("utf-8"))
                zf.writestr("src/README.md", f"# {self.faker.catch_phrase()}\n\n{self.faker.text()}".encode("utf-8"))

            elif theme == "financial_data":
                # Nén bảng dữ liệu CSV và báo cáo
                csv_buffer = io.StringIO()
                csv_buffer.write("id,customer,amount,date\n")
                for j in range(1, 20):
                    csv_buffer.write(f"{j},{self.faker.name()},{round(random.uniform(100.0, 5000.0), 2)},{self.faker.date()}\n")
                zf.writestr("finance/q1_revenue.csv", csv_buffer.getvalue().encode("utf-8"))
                zf.writestr("finance/audit_notes.txt", self.faker.paragraph().encode("utf-8"))

            else:  # system_backup
                # Nén file log và file cấu hình
                zf.writestr("backup/app.log", "\n".join(f"{self.faker.iso8601()} [INFO] Process event {k}" for k in range(30)).encode("utf-8"))
                zf.writestr("backup/server.yaml", f"server:\n  host: 0.0.0.0\n  port: 8080\n".encode("utf-8"))

    def _generate_tar_archive(self, file_path: Path) -> None:
        """
        Tạo file TAR nén Gzip (.tar.gz).
        """
        with tarfile.open(file_path, mode="w:gz") as tf:
            # Tạo file 1
            content1 = f"Báo cáo lưu trữ: {self.faker.company()}\n{self.faker.text()}".encode("utf-8")
            ti1 = tarfile.TarInfo(name="archive/report.txt")
            ti1.size = len(content1)
            tf.addfile(ti1, io.BytesIO(content1))

            # Tạo file 2
            content2 = f"id,metric,value\n1,cpu,45.2\n2,ram,68.9\n".encode("utf-8")
            ti2 = tarfile.TarInfo(name="archive/metrics.csv")
            ti2.size = len(content2)
            tf.addfile(ti2, io.BytesIO(content2))

