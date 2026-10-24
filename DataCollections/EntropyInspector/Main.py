"""
Giao diện dòng lệnh (CLI Entry Point) điều khiển module EntropyInspector:
- Cung cấp các chế độ giám định Shannon Entropy:
    1. 'realtime'        : Lắng nghe sự kiện file động (Created, Modified, Renamed), tính entropy tức thời.
    2. 'snapshot-before' : Quét toàn bộ file mồi ban đầu để tạo Baseline Entropy.
    3. 'snapshot-after'  : Quét kiểm kê toàn bộ file mồi sau thử nghiệm để tạo Final Entropy.
    4. 'compare'         : So sánh chênh lệch giữa Baseline và Final để thống kê tỷ lệ mã hóa.
- Tự động lưu trữ log chuẩn về Data/Raw/.
- Đảm bảo hiển thị Unicode tiếng Việt mượt mà trên console Windows.
"""

import sys
import time
import argparse
from pathlib import Path
from typing import List, Optional

# Đảm bảo console Windows hiển thị ký tự tiếng Việt UTF-8 chuẩn xác, tránh lỗi cp1252
if sys.platform.startswith("win"):
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Thêm đường dẫn hiện tại và project root vào sys.path để hỗ trợ chạy trực tiếp từ bất kỳ đâu
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
for p in [str(CURRENT_DIR), str(PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Nạp EntropyManager linh hoạt
try:
    from .Managers.EntropyManager import EntropyManager
except (ImportError, ValueError):
    from Managers.EntropyManager import EntropyManager


def parse_arguments() -> argparse.Namespace:
    """Định nghĩa và phân tích các tham số dòng lệnh."""
    parser = argparse.ArgumentParser(
        description="EntropyInspector - Bộ giám định Shannon Entropy thời gian thực và Snapshot trên Windows Sandbox."
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="realtime",
        choices=["realtime", "snapshot-before", "snapshot-after", "compare"],
        help="Chế độ giám định: 'realtime' (theo dõi động), 'snapshot-before' (baseline), 'snapshot-after' (final), 'compare' (so sánh delta). Mặc định: realtime."
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="Đường dẫn thư mục mục tiêu tùy chọn (mặc định: Desktop, Documents, Downloads DecoyDocs)."
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Tên file hoặc đường dẫn lưu file CSV kết quả (mặc định: baseline_entropy.csv, final_entropy.csv hoặc raw_entropy_events.csv)."
    )
    parser.add_argument(
        "--baseline-file",
        type=str,
        default=None,
        help="Đường dẫn file CSV baseline dùng cho chế độ 'compare' (mặc định: Data/Raw/baseline_entropy.csv)."
    )
    parser.add_argument(
        "--final-file",
        type=str,
        default=None,
        help="Đường dẫn file CSV final dùng cho chế độ 'compare' (mặc định: Data/Raw/final_entropy.csv)."
    )
    return parser.parse_args()


def _resolve_snapshot_path(file_arg: Optional[str], default_filename: str, raw_dir: Path) -> Path:
    """Tự động phân giải đường dẫn file Snapshot (hỗ trợ cả đường dẫn tuyệt đối, tương đối hoặc chỉ tên file)."""
    if not file_arg:
        return raw_dir / default_filename

    # 1. Kiểm tra trực tiếp đường dẫn truyền vào
    p = Path(file_arg)
    if p.exists():
        return p

    # 2. Thử tìm trong thư mục Data/Raw/
    candidate_in_raw = raw_dir / p.name
    if candidate_in_raw.exists():
        return candidate_in_raw

    # 3. Thử tự động thêm đuôi .csv nếu người dùng không gõ
    if not p.suffix:
        candidate_with_csv = raw_dir / f"{p.name}.csv"
        if candidate_with_csv.exists():
            return candidate_with_csv
        candidate_local = Path(f"{p}.csv")
        if candidate_local.exists():
            return candidate_local

    # Trả về đường dẫn gốc hoặc trong raw_dir để EntropyManager báo lỗi rõ ràng nếu không tìm thấy
    return candidate_in_raw if not p.is_absolute() else p


def main() -> None:
    """Hàm điều khiển chính của chương trình."""
    args = parse_arguments()

    custom_dirs: Optional[List[Path]] = [Path(args.dir)] if args.dir else None
    manager = EntropyManager(target_dirs=custom_dirs)

    print("\n" + "=" * 65)
    print("      ENTROPY INSPECTOR - BỘ GIÁM ĐỊNH SHANNON ENTROPY")
    print("=" * 65)
    print(f"• Chế độ hoạt động : {args.mode.upper()}")
    print(f"• Thư mục mục tiêu : {[str(d) for d in manager.target_dirs]}")
    print(f"• Thư mục Raw Data : {manager.raw_data_dir}")
    print("=" * 65 + "\n")

    if args.mode == "snapshot-before":
        filename = args.output or "baseline_entropy.csv"
        manager.take_baseline_snapshot(filename=filename)

    elif args.mode == "snapshot-after":
        filename = args.output or "final_entropy.csv"
        manager.take_final_snapshot(filename=filename)

    elif args.mode == "compare":
        baseline_path = _resolve_snapshot_path(args.baseline_file, "baseline_entropy.csv", manager.raw_data_dir)
        final_path = _resolve_snapshot_path(args.final_file, "final_entropy.csv", manager.raw_data_dir)
        manager.compare_snapshots(baseline_csv=baseline_path, final_csv=final_path)

    elif args.mode == "realtime":
        filename = args.output or "raw_entropy_events.csv"
        print("[*] Đang khởi động tiến trình giám sát thời gian thực...")
        print("[*] Nhấn Ctrl+C để dừng giám sát và xuất dữ liệu ra CSV.\n")
        
        manager.start_realtime_watch()
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n[!] Đã nhận tín hiệu dừng (Ctrl+C). Đang hoàn tất ghi dữ liệu...")
        finally:
            manager.stop_realtime_watch(filename=filename)


if __name__ == "__main__":
    main()
