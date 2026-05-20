#!/usr/bin/env python3
"""
去除研究区边界的内部孔洞
保留外部边界，移除所有内部孔洞
"""

import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
from pathlib import Path

def remove_holes(geometry):
    """移除几何对象的所有内部孔洞"""
    if geometry.geom_type == 'Polygon':
        # 只保留外部边界
        return Polygon(geometry.exterior.coords)
    elif geometry.geom_type == 'MultiPolygon':
        # 对每个多边形移除孔洞
        return MultiPolygon([Polygon(poly.exterior.coords) for poly in geometry.geoms])
    else:
        return geometry

def main():
    # 输入输出路径
    input_file = Path("output/data/study_area_cleaned.gpkg")
    output_file = Path("output/data/study_area_no_holes.gpkg")

    print(f"读取研究区边界: {input_file}")
    gdf = gpd.read_file(input_file)

    print(f"原始几何类型: {gdf.geometry.iloc[0].geom_type}")
    print(f"原始要素数量: {len(gdf)}")

    # 检查是否有孔洞
    has_holes = False
    if gdf.geometry.iloc[0].geom_type == 'Polygon':
        has_holes = len(gdf.geometry.iloc[0].interiors) > 0
        if has_holes:
            print(f"检测到 {len(gdf.geometry.iloc[0].interiors)} 个内部孔洞")
    elif gdf.geometry.iloc[0].geom_type == 'MultiPolygon':
        total_holes = sum(len(poly.interiors) for poly in gdf.geometry.iloc[0].geoms)
        has_holes = total_holes > 0
        if has_holes:
            print(f"检测到 {total_holes} 个内部孔洞")

    if not has_holes:
        print("未检测到内部孔洞，无需处理")
        return

    # 移除孔洞
    print("移除内部孔洞...")
    gdf['geometry'] = gdf['geometry'].apply(remove_holes)

    # 保存结果
    print(f"保存结果: {output_file}")
    gdf.to_file(output_file, driver='GPKG')

    # 同时保存GeoJSON格式
    output_geojson = output_file.with_suffix('.geojson')
    print(f"保存GeoJSON: {output_geojson}")
    gdf.to_file(output_geojson, driver='GeoJSON')

    print("\n处理完成！")
    print(f"输出文件: {output_file}")
    print(f"输出文件: {output_geojson}")

if __name__ == "__main__":
    main()
