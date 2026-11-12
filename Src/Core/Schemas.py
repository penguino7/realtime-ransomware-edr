
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Set, Optional, Dict, Any

try:
    from .Config import Config
except (ImportError, ValueError):
    from Src.Core.Config import Config


# Phân loại các thao tác I/O hệ thống tệp chuẩn hóa từ Procmon hoặc Kernel IRP.
class IRPOperation(str, Enum):
    CREATE = "CREATE"
    WRITE = "WRITE"
    READ = "READ"
    RENAME = "RENAME"
    DELETE = "DELETE"
    CLOSE = "CLOSE"
    OTHER = "OTHER"

    # Chuẩn hóa tên thao tác từ chuỗi Procmon hoặc Minifilter Driver.
    @classmethod
    def from_str(cls, op_name: str) -> "IRPOperation":
        op_upper = op_name.strip().upper()
        if "CREATE" in op_upper:
            return cls.CREATE
        elif "WRITE" in op_upper:
            return cls.WRITE
        elif "READ" in op_upper:
            return cls.READ
        elif "RENAME" in op_upper or "SETRENAME" in op_upper:
            return cls.RENAME
        elif "DELETE" in op_upper or "SETDISPOSITION" in op_upper:
            return cls.DELETE
        elif "CLOSE" in op_upper or "CLEANUP" in op_upper:
            return cls.CLOSE
        return cls.OTHER


# Đại diện cho 1 sự kiện I/O hoàn chỉnh sau khi ghép cặp
# thao tác hệ thống tệp và độ hỗn loạn Shannon Entropy.
@dataclass(slots=True)
class IRPEvent:
    timestamp: float                    # Dấu thời gian micro-giây 
    pid: int                            # Process ID thực thi thao tác
    process_name: str                   # Tên file thực thi 
    operation: IRPOperation             # Loại thao tác chuẩn hóa
    file_path: str                      # Đường dẫn tệp mục tiêu 
    old_path: Optional[str] = None      # Đường dẫn cũ nếu là thao tác đổi tên 
    size_bytes: int = 0                 # Số lượng byte được đọc hoặc ghi
    entropy: float = 0.0                # Shannon Entropy tức thời của file (0.0 - 8.0)
    baseline_entropy: float = 0.0       # Shannon Entropy gốc ban đầu từ Baseline Snapshot
    entropy_matched: bool = False       # True nếu ghép cặp thành công với watchdog realtime
    match_delta_sec: Optional[float] = None # Sai lệch thời gian giữa IRP và Watchdog (giây)
    entropy_source: str = "baseline_fallback" # Nguồn entropy: "realtime", "baseline_fallback", "deletion"

    # Độ biến thiên Entropy so với Baseline (Delta H = H_current - H_baseline).
    @property
    def entropy_diff(self) -> float:
        return round(self.entropy - self.baseline_entropy, 4)

    # Phần mở rộng định dạng file (ví dụ: .docx, .txt).
    @property
    def extension(self) -> str:
        return Path(self.file_path).suffix.lower()

    # Kiểm tra tệp tin có đạt ngưỡng Entropy mã hóa theo Config hay không.
    @property
    def is_high_entropy(self) -> bool:
        return self.entropy >= Config.HIGH_ENTROPY_THRESHOLD

    # Chuyển đổi thành từ điển phục vụ lưu trữ trung gian (Interim CSV).
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "pid": self.pid,
            "process_name": self.process_name,
            "operation": self.operation.value,
            "file_path": self.file_path,
            "old_path": self.old_path or "",
            "size_bytes": self.size_bytes,
            "entropy": self.entropy,
            "baseline_entropy": self.baseline_entropy,
            "entropy_diff": self.entropy_diff,
            "entropy_matched": self.entropy_matched,
            "match_delta_sec": self.match_delta_sec if self.match_delta_sec is not None else "",
            "entropy_source": self.entropy_source,
        }


# Đại diện cho một lát cắt dữ liệu trong cửa sổ trượt (Short, Medium hoặc Long)
# tại thời điểm tính toán đặc trưng của tiến trình.
@dataclass(slots=True)
class WindowSlice:
    window_type: str                            # Loại cửa sổ ("SHORT", "MEDIUM", "LONG")
    events: List[IRPEvent] = field(default_factory=list)
    distinct_files: Set[str] = field(default_factory=set)
    start_time: float = 0.0                     # Thời điểm bắt đầu sự kiện đầu tiên trong cửa sổ
    end_time: float = 0.0                       # Thời điểm kết thúc sự kiện cuối cùng trong cửa sổ

    # Khoảng thời gian tồn tại của cửa sổ tính bằng giây (Delta t).
    @property
    def duration_sec(self) -> float:
        duration = self.end_time - self.start_time
        return max(0.0, round(duration, 6))

    # Tổng dung lượng byte đã ghi trong cửa sổ.
    @property
    def total_write_bytes(self) -> int:
        return sum(ev.size_bytes for ev in self.events if ev.operation == IRPOperation.WRITE)

    # Tổng số lần thực hiện thao tác WRITE trong cửa sổ.
    @property
    def write_ops_count(self) -> int:
        return sum(1 for ev in self.events if ev.operation == IRPOperation.WRITE)

    # Tổng số lần thực hiện thao tác READ trong cửa sổ.
    @property
    def read_ops_count(self) -> int:
        return sum(1 for ev in self.events if ev.operation == IRPOperation.READ)

    # Tổng số lần thực hiện thao tác RENAME trong cửa sổ.
    @property
    def rename_count(self) -> int:
        return sum(1 for ev in self.events if ev.operation == IRPOperation.RENAME)

    # Tổng số lần thực hiện thao tác DELETE trong cửa sổ.
    @property
    def delete_count(self) -> int:
        return sum(1 for ev in self.events if ev.operation == IRPOperation.DELETE)


# Vector đặc trưng hoàn chỉnh của một Tick
@dataclass(slots=True)
class FeatureVector:
    # 1. Metadata định danh (4 cột)
    sample_id: str                      # Mã định danh phiên chạy (ví dụ: session_benign_01)
    pid: int                            # Định danh duy nhất của tiến trình (Process ID)
    process_name: str                   # Tên tiến trình thực thi
    tick_index: int                     # Chỉ số Tick (1, 2, 3...)

    # 2. Short Window Features (13 đặc trưng)
    short_duration_sec: float
    short_write_ops_per_sec: float
    short_read_ops_per_sec: float
    short_write_bytes_per_sec: float
    short_write_ops_per_file: float     # [MỚI] Tần suất ghi trên mỗi file trong cửa sổ ngắn (Clock-Free)
    short_write_bytes_per_file: float   # [MỚI] Dung lượng byte ghi trên mỗi file trong cửa sổ ngắn (Clock-Free)
    short_read_to_write_ratio: float    # [MỚI] Tỷ lệ Đọc/Ghi trong cửa sổ ngắn (Clock-Free)
    short_mean_entropy: float
    short_max_entropy: float
    short_entropy_diff: float
    short_rename_count: int
    short_delete_count: int
    short_ext_diversity: float

    # 3. Medium Window Features (9 đặc trưng)
    med_duration_sec: float
    med_write_ops_per_sec: float
    med_read_to_write_ratio: float
    med_mean_entropy: float
    med_high_entropy_ratio: float
    med_rename_count: int
    med_delete_count: int
    med_ext_diversity: float
    med_dir_traversal_count: int

    # 4. Long Window Features (1 metadata quy mô + 8 đặc trưng)
    long_total_files: int               # Metadata lưu CSV, loại khỏi tập train để tránh bias độ dài phiên
    long_duration_sec: float
    long_mean_entropy: float
    long_entropy_diff: float
    long_high_entropy_ratio: float
    long_rename_ratio: float
    long_delete_ratio: float
    long_new_ext_files_ratio: float
    long_inplace_rewrite_ratio: float

    # 5. Target Label (1 cột)
    label: int                          # 0 = Benign, 1 = Ransomware

    # Xuất toàn bộ 36 trường dữ liệu thành Dictionary chuẩn
    # khớp chính xác 100% với header của dataset.csv.
    def to_dict(self) -> Dict[str, Any]:
        return {
            # Metadata
            "sample_id": self.sample_id,
            "pid": self.pid,
            "process_name": self.process_name,
            "tick_index": self.tick_index,
            # Short Window (13)
            "short_duration_sec": self.short_duration_sec,
            "short_write_ops_per_sec": self.short_write_ops_per_sec,
            "short_read_ops_per_sec": self.short_read_ops_per_sec,
            "short_write_bytes_per_sec": self.short_write_bytes_per_sec,
            "short_write_ops_per_file": self.short_write_ops_per_file,
            "short_write_bytes_per_file": self.short_write_bytes_per_file,
            "short_read_to_write_ratio": self.short_read_to_write_ratio,
            "short_mean_entropy": self.short_mean_entropy,
            "short_max_entropy": self.short_max_entropy,
            "short_entropy_diff": self.short_entropy_diff,
            "short_rename_count": self.short_rename_count,
            "short_delete_count": self.short_delete_count,
            "short_ext_diversity": self.short_ext_diversity,
            # Medium Window (9)
            "med_duration_sec": self.med_duration_sec,
            "med_write_ops_per_sec": self.med_write_ops_per_sec,
            "med_read_to_write_ratio": self.med_read_to_write_ratio,
            "med_mean_entropy": self.med_mean_entropy,
            "med_high_entropy_ratio": self.med_high_entropy_ratio,
            "med_rename_count": self.med_rename_count,
            "med_delete_count": self.med_delete_count,
            "med_ext_diversity": self.med_ext_diversity,
            "med_dir_traversal_count": self.med_dir_traversal_count,
            # Long Window (1 metadata + 8 đặc trưng)
            "long_total_files": self.long_total_files,
            "long_duration_sec": self.long_duration_sec,
            "long_mean_entropy": self.long_mean_entropy,
            "long_entropy_diff": self.long_entropy_diff,
            "long_high_entropy_ratio": self.long_high_entropy_ratio,
            "long_rename_ratio": self.long_rename_ratio,
            "long_delete_ratio": self.long_delete_ratio,
            "long_new_ext_files_ratio": self.long_new_ext_files_ratio,
            "long_inplace_rewrite_ratio": self.long_inplace_rewrite_ratio,
            # Label
            "label": self.label,
        }

    # Trích xuất danh sách đúng 30 giá trị đặc trưng số học theo thứ tự chuẩn
    # (Model A - Time-Aware / Full Model) để phục vụ suy luận mô hình AI.
    def to_feature_list(self) -> List[float]:
        return [
            # Short Window (13)
            self.short_duration_sec,
            self.short_write_ops_per_sec,
            self.short_read_ops_per_sec,
            self.short_write_bytes_per_sec,
            self.short_write_ops_per_file,
            self.short_write_bytes_per_file,
            self.short_read_to_write_ratio,
            self.short_mean_entropy,
            self.short_max_entropy,
            self.short_entropy_diff,
            float(self.short_rename_count),
            float(self.short_delete_count),
            self.short_ext_diversity,
            # Medium Window (9)
            self.med_duration_sec,
            self.med_write_ops_per_sec,
            self.med_read_to_write_ratio,
            self.med_mean_entropy,
            self.med_high_entropy_ratio,
            float(self.med_rename_count),
            float(self.med_delete_count),
            self.med_ext_diversity,
            float(self.med_dir_traversal_count),
            # Long Window (8 features - không gồm long_total_files)
            self.long_duration_sec,
            self.long_mean_entropy,
            self.long_entropy_diff,
            self.long_high_entropy_ratio,
            self.long_rename_ratio,
            self.long_delete_ratio,
            self.long_new_ext_files_ratio,
            self.long_inplace_rewrite_ratio,
        ]

    # Trích xuất danh sách 23 đặc trưng độc lập thời gian (Model B - Clock-Free / Anti-Sleep-Evasion).
    # Loại bỏ 7 đặc trưng phụ thuộc thời gian (short/med/long duration, 3 ops_per_sec, write_bytes_per_sec)
    # và không gồm long_total_files.
    def to_time_invariant_feature_list(self) -> List[float]:
        return [
            # Short Window (9 features không phụ thuộc thời gian)
            self.short_write_ops_per_file,
            self.short_write_bytes_per_file,
            self.short_read_to_write_ratio,
            self.short_mean_entropy,
            self.short_max_entropy,
            self.short_entropy_diff,
            float(self.short_rename_count),
            float(self.short_delete_count),
            self.short_ext_diversity,
            # Medium Window (7 features không phụ thuộc thời gian)
            self.med_read_to_write_ratio,
            self.med_mean_entropy,
            self.med_high_entropy_ratio,
            float(self.med_rename_count),
            float(self.med_delete_count),
            self.med_ext_diversity,
            float(self.med_dir_traversal_count),
            # Long Window (7 features không phụ thuộc thời gian)
            self.long_mean_entropy,
            self.long_entropy_diff,
            self.long_high_entropy_ratio,
            self.long_rename_ratio,
            self.long_delete_ratio,
            self.long_new_ext_files_ratio,
            self.long_inplace_rewrite_ratio,
        ]


# Cảnh báo phát hiện hành vi Ransomware thời gian thực do Detector sinh ra
# để chuyển sang Responder kích hoạt phản ứng tiêu diệt tiến trình.
@dataclass(slots=True)
class DetectionAlert:
    pid: int                            # PID của tiến trình độc hại
    process_name: str                   # Tên file thực thi độc hại
    confidence: float                   # Điểm xác suất dự đoán của mô hình AI
    tick_index: int                     # Chỉ số Tick phát hiện
    blast_radius: int                   # Số lượng file riêng biệt đã bị tác động
    timestamp: float                    # Thời điểm đưa ra quyết định cảnh báo
    features: Optional[FeatureVector] = None  # Vector đặc trưng làm bằng chứng số (evidence)
