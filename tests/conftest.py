import pytest

from manzil.scenarios.demand import DEFAULT_NET, build_demand
from manzil.sim.network import NetworkModel


@pytest.fixture(scope="session")
def grid_model() -> NetworkModel:
    return NetworkModel.from_file(DEFAULT_NET)


@pytest.fixture(scope="session")
def light_cfg(tmp_path_factory):
    """A short seeded light-demand scenario (600 s) in a temporary folder."""
    out = tmp_path_factory.mktemp("demand")
    return build_demand("light", seed=0, duration_s=600, out_dir=out).sumocfg
