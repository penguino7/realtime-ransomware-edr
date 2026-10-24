"""
ShannonEntropyCalculator: Module lõi tính toán Shannon Entropy trên vùng đệm byte
và thực hiện giám định tệp tin an toàn với cơ chế Exponential Backoff chống xung đột I/O.
"""

import math
import os
import time
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class EntropyResult:
    """
    Cấu trúc dữ liệu chuẩn hóa lưu trữ kết quả giám định Entropy của một tệp tin.
    """
    entropy: float        # Giá trị Shannon Entropy đo được (0.0000 - 8.0000)
    file_size: int        # Dung lượng tệp tin tính theo bytes
    status: str           # Trạng thái: STATUS_SUCCESS, STATUS_LOCKED, STATUS_NOT_FOUND, STATUS_ERROR
    read_time_ms: float   # Thời gian thực thi quá trình đọc và tính toán (mili-giây)


class ShannonEntropyCalculator:
    """
    Lớp tính toán Shannon Entropy trên chuỗi byte và giám định tệp tin với khả năng chịu lỗi cao (Fault-Tolerant).
    """

    # Các mã trạng thái chuẩn hóa
    STATUS_SUCCESS = "STATUS_SUCCESS"      # Đọc và tính toán thành công
    STATUS_LOCKED = "STATUS_LOCKED"        # Tệp bị khóa độc quyền bởi tiến trình khác sau khi đã thử lại tối đa
    STATUS_NOT_FOUND = "STATUS_NOT_FOUND"  # Tệp không tồn tại hoặc là tệp tạm bị xóa chớp nhoáng
    STATUS_ERROR = "STATUS_ERROR"          # Lỗi không xác định khác trong quá trình đọc

    def __init__(
        self,
        max_read_bytes: int = 65536,
        max_retries: int = 5,
        initial_backoff_sec: float = 0.005,
    ) -> None:
        
        self.max_read_bytes = max_read_bytes
        self.max_retries = max_retries
        self.initial_backoff_sec = initial_backoff_sec

    @staticmethod
    def calculate_bytes_entropy(data: bytes) -> float:
        """
        Tính toán giá trị Shannon Entropy toán học trên một mảng byte trong bộ nhớ RAM.

        Công thức: H(B) = -sum(p_i * log2(p_i))
        Trả về số thực trong khoảng [0.0, 8.0], làm tròn 4 chữ số thập phân.
        """
        if not data:
            return 0.0

        length = len(data)
        frequencies = Counter(data)
        entropy = 0.0

        # Duyệt qua tần suất xuất hiện của 256 giá trị byte có trong khối dữ liệu
        for count in frequencies.values():
            probability = count / length
            if probability > 0.0:
                entropy -= probability * math.log2(probability)

        return float(round(entropy, 4))

    def read_file_safely(self, file_path: str) -> tuple[bytes, int, str]:
        """
        Đọc vùng đệm đầu của tệp tin an toàn với cơ chế Exponential Backoff,
        tự động xử lý xung đột khóa tệp (Sharing Violation) và tệp tạm biến mất chớp nhoáng.

        Trả về:
            tuple gồm (chuỗi byte đọc được, dung lượng tệp theo bytes, mã trạng thái)
        """
        for attempt in range(self.max_retries):
            try:
                # Kiểm tra sự tồn tại của tệp trên hệ thống tệp
                if not os.path.exists(file_path):
                    return b"", 0, self.STATUS_NOT_FOUND

                file_size = os.path.getsize(file_path)

                # Mở tệp ở chế độ đọc nhị phân (Binary Read)
                with open(file_path, "rb") as file_handle:
                    chunk = file_handle.read(self.max_read_bytes)
                    return chunk, file_size, self.STATUS_SUCCESS

            except FileNotFoundError:
                # Bắt ngoại lệ an toàn nếu tệp tạm thời bị xóa ngay khi vừa kích hoạt sự kiện
                return b"", 0, self.STATUS_NOT_FOUND

            except (PermissionError, IOError, OSError):
                # Xung đột khóa tệp: Áp dụng Exponential Backoff (5ms, 10ms, 20ms, 40ms, 80ms...)
                # Chờ tiến trình (ransomware hoặc phần mềm nén) nhả handle sau khi ghi xong
                backoff_delay = self.initial_backoff_sec * (2 ** attempt)
                time.sleep(backoff_delay)

        # Nếu đã thử lại hết số lần tối đa mà vẫn bị khóa
        return b"", 0, self.STATUS_LOCKED

    def inspect_file(self, file_path: str) -> EntropyResult:
        """
        Thực hiện toàn bộ chu trình giám định tệp tin:
        1. Đọc an toàn vùng đệm tối đa 64KB đầu tiên.
        2. Đo kích thước tệp.
        3. Tính toán Shannon Entropy.
        4. Đo đạc thời gian thực thi micro-giây.

        """
        start_time = time.perf_counter()

        chunk_bytes, file_size, status = self.read_file_safely(file_path)

        if status == self.STATUS_SUCCESS:
            entropy_value = self.calculate_bytes_entropy(chunk_bytes)
        else:
            entropy_value = 0.0

        # Tính toán thời gian thực thi ra đơn vị mili-giây (ms)
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        return EntropyResult(
            entropy=entropy_value,
            file_size=file_size,
            status=status,
            read_time_ms=round(duration_ms, 3),
        )
