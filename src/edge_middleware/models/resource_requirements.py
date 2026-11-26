"""Static resource requirements and reference compute cost for a task."""

from collections.abc import Collection, Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResourceRequirements:
    """CPU capacity in millicores, RAM in bytes, and reference compute time in ms."""

    min_cpu_millicores: int
    min_ram_bytes: int
    estimated_compute_ms: int
    required_capabilities: Collection[str] = frozenset()

    def __post_init__(self) -> None:
        for name, value in (
            ("min_cpu_millicores", self.min_cpu_millicores),
            ("min_ram_bytes", self.min_ram_bytes),
            ("estimated_compute_ms", self.estimated_compute_ms),
        ):
            if type(value) is not int:
                raise TypeError(f"{name} must be an int")
            if value <= 0:
                raise ValueError(f"{name} must be positive")

        capabilities = self.required_capabilities
        if not isinstance(capabilities, Collection) or isinstance(
            capabilities, (str, bytes, bytearray, Mapping)
        ):
            raise TypeError("required_capabilities must be a collection of identifiers")
        identifiers = tuple(capabilities)
        for identifier in identifiers:
            if type(identifier) is not str:
                raise TypeError("capability identifiers must be strings")
            if not identifier.strip():
                raise ValueError("capability identifiers must not be blank")
        object.__setattr__(self, "required_capabilities", frozenset(identifiers))
