"""
Kiểm thử đơn vị cho phân hệ Data.ParsersRawLog
"""

import unittest
from pathlib import Path
from Src.Core.Schemas import IRPOperation, IRPEvent
from Src.Data.ParsersRawLog import LogFormatters, EntropyLoader, EntropyMatcher, IrpParser


class TestDataPipeline(unittest.TestCase):
    """Bộ kiểm thử đơn vị cho toàn bộ pipeline tiền xử lý dữ liệu."""

    def test_log_formatters(self):
        """Kiểm tra LogFormatters: timestamps và regex bóc tách."""
        # 1. Procmon Timestamp
        sec_procmon = LogFormatters.parse_procmon_timestamp("3:20:58.7449945 PM")
        expected_sec = 15 * 3600 + 20 * 60 + 58 + 0.744994
        self.assertAlmostEqual(sec_procmon, expected_sec, places=4)

        # 2. Realtime Timestamp
        sec_rt = LogFormatters.parse_realtime_timestamp("15:20:58.833709")
        expected_rt = 15 * 3600 + 20 * 60 + 58 + 0.833709
        self.assertAlmostEqual(sec_rt, expected_rt, places=4)

        # 3. Bóc tách Length
        detail_len = "Offset: 1,328, Length: 142, Priority: Normal"
        self.assertEqual(LogFormatters.extract_length(detail_len), 142)

        # 4. Bóc tách Rename path
        detail_rename = r"FileName: C:\Users\nhat\Desktop\DecoyDocs\sample.docx.locked"
        self.assertEqual(
            LogFormatters.extract_rename_path(detail_rename),
            r"C:\Users\nhat\Desktop\DecoyDocs\sample.docx.locked"
        )

    def test_entropy_loader_and_matcher(self):
        """Kiểm tra nạp dữ liệu và ghép cặp entropy."""
        raw_rt = Path("Data/Raw/realtime_entropy.csv")
        raw_before = Path("Data/Raw/before_entropy_01.csv")

        if raw_rt.exists() and raw_before.exists():
            loader = EntropyLoader(baseline_path=raw_before, realtime_path=raw_rt)
            loader.load_all()

            self.assertGreater(len(loader.baseline_map), 900)
            self.assertGreater(len(loader.realtime_map), 100)

            matcher = EntropyMatcher(loader=loader, tolerance_sec=2.0)

            # Test DELETE operation
            curr_h, base_h = matcher.match("any_path", 55258.0, IRPOperation.DELETE)
            self.assertEqual(curr_h, 0.0)

    def test_irp_parser_pipeline(self):
        """Kiểm tra luồng tích hợp của IrpParser với dữ liệu thực tế."""
        raw_procmon = Path("Data/Raw/Procmon_log.CSV")
        raw_rt = Path("Data/Raw/realtime_entropy.csv")
        raw_before = Path("Data/Raw/before_entropy_01.csv")

        if raw_procmon.exists() and raw_rt.exists() and raw_before.exists():
            parser = IrpParser(
                procmon_path=raw_procmon,
                realtime_entropy_path=raw_rt,
                baseline_entropy_path=raw_before
            )

            # Parse 100 sự kiện đầu
            events = parser.parse(limit=100)
            self.assertEqual(len(events), 100)
            for ev in events:
                self.assertIsInstance(ev, IRPEvent)
                self.assertIn(ev.operation, IrpParser.TARGET_OPERATIONS)
                self.assertIn("decoydocs", ev.file_path.lower())


if __name__ == "__main__":
    unittest.main()
