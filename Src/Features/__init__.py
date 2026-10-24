"""
Package Src.Features
====================
Chứa các thành phần trích xuất đặc trưng toán học cho hệ thống EDR:
- WindowManager: Quản lý 3 tầng cửa sổ trượt (Short, Medium, Long) theo từng PID.
"""

from .WindowManager import WindowManager

__all__ = ["WindowManager"]

