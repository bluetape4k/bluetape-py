# Issue #57 Testcontainers Redis Wrapper 교훈

## 배경

Issue #57에서는 `bluetape-testcontainers`에 집중한 distribution과 ecosystem이
소유하는 Redis 8 test server를 추가했다. 어려운 경계는 Redis를 시작하는 일이
아니라, 모든 숨은 provider 단계가 public timeout, diagnostic, cleanup contract를
따르도록 하면서 default `bluetape` install은 provider-free로 유지하는 일이었다.

## 결정 사항

- Redis module이 아니라 Testcontainers core `DockerContainer`를 기반으로 한다. 이를
  통해 ecosystem이 `redis:8` compatibility line, readiness command, dynamic port,
  connection detail을 소유하면서 redis-py를 추가하지 않는다.
- 먼저 local image를 확인하고, image가 없으면 bounded child process에서 pull한다.
  Docker SDK `images.pull()`은 client 주변에 timeout이 있어도 unbounded request
  path를 hardcode한다.
- 이 wrapper에서는 Testcontainers Ryuk을 건너뛴다. Ryuk은 `startup_timeout` 바깥에서
  별도의 image acquisition과 connection loop를 수행한다. 대신 bounded Docker
  client로 core container를 시작하고, label을 지정하며, 명시적인 cleanup을 소유한다.
- `from None`으로 provider exception chaining을 억제한다. redacted public message만
  제공하는 것으로는 부족하다. chained traceback이 daemon path, registry response,
  credential을 여전히 노출할 수 있다.
- termination failure 뒤에도 container reference를 유지한다. startup과
  context-manager cleanup 경로 모두 caller에게 `close()` 재시도를 안내한다.
- Docker 기반 verification은 직렬로 실행하고, provider-free default wheel smoke
  test와 분리한다.

## 결과와 증거

- Unit test가 validation, lifecycle transition, cleanup retry, provider redaction,
  bounded pull, no-Ryuk startup, IPv6 URL, package isolation을 다룬다.
- 실제 Docker test가 Redis 8 server 두 개를 순차적으로 시작하고 RESP
  `PING`/`SET`/`GET`을 수행해 lifecycle 사이에 stale state가 교차하지 않음을 증명한다.
- 확인된 local compatibility image는
  `redis@sha256:2838d5524559494f6f1cd66e97e76b200d64a633a8614200620755ed395daf32`다.
- Full-suite, Ruff, all-package build, workflow lint, diff hygiene, isolated
  default-wheel check가 verifier artifact에 기록되어 있다.

## 검토에서 놓친 점과 향후 보호 장치

- provider startup code는 처음부터 끝까지 읽어야 한다. public `start()` method가
  요청한 resource보다 먼저 support container를 초기화하면 wrapper 수준의 timeout
  주장이 무효가 될 수 있다.
- 여러 distribution의 test package 이름은 workspace에서 충돌할 수 있다. top-level
  `tests` package를 여러 개 두는 대신 고유한 nested test package를 사용한다.
- dynamic connection URL은 IPv6 authority를 bracket으로 감싸야 한다.
- `:`나 `@sha256:`의 존재만 확인하지 말고 tag와 digest가 비어 있지 않은지 검증한다.
- bounded start path에서 사용하는 private attribute를 포함해 container configuration
  contract test를 provider upgrade와 함께 동기화한다.
- README example은 직접 실행 가능해야 하며, pytest fixture ownership을 명시적으로
  설명한다. 어떤 resource scope도 자동으로 선택하는 plugin을 조용히 허용하지 않는다.
