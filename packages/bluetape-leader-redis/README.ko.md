# bluetape-leader-redis

[English](README.md) | 한국어

`bluetape-leader-redis`는 `bluetape-leader`를 위한 opt-in Redis adapter 패키지
경계를 예약합니다.

현재 패키지는 Redis adapter namespace만 예약합니다.
Redis lock과 leader 동작은 아직 구현하지 않았습니다. 이 placeholder를 coordination
또는 소유권 판단에 사용하면 안 됩니다.

PyPI 공개는 보류 상태입니다. 향후 전용 배포본과 meta extra의 설치 형태는 다음과
같습니다.

```bash
pip install bluetape-leader-redis
pip install "bluetape[leader-redis]"
```

이 배포본의 runtime dependency는 `bluetape-leader==0.1.0`과 `redis==8.0.1`뿐입니다.
기본, `dev`, `all` meta 설치에는 포함하지 않습니다.
