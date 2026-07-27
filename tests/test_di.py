import pytest

from src.domain.exceptions import DependencyResolutionError, ServiceRegistrationError
from src.utils.di import Container


class IService:
    def do_work(self):
        pass


class MyService(IService):
    def do_work(self):
        return "work"


class DependingService:
    def __init__(self, service: IService):
        self.service = service


def test_singleton_registration():
    container = Container()
    container.register_singleton(IService, implementation=MyService)

    instance1 = container.resolve(IService)
    instance2 = container.resolve(IService)

    assert instance1 is instance2
    assert isinstance(instance1, MyService)


def test_transient_registration():
    container = Container()
    container.register_transient(IService, implementation=MyService)

    instance1 = container.resolve(IService)
    instance2 = container.resolve(IService)

    assert instance1 is not instance2
    assert isinstance(instance1, MyService)


def test_dependency_resolution():
    container = Container()
    container.register_singleton(IService, implementation=MyService)
    container.register_transient(DependingService, implementation=DependingService)

    depending = container.resolve(DependingService)
    assert isinstance(depending.service, MyService)


def test_missing_dependency():
    container = Container()
    with pytest.raises(DependencyResolutionError):
        container.resolve(IService)


def test_duplicate_singleton_registration():
    container = Container()
    container.register_singleton(IService, implementation=MyService)
    with pytest.raises(ServiceRegistrationError):
        container.register_singleton(IService, implementation=MyService)


def test_duplicate_transient_registration():
    container = Container()
    container.register_transient(IService, implementation=MyService)
    with pytest.raises(ServiceRegistrationError):
        container.register_transient(IService, implementation=MyService)


def test_singleton_factory_resolution():
    container = Container()
    container.register_singleton(IService, factory=lambda: MyService())
    inst1 = container.resolve(IService)
    inst2 = container.resolve(IService)
    assert inst1 is inst2
    assert inst1.do_work() == "work"


def test_transient_factory_resolution():
    container = Container()
    container.register_transient(IService, factory=lambda: MyService())
    inst1 = container.resolve(IService)
    inst2 = container.resolve(IService)
    assert inst1 is not inst2
    assert inst1.do_work() == "work"


def test_missing_annotation_resolution():
    class UnannotatedService:
        def __init__(self, some_dependency):
            self.dep = some_dependency

    container = Container()
    container.register_transient(UnannotatedService, implementation=UnannotatedService)
    with pytest.raises(DependencyResolutionError) as exc_info:
        container.resolve(UnannotatedService)
    assert "lacks type annotation" in str(exc_info.value)


def test_cannot_resolve_singleton_without_binding():
    container = Container()
    # Force injection registration dictionary without impl/factory
    container._services[IService] = {
        "type": "singleton",
        "implementation": None,
        "instance": None,
        "factory": None,
    }
    with pytest.raises(DependencyResolutionError):
        container.resolve(IService)


def test_cannot_resolve_transient_without_binding():
    container = Container()
    container._services[IService] = {"type": "transient", "implementation": None, "factory": None}
    with pytest.raises(DependencyResolutionError):
        container.resolve(IService)
