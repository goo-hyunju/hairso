"""0단계 PoC — 이 GPU(RTX 5060 Ti / Blackwell sm_120)에서 PyTorch CUDA 가 실제로 동작하는지 검증.

로컬 이미지 생성(경로 A)의 전제조건. 여기서 실패하면(=cu128 미지원/커널 없음)
모델 다운로드 이전에 런타임 문제를 먼저 해결해야 한다.
성공 기준: cuda 사용가능 + GPU 텐서 연산 + 결과가 CPU 계산과 일치.
"""

from __future__ import annotations

import sys

import torch


def main() -> int:
    print(f"torch      : {torch.__version__}")
    print(f"cuda build : {torch.version.cuda}")
    print(f"available  : {torch.cuda.is_available()}")
    if not torch.cuda.is_available():
        print("FAIL: CUDA 사용 불가 — cu128 휠/드라이버 확인 필요")
        return 1

    dev = torch.device("cuda:0")
    print(f"device     : {torch.cuda.get_device_name(0)}")
    cap = torch.cuda.get_device_capability(0)
    print(f"capability : sm_{cap[0]}{cap[1]}")  # Blackwell = sm_120

    # 실제 GPU 커널이 도는지 — 행렬곱을 GPU 에서 계산해 CPU 결과와 대조.
    a = torch.randn(1024, 1024, device=dev)
    b = torch.randn(1024, 1024, device=dev)
    c = a @ b
    torch.cuda.synchronize()
    ref = a.cpu() @ b.cpu()
    ok = torch.allclose(c.cpu(), ref, atol=1e-2)
    free, total = torch.cuda.mem_get_info(dev)
    print(f"vram       : {total / 1e9:.1f}GB total / {free / 1e9:.1f}GB free")
    print(f"matmul ok  : {ok}")
    if not ok:
        print("FAIL: GPU 연산 결과가 CPU 와 불일치 — 커널 문제 가능")
        return 1
    print("PASS: 이 GPU 에서 PyTorch CUDA 정상 동작")
    return 0


if __name__ == "__main__":
    sys.exit(main())
