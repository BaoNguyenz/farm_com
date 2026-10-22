"""
Unit tests for Spatial Grid Discretization & Topology Indexing (Task 3.1)
"""
import pytest
from backend.core.twin_state import create_default_farm, FarmDigitalTwin, PlotZone


@pytest.fixture
def farm_4x4():
    return create_default_farm(width=4, height=4)


def test_grid_initialization_dimensions(farm_4x4):
    assert farm_4x4.grid_width == 4
    assert farm_4x4.grid_height == 4
    assert len(farm_4x4.zones) == 16


def test_get_zone_at_coordinate(farm_4x4):
    zone = farm_4x4.get_zone_at(2, 3)
    assert zone is not None
    assert zone.x == 2
    assert zone.y == 3
    assert zone.id == "Z_2_3"

    # Out of bounds
    assert farm_4x4.get_zone_at(10, 10) is None
    assert farm_4x4.get_zone_at(-1, 0) is None


def test_von_neumann_neighborhood_topology(farm_4x4):
    # Corner (0, 0): adjacent to (0, 1) and (1, 0) -> exactly 2 neighbors
    corner_neighbors = farm_4x4.get_neighbors(0, 0, diagonal=False)
    assert len(corner_neighbors) == 2
    coords = {(z.x, z.y) for z in corner_neighbors}
    assert coords == {(0, 1), (1, 0)}

    # Interior (1, 1): adjacent to 4 neighbors
    interior_neighbors = farm_4x4.get_neighbors(1, 1, diagonal=False)
    assert len(interior_neighbors) == 4
    interior_coords = {(z.x, z.y) for z in interior_neighbors}
    assert interior_coords == {(1, 2), (1, 0), (2, 1), (0, 1)}

    # Edge (2, 0): adjacent to 3 neighbors
    edge_neighbors = farm_4x4.get_neighbors(2, 0, diagonal=False)
    assert len(edge_neighbors) == 3


def test_moore_neighborhood_diagonal_topology(farm_4x4):
    # Corner (0, 0) with diagonals -> 3 neighbors: (0, 1), (1, 0), (1, 1)
    corner_moore = farm_4x4.get_neighbors(0, 0, diagonal=True)
    assert len(corner_moore) == 3

    # Interior (1, 1) with diagonals -> 8 neighbors
    interior_moore = farm_4x4.get_neighbors(1, 1, diagonal=True)
    assert len(interior_moore) == 8


def test_filter_by_crop_type(farm_4x4):
    coffee_zones = farm_4x4.get_zones_by_crop("coffee")
    assert len(coffee_zones) > 0
    for z in coffee_zones:
        assert "coffee" in z.crop_type.lower()


def test_stressed_zones_filtering(farm_4x4):
    # Default factory initializes Z_2_1 as water_stressed
    stressed = farm_4x4.get_stressed_zones()
    assert len(stressed) >= 1
    assert any(z.id == "Z_2_1" for z in stressed)


def test_spatial_summary_metrics(farm_4x4):
    summary = farm_4x4.get_spatial_summary()
    assert summary["total_zones"] == 16
    assert summary["grid_dimensions"] == "4x4"
    assert 30.0 <= summary["mean_soil_moisture_pct"] <= 85.0
    assert 0.40 <= summary["mean_ndvi"] <= 0.90
    assert summary["stressed_zone_count"] >= 1
    assert summary["healthy_zone_count"] + summary["stressed_zone_count"] == 16
