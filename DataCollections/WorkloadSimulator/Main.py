

import sys
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

# Thêm đường dẫn hiện tại vào sys.path để hỗ trợ chạy trực tiếp từ bất kỳ đâu
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

# Nạp WorkloadManager linh hoạt
try:
    from .Managers.WorkloadManager import WorkloadManager
except (ImportError, ValueError):
    from Managers.WorkloadManager import WorkloadManager


def parse_arguments() -> argparse.Namespace:
    """Định nghĩa và phân tích các tham số dòng lệnh."""
    parser = argparse.ArgumentParser(
        description="WorkloadSimulator - Bộ giả lập hành vi người dùng lành tính (Benign Workloads) trên Windows Sandbox."
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="mixed",
        choices=["mixed", "all", "compression", "office", "fileops", "image"],
        help="Chế độ thực thi: 'mixed' (ngẫu nhiên hỗn hợp), 'all' (tuần tự các tác vụ), hoặc tác vụ riêng biệt ('compression', 'office', 'fileops', 'image'). Mặc định: mixed."
    )
    parser.add_argument(
        "--count",
        "--iterations",
        dest="count",
        type=int,
        default=10,
        help="Tổng số hành vi (với mixed) hoặc số chu kỳ lặp lại cho mỗi tác vụ (với specific/all). Mặc định: 10."
    )
    parser.add_argument(
        "--delay-min",
        type=float,
        default=1.0,
        help="Thời gian nghỉ ngẫu nhiên tối thiểu giữa các hành vi (tính bằng giây). Mặc định: 1.0s."
    )
    parser.add_argument(
        "--delay-max",
        type=float,
        default=3.0,
        help="Thời gian nghỉ ngẫu nhiên tối đa giữa các hành vi (tính bằng giây). Mặc định: 3.0s."
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="Đường dẫn thư mục mục tiêu tùy chọn (nếu muốn chạy trên thư mục riêng thay vì mặc định)."
    )
    parser.add_argument(
        "--tool-path",
        type=str,
        default=None,
        help="Đường dẫn tùy chỉnh tới file thực thi 7z.exe hoặc WinRAR.exe."
    )
    return parser.parse_args()


def main() -> None:
    """Hàm điều khiển chính của chương trình."""
    args = parse_arguments()

    if args.delay_min < 0 or args.delay_max < 0 or args.delay_min > args.delay_max:
        print("[!] Lỗi: Tham số khoảng trễ không hợp lệ (--delay-min phải <= --delay-max và >= 0).", file=sys.stderr)
        sys.exit(1)

    if args.count <= 0:
        print("[!] Lỗi: Số lượng --count / --iterations phải lớn hơn 0.", file=sys.stderr)
        sys.exit(1)

    custom_dirs: Optional[List[Path]] = [Path(args.dir)] if args.dir else None
    manager = WorkloadManager(target_dirs=custom_dirs, custom_tool_path=args.tool_path)

    print("\n" + "=" * 60)
    print("      WORKLOAD SIMULATOR - GIẢ LẬP HÀNH VI LÀNH TÍNH")
    print("=" * 60)
    print(f"• Chế độ hoạt động : {args.mode.upper()}")
    print(f"• Số lượng chu kỳ  : {args.count}")
    print(f"• Độ trễ tự nhiên  : {args.delay_min}s -> {args.delay_max}s")
    print(f"• Thư mục mục tiêu : {[str(d) for d in manager.target_dirs]}")
    print("=" * 60)

    try:
        if args.mode == "mixed":
            manager.run_mixed(
                total_actions=args.count,
                min_delay=args.delay_min,
                max_delay=args.delay_max
            )
        elif args.mode == "all":
            manager.run_all_sequential(
                iterations_per_task=args.count,
                min_delay=args.delay_min,
                max_delay=args.delay_max
            )
        else:
            manager.run_workload(
                task_name=args.mode,
                iterations=args.count,
                min_delay=args.delay_min,
                max_delay=args.delay_max
            )
    except KeyboardInterrupt:
        print("\n\n[!] Người dùng đã bấm Ctrl+C để dừng mô phỏng sớm.")
    finally:
        manager.print_summary()


if __name__ == "__main__":
    main()
