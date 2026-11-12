import random
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from faker import Faker

from .BaseWorkload import BaseWorkload

# Thiết lập encoding UTF-8 cho console Windows tránh UnicodeEncodeError
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# Kịch bản giả lập thao tác lập trình, cập nhật cấu hình và ghi cơ sở dữ liệu theo cụm thư mục
class DevelopmentWorkload(BaseWorkload):

    BURST_SIZE = 20

    # Khởi tạo workload lập trình với dải số lượng tệp mục tiêu
    def __init__(
        self,
        target_dirs: Optional[List[Path]] = None,
        min_files: int = 60,
        max_files: int = 150,
        locale: str = "vi_VN"
    ) -> None:
        super().__init__(target_dirs=target_dirs, name="DevelopmentWorkload")
        self.min_files = max(5, min_files)
        self.max_files = max(self.min_files, max_files)
        try:
            self.faker = Faker(locale)
        except Exception:
            self.faker = Faker("en_US")

    # Bổ sung hàm tiện ích mới vào tệp mã nguồn Python (.py)
    def _modify_python(self, file_path: Path) -> bool:
        try:
            func_name = f"helper_{self.faker.word()}_{random.randint(100, 999)}"
            new_code = (
                f"\n\ndef {func_name}(payload: dict) -> bool:\n"
                f"    # {self.faker.sentence()} (cập nhật ngày {time.strftime('%Y-%m-%d')})\n"
                f"    validated_data = {{k: str(v) for k, v in payload.items()}}\n"
                f"    return len(validated_data) > 0\n"
            )
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(new_code)
            return True
        except Exception:
            return False

    # Chèn thêm hàm tính toán mới vào tệp mã nguồn C++ (.cpp)
    def _modify_cpp(self, file_path: Path) -> bool:
        try:
            func_name = f"Process{self.faker.word().capitalize()}{random.randint(10, 99)}"
            new_code = (
                f"\n\n// Bổ sung module xử lý dữ liệu lúc {time.strftime('%H:%M:%S')}\n"
                f"int {func_name}(const std::vector<int>& inputData) {{\n"
                f"    int total = 0;\n"
                f"    for (int val : inputData) {{\n"
                f"        total += val;\n"
                f"    }}\n"
                f"    return total;\n"
                f"}}\n"
            )
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(new_code)
            return True
        except Exception:
            return False

    # Bổ sung khối phần tử mới vào cuối tệp HTML hoặc XML
    def _modify_markup(self, file_path: Path) -> bool:
        try:
            ext = file_path.suffix.lower()
            if ext == ".html":
                snippet = (
                    f"\n<!-- Cập nhật giao diện lúc {time.strftime('%Y-%m-%d %H:%M:%S')} -->\n"
                    f"<section class=\"user-card\">\n"
                    f"    <h3>{self.faker.name()}</h3>\n"
                    f"    <p>{self.faker.sentence()}</p>\n"
                    f"</section>\n"
                )
            else:
                snippet = (
                    f"\n<!-- Audit Record {time.strftime('%Y-%m-%d')} -->\n"
                    f"<auditEntry>\n"
                    f"    <author>{self.faker.name()}</author>\n"
                    f"    <action>UPDATE_CONFIG</action>\n"
                    f"</auditEntry>\n"
                )
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(snippet)
            return True
        except Exception:
            return False

    # Thêm câu lệnh INSERT giao dịch vào tệp kịch bản SQL (.sql)
    def _modify_sql(self, file_path: Path) -> bool:
        try:
            query = (
                f"\n-- Giao dịch kế toán lúc {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"INSERT INTO transactions (customer, amount, status) VALUES "
                f"('{self.faker.name()}', {random.uniform(50.0, 5000.0):.2f}, 'COMPLETED');\n"
            )
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(query)
            return True
        except Exception:
            return False

    # Kết nối SQLite (.db, .sqlite) và chèn bản ghi kiểm toán theo block 4KB
    def _modify_sqlite(self, file_path: Path) -> bool:
        conn = None
        try:
            conn = sqlite3.connect(str(file_path), timeout=3.0)
            cursor = conn.cursor()

            cursor.execute(
                "CREATE TABLE IF NOT EXISTS audit_logs ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "event_time TEXT, user_name TEXT, action_detail TEXT)"
            )

            for _ in range(random.randint(1, 2)):
                cursor.execute(
                    "INSERT INTO audit_logs (event_time, user_name, action_detail) VALUES (?, ?, ?)",
                    (time.strftime("%Y-%m-%d %H:%M:%S"), self.faker.user_name(), self.faker.sentence())
                )

            conn.commit()
            return True
        except Exception:
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    # Chèn thêm section/trường cấu hình mới vào tệp .ini hoặc .yaml
    def _modify_config(self, file_path: Path) -> bool:
        try:
            ext = file_path.suffix.lower()
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            if ext == ".yaml":
                snippet = (
                    f"\n# Cập nhật lúc {timestamp}\n"
                    f"metrics_collector:\n"
                    f"  interval_seconds: {random.choice([15, 30, 60])}\n"
                    f"  batch_size: {random.choice([100, 250, 500])}\n"
                )
            else:
                snippet = (
                    f"\n; Section sinh tự động lúc {timestamp}\n"
                    f"[Service_{random.randint(100, 999)}]\n"
                    f"worker_threads = {random.choice([4, 8, 16])}\n"
                    f"timeout_ms = {random.choice([1000, 3000, 5000])}\n"
                )
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(snippet)
            return True
        except Exception:
            return False

    # Ghi nối tiếp các dòng nhật ký vận hành hệ thống vào cuối file .log
    def _modify_log(self, file_path: Path) -> bool:
        try:
            levels = ["INFO", "DEBUG", "WARNING"]
            entries = []
            for _ in range(random.randint(2, 5)):
                now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                level = random.choice(levels)
                entries.append(
                    f"[{now_str}] [{level}] PID={random.randint(1000, 9999)} "
                    f"User='{self.faker.user_name()}' -> {self.faker.sentence()}"
                )
            with open(file_path, "a", encoding="utf-8") as f:
                f.write("\n" + "\n".join(entries) + "\n")
            return True
        except Exception:
            return False

    # Thực thi kịch bản lập trình và quản trị hệ thống theo cụm thư mục
    def execute(self) -> Dict[str, Any]:
        handlers = {
            ".py": self._modify_python,
            ".cpp": self._modify_cpp,
            ".html": self._modify_markup,
            ".xml": self._modify_markup,
            ".sql": self._modify_sql,
            ".db": self._modify_sqlite,
            ".sqlite": self._modify_sqlite,
            ".ini": self._modify_config,
            ".yaml": self._modify_config,
            ".log": self._modify_log,
        }
        files = self.find_files(extensions=list(handlers.keys()))

        if not files:
            print("[!] Không tìm thấy file mã nguồn/database/config nào trong DecoyDocs.")
            return {"workload": self.name, "status": "skipped", "message": "Không có file mã nguồn hoặc cấu hình"}

        target_count = (
            random.randint(self.min_files, min(len(files), self.max_files))
            if len(files) >= self.min_files
            else len(files)
        )
        selected_files = self.select_files_clustered(files, target_count=target_count, locality_ratio=0.85)

        print(f"[*] [{self.name}] Bắt đầu thao tác trên {len(selected_files)} file mã nguồn & dữ liệu...")
        modified_count = 0

        for idx, file_path in enumerate(selected_files):
            handler = handlers.get(file_path.suffix.lower())
            if handler and handler(file_path):
                modified_count += 1

            self.burst_or_pause(idx, burst_size=self.BURST_SIZE, burst_delay=(0.01, 0.05), pause_range=(1.0, 2.5))

        print(f"[+] [{self.name}] Đã thao tác thành công trên {modified_count}/{len(selected_files)} tệp tin.")

        return {
            "workload": self.name,
            "status": "success",
            "files_modified": modified_count,
            "total_targeted": len(selected_files)
        }
