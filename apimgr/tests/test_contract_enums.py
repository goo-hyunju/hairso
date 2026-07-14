"""F8 parity — domain enum 이 contract/enums.json 정본과 일치하는지 검증.

BE 코드에서 enum 값이 드리프트하면 이 테스트가 실패한다. FE 는 별도로 자기 사본과 대조한다.
"""

import json
import unittest
from pathlib import Path

from app.domain.enums import (
    CreditTxType,
    ErrorCode,
    GenerationStatus,
    GenerationType,
    ProviderJobStatus,
    ProviderName,
)

_CONTRACT = Path(__file__).resolve().parents[1] / "contract" / "enums.json"


class TestContractEnums(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(_CONTRACT.read_text(encoding="utf-8"))

    def _values(self, enum_cls):
        return [m.value for m in enum_cls]

    def test_generation_status(self):
        self.assertEqual(self._values(GenerationStatus), self.data["GenerationStatus"])

    def test_generation_type(self):
        self.assertEqual(self._values(GenerationType), self.data["GenerationType"])

    def test_provider_name(self):
        self.assertEqual(self._values(ProviderName), self.data["ProviderName"])

    def test_provider_job_status(self):
        self.assertEqual(self._values(ProviderJobStatus), self.data["ProviderJobStatus"])

    def test_error_code(self):
        self.assertEqual(self._values(ErrorCode), self.data["ErrorCode"])

    def test_credit_tx_type(self):
        self.assertEqual(self._values(CreditTxType), self.data["CreditTxType"])

    def test_video_provider_subset(self):
        # VideoProviderName = ProviderName - {GEMINI}
        expected = [v for v in self.data["ProviderName"] if v != "GEMINI"]
        # 순서는 계약 파일 기준으로 별도 정의됨
        self.assertEqual(set(self.data["VideoProviderName"]), set(expected))


if __name__ == "__main__":
    unittest.main()
