"""
Tạo các tệp tin hình ảnh (.jpg, .png).

"""

import random
from pathlib import Path
from faker import Faker
from PIL import Image, ImageDraw
from .Base import BaseFileGenerator


class ImageFileGenerator(BaseFileGenerator):
    """
    Tạo các tệp tin hình ảnh chuẩn JPEG và PNG
    """

    def __init__(self, faker: Faker, image_format: str = "JPEG") -> None:
 
        super().__init__(faker)
        self.image_format = image_format.upper()
        if self.image_format not in ("JPEG", "PNG"):
            raise ValueError(f"Định dạng ảnh không hợp lệ: {self.image_format}. Chỉ hỗ trợ 'JPEG' hoặc 'PNG'.")

    def generate(self, file_path: Path) -> None:
        """
        Vẽ hình khối và nhãn văn bản ngẫu nhiên, xuất ra tệp ảnh chuẩn trên đĩa cứng.
        """
        # Kích thước ảnh biến thiên ngẫu nhiên
        width = random.randint(450, 800)
        height = random.randint(350, 600)

        # Màu nền ngẫu nhiên tạo độ phong phú cho mảng pixel
        bg_color = (
            random.randint(50, 230),
            random.randint(50, 230),
            random.randint(50, 230)
        )

        image = Image.new("RGB", (width, height), color=bg_color)
        draw = ImageDraw.Draw(image)

        # Vẽ đường viền trang trí
        draw.rectangle(
            [(15, 15), (width - 15, height - 15)],
            outline=(255, 255, 255),
            width=2
        )

        # Vẽ các nhãn text giả lập thông tin bức ảnh
        draw.text((30, 30), f"Decoy Asset: {self.faker.company()}", fill=(255, 255, 255))
        draw.text((30, 55), f"Asset ID: {self.faker.uuid4()[:8].upper()}", fill=(255, 255, 255))
        draw.text((30, 80), f"Capture Date: {self.faker.date()}", fill=(255, 255, 255))

        # Xuất file với định dạng chuẩn
        image.save(str(file_path), format=self.image_format)
