

import csv
import os
from pathlib import Path
from typing import List, Optional, Union

try:
    from ...Core.Schemas import IRPEvent, IRPOperation
    from .LogFormatters import LogFormatters
    from .EntropyLoader import EntropyLoader
    from .EntropyMatcher import EntropyMatcher, EntropyMatchResult
except (ImportError, ValueError):
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

    def __init__(
        self,
        procmon_path: Union[str, Path],
        realtime_entropy_path: Union[str, Path],
        baseline_entropy_path: Union[str, Path],
        decoy_keyword: str = "DecoyDocs",
        tolerance_sec: float = 0.3
    ) -> None:

        self.procmon_path = Path(procmon_path)
        self.decoy_keyword = decoy_keyword.lower()

        # Khởi tạo các thành phần chuyên biệt (Delegation Pattern)
        self.loader = EntropyLoader(
            baseline_path=baseline_entropy_path,
            realtime_path=realtime_entropy_path
        )
        self.matcher = EntropyMatcher(
            loader=self.loader,
            tolerance_sec=tolerance_sec
        )

    def parse(self, limit: Optional[int] = None) -> List[IRPEvent]:
        """
        Duyệt qua Procmon log, áp dụng 3 cổng lọc và ghép cặp tạo danh sách IRPEvent.
        """
        if not self.procmon_path.exists():
            raise FileNotFoundError(f"Không tìm thấy Procmon log: {self.procmon_path}")

        # Nạp dữ liệu entropy vào RAM nếu chưa nạp
        self.loader.load_all()

        parsed_events: List[IRPEvent] = []

        with open(self.procmon_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            header = next(reader, None)

            count = 0
            for row in reader:
                if len(row) < 7:
                    continue

                raw_ts = row[0]
                proc_name = row[1].strip()
                raw_pid = row[2].strip()
                raw_op = row[3].strip()
                raw_path = row[4].strip()
                raw_result = row[5].strip().upper()
                raw_detail = row[6].strip()

                # Cổng 1: Lọc kết quả thực thi (Chỉ lấy SUCCESS hoặc BUFFER OVERFLOW)
                if raw_result not in ("SUCCESS", "BUFFER OVERFLOW"):
                    continue

                # Cổng 2: Chuẩn hóa và lọc loại thao tác IRP
                op = IRPOperation.from_str(raw_op)
                if op not in self.TARGET_OPERATIONS:
                    continue

                try:
                    pid = int(raw_pid)
                except ValueError:
                    continue

                # Xử lý trường hợp đổi tên file (SetRenameInformationFile)
                # QUAN TRỌNG: Bóc tách destination TRƯỚC khi lọc DecoyDocs
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

                # Cổng 3: Lọc theo thư mục mồi Decoy
                # Cho phép giữ lại nếu HOẶC source_path HOẶC dest_path nằm trong thư mục mồi
                if self.decoy_keyword:
                    in_src = self.decoy_keyword in raw_path.lower()
                    in_dst = new_path is not None and self.decoy_keyword in new_path.lower()
                    if not in_src and not in_dst:
                        continue

                # Chuẩn hóa đường dẫn theo quy chuẩn Windows
                norm_path = LogFormatters.normalize_windows_path(target_path)
                old_norm_path = LogFormatters.normalize_windows_path(old_path) if old_path else None

                ts_sec = LogFormatters.parse_procmon_timestamp(raw_ts)
                size_bytes = LogFormatters.extract_length(raw_detail)

                # Ghép cặp Entropy với Audit Metadata
                match_res: EntropyMatchResult = self.matcher.match(
                    norm_path=norm_path,
                    irp_ts=ts_sec,
                    op=op,
                    old_norm_path=old_norm_path
                )

                event = IRPEvent(
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

                parsed_events.append(event)
                count += 1
                if limit and count >= limit:
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
