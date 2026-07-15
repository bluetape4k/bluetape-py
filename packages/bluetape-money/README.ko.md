# bluetape-money

[English](README.md) | 한국어

표준 라이브러리만 사용하는 ISO 4217 currency와 정확한 `Decimal` money 값을
caller가 제공하는 exchange rate와 함께 제공합니다.

## 설치

PyPI 배포는 보류 중입니다. 목표 focused 및 meta-extra 설치 형태는 다음과 같습니다.

```bash
pip install bluetape-money
pip install "bluetape[money]"
```

기본 `bluetape` 설치에는 이 패키지가 포함되지 않습니다.

## 빠른 시작

<!-- value-example:start -->
```python
from decimal import ROUND_HALF_UP

from bluetape.money import EUR, USD, ExchangeRate, Money, convert

price = Money.of("12.345", USD)
assert price.quantize(rounding=ROUND_HALF_UP) == Money.of("12.35", USD)

rate = ExchangeRate.of(USD, EUR, "0.925")
euros = convert(price, rate)
assert euros == Money.of("11.419125", EUR)
assert convert(euros, rate) == price

try:
    Money.of(12.34, USD)
except TypeError:
    pass
else:
    raise AssertionError("binary floats must be rejected")
```
<!-- value-example:end -->

Amount와 rate는 bounded exact `Decimal`, integer, strict ASCII decimal
문자열만 받습니다. 모든 binary float와 boolean은 산술 전에 거부합니다. 연산은
package-local Decimal context를 사용하며 caller ambient precision을 변경하거나
상속하지 않습니다.

## ISO 4217 스냅샷

Currency metadata는 commit한 SIX ISO 4217 current List One snapshot에서 offline
생성합니다. 정확한 XML과 provenance manifest는
`docs/research/sources/iso4217/`에 있으며 `scripts/update-iso4217.py`가 명시적 local
input으로 Python table을 결정적으로 재생성합니다. Import, build, normal use는
network에 접근하지 않습니다. `XXX`와 `XTS`는 제외합니다.

## 반올림과 환율

산술은 자동으로 반올림하지 않습니다. `quantize()`와 `minor_units()`가 caller가
선택한 stdlib Decimal rounding을 포함한 minor-unit 정책을 명시합니다. Current ISO
row에 minor unit이 없는 currency는 이 연산을 거부합니다.

`ExchangeRate`는 caller가 제공하는 양의 exact base-to-quote 값입니다. `convert()`는
quantize하지 않고 양방향을 지원합니다. Package는 FX provider, freshness policy,
cache, retry, background task, I/O를 소유하지 않습니다.

## 버전 없는 스키마

정확한 primitive schema는 version과 extra key가 없는
`{"amount": str, "currency": str}`입니다. Canonical format은 fixed-point
`CODE amount`입니다. Symbol, locale rule, Unicode digit, whitespace drift, float,
unknown 또는 제외된 currency code를 거부합니다.

## 현재 데이터와 비역사성

Lookup은 commit한 current snapshot을 나타내며 historical tender나 jurisdiction
policy가 아닙니다. 새 package version에서 추가된 code는 rollback 뒤 읽지 못할 수
있습니다. Archival application은 package version을 pin하거나 historical currency
table을 직접 소유해야 합니다. `bluetape-money` 또는 `bluetape[money]`를 제거하기
전에 import를 중단하고 exact primitive value를 유지합니다.

## 보류 범위

Locale/CLDR formatting, accounting, tax, allocation, historical ISO code,
provider-backed FX는 보류합니다. Locale money와 FX provider는 data source,
freshness, cache, failure, lifecycle ownership을 정하는 별도 issue가 필요합니다.
