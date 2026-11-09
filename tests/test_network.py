"""Task 1.4: the network reader derives everything from the .net.xml (no hard-coded IDs)."""

from manzil.scenarios.grid import GridSpec, build_grid
from manzil.sim.network import NetworkModel


def test_grid_intersections(grid_model):
    assert len(grid_model.intersections) == 9
    for x in grid_model.intersections.values():
        assert x.num_links == 16  # 4 approaches x (right, 2 straight, left)
        assert len(x.approaches) == 4
        assert len(x.incoming_lanes) == 8
        assert len(x.green_phases) == 2
        assert {link.direction for link in x.links} == {"r", "s", "l"}


def test_green_phases_cover_every_link(grid_model):
    for x in grid_model.intersections.values():
        served = set().union(*(g.green_links() for g in x.green_phases))
        assert served == set(range(x.num_links))


def test_program_greens_are_conflict_free(grid_model):
    for x in grid_model.intersections.values():
        for g in x.green_phases:
            assert x.conflicts_in(g.state) == []


def test_all_green_is_a_conflict(grid_model):
    for x in grid_model.intersections.values():
        assert x.conflicts_in("G" * x.num_links)


def test_permissive_left_promoted_to_priority_is_a_conflict(grid_model):
    x = grid_model.intersections["B1"]
    state = x.green_phases[0].state
    assert "g" in state
    assert x.conflicts_in(state.replace("g", "G"))


def test_foe_relation_is_symmetric(grid_model):
    for x in grid_model.intersections.values():
        for a in range(x.num_links):
            for b in range(x.num_links):
                assert x.are_foes(a, b) == x.are_foes(b, a)


def test_network_id_is_stable(grid_model):
    again = NetworkModel.from_file(grid_model.net_file)
    assert again.network_id == grid_model.network_id


def test_reader_works_on_another_network(tmp_path):
    net_file = build_grid(tmp_path, GridSpec(size=4, lanes=1))
    model = NetworkModel.from_file(net_file)
    assert len(model.intersections) == 16
    for x in model.intersections.values():
        for g in x.green_phases:
            assert x.conflicts_in(g.state) == []
