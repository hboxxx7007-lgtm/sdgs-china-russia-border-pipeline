#!/usr/bin/env python3
"""Calculate grid indicators for the configured multiyear SDGs workflow."""

import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio

from workflow_config import (
    CITY_POINTS_PATH,
    DATA_DIR,
    DISPLAY_CRS,
    GEE_MULTIYEAR_DIR,
    GRID_PATH,
    INDICATORS,
    MAJOR_ROADS_PATH,
    METRIC_CRS,
    PORTS_PATH,
    TARGET_YEARS,
    YEAR_MAPPING,
    period_label,
    year_label,
)


def sample_raster_at_centroids(gdf, raster_path):
    """Sample raster values at grid centroids after matching CRS.

    Centroids are calculated in the project metric CRS to avoid geographic-CRS
    centroid artifacts, then transformed to the raster CRS for sampling.
    """
    with rasterio.open(raster_path) as src:
        centroid_gdf = gdf.to_crs(METRIC_CRS).copy()
        centroid_gdf["geometry"] = centroid_gdf.geometry.centroid
        sample_gdf = centroid_gdf.to_crs(src.crs)
        centroids = sample_gdf.geometry
        coords = [(pt.x, pt.y) for pt in centroids]
        values = []
        band = src.read(1)
        for x, y in coords:
            try:
                row, col = src.index(x, y)
            except Exception:
                values.append(np.nan)
                continue
            if 0 <= row < src.height and 0 <= col < src.width:
                val = band[row, col]
                if src.nodata is not None and val == src.nodata:
                    values.append(np.nan)
                elif np.isnan(val):
                    values.append(np.nan)
                else:
                    values.append(float(val))
            else:
                values.append(np.nan)
        return np.array(values, dtype=float)


def raster_path_for(indicator_config, target_year):
    year_key = indicator_config["year_key"]
    template = indicator_config["template"]
    if year_key == "static":
        return GEE_MULTIYEAR_DIR / template, "static"
    source_year = YEAR_MAPPING[target_year][year_key]
    if source_year is None:
        return None, None
    return GEE_MULTIYEAR_DIR / template.format(year=source_year), source_year


def validate_required_sources():
    missing = []
    for target_year in TARGET_YEARS:
        for indicator, config in INDICATORS.items():
            if config["template"] is None:
                continue
            raster_path, _ = raster_path_for(config, target_year)
            if raster_path is not None and not raster_path.exists():
                missing.append(str(raster_path))
    for path in [CITY_POINTS_PATH, MAJOR_ROADS_PATH, PORTS_PATH]:
        if not path.exists():
            missing.append(str(path))
    if missing and os.environ.get("ALLOW_MISSING_INDICATORS", "0") != "1":
        unique_missing = "\n".join(f"  - {path}" for path in sorted(set(missing)))
        raise FileNotFoundError(
            "Required v4 indicator source files are missing. "
            "Download/prepare them before overwriting grid indicator outputs:\n"
            + unique_missing
        )


def add_port_distance(grid):
    if not PORTS_PATH.exists():
        grid["dist_port"] = np.nan
        print(f"   MISSING ports: {PORTS_PATH}")
        return grid

    grid_metric = grid.to_crs(METRIC_CRS)
    ports = gpd.read_file(PORTS_PATH).to_crs(METRIC_CRS)
    port_union = ports.geometry.union_all()
    grid["dist_port"] = grid_metric.geometry.centroid.distance(port_union) / 1000
    print(f"   OK dist_port: mean={grid['dist_port'].mean():.2f} km")
    return grid


def add_vector_distance(grid, path, column, label):
    if not path.exists():
        grid[column] = np.nan
        print(f"   MISSING {label}: {path}")
        return grid, 0

    grid_metric = grid.to_crs(METRIC_CRS)
    source = gpd.read_file(path).to_crs(METRIC_CRS)
    if len(source) == 0:
        grid[column] = np.nan
        print(f"   EMPTY {label}: {path}")
        return grid, 0
    source_union = source.geometry.union_all()
    grid[column] = grid_metric.geometry.centroid.distance(source_union) / 1000
    valid = int(grid[column].notna().sum())
    print(f"   OK {column}: mean={grid[column].mean():.2f} km from {len(source)} {label} features")
    return grid, valid


def main():
    print("=" * 60)
    print(f"Multiyear grid indicators: {year_label()} ({period_label()})")
    print(f"Metric CRS: {METRIC_CRS}")
    print("=" * 60)

    if not GRID_PATH.exists():
        raise FileNotFoundError(GRID_PATH)
    validate_required_sources()
    grid_template = gpd.read_file(GRID_PATH).to_crs(DISPLAY_CRS)
    print(f"Grid cells: {len(grid_template)}")
    print(f"Grid CRS for storage: {grid_template.crs}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    metadata_rows = []
    missing_required = []

    for target_year in TARGET_YEARS:
        print("\n" + "=" * 60)
        print(f"Processing model year {target_year}")
        print("=" * 60)
        grid = grid_template.copy()

        for indicator, config in INDICATORS.items():
            if indicator in {"dist_port", "dist_city", "dist_major_road"}:
                continue
            print(f"\n{config['description']} ({indicator})")
            raster_path, source_year = raster_path_for(config, target_year)
            if raster_path is None:
                grid[indicator] = np.nan
                print(f"   MISSING by design for {target_year}")
                metadata_rows.append({
                    "model_year": target_year,
                    "indicator": indicator,
                    "source_year": "missing",
                    "file": "",
                    "valid": 0,
                    "missing_reason": "source unavailable; no backcast",
                })
                continue
            if not raster_path.exists():
                grid[indicator] = np.nan
                print(f"   FILE NOT FOUND: {raster_path.name}")
                missing_required.append(str(raster_path))
                metadata_rows.append({
                    "model_year": target_year,
                    "indicator": indicator,
                    "source_year": source_year,
                    "file": str(raster_path),
                    "valid": 0,
                    "missing_reason": "file not downloaded",
                })
                continue

            values = sample_raster_at_centroids(grid, raster_path)
            grid[indicator] = values
            valid_values = values[~np.isnan(values)]
            print(f"   OK {len(valid_values)}/{len(grid)} valid from {raster_path.name}")
            if len(valid_values):
                print(f"   range=[{valid_values.min():.4f}, {valid_values.max():.4f}], mean={valid_values.mean():.4f}")
            metadata_rows.append({
                "model_year": target_year,
                "indicator": indicator,
                "source_year": source_year,
                "file": str(raster_path),
                "valid": int(len(valid_values)),
                "missing_reason": (
                    "uses 2020 population baseline"
                    if target_year == 2024 and indicator == "pop_density" and source_year == 2020
                    else "uses 2012 VIIRS as initial-period proxy"
                    if target_year == 2010 and indicator == "nightlight" and source_year == 2012
                    else ""
                ),
            })

        print("\nI3.1 distance to border ports")
        grid = add_port_distance(grid)
        metadata_rows.append({
            "model_year": target_year,
            "indicator": "dist_port",
            "source_year": "static",
            "file": str(PORTS_PATH),
            "valid": int(grid["dist_port"].notna().sum()),
            "missing_reason": "",
        })

        print("\nD2.2 distance to nearest city/town node")
        grid, valid_city = add_vector_distance(grid, CITY_POINTS_PATH, "dist_city", "city/town")
        if valid_city == 0:
            missing_required.append(str(CITY_POINTS_PATH))
        metadata_rows.append({
            "model_year": target_year,
            "indicator": "dist_city",
            "source_year": "quasi-static",
            "file": str(CITY_POINTS_PATH),
            "valid": valid_city,
            "missing_reason": "quasi-static accessibility indicator",
        })

        print("\nD2.3 distance to nearest major road")
        grid, valid_road = add_vector_distance(grid, MAJOR_ROADS_PATH, "dist_major_road", "major road")
        if valid_road == 0:
            missing_required.append(str(MAJOR_ROADS_PATH))
        metadata_rows.append({
            "model_year": target_year,
            "indicator": "dist_major_road",
            "source_year": "quasi-static",
            "file": str(MAJOR_ROADS_PATH),
            "valid": valid_road,
            "missing_reason": "quasi-static accessibility indicator",
        })

        if missing_required and os.environ.get("ALLOW_MISSING_INDICATORS", "0") != "1":
            unique_missing = "\n".join(f"  - {path}" for path in sorted(set(missing_required)))
            raise FileNotFoundError(
                "Required v4 indicator source files are missing. "
                "Download/prepare them before overwriting grid indicator outputs:\n"
                + unique_missing
            )

        output_path = DATA_DIR / f"grid_indicators_{target_year}.gpkg"
        output_cols = ["geometry"] + list(INDICATORS.keys())
        grid[output_cols].to_file(output_path, driver="GPKG")
        print(f"\nSaved {output_path}")

    import pandas as pd

    metadata_path = DATA_DIR / "indicator_source_years.csv"
    pd.DataFrame(metadata_rows).to_csv(metadata_path, index=False)
    print("\n" + "=" * 60)
    print("Indicator calculation complete")
    print(f"Source-year metadata: {metadata_path}")


if __name__ == "__main__":
    main()
