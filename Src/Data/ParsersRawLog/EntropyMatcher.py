
from dataclasses import dataclass
from typing import Optional

try:
    from ...Core.Schemas import IRPOperation
    from .EntropyLoader import EntropyLoader
except (ImportError, ValueError):
    from Src.Core.Schemas import IRPOperation
    from Src.Data.ParsersRawLog.EntropyLoader import EntropyLoader


@dataclass(slots=True)
class EntropyMatchResult:
    """
    Kết quả ghép cặp chi tiết giữa sự kiện IRP và Shannon Entropy
    """
    current_entropy: float              # Shannon Entropy thời điểm IRP (0.0 - 8.0)
    baseline_entropy: float             # Shannon Entropy gốc ban đầu từ baseline snapshot
    entropy_diff: float                 # Biến thiên Delta H = H_current - H_baseline
    matched: bool                       # True nếu bắt được event realtime trong ngưỡng tolerance
    match_delta_sec: Optional[float]    # Chênh lệch thời gian giữa IRP và Watchdog (giây)
    entropy_source: str                 # Nguồn gốc: "realtime", "baseline_fallback", "deletion"

class EntropyMatcher:
    """
    Thực hiện ghép cặp thời gian thực giữa thao tác IRP của tiến trình
    với giá trị Shannon Entropy tương ứng từ EntropyLoader.
    """

    def __init__(self, loader: EntropyLoader, tolerance_sec: float = 0.3) -> None:
        self.loader = loader
        self.tolerance_sec = tolerance_sec

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
        baseline_h = self.loader.baseline_map.get(norm_path)
        if baseline_h is None and old_norm_path:
            baseline_h = self.loader.baseline_map.get(old_norm_path, 0.0)
        if baseline_h is None:
            baseline_h = 0.0

        # 1. Thao tác XÓA file -> Entropy sau khi xóa bằng 0.0
        if op == IRPOperation.DELETE:
            delta_h = round(0.0 - baseline_h, 4)
            return EntropyMatchResult(
                current_entropy=0.0,
                baseline_entropy=baseline_h,
                entropy_diff=delta_h,
                matched=True,
                match_delta_sec=0.0,
                entropy_source="deletion"
            )

        # 2. Tìm sự kiện đo Watchdog gần nhất trong realtime map (tìm theo path mới hoặc path cũ)
        events = self.loader.realtime_map.get(norm_path)
        if not events and old_norm_path:
            events = self.loader.realtime_map.get(old_norm_path)

        if events:
            best_event = min(events, key=lambda e: abs(e[0] - irp_ts))
            diff_sec = round(abs(best_event[0] - irp_ts), 6)
            if diff_sec <= self.tolerance_sec:
                current_h = best_event[1]
                delta_h = round(current_h - baseline_h, 4)
                return EntropyMatchResult(
                    current_entropy=current_h,
                    baseline_entropy=baseline_h,
                    entropy_diff=delta_h,
                    matched=True,
                    match_delta_sec=diff_sec,
                    entropy_source="realtime"
                )

        # 3. Fallback an toàn: Thao tác READ hoặc chưa kịp đo -> giữ nguyên baseline
        return EntropyMatchResult(
            current_entropy=baseline_h,
            baseline_entropy=baseline_h,
            entropy_diff=0.0,
            matched=False,
            match_delta_sec=None,
            entropy_source="baseline_fallback"
        )

