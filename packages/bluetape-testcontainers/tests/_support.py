from dataclasses import dataclass, field


@dataclass
class FakeContainer:
    host: str = "127.0.0.1"
    mapped_port: int = 46379
    start_error: BaseException | None = None
    stop_error: Exception | None = None
    starts: int = 0
    stops: int = 0

    def start(self) -> "FakeContainer":
        self.starts += 1
        if self.start_error is not None:
            raise self.start_error
        return self

    def stop(self) -> None:
        self.stops += 1
        if self.stop_error is not None:
            raise self.stop_error

    def get_container_host_ip(self) -> str:
        return self.host

    def get_exposed_port(self, port: int) -> int:
        assert port == 6379
        return self.mapped_port


@dataclass
class ContainerFactory:
    container: FakeContainer
    calls: list[tuple[str, float]] = field(default_factory=list)

    def __call__(self, image: str, startup_timeout: float) -> FakeContainer:
        self.calls.append((image, startup_timeout))
        return self.container
