"""ProviderJobStatus -> 내부 GenerationStatus 매핑 테스트."""

import unittest

from app.domain.enums import GenerationStatus as S
from app.domain.enums import GenerationType, ProviderJobStatus
from app.domain.status_mapping import map_provider_status


class TestStatusMapping(unittest.TestCase):
    def test_video_succeeded_maps_to_post_processing(self):
        # 영상: provider 완료여도 내부는 POST_PROCESSING(후처리 대기), SUCCEEDED 아님
        self.assertEqual(
            map_provider_status(GenerationType.VIDEO, ProviderJobStatus.SUCCEEDED),
            S.POST_PROCESSING,
        )

    def test_image_succeeded_maps_to_succeeded(self):
        # 이미지: 후처리 없음 -> 직행 SUCCEEDED
        self.assertEqual(
            map_provider_status(GenerationType.IMAGE, ProviderJobStatus.SUCCEEDED),
            S.SUCCEEDED,
        )

    def test_pending_maps_to_queued(self):
        for t in (GenerationType.IMAGE, GenerationType.VIDEO):
            self.assertEqual(
                map_provider_status(t, ProviderJobStatus.PENDING), S.QUEUED
            )

    def test_all_provider_statuses_have_mapping(self):
        for t in (GenerationType.IMAGE, GenerationType.VIDEO):
            for ps in ProviderJobStatus:
                self.assertIsInstance(map_provider_status(t, ps), S)


if __name__ == "__main__":
    unittest.main()
