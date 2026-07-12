# bluetape-compression

[English](README.md) | 한국어

백엔드 Python 코드에서 사용할 수 있는 immutable byte compressor 계약과 제한된
압축 해제 기능을 제공합니다.

현재 `bluetape-compression`은 source workspace에서 사용할 수 있습니다. PyPI
배포는 보류 중이므로 아래 명령은 배포가 활성화된 뒤의 설치 형태를 설명합니다.

## 설치

기본 패키지는 Python 빌드에 포함된 선택적 표준 라이브러리 `zlib`만 사용하며
gzip, zlib-wrapped, raw-DEFLATE codec을 제공합니다. Native provider는 필요한
알고리즘만 extra로 설치합니다.

```bash
pip install bluetape-compression
pip install "bluetape-compression[lz4]"
pip install "bluetape-compression[snappy]"
pip install "bluetape-compression[zstd]"
pip install "bluetape-compression[native]"  # native provider 3종 모두 설치
```

`bluetape` 메타 배포 패키지에서도 `compression`, `compression-lz4`,
`compression-snappy`, `compression-zstd`, `compression-native` extra를 같은
용도로 제공합니다. Native provider는 기본 설치와 `dev`, `all` extra에 들어가지
않습니다.

로컬 workspace에서는 다음 명령을 사용합니다.

```bash
uv sync --package bluetape-compression --extra native --locked
```

## Compressor 계약

`Compressor`는 상속을 요구하지 않는 `typing.Protocol`입니다. 같은 property와
method를 구현한 객체라면 패키지의 base class를 상속하지 않아도 호출자에게
주입할 수 있습니다.

```python
from bluetape.compression import Compressor, GzipCompressor


def roundtrip(compressor: Compressor, source: bytes) -> bytes:
    return compressor.decompress(compressor.compress(source))


assert roundtrip(GzipCompressor(), b"order:42") == b"order:42"
```

패키지가 제공하는 구현은 모두 frozen, slotted dataclass입니다. 각 구현은 고정된
`algorithm` ID를 제공하고 `bytes`, `bytearray`, `memoryview`를 받아 `bytes`를
반환하며, 압축을 풀 때 `max_output_size`를 지킵니다.

| Class | Algorithm ID | Format | Level |
|---|---|---|---|
| `GzipCompressor` | `gzip` | 완전한 gzip member | `-1..9`, 기본값 `9` |
| `ZlibCompressor` | `zlib` | 하나의 zlib-wrapped stream | `-1..9`, 기본값 `-1` |
| `DeflateCompressor` | `deflate` | 하나의 raw DEFLATE stream | `-1..9`, 기본값 `-1` |
| `Lz4Compressor` | `lz4-frame` | content size와 checksum을 포함한 완전한 LZ4 frame | `0..16`, 기본값 `0` |
| `SnappyCompressor` | `snappy-raw` | Raw Snappy block | provider 고정값 |
| `ZstdCompressor` | `zstd-frame` | content size와 checksum을 포함한 완전한 Zstandard frame | `1..22`, 기본값 `3` |

Native 구현은 `bluetape.compression.native`에서 import합니다.

```python
from bluetape.compression.native import Lz4Compressor, SnappyCompressor, ZstdCompressor

compressor = ZstdCompressor(level=3, max_output_size=8 * 1024 * 1024)
encoded = compressor.compress(b"redis-value")
assert compressor.decompress(encoded) == b"redis-value"
```

Provider를 설치하지 않아도 native namespace 자체는 import할 수 있습니다. 다만
해당 extra 없이 native compressor를 생성하면 정확한 설치 방법을 담은
`CompressionError`가 발생합니다.

## 함수와 실패 규칙

기존 `gzip_*`, `zlib_*`, `deflate_*` 함수도 계속 공개합니다. 표준 라이브러리
compressor class가 이 함수를 호출하므로 기존 동작을 유지합니다.

- 모든 compressor는 빈 입력을 roundtrip할 수 있습니다.
- 별도 값을 지정하지 않으면 압축 해제 결과는 `DEFAULT_MAX_OUTPUT_SIZE`(64 MiB)를
  넘지 않습니다. 호출자는 0 이상의 다른 한도를 지정할 수 있습니다.
- 올바르지 않거나 잘렸거나 크기가 맞지 않거나 뒤에 데이터가 붙은 payload는
  `CompressionError`를 발생시킵니다. 결과가 한도를 넘으면
  `DecompressionLimitError`가 발생합니다.
- Gzip은 완전한 member 여러 개를 이어 붙인 입력을 허용합니다. 나머지 format은
  하나의 완전한 payload만 허용하며 trailing data를 거부합니다.
- 오류 메시지에 압축 payload를 넣지 않으며, 패키지가 호출자 데이터를 log로
  남기지 않습니다.
- 이 한도는 반환할 논리 payload 크기를 제한할 뿐 process 전체 메모리의 hard
  ceiling은 아닙니다. 호출자는 이미 압축 입력을 소유하고, 성공한 method는 완전한
  `bytes`를 반환합니다.

## Redis payload 조합

압축은 serialization과 Redis 전송에서 분리되어 있습니다.

```text
value -> serialize -> compress -> Redis bytes
Redis bytes -> decompress -> deserialize -> value
```

Serializer schema와 compressor 설정은 application configuration에서 고정해야
하며, 신뢰할 수 없는 payload byte를 보고 자동 선택하면 안 됩니다. Python API는
다른 bluetape 언어 구현과 기능 및 실패 규칙의 의미를 맞추지만, 언어 간 wire
호환은 약속하지 않습니다.

## 범위 밖

- Streaming, file/path, registry, auto-detection API.
- Encryption 또는 serializer/compressor 자동 협상.
- 이번 변경에서의 PyPI 배포.
