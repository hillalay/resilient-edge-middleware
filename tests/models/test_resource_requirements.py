from dataclasses import FrozenInstanceError, replace

import pytest

from edge_middleware.models.resource_requirements import ResourceRequirements


def test_resource_units_and_immutable_capabilities():
    capabilities = ["gpu", "avx2", "gpu"]
    resources = ResourceRequirements(250, 128 * 1024**2, 1500, capabilities)

    capabilities.clear()

    assert resources.min_cpu_millicores == 250
    assert resources.min_ram_bytes == 134_217_728
    assert resources.estimated_compute_ms == 1500
    assert resources.required_capabilities == frozenset({"gpu", "avx2"})
    assert type(resources.required_capabilities) is frozenset
    assert ResourceRequirements(1, 1, 1).required_capabilities == frozenset()
    with pytest.raises(FrozenInstanceError):
        resources.min_ram_bytes = 1


@pytest.mark.parametrize(
    "field", ["min_cpu_millicores", "min_ram_bytes", "estimated_compute_ms"]
)
@pytest.mark.parametrize("value", [0, -1])
def test_rejects_nonpositive_resource_values(field, value):
    with pytest.raises(ValueError, match=field):
        replace(ResourceRequirements(1, 1, 1), **{field: value})


@pytest.mark.parametrize(
    "field", ["min_cpu_millicores", "min_ram_bytes", "estimated_compute_ms"]
)
@pytest.mark.parametrize("value", [True, 1.5, "1"])
def test_rejects_noninteger_resource_values(field, value):
    with pytest.raises(TypeError, match=field):
        replace(ResourceRequirements(1, 1, 1), **{field: value})


@pytest.mark.parametrize("capabilities", ["gpu", {"gpu": True}, None, [1], [["gpu"]]])
def test_rejects_invalid_capability_types(capabilities):
    with pytest.raises(TypeError, match="capabilit"):
        ResourceRequirements(1, 1, 1, capabilities)


@pytest.mark.parametrize("identifier", ["", " \t"])
def test_rejects_blank_capability_ids(identifier):
    with pytest.raises(ValueError, match="capability identifiers"):
        ResourceRequirements(1, 1, 1, [identifier])
