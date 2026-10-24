"""
Package Src.Features
====================
Chứa các thành phần trích xuất đặc trưng toán học cho hệ thống EDR:
- WindowManager: Quản lý 3 tầng cửa sổ trượt (Short, Medium, Long) theo từng PID.
- FeatureExtractor: Hiện thực hóa 27 công thức toán học vật lý, đóng gói FeatureVector.
"""

from .WindowManager import WindowManager
from .FeatureExtractor import FeatureExtractor

__all__ = ["WindowManager", "FeatureExtractor"]
