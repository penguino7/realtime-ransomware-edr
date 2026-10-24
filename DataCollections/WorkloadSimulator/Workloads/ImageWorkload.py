
import random
from pathlib import Path
from typing import List, Dict, Optional, Any
from PIL import Image
from .BaseWorkload import BaseWorkload


class ImageWorkload(BaseWorkload):
    """
    Kịch bản xử lý ảnh hàng loạt (xoay ảnh, resize, lật ảnh) trên các thư mục mồi DecoyDocs.
    """

    def __init__(self, target_dirs: Optional[List[Path]] = None) -> None:
        super().__init__(target_dirs=target_dirs, name="ImageWorkload")

    def _process_single_image(self, image_path: Path) -> bool:
        """
        Đọc và chỉnh sửa một tệp tin ảnh, sau đó lưu đè lại vào đĩa.
        """
        try:
            # Mở và nạp dữ liệu ảnh vào RAM trước để đóng file handle, tránh lock file trên Windows
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

            # Xác định định dạng ảnh và lưu đè lại
            is_png = image_path.suffix.lower() == ".png"
            fmt = "PNG" if is_png else "JPEG"

            if fmt == "JPEG" and processed.mode in ("RGBA", "P"):
                processed = processed.convert("RGB")

            processed.save(str(image_path), format=fmt, quality=90)
            return True
        except Exception:
            return False

    def execute(self) -> Dict[str, Any]:
        """
        Thực thi kịch bản xử lý ảnh hàng loạt trên danh sách file mồi.
        """
        target_extensions = [".jpg", ".jpeg", ".png"]
        files = self.find_files(extensions=target_extensions)

        if not files:
            print("[!] Không tìm thấy file ảnh nào trong DecoyDocs.")
            return {"workload": self.name, "status": "skipped", "message": "Không có file ảnh"}

        # Chọn ngẫu nhiên từ 6 đến 15 file ảnh để xử lý
        random.shuffle(files)
        selected_files = files[:min(len(files), 15)]

        print(f"[*] [{self.name}] Bắt đầu mở và xử lý đồ họa hàng loạt trên {len(selected_files)} file ảnh...")
        processed_count = 0

        for file_path in selected_files:
            if self._process_single_image(file_path):
                processed_count += 1

            # Tạm dừng ngắn mô phỏng nhịp xử lý liên tiếp của phần mềm đồ họa
            self.random_delay(0.1, 0.3)

        print(f"[+] [{self.name}] Đã xử lý và lưu thành công {processed_count}/{len(selected_files)} tệp tin ảnh.")

        return {
            "workload": self.name,
            "status": "success",
            "images_processed": processed_count,
            "total_targeted": len(selected_files)
        }
