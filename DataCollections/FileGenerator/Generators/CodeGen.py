
import random
from pathlib import Path
from typing import Optional, List
from faker import Faker

try:
    from .Base import BaseFileGenerator
except (ImportError, ValueError):
    from Base import BaseFileGenerator


class SourceCodeGenerator(BaseFileGenerator):
    """
    Sinh các file mã nguồn lập trình với đa dạng kịch bản, cấu trúc và kích thước.
    """

    def __init__(self, faker: Faker, lang: Optional[str] = None) -> None:
        super().__init__(faker)
        self.lang = lang.lower().lstrip(".") if lang else None

    def generate(self, file_path: Path) -> None:
        """
        Xác định định dạng ngôn ngữ và xuất file mã nguồn ra đĩa.
        """
        ext = self.lang or file_path.suffix.lstrip(".").lower()

        if ext == "py":
            content = self._generate_python()
        elif ext == "sql":
            content = self._generate_sql()
        elif ext == "html":
            content = self._generate_html()
        elif ext == "xml":
            content = self._generate_xml()
        elif ext in ("cpp", "c"):
            content = self._generate_cpp()
        elif ext == "java":
            content = self._generate_java()
        elif ext in ("js", "ts"):
            content = self._generate_javascript()
        else:
            content = self._generate_python()

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    # =========================================================================
    # 1. PYTHON GENERATION (ĐA DẠNG 4 MẪU KIẾN TRÚC)
    # =========================================================================
    def _generate_python(self) -> str:
        templates = [
            self._py_template_api_controller,
            self._py_template_data_pipeline,
            self._py_template_ml_trainer,
            self._py_template_system_utils,
        ]
        return random.choice(templates)()

    def _py_template_api_controller(self) -> str:
        """Mẫu 1: RESTful API Controller (Flask / FastAPI style)"""
        service_name = "".join(self.faker.words(nb=2)).capitalize()
        resource = self.faker.word().lower()
        lines = [
            '"""',
            f"API Controller: {service_name} Router",
            f"Tác giả: {self.faker.name()}",
            f"Phiên bản: {random.randint(1, 3)}.{random.randint(0, 9)}.{random.randint(0, 9)}",
            '"""',
            "from fastapi import APIRouter, HTTPException, Depends, status",
            "from pydantic import BaseModel, EmailStr, Field",
            "from typing import List, Optional, Dict, Any",
            "import logging",
            "import time",
            "",
            f"router = APIRouter(prefix='/{resource}s', tags=['{service_name}'])",
            f"logger = logging.getLogger('{resource}_api')",
            "",
            f"class {service_name}Schema(BaseModel):",
            f"    id: Optional[int] = Field(None, description='ID định danh')",
            f"    title: str = Field(..., max_length=150, example='{self.faker.catch_phrase()}')",
            f"    description: Optional[str] = Field(None, example='{self.faker.sentence()}')",
            f"    is_active: bool = True",
            f"    created_by: str = '{self.faker.user_name()}'",
            "",
            f"class {service_name}Update(BaseModel):",
            f"    title: Optional[str] = None",
            f"    is_active: Optional[bool] = None",
            "",
            f"# Bộ nhớ đệm tạm thời",
            f"DB_MOCK: Dict[int, Dict[str, Any]] = {{}}",
            "",
            f"@router.get('/', response_model=List[{service_name}Schema])",
            f"async def list_{resource}s(skip: int = 0, limit: int = 50):",
            f"    '''Lấy danh sách {resource} với phân trang.'''",
            f"    logger.info(f'Truy vấn danh sách {resource} từ {{skip}} đến {{limit}}')",
            f"    items = list(DB_MOCK.values())[skip : skip + limit]",
            f"    return items",
            "",
            f"@router.post('/', status_code=status.HTTP_201_CREATED)",
            f"async def create_{resource}(payload: {service_name}Schema):",
            f"    item_id = len(DB_MOCK) + 1",
            f"    data = payload.dict()",
            f"    data['id'] = item_id",
            f"    DB_MOCK[item_id] = data",
            f"    logger.info(f'Tạo mới {resource} thành công với ID: {{item_id}}')",
            f"    return data",
            "",
            f"@router.get('/{{item_id}}')",
            f"async def get_{resource}_by_id(item_id: int):",
            f"    if item_id not in DB_MOCK:",
            f"        raise HTTPException(status_code=404, detail=f'{service_name} #{{item_id}} không tồn tại')",
            f"    return DB_MOCK[item_id]",
        ]
        return "\n".join(lines)

    def _py_template_data_pipeline(self) -> str:
        """Mẫu 2: Data Pipeline & ETL Processor (Pandas / Data Cleaning style)"""
        pipeline_name = self.faker.word().capitalize() + "ETLPipeline"
        batch_size = random.choice([100, 250, 500, 1000])
        lines = [
            '"""',
            f"Pipeline: {pipeline_name}",
            f"Hệ thống làm sạch và tổng hợp dữ liệu doanh nghiệp",
            '"""',
            "import os",
            "import csv",
            "import math",
            "import statistics",
            "from pathlib import Path",
            "from typing import List, Dict, Generator",
            "",
            f"class {pipeline_name}:",
            f"    BATCH_SIZE = {batch_size}",
            "",
            f"    def __init__(self, input_dir: str, output_dir: str) -> None:",
            f"        self.input_dir = Path(input_dir)",
            f"        self.output_dir = Path(output_dir)",
            f"        self.metrics = {{'processed': 0, 'errors': 0, 'skipped': 0}}",
            "",
            f"    def stream_raw_data(self) -> Generator[Dict[str, str], None, None]:",
            f"        '''Đọc dữ liệu theo luồng chống quá tải bộ nhớ RAM.'''",
            f"        if not self.input_dir.exists():",
            f"            return",
            f"        for csv_file in self.input_dir.glob('*.csv'):",
            f"            with open(csv_file, 'r', encoding='utf-8', errors='replace') as f:",
            f"                reader = csv.DictReader(f)",
            f"                for row in reader:",
            f"                    yield row",
            "",
            f"    def transform_and_validate(self, record: Dict[str, str]) -> Dict[str, Any]:",
            f"        '''Chuẩn hóa các trường giá trị số học và kiểm tra toàn vẹn.'''",
            f"        cleaned = {{}}",
            f"        for k, v in record.items():",
            f"            cleaned[k.strip().lower()] = v.strip()",
            f"        raw_val = float(cleaned.get('amount', 0.0))",
            f"        cleaned['normalized_amount'] = round(math.log1p(max(0.0, raw_val)), 4)",
            f"        self.metrics['processed'] += 1",
            f"        return cleaned",
            "",
            f"    def compute_summary_stats(self, values: List[float]) -> Dict[str, float]:",
            f"        if not values:",
            f"            return {{'mean': 0.0, 'variance': 0.0}}",
            f"        return {{",
            f"            'mean': round(statistics.mean(values), 4),",
            f"            'stdev': round(statistics.stdev(values) if len(values) > 1 else 0.0, 4),",
            f"            'median': round(statistics.median(values), 4)",
            f"        }}",
        ]
        return "\n".join(lines)

    def _py_template_ml_trainer(self) -> str:
        """Mẫu 3: Machine Learning Model Trainer (Scikit-Learn style)"""
        model_type = random.choice(["RandomForestClassifier", "GradientBoostingClassifier", "LogisticRegression"])
        n_estimators = random.choice([50, 100, 200])
        lines = [
            '"""',
            f"Huấn luyện mô hình phân loại: {model_type}",
            f"Dự án: Phân tích phát hiện bất thường hành vi hệ thống",
            '"""',
            "import numpy as np",
            "import joblib",
            "from pathlib import Path",
            f"from sklearn.ensemble import {model_type}",
            "from sklearn.model_selection import StratifiedKFold, cross_val_score",
            "from sklearn.metrics import classification_report, roc_auc_score",
            "",
            "def build_model(random_state: int = 42):",
            f"    model = {model_type}(",
            f"        n_estimators={n_estimators},",
            f"        max_depth={random.choice([5, 8, 12, None])},",
            f"        random_state=random_state,",
            f"        n_jobs=-1",
            f"    )",
            f"    return model",
            "",
            "def evaluate_cross_validation(X: np.ndarray, y: np.ndarray, n_splits: int = 5):",
            f"    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)",
            f"    model = build_model()",
            f"    scores = cross_val_score(model, X, y, cv=skf, scoring='f1_macro')",
            f"    print(f'F1-Score trung bình qua {{n_splits}} Folds: {{scores.mean():.4f}} (+/- {{scores.std():.4f}})')",
            f"    return scores",
            "",
            "def export_artifacts(model, output_path: str):",
            f"    out_file = Path(output_path)",
            f"    out_file.parent.mkdir(parents=True, exist_ok=True)",
            f"    joblib.dump(model, out_file, compress=3)",
            f"    print(f'Mô hình đã được đóng gói thành công tại: {{out_file}}')",
        ]
        return "\n".join(lines)

    def _py_template_system_utils(self) -> str:
        """Mẫu 4: System Helper & Cryptography Utilities"""
        mod_name = self.faker.word().capitalize() + "CryptoUtil"
        lines = [
            '"""',
            f"Utility: {mod_name}",
            f"Bộ công cụ kiểm tra băm toàn vẹn (Hashing) và mã hóa chuỗi nhị phân",
            '"""',
            "import hashlib",
            "import hmac",
            "import base64",
            "import secrets",
            "from typing import Tuple",
            "",
            f"class {mod_name}:",
            f"    SALT_SIZE = 16",
            f"    HASH_ROUNDS = 100000",
            "",
            f"    @staticmethod",
            f"    def generate_secure_token(length: int = 32) -> str:",
            f"        return secrets.token_urlsafe(length)",
            "",
            f"    @staticmethod",
            f"    def hash_password(password: str) -> Tuple[str, str]:",
            f"        salt = secrets.token_bytes({mod_name}.SALT_SIZE)",
            f"        key = hashlib.pbkdf2_hmac(",
            f"            'sha256',",
            f"            password.encode('utf-8'),",
            f"            salt,",
            f"            {mod_name}.HASH_ROUNDS",
            f"        )",
            f"        salt_b64 = base64.b64encode(salt).decode('ascii')",
            f"        key_b64 = base64.b64encode(key).decode('ascii')",
            f"        return salt_b64, key_b64",
            "",
            f"    @staticmethod",
            f"    def verify_integrity(data_bytes: bytes, expected_hash: str) -> bool:",
            f"        calc_hash = hashlib.sha256(data_bytes).hexdigest()",
            f"        return hmac.compare_digest(calc_hash.lower(), expected_hash.lower())",
        ]
        return "\n".join(lines)

    # =========================================================================
    # 2. SQL GENERATION (ĐA DẠNG 3 MẪU NGHIỆP VỤ)
    # =========================================================================
    def _generate_sql(self) -> str:
        templates = [
            self._sql_template_ecommerce,
            self._sql_template_banking,
            self._sql_template_human_resources,
        ]
        return random.choice(templates)()

    def _sql_template_ecommerce(self) -> str:
        """Mẫu SQL 1: E-Commerce Store (Khách hàng, Đơn hàng, Sản phẩm)"""
        prefix = self.faker.word().lower()
        lines = [
            f"-- Schema Hệ thống Bán lẻ & Quản lý Kho hàng",
            f"-- Cơ sở dữ liệu: shop_{prefix}",
            "",
            f"CREATE TABLE products (",
            f"    product_id INT PRIMARY KEY AUTO_INCREMENT,",
            f"    sku VARCHAR(50) UNIQUE NOT NULL,",
            f"    product_name VARCHAR(200) NOT NULL,",
            f"    category_id INT NOT NULL,",
            f"    unit_price DECIMAL(10, 2) NOT NULL,",
            f"    stock_quantity INT DEFAULT 0,",
            f"    is_available BOOLEAN DEFAULT TRUE",
            f");",
            "",
            f"CREATE TABLE orders (",
            f"    order_id INT PRIMARY KEY AUTO_INCREMENT,",
            f"    customer_name VARCHAR(150) NOT NULL,",
            f"    customer_email VARCHAR(100) NOT NULL,",
            f"    order_total DECIMAL(12, 2) NOT NULL,",
            f"    order_status VARCHAR(30) DEFAULT 'PENDING',",
            f"    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            f");",
            "",
            f"CREATE INDEX idx_orders_customer ON orders(customer_email);",
            "",
        ]
        for _ in range(random.randint(6, 12)):
            prod = self.faker.catch_phrase().replace("'", "''")
            price = round(random.uniform(15.0, 1200.0), 2)
            qty = random.randint(5, 200)
            lines.append(
                f"INSERT INTO products (sku, product_name, category_id, unit_price, stock_quantity) "
                f"VALUES ('SKU-{random.randint(1000, 9999)}', '{prod}', {random.randint(1, 10)}, {price}, {qty});"
            )
        lines.append("")
        lines.append(f"SELECT p.category_id, COUNT(p.product_id) AS total_items, SUM(p.stock_quantity * p.unit_price) AS total_inventory_value FROM products p GROUP BY p.category_id;")
        return "\n".join(lines)

    def _sql_template_banking(self) -> str:
        """Mẫu SQL 2: Ngân hàng & Giao dịch Tài chính"""
        lines = [
            f"-- Hệ thống Giám định Giao dịch Ngân hàng & Sổ cái",
            "",
            f"CREATE TABLE accounts (",
            f"    account_number VARCHAR(20) PRIMARY KEY,",
            f"    account_holder VARCHAR(150) NOT NULL,",
            f"    id_card_number VARCHAR(20) NOT NULL,",
            f"    current_balance DECIMAL(18, 2) NOT NULL DEFAULT 0.00,",
            f"    account_type VARCHAR(20) DEFAULT 'SAVINGS',",
            f"    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            f");",
            "",
            f"CREATE TABLE transactions (",
            f"    trans_id VARCHAR(64) PRIMARY KEY,",
            f"    source_account VARCHAR(20) NOT NULL,",
            f"    destination_account VARCHAR(20) NOT NULL,",
            f"    amount DECIMAL(15, 2) NOT NULL,",
            f"    fee DECIMAL(8, 2) DEFAULT 0.00,",
            f"    trans_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            f");",
            "",
        ]
        for _ in range(random.randint(6, 10)):
            acc = f"VIB{random.randint(10000000, 99999999)}"
            name = self.faker.name().replace("'", "''")
            bal = round(random.uniform(500.0, 250000.0), 2)
            lines.append(
                f"INSERT INTO accounts (account_number, account_holder, id_card_number, current_balance) "
                f"VALUES ('{acc}', '{name}', '{self.faker.ssn()}', {bal});"
            )
        lines.append("")
        lines.append("SELECT source_account, SUM(amount) AS total_sent FROM transactions GROUP BY source_account HAVING total_sent > 10000.00;")
        return "\n".join(lines)

    def _sql_template_human_resources(self) -> str:
        """Mẫu SQL 3: Quản lý Nhân sự & Bảng lương"""
        lines = [
            f"-- Bảng lương & Hồ sơ Nhân viên Tập đoàn",
            "",
            f"CREATE TABLE employees (",
            f"    emp_id INT PRIMARY KEY AUTO_INCREMENT,",
            f"    full_name VARCHAR(120) NOT NULL,",
            f"    department VARCHAR(50) NOT NULL,",
            f"    job_title VARCHAR(80) NOT NULL,",
            f"    base_salary DECIMAL(12, 2) NOT NULL,",
            f"    hire_date DATE NOT NULL",
            f");",
            "",
        ]
        for _ in range(random.randint(6, 12)):
            name = self.faker.name().replace("'", "''")
            dept = random.choice(["Kỹ thuật", "Kinh doanh", "Nhân sự", "Tài chính", "Marketing"])
            job = self.faker.job().replace("'", "''")
            sal = random.randint(15, 80) * 1000000
            lines.append(
                f"INSERT INTO employees (full_name, department, job_title, base_salary, hire_date) "
                f"VALUES ('{name}', '{dept}', '{job}', {sal}, '{self.faker.date()}');"
            )
        lines.append("")
        lines.append("SELECT department, COUNT(emp_id) AS total_staff, AVG(base_salary) AS average_salary FROM employees GROUP BY department;")
        return "\n".join(lines)

    # =========================================================================
    # 3. HTML / XML / C++ / JAVA / JS (ĐA DẠNG NỘI DUNG)
    # =========================================================================
    def _generate_html(self) -> str:
        title = self.faker.catch_phrase()
        theme = random.choice(["#007bff", "#28a745", "#dc3545", "#6f42c1", "#fd7e14"])
        rows_count = random.randint(8, 20)
        lines = [
            "<!DOCTYPE html>",
            "<html lang='vi'>",
            "<head>",
            "    <meta charset='UTF-8'>",
            f"    <title>{title}</title>",
            "    <style>",
            "        body { font-family: Segoe UI, Tahoma, sans-serif; margin: 30px; background: #fafafa; }",
            f"        .card {{ background: white; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); padding: 20px; }}",
            f"        h2 {{ color: {theme}; }}",
            "        table { width: 100%; border-collapse: collapse; margin-top: 15px; }",
            f"        th {{ background: {theme}; color: white; padding: 10px; }}",
            "        td { padding: 8px; border-bottom: 1px solid #eee; }",
            "    </style>",
            "</head>",
            "<body>",
            "    <div class='card'>",
            f"        <h2>Báo Cáo: {title}</h2>",
            f"        <p>Phụ trách: <strong>{self.faker.name()}</strong> | Mã kiểm toán: <code>{self.faker.uuid4()[:8]}</code></p>",
            "        <table>",
            "            <thead><tr><th>#</th><th>Khách Hàng</th><th>Điện Thoại</th><th>Doanh Thu</th></tr></thead>",
            "            <tbody>",
        ]
        for i in range(1, rows_count + 1):
            rev = f"{random.randint(100, 990) * 10000:,} đ"
            lines.append(f"                <tr><td>{i}</td><td>{self.faker.name()}</td><td>{self.faker.phone_number()}</td><td>{rev}</td></tr>")
        lines.extend([
            "            </tbody>",
            "        </table>",
            "    </div>",
            "</body>",
            "</html>"
        ])
        return "\n".join(lines)

    def _generate_xml(self) -> str:
        root_tag = random.choice(["catalog", "inventory", "export_data", "system_audit"])
        lines = [
            "<?xml version='1.0' encoding='UTF-8'?>",
            f"<{root_tag} timestamp='{self.faker.iso8601()}'>",
            f"    <meta>",
            f"        <tenant_id>{self.faker.uuid4()}</tenant_id>",
            f"        <operator>{self.faker.user_name()}</operator>",
            f"    </meta>",
            f"    <items>",
        ]
        for i in range(1, random.randint(8, 16)):
            lines.append(f"        <item id='{i}'>")
            lines.append(f"            <name>{self.faker.word().capitalize()}</name>")
            lines.append(f"            <status>{random.choice(['ACTIVE', 'INACTIVE', 'ARCHIVED'])}</status>")
            lines.append(f"            <score>{round(random.uniform(1.0, 99.9), 2)}</score>")
            lines.append(f"        </item>")
        lines.append("    </items>")
        lines.append(f"</{root_tag}>")
        return "\n".join(lines)

    def _generate_cpp(self) -> str:
        class_name = self.faker.word().capitalize() + "Handler"
        return "\n".join([
            "#include <iostream>",
            "#include <vector>",
            "#include <string>",
            "#include <algorithm>",
            "",
            f"class {class_name} {{",
            "private:",
            "    int instanceId;",
            "    std::string tag;",
            "    std::vector<int> buffer;",
            "public:",
            f"    {class_name}(int id, std::string t) : instanceId(id), tag(t) {{",
            "        std::cout << \"Khởi tạo: \" << tag << \" ID=\" << instanceId << std::endl;",
            "    }",
            "    void appendValue(int val) { buffer.push_back(val); }",
            "    double getAverage() const {",
            "        if (buffer.empty()) return 0.0;",
            "        double sum = 0;",
            "        for (int v : buffer) sum += v;",
            "        return sum / buffer.size();",
            "    }",
            "};",
            "",
            "int main() {",
            f"    {class_name} obj({random.randint(100, 999)}, \"{self.faker.word()}\");",
            f"    for (int i = 0; i < {random.randint(5, 15)}; ++i) obj.appendValue(i * 10);",
            "    return 0;",
            "}"
        ])

    def _generate_java(self) -> str:
        class_name = self.faker.word().capitalize() + "Service"
        return "\n".join([
            "package com.company.app;",
            "",
            "import java.util.List;",
            "import java.util.ArrayList;",
            "",
            f"public class {class_name} {{",
            f"    private final String serviceTag = \"{class_name}\";",
            f"    private final List<String> cache = new ArrayList<>();",
            "",
            f"    public void addItem(String item) {{",
            "        this.cache.add(item);",
            "    }",
            "",
            "    public int getCacheSize() {",
            "        return this.cache.size();",
            "    }",
            "}"
        ])

    def _generate_javascript(self) -> str:
        mod = self.faker.word()
        return "\n".join([
            "/**",
            f" * Module xử lý nghiệp vụ: {mod}",
            f" * Phiên bản: {random.randint(1, 4)}.{random.randint(0, 9)}",
            " */",
            f"const {mod}Config = {{",
            f"    timeoutMs: {random.choice([3000, 5000, 10000])},",
            f"    retries: {random.randint(2, 5)},",
            f"    endpoint: 'https://api.internal.corp/{mod}'",
            "};",
            "",
            f"function executeTask(payload) {{",
            "    console.log('Bắt đầu thực thi tác vụ...');",
            "    return { status: 'SUCCESS', timestamp: Date.now() };",
            "}",
            "",
            f"module.exports = {{ {mod}Config, executeTask }};"
        ])
