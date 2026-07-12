# bluetape-cache-redis

[English](README.md) | 한국어

bluetape-py용 Python 3.13+ 선택형 Redis 바이트 provider와 크기 제한 result envelope 계약을
제공합니다. 애플리케이션 직렬화와 압축 정책은 호출자가 소유하며 기본 `bluetape` 설치에는
포함되지 않습니다.

```bash
pip install "bluetape[cache-redis]"
```

안정 공개 API에는 구조적 payload/format 계약, 불변 result envelope, 민감정보를 제거한 provider
오류, 동등한 동기/비동기 바이트 연산이 포함됩니다. 전체 사용법과 운영 지침은 구현 검증 후
확장합니다.

