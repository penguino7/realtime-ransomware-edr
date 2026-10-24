
import re
from datetime import datetime
from typing import Optional


class LogFormatters:
    """
    Tập hợp các tiện ích tĩnh chuyển đổi định dạng và biểu thức chính quy (Regex)
    xử lý các trường dữ liệu chuỗi trong file log thô.
    """

    @staticmethod
    def parse_procmon_timestamp(ts_str: str) -> float:
        """
        Chuyển đổi chuỗi thời gian 12-giờ của Procmon (ví dụ: '3:20:58.7449945 PM')
        thành số giây thực tính từ đầu ngày (độ chính xác micro-giây).
        """
        ts_str = ts_str.strip().strip('"')
        parts = ts_str.split()
        if len(parts) == 2:
            time_part, period = parts[0], parts[1]
            if "." in time_part:
                hms, frac = time_part.split(".", 1)
                frac_micro = (frac + "000000")[:6]
                clean_str = f"{hms}.{frac_micro} {period}"
            else:
                clean_str = f"{time_part}.000000 {period}"

            try:
                dt = datetime.strptime(clean_str, "%I:%M:%S.%f %p")
                return dt.hour * 3600.0 + dt.minute * 60.0 + dt.second + dt.microsecond / 1e6
            except ValueError:
                pass
        return 0.0

    @staticmethod
    def parse_realtime_timestamp(ts_str: str) -> float:
        """
        Chuyển đổi chuỗi thời gian 24-giờ của Watchdog (ví dụ: '15:20:58.833709')
        thành số giây thực tính từ đầu ngày.
        """
        ts_str = ts_str.strip().strip('"')
        try:
            if "." in ts_str:
                dt = datetime.strptime(ts_str, "%H:%M:%S.%f")
            else:
                dt = datetime.strptime(ts_str, "%H:%M:%S")
            return dt.hour * 3600.0 + dt.minute * 60.0 + dt.second + dt.microsecond / 1e6
        except ValueError:
            return 0.0

    @staticmethod
    def extract_length(detail_str: str) -> int:
        """
        Trích xuất số lượng bytes (Length: X) từ cột Detail của Procmon.
        Ví dụ: 'Offset: 1,328, Length: 142, Priority: Normal' -> 142.
        """
        match = re.search(r"Length:\s*([0-9,]+)", detail_str)
        if match:
            clean_digits = match.group(1).replace(",", "")
            try:
                return int(clean_digits)
            except ValueError:
                return 0
        return 0

    @staticmethod
    def extract_rename_path(detail_str: str) -> Optional[str]:
        """
        Trích xuất đường dẫn file mới từ cột Detail khi có thao tác đổi tên (SetRenameInformationFile).
        Ví dụ: 'FileName: C:\\Users\\...\\file.docx.locked' -> 'C:\\Users\\...\\file.docx.locked'.
        """
        match = re.search(r"FileName:\s*(.+)", detail_str)
        if match:
            return match.group(1).strip()
        return None
