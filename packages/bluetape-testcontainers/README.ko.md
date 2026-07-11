# bluetape-testcontainers

[English](README.md) | 한국어

`bluetape-testcontainers`는 bluetape Python 생태계의 Docker 기반 테스트 서버
경계를 관리합니다. 프로덕션 Redis client 패키지가 아니라 테스트 인프라입니다.

## 설치

현재 PyPI 배포는 보류 중입니다. 배포가 시작된 뒤의 설치 형태는 다음과 같습니다.

```bash
pip install "bluetape[testcontainers]"
# 또는
pip install bluetape-testcontainers
```

기본 `bluetape` 설치에는 provider가 추가되지 않습니다. Testcontainers와 Docker
SDK는 명시적인 extra나 목적별 패키지를 설치할 때만 들어옵니다. 이 래퍼는
redis-py에 의존하지 않습니다.

## Redis

```python
from bluetape.testcontainers import RedisServer

with RedisServer() as redis:
    configure_test(redis_url=redis.url)
```

- 기본 image: `redis:8`
- 동적으로 매핑한 host port만 사용
- 명시적인 `start()`/`close()` 또는 context manager가 수명주기를 소유
- `startup_timeout` 안에서 image pull과 `redis-cli ping` readiness를 수행
- Docker 기반 test suite는 직렬 실행
- tag나 digest를 지정한 image override는 허용하지만 `latest`는 거절

객체를 생성할 때는 Docker에 접근하지 않습니다. `start()`가 성공하면 `close()`를
호출할 때까지 `host`, `port`, `url`, 불변 `details`에서 매핑된 endpoint를 읽을 수
있습니다. 같은 객체가 실행 중일 때 `start()`를 다시 호출하는 것은 안전하지만,
닫은 객체를 다시 시작할 수는 없습니다.

Container termination에 실패하면 래퍼가 container 참조를 유지합니다. `close()`를
다시 호출하면 정리를 재시도하며, termination에 성공한 뒤부터 no-op으로 동작합니다.

시작에 실패하면 `TestcontainerStartError`가 안정적인 `StartFailureKind` 하나를
제공합니다. 종류는 `runtime-unavailable`, `image-pull`, `readiness-timeout`,
`wrapper-failure`입니다. Provider 진단 정보는 공개 오류 문자열에 넣지 않고
exception cause에 보존합니다.

Docker 기반 테스트에는 Docker-compatible runtime이 필요하며 직렬로 실행해야 합니다.

```bash
uv run pytest -m testcontainers packages/bluetape-testcontainers -q
```
