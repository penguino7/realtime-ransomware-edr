
from pathlib import Path
from typing import Dict, Any, List, Set, Optional

try:
    from ..Core.Config import Config
    from ..Core.Schemas import WindowSlice, FeatureVector, IRPOperation, IRPEvent
except (ImportError, ValueError):
    from Src.Core.Config import Config
    from Src.Core.Schemas import WindowSlice, FeatureVector, IRPOperation, IRPEvent


class FeatureExtractor:
    """
    Bộ trích xuất đặc trưng toán học của hệ thống Realtime Ransomware EDR.
    """

    def __init__(
        self,
        epsilon: Optional[float] = None,
        min_duration_floor: Optional[float] = None,
        high_entropy_threshold: Optional[float] = None,
        monitored_extensions: Optional[Set[str]] = None,
    ) -> None:
        """
        Khởi tạo FeatureExtractor với các tham số cấu hình lấy từ Config.
        """
        self.epsilon: float = epsilon or Config.EPSILON
        self.min_duration_floor: float = min_duration_floor or Config.MIN_DURATION_FLOOR_SEC
        self.high_entropy_threshold: float = high_entropy_threshold or Config.HIGH_ENTROPY_THRESHOLD
        self.monitored_extensions: Set[str] = monitored_extensions or Config.MONITORED_EXTENSIONS

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
        """
        Phương thức điều phối chính: Tính toán toàn bộ 27 đặc trưng và đóng gói vào FeatureVector.
        """
        short_feats = self._compute_short_features(short_slice)
        med_feats = self._compute_medium_features(med_slice)
        long_feats = self._compute_long_features(long_slice)

        return FeatureVector(
            # 1. Metadata định danh (4 cột)
            sample_id=sample_id,
            pid=pid,
            process_name=process_name,
            tick_index=tick_index,
            # 2. Short Window Features (10 đặc trưng)
            short_duration_sec=short_feats["short_duration_sec"],
            short_write_ops_per_sec=short_feats["short_write_ops_per_sec"],
            short_read_ops_per_sec=short_feats["short_read_ops_per_sec"],
            short_write_bytes_per_sec=short_feats["short_write_bytes_per_sec"],
            short_mean_entropy=short_feats["short_mean_entropy"],
            short_max_entropy=short_feats["short_max_entropy"],
            short_entropy_diff=short_feats["short_entropy_diff"],
            short_rename_count=short_feats["short_rename_count"],
            short_delete_count=short_feats["short_delete_count"],
            short_ext_diversity=short_feats["short_ext_diversity"],
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
            # 4. Long Window Features (8 đặc trưng)
            long_total_files=long_feats["long_total_files"],
            long_duration_sec=long_feats["long_duration_sec"],
            long_mean_entropy=long_feats["long_mean_entropy"],
            long_rename_count=long_feats["long_rename_count"],
            long_delete_count=long_feats["long_delete_count"],
            long_new_ext_count=long_feats["long_new_ext_count"],
            long_dir_traversal_count=long_feats["long_dir_traversal_count"],
            long_inplace_rewrite_ratio=long_feats["long_inplace_rewrite_ratio"],
            # 5. Target Label (1 cột)
            label=label,
        )

    def _compute_short_features(self, short_slice: WindowSlice) -> Dict[str, Any]:
        """
        Tính toán 10 đặc trưng của Cửa Sổ Ngắn (10 file riêng biệt gần nhất).
        """
        duration = short_slice.duration_sec
        write_ops = short_slice.write_ops_count
        read_ops = short_slice.read_ops_count
        write_bytes = short_slice.total_write_bytes

        # Tốc độ I/O (áp dụng ngưỡng sàn thời gian tối thiểu chống bùng nổ số học ảo)
        eff_duration = max(duration, self.min_duration_floor)
        write_ops_per_sec = round(write_ops / eff_duration, 4)
        read_ops_per_sec = round(read_ops / eff_duration, 4)
        write_bytes_per_sec = round(write_bytes / eff_duration, 4)

        # Trích xuất Entropy của từng file riêng biệt trong cửa sổ ngắn
        file_entropies, file_diffs = self._get_per_file_entropy_stats(short_slice)
        mean_entropy = round(sum(file_entropies) / len(file_entropies), 4) if file_entropies else 0.0
        max_entropy = round(max(file_entropies), 4) if file_entropies else 0.0
        entropy_diff = round(sum(file_diffs) / len(file_diffs), 4) if file_diffs else 0.0

        # Thao tác cấu trúc
        rename_count = short_slice.rename_count
        delete_count = short_slice.delete_count

        # Độ đa dạng định dạng file (unique extensions / total files)
        unique_exts = {
            Path(f).suffix.lower() for f in short_slice.distinct_files
            if Path(f).suffix
        }
        total_files = len(short_slice.distinct_files)
        ext_diversity = round(len(unique_exts) / (total_files + self.epsilon), 4) if total_files else 0.0

        return {
            "short_duration_sec": duration,
            "short_write_ops_per_sec": write_ops_per_sec,
            "short_read_ops_per_sec": read_ops_per_sec,
            "short_write_bytes_per_sec": write_bytes_per_sec,
            "short_mean_entropy": mean_entropy,
            "short_max_entropy": max_entropy,
            "short_entropy_diff": entropy_diff,
            "short_rename_count": rename_count,
            "short_delete_count": delete_count,
            "short_ext_diversity": ext_diversity,
        }

    def _compute_medium_features(self, med_slice: WindowSlice) -> Dict[str, Any]:
        """
        Tính toán 9 đặc trưng của Cửa Sổ Vừa (tối đa 50 file riêng biệt gần nhất).
        """
        duration = med_slice.duration_sec
        write_ops = med_slice.write_ops_count
        read_ops = med_slice.read_ops_count

        # Tốc độ ghi và tỷ lệ Đọc/Ghi
        eff_duration = max(duration, self.min_duration_floor)
        write_ops_per_sec = round(write_ops / eff_duration, 4)
        read_to_write_ratio = round(read_ops / (write_ops + self.epsilon), 4)

        # Trích xuất thống kê Entropy
        file_entropies, _ = self._get_per_file_entropy_stats(med_slice)
        mean_entropy = round(sum(file_entropies) / len(file_entropies), 4) if file_entropies else 0.0
        high_entropy_count = sum(1 for h in file_entropies if h >= self.high_entropy_threshold)
        total_files = len(med_slice.distinct_files)
        high_entropy_ratio = round(high_entropy_count / (total_files + self.epsilon), 4) if total_files else 0.0

        # Thao tác cấu trúc
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

    def _compute_long_features(self, long_slice: WindowSlice) -> Dict[str, Any]:
        """
        Tính toán 8 đặc trưng của Cửa Sổ Dài (Tích lũy toàn bộ vòng đời tiến trình).
        """
        total_files = len(long_slice.distinct_files)
        duration = long_slice.duration_sec

        # Entropy trung bình tích lũy toàn bộ vòng đời
        file_entropies, _ = self._get_per_file_entropy_stats(long_slice)
        mean_entropy = round(sum(file_entropies) / len(file_entropies), 4) if file_entropies else 0.0

        # Tổng số lần đổi tên và xóa tích lũy
        rename_count = long_slice.rename_count
        delete_count = long_slice.delete_count

        # Đếm số lượng phần mở rộng lạ sinh ra lần đầu (không thuộc danh mục mồi chuẩn)
        new_exts = {
            Path(f).suffix.lower() for f in long_slice.distinct_files
            if Path(f).suffix and Path(f).suffix.lower() not in self.monitored_extensions
        }
        new_ext_count = len(new_exts)

        # Tổng số thư mục khác nhau đã bị xâm nhập từ đầu đến giờ
        unique_dirs = {
            str(Path(f).parent).lower() for f in long_slice.distinct_files
            if f
        }
        dir_traversal_count = len(unique_dirs)

        # Tỷ lệ ghi đè trực tiếp lên chính file cũ (In-place rewrite ratio)
        written_files = {
            ev.file_path.strip().lower() for ev in long_slice.events
            if ev.operation == IRPOperation.WRITE and ev.file_path
        }
        inplace_rewrite_ratio = round(len(written_files) / (total_files + self.epsilon), 4) if total_files else 0.0

        return {
            "long_total_files": total_files,
            "long_duration_sec": duration,
            "long_mean_entropy": mean_entropy,
            "long_rename_count": rename_count,
            "long_delete_count": delete_count,
            "long_new_ext_count": new_ext_count,
            "long_dir_traversal_count": dir_traversal_count,
            "long_inplace_rewrite_ratio": inplace_rewrite_ratio,
        }

    @staticmethod
    def _get_per_file_entropy_stats(window_slice: WindowSlice) -> tuple[List[float], List[float]]:
        """
        Trích xuất giá trị Entropy mới nhất và Delta H của từng file riêng biệt trong lát cắt.
        Đảm bảo mỗi file chỉ đóng góp đúng 1 giá trị mới nhất vào thống kê trung bình.
        """
        latest_entropy_map: Dict[str, float] = {}
        latest_diff_map: Dict[str, float] = {}

        for ev in window_slice.events:
            if not ev.file_path:
                continue
            norm_path = ev.file_path.strip().lower()
            if norm_path in window_slice.distinct_files:
                # Cập nhật trạng thái entropy mới nhất của file tại thời điểm này
                latest_entropy_map[norm_path] = ev.entropy
                latest_diff_map[norm_path] = ev.entropy_diff

        entropies = list(latest_entropy_map.values())
        diffs = list(latest_diff_map.values())
        return entropies, diffs
