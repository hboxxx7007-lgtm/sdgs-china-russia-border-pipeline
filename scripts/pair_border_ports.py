#!/usr/bin/env python3
"""
将中俄口岸数据配对合并为"一对口岸一个点位"的标准格式。
每对中国-俄罗斯口岸合并为两侧连线的中点，输出到 border_ports_paired.gpkg。
"""

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from pathlib import Path

DATA_DIR = Path("data")
INPUT_FILE = DATA_DIR / "border_ports.gpkg"
OUTPUT_FILE = DATA_DIR / "border_ports_paired.gpkg"
BOTH_SIDES_FILE = DATA_DIR / "border_ports_both_sides.gpkg"

RUSSIAN_PORTS = {
    "Manzhouli": {
        "name_ru_side": "Zabaykalsk",
        "name_cn_ru_side": "后贝加尔斯克",
        "lon_ru": 117.3270,
        "lat_ru": 49.6516,
    },
    "Heihe": {
        "name_ru_side": "Blagoveshchensk",
        "name_cn_ru_side": "布拉戈维申斯克",
        "lon_ru": 127.5405,
        "lat_ru": 50.2796,
    },
    "Suifenhe": {
        "name_ru_side": "Pogranichny",
        "name_cn_ru_side": "格罗捷科沃",
        "lon_ru": 131.3778,
        "lat_ru": 44.4097,
    },
    "Hunchun": {
        "name_ru_side": "Kraskino",
        "name_cn_ru_side": "卡拉斯基诺",
        "lon_ru": 130.7813,
        "lat_ru": 42.7107,
    },
    "Dongning": {
        "name_ru_side": "Poltavka",
        "name_cn_ru_side": "波尔塔夫卡",
        "lon_ru": 131.2533,
        "lat_ru": 44.0221,
    },
    "Tongjiang": {
        "name_ru_side": "Nizhneleninskoye",
        "name_cn_ru_side": "下列宁斯阔耶",
        "lon_ru": 132.6678,
        "lat_ru": 47.9644,
    },
    "Fuyuan": {
        "name_ru_side": "Imeni Khabarovskogo",
        "name_cn_ru_side": "哈巴罗夫斯克附近",
        "lon_ru": 134.3500,
        "lat_ru": 48.4000,
    },
    "Luobei": {
        "name_ru_side": "Amurzet",
        "name_cn_ru_side": "阿穆尔泽特",
        "lon_ru": 131.0981,
        "lat_ru": 47.6967,
    },
    "Jiayin": {
        "name_ru_side": "Pashkovo",
        "name_cn_ru_side": "帕什科沃",
        "lon_ru": 130.4800,
        "lat_ru": 48.9300,
    },
    "Xunke": {
        "name_ru_side": "Poyarkovo",
        "name_cn_ru_side": "波亚尔科沃",
        "lon_ru": 128.6547,
        "lat_ru": 49.6259,
    },
    "Mohe": {
        "name_ru_side": "Galinda",
        "name_cn_ru_side": "加林达",
        "lon_ru": 123.0500,
        "lat_ru": 53.1200,
    },
    "Huma": {
        "name_ru_side": "Ushakovo",
        "name_cn_ru_side": "乌沙科沃",
        "lon_ru": 127.0500,
        "lat_ru": 51.8500,
    },
    "Jixi": {
        "name_ru_side": "Turii Rog",
        "name_cn_ru_side": "图里罗格",
        "lon_ru": 131.9818,
        "lat_ru": 45.2368,
    },
    "Raohe": {
        "name_ru_side": "Pokrovka",
        "name_cn_ru_side": "波克罗夫卡",
        "lon_ru": 134.2500,
        "lat_ru": 46.9500,
    },
    "Hulin": {
        "name_ru_side": "Markovo",
        "name_cn_ru_side": "马尔科沃",
        "lon_ru": 133.3500,
        "lat_ru": 45.8500,
    },
}


def main():
    cn_ports = gpd.read_file(INPUT_FILE)
    print(f"读取中国侧口岸: {len(cn_ports)} 个")
    print(f"CRS: {cn_ports.crs}")
    print()

    records = []
    for _, row in cn_ports.iterrows():
        cn_name = row["name"]
        if cn_name not in RUSSIAN_PORTS:
            print(f"  警告: 未找到 {cn_name} 的俄罗斯配对口岸，跳过")
            continue

        ru_info = RUSSIAN_PORTS[cn_name]
        cn_lon = row.geometry.x
        cn_lat = row.geometry.y
        ru_lon = ru_info["lon_ru"]
        ru_lat = ru_info["lat_ru"]

        mid_lon = (cn_lon + ru_lon) / 2
        mid_lat = (cn_lat + ru_lat) / 2

        cn_metric = gpd.GeoSeries([Point(cn_lon, cn_lat)], crs="EPSG:4326").to_crs("ESRI:102025")
        ru_metric = gpd.GeoSeries([Point(ru_lon, ru_lat)], crs="EPSG:4326").to_crs("ESRI:102025")
        pair_dist_km = cn_metric.geometry.iloc[0].distance(ru_metric.geometry.iloc[0]) / 1000

        records.append({
            "pair_id": cn_name,
            "name_cn_side": row["name_cn"],
            "name_ru_side": ru_info["name_cn_ru_side"],
            "name_en_cn": cn_name,
            "name_en_ru": ru_info["name_ru_side"],
            "type": row["type"],
            "province": row["province"],
            "status": row["status"],
            "lon_cn": round(cn_lon, 4),
            "lat_cn": round(cn_lat, 4),
            "lon_ru": round(ru_lon, 4),
            "lat_ru": round(ru_lat, 4),
            "lon_mid": round(mid_lon, 4),
            "lat_mid": round(mid_lat, 4),
            "pair_dist_km": round(pair_dist_km, 1),
            "geometry": Point(mid_lon, mid_lat),
        })

        print(f"  {row['name_cn']}({cn_name}) <-> {ru_info['name_cn_ru_side']}({ru_info['name_ru_side']})")
        print(f"    中国侧: ({cn_lon:.4f}, {cn_lat:.4f})")
        print(f"    俄罗斯侧: ({ru_lon:.4f}, {ru_lat:.4f})")
        print(f"    中点: ({mid_lon:.4f}, {mid_lat:.4f})  跨境距离: {pair_dist_km:.1f} km")

    result_gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")

    result_gdf.to_file(OUTPUT_FILE, driver="GPKG")
    print(f"\n保存配对口岸到: {OUTPUT_FILE}")
    print(f"共 {len(result_gdf)} 对口岸")

    print("\n=== 输出文件验证 ===")
    verify_gdf = gpd.read_file(OUTPUT_FILE)
    print(f"记录数: {len(verify_gdf)}")
    print(f"CRS: {verify_gdf.crs}")
    print(f"字段: {list(verify_gdf.columns)}")
    print(f"几何类型: {verify_gdf.geometry.geom_type.unique()}")
    print(f"空间范围: {verify_gdf.total_bounds}")
    print(f"\n配对口岸列表:")
    for _, r in verify_gdf.iterrows():
        print(f"  {r['name_cn_side']} <-> {r['name_ru_side']}  "
              f"中点({r['lon_mid']:.4f}, {r['lat_mid']:.4f})  "
              f"距离{r['pair_dist_km']:.1f}km")

    both_sides_records = []
    for _, row in cn_ports.iterrows():
        cn_name = row["name"]
        if cn_name not in RUSSIAN_PORTS:
            continue
        ru_info = RUSSIAN_PORTS[cn_name]
        cn_lon = row.geometry.x
        cn_lat = row.geometry.y
        ru_lon = ru_info["lon_ru"]
        ru_lat = ru_info["lat_ru"]

        both_sides_records.append({
            "name": cn_name,
            "name_cn": row["name_cn"],
            "country": "China",
            "paired_port": ru_info["name_ru_side"],
            "geometry": Point(cn_lon, cn_lat),
        })
        both_sides_records.append({
            "name": ru_info["name_ru_side"],
            "name_cn": ru_info["name_cn_ru_side"],
            "country": "Russia",
            "paired_port": cn_name,
            "geometry": Point(ru_lon, ru_lat),
        })

    both_gdf = gpd.GeoDataFrame(both_sides_records, crs="EPSG:4326")
    both_gdf.to_file(BOTH_SIDES_FILE, driver="GPKG")
    print(f"\n保存双侧口岸到: {BOTH_SIDES_FILE}")
    print(f"共 {len(both_gdf)} 个口岸点 (中国侧{len(both_gdf[both_gdf['country']=='China'])}个, 俄罗斯侧{len(both_gdf[both_gdf['country']=='Russia'])}个)")

    print("\n=== 双侧口岸验证 ===")
    verify_both = gpd.read_file(BOTH_SIDES_FILE)
    print(f"记录数: {len(verify_both)}")
    print(f"CRS: {verify_both.crs}")
    print(f"字段: {list(verify_both.columns)}")
    for _, r in verify_both.iterrows():
        print(f"  [{r['country']}] {r['name_cn']}({r['name']}) <-> {r['paired_port']}")


if __name__ == "__main__":
    main()
