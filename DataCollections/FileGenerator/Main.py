"""
Giao diện dòng lệnh (CLI Entry Point) điều khiển module FileGenerator:
- Cung cấp các tham số cấu hình: số lượng file, thư mục tùy chọn, lệnh dọn dẹp.
- Kích hoạt FileEnvironmentManager thực thi sinh file mồi hoặc rollback tài nguyên.
- Kết xuất báo cáo phân bổ định dạng và dung lượng chiếm dụng trên đĩa.
"""

import sys
import argparse
from pathlib import Path

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

# Nạp FileEnvironmentManager linh hoạt
try:
    from .Managers.FileManager import FileEnvironmentManager
except (ImportError, ValueError):
    from Managers.FileManager import FileEnvironmentManager


def parse_arguments() -> argparse.Namespace:
    """Định nghĩa và phân tích các tham số dòng lệnh."""
    parser = argparse.ArgumentParser(
        description="FileGenerator - Bộ sinh và dọn dẹp môi trường tệp tin mồi phục vụ kiểm thử Ransomware."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=300,
        help="Tổng số lượng file mồi cần sinh (mặc định: 300 files)."
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Thực hiện dọn dẹp, xóa sạch toàn bộ các file mồi đã tạo."
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="Đường dẫn thư mục mục tiêu tùy chọn (nếu muốn tạo tại 1 thư mục riêng)."
    )
    return parser.parse_args()


def display_summary_report(report: dict) -> None:
    """In bảng báo cáo thống kê tệp tin mồi ra màn hình."""
    print("\n" + "=" * 50)
    print("       BÁO CÁO MÔI TRƯỜNG TỆP TIN MỒI (DECOY)")
    print("=" * 50)
    print(f"• Tổng số file tạo thành công : {report['total_files']} files")
    print(f"• Tổng dung lượng chiếm dụng  : {report['total_size_mb']} MB ({report['total_size_bytes']:,} bytes)")
    print("• Thư mục mục tiêu            :")
    for directory in report["target_directories"]:
        print(f"   -> {directory}")
    print("• Phân bổ theo từng định dạng :")
    for ext, count in sorted(report["breakdown_by_extension"].items()):
        print(f"   - {ext.upper():<6} : {count:>3} files")
    print("=" * 50 + "\n")


def main() -> None:
    """Hàm điều khiển chính của chương trình."""
    args = parse_arguments()

    custom_dirs = [Path(args.dir)] if args.dir else None
    manager = FileEnvironmentManager(base_dirs=custom_dirs)

    if args.cleanup:
        manager.cleanup()
        return

    # Sinh file mồi và in báo cáo kết quả
    manager.populate(total_files=args.count)
    report = manager.get_summary_report()
    display_summary_report(report)


if __name__ == "__main__":
    main()

