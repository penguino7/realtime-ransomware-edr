

import csv
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple, Any

# Đảm bảo đường dẫn gốc của project luôn có trong sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from ..Core.Schemas import IRPEvent, IRPOperation, FeatureVector
    from ..Features.WindowManager import WindowManager
    from ..Features.FeatureExtractor import FeatureExtractor
    from .ParsersRawLog.IrpParser import IrpParser
except (ImportError, ValueError):
    from Src.Core.Schemas import IRPEvent, IRPOperation, FeatureVector
    from Src.Features.WindowManager import WindowManager
    from Src.Features.FeatureExtractor import FeatureExtractor
    from Src.Data.ParsersRawLog.IrpParser import IrpParser


class DatasetBuilder:


    # Danh sách 32 cột chuẩn xác của dataset.csv
    DATASET_HEADER = [
        # Metadata định danh (4)
        "sample_id",
        "pid",
        "process_name",
        "tick_index",
        # Short Window Features (10)
        "short_duration_sec",
        "short_write_ops_per_sec",
        "short_read_ops_per_sec",
        "short_write_bytes_per_sec",
        "short_mean_entropy",
        "short_max_entropy",
        "short_entropy_diff",
        "short_rename_count",
        "short_delete_count",
        "short_ext_diversity",
        # Medium Window Features (9)
        "med_duration_sec",
        "med_write_ops_per_sec",
        "med_read_to_write_ratio",
        "med_mean_entropy",
        "med_high_entropy_ratio",
        "med_rename_count",
        "med_delete_count",
        "med_ext_diversity",
        "med_dir_traversal_count",
        # Long Window Features (8)
        "long_total_files",
        "long_duration_sec",
        "long_mean_entropy",
        "long_rename_count",
        "long_delete_count",
        "long_new_ext_count",
        "long_dir_traversal_count",
        "long_inplace_rewrite_ratio",
        # Target Label (1)
        "label"
    ]

    def __init__(
        self,
        raw_dir: Union[str, Path] = "Data/Raw",
        interim_dir: Union[str, Path] = "Data/Interim",
        output_csv_path: Union[str, Path] = "Data/Processed/dataset.csv",
        window_manager: Optional[WindowManager] = None,
        feature_extractor: Optional[FeatureExtractor] = None
    ) -> None:
        
        self.raw_dir = Path(raw_dir)
        self.interim_dir = Path(interim_dir)
        self.output_csv_path = Path(output_csv_path)

        self.window_manager = window_manager or WindowManager()
        self.feature_extractor = feature_extractor or FeatureExtractor()

    def discover_raw_sessions(self) -> List[Dict[str, Any]]:
        """
        Quét các thư mục session chuẩn trong Data/Raw/:
        Quy ước cấu trúc: Data/Raw/<Session_Name>/
        Mỗi thư mục hợp lệ bắt buộc chứa đủ 3 tệp:
        - before_entropy.csv (Snapshot baseline)
        - realtime_entropy.csv (Entropy đo bởi Watchdog)
        - procmon.csv (Nhật ký IRP Procmon)
        """
        sessions: List[Dict[str, Any]] = []
        if not self.raw_dir.exists():
            return sessions

        for sdir in sorted(self.raw_dir.iterdir()):
            if sdir.is_dir() and not sdir.name.startswith("."):
                procmon = sdir / "procmon.csv"
                realtime = sdir / "realtime_entropy.csv"
                baseline = sdir / "before_entropy.csv"

                if procmon.exists() and realtime.exists() and baseline.exists():
                    label = 1 if "malware" in sdir.name.lower() or "ransom" in sdir.name.lower() else 0
                    sessions.append({
                        "session_name": sdir.name,
                        "procmon_path": procmon,
                        "realtime_path": realtime,
                        "baseline_path": baseline,
                        "label": label
                    })

        return sessions

    def build_interim_from_raw(self, reparse: bool = False) -> List[Path]:
        """
        Gọi IrpParser hàng loạt để làm sạch các phiên thô và lưu vào Data/Interim/.

        """
        self.interim_dir.mkdir(parents=True, exist_ok=True)
        raw_sessions = self.discover_raw_sessions()
        interim_paths: List[Path] = []

        for sess in raw_sessions:
            s_name = sess["session_name"]
            out_file = self.interim_dir / f"{s_name}_cleaned.csv"

            if out_file.exists() and not reparse:
                interim_paths.append(out_file)
                continue

            parser = IrpParser(
                procmon_path=sess["procmon_path"],
                realtime_entropy_path=sess["realtime_path"],
                baseline_entropy_path=sess["baseline_path"]
            )
            parser.export_interim_csv(out_file)
            interim_paths.append(out_file)

        return interim_paths

    def discover_interim_sessions(self) -> List[Tuple[Path, str, int]]:
        """
        Quét thư mục Data/Interim/ để tìm toàn bộ các file *_cleaned.csv có sẵn,
        tự động xác định nhãn dựa trên tên tệp tin.

        :return: Danh sách các bộ (interim_path, sample_id, label).
        """
        if not self.interim_dir.exists():
            return []

        interim_files = list(self.interim_dir.glob("*_cleaned.csv"))
        sessions: List[Tuple[Path, str, int]] = []

        for fpath in interim_files:
            sample_id = fpath.stem.replace("_cleaned", "")
            lower_name = sample_id.lower()
            label = 1 if "malware" in lower_name or "ransom" in lower_name else 0
            sessions.append((fpath, sample_id, label))

        # Sắp xếp tên session để đảm bảo tính tái lập (Reproducibility)
        sessions.sort(key=lambda s: s[1])
        return sessions

    def process_interim_session(
        self,
        interim_path: Union[str, Path],
        sample_id: str,
        label: int
    ) -> List[FeatureVector]:
        """
        Đọc một file interim CSV dạng luồng, bơm vào WindowManager và trích xuất đặc trưng.
        """
        file_path = Path(interim_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Không tìm thấy interim log: {file_path}")

        # QUAN TRỌNG: Cách ly phiên (Session Isolation)
        # Reset sạch bộ nhớ đệm của WindowManager để không rò rỉ PID giữa các phiên
        self.window_manager.reset()

        vectors: List[FeatureVector] = []

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    ts = float(row["timestamp"])
                    pid = int(row["pid"])
                    proc_name = row["process_name"]
                    op = IRPOperation.from_str(row["operation"])
                    target_path = row["file_path"]
                    old_path = row["old_path"] if row.get("old_path") else None
                    size_bytes = int(row["size_bytes"]) if row.get("size_bytes") else 0
                    entropy = float(row["entropy"]) if row.get("entropy") else 0.0
                    baseline_h = float(row["baseline_entropy"]) if row.get("baseline_entropy") else 0.0

                    # Thu nhận các trường siêu dữ liệu kiểm toán (Audit Metadata)
                    raw_matched = str(row.get("entropy_matched", "False")).lower()
                    entropy_matched = raw_matched in ("true", "1")
                    raw_delta = row.get("match_delta_sec")
                    match_delta_sec = float(raw_delta) if raw_delta and raw_delta.strip() else None
                    entropy_source = row.get("entropy_source", "baseline_fallback")
                except (ValueError, KeyError):
                    continue

                event = IRPEvent(
                    timestamp=ts,
                    pid=pid,
                    process_name=proc_name,
                    operation=op,
                    file_path=target_path,
                    old_path=old_path,
                    size_bytes=size_bytes,
                    entropy=entropy,
                    baseline_entropy=baseline_h,
                    entropy_matched=entropy_matched,
                    match_delta_sec=match_delta_sec,
                    entropy_source=entropy_source
                )

                # Bơm sự kiện vào WindowManager
                slices_tuple = self.window_manager.add_event(event)

                # Nếu đạt ngưỡng Tick (chạm mốc 10 * k files)
                if slices_tuple is not None:
                    short_slice, med_slice, long_slice, tick_index = slices_tuple

                    feature_vector = self.feature_extractor.extract_features(
                        short_slice=short_slice,
                        med_slice=med_slice,
                        long_slice=long_slice,
                        sample_id=sample_id,
                        pid=pid,
                        process_name=proc_name,
                        tick_index=tick_index,
                        label=label
                    )
                    vectors.append(feature_vector)

        return vectors

    def build(self, reparse_raw: bool = False) -> Path:
        """
        Quy trình xây dựng toàn diện tập dữ liệu:
        1. Quét hoặc làm sạch các phiên thô sang Data/Interim/.
        2. Duyệt qua từng phiên Interim, tạo vector đặc trưng tại mỗi Tick.
        3. Ghi toàn bộ dữ liệu 31 cột vào Data/Processed/dataset.csv.

        """
        # Nếu thư mục interim trống hoặc có yêu cầu reparse
        interim_sessions = self.discover_interim_sessions()
        if not interim_sessions or reparse_raw:
            self.build_interim_from_raw(reparse=reparse_raw)
            interim_sessions = self.discover_interim_sessions()

        if not interim_sessions:
            raise RuntimeError("Không tìm thấy dữ liệu nào trong Data/Interim/ để xây dựng dataset.")

        self.output_csv_path.parent.mkdir(parents=True, exist_ok=True)

        total_samples = 0
        with open(self.output_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.DATASET_HEADER)
            writer.writeheader()

            for interim_path, sample_id, label in interim_sessions:
                vectors = self.process_interim_session(
                    interim_path=interim_path,
                    sample_id=sample_id,
                    label=label
                )
                # Sắp xếp các mẫu theo PID và Tick Index để từng tiến trình hiển thị tuần tự, chuẩn mực
                vectors.sort(key=lambda v: (v.pid, v.tick_index))
                for vec in vectors:
                    writer.writerow(vec.to_dict())
                total_samples += len(vectors)

        return self.output_csv_path

    def get_dataset_summary(self) -> Dict[str, Any]:
        """
        Thống kê tổng quan về tệp dữ liệu đã xây dựng (số dòng, số cột, phân bố nhãn).
        """
        if not self.output_csv_path.exists():
            return {"exists": False, "message": "dataset.csv chưa được khởi tạo."}

        benign_count = 0
        malware_count = 0
        total_rows = 0

        with open(self.output_csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames or []
            for row in reader:
                total_rows += 1
                lbl = row.get("label", "0").strip()
                if lbl == "1":
                    malware_count += 1
                else:
                    benign_count += 1

        imbalance_ratio = round(benign_count / max(1, malware_count), 2)

        return {
            "exists": True,
            "file_path": str(self.output_csv_path),
            "total_samples": total_rows,
            "benign_samples": benign_count,
            "malware_samples": malware_count,
            "imbalance_ratio": f"{imbalance_ratio}:1" if malware_count > 0 else "N/A (chỉ có benign)",
            "columns_count": len(columns),
            "features_count": len(columns) - 4  # Trừ 3 metadata và 1 label = 27 đặc trưng
        }


if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    builder = DatasetBuilder()
    output_path = builder.build()
    print(f"Xây dựng dataset thành công tại: {output_path}")
    summary = builder.get_dataset_summary()
    print("Thống kê dataset:")
    for k, v in summary.items():
        print(f"  - {k}: {v}")
