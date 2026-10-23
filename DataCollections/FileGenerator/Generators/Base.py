"""

Lớp cơ sở trừu tượng định nghĩa giao diện chuẩn cho tất cả các bộ sinh tệp tin.

"""

from abc import ABC, abstractmethod
from pathlib import Path
from faker import Faker


class BaseFileGenerator(ABC):
   

    def __init__(self, faker: Faker) -> None:
        """
        Lớp Faker để sinh dữ liệu giả lập tự nhiên.
        """
        self.faker = faker

    @abstractmethod
    def generate(self, file_path: Path) -> None:
        """
        Thực thi logic tạo nội dung hợp lệ (có Magic Bytes chuẩn và Entropy tự nhiên)
        rồi ghi tệp tin ra đĩa cứng.
        """
        pass
