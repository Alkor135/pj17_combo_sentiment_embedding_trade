from datetime import date, timedelta
from pathlib import Path
import shutil
import unittest

import prepare


class PrepareDoneCleanupTests(unittest.TestCase):
    def test_selects_done_markers_older_than_10_days_and_limits_to_10_newest(self):
        today = date(2026, 4, 19)
        filenames = []

        for offset in range(15):
            marker_date = today - timedelta(days=offset)
            filenames.append(f"rts_SPBFUT192yc_{marker_date:%Y-%m-%d}.done")

        filenames.extend(
            [
                "mix_SPBFUT192yc_invalid.done",
                "positions.yaml",
            ]
        )

        paths = [Path(name) for name in filenames]

        to_delete = prepare.get_done_markers_to_delete(
            paths,
            today=today,
            max_age_days=10,
            max_files=10,
        )

        self.assertEqual(
            [path.name for path in to_delete],
            [
                "rts_SPBFUT192yc_2026-04-09.done",
                "rts_SPBFUT192yc_2026-04-08.done",
                "rts_SPBFUT192yc_2026-04-07.done",
                "rts_SPBFUT192yc_2026-04-06.done",
                "rts_SPBFUT192yc_2026-04-05.done",
            ],
        )

    def test_cleanup_prepare_logs_keeps_only_three_newest_files(self):
        log_dir = Path(__file__).resolve().parent / "_tmp_prepare_logs"
        if log_dir.exists():
            shutil.rmtree(log_dir)
        log_dir.mkdir(parents=True)
        try:
            names = [
                "prepare_2026-04-19_21-00-01.txt",
                "prepare_2026-04-19_21-00-02.txt",
                "prepare_2026-04-19_21-00-03.txt",
                "prepare_2026-04-19_21-00-04.txt",
            ]
            for name in names:
                (log_dir / name).write_text("log", encoding="utf-8")

            prepare.cleanup_prepare_logs(log_dir, max_files=3)

            self.assertEqual(
                sorted(path.name for path in log_dir.glob("prepare_*.txt")),
                names[-3:],
            )
        finally:
            shutil.rmtree(log_dir)


if __name__ == "__main__":
    unittest.main()
