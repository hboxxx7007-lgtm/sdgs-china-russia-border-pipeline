#!/usr/bin/env python3
"""Run ESDA spatial clustering analysis for the multiyear SDG index."""

from __future__ import annotations

import warnings

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
from esda.moran import Moran, Moran_Local
from libpysal.weights import Queen
from libpysal.weights.util import w_subset

from workflow_config import BASE_YEAR, DATA_DIR, FIGURES_DIR, LATEST_YEAR, PROGRESS_DIR, TARGET_YEARS, period_label, year_label


PERMUTATIONS = 999
P_THRESHOLD = 0.05
RANDOM_SEED = 20260512


def _change_rate(current: pd.Series, previous: pd.Series) -> pd.Series:
    base = previous.where(previous.ne(0))
    return (current - previous) / base * 100


def _format_float(value: float, digits: int = 4) -> str:
    if pd.isna(value):
        return ""
    return f"{value:.{digits}f}"


def _lisa_cluster_labels(local_moran: Moran_Local) -> tuple[np.ndarray, np.ndarray]:
    quadrant_labels = np.array(["Not significant"] * len(local_moran.q), dtype=object)
    significant = local_moran.p_sim < P_THRESHOLD
    label_map = {
        1: "HH 高值集聚",
        2: "LH 低值-高邻",
        3: "LL 低值集聚",
        4: "HL 高值-低邻",
    }
    for q_value, label in label_map.items():
        quadrant_labels[(local_moran.q == q_value) & significant] = label
    return quadrant_labels, significant


def _lisa_stats(gdf: gpd.GeoDataFrame, column: str, cluster_column: str) -> pd.DataFrame:
    counts = gdf[cluster_column].value_counts().reindex(
        ["HH 高值集聚", "LL 低值集聚", "HL 高值-低邻", "LH 低值-高邻", "Not significant"],
        fill_value=0,
    )
    rows = []
    total = len(gdf)
    for cluster, count in counts.items():
        subset = gdf[gdf[cluster_column] == cluster]
        rows.append(
            {
                "variable": column,
                "cluster": cluster,
                "count": int(count),
                "percentage": count / total * 100,
                "mean_value": subset[column].mean() if count else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _subset_weights(weights: Queen, ids: list[int]) -> Queen:
    if len(ids) == weights.n:
        return weights
    subset = w_subset(weights, ids)
    subset.transform = "r"
    return subset


def _write_markdown(
    global_df: pd.DataFrame,
    lisa_stats: pd.DataFrame,
    output_gpkg: str,
    global_csv: str,
    lisa_csv: str,
    latest_png: str,
    change_png: str,
) -> None:
    latest_global = global_df[global_df["variable"] == f"sdg_index_{LATEST_YEAR}"].iloc[0]
    change_global = global_df[global_df["variable"] == f"change_rate_{BASE_YEAR}_{LATEST_YEAR}"].iloc[0]
    latest_lisa = lisa_stats[lisa_stats["variable"] == f"sdg_index_{LATEST_YEAR}"].copy()
    change_lisa = lisa_stats[lisa_stats["variable"] == f"change_rate_{BASE_YEAR}_{LATEST_YEAR}"].copy()

    def pct_row(df: pd.DataFrame, label: str, column: str) -> str:
        row = df[df["cluster"] == label].iloc[0]
        return f"{int(row['count'])}个，占{row['percentage']:.2f}%"

    md = f"""# ESDA空间集聚分析补充结果

**生成日期：** 2026-05-12  
**分析对象：** 中俄东北-远东经济走廊10km评价网格，模型年份为{year_label()}。  
**输入数据：** `output/data/grid_sdg_multiyear.gpkg`。  
**输出数据：** `{global_csv}`、`{lisa_csv}`、`{output_gpkg}`。  
**预览图：** `{latest_png}`、`{change_png}`。

## 一、当前数据处理链条梳理

本文现有数据处理链条为：研究区边界去洞与几何修复，使用 `ESRI:102025` 生成10km评价网格；围绕{year_label()}四期年度或准年度数据计算人口、夜光、耕地、通达性、生态状态和环境约束等四维十二项指标；对连续指标进行1%-99%全时期极值剪裁，对正负向指标进行全时期合并极差标准化；在维度内部计算固定熵权，并保持四个维度等权；最后使用固定正负理想解TOPSIS计算各网格SDG综合指数。

在上述综合评价结果基础上，本文原有时空分析已经计算均值、变异系数、年份间相关系数、2010—2024变化率和“2024年发展水平×2010—2024变化趋势”的水平—变化类型区。ESDA空间集聚分析是在该结果之上的补充检验，用于回答综合指数是否存在空间自相关，以及高值、低值是否在局部形成显著集聚。

## 二、ESDA方法说明

ESDA（探索性空间数据分析）通过空间分布格局描述和可视化，发现研究变量的空间关联性和集聚性。本文以10km网格面邻接关系构建Queen邻接空间权重矩阵，并进行行标准化处理。Global Moran's I用于判断研究区整体空间自相关，LISA用于识别局部高值集聚、低值集聚以及空间离群单元。LISA结果按置换检验显著性筛选，显著性阈值为p < {P_THRESHOLD}，置换次数为{PERMUTATIONS}次。

## 三、Global Moran's I结果

Global Moran's I结果显示，{LATEST_YEAR}年SDG综合指数的Moran's I为{_format_float(latest_global['moran_i'])}，模拟检验p值为{_format_float(latest_global['p_sim'])}；{period_label()}变化率的Moran's I为{_format_float(change_global['moran_i'])}，模拟检验p值为{_format_float(change_global['p_sim'])}。这说明综合指数及其全期变化均不是随机散布，而具有明显空间自相关。其中，综合指数空间自相关更强，表明研究区发展水平受自然本底、通达条件和人口建设格局共同作用，呈现较稳定的空间邻近集聚特征。

| 变量 | Moran's I | 期望值 | z值 | p值 |
|---|---:|---:|---:|---:|
"""
    for _, row in global_df.iterrows():
        md += (
            f"| {row['variable']} | {_format_float(row['moran_i'])} | "
            f"{_format_float(row['expected_i'])} | {_format_float(row['z_sim'])} | "
            f"{_format_float(row['p_sim'])} |\n"
        )

    md += f"""
## 四、LISA局部集聚结果

以{LATEST_YEAR}年综合指数为例，HH高值集聚为{pct_row(latest_lisa, 'HH 高值集聚', 'percentage')}，LL低值集聚为{pct_row(latest_lisa, 'LL 低值集聚', 'percentage')}。HH单元表示自身综合指数较高且邻近网格也较高，可作为综合状态较优且空间连续性较强的区域识别线索；LL单元表示自身与邻近网格均处于较低水平，是后续讨论基本服务、生态韧性和必要联通维护时需要重点关注的空间单元。

从{period_label()}变化率看，HH高值集聚为{pct_row(change_lisa, 'HH 高值集聚', 'percentage')}，LL低值集聚为{pct_row(change_lisa, 'LL 低值集聚', 'percentage')}。变化率HH表示相对改善在空间上具有邻近集聚，变化率LL表示相对下降或改善不足在空间上具有邻近集聚。该结果应作为“变化趋势的空间相关线索”解释，不能直接写成某项政策导致增长或下降。

| 变量 | LISA类型 | 网格数 | 占比 | 类型均值 |
|---|---:|---:|---:|---:|
"""
    for _, row in lisa_stats.iterrows():
        md += (
            f"| {row['variable']} | {row['cluster']} | {int(row['count'])} | "
            f"{row['percentage']:.2f}% | {_format_float(row['mean_value'])} |\n"
        )

    md += """
## 五、预览图与论文写作边界

预览图已输出为 `output/figures/esda_lisa_sdg_index_2024.png` 和 `output/figures/esda_lisa_change_rate_2010_2024.png`。正式论文制图建议在QGIS中读取 `esda_lisa_clusters.gpkg`，使用 `lisa_sdg_index_2024_cluster` 或 `lisa_change_rate_2010_2024_cluster` 字段分类设色。

ESDA结果可以用于替换或补充原文中“热点类型区不是统计显著热点”的说明：原水平—变化类型区仍是描述性分位数分类，而本次新增的LISA才是基于空间权重矩阵和置换检验的局部空间集聚识别。正文中应区分二者，避免把描述性类型区和统计显著热点混用。
"""
    path = PROGRESS_DIR / "esda_spatial_clustering_2026-05-12.md"
    path.write_text(md, encoding="utf-8")


def _plot_lisa(gdf: gpd.GeoDataFrame, cluster_col: str, title: str, output_path) -> None:
    colors = {
        "HH 高值集聚": "#b2182b",
        "LL 低值集聚": "#2166ac",
        "HL 高值-低邻": "#ef8a62",
        "LH 低值-高邻": "#67a9cf",
        "Not significant": "#e6e6e6",
        "Missing": "#ffffff",
    }
    legend_labels = {
        "HH 高值集聚": "HH high-high",
        "LL 低值集聚": "LL low-low",
        "HL 高值-低邻": "HL high-low",
        "LH 低值-高邻": "LH low-high",
        "Not significant": "Not significant",
        "Missing": "Missing",
    }
    plot_gdf = gdf.to_crs("ESRI:102025")
    fig, ax = plt.subplots(figsize=(10, 7), dpi=180)
    legend_handles = []
    for label, color in colors.items():
        subset = plot_gdf[plot_gdf[cluster_col] == label]
        if subset.empty:
            continue
        subset.plot(ax=ax, color=color, edgecolor="none", label=label)
        legend_handles.append(Patch(facecolor=color, edgecolor="none", label=legend_labels[label]))
    plot_gdf.boundary.plot(ax=ax, color="#555555", linewidth=0.05)
    ax.set_title(title, fontsize=12)
    ax.set_axis_off()
    ax.legend(handles=legend_handles, loc="lower left", frameon=True, fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    input_path = DATA_DIR / "grid_sdg_multiyear.gpkg"
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    print("=" * 60)
    print(f"ESDA spatial clustering analysis: {year_label()}")
    print("=" * 60)

    grid = gpd.read_file(input_path)
    print(f"Grid cells: {len(grid)}")

    full_period = f"{BASE_YEAR}_{LATEST_YEAR}"
    change_col = f"change_rate_{full_period}"
    grid[change_col] = _change_rate(grid[f"sdg_index_{LATEST_YEAR}"], grid[f"sdg_index_{BASE_YEAR}"])

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        weights = Queen.from_dataframe(grid, use_index=True)
    weights.transform = "r"
    print(f"Neighbor links: {weights.s0:.0f}; islands: {len(weights.islands)}")

    variables = [f"sdg_index_{year}" for year in TARGET_YEARS] + [change_col]
    global_rows = []
    np.random.seed(RANDOM_SEED)
    for variable in variables:
        valid = grid[variable].notna()
        variable_weights = _subset_weights(weights, grid.index[valid].tolist())
        moran = Moran(grid.loc[valid, variable].to_numpy(), variable_weights, permutations=PERMUTATIONS)
        global_rows.append(
            {
                "variable": variable,
                "moran_i": moran.I,
                "expected_i": moran.EI,
                "z_sim": moran.z_sim,
                "p_sim": moran.p_sim,
                "permutations": PERMUTATIONS,
                "n": int(valid.sum()),
            }
        )
        print(f"{variable}: I={moran.I:.4f}, p={moran.p_sim:.4f}")

    lisa_variables = [f"sdg_index_{LATEST_YEAR}", change_col]
    lisa_stats_frames = []
    for variable in lisa_variables:
        valid = grid[variable].notna()
        variable_weights = _subset_weights(weights, grid.index[valid].tolist())
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            local = Moran_Local(
                grid.loc[valid, variable].to_numpy(),
                variable_weights,
                permutations=PERMUTATIONS,
                seed=RANDOM_SEED,
            )
        labels, significant = _lisa_cluster_labels(local)
        cluster_col = f"lisa_{variable}_cluster"
        p_col = f"lisa_{variable}_p"
        i_col = f"lisa_{variable}_i"
        grid[cluster_col] = "Missing"
        grid[p_col] = np.nan
        grid[i_col] = np.nan
        grid.loc[valid, cluster_col] = labels
        grid.loc[valid, p_col] = local.p_sim
        grid.loc[valid, i_col] = local.Is
        lisa_stats_frames.append(_lisa_stats(grid[valid].copy(), variable, cluster_col))
        print(f"{variable}: significant LISA cells={int(significant.sum())}")

    global_df = pd.DataFrame(global_rows)
    lisa_stats = pd.concat(lisa_stats_frames, ignore_index=True)

    global_csv = DATA_DIR / "esda_global_moran.csv"
    lisa_csv = DATA_DIR / "esda_lisa_statistics.csv"
    output_gpkg = DATA_DIR / "esda_lisa_clusters.gpkg"
    latest_png = FIGURES_DIR / "esda_lisa_sdg_index_2024.png"
    change_png = FIGURES_DIR / "esda_lisa_change_rate_2010_2024.png"

    global_df.to_csv(global_csv, index=False)
    lisa_stats.to_csv(lisa_csv, index=False)
    grid.to_file(output_gpkg, driver="GPKG")
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    _plot_lisa(grid, f"lisa_sdg_index_{LATEST_YEAR}_cluster", f"LISA clusters: SDG index {LATEST_YEAR}", latest_png)
    _plot_lisa(grid, f"lisa_change_rate_{BASE_YEAR}_{LATEST_YEAR}_cluster", f"LISA clusters: SDG change rate {period_label()}", change_png)
    _write_markdown(global_df, lisa_stats, str(output_gpkg), str(global_csv), str(lisa_csv), str(latest_png), str(change_png))

    print("Saved:")
    print(f"  {global_csv}")
    print(f"  {lisa_csv}")
    print(f"  {output_gpkg}")
    print(f"  {latest_png}")
    print(f"  {change_png}")
    print(f"  {PROGRESS_DIR / 'esda_spatial_clustering_2026-05-12.md'}")


if __name__ == "__main__":
    main()
