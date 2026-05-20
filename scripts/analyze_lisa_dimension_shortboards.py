#!/usr/bin/env python3
"""Identify dimension and indicator shortboards for LISA cluster types."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd

from workflow_config import DATA_DIR, INDICATORS, LATEST_YEAR, PROGRESS_DIR, period_label


LISA_GROUPS = {
    f"lisa_sdg_index_{LATEST_YEAR}_cluster": f"{LATEST_YEAR}年综合指数LISA",
    f"lisa_change_rate_2010_{LATEST_YEAR}_cluster": f"2010-{LATEST_YEAR}变化率LISA",
}

CLUSTER_ORDER = ["HH 高值集聚", "LL 低值集聚", "HL 高值-低邻", "LH 低值-高邻", "Not significant"]
DIMENSION_LABELS = {
    "D1": "D1 人类活动",
    "D2": "D2 通达性",
    "D3": "D3 生态状态",
    "D4": "D4 环境约束",
}


def _fmt(value: float, digits: int = 4) -> str:
    if pd.isna(value):
        return ""
    return f"{value:.{digits}f}"


def _pct(value: float) -> str:
    if pd.isna(value):
        return ""
    return f"{value:.2f}%"


def _dimension_id(label: str) -> str:
    return label.split()[0]


def _load_inputs() -> tuple[gpd.GeoDataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    lisa_path = DATA_DIR / "esda_lisa_clusters.gpkg"
    indicators_path = DATA_DIR / f"grid_indicators_{LATEST_YEAR}.gpkg"
    weights_path = DATA_DIR / "weights_multiyear.csv"
    ranges_path = DATA_DIR / "normalization_ranges.csv"
    for path in [lisa_path, indicators_path, weights_path, ranges_path]:
        if not path.exists():
            raise FileNotFoundError(path)

    lisa = gpd.read_file(lisa_path)
    indicators = gpd.read_file(indicators_path, ignore_geometry=True)
    weights = pd.read_csv(weights_path)
    ranges = pd.read_csv(ranges_path)
    if len(lisa) != len(indicators):
        raise ValueError(f"Row mismatch: {lisa_path}={len(lisa)}, {indicators_path}={len(indicators)}")
    return lisa, indicators, weights, ranges


def _normalize_indicators(indicators: pd.DataFrame, ranges: pd.DataFrame) -> pd.DataFrame:
    normalized = pd.DataFrame(index=indicators.index)
    range_lookup = ranges.set_index("indicator")
    for indicator, config in INDICATORS.items():
        if indicator not in indicators.columns:
            normalized[indicator] = np.nan
            continue
        row = range_lookup.loc[indicator]
        min_value = row["global_min"]
        max_value = row["global_max"]
        clipped = indicators[indicator].clip(lower=min_value, upper=max_value)
        if np.isclose(min_value, max_value):
            normalized[indicator] = 0.5
        elif config["direction"] == "positive":
            normalized[indicator] = (clipped - min_value) / (max_value - min_value)
        else:
            normalized[indicator] = (max_value - clipped) / (max_value - min_value)
    return normalized


def _indicator_metadata(weights: pd.DataFrame) -> pd.DataFrame:
    weight_lookup = weights.set_index("indicator")
    rows = []
    for indicator, config in INDICATORS.items():
        weight_row = weight_lookup.loc[indicator]
        rows.append(
            {
                "indicator": indicator,
                "indicator_name": config["description"],
                "dimension": _dimension_id(config["dimension"]),
                "dimension_name": config["dimension"],
                "direction": config["direction"],
                "unit": config.get("unit", ""),
                "local_weight": weight_row["local_weight"],
                "weight": weight_row["weight"],
            }
        )
    return pd.DataFrame(rows)


def _top_indicator(details: pd.DataFrame, dimension: str, rank: int = 1) -> str:
    subset = details[details["dimension"] == dimension].sort_values(
        ["shortboard_strength", "normalized_mean"],
        ascending=[False, True],
    )
    if len(subset) < rank:
        return ""
    row = subset.iloc[rank - 1]
    return f"{row['indicator_name']}（{row['indicator']}）"


def _constraint_phrase(indicator_row: pd.Series) -> str:
    name = indicator_row["indicator_name"]
    raw = _fmt(indicator_row["raw_mean"], 3)
    norm = _fmt(indicator_row["normalized_mean"], 3)
    if indicator_row["direction"] == "positive":
        return f"{name}标准化均值为{norm}（原始均值{raw}），相对理想状态仍有支撑差距"
    return f"{name}标准化均值为{norm}（原始均值{raw}），说明该约束仍有影响"


def _build_tables(
    lisa: gpd.GeoDataFrame,
    indicators: pd.DataFrame,
    normalized: pd.DataFrame,
    metadata: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    combined = pd.concat(
        [
            lisa.drop(columns="geometry").reset_index(drop=True),
            indicators.add_prefix("raw_").reset_index(drop=True),
            normalized.add_prefix("norm_").reset_index(drop=True),
        ],
        axis=1,
    )
    total = len(combined)
    summary_rows = []
    detail_rows = []

    for lisa_col, lisa_label in LISA_GROUPS.items():
        for cluster in CLUSTER_ORDER:
            subset = combined[combined[lisa_col] == cluster]
            count = len(subset)
            if count == 0:
                continue

            dim_means = {
                dim: subset[f"{dim}_score_{LATEST_YEAR}"].mean()
                for dim in ["D1", "D2", "D3", "D4"]
            }
            ranked_dims = sorted(dim_means, key=lambda dim: dim_means[dim])

            cluster_details = []
            for _, meta in metadata.iterrows():
                indicator = meta["indicator"]
                raw_mean = subset[f"raw_{indicator}"].mean()
                normalized_mean = subset[f"norm_{indicator}"].mean()
                strength = (1 - normalized_mean) * meta["local_weight"]
                row = {
                    "lisa_variable": lisa_col,
                    "lisa_label": lisa_label,
                    "lisa_cluster": cluster,
                    "count": count,
                    "percentage": count / total * 100,
                    **meta.to_dict(),
                    "raw_mean": raw_mean,
                    "normalized_mean": normalized_mean,
                    "shortboard_strength": strength,
                }
                detail_rows.append(row)
                cluster_details.append(row)

            details_df = pd.DataFrame(cluster_details)
            primary_dim = ranked_dims[0]
            secondary_dim = ranked_dims[1]
            primary_indicator = _top_indicator(details_df, primary_dim)
            secondary_indicator = _top_indicator(details_df, secondary_dim)
            strongest_indicator = details_df.sort_values(
                ["shortboard_strength", "normalized_mean"],
                ascending=[False, True],
            ).iloc[0]
            second_strongest = details_df.sort_values(
                ["shortboard_strength", "normalized_mean"],
                ascending=[False, True],
            ).iloc[1]

            summary_rows.append(
                {
                    "lisa_variable": lisa_col,
                    "lisa_label": lisa_label,
                    "lisa_cluster": cluster,
                    "count": count,
                    "percentage": count / total * 100,
                    f"sdg_index_{LATEST_YEAR}_mean": subset[f"sdg_index_{LATEST_YEAR}"].mean(),
                    f"change_rate_2010_{LATEST_YEAR}_mean": subset[f"change_rate_2010_{LATEST_YEAR}"].mean(),
                    "D1_score_mean": dim_means["D1"],
                    "D2_score_mean": dim_means["D2"],
                    "D3_score_mean": dim_means["D3"],
                    "D4_score_mean": dim_means["D4"],
                    "primary_shortboard_dimension": DIMENSION_LABELS[primary_dim],
                    "secondary_shortboard_dimension": DIMENSION_LABELS[secondary_dim],
                    "primary_constraint_indicator": primary_indicator,
                    "secondary_constraint_indicator": secondary_indicator,
                    "strongest_indicator_constraint": f"{strongest_indicator['indicator_name']}（{strongest_indicator['indicator']}）",
                    "second_indicator_constraint": f"{second_strongest['indicator_name']}（{second_strongest['indicator']}）",
                }
            )

    return pd.DataFrame(summary_rows), pd.DataFrame(detail_rows)


def _detail_phrase(details: pd.DataFrame, lisa_col: str, cluster: str, dimension_name: str) -> str:
    dim = dimension_name.split()[0]
    subset = details[
        (details["lisa_variable"] == lisa_col)
        & (details["lisa_cluster"] == cluster)
        & (details["dimension"] == dim)
    ].sort_values(["shortboard_strength", "normalized_mean"], ascending=[False, True])
    phrases = [_constraint_phrase(row) for _, row in subset.head(2).iterrows()]
    return "；".join(phrases)


def _markdown_table(rows: list[list[str]], headers: list[str]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)


def _write_markdown(summary: pd.DataFrame, details: pd.DataFrame) -> None:
    output_path = PROGRESS_DIR / "lisa_dimension_shortboard_2026-05-12.md"
    md = [
        "# LISA类型区维度短板识别",
        "",
        "**生成日期：** 2026-05-12  ",
        "**分析对象：** 2024年综合指数LISA类型区与2010-2024变化率LISA类型区。  ",
        "**方法口径：** 短板先由D1-D4维度分数和指标标准化得分判定，熵权/TOPSIS权重仅用于解释哪些指标对类型区差异具有更强区分作用，不直接把权重大小解释为短板。",
        "",
        "## 一、判定方法",
        "",
        "本文对每个LISA类型区计算D1人类活动、D2通达性、D3生态状态和D4环境约束的2024年维度分数均值。维度分数越低，说明该类型区在该维度上越接近相对不利状态，因此将最低维度作为主短板，次低维度作为次短板。进一步地，本文使用2024年原始指标和全时期标准化范围计算各指标标准化均值，并结合维度内熵权得到加权短板强度。该强度用于排序“得分低且区分度较强”的指标，不能单独作为机制说明。",
        "",
    ]

    for lisa_col, lisa_label in LISA_GROUPS.items():
        sub = summary[summary["lisa_variable"] == lisa_col].copy()
        section_no = "二" if lisa_col == f"lisa_sdg_index_{LATEST_YEAR}_cluster" else "三"
        md.extend([f"## {section_no}、{lisa_label}维度短板", ""])
        table_rows = []
        for _, row in sub.iterrows():
            table_rows.append(
                [
                    row["lisa_cluster"],
                    str(int(row["count"])),
                    _pct(row["percentage"]),
                    _fmt(row[f"sdg_index_{LATEST_YEAR}_mean"]),
                    _fmt(row[f"change_rate_2010_{LATEST_YEAR}_mean"], 2),
                    _fmt(row["D1_score_mean"], 3),
                    _fmt(row["D2_score_mean"], 3),
                    _fmt(row["D3_score_mean"], 3),
                    _fmt(row["D4_score_mean"], 3),
                    row["primary_shortboard_dimension"],
                    row["primary_constraint_indicator"],
                ]
            )
        md.append(
            _markdown_table(
                table_rows,
                ["LISA类型", "网格数", "占比", "2024指数", "变化率", "D1", "D2", "D3", "D4", "主短板", "主约束指标"],
            )
        )
        md.append("")

        for _, row in sub.iterrows():
            cluster = row["lisa_cluster"]
            primary = row["primary_shortboard_dimension"]
            secondary = row["secondary_shortboard_dimension"]
            primary_detail = _detail_phrase(details, lisa_col, cluster, primary)
            secondary_detail = _detail_phrase(details, lisa_col, cluster, secondary)
            if lisa_col == f"lisa_change_rate_2010_{LATEST_YEAR}_cluster":
                prefix = "该类型表示变化趋势上的空间相关线索，不能解释为治理效果优劣。"
            else:
                prefix = "该类型表示当前综合水平的空间集聚或离群特征。"
            md.append(
                f"- **{cluster}：** {prefix}该类型区主短板为{primary}，次短板为{secondary}。"
                f"主短板内部，{primary_detail}；次短板内部，{secondary_detail}。"
            )
        md.append("")

    md.extend(
        [
            "## 四、论文写作边界",
            "",
            "1. 不以权重大小直接判定短板；权重只说明指标在样本空间差异中的区分度。",
            "2. 对变化率LISA，HH仅表示相对改善具有邻近集聚，LL仅表示改善不足或相对下降具有邻近集聚，不写成政策成败。",
            "3. LISA结果用于补充空间相关和集聚特征识别，不构成机制检验。",
        ]
    )
    output_path.write_text("\n".join(md) + "\n", encoding="utf-8")


def _validate(summary: pd.DataFrame, details: pd.DataFrame, lisa: gpd.GeoDataFrame, normalized: pd.DataFrame) -> None:
    expected_total = len(lisa)
    for lisa_col in LISA_GROUPS:
        total = int(summary[summary["lisa_variable"] == lisa_col]["count"].sum())
        if total != expected_total:
            raise AssertionError(f"{lisa_col} count sum {total} != {expected_total}")

        for _, row in summary[summary["lisa_variable"] == lisa_col].iterrows():
            subset = lisa[lisa[lisa_col] == row["lisa_cluster"]]
            for dim in ["D1", "D2", "D3", "D4"]:
                expected = subset[f"{dim}_score_{LATEST_YEAR}"].mean()
                actual = row[f"{dim}_score_mean"]
                if not np.isclose(expected, actual, equal_nan=True):
                    raise AssertionError(f"{lisa_col}/{row['lisa_cluster']}/{dim}: {actual} != {expected}")

    sample_indicator = "dist_port"
    range_path = DATA_DIR / "normalization_ranges.csv"
    ranges = pd.read_csv(range_path).set_index("indicator")
    raw = gpd.read_file(DATA_DIR / f"grid_indicators_{LATEST_YEAR}.gpkg", ignore_geometry=True)[sample_indicator].iloc[0]
    r = ranges.loc[sample_indicator]
    clipped = min(max(raw, r["global_min"]), r["global_max"])
    expected_norm = (r["global_max"] - clipped) / (r["global_max"] - r["global_min"])
    if not np.isclose(normalized[sample_indicator].iloc[0], expected_norm):
        raise AssertionError("Normalization check failed for dist_port")

    md = (PROGRESS_DIR / "lisa_dimension_shortboard_2026-05-12.md").read_text(encoding="utf-8")
    banned = ["快速增长", "衰退", "31248", "九指标", "政策成功", "政策失败", "因果机制"]
    for term in banned:
        if term in md:
            raise AssertionError(f"Banned term in markdown: {term}")


def main() -> None:
    print("=" * 60)
    print("LISA dimension shortboard analysis")
    print("=" * 60)
    lisa, indicators, weights, ranges = _load_inputs()
    normalized = _normalize_indicators(indicators, ranges)
    metadata = _indicator_metadata(weights)
    summary, details = _build_tables(lisa, indicators, normalized, metadata)

    summary_path = DATA_DIR / "lisa_dimension_shortboard_statistics.csv"
    details_path = DATA_DIR / "lisa_indicator_shortboard_details.csv"
    summary.to_csv(summary_path, index=False)
    details.to_csv(details_path, index=False)
    _write_markdown(summary, details)
    _validate(summary, details, lisa, normalized)

    print("Saved:")
    print(f"  {summary_path}")
    print(f"  {details_path}")
    print(f"  {PROGRESS_DIR / 'lisa_dimension_shortboard_2026-05-12.md'}")
    print("Validation passed.")


if __name__ == "__main__":
    main()
