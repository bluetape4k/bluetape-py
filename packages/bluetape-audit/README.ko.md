# bluetape-audit

Python 네이티브 bluetape 애플리케이션을 위한 저장소 독립적인 감사 이벤트
계약 패키지입니다.

전용 배포본은 다음과 같이 설치합니다.

```bash
pip install bluetape-audit
```

얇은 메타 배포본의 audit extra로도 설치할 수 있습니다.

```bash
pip install "bluetape[audit]"
```

현재 제공하는 오류 경계는 `bluetape.audit`에서 가져옵니다. 이 패키지는 런타임
의존성이 없으며 저장소, 전송, 로깅, 백그라운드 워커 또는 루트 `bluetape`
편의 모듈을 제공하지 않습니다.
