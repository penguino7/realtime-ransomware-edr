import random
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from .BaseWorkload import BaseWorkload


# Kịch bản xử lý ảnh hàng loạt (xoay, resize, lật) theo cụm thư mục ảnh
class ImageWorkload(BaseWorkload):

    BURST_SIZE = 15

    # Khởi tạo workload đồ họa với dải số lượng ảnh mục tiêu
    def __init__(
        self,
        target_dirs: Optional[List[Path]] = None,
        min_files: int = 40,
        max_files: int = 100
    ) -> None:
        super().__init__(target_dirs=target_dirs, name="ImageWorkload")
        self.min_files = max(5, min_files)
        self.max_files = max(self.min_files, max_files)

    # Đọc, chỉnh sửa một tệp ảnh trong RAM và lưu đè lại vào đĩa
    def _process_single_image(self, image_path: Path) -> bool:
        try:
            # Nạp ảnh vào RAM trước để đóng file handle, tránh lock file trên Windows
            with Image.open(image_path) as img:
                img.load()
                action = random.choice(["rotate", "resize", "flip"])

                if action == "rotate":
                    angle = random.choice([90, 180, 270])
                    processed = img.rotate(angle, expand=True)
                elif action == "resize":
                    factor = random.uniform(0.85, 0.95)
                    new_w = max(10, int(img.width * factor))
                    new_h = max(10, int(img.height * factor))
                    processed = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                else:
                    processed = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

            is_png = image_path.suffix.lower() == ".png"
            fmt = "PNG" if is_png else "JPEG"

            if fmt == "JPEG" and processed.mode in ("RGBA", "P"):
                processed = processed.convert("RGB")

            processed.save(str(image_path), format=fmt, quality=90)
            return True
        except Exception:
            return False

    # Thực thi kịch bản xử lý ảnh hàng loạt theo cụm thư mục và nhịp burst/pause
    def execute(self) -> Dict[str, Any]:
        target_extensions = [".jpg", ".jpeg", ".png"]
        files = self.find_files(extensions=target_extensions)

        if not files:
            print("[!] Không tìm thấy file ảnh nào trong DecoyDocs.")
            return {"workload": self.name, "status": "skipped", "message": "Không có file ảnh"}

        target_count = (
            random.randint(self.min_files, min(len(files), self.max_files))
            if len(files) >= self.min_files
            else len(files)
        )
        selected_files = self.select_files_clustered(files, target_count=target_count, locality_ratio=0.85)

        print(f"[*] [{self.name}] Bắt đầu mở và xử lý đồ họa hàng loạt trên {len(selected_files)} file ảnh...")
        processed_count = 0

        for idx, file_path in enumerate(selected_files):
            if self._process_single_image(file_path):
                processed_count += 1

            self.burst_or_pause(idx, burst_size=self.BURST_SIZE, burst_delay=(0.01, 0.05), pause_range=(1.0, 2.5))

        print(f"[+] [{self.name}] Đã xử lý và lưu thành công {processed_count}/{len(selected_files)} tệp tin ảnh.")

        return {
            "workload": self.name,
            "status": "success",
            "images_processed": processed_count,
            "total_targeted": len(selected_files)
        }
