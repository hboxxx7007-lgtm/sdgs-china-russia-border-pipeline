#!/usr/bin/env python3
"""Generate a data quality report for the multiyear thesis workflow."""

from datetime import datetime

import geopandas as gpd
import pandas as pd

from workflow_config import DATA_DIR, INDICATORS, LATEST_YEAR, PROGRESS_DIR, TARGET_YEARS, period_label, year_label


REPORT = PROGRESS_DIR / "data_quality_report.md"


def layer_summary(path):
    if not path.exists():
        return None
    gdf = gpd.read_file(path)
    bounds = [] if len(gdf) == 0 else [round(float(v), 4) for v in gdf.total_bounds]
    return {
        "path": str(path),
        "rows": len(gdf),
        "crs": str(gdf.crs),
        "geometry": {str(k): int(v) for k, v in gdf.geometry.geom_type.value_counts().items()},
        "bounds": bounds,
    }


def format_layer(summary):
    if summary is None:
        return "| missing | - | - | - | - |"
    return f"| `{summary['path']}` | {summary['rows']} | {summary['crs']} | {summary['geometry']} | {summary['bounds']} |"


def indicator_tables():
    sections = []
    for year in TARGET_YEARS:
        path = DATA_DIR / f"grid_indicators_{year}.gpkg"
        sections.append(f"### {year} 年指标完整性\n")
        if not path.exists():
            sections.append(f"暂无 `{path.name}`。\n")
            continue
        gdf = gpd.read_file(path)
        rows = ["| 指标 | 字段 | 有效网格 | 完整性 | 最小值 | 最大值 |", "|---|---|---:|---:|---:|---:|"]
        for col, cfg in INDICATORS.items():
            if col not in gdf.columns:
                rows.append(f"| {cfg['description']} | `{col}` | 0 | 0.0% | - | - |")
                continue
            series = gdf[col]
            valid = int(series.notna().sum())
            pct = valid / len(gdf) * 100 if len(gdf) else 0
            min_value = "-" if valid == 0 else f"{series.min():.4f}"
            max_value = "-" if valid == 0 else f"{series.max():.4f}"
            rows.append(f"| {cfg['description']} | `{col}` | {valid} | {pct:.1f}% | {min_value} | {max_value} |")
        sections.append("\n".join(rows) + "\n")
    return "\n".join(sections)


def weights_table():
    path = DATA_DIR / "weights_multiyear.csv"
    if not path.exists():
        return "暂无 `weights_multiyear.csv`。\n"
    df = pd.read_csv(path)
    rows = ["| 年份 | 维度 | 指标 | 字段 | 熵值 | 维度内权重 | 最终权重 |", "|---:|---|---|---|---:|---:|---:|"]
    for _, row in df.iterrows():
        local_weight = row["local_weight"] if "local_weight" in df.columns else row["weight"]
        dimension = row["dimension"] if "dimension" in df.columns else "-"
        rows.append(
            f"| {row['year']} | {dimension} | {row['description']} | `{row['indicator']}` | "
            f"{row['entropy']:.6f} | {local_weight:.6f} | {row['weight']:.6f} |"
        )
    return "\n".join(rows) + "\n"


def clipping_table():
    path = DATA_DIR / "outlier_clip_ranges.csv"
    if not path.exists():
        return "暂无 `outlier_clip_ranges.csv`。\n"
    df = pd.read_csv(path).fillna("")
    rows = [
        "| 指标 | 类型 | 原始最小值 | 原始最大值 | P1/下限 | P99/上限 | 下侧剪裁 | 上侧剪裁 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in df.iterrows():
        rows.append(
            f"| `{row['indicator']}` | {row['value_type']} | {row['raw_min']} | {row['raw_max']} | "
            f"{row['p01']} | {row['p99']} | {row['clipped_low_cells']} | {row['clipped_high_cells']} |"
        )
    return "\n".join(rows) + "\n"


def clipping_sensitivity_table():
    path = DATA_DIR / "outlier_clipping_sensitivity.csv"
    if not path.exists():
        return "暂无 `outlier_clipping_sensitivity.csv`。\n"
    df = pd.read_csv(path).fillna("")
    rows = ["| 年份 | Pearson | Spearman | 剪裁版均值 | 未剪裁版均值 |", "|---:|---:|---:|---:|---:|"]
    for _, row in df.iterrows():
        rows.append(
            f"| {row['year']} | {row['pearson_clipped_unclipped']:.6f} | "
            f"{row['spearman_clipped_unclipped']:.6f} | {row['clipped_mean']:.6f} | {row['unclipped_mean']:.6f} |"
        )
    return "\n".join(rows) + "\n"


def metadata_table():
    path = DATA_DIR / "indicator_source_years.csv"
    if not path.exists():
        return "暂无 `indicator_source_years.csv`。\n"
    df = pd.read_csv(path)
    df = df.fillna("")
    rows = ["| 模型年份 | 指标 | 数据年份 | 有效网格 | 缺失说明 |", "|---:|---|---|---:|---|"]
    for _, row in df.iterrows():
        rows.append(
            f"| {row['model_year']} | `{row['indicator']}` | {row['source_year']} | {row['valid']} | {row.get('missing_reason', '')} |"
        )
    return "\n".join(rows) + "\n"


def main():
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    layers = [
        DATA_DIR / "study_area_no_holes.gpkg",
        DATA_DIR / "study_area_grid_10km.gpkg",
        DATA_DIR / "border_ports.gpkg",
        *(DATA_DIR / f"grid_indicators_{year}.gpkg" for year in TARGET_YEARS),
        DATA_DIR / "grid_sdg_multiyear.gpkg",
        DATA_DIR / "trend_analysis.gpkg",
    ]
    lines = [
        "# 数据质量报告",
        "",
        f"**生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**目标年份：** {year_label()}",
        f"**分析期：** {period_label()}",
        "",
        "## 图层概览",
        "",
        "| 文件 | 要素数 | CRS | 几何类型 | 范围 |",
        "|---|---:|---|---|---|",
    ]
    lines.extend(format_layer(layer_summary(path)) for path in layers)
    lines.extend([
        "",
        "## 指标完整性",
        "",
        indicator_tables(),
        "## 数据年份映射",
        "",
        metadata_table(),
        "## 固定权重",
        "",
        weights_table(),
        "## 极值剪裁",
        "",
        "主模型对连续指标使用全时期合并样本的 1%-99% 分位剪裁；比例类指标限制在 0-1。",
        "",
        clipping_table(),
        "## 剪裁敏感性",
        "",
        clipping_sensitivity_table(),
        "## 关键局限",
        "",
        "- 2010 模型年夜间灯光采用 2012 年 VIIRS 数据作为起始期近似替代，不能解释为 2010 年夜光实测值。",
        "- 2024 年人口指标沿用 2020 人口基线，不能解释为 2024 年人口观测值。",
        "- 2024 年是最新完整主模型年份；2025 年数据只可作为局部更新或后续展望，不替代完整主模型。",
        "- 城市和道路可达性指标为准静态通达性约束，不解释为 2010-2024 年逐年交通建设变化。",
        "- 旧 `grid_sdg_index.gpkg` 和旧 2000-2020 结果只作流程验证，不支撑终稿结论。",
        "",
    ])
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Data quality report saved: {REPORT}")


if __name__ == "__main__":
    main()
