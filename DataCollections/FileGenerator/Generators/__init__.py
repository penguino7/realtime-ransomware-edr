"""
Chứa các bộ sinh tệp tin theo từng định dạng chuyên biệt.
"""

from .Base import BaseFileGenerator
from .TextGen import TextDocumentGenerator, StructuredDataGenerator
from .OfficeGen import OfficeDocumentGenerator
from .PdfGen import PDFDocumentGenerator
from .ImageGen import ImageFileGenerator

__all__ = [
    "BaseFileGenerator",
    "TextDocumentGenerator",
    "StructuredDataGenerator",
    "OfficeDocumentGenerator",
    "PDFDocumentGenerator",
    "ImageFileGenerator",
]

