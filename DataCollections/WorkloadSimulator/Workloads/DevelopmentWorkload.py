
import sys
import time
import random
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Any
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


class DevelopmentWorkload(BaseWorkload):
    """
    Kịch bản thực hiện các thao tác lập trình, cập nhật cấu hình và tương tác cơ sở dữ liệu.
    """

    def __init__(
        self,
        target_dirs: Optional[List[Path]] = None,
        locale: str = "vi_VN"
    ) -> None:
        super().__init__(target_dirs=target_dirs, name="DevelopmentWorkload")
        try:
            self.faker = Faker(locale)
        except Exception:
            self.faker = Faker("en_US")

    def _modify_python(self, file_path: Path) -> bool:
        """Mở tệp mã nguồn Python .py, bổ sung hàm tiện ích mới và lưu đè lại."""
        try:
            func_name = f"helper_{self.faker.word()}_{random.randint(100, 999)}"
            new_code = (
                f"\n\ndef {func_name}(payload: dict) -> bool:\n"
                f"    \"\"\"{self.faker.sentence()}\"\"\"\n"
                f"    # Tự động cập nhật logic nghiệp vụ ngày {time.strftime('%Y-%m-%d')}\n"
                f"    validated_data = {{k: str(v) for k, v in payload.items()}}\n"
                f"    return len(validated_data) > 0\n"
            )
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(new_code)
            return True
        except Exception:
            return False

    def _modify_cpp(self, file_path: Path) -> bool:
        """Mở tệp mã nguồn C++ .cpp, chèn thêm một hàm tính toán và lưu đè lại."""
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

    def _modify_markup(self, file_path: Path) -> bool:
        """Mở tệp HTML hoặc XML, bổ sung khối phần tử mới vào cuối văn bản."""
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

    def _modify_sql(self, file_path: Path) -> bool:
        """Mở tệp kịch bản SQL .sql, thêm câu lệnh chèn bản ghi giao dịch."""
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

    def _modify_sqlite(self, file_path: Path) -> bool:
        """
        Kết nối tới tệp SQLite (.db, .sqlite), thực thi câu lệnh INSERT giao dịch thật.
        Kích hoạt cơ chế ghi đè dữ liệu theo từng block 4KB chuẩn của database engine.
        """
        conn = None
        try:
            conn = sqlite3.connect(str(file_path), timeout=3.0)
            cursor = conn.cursor()

            # Tạo bảng nhật ký nếu chưa có để đảm bảo tương thích mọi file DB
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_time TEXT,
                    user_name TEXT,
                    action_detail TEXT
                )
                """
            )

            # Chèn 1-2 dòng nhật ký kiểm toán hệ thống
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

    def _modify_config(self, file_path: Path) -> bool:
        """Mở tệp cấu hình .ini hoặc .yaml, chèn thêm trường thiết lập mới."""
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

    def _modify_log(self, file_path: Path) -> bool:
        """Ghi nối tiếp các dòng nhật ký vận hành hệ thống vào cuối file .log."""
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

    def execute(self) -> Dict[str, Any]:
        """
        Thực thi kịch bản mô phỏng các hoạt động lập trình và quản trị hệ thống.
        """
        target_extensions = [
            ".py", ".cpp", ".html", ".xml", ".sql",
            ".db", ".sqlite", ".ini", ".yaml", ".log"
        ]
        files = self.find_files(extensions=target_extensions)

        if not files:
            print("[!] Không tìm thấy file mã nguồn/database/config nào trong DecoyDocs.")
            return {"workload": self.name, "status": "skipped", "message": "Không có file mã nguồn hoặc cấu hình"}

        # Chọn ngẫu nhiên từ 5 đến 15 file để thao tác
        random.shuffle(files)
        selected_files = files[:min(len(files), 15)]

        print(f"[*] [{self.name}] Bắt đầu thao tác trên {len(selected_files)} file mã nguồn & dữ liệu...")
        modified_count = 0

        for file_path in selected_files:
            ext = file_path.suffix.lower()
            success = False

            if ext == ".py":
                success = self._modify_python(file_path)
            elif ext == ".cpp":
                success = self._modify_cpp(file_path)
            elif ext in (".html", ".xml"):
                success = self._modify_markup(file_path)
            elif ext == ".sql":
                success = self._modify_sql(file_path)
            elif ext in (".db", ".sqlite"):
                success = self._modify_sqlite(file_path)
            elif ext in (".ini", ".yaml"):
                success = self._modify_config(file_path)
            elif ext == ".log":
                success = self._modify_log(file_path)

            if success:
                modified_count += 1

            # Tạm dừng ngắn mô phỏng thao tác gõ bàn phím và biên dịch
            self.random_delay(0.1, 0.4)

        print(f"[+] [{self.name}] Đã thao tác thành công trên {modified_count}/{len(selected_files)} tệp tin.")

        return {
            "workload": self.name,
            "status": "success",
            "files_modified": modified_count,
            "total_targeted": len(selected_files)
        }
