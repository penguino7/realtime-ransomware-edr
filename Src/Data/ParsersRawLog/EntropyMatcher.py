
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple, List

try:
    from ...Core.Config import Config
    from ...Core.Schemas import IRPOperation
    from .EntropyLoader import EntropyLoader
    from .LogFormatters import LogFormatters
except (ImportError, ValueError):
    from Src.Core.Config import Config
    from Src.Core.Schemas import IRPOperation
    from Src.Data.ParsersRawLog.EntropyLoader import EntropyLoader
    from Src.Data.ParsersRawLog.LogFormatters import LogFormatters


@dataclass(slots=True)
class EntropyMatchResult:
    """
    Kết quả ghép cặp chi tiết giữa sự kiện IRP và Shannon Entropy.
    """
    current_entropy: float              # Shannon Entropy thời điểm IRP (0.0 - 8.0)
    baseline_entropy: float             # Shannon Entropy gốc ban đầu từ baseline snapshot
    entropy_diff: float                 # Biến thiên Delta H = H_current - H_baseline
    matched: bool                       # True nếu bắt được event realtime trong ngưỡng tolerance
    match_delta_sec: Optional[float]    # Chênh lệch thời gian giữa IRP và Watchdog (giây)
    entropy_source: str                 # Nguồn gốc: "realtime", "realtime_new_file", "realtime_deletion", "deletion_fallback", "baseline_fallback"


class EntropyMatcher:
    """
    Thực hiện ghép cặp thời gian thực giữa thao tác IRP của tiến trình
    với giá trị Shannon Entropy tương ứng từ EntropyLoader.
    """

    def __init__(self, loader: EntropyLoader, tolerance_sec: Optional[float] = None) -> None:
        """
        Khởi tạo EntropyMatcher.

        :param loader: Đối tượng EntropyLoader đã nạp dữ liệu baseline và realtime.
        :param tolerance_sec: Ngưỡng dung sai thời gian tối đa (giây).
                              Nếu None, tự động lấy từ Config.TIMESTAMP_TOLERANCE_MS / 1000.0 (mặc định 0.2s).
        """
        self.loader = loader
        if tolerance_sec is not None:
            self.tolerance_sec = tolerance_sec
        else:
            self.tolerance_sec = getattr(Config, "TIMESTAMP_TOLERANCE_MS", 200.0) / 1000.0

    def _get_baseline(self, norm_path: str, old_norm_path: Optional[str]) -> Tuple[float, bool]:
        """
        Tra cứu giá trị Entropy nền tảng từ snapshot ban đầu.
        Hỗ trợ:
        1. Đường dẫn trực tiếp norm_path
        2. Đường dẫn cũ old_norm_path (từ sự kiện RENAME)
        3. Bảng bí danh alias_map (nếu file đã đổi tên)
        4. Tên gốc Path(norm_path).stem (cho trường hợp ransomware gắn thêm đuôi như .lockbit, .locked)
        """
        # 1. Tra cứu trực tiếp
        baseline_h = self.loader.baseline_map.get(norm_path)
        if baseline_h is not None and baseline_h > 0.0:
            return baseline_h, True

        # 2. Tra cứu qua old_norm_path
        if old_norm_path:
            baseline_h = self.loader.baseline_map.get(old_norm_path)
            if baseline_h is not None and baseline_h > 0.0:
                return baseline_h, True

        # 3. Tra cứu qua bảng bí danh alias_map
        alias = self.loader.alias_map.get(norm_path)
        if alias:
            baseline_h = self.loader.baseline_map.get(alias)
            if baseline_h is not None and baseline_h > 0.0:
                return baseline_h, True

        # 4. Tra cứu qua tên gốc khi file bị nối thêm phần mở rộng mã hóa (ví dụ: a.docx.lockbit -> a.docx)
        p = Path(norm_path)
        if "." in p.stem:
            stem_candidate = LogFormatters.normalize_windows_path(str(p.parent / p.stem))
            baseline_h = self.loader.baseline_map.get(stem_candidate)
            if baseline_h is not None and baseline_h > 0.0:
                return baseline_h, True

        # 5. Tra cứu qua tìm-trùng-stem trong cùng thư mục cho kiểu thay đuôi (ví dụ: baocao.docx -> baocao.locked)
        target_stem = p.stem.lower()
        parent_str = LogFormatters.normalize_windows_path(str(p.parent))
        for base_path, base_h in self.loader.baseline_map.items():
            bp = Path(base_path)
            if LogFormatters.normalize_windows_path(str(bp.parent)) == parent_str and bp.stem.lower() == target_stem:
                if base_h > 0.0:
                    return base_h, True

        return 0.0, False

    def _get_realtime_events(self, norm_path: str, old_norm_path: Optional[str]) -> Optional[List]:
        """
        Truy xuất danh sách sự kiện realtime theo đường dẫn hiện tại, đường dẫn cũ
        hoặc thông qua bảng bí danh đổi tên alias_map.
        """
        # 1. Tra cứu trực tiếp theo norm_path
        events = self.loader.realtime_map.get(norm_path)
        if events:
            return events

        # 2. Tra cứu theo old_norm_path
        if old_norm_path:
            events = self.loader.realtime_map.get(old_norm_path)
            if events:
                return events

        # 3. Tra cứu qua bí danh alias_map (liên kết giữa A.docx <-> A.docx.lockbit)
        alias = self.loader.alias_map.get(norm_path)
        if alias:
            events = self.loader.realtime_map.get(alias)
            if events:
                return events

        if old_norm_path:
            alias_old = self.loader.alias_map.get(old_norm_path)
            if alias_old:
                events = self.loader.realtime_map.get(alias_old)
                if events:
                    return events

        return None

    def _match_delete(
        self,
        norm_path: str,
        irp_ts: float,
        baseline_val: float,
        has_baseline: bool,
        old_norm_path: Optional[str] = None
    ) -> EntropyMatchResult:
        """Xử lý ghép cặp cho thao tác XÓA tệp (IRPOperation.DELETE), entropy sau xóa là 0.0."""
        delta_h = round(0.0 - baseline_val, 4) if has_baseline else 0.0
        events = self._get_realtime_events(norm_path, old_norm_path)

        if events:
            del_events = [e for e in events if len(e) >= 4 and e[3] == "DELETED"]
            if del_events:
                best_del = min(del_events, key=lambda e: abs(e[0] - irp_ts))
                diff_sec = round(abs(best_del[0] - irp_ts), 6)
                if diff_sec <= self.tolerance_sec:
                    return EntropyMatchResult(
                        current_entropy=0.0,
                        baseline_entropy=baseline_val,
                        entropy_diff=delta_h,
                        matched=True,
                        match_delta_sec=diff_sec,
                        entropy_source="realtime_deletion"
                    )

        # Fallback an toàn nếu file tạm bị xóa chớp nhoáng Watchdog chưa kịp ghi
        return EntropyMatchResult(
            current_entropy=0.0,
            baseline_entropy=baseline_val,
            entropy_diff=delta_h,
            matched=False,
            match_delta_sec=0.0,
            entropy_source="deletion_fallback"
        )

    def _match_content(
        self,
        norm_path: str,
        irp_ts: float,
        baseline_val: float,
        has_baseline: bool,
        old_norm_path: Optional[str] = None
    ) -> Optional[EntropyMatchResult]:
        """Xử lý ghép cặp cho thao tác sửa đổi nội dung (WRITE, CREATE, RENAME)."""
        events = self._get_realtime_events(norm_path, old_norm_path)
        if not events:
            return None

        # Ưu tiên các sự kiện đo đạc nội dung thực (MODIFIED, CREATED, RENAMED), bỏ qua DELETED
        content_events = [e for e in events if len(e) < 4 or e[3] != "DELETED"]
        target_events = content_events if content_events else events

        best_event = min(target_events, key=lambda e: abs(e[0] - irp_ts))
        diff_sec = round(abs(best_event[0] - irp_ts), 6)
        if diff_sec <= self.tolerance_sec:
            current_h = best_event[1]
            delta_h = round(current_h - baseline_val, 4) if has_baseline else 0.0
            source_tag = "realtime" if has_baseline else "realtime_new_file"
            return EntropyMatchResult(
                current_entropy=current_h,
                baseline_entropy=baseline_val,
                entropy_diff=delta_h,
                matched=True,
                match_delta_sec=diff_sec,
                entropy_source=source_tag
            )

        return None

    def match(
        self,
        norm_path: str,
        irp_ts: float,
        op: IRPOperation,
        old_norm_path: Optional[str] = None
    ) -> EntropyMatchResult:
        """
        Tìm giá trị Shannon Entropy tương ứng với thời điểm và thao tác IRP.
        """
        baseline_val, has_baseline = self._get_baseline(norm_path, old_norm_path)

        # 1. Thao tác XÓA file (IRPOperation.DELETE)
        if op == IRPOperation.DELETE:
            return self._match_delete(norm_path, irp_ts, baseline_val, has_baseline, old_norm_path)

        # 2. Thao tác GHI, TẠO MỚI, ĐỔI TÊN (WRITE, CREATE, RENAME)
        content_result = self._match_content(norm_path, irp_ts, baseline_val, has_baseline, old_norm_path)
        if content_result is not None:
            return content_result

        # 3. Fallback an toàn: Thao tác READ hoặc chưa kịp đo -> giữ nguyên baseline
        return EntropyMatchResult(
            current_entropy=baseline_val,
            baseline_entropy=baseline_val,
            entropy_diff=0.0,
            matched=False,
            match_delta_sec=None,
            entropy_source="baseline_fallback"
        )
