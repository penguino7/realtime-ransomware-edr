
from pathlib import Path
from typing import Dict, Any, List, Set, Optional

try:
    from ..Core.Config import Config
    from ..Core.Schemas import WindowSlice, FeatureVector, IRPOperation, IRPEvent
except (ImportError, ValueError):
    from Src.Core.Config import Config
    from Src.Core.Schemas import WindowSlice, FeatureVector, IRPOperation, IRPEvent


# Bộ trích xuất đặc trưng toán học của hệ thống Realtime Ransomware EDR.
class FeatureExtractor:
    MAX_READ_TO_WRITE_RATIO: float = 100.0

    # Khởi tạo FeatureExtractor với các tham số cấu hình lấy từ Config.
    def __init__(
        self,
        epsilon: Optional[float] = None,
        min_duration_floor: Optional[float] = None,
        high_entropy_threshold: Optional[float] = None,
        monitored_extensions: Optional[Set[str]] = None,
        max_read_to_write_ratio: Optional[float] = None,
    ) -> None:
        self.epsilon: float = epsilon or Config.EPSILON
        self.min_duration_floor: float = min_duration_floor or Config.MIN_DURATION_FLOOR_SEC
        self.high_entropy_threshold: float = high_entropy_threshold or Config.HIGH_ENTROPY_THRESHOLD
        self.monitored_extensions: Set[str] = monitored_extensions or Config.MONITORED_EXTENSIONS
        self.max_read_to_write_ratio: float = (
            max_read_to_write_ratio
            if max_read_to_write_ratio is not None
            else getattr(Config, "MAX_READ_TO_WRITE_RATIO", self.MAX_READ_TO_WRITE_RATIO)
        )

    # Phương thức điều phối chính: Tính toán toàn bộ 33 đặc trưng và đóng gói vào FeatureVector.
    def extract_features(
        self,
        short_slice: WindowSlice,
        med_slice: WindowSlice,
        long_slice: WindowSlice,
        sample_id: str,
        pid: int,
        process_name: str,
        tick_index: int,
        label: int = 0
    ) -> FeatureVector:
        short_feats = self._compute_short_features(short_slice)
        med_feats = self._compute_medium_features(med_slice)
        long_feats = self._compute_long_features(long_slice)

        return FeatureVector(
            # 1. Metadata định danh (4 cột)
            sample_id=sample_id,
            pid=pid,
            process_name=process_name,
            tick_index=tick_index,
            # 2. Short Window Features (16 đặc trưng)
            short_duration_sec=short_feats["short_duration_sec"],
            short_write_ops_per_sec=short_feats["short_write_ops_per_sec"],
            short_read_ops_per_sec=short_feats["short_read_ops_per_sec"],
            short_write_bytes_per_sec=short_feats["short_write_bytes_per_sec"],
            short_write_ops_per_file=short_feats["short_write_ops_per_file"],
            short_write_bytes_per_file=short_feats["short_write_bytes_per_file"],
            short_read_to_write_ratio=short_feats["short_read_to_write_ratio"],
            short_mean_entropy=short_feats["short_mean_entropy"],
            short_max_entropy=short_feats["short_max_entropy"],
            short_entropy_diff=short_feats["short_entropy_diff"],
            short_high_entropy_ratio=short_feats["short_high_entropy_ratio"],
            short_rename_count=short_feats["short_rename_count"],
            short_delete_count=short_feats["short_delete_count"],
            short_ext_diversity=short_feats["short_ext_diversity"],
            short_new_ext_files_ratio=short_feats["short_new_ext_files_ratio"],
            short_inplace_rewrite_ratio=short_feats["short_inplace_rewrite_ratio"],
            # 3. Medium Window Features (9 đặc trưng)
            med_duration_sec=med_feats["med_duration_sec"],
            med_write_ops_per_sec=med_feats["med_write_ops_per_sec"],
            med_read_to_write_ratio=med_feats["med_read_to_write_ratio"],
            med_mean_entropy=med_feats["med_mean_entropy"],
            med_high_entropy_ratio=med_feats["med_high_entropy_ratio"],
            med_rename_count=med_feats["med_rename_count"],
            med_delete_count=med_feats["med_delete_count"],
            med_ext_diversity=med_feats["med_ext_diversity"],
            med_dir_traversal_count=med_feats["med_dir_traversal_count"],
            # 4. Long Window Features (1 metadata + 8 đặc trưng)
            long_total_files=long_feats["long_total_files"],
            long_duration_sec=long_feats["long_duration_sec"],
            long_mean_entropy=long_feats["long_mean_entropy"],
            long_entropy_diff=long_feats["long_entropy_diff"],
            long_high_entropy_ratio=long_feats["long_high_entropy_ratio"],
            long_rename_ratio=long_feats["long_rename_ratio"],
            long_delete_ratio=long_feats["long_delete_ratio"],
            long_new_ext_files_ratio=long_feats["long_new_ext_files_ratio"],
            long_inplace_rewrite_ratio=long_feats["long_inplace_rewrite_ratio"],
            # 5. Target Label (1 cột)
            label=label,
        )

    # Tính tỷ lệ Đọc/Ghi có chặn trần max_read_to_write_ratio chống bùng nổ khi write_ops = 0.
    def _compute_read_to_write_ratio(self, read_ops: int, write_ops: int) -> float:
        if write_ops == 0:
            return self.max_read_to_write_ratio if read_ops > 0 else 0.0
        return round(min(read_ops / write_ops, self.max_read_to_write_ratio), 4)

    # Tính các chỉ số Write-Entropy dùng chung cho cả 3 tầng cửa sổ.
    def _compute_write_entropy_metrics(
        self, window_slice: WindowSlice
    ) -> tuple[float, float, float, float]:
        file_entropies, file_diffs = self._get_per_file_entropy_stats(window_slice)
        total_written_files = len(file_entropies)
        if total_written_files == 0:
            return 0.0, 0.0, 0.0, 0.0
        mean_entropy = round(sum(file_entropies) / total_written_files, 4)
        max_entropy = round(max(file_entropies), 4)
        entropy_diff = round(sum(file_diffs) / len(file_diffs), 4) if file_diffs else 0.0
        high_entropy_count = sum(1 for h in file_entropies if h >= self.high_entropy_threshold)
        high_entropy_ratio = round(high_entropy_count / total_written_files, 4)
        return mean_entropy, max_entropy, entropy_diff, high_entropy_ratio

    # Tính tỷ lệ file mang đuôi lạ và tỷ lệ ghi đè in-place trên tổng số file của lát cắt.
    def _compute_new_ext_and_inplace_ratios(
        self, window_slice: WindowSlice, total_files: int
    ) -> tuple[float, float]:
        if total_files <= 0:
            return 0.0, 0.0
        new_ext_files = sum(
            1 for f in window_slice.distinct_files
            if Path(f).suffix and Path(f).suffix.lower() not in self.monitored_extensions
        )
        new_ext_files_ratio = round(new_ext_files / (total_files + self.epsilon), 4)
        written_files = {
            ev.file_path.strip().lower() for ev in window_slice.events
            if ev.operation == IRPOperation.WRITE and ev.file_path
        }
        inplace_rewrite_ratio = round(len(written_files) / (total_files + self.epsilon), 4)
        return new_ext_files_ratio, inplace_rewrite_ratio

    # Tính toán 16 đặc trưng của Cửa Sổ Ngắn (10 file riêng biệt gần nhất).
    def _compute_short_features(self, short_slice: WindowSlice) -> Dict[str, Any]:
        duration = short_slice.duration_sec
        write_ops = short_slice.write_ops_count
        read_ops = short_slice.read_ops_count
        write_bytes = short_slice.total_write_bytes
        total_files = len(short_slice.distinct_files)

        # Tốc độ I/O theo thời gian (áp dụng ngưỡng sàn thời gian tối thiểu chống bùng nổ số học ảo)
        eff_duration = max(duration, self.min_duration_floor)
        write_ops_per_sec = round(write_ops / eff_duration, 4)
        read_ops_per_sec = round(read_ops / eff_duration, 4)
        write_bytes_per_sec = round(write_bytes / eff_duration, 4)

        # Các đặc trưng độc lập thời gian (Clock-Free / Per-File & Tỷ lệ hành vi)
        eff_files = max(total_files, 1)
        short_write_ops_per_file = round(write_ops / eff_files, 4)
        short_write_bytes_per_file = round(write_bytes / eff_files, 4)
        short_read_to_write_ratio = self._compute_read_to_write_ratio(read_ops, write_ops)

        mean_entropy, max_entropy, entropy_diff, high_entropy_ratio = (
            self._compute_write_entropy_metrics(short_slice)
        )
        new_ext_files_ratio, inplace_rewrite_ratio = (
            self._compute_new_ext_and_inplace_ratios(short_slice, total_files)
        )

        # Thao tác cấu trúc
        rename_count = short_slice.rename_count
        delete_count = short_slice.delete_count

        # Độ đa dạng định dạng file (unique extensions / total files)
        unique_exts = {
            Path(f).suffix.lower() for f in short_slice.distinct_files
            if Path(f).suffix
        }
        ext_diversity = round(len(unique_exts) / (total_files + self.epsilon), 4) if total_files else 0.0

        return {
            "short_duration_sec": duration,
            "short_write_ops_per_sec": write_ops_per_sec,
            "short_read_ops_per_sec": read_ops_per_sec,
            "short_write_bytes_per_sec": write_bytes_per_sec,
            "short_write_ops_per_file": short_write_ops_per_file,
            "short_write_bytes_per_file": short_write_bytes_per_file,
            "short_read_to_write_ratio": short_read_to_write_ratio,
            "short_mean_entropy": mean_entropy,
            "short_max_entropy": max_entropy,
            "short_entropy_diff": entropy_diff,
            "short_high_entropy_ratio": high_entropy_ratio,
            "short_rename_count": rename_count,
            "short_delete_count": delete_count,
            "short_ext_diversity": ext_diversity,
            "short_new_ext_files_ratio": new_ext_files_ratio,
            "short_inplace_rewrite_ratio": inplace_rewrite_ratio,
        }

    # Tính toán 9 đặc trưng của Cửa Sổ Vừa (tối đa 50 file riêng biệt gần nhất).
    def _compute_medium_features(self, med_slice: WindowSlice) -> Dict[str, Any]:
        duration = med_slice.duration_sec
        write_ops = med_slice.write_ops_count
        read_ops = med_slice.read_ops_count

        # Tốc độ ghi và tỷ lệ Đọc/Ghi
        eff_duration = max(duration, self.min_duration_floor)
        write_ops_per_sec = round(write_ops / eff_duration, 4)
        read_to_write_ratio = self._compute_read_to_write_ratio(read_ops, write_ops)

        # Trích xuất thống kê Write-Entropy (ShieldFS: chỉ tính trên các file có thao tác ghi/sửa đổi)
        mean_entropy, _, _, high_entropy_ratio = self._compute_write_entropy_metrics(med_slice)

        # Thao tác cấu trúc
        total_files = len(med_slice.distinct_files)
        rename_count = med_slice.rename_count
        delete_count = med_slice.delete_count

        # Độ đa dạng định dạng file
        unique_exts = {
            Path(f).suffix.lower() for f in med_slice.distinct_files
            if Path(f).suffix
        }
        ext_diversity = round(len(unique_exts) / (total_files + self.epsilon), 4) if total_files else 0.0

        # Số lượng thư mục cha khác nhau bị duyệt qua
        unique_dirs = {
            str(Path(f).parent).lower() for f in med_slice.distinct_files
            if f
        }
        dir_traversal_count = len(unique_dirs)

        return {
            "med_duration_sec": duration,
            "med_write_ops_per_sec": write_ops_per_sec,
            "med_read_to_write_ratio": read_to_write_ratio,
            "med_mean_entropy": mean_entropy,
            "med_high_entropy_ratio": high_entropy_ratio,
            "med_rename_count": rename_count,
            "med_delete_count": delete_count,
            "med_ext_diversity": ext_diversity,
            "med_dir_traversal_count": dir_traversal_count,
        }

    # Tính toán đặc trưng của Cửa Sổ Dài (Tích lũy toàn bộ vòng đời tiến trình).
    # Lưu ý: long_total_files chỉ lưu làm metadata CSV (không đưa vào train);
    # các đặc trưng hành vi được chuẩn hóa sang tỷ lệ để bất biến theo độ dài phiên.
    def _compute_long_features(self, long_slice: WindowSlice) -> Dict[str, Any]:
        total_files = len(long_slice.distinct_files)
        duration = long_slice.duration_sec

        # Thống kê Write-Entropy tích lũy toàn bộ vòng đời
        mean_entropy, _, entropy_diff, high_entropy_ratio = (
            self._compute_write_entropy_metrics(long_slice)
        )

        # Tỷ lệ đổi tên và xóa tích lũy trên tổng số file đã chạm
        rename_ratio = round(long_slice.rename_count / (total_files + self.epsilon), 4) if total_files > 0 else 0.0
        delete_ratio = round(long_slice.delete_count / (total_files + self.epsilon), 4) if total_files > 0 else 0.0

        # Tỷ lệ file mang đuôi lạ và tỷ lệ ghi đè trực tiếp lên file cũ
        new_ext_files_ratio, inplace_rewrite_ratio = (
            self._compute_new_ext_and_inplace_ratios(long_slice, total_files)
        )

        return {
            "long_total_files": total_files,
            "long_duration_sec": duration,
            "long_mean_entropy": mean_entropy,
            "long_entropy_diff": entropy_diff,
            "long_high_entropy_ratio": high_entropy_ratio,
            "long_rename_ratio": rename_ratio,
            "long_delete_ratio": delete_ratio,
            "long_new_ext_files_ratio": new_ext_files_ratio,
            "long_inplace_rewrite_ratio": inplace_rewrite_ratio,
        }

    # Trích xuất giá trị Entropy mới nhất và Delta H của từng file riêng biệt trong lát cắt.
    # Áp dụng nguyên lý Write-Entropy (ShieldFS):
    # - Chỉ xét các sự kiện thay đổi nội dung dữ liệu (WRITE, RENAME mang dữ liệu mới).
    # - Tuyệt đối loại trừ các sự kiện DELETE (H=0.0) và READ để không làm méo mó và pha loãng phân phối entropy.
    # - Đảm bảo mỗi file chỉ đóng góp đúng 1 giá trị mới nhất vào thống kê trung bình.
    @classmethod
    def _get_per_file_entropy_stats(cls, window_slice: WindowSlice) -> tuple[List[float], List[float]]:
        latest_entropy_map: Dict[str, float] = {}
        latest_diff_map: Dict[str, float] = {}

        # Các thao tác ghi nhận sự thay đổi nội dung file thực tế
        CONTENT_MODIFYING_OPS = {IRPOperation.WRITE, IRPOperation.RENAME}

        for ev in window_slice.events:
            if not ev.file_path:
                continue
            # Chỉ ghi nhận các sự kiện ghi/đổi tên nội dung
            if ev.operation not in CONTENT_MODIFYING_OPS:
                continue

            norm_path = ev.file_path.strip().lower()
            if norm_path in window_slice.distinct_files:
                # Cập nhật trạng thái entropy mới nhất của file tại thời điểm này
                latest_entropy_map[norm_path] = ev.entropy
                latest_diff_map[norm_path] = ev.entropy_diff

        entropies = list(latest_entropy_map.values())
        diffs = list(latest_diff_map.values())
        return entropies, diffs
