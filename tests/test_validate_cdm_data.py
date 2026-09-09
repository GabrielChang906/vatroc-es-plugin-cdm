from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from validate_cdm_data import Validator  # noqa: E402


VALID_RATE = "RCTP:A:05L:*:D:05R:*:*:30_20\n"
VALID_SID = "RCSS,10,APU,10,KUDOS,3\n"
VALID_TAXI = "RCTP:05R:25.05:121.20:25.11:121.20:25.11:121.27:25.05:121.27:20\n"


class ValidatorTests(unittest.TestCase):
    def validate(self, *, rate=VALID_RATE, sid=VALID_SID, taxi=VALID_TAXI) -> Validator:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "rate.txt").write_text(rate, encoding="utf-8")
            (root / "sidInterval.txt").write_text(sid, encoding="utf-8")
            (root / "taxizones.txt").write_text(taxi, encoding="utf-8")
            validator = Validator(root, annotations=False)
            with redirect_stdout(StringIO()):
                validator.run()
            return validator

    def test_valid_files_pass(self) -> None:
        validator = self.validate(
            rate=VALID_RATE + "RCSS:A:*:*:D:10,28:*:*:30_20\n"
        )
        self.assertEqual(validator.errors, 0)
        self.assertEqual(validator.warnings, 0)

    def test_conflicting_rate_selector_fails(self) -> None:
        validator = self.validate(rate=VALID_RATE + "RCTP:A:05L:*:D:05R:*:*:25_15\n")
        self.assertGreater(validator.errors, 0)

    def test_reversed_sid_pair_conflict_fails(self) -> None:
        validator = self.validate(
            rate=VALID_RATE + "RCSS:A:*:*:D:10:*:*:30_20\n",
            sid=VALID_SID + "RCSS,10,KUDOS,10,APU,4\n",
        )
        self.assertGreater(validator.errors, 0)

    def test_self_crossing_taxi_polygon_fails(self) -> None:
        validator = self.validate(
            taxi="RCTP:05R:25.05:121.20:25.11:121.27:25.11:121.20:25.05:121.27:20\n"
        )
        self.assertGreater(validator.errors, 0)

    def test_operational_values_are_not_hard_coded(self) -> None:
        validator = self.validate(
            rate="RCTP:A:05L:*:D:05R:*:*:17_9\n",
            sid="RCTP,05R,CHALI,05R,CHALI,6.5\n",
            taxi="RCTP:05R:25.05:121.20:25.11:121.20:25.11:121.27:25.05:121.27:27\n",
        )
        self.assertEqual(validator.errors, 0)


if __name__ == "__main__":
    unittest.main()
