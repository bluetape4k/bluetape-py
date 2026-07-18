# bluetape-leader

[English](README.md) | 한국어

`bluetape-leader`는 향후 leader election과 distributed lock 계약을 위한 표준
라이브러리 전용 backend-neutral 패키지 경계를 예약합니다.

현재 공개 표면은 값이 노출되지 않는 leader 오류 계약만 포함합니다.
옵션, lease, elector, lock 동작은 아직 구현하지 않았습니다. 이 패키지는 동작하는
coordination library가 아니라 계약 미리보기로 사용해야 합니다.

PyPI 공개는 보류 상태입니다. 향후 전용 배포본과 meta extra의 설치 형태는 다음과
같습니다.

```bash
pip install bluetape-leader
pip install "bluetape[leader]"
```

Redis 지원은 opt-in `bluetape-leader-redis` 배포본으로 분리합니다. 기본
`bluetape` 설치는 계속 core-only입니다.
