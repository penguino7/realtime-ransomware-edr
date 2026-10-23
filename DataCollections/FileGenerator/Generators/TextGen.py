"""
Bộ sinh các tệp tin văn bản text (.txt) và dữ liệu có cấu trúc (.json, .csv).
"""

import json
import csv
import random
from pathlib import Path
from typing import List, Dict, Any
from faker import Faker
from .Base import BaseFileGenerator


class TextDocumentGenerator(BaseFileGenerator):
    """
    Tạo các file văn bản text với nội dung ngẫu nhiên
    """

    def generate(self, file_path: Path) -> None:
        """
        Sinh file văn bản UTF-8 chứa từ 5 đến 15 đoạn văn ngẫu nhiên.
        Đảm bảo dung lượng từ vài KB đến vài chục KB với phân bố byte đồng đều.
        """
        num_paragraphs = random.randint(5, 15)
        content = "\n\n".join(self.faker.paragraphs(nb=num_paragraphs))
        file_path.write_text(content, encoding="utf-8")


class StructuredDataGenerator(BaseFileGenerator):
    """
    Tạo các file văn bản có cấu trúc như json , csv 
    """

    def __init__(self, faker: Faker, file_type: str = "json") -> None:
        
        super().__init__(faker)
        self.file_type = file_type.lower()
        if self.file_type not in ("json", "csv"):
            raise ValueError(f"Loại file không hợp lệ: {self.file_type}. Chỉ hỗ trợ 'json' hoặc 'csv'.")

    def _generate_records(self, count: int = 25) -> List[Dict[str, Any]]:
        """
        Sinh danh sách bản ghi mẫu với các trường dữ liệu thực tế.        """
        records = []
        for i in range(1, count + 1):
            records.append({
                "record_id": i,
                "full_name": self.faker.name(),
                "email": self.faker.email(),
                "phone_number": self.faker.phone_number(),
                "residential_address": self.faker.address().replace("\n", ", "),
                "account_balance": round(random.uniform(250.0, 15000.0), 2),
                "created_at": self.faker.date_time_this_decade().strftime("%Y-%m-%d %H:%M:%S")
            })
        return records

    def generate(self, file_path: Path) -> None:
        """
        Ghi dữ liệu có cấu trúc ra file JSON hoặc CSV tương ứng.
        """
        records = self._generate_records(count=random.randint(20, 50))

        if self.file_type == "json":
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=4, ensure_ascii=False)
        elif self.file_type == "csv":
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
                writer.writeheader()
                writer.writerows(records)

