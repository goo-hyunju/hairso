"""상태 전이 규칙 테스트 — stdlib unittest(오프라인 통과)."""

import unittest

from app.domain.enums import GenerationStatus as S
from app.domain.enums import GenerationType
from app.domain.errors import InvalidStateTransition
from app.domain.state_machine import assert_transition, can_transition, is_terminal


class TestStateMachine(unittest.TestCase):
    def test_video_forward_chain(self):
        v = GenerationType.VIDEO
        self.assertTrue(can_transition(v, S.CREATED, S.SUBMITTED))
        self.assertTrue(can_transition(v, S.SUBMITTED, S.QUEUED))
        self.assertTrue(can_transition(v, S.QUEUED, S.PROCESSING))
        self.assertTrue(can_transition(v, S.PROCESSING, S.POST_PROCESSING))
        self.assertTrue(can_transition(v, S.POST_PROCESSING, S.SUCCEEDED))
        self.assertTrue(can_transition(v, S.SUCCEEDED, S.EXPIRED))

    def test_image_has_no_post_processing(self):
        i = GenerationType.IMAGE
        # 이미지는 PROCESSING -> SUCCEEDED 직행, POST_PROCESSING 없음
        self.assertTrue(can_transition(i, S.PROCESSING, S.SUCCEEDED))
        self.assertFalse(can_transition(i, S.PROCESSING, S.POST_PROCESSING))

    def test_succeeded_not_reverted_by_late_processing(self):
        # 규칙 §4.16: SUCCEEDED 를 늦은 PROCESSING webhook 으로 되돌리지 않는다.
        for t in (GenerationType.IMAGE, GenerationType.VIDEO):
            self.assertFalse(can_transition(t, S.SUCCEEDED, S.PROCESSING))

    def test_terminal_has_no_outgoing(self):
        for t in (GenerationType.IMAGE, GenerationType.VIDEO):
            for term in (S.FAILED, S.CANCELED, S.EXPIRED):
                self.assertTrue(is_terminal(term))
                for target in S:
                    if target is S.EXPIRED and term is S.SUCCEEDED:
                        continue
                    self.assertFalse(can_transition(t, term, target))

    def test_same_state_is_not_a_valid_transition(self):
        # 자기 자신으로의 전이는 allowed set 에 없다 -> Service 가 no-op 로 처리해야 함
        self.assertFalse(can_transition(GenerationType.VIDEO, S.PROCESSING, S.PROCESSING))

    def test_assert_transition_raises_on_illegal(self):
        with self.assertRaises(InvalidStateTransition):
            assert_transition(GenerationType.VIDEO, S.SUCCEEDED, S.PROCESSING)

    def test_provider_can_skip_intermediate_states(self):
        # 결함#1 회귀: provider 가 PROCESSING 을 건너뛰고 완료를 알려도 정체되지 않아야 한다.
        # VIDEO: provider SUCCEEDED -> POST_PROCESSING 매핑 → SUBMITTED/QUEUED 에서 도달 가능해야 함.
        self.assertTrue(can_transition(GenerationType.VIDEO, S.SUBMITTED, S.POST_PROCESSING))
        self.assertTrue(can_transition(GenerationType.VIDEO, S.QUEUED, S.POST_PROCESSING))
        # IMAGE: provider SUCCEEDED -> SUCCEEDED → SUBMITTED/QUEUED 에서 직행 가능해야 함.
        self.assertTrue(can_transition(GenerationType.IMAGE, S.SUBMITTED, S.SUCCEEDED))
        self.assertTrue(can_transition(GenerationType.IMAGE, S.QUEUED, S.SUCCEEDED))
        # 단 IMAGE 는 여전히 POST_PROCESSING 에 도달하지 않는다.
        self.assertFalse(can_transition(GenerationType.IMAGE, S.SUBMITTED, S.POST_PROCESSING))


if __name__ == "__main__":
    unittest.main()
