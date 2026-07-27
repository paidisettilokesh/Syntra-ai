from typing import Any, Callable, Dict, Type, TypeVar

from src.domain.exceptions import DependencyResolutionError, ServiceRegistrationError

T = TypeVar("T")


class Container:
    def __init__(self):
        self._services: Dict[Type, Dict[str, Any]] = {}

    def register_singleton(
        self,
        interface: Type[T],
        implementation: Type[T] = None,
        instance: T = None,
        factory: Callable[[], T] = None,
    ):
        if interface in self._services:
            raise ServiceRegistrationError(f"Service {interface.__name__} is already registered.")

        self._services[interface] = {
            "type": "singleton",
            "implementation": implementation,
            "instance": instance,
            "factory": factory,
        }

    def register_transient(
        self, interface: Type[T], implementation: Type[T] = None, factory: Callable[[], T] = None
    ):
        if interface in self._services:
            raise ServiceRegistrationError(f"Service {interface.__name__} is already registered.")

        self._services[interface] = {
            "type": "transient",
            "implementation": implementation,
            "factory": factory,
        }

    def resolve(self, interface: Type[T]) -> T:
        if interface not in self._services:
            raise DependencyResolutionError(f"Service {interface.__name__} is not registered.")

        registration = self._services[interface]

        if registration["type"] == "singleton":
            if registration["instance"] is None:
                if registration["factory"]:
                    registration["instance"] = registration["factory"]()
                elif registration["implementation"]:
                    registration["instance"] = self._build(registration["implementation"])
                else:
                    raise DependencyResolutionError(
                        f"Cannot resolve singleton {interface.__name__}"
                    )
            return registration["instance"]

        elif registration["type"] == "transient":
            if registration["factory"]:
                return registration["factory"]()
            elif registration["implementation"]:
                return self._build(registration["implementation"])
            else:
                raise DependencyResolutionError(f"Cannot resolve transient {interface.__name__}")

    def _build(self, implementation: Type[T]) -> T:
        import inspect

        if implementation.__init__ is object.__init__:
            return implementation()

        signature = inspect.signature(implementation.__init__)
        params = signature.parameters

        dependencies = {}
        for name, param in params.items():
            if name == "self":
                continue
            if param.annotation == inspect.Parameter.empty:
                raise DependencyResolutionError(
                    f"Parameter '{name}' in {implementation.__name__} lacks type annotation."
                )

            # Recursively resolve dependency
            dependencies[name] = self.resolve(param.annotation)

        return implementation(**dependencies)


container = Container()
