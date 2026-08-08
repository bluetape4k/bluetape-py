# bluetape-measure

[English](README.md) | 한국어

표준 라이브러리만 사용하며 런타임 dimension을 검사하는 불변 선형 측정값입니다.

## 설치

PyPI 배포는 보류 중입니다. 목표 집중 패키지 및 meta extra 설치 형태는 다음과 같습니다.

```bash
pip install bluetape-measure
pip install "bluetape[measure]"
```

기본 `bluetape` 설치에는 이 패키지가 포함되지 않습니다.

## 빠른 시작

<!-- value-example:start -->
```python
from bluetape.measure import KILOMETER, METER, Dimension, Measure, Unit, parse_measure

distance = Measure(1.25, KILOMETER)
assert distance.to(METER) == Measure(1250, METER)
assert parse_measure("1250 m").equivalent_to(distance)

smoot = Unit("smoot", "smoot", Dimension.LENGTH, 1.7018)
custom = Measure.from_dict({"amount": "2.0", "unit": "smoot"}, units=[smoot])
assert custom == Measure(2, smoot)
```
<!-- value-example:end -->

기본 제공 집합은 meter, kilometer, centimeter, millimeter, second, millisecond,
minute, hour, gram, kilogram입니다. 산술은 같은 runtime `Dimension` 안에서만
변환하며 호환되지 않는 dimension은 명시적으로 실패합니다.

## 사용자 정의 단위

`Unit`은 불변이며 dimension base unit에 대한 양의 선형 비율을 설명합니다.
애플리케이션이 custom unit 정의를 소유하고 동일한 bounded, duplicate-free unit
iterable을 `parse_measure()` 또는 `Measure.from_dict()`에 전달합니다. Mutable global
registry와 unit-definition file loader는 없습니다.

## 버전 없는 스키마

정확한 primitive schema는 version field와 extra key가 없는
`{"amount": str, "unit": str}`입니다. Deserialization은 caller가 전달한 unit
iterable에서만 symbol을 해석합니다. Amount는 strict ASCII finite-number grammar를
사용하며 Unicode digit, boolean, NaN, infinity, surrounding whitespace를 거부합니다.

## 영속성과 롤백

정확한 두 key primitive schema를 저장하고 custom unit 정의를 application
configuration과 함께 유지합니다. `bluetape-measure` 또는 `bluetape[measure]`를
제거하기 전에 import를 중단하고 schema와 unit 정의를 보존합니다. Rollback 후에도
application이 같은 불변 정의를 제공해야 custom 값을 읽을 수 있습니다.

## 보류 범위

복합 단위, dimensional-expression parsing, affine temperature conversion,
currency value, locale formatting, arbitrary numeric protocol, global registry는
보류합니다. 실제 compound 또는 temperature consumer가 생기면 별도 issue로
설계합니다.
