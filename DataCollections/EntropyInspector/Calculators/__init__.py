"""
Package Calculators phục vụ tính toán các chỉ số thống kê và Shannon Entropy cho EntropyInspector.
"""

from DataCollections.EntropyInspector.Calculators.ShannonEntropyCalculator import (
    EntropyResult,
    ShannonEntropyCalculator,
)

__all__ = ["ShannonEntropyCalculator", "EntropyResult"]
