"""
Bộ sinh các tệp tin cơ sở dữ liệu nhị phân (.db, .sqlite) và tệp cấu hình hệ thống (.ini, .yaml, .log).
Mục đích:
- Tạo các tệp tin cơ sở dữ liệu thật bằng thư viện sqlite3 (có Magic Bytes 'SQLite format 3').
- Tạo các tệp cấu hình, nhật ký máy chủ chân thực với nhiều ngữ cảnh nghiệp vụ khác nhau.
- Đây là mục tiêu tống tiền ưu tiên số 1 của các dòng Ransomware doanh nghiệp (như LockBit, Conti, Ryuk).
"""

import os
import random
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from faker import Faker

try:
    from .Base import BaseFileGenerator
except (ImportError, ValueError):
    from Base import BaseFileGenerator


class DatabaseConfigFileGenerator(BaseFileGenerator):
    """
    Sinh các tệp tin cơ sở dữ liệu nhị phân SQLite (.db, .sqlite)
    và các tệp cấu hình, nhật ký (.ini, .yaml, .log).
    """

    def __init__(self, faker: Faker, file_type: Optional[str] = None) -> None:
        super().__init__(faker)
        self.file_type = file_type.lower().lstrip(".") if file_type else None

    def generate(self, file_path: Path) -> None:
        """
        Xác định định dạng tệp tin và thực thi logic sinh dữ liệu tương ứng.
        """
        ext = self.file_type or file_path.suffix.lstrip(".").lower()
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if ext in ("db", "sqlite", "sqlite3"):
            self._generate_sqlite_database(file_path)
        elif ext == "ini":
            content = self._generate_ini_config()
            file_path.write_text(content, encoding="utf-8")
        elif ext in ("yaml", "yml"):
            content = self._generate_yaml_config()
            file_path.write_text(content, encoding="utf-8")
        elif ext == "log":
            content = self._generate_system_log()
            file_path.write_text(content, encoding="utf-8")
        else:
            self._generate_sqlite_database(file_path)

    # =========================================================================
    # 1. CƠ SỞ DỮ LIỆU SQLITE THẬT (.db, .sqlite) - ĐA DẠNG NGHIỆP VỤ
    # =========================================================================
    def _generate_sqlite_database(self, file_path: Path) -> None:
        """
        Khởi tạo tệp cơ sở dữ liệu SQLite nhị phân thực thụ có Magic Bytes chuẩn.
        Đa dạng hóa 3 chủ đề: Ngân hàng, Khách hàng & Hóa đơn, Quản trị Người dùng.
        """
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass

        conn = sqlite3.connect(str(file_path))
        cursor = conn.cursor()

        schema_choice = random.choice(["banking", "crm", "auth"])

        if schema_choice == "banking":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    account_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_number TEXT UNIQUE NOT NULL,
                    owner_name TEXT NOT NULL,
                    balance REAL NOT NULL,
                    created_date TEXT NOT NULL
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_number TEXT NOT NULL,
                    amount REAL NOT NULL,
                    tx_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                );
            """)
            for i in range(1, random.randint(15, 30)):
                acc_num = f"ACC_{random.randint(100000, 999999)}_{i}"
                cursor.execute(
                    "INSERT OR IGNORE INTO accounts (account_number, owner_name, balance, created_date) VALUES (?, ?, ?, ?)",
                    (acc_num, self.faker.name(), round(random.uniform(500.0, 50000.0), 2), self.faker.date())
                )
                cursor.execute(
                    "INSERT INTO transactions (account_number, amount, tx_type, timestamp) VALUES (?, ?, ?, ?)",
                    (acc_num, round(random.uniform(10.0, 5000.0), 2), random.choice(["DEPOSIT", "WITHDRAW", "TRANSFER"]), self.faker.iso8601())
                )

        elif schema_choice == "crm":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    cust_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name TEXT NOT NULL,
                    contact_person TEXT NOT NULL,
                    contact_email TEXT NOT NULL,
                    phone_number TEXT NOT NULL,
                    annual_revenue REAL DEFAULT 0.0
                );
            """)
            for i in range(1, random.randint(15, 30)):
                cursor.execute(
                    "INSERT INTO customers (company_name, contact_person, contact_email, phone_number, annual_revenue) VALUES (?, ?, ?, ?, ?)",
                    (f"{self.faker.company()} #{i}", self.faker.name(), self.faker.email(), self.faker.phone_number(), round(random.uniform(50000.0, 2000000.0), 2))
                )

        else:  # auth schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    hashed_pwd TEXT NOT NULL,
                    role TEXT NOT NULL,
                    last_login TEXT
                );
            """)
            for i in range(1, random.randint(15, 30)):
                cursor.execute(
                    "INSERT OR IGNORE INTO users (username, hashed_pwd, role, last_login) VALUES (?, ?, ?, ?)",
                    (f"{self.faker.user_name()}_{i}", self.faker.sha256(), random.choice(["ADMIN", "OPERATOR", "ANALYST", "VIEWER"]), self.faker.iso8601())
                )

        conn.commit()
        conn.close()

    # =========================================================================
    # 2. CẤU HÌNH INI (.ini)
    # =========================================================================
    def _generate_ini_config(self) -> str:
        """Sinh tệp cấu hình INI chuẩn với nhiều khối thiết lập thực tế."""
        app_name = self.faker.word().lower()
        lines = [
            f"# ==================================================",
            f"# Cấu hình Dịch vụ Hệ thống: {app_name.upper()}",
            f"# Tự động sinh lúc: {self.faker.date_time()}",
            f"# ==================================================",
            "",
            "[database]",
            f"host = {self.faker.ipv4()}",
            f"port = {random.choice([5432, 3306, 1433, 27017])}",
            f"name = {app_name}_production_db",
            f"username = db_admin_{self.faker.word()}",
            f"password = {self.faker.password(length=18)}",
            f"pool_size = {random.choice([10, 20, 50, 100])}",
            f"timeout_seconds = 30",
            "",
            "[server]",
            f"bind_address = 0.0.0.0",
            f"listen_port = {random.randint(8000, 9500)}",
            f"workers = {random.choice([2, 4, 8, 16])}",
            f"debug_mode = false",
            f"environment = production",
            "",
            "[security]",
            f"jwt_secret_key = {self.faker.sha256()}",
            f"token_expire_minutes = {random.choice([60, 120, 1440])}",
            f"enable_cors = true",
            f"allowed_origins = https://{self.faker.domain_name()}",
            "",
            "[logging]",
            f"log_level = {random.choice(['INFO', 'WARN', 'DEBUG'])}",
            f"log_file_path = /var/log/{app_name}/application.log",
            f"max_bytes_per_file = 10485760",
            f"backup_count = 5",
        ]
        return "\n".join(lines)

    # =========================================================================
    # 3. CẤU HÌNH YAML (.yaml, .yml)
    # =========================================================================
    def _generate_yaml_config(self) -> str:
        """Sinh tệp cấu hình YAML phân cấp chuẩn cho Docker/Kubernetes/Service."""
        service = self.faker.word().lower()
        lines = [
            "---",
            f"# Cấu hình triển khai Kubernetes / Docker Compose",
            f"# Dịch vụ: {service}-microservice",
            "apiVersion: apps/v1",
            "kind: Deployment",
            "metadata:",
            f"  name: {service}-deployment",
            f"  namespace: production",
            "  labels:",
            f"    app: {service}",
            f"    tier: backend",
            "spec:",
            f"  replicas: {random.randint(2, 6)}",
            "  selector:",
            "    matchLabels:",
            f"      app: {service}",
            "  template:",
            "    metadata:",
            "      labels:",
            f"        app: {service}",
            "    spec:",
            "      containers:",
            f"        - name: {service}-app",
            f"          image: registry.internal.corp/{service}:v{random.randint(1, 3)}.{random.randint(0, 9)}",
            "          ports:",
            f"            - containerPort: {random.randint(8000, 9000)}",
            "          resources:",
            "            limits:",
            f"              cpu: '{random.choice([0.5, 1.0, 2.0])}'",
            f"              memory: '{random.choice([512, 1024, 2048])}Mi'",
            "            requests:",
            "              cpu: '250m'",
            "              memory: '256Mi'",
            "          env:",
            f"            - name: DATABASE_URL",
            f"              value: 'postgresql://admin:{self.faker.password(length=12)}@{self.faker.ipv4()}:5432/{service}_db'",
            f"            - name: REDIS_HOST",
            f"              value: '{self.faker.ipv4()}'",
            f"            - name: ENABLE_METRICS",
            f"              value: 'true'",
        ]
        return "\n".join(lines)

    # =========================================================================
    # 4. NHẬT KÝ HỆ THỐNG LOG (.log)
    # =========================================================================
    def _generate_system_log(self) -> str:
        """Sinh tệp log hệ thống chứa từ 30 đến 60 dòng log chân thực."""
        log_lines = []
        app_name = self.faker.word().upper()
        levels = ["INFO", "INFO", "INFO", "WARN", "ERROR"]

        for _ in range(random.randint(30, 60)):
            ts = self.faker.iso8601()
            level = random.choice(levels)
            ip = self.faker.ipv4()
            user = self.faker.user_name()
            latency = round(random.uniform(5.0, 450.0), 2)
            action = random.choice([
                f"Người dùng '{user}' đăng nhập thành công từ {ip}",
                f"Thực hiện truy vấn SQL: SELECT * FROM transactions WHERE user_id={random.randint(10, 999)} [{latency}ms]",
                f"Tạo token xác thực JWT cho phiên làm việc mới",
                f"Cảnh báo bộ nhớ đệm Redis vượt ngưỡng 75%",
                f"Lỗi kết nối tới cổng thanh toán đối tác [Timeout={latency}ms]",
                f"Hoàn tất sao lưu cơ sở dữ liệu định kỳ vào vùng lưu trữ S3",
                f"Xác thực thất bại 3 lần liên tiếp từ địa chỉ IP: {ip}"
            ])
            log_lines.append(f"{ts} [{level:<5}] [{app_name}] [PID:{random.randint(1000, 9999)}] - {action}")

        return "\n".join(log_lines)
