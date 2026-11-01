

import csv
import os
from pathlib import Path
from typing import List, Optional, Set, Union, Generator, Tuple

try:
    from ...Core.Config import Config
    from ...Core.Schemas import IRPEvent, IRPOperation
    from .LogFormatters import LogFormatters
    from .EntropyLoader import EntropyLoader
    from .EntropyMatcher import EntropyMatcher, EntropyMatchResult
except (ImportError, ValueError):
    from Src.Core.Config import Config
    from Src.Core.Schemas import IRPEvent, IRPOperation
    from Src.Data.ParsersRawLog.LogFormatters import LogFormatters
    from Src.Data.ParsersRawLog.EntropyLoader import EntropyLoader
    from Src.Data.ParsersRawLog.EntropyMatcher import EntropyMatcher, EntropyMatchResult


class IrpParser:

    # 5 thao tác IRP trọng yếu cần giám sát mã hóa
    TARGET_OPERATIONS = {
        IRPOperation.CREATE,
        IRPOperation.WRITE,
        IRPOperation.READ,
        IRPOperation.RENAME,
        IRPOperation.DELETE,
    }

    # Từ khóa xác định thao tác mở file có ý đồ đọc/ghi nội dung thực sự (loại trừ CREATE flood do chỉ đọc metadata)
    MEANINGFUL_CREATE_KEYWORDS = (
        "generic read",
        "generic write",
        "read data",
        "write data",
        "append data",
        "overwrite",
        "supersede",
    )

    # Chỉ số các cột chuẩn trong tệp CSV xuất từ Process Monitor
    COL_TIME = 0
    COL_PROCESS = 1
    COL_PID = 2
    COL_OPERATION = 3
    COL_PATH = 4
    COL_RESULT = 5
    COL_DETAIL = 6

    def __init__(
        self,
        procmon_path: Union[str, Path],
        realtime_entropy_path: Union[str, Path],
        baseline_entropy_path: Union[str, Path],
        decoy_keyword: str = "DecoyDocs",
        tolerance_sec: Optional[float] = None,
        excluded_processes: Optional[Set[str]] = None
    ) -> None:
        self.procmon_path = Path(procmon_path)
        self.decoy_keyword = decoy_keyword.lower()
        self.excluded_processes: Set[str] = {
            p.lower() for p in (excluded_processes if excluded_processes is not None else Config.EXCLUDED_PROCESSES)
        }
        if tolerance_sec is None:
            self.tolerance_sec: float = Config.TIMESTAMP_TOLERANCE_MS / 1000.0
        else:
            self.tolerance_sec: float = float(tolerance_sec)

        # Khởi tạo các thành phần chuyên biệt (Delegation Pattern)
        self.loader = EntropyLoader(
            baseline_path=baseline_entropy_path,
            realtime_path=realtime_entropy_path
        )
        self.matcher = EntropyMatcher(
            loader=self.loader,
            tolerance_sec=self.tolerance_sec
        )

    def _read_procmon_rows(self) -> Generator[List[str], None, None]:
        """Đọc tuần tự từng dòng dữ liệu từ tệp Procmon CSV, bỏ qua header."""
        with open(self.procmon_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                yield row

    def _is_excluded_process(self, proc_name: str) -> bool:
        """Kiểm tra tiến trình có thuộc danh sách loại trừ (hệ thống, đo đạc) không."""
        return proc_name.lower() in self.excluded_processes

    @staticmethod
    def _is_success_result(raw_result: str) -> bool:
        """Kiểm tra kết quả thực thi IRP có thành công hoặc buffer overflow không."""
        return raw_result in ("SUCCESS", "BUFFER OVERFLOW")

    @classmethod
    def _is_meaningful_create(cls, raw_detail: str) -> bool:
        """
        Kiểm tra xem sự kiện CreateFile có thực sự truy cập hoặc thao tác dữ liệu hay không.
        Bỏ qua các sự kiện mở file chỉ để đọc thuộc tính (Read Attributes, Read Control, stat, exists).
        """
        detail_lower = raw_detail.lower()
        return any(kw in detail_lower for kw in cls.MEANINGFUL_CREATE_KEYWORDS)

    @staticmethod
    def _resolve_paths(
        op: IRPOperation, raw_path: str, raw_detail: str
    ) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Bóc tách và xác định target_path, old_path, new_path.
        Đặc biệt với SetRenameInformationFile, new_path nằm trong cột Detail.
        """
        old_path: Optional[str] = None
        new_path: Optional[str] = None
        if op == IRPOperation.RENAME:
            new_path = LogFormatters.extract_rename_path(raw_detail)
            if new_path:
                old_path = raw_path
                target_path = new_path
            else:
                target_path = raw_path
        else:
            target_path = raw_path
        return target_path, old_path, new_path

    def _is_decoy_path(self, raw_path: str, new_path: Optional[str]) -> bool:
        """Kiểm tra thao tác có tác động tới thư mục mồi DecoyDocs hay không."""
        if not self.decoy_keyword:
            return True
        in_src = self.decoy_keyword in raw_path.lower()
        in_dst = new_path is not None and self.decoy_keyword in new_path.lower()
        return in_src or in_dst

    def _parse_row(self, row: List[str]) -> Optional[IRPEvent]:
        """
        Phân tích và lọc 1 dòng Procmon log, ghép cặp Entropy và tạo IRPEvent.
        Trả về None nếu dòng không thỏa mãn các cổng kiểm tra.
        """
        if len(row) < 7:
            return None

        proc_name = row[self.COL_PROCESS].strip()
        if self._is_excluded_process(proc_name):
            return None

        raw_result = row[self.COL_RESULT].strip().upper()
        if not self._is_success_result(raw_result):
            return None

        raw_op = row[self.COL_OPERATION].strip()
        op = IRPOperation.from_str(raw_op)
        if op not in self.TARGET_OPERATIONS:
            return None

        raw_detail = row[self.COL_DETAIL].strip()

        # Cổng lọc CREATE flood: Bỏ qua các sự kiện mở file chỉ để thăm dò thuộc tính (Read Attributes, stat, exists)
        if op == IRPOperation.CREATE and not self._is_meaningful_create(raw_detail):
            return None

        try:
            pid = int(row[self.COL_PID].strip())
        except ValueError:
            return None

        raw_path = row[self.COL_PATH].strip()

        target_path, old_path, new_path = self._resolve_paths(op, raw_path, raw_detail)

        if not self._is_decoy_path(raw_path, new_path):
            return None

        norm_path = LogFormatters.normalize_windows_path(target_path)
        old_norm_path = LogFormatters.normalize_windows_path(old_path) if old_path else None

        ts_sec = LogFormatters.parse_procmon_timestamp(row[self.COL_TIME])
        size_bytes = LogFormatters.extract_length(raw_detail)

        match_res: EntropyMatchResult = self.matcher.match(
            norm_path=norm_path,
            irp_ts=ts_sec,
            op=op,
            old_norm_path=old_norm_path
        )

        return IRPEvent(
            timestamp=ts_sec,
            pid=pid,
            process_name=proc_name,
            operation=op,
            file_path=target_path,
            old_path=old_path,
            size_bytes=size_bytes,
            entropy=match_res.current_entropy,
            baseline_entropy=match_res.baseline_entropy,
            entropy_matched=match_res.matched,
            match_delta_sec=match_res.match_delta_sec,
            entropy_source=match_res.entropy_source
        )

    def parse(self, limit: Optional[int] = None) -> List[IRPEvent]:
        """
        Duyệt qua Procmon log, áp dụng các cổng lọc và ghép cặp tạo danh sách IRPEvent.
        """
        if not self.procmon_path.exists():
            raise FileNotFoundError(f"Không tìm thấy Procmon log: {self.procmon_path}")

        self.loader.load_all()
        parsed_events: List[IRPEvent] = []

        for row in self._read_procmon_rows():
            event = self._parse_row(row)
            if event is not None:
                parsed_events.append(event)
                if limit and len(parsed_events) >= limit:
                    break

        return parsed_events

    def export_interim_csv(self, output_path: Union[str, Path], limit: Optional[int] = None) -> Path:
        """
        Lưu danh sách IRPEvent vào tệp CSV trung gian tại Data/Interim/.
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        events = self.parse(limit=limit)

        fieldnames = [
            "timestamp",
            "pid",
            "process_name",
            "operation",
            "file_path",
            "old_path",
            "size_bytes",
            "entropy",
            "baseline_entropy",
            "entropy_diff",
            "entropy_matched",
            "match_delta_sec",
            "entropy_source"
        ]

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for event in events:
                writer.writerow(event.to_dict())

        return output_file
