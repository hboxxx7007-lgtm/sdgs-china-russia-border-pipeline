#!/usr/bin/env python3
"""Shared configuration for the China-Russia border SDGs workflow."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "output" / "data"
FIGURES_DIR = PROJECT_ROOT / "output" / "figures"
PROGRESS_DIR = PROJECT_ROOT / "output" / "progress"
QGIS_DIR = PROJECT_ROOT / "output" / "qgis"
QGIS_EXPORT_DIR = QGIS_DIR / "exports"

STUDY_AREA_PATH = DATA_DIR / "study_area_no_holes.gpkg"
GRID_PATH = DATA_DIR / "study_area_grid_10km.gpkg"
PORTS_PATH = DATA_DIR / "border_ports_both_sides.gpkg"
GEE_MULTIYEAR_DIR = DATA_DIR / "gee_multiyear"
ACCESSIBILITY_DIR = DATA_DIR / "accessibility"
CITY_POINTS_PATH = ACCESSIBILITY_DIR / "city_points_clean.gpkg"
MAJOR_ROADS_PATH = ACCESSIBILITY_DIR / "major_roads_clean.gpkg"

TARGET_YEARS = [2010, 2015, 2020, 2024]
BASE_YEAR = TARGET_YEARS[0]
LATEST_YEAR = TARGET_YEARS[-1]
TARGET_RESOLUTION = 10000

# EPSG:4326 is used for raw storage/GEE export/display. Analysis that needs
# area, distance, grids, or QGIS formal map layouts uses the Albers CRS below.
DISPLAY_CRS = "EPSG:4326"
METRIC_CRS = "ESRI:102025"

YEAR_MAPPING = {
    # VIIRS starts after 2012 in the checked GEE collection. The 2010 model
    # year therefore uses 2012 VIIRS as an initial-period proxy and discloses
    # the source-year mismatch in quality reports and thesis text.
    2010: {"pop": 2010, "viirs": 2012, "modis": 2010, "ndvi": 2010, "npp": 2010, "climate": 2010},
    2015: {"pop": 2015, "viirs": 2015, "modis": 2015, "ndvi": 2015, "npp": 2015, "climate": 2015},
    2020: {"pop": 2020, "viirs": 2020, "modis": 2020, "ndvi": 2020, "npp": 2020, "climate": 2020},
    # GPW/WorldPop annual population is not available after 2020 in the checked
    # GEE collections, so 2024 uses the latest population baseline and is
    # reported as a population-data limitation in the quality report.
    2024: {"pop": 2020, "viirs": 2024, "modis": 2024, "ndvi": 2024, "npp": 2024, "climate": 2024},
}

INDICATORS = {
    "pop_density": {
        "direction": "positive",
        "dimension": "D1 人类活动",
        "description": "D1.1 人口密度",
        "unit": "人/km2",
        "template": "I1_1_population_density_{year}.tif",
        "year_key": "pop",
        "value_type": "continuous",
    },
    "nightlight": {
        "direction": "positive",
        "dimension": "D1 人类活动",
        "description": "D1.2 夜间灯光强度",
        "unit": "nW/cm2/sr",
        "template": "I2_1_nightlight_intensity_{year}.tif",
        "year_key": "viirs",
        "value_type": "continuous",
    },
    "cropland_ratio": {
        "direction": "positive",
        "dimension": "D1 人类活动",
        "description": "D1.3 耕地/农田比例",
        "unit": "比例(0-1)",
        "template": "I1_3_cropland_ratio_{year}.tif",
        "year_key": "modis",
        "value_type": "ratio",
    },
    "dist_port": {
        "direction": "negative",
        "dimension": "D2 通达性",
        "description": "D2.1 距边境口岸距离",
        "unit": "km",
        "template": None,
        "year_key": None,
        "value_type": "continuous",
    },
    "dist_city": {
        "direction": "negative",
        "dimension": "D2 通达性",
        "description": "D2.2 距最近城市/城镇节点距离",
        "unit": "km",
        "template": None,
        "year_key": None,
        "value_type": "continuous",
    },
    "dist_major_road": {
        "direction": "negative",
        "dimension": "D2 通达性",
        "description": "D2.3 距主要道路距离",
        "unit": "km",
        "template": None,
        "year_key": None,
        "value_type": "continuous",
    },
    "ndvi": {
        "direction": "positive",
        "dimension": "D3 生态状态",
        "description": "D3.1 NDVI",
        "unit": "无量纲",
        "template": "I4_1_NDVI_{year}.tif",
        "year_key": "ndvi",
        "value_type": "continuous",
    },
    "forest_ratio": {
        "direction": "positive",
        "dimension": "D3 生态状态",
        "description": "D3.2 林地覆盖率",
        "unit": "比例(0-1)",
        "template": "I4_2_forest_cover_{year}.tif",
        "year_key": "modis",
        "value_type": "ratio",
    },
    "npp": {
        "direction": "positive",
        "dimension": "D3 生态状态",
        "description": "D3.3 净初级生产力",
        "unit": "kgC/m2",
        "template": "I4_3_NPP_{year}.tif",
        "year_key": "npp",
        "value_type": "continuous",
    },
    "slope": {
        "direction": "negative",
        "dimension": "D4 环境约束",
        "description": "D4.1 地形坡度",
        "unit": "度",
        "template": "I5_1_slope_static.tif",
        "year_key": "static",
        "value_type": "continuous",
    },
    "climate_water_stress": {
        "direction": "negative",
        "dimension": "D4 环境约束",
        "description": "D4.2 气候水分亏缺",
        "unit": "mm",
        "template": "I6_1_climate_water_deficit_{year}.tif",
        "year_key": "climate",
        "value_type": "continuous",
    },
    "cold_stress": {
        "direction": "negative",
        "dimension": "D4 环境约束",
        "description": "D4.3 低温冷胁迫",
        "unit": "℃·月",
        "template": "I6_2_cold_stress_{year}.tif",
        "year_key": "climate",
        "value_type": "continuous",
    },
}


def year_label() -> str:
    return "/".join(str(year) for year in TARGET_YEARS)


def period_label() -> str:
    return f"{BASE_YEAR}-{LATEST_YEAR}"
