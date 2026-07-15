# Issue #13 Value Package Delivery Lessons

## Context and decision

ID, 측정값, 금액은 모두 작은 값 객체처럼 보이지만 실패 경계가 다르다. ID는 clock/entropy와
정렬 단조성, 측정값은 dimension/registry, 금액은 Decimal/ISO snapshot/rounding policy가 핵심이다.
세 패키지를 하나의 공통 추상화로 묶지 않고 stdlib-only 독립 배포판으로 유지하며, meta package는
opt-in extra만 제공하고 기본 설치는 계속 `bluetape-core`만 의존하도록 결정했다.

## Reusable findings

### 값 객체의 작은 API보다 caller-owned policy를 먼저 고정한다

UUIDv7과 ULID 생성기는 clock과 entropy를 주입받고, measure 역직렬화는 unit registry를 호출자가
제공하며, money exchange와 quantize는 rate와 rounding mode를 호출자가 전달한다. 이 경계를 먼저
고정하면 숨은 thread, scheduler, network fetch, global registry, locale, ambient Decimal context가
패키지 계약으로 침투하는 것을 막을 수 있다.

### 표준 데이터는 런타임 네트워크가 아니라 재현 가능한 source artifact다

ISO 4217은 현재 snapshot이며 역사적 통화 원장이나 환율 서비스가 아니다. 고정 fixture로 generator를
검증하고 생성 결과의 byte identity를 확인하면, production import는 네트워크 없이 결정적이고 변경은
review 가능한 source diff가 된다. 최신성은 자동 background refresh가 아니라 명시적 snapshot 갱신
작업으로 관리해야 한다.

Canonical URL을 사용한 생성은 단순히 XML well-formed 여부만 검사해서는 안 된다. 빈 테이블,
필수 국가명 누락, 중첩 element, 예상 밖 attribute를 거부하고, 현재 snapshot 280 rows/178 currencies에
대해 보수적인 하한 250/150을 적용해야 잘린 응답을 정상 current table로 오인하지 않는다. Full source
재생성 결과와 committed module의 byte identity까지 묶어야 provenance가 실제 output을 증명한다.

다운로드 원문의 SHA-256을 provenance로 보존할 때 Git text normalization도 데이터 파이프라인의
일부다. CRLF 원본을 일반 text로 add하면 maintainer worktree와 Linux checkout의 blob bytes가 달라질
수 있다. Raw digest가 계약이면 해당 source family를 `.gitattributes`의 `binary`로 고정하고,
worktree bytes와 Git index bytes가 같은지 CI에서 직접 검사해야 한다.

### bounded Decimal과 exact Decimal은 다른 계약이다

precision 256 context에서 결과가 256 digits 이내라는 사실은 입력의 정확한 값이 보존됐다는 뜻이
아니다. `Inexact`와 `Rounded`를 trap하지 않으면 200-digit 곱셈, 1/3 나눗셈, FX, 누적 합계가 조용히
반올림된다. 일반 산술은 두 signal을 차단하고, caller가 rounding mode를 명시한 `quantize()` 경로만
국소적으로 허용해야 한다.

### Python namespace package의 격리는 wheel에서 증명한다

source checkout import만으로는 sibling package 누출과 root `bluetape/__init__.py` 생성을 발견하기
어렵다. 각 focused wheel, 개별 meta extra, aggregate extra, dev/all, default를 별도 Python 3.13.14
환경에 offline/no-index/no-deps로 설치하고 module origin과 부재를 확인해야 실제 배포 경계를 증명할
수 있다. 기본 meta 환경에서는 세 value module이 모두 없어야 한다.

### 비패키지 test directory의 module 이름은 workspace 전역 계약이다

서로 다른 package 아래의 `test_parse.py`와 `test_serialization.py`도 한 pytest process에서는 같은
top-level module 이름으로 충돌한다. package별 focused test가 통과해도 full-workspace collection에서만
드러난다. 새 workspace package의 test basename은 package-specific하게 만들고, 새 배포판은 기존의
모든 fail-closed release classifier에 동시에 등록해야 한다.

### README 예제는 built wheel 밖에서 실행한다

문서 코드가 source tree의 우연한 import path에 기대지 않도록 EN/KO 예제를 동일한 marker로 추출하고,
세 wheel을 격리 환경에 설치한 뒤 checkout 밖에서 `python -I`로 실행했다. 이 방식은 번역 동기화,
공개 export, packaging, 빠른 시작 코드가 하나의 계약으로 유지되게 한다.

## Verification evidence

- ID 15개, measure 18개, money 85개, meta/docs 6개 targeted test가 통과했다.
- PR portability repair 후 CI-shaped workspace는 `1711 passed, 139 deselected`로 통과했다.
- 18개 배포판 build와 10개 격리 환경 value-wheel verifier가 통과했다.
- Ruff, format, actionlint, diff hygiene, SVG/PNG 감사가 통과했다.
- 세 독립 구현 재검토는 최종 `P0=0, P1=0, P2=0`으로 수렴했다.

## Future guard

새 value package나 공개 값 타입을 추가할 때 stdlib-only 경계, caller-owned policy, primitive
serialization schema, persistence/rollback 문구, package-specific test module 이름, 모든 release
classifier, focused/default wheel absence, EN/KO installed-wheel example을 함께 갱신한다. 숨은 전역 상태,
런타임 network refresh, implicit conversion, 자동 환율/locale 정책이 필요해지면 기존 값 패키지에
추가하지 말고 별도 opt-in 경계로 재설계한다.
