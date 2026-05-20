#!/usr/bin/env python3
"""Generate the official 10 km evaluation grid from the no-hole study area."""

import numpy as np
import geopandas as gpd
from shapely.geometry import box

from workflow_config import DISPLAY_CRS, GRID_PATH, METRIC_CRS, STUDY_AREA_PATH, TARGET_RESOLUTION


def main() -> None:
    if not STUDY_AREA_PATH.exists():
        raise FileNotFoundError(STUDY_AREA_PATH)

    study = gpd.read_file(STUDY_AREA_PATH).to_crs(METRIC_CRS)
    study_union = study.geometry.union_all()
    xmin, ymin, xmax, ymax = study.total_bounds

    xs = np.arange(np.floor(xmin / TARGET_RESOLUTION) * TARGET_RESOLUTION, xmax, TARGET_RESOLUTION)
    ys = np.arange(np.floor(ymin / TARGET_RESOLUTION) * TARGET_RESOLUTION, ymax, TARGET_RESOLUTION)

    cells = []
    for x in xs:
        for y in ys:
            cell = box(x, y, x + TARGET_RESOLUTION, y + TARGET_RESOLUTION)
            if cell.centroid.within(study_union):
                cells.append(cell)

    grid = gpd.GeoDataFrame({"grid_id": np.arange(1, len(cells) + 1)}, geometry=cells, crs=METRIC_CRS)
    grid_wgs84 = grid.to_crs(DISPLAY_CRS)
    GRID_PATH.parent.mkdir(parents=True, exist_ok=True)
    GRID_PATH.unlink(missing_ok=True)
    grid_wgs84.to_file(GRID_PATH, layer="study_area_grid_10km", driver="GPKG")

    print("=" * 60)
    print("Official 10 km grid generated")
    print(f"Study area: {STUDY_AREA_PATH}")
    print(f"Grid: {GRID_PATH}")
    print(f"Cells: {len(grid_wgs84)}")
    print(f"CRS for storage: {grid_wgs84.crs}")
    print(f"Bounds: {[round(float(v), 6) for v in grid_wgs84.total_bounds]}")


if __name__ == "__main__":
    main()
