

import csv
import os
from pathlib import Path
from typing import List, Optional, Union

try:
    from ...Core.Schemas import IRPEvent, IRPOperation
    from .LogFormatters import LogFormatters
    from .EntropyLoader import EntropyLoader
    from .EntropyMatcher import EntropyMatcher
except (ImportError, ValueError):
    from Src.Core.Schemas import IRPEvent, IRPOperation
    from Src.Data.ParsersRawLog.LogFormatters import LogFormatters
    from Src.Data.ParsersRawLog.EntropyLoader import EntropyLoader
    from Src.Data.ParsersRawLog.EntropyMatcher import EntropyMatcher


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
        tolerance_sec: float = 2.0
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

                # Cổng 1: Lọc theo thư mục mồi Decoy
                if self.decoy_keyword and self.decoy_keyword not in raw_path.lower():
                    continue

                # Cổng 2: Lọc kết quả thực thi thành công
                if raw_result not in ("SUCCESS", "BUFFER OVERFLOW"):
                    continue

                # Cổng 3: Chuẩn hóa và lọc loại thao tác
                op = IRPOperation.from_str(raw_op)
                if op not in self.TARGET_OPERATIONS:
                    continue

                try:
                    pid = int(raw_pid)
                except ValueError:
                    continue

                ts_sec = LogFormatters.parse_procmon_timestamp(raw_ts)
                norm_path = os.path.normpath(raw_path).lower()
                size_bytes = LogFormatters.extract_length(raw_detail)

                old_path: Optional[str] = None
                target_path = raw_path

                # Xử lý trường hợp đổi tên file (SetRenameInformationFile)
                if op == IRPOperation.RENAME:
                    new_path = LogFormatters.extract_rename_path(raw_detail)
                    if new_path:
                        old_path = raw_path
                        target_path = new_path
                        norm_path = os.path.normpath(target_path).lower()

                # Ghép cặp Entropy
                current_entropy, baseline_entropy = self.matcher.match(
                    norm_path=norm_path,
                    irp_ts=ts_sec,
                    op=op
                )

                event = IRPEvent(
                    timestamp=ts_sec,
                    pid=pid,
                    process_name=proc_name,
                    operation=op,
                    file_path=target_path,
                    old_path=old_path,
                    size_bytes=size_bytes,
                    entropy=current_entropy,
                    baseline_entropy=baseline_entropy
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
            "entropy_diff"
        ]

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for event in events:
                writer.writerow(event.to_dict())

        return output_file

