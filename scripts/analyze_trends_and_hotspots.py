#!/usr/bin/env python3
"""Analyze temporal trends and hotspot classes for the multiyear SDG index."""

import geopandas as gpd
import numpy as np
import pandas as pd

from workflow_config import BASE_YEAR, DATA_DIR, LATEST_YEAR, TARGET_YEARS, period_label, year_label


def classify_hotspot(level, trend):
    if pd.isna(level) or pd.isna(trend):
        return np.nan
    return f"{level}_{trend}"


def calculate_change_rate(current, previous):
    base = previous.where(previous.ne(0))
    return (current - previous) / base * 100


def calculate_aagr(current, previous, years):
    base = previous.where(previous.gt(0))
    return ((current / base) ** (1 / years) - 1) * 100


def main():
    input_path = DATA_DIR / "grid_sdg_multiyear.gpkg"
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    print("=" * 60)
    print(f"Trend and hotspot analysis: {year_label()}")
    print("=" * 60)
    grid = gpd.read_file(input_path)
    print(f"Grid cells: {len(grid)}")

    for previous, current in zip(TARGET_YEARS[:-1], TARGET_YEARS[1:]):
        grid[f"change_abs_{previous}_{current}"] = grid[f"sdg_index_{current}"] - grid[f"sdg_index_{previous}"]
        grid[f"change_rate_{previous}_{current}"] = calculate_change_rate(
            grid[f"sdg_index_{current}"],
            grid[f"sdg_index_{previous}"],
        )
        years = current - previous
        grid[f"AAGR_{previous}_{current}"] = calculate_aagr(
            grid[f"sdg_index_{current}"],
            grid[f"sdg_index_{previous}"],
            years,
        )

    full_period = f"{BASE_YEAR}_{LATEST_YEAR}"
    grid[f"change_abs_{full_period}"] = grid[f"sdg_index_{LATEST_YEAR}"] - grid[f"sdg_index_{BASE_YEAR}"]
    grid[f"change_rate_{full_period}"] = calculate_change_rate(
        grid[f"sdg_index_{LATEST_YEAR}"],
        grid[f"sdg_index_{BASE_YEAR}"],
    )
    grid[f"AAGR_{full_period}"] = calculate_aagr(
        grid[f"sdg_index_{LATEST_YEAR}"],
        grid[f"sdg_index_{BASE_YEAR}"],
        LATEST_YEAR - BASE_YEAR,
    )

    q25_level = grid[f"sdg_index_{LATEST_YEAR}"].quantile(0.25)
    q75_level = grid[f"sdg_index_{LATEST_YEAR}"].quantile(0.75)
    q25_change = grid[f"change_rate_{full_period}"].quantile(0.25)
    q75_change = grid[f"change_rate_{full_period}"].quantile(0.75)

    grid["level_class"] = pd.cut(
        grid[f"sdg_index_{LATEST_YEAR}"],
        bins=[-np.inf, q25_level, q75_level, np.inf],
        labels=["低水平", "中等水平", "高水平"],
        include_lowest=True,
    )
    grid["trend_class"] = pd.cut(
        grid[f"change_rate_{full_period}"],
        bins=[-np.inf, q25_change, q75_change, np.inf],
        labels=["相对下降", "中等变化", "相对改善"],
        include_lowest=True,
    )
    grid["hotspot_type"] = [classify_hotspot(a, b) for a, b in zip(grid["level_class"], grid["trend_class"])]

    stats = []
    for year in TARGET_YEARS:
        s = grid[f"sdg_index_{year}"]
        stats.append({
            "year": year,
            "mean": s.mean(),
            "std": s.std(),
            "min": s.min(),
            "max": s.max(),
            "cv": s.std() / s.mean() if not np.isclose(s.mean(), 0) else np.nan,
        })
    stats_df = pd.DataFrame(stats)

    corr_rows = []
    for previous, current in zip(TARGET_YEARS[:-1], TARGET_YEARS[1:]):
        corr_rows.append({
            "period": f"{previous}-{current}",
            "correlation": grid[[f"sdg_index_{previous}", f"sdg_index_{current}"]].corr().iloc[0, 1],
        })
    corr_rows.append({
        "period": period_label(),
        "correlation": grid[[f"sdg_index_{BASE_YEAR}", f"sdg_index_{LATEST_YEAR}"]].corr().iloc[0, 1],
    })

    hotspot_counts = grid["hotspot_type"].value_counts().sort_index()
    hotspot_stats = pd.DataFrame({
        "hotspot_type": hotspot_counts.index,
        "count": hotspot_counts.values,
        "percentage": hotspot_counts.values / len(grid) * 100,
    })

    output_path = DATA_DIR / "trend_analysis.gpkg"
    grid.to_file(output_path, driver="GPKG")
    stats_path = DATA_DIR / "trend_statistics.csv"
    stats_df.to_csv(stats_path, index=False)
    hotspot_path = DATA_DIR / "hotspot_statistics.csv"
    hotspot_stats.to_csv(hotspot_path, index=False)
    corr_path = DATA_DIR / "temporal_correlation.csv"
    pd.DataFrame(corr_rows).to_csv(corr_path, index=False)

    print(f"Full-period change mean ({period_label()}): {grid[f'change_rate_{full_period}'].mean():.2f}%")
    print(f"Hotspot classes: {len(hotspot_counts)}")
    print("Saved:")
    print(f"  {output_path}")
    print(f"  {stats_path}")
    print(f"  {hotspot_path}")
    print(f"  {corr_path}")


if __name__ == "__main__":
    main()
