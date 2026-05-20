#!/usr/bin/env python3
"""Assign country/admin1 groups to SDG grids and summarize differences.

GADM is used as the preferred administrative boundary source because its ADM1
coverage generally matches provincial/state units more reliably for this study
area. geoBoundaries remains as a documented fallback so the workflow can still
run when the GADM server is temporarily unreachable.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import subprocess

from workflow_config import BASE_YEAR, DATA_DIR, DISPLAY_CRS, INDICATORS, LATEST_YEAR, METRIC_CRS


BOUNDARY_DIR = DATA_DIR / "admin_boundaries"
COUNTRIES = {
    "China": "CHN",
    "Russia": "RUS",
}
GADM_VERSION = "4.1"


def _download(url: str, out: Path, timeout: tuple[int, int] = (20, 240)) -> Path:
    if out.exists() and out.stat().st_size > 0:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")
    print(f"Downloading {url}")
    try:
        with requests.get(url, stream=True, timeout=timeout) as resp:
            resp.raise_for_status()
            with tmp.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        fh.write(chunk)
        tmp.replace(out)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        # GADM's server can stall during TLS/HTTP negotiation on some networks;
        # curl with IPv4 + HTTP/1.1 has proven more reliable while keeping the
        # same official source URL.
        subprocess.run(
            [
                "curl",
                "-4",
                "--http1.1",
                "-L",
                "--retry",
                "2",
                "--retry-delay",
                "3",
                "--connect-timeout",
                str(timeout[0]),
                "--max-time",
                str(timeout[1]),
                "-o",
                str(out),
                url,
            ],
            check=True,
        )
    return out


def download_gadm_adm1(iso3: str) -> Path:
    """Download GADM ADM1 as zipped GeoJSON and return a readable vector path."""
    BOUNDARY_DIR.mkdir(parents=True, exist_ok=True)
    out_json = BOUNDARY_DIR / f"gadm41_{iso3}_ADM1.json"
    if out_json.exists() and out_json.stat().st_size > 0:
        return out_json
    zip_path = BOUNDARY_DIR / f"gadm41_{iso3}_ADM1.json.zip"
    url = f"https://geodata.ucdavis.edu/gadm/gadm{GADM_VERSION}/json/gadm41_{iso3}_1.json.zip"
    _download(url, zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        members = [m for m in zf.namelist() if m.lower().endswith((".json", ".geojson"))]
        if not members:
            raise RuntimeError(f"No GeoJSON member found in {zip_path}")
        with zf.open(members[0]) as src, out_json.open("wb") as dst:
            dst.write(src.read())
    return out_json


def download_geoboundary(iso3: str) -> Path:
    BOUNDARY_DIR.mkdir(parents=True, exist_ok=True)
    out = BOUNDARY_DIR / f"geoBoundaries_{iso3}_ADM1.geojson"
    if out.exists() and out.stat().st_size > 0:
        return out
    meta_url = f"https://www.geoboundaries.org/api/current/gbOpen/{iso3}/ADM1/"
    meta = requests.get(meta_url, timeout=60)
    meta.raise_for_status()
    data = meta.json()
    gj_url = data["gjDownloadURL"]
    _download(gj_url, out, timeout=(20, 300))
    return out


def load_admin_boundaries() -> gpd.GeoDataFrame:
    frames = []
    for country, iso3 in COUNTRIES.items():
        source = "GADM"
        try:
            path = download_gadm_adm1(iso3)
        except Exception as exc:
            print(f"GADM download/read failed for {iso3}: {exc}; falling back to geoBoundaries.")
            path = download_geoboundary(iso3)
            source = "geoBoundaries"
        gdf = gpd.read_file(path).to_crs(DISPLAY_CRS)
        name_col = next((c for c in ["NAME_1", "shapeName", "shapeName_1", "name"] if c in gdf.columns), None)
        if name_col is None:
            name_col = gdf.columns[0]
        keep = gdf[[name_col, "geometry"]].copy()
        keep = keep.rename(columns={name_col: "admin1_name"})
        keep["country_group"] = country
        keep["admin1_group"] = keep["country_group"] + " - " + keep["admin1_name"].astype(str)
        keep["boundary_source"] = source
        frames.append(keep)
    admin = pd.concat(frames, ignore_index=True)
    return gpd.GeoDataFrame(admin, geometry="geometry", crs=DISPLAY_CRS)


def dimension_ids() -> list[str]:
    ids = []
    for cfg in INDICATORS.values():
        dim = cfg["dimension"].split()[0]
        if dim not in ids:
            ids.append(dim)
    return ids


def summarize_by(grouped: gpd.GeoDataFrame, group_col: str, output_csv: Path) -> pd.DataFrame:
    full_change = f"change_rate_{BASE_YEAR}_{LATEST_YEAR}"
    rows = []
    dims = dimension_ids()
    for name, part in grouped.groupby(group_col, dropna=False):
        row = {
            group_col: name,
            "grid_count": int(len(part)),
            f"sdg_index_{BASE_YEAR}_mean": part[f"sdg_index_{BASE_YEAR}"].mean(),
            f"sdg_index_{LATEST_YEAR}_mean": part[f"sdg_index_{LATEST_YEAR}"].mean(),
            f"change_rate_{BASE_YEAR}_{LATEST_YEAR}_mean": part[full_change].mean(),
            f"change_rate_{BASE_YEAR}_{LATEST_YEAR}_median": part[full_change].median(),
            "high_level_share_pct": (part["level_class"].astype(str).eq("高水平").mean() * 100),
            "relative_improvement_share_pct": (part["trend_class"].astype(str).eq("相对改善").mean() * 100),
        }
        latest_dim_means = {}
        for dim in dims:
            base_col = f"{dim}_score_{BASE_YEAR}"
            latest_col = f"{dim}_score_{LATEST_YEAR}"
            if base_col in part.columns and latest_col in part.columns:
                base_mean = part[base_col].mean()
                latest_mean = part[latest_col].mean()
                latest_dim_means[dim] = latest_mean
                row[f"{base_col}_mean"] = base_mean
                row[f"{latest_col}_mean"] = latest_mean
                row[f"{dim}_score_change_{BASE_YEAR}_{LATEST_YEAR}_mean"] = latest_mean - base_mean
        if latest_dim_means:
            ordered = sorted(latest_dim_means.items(), key=lambda item: item[1], reverse=True)
            row[f"top_dimension_{LATEST_YEAR}"] = ordered[0][0]
            row[f"weak_dimension_{LATEST_YEAR}"] = ordered[-1][0]
        rows.append(row)
    df = pd.DataFrame(rows).sort_values("grid_count", ascending=False)
    df.to_csv(output_csv, index=False)
    return df


def hotspot_table(grouped: gpd.GeoDataFrame, group_col: str, output_csv: Path) -> pd.DataFrame:
    table = pd.crosstab(grouped[group_col], grouped["hotspot_type"], normalize="index") * 100
    table.insert(0, "grid_count", grouped.groupby(group_col).size())
    table = table.reset_index().sort_values("grid_count", ascending=False)
    table.to_csv(output_csv, index=False)
    return table


def main() -> None:
    trend_path = DATA_DIR / "trend_analysis.gpkg"
    if not trend_path.exists():
        raise FileNotFoundError(trend_path)
    grid = gpd.read_file(trend_path).to_crs(DISPLAY_CRS)
    admin = load_admin_boundaries()
    admin_path = BOUNDARY_DIR / "china_russia_admin1.gpkg"
    admin.to_file(admin_path, driver="GPKG")

    centroids = grid.to_crs(METRIC_CRS).copy()
    centroids["grid_join_id"] = np.arange(len(centroids))
    centroids["geometry"] = centroids.geometry.centroid
    centroids = centroids.to_crs(DISPLAY_CRS)
    joined = gpd.sjoin(
        centroids[["grid_join_id", "geometry"]],
        admin[["country_group", "admin1_name", "admin1_group", "boundary_source", "geometry"]],
        how="left",
        predicate="within",
    ).drop(columns=["index_right"])
    # Administrative boundary datasets can contain tiny overlaps along borders.
    # Keep one deterministic match per grid centroid and reindex to the original grid.
    joined = joined.sort_values(["grid_join_id", "country_group", "admin1_name"]).drop_duplicates("grid_join_id")
    joined = joined.set_index("grid_join_id").reindex(range(len(grid)))
    grouped = grid.copy()
    grouped["country_group"] = joined["country_group"].fillna("Unmatched").values
    grouped["admin1_name"] = joined["admin1_name"].fillna("Unmatched").values
    grouped["admin1_group"] = joined["admin1_group"].fillna("Unmatched").values
    grouped["boundary_source"] = joined["boundary_source"].fillna("Unmatched").values
    out_gpkg = DATA_DIR / "grid_admin_grouped.gpkg"
    grouped.to_file(out_gpkg, driver="GPKG")

    country_stats = summarize_by(grouped, "country_group", DATA_DIR / "country_group_statistics.csv")
    admin_stats = summarize_by(grouped, "admin1_group", DATA_DIR / "admin1_group_statistics.csv")
    hotspot_stats = hotspot_table(grouped, "admin1_group", DATA_DIR / "admin1_hotspot_statistics.csv")
    print(f"Saved grouped grid: {out_gpkg}")
    print(f"Saved admin boundary: {admin_path}")
    print("Country groups:")
    print(country_stats.to_string(index=False))
    print("\nTop admin1 groups:")
    print(admin_stats.head(12).to_string(index=False))


if __name__ == "__main__":
    main()
