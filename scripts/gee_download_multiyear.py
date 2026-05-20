#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Submit GEE exports for the 2010-2024 SDGs multiyear workflow."""

import os
import sys

import ee
import geopandas as gpd

from workflow_config import (
    DISPLAY_CRS,
    GEE_MULTIYEAR_DIR,
    METRIC_CRS,
    PROJECT_ROOT,
    STUDY_AREA_PATH,
    TARGET_RESOLUTION,
    TARGET_YEARS,
    YEAR_MAPPING,
    year_label,
)

EXPORT_BUFFER_METERS = TARGET_RESOLUTION * 2
EXPORT_SOUTH_BOUND = 34.0


def local_tif_exists(name):
    return (GEE_MULTIYEAR_DIR / f"{name}.tif").exists()


def export_image(image, name, roi, tasks):
    if local_tif_exists(name) and os.environ.get("FORCE_GEE_EXPORT", "0") != "1":
        print(f"  SKIP local exists {name}.tif")
        return
    task = ee.batch.Export.image.toDrive(
        image=image.toFloat(),
        description=name,
        folder="GEE_SDGs_MultiYear",
        fileNamePrefix=name,
        region=roi,
        scale=TARGET_RESOLUTION,
        crs=DISPLAY_CRS,
        maxPixels=1e13,
    )
    task.start()
    tasks.append(task)
    print(f"  OK {name}")


def export_roi_from_study_area(gdf):
    """Build a padded WGS84 export rectangle from the official study area.

    The padding prevents edge pixels along the southern/eastern/northern/western
    border from being dropped by Earth Engine's export grid alignment. The
    analysis grid is still generated from the unbuffered no-hole study area.
    """
    study_metric = gdf.to_crs(METRIC_CRS)
    padded = study_metric.copy()
    padded["geometry"] = padded.geometry.buffer(EXPORT_BUFFER_METERS)
    padded_wgs84 = padded.to_crs(DISPLAY_CRS)
    bounds = padded_wgs84.total_bounds
    bounds[1] = min(bounds[1], EXPORT_SOUTH_BOUND)
    return ee.Geometry.Rectangle([bounds[0], bounds[1], bounds[2], bounds[3]]), bounds


def first_image(collection, label):
    image = ee.Image(collection.first())
    count = collection.size().getInfo()
    if count == 0:
        raise RuntimeError(f"GEE collection has no image for {label}")
    return image


def population_image(year, roi):
    image = first_image(
        ee.ImageCollection("CIESIN/GPWv411/GPW_Population_Density")
        .filter(ee.Filter.stringContains("system:index", str(year))),
        f"GPW population {year}",
    )
    pop = image.select("population_density").setDefaultProjection(crs=DISPLAY_CRS, scale=928).clip(roi)
    pop_10km = pop.reduceResolution(ee.Reducer.mean(), maxPixels=4096).reproject(
        crs=DISPLAY_CRS, scale=TARGET_RESOLUTION
    )
    return pop_10km


def viirs_image(year, roi):
    if year is None:
        return None
    collection_id = (
        "NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG"
        if year == 2012
        else "NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG"
    )
    image = (
        ee.ImageCollection(collection_id)
        .filterDate(f"{year}-01-01", f"{year + 1}-01-01")
        .select("avg_rad")
        .mean()
        .setDefaultProjection(crs=DISPLAY_CRS, scale=500)
        .clip(roi)
    )
    return image.reduceResolution(ee.Reducer.mean(), maxPixels=4096).reproject(
        crs=DISPLAY_CRS, scale=TARGET_RESOLUTION
    )


def landcover_images(year, roi):
    lc = first_image(
        ee.ImageCollection("MODIS/061/MCD12Q1").filter(ee.Filter.calendarRange(year, year, "year")),
        f"MODIS MCD12Q1 {year}",
    ).select("LC_Type1").setDefaultProjection(crs=DISPLAY_CRS, scale=500).clip(roi)

    cropland = lc.eq(12).Or(lc.eq(14))
    cropland_ratio = cropland.reduceResolution(ee.Reducer.mean(), maxPixels=4096).reproject(
        crs=DISPLAY_CRS, scale=TARGET_RESOLUTION
    )
    forest = lc.gte(1).And(lc.lte(5))
    forest_ratio = forest.reduceResolution(ee.Reducer.mean(), maxPixels=4096).reproject(
        crs=DISPLAY_CRS, scale=TARGET_RESOLUTION
    )
    return cropland_ratio, forest_ratio


def ndvi_image(year, roi):
    ndvi = (
        ee.ImageCollection("MODIS/061/MOD13A3")
        .filterDate(f"{year}-05-01", f"{year}-10-01")
        .select("NDVI")
        .mean()
        .multiply(0.0001)
        .setDefaultProjection(crs=DISPLAY_CRS, scale=1000)
        .clip(roi)
    )
    return ndvi.reduceResolution(ee.Reducer.mean(), maxPixels=4096).reproject(
        crs=DISPLAY_CRS, scale=TARGET_RESOLUTION
    )


def npp_image(year, roi):
    npp = first_image(
        ee.ImageCollection("MODIS/061/MOD17A3HGF").filter(ee.Filter.calendarRange(year, year, "year")),
        f"MODIS MOD17A3HGF NPP {year}",
    ).select("Npp").multiply(0.0001).setDefaultProjection(crs=DISPLAY_CRS, scale=500).clip(roi)
    return npp.reduceResolution(ee.Reducer.mean(), maxPixels=4096).reproject(
        crs=DISPLAY_CRS, scale=TARGET_RESOLUTION
    )


def slope_image(roi):
    dem = ee.Image("USGS/GTOPO30").setDefaultProjection(crs=DISPLAY_CRS, scale=1000)
    slope = ee.Terrain.slope(dem).clip(roi)
    return slope.reduceResolution(ee.Reducer.mean(), maxPixels=4096).reproject(
        crs=DISPLAY_CRS, scale=TARGET_RESOLUTION
    )


def climate_water_stress_image(year, roi):
    deficit = (
        ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE")
        .filterDate(f"{year}-01-01", f"{year + 1}-01-01")
        .select("def")
        .sum()
        .multiply(0.1)
        .setDefaultProjection(crs=DISPLAY_CRS, scale=4638.3)
        .clip(roi)
    )
    return deficit.reduceResolution(ee.Reducer.mean(), maxPixels=4096).reproject(
        crs=DISPLAY_CRS, scale=TARGET_RESOLUTION
    )


def cold_stress_image(year, roi):
    """Annual cold-degree months from TerraClimate monthly minimum temperature.

    TerraClimate temperature bands are stored as 0.1 degrees C. This proxy sums
    monthly cold intensity below 0 C, so larger values mean stronger cold stress.
    """
    monthly_cold = (
        ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE")
        .filterDate(f"{year}-01-01", f"{year + 1}-01-01")
        .select("tmmn")
        .map(lambda img: img.multiply(0.1).multiply(-1).max(0))
    )
    cold = monthly_cold.sum().setDefaultProjection(crs=DISPLAY_CRS, scale=4638.3).clip(roi)
    return cold.reduceResolution(ee.Reducer.mean(), maxPixels=4096).reproject(
        crs=DISPLAY_CRS, scale=TARGET_RESOLUTION
    )


def main():
    project_id = os.environ.get("EARTHENGINE_PROJECT", "sdgs-china-russia-border")
    ee.Initialize(project=project_id, opt_url="https://earthengine-highvolume.googleapis.com")

    if not STUDY_AREA_PATH.exists():
        print(f"Missing study area: {STUDY_AREA_PATH}")
        sys.exit(1)

    GEE_MULTIYEAR_DIR.mkdir(parents=True, exist_ok=True)
    gdf = gpd.read_file(STUDY_AREA_PATH).to_crs(DISPLAY_CRS)
    study_bounds = gdf.total_bounds
    roi, export_bounds = export_roi_from_study_area(gdf)

    tasks = []
    print("=" * 60)
    print(f"GEE multiyear export: {year_label()}")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Earth Engine project: {project_id}")
    print(f"Study area: {STUDY_AREA_PATH.name}")
    print(f"Study bounds: {[round(float(v), 6) for v in study_bounds]}")
    print(f"Export bounds with {EXPORT_BUFFER_METERS / 1000:.0f} km buffer and south bound {EXPORT_SOUTH_BOUND}°N: {[round(float(v), 6) for v in export_bounds]}")
    print("=" * 60)

    exported_population_years = set()
    exported_modis_years = set()
    exported_ndvi_years = set()

    print("\n[1/6] Population density")
    for target_year in TARGET_YEARS:
        source_year = YEAR_MAPPING[target_year]["pop"]
        if source_year in exported_population_years:
            print(f"  SKIP population {source_year}: already exported for another target year")
            continue
        pop = population_image(source_year, roi)
        export_image(pop, f"I1_1_population_density_{source_year}", roi, tasks)
        exported_population_years.add(source_year)

    print("\n[2/6] VIIRS monthly stable lights annual mean")
    exported_viirs_years = set()
    for target_year in TARGET_YEARS:
        source_year = YEAR_MAPPING[target_year]["viirs"]
        if source_year is None:
            print(f"  SKIP nightlight {target_year}: VIIRS unavailable, kept as missing")
            continue
        if source_year in exported_viirs_years:
            print(f"  SKIP nightlight {source_year}: already exported for another target year")
            continue
        export_image(viirs_image(source_year, roi), f"I2_1_nightlight_intensity_{source_year}", roi, tasks)
        exported_viirs_years.add(source_year)

    print("\n[3/6] MODIS land cover indicators")
    for target_year in TARGET_YEARS:
        source_year = YEAR_MAPPING[target_year]["modis"]
        if source_year in exported_modis_years:
            continue
        cropland_ratio, forest_ratio = landcover_images(source_year, roi)
        export_image(cropland_ratio, f"I1_3_cropland_ratio_{source_year}", roi, tasks)
        export_image(forest_ratio, f"I4_2_forest_cover_{source_year}", roi, tasks)
        exported_modis_years.add(source_year)

    print("\n[4/6] MODIS NDVI growing-season mean and annual NPP")
    for target_year in TARGET_YEARS:
        source_year = YEAR_MAPPING[target_year]["ndvi"]
        if source_year in exported_ndvi_years:
            continue
        export_image(ndvi_image(source_year, roi), f"I4_1_NDVI_{source_year}", roi, tasks)
        exported_ndvi_years.add(source_year)
    exported_npp_years = set()
    for target_year in TARGET_YEARS:
        source_year = YEAR_MAPPING[target_year]["npp"]
        if source_year in exported_npp_years:
            continue
        export_image(npp_image(source_year, roi), f"I4_3_NPP_{source_year}", roi, tasks)
        exported_npp_years.add(source_year)

    print("\n[5/6] Static slope")
    export_image(slope_image(roi), "I5_1_slope_static", roi, tasks)

    print("\n[6/6] TerraClimate annual climate water deficit and cold stress")
    exported_climate_years = set()
    for target_year in TARGET_YEARS:
        source_year = YEAR_MAPPING[target_year]["climate"]
        if source_year in exported_climate_years:
            continue
        export_image(climate_water_stress_image(source_year, roi), f"I6_1_climate_water_deficit_{source_year}", roi, tasks)
        export_image(cold_stress_image(source_year, roi), f"I6_2_cold_stress_{source_year}", roi, tasks)
        exported_climate_years.add(source_year)

    print("\n" + "=" * 60)
    print(f"Submitted {len(tasks)} tasks to Google Drive folder GEE_SDGs_MultiYear")
    if len(tasks) == 0:
        print("No tasks were submitted because all expected local TIFFs already exist or are intentionally missing.")
    print("After tasks finish, download GeoTIFF files into output/data/gee_multiyear/")


if __name__ == "__main__":
    main()
