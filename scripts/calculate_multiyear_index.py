#!/usr/bin/env python3
"""Calculate multiyear comparable SDG index with fixed entropy-TOPSIS weights."""

import geopandas as gpd
import numpy as np
import pandas as pd

from workflow_config import DATA_DIR, INDICATORS, TARGET_YEARS, year_label


CLIP_LOWER_Q = 0.01
CLIP_UPPER_Q = 0.99


def normalize_indicator_unified(series_dict, direction):
    all_values = pd.concat(series_dict.values()).dropna()
    if len(all_values) == 0:
        return {year: pd.Series(np.nan, index=series.index) for year, series in series_dict.items()}, np.nan, np.nan
    global_min = all_values.min()
    global_max = all_values.max()
    if np.isclose(global_min, global_max):
        return {year: pd.Series(0.5, index=series.index) for year, series in series_dict.items()}, global_min, global_max
    normalized = {}
    for year, series in series_dict.items():
        if direction == "positive":
            normalized[year] = (series - global_min) / (global_max - global_min)
        else:
            normalized[year] = (global_max - series) / (global_max - global_min)
    return normalized, global_min, global_max


def clip_indicator_unified(series_dict, config):
    """Clip outliers using all years together before normalization."""
    combined = pd.concat(series_dict.values()).dropna()
    if len(combined) == 0:
        return series_dict, {
            "raw_min": np.nan,
            "raw_max": np.nan,
            "p01": np.nan,
            "p99": np.nan,
            "clipped_min": np.nan,
            "clipped_max": np.nan,
            "clipped_low_cells": 0,
            "clipped_high_cells": 0,
            "clip_applied": False,
        }

    raw_min = combined.min()
    raw_max = combined.max()
    value_type = config.get("value_type", "continuous")
    if value_type == "ratio":
        lower, upper = 0.0, 1.0
        clip_applied = False
    else:
        lower = combined.quantile(CLIP_LOWER_Q)
        upper = combined.quantile(CLIP_UPPER_Q)
        clip_applied = not np.isclose(lower, upper)

    clipped = {}
    low_count = 0
    high_count = 0
    for year, series in series_dict.items():
        if value_type == "ratio":
            clipped_series = series.clip(lower=0, upper=1)
        elif clip_applied:
            low_count += int(series.lt(lower).sum())
            high_count += int(series.gt(upper).sum())
            clipped_series = series.clip(lower=lower, upper=upper)
        else:
            clipped_series = series.copy()
        clipped[year] = clipped_series

    clipped_combined = pd.concat(clipped.values()).dropna()
    return clipped, {
        "raw_min": raw_min,
        "raw_max": raw_max,
        "p01": lower,
        "p99": upper,
        "clipped_min": clipped_combined.min() if len(clipped_combined) else np.nan,
        "clipped_max": clipped_combined.max() if len(clipped_combined) else np.nan,
        "clipped_low_cells": low_count,
        "clipped_high_cells": high_count,
        "clip_applied": clip_applied,
    }


def calculate_entropy_weight(data):
    data = data.clip(lower=0) + 1e-6
    n, _ = data.shape
    k = 1 / np.log(n)
    data_sum = data.sum(axis=0)
    p = data / data_sum
    p_log = p.replace(0, 1e-10)
    entropy = -k * (p * np.log(p_log)).sum(axis=0)
    divergence = 1 - entropy
    if np.isclose(divergence.sum(), 0):
        weights = pd.Series(1 / data.shape[1], index=data.columns)
    else:
        weights = divergence / divergence.sum()
    return weights, entropy


def calculate_dimension_equal_weights(data, indicators):
    dimensions = {}
    for indicator in data.columns:
        dimensions.setdefault(indicators[indicator]["dimension"], []).append(indicator)

    dimension_weight = 1 / len(dimensions)
    final_weights = pd.Series(0.0, index=data.columns, dtype=float)
    entropy = pd.Series(np.nan, index=data.columns, dtype=float)
    local_weights = pd.Series(np.nan, index=data.columns, dtype=float)

    for _, cols in dimensions.items():
        local_data = data[cols]
        local_weight, local_entropy = calculate_entropy_weight(local_data)
        for col in cols:
            local_weights[col] = local_weight[col]
            entropy[col] = local_entropy[col]
            final_weights[col] = local_weight[col] * dimension_weight

    return final_weights, entropy, local_weights, dimensions


WEIGHT_SCHEME = "fixed_global_within_dimension_entropy_equal_dimension"


def calculate_topsis_fixed_ideal(normalized_data, weights):
    """TOPSIS with fixed normalized ideal points: best=1 and worst=0."""
    weights = weights.reindex(normalized_data.columns).fillna(0)
    weighted = normalized_data * weights
    ideal_best = weights
    ideal_worst = weights * 0
    dist_best = np.sqrt(((weighted - ideal_best) ** 2).sum(axis=1))
    dist_worst = np.sqrt(((weighted - ideal_worst) ** 2).sum(axis=1))
    denom = dist_best + dist_worst
    return dist_worst / denom.replace(0, np.nan)


def fill_for_model(df, fill_values=None):
    if fill_values is None:
        fill_values = df.median(numeric_only=True)
    filled = df.fillna(fill_values)
    return filled.fillna(0.5)


def dimension_id(label):
    return label.split()[0]


def calculate_dimension_scores(df_filled, local_weights, dimensions):
    scores = {}
    for dimension, cols in dimensions.items():
        dim = dimension_id(dimension)
        weights = local_weights.reindex(cols).fillna(1 / len(cols))
        scores[dim] = (df_filled[cols] * weights).sum(axis=1)
    return scores


def calculate_pipeline(data, use_clipping):
    source_values = {year: {} for year in TARGET_YEARS}
    normalized = {year: {} for year in TARGET_YEARS}
    norm_rows = []
    clip_rows = []

    for indicator, config in INDICATORS.items():
        raw_series_dict = {
            year: data[year][indicator] if indicator in data[year].columns else pd.Series(np.nan, index=data[year].index)
            for year in TARGET_YEARS
        }
        if use_clipping:
            series_dict, clip_info = clip_indicator_unified(raw_series_dict, config)
        else:
            series_dict = raw_series_dict
            combined = pd.concat(raw_series_dict.values()).dropna()
            clip_info = {
                "raw_min": combined.min() if len(combined) else np.nan,
                "raw_max": combined.max() if len(combined) else np.nan,
                "p01": np.nan,
                "p99": np.nan,
                "clipped_min": combined.min() if len(combined) else np.nan,
                "clipped_max": combined.max() if len(combined) else np.nan,
                "clipped_low_cells": 0,
                "clipped_high_cells": 0,
                "clip_applied": False,
            }
        normalized_dict, global_min, global_max = normalize_indicator_unified(series_dict, config["direction"])
        for year in TARGET_YEARS:
            source_values[year][indicator] = series_dict[year]
            normalized[year][indicator] = normalized_dict[year]
        norm_rows.append({
            "indicator": indicator,
            "description": config["description"],
            "direction": config["direction"],
            "global_min": global_min,
            "global_max": global_max,
            "clipping": "p01_p99" if use_clipping else "none",
        })
        clip_rows.append({
            "indicator": indicator,
            "description": config["description"],
            "value_type": config.get("value_type", "continuous"),
            **clip_info,
        })

    combined_norm = pd.concat(
        [pd.DataFrame(normalized[year]).assign(model_year=year) for year in TARGET_YEARS],
        ignore_index=True,
    )
    combined_indicators = combined_norm[list(INDICATORS)]
    global_fill_values = combined_indicators.median(numeric_only=True)
    combined_filled = fill_for_model(combined_indicators, global_fill_values)
    weights, entropies, local_weights, dimensions = calculate_dimension_equal_weights(combined_filled, INDICATORS)

    result = data[TARGET_YEARS[-1]][["geometry"]].copy()
    result["weight_scheme"] = WEIGHT_SCHEME + ("_p01_p99_clipped" if use_clipping else "_unclipped")
    missing_rows = []
    for year in TARGET_YEARS:
        df_norm = pd.DataFrame(normalized[year])
        missing_before = df_norm.isna().sum()
        df_filled = fill_for_model(df_norm, global_fill_values)
        result[f"sdg_index_{year}"] = calculate_topsis_fixed_ideal(df_filled, weights)
        result[f"weighted_sum_{year}"] = (df_filled * weights).sum(axis=1)
        for dim, score in calculate_dimension_scores(df_filled, local_weights, dimensions).items():
            result[f"{dim}_score_{year}"] = score
        for indicator, count in missing_before.items():
            missing_rows.append({"year": year, "indicator": indicator, "missing_cells": int(count)})

    return {
        "result": result,
        "normalized": normalized,
        "norm_rows": norm_rows,
        "clip_rows": clip_rows,
        "weights": weights,
        "entropies": entropies,
        "local_weights": local_weights,
        "dimensions": dimensions,
        "missing_rows": missing_rows,
        "global_fill_values": global_fill_values,
    }


def main():
    print("=" * 60)
    print(f"Multiyear SDG index: {year_label()}")
    print("=" * 60)

    data = {}
    for year in TARGET_YEARS:
        path = DATA_DIR / f"grid_indicators_{year}.gpkg"
        if not path.exists():
            raise FileNotFoundError(path)
        data[year] = gpd.read_file(path)
        print(f"Loaded {year}: {len(data[year])} cells")

    print("\nUnified clipping + normalization")
    clipped = calculate_pipeline(data, use_clipping=True)
    unclipped = calculate_pipeline(data, use_clipping=False)
    normalized = clipped["normalized"]
    fixed_weights = clipped["weights"]
    fixed_entropies = clipped["entropies"]
    fixed_local_weights = clipped["local_weights"]
    dimensions = clipped["dimensions"]
    global_fill_values = clipped["global_fill_values"]
    for row in clipped["norm_rows"]:
        print(f"  {row['indicator']}: min={row['global_min']}, max={row['global_max']}")

    pd.DataFrame(clipped["norm_rows"]).to_csv(DATA_DIR / "normalization_ranges.csv", index=False)
    pd.DataFrame(clipped["clip_rows"]).to_csv(DATA_DIR / "outlier_clip_ranges.csv", index=False)
    pd.DataFrame(unclipped["norm_rows"]).to_csv(DATA_DIR / "normalization_ranges_unclipped.csv", index=False)

    print("\nFixed global within-dimension entropy weights; dimensions equal-weighted")
    print(f"  fixed global: weight sum={fixed_weights.sum():.6f}")

    fixed_weight_rows = []
    for indicator in INDICATORS:
        dimension = INDICATORS[indicator]["dimension"]
        fixed_weight_rows.append({
            "year": "all_years",
            "weight_scheme": WEIGHT_SCHEME,
            "indicator": indicator,
            "description": INDICATORS[indicator]["description"],
            "dimension": dimension,
            "dimension_weight": 1 / len(dimensions),
            "entropy": float(fixed_entropies[indicator]),
            "local_weight": float(fixed_local_weights[indicator]),
            "weight": float(fixed_weights[indicator]),
        })

    weights_df = pd.DataFrame(fixed_weight_rows)
    weight_path = DATA_DIR / "weights_multiyear.csv"
    weights_df.to_csv(weight_path, index=False)
    fixed_weight_path = DATA_DIR / "fixed_weights_multiyear.csv"
    weights_df.to_csv(fixed_weight_path, index=False)
    print(f"Saved fixed weights: {weight_path}")
    print(f"Saved fixed weights copy: {fixed_weight_path}")

    diagnostic_weight_rows = []
    print("\nDiagnostic only: year-specific within-dimension entropy weights")
    for year in TARGET_YEARS:
        df_year = fill_for_model(pd.DataFrame(normalized[year]))
        yearly_weights, entropies, local_weights, yearly_dimensions = calculate_dimension_equal_weights(df_year, INDICATORS)
        print(f"  {year}: diagnostic weight sum={yearly_weights.sum():.6f}")
        for indicator in INDICATORS:
            dimension = INDICATORS[indicator]["dimension"]
            diagnostic_weight_rows.append({
                "year": year,
                "weight_scheme": "diagnostic_year_specific_within_dimension_entropy_equal_dimension",
                "indicator": indicator,
                "description": INDICATORS[indicator]["description"],
                "dimension": dimension,
                "dimension_weight": 1 / len(yearly_dimensions),
                "entropy": float(entropies[indicator]),
                "local_weight": float(local_weights[indicator]),
                "weight": float(yearly_weights[indicator]),
            })

    yearly_diag_path = DATA_DIR / "weights_multiyear_diagnostic_yearly.csv"
    pd.DataFrame(diagnostic_weight_rows).to_csv(yearly_diag_path, index=False)
    print(f"Saved diagnostic yearly weights: {yearly_diag_path}")

    result = clipped["result"]
    missing_rows = clipped["missing_rows"]
    print("\nTOPSIS index with fixed best=1 and worst=0 normalized ideals")
    for year in TARGET_YEARS:
        s = result[f"sdg_index_{year}"]
        print(f"  {year}: valid={s.notna().sum()}, mean={s.mean():.4f}, range=[{s.min():.4f}, {s.max():.4f}]")

    pd.DataFrame(missing_rows).to_csv(DATA_DIR / "missing_cells_multiyear.csv", index=False)

    sensitivity = []
    for year in TARGET_YEARS:
        score = result[f"sdg_index_{year}"]
        weighted = result[f"weighted_sum_{year}"]
        equal_weight = fill_for_model(pd.DataFrame(normalized[year]), global_fill_values).mean(axis=1)
        sensitivity.append({
            "year": year,
            "weight_scheme": WEIGHT_SCHEME,
            "pearson_topsis_weighted_sum": score.corr(weighted),
            "spearman_topsis_weighted_sum": score.corr(weighted, method="spearman"),
            "pearson_topsis_equal_weight": score.corr(equal_weight),
            "spearman_topsis_equal_weight": score.corr(equal_weight, method="spearman"),
        })
    sensitivity_path = DATA_DIR / "sensitivity_analysis.csv"
    pd.DataFrame(sensitivity).to_csv(sensitivity_path, index=False)

    unclipped_result = unclipped["result"]
    clip_compare = []
    for year in TARGET_YEARS:
        clip_compare.append({
            "year": year,
            "pearson_clipped_unclipped": result[f"sdg_index_{year}"].corr(unclipped_result[f"sdg_index_{year}"]),
            "spearman_clipped_unclipped": result[f"sdg_index_{year}"].corr(
                unclipped_result[f"sdg_index_{year}"], method="spearman"
            ),
            "clipped_mean": result[f"sdg_index_{year}"].mean(),
            "unclipped_mean": unclipped_result[f"sdg_index_{year}"].mean(),
        })
    clip_compare_path = DATA_DIR / "outlier_clipping_sensitivity.csv"
    pd.DataFrame(clip_compare).to_csv(clip_compare_path, index=False)

    output_path = DATA_DIR / "grid_sdg_multiyear.gpkg"
    result.to_file(output_path, driver="GPKG")
    csv_path = DATA_DIR / "grid_sdg_multiyear.csv"
    result.drop(columns=["geometry"]).to_csv(csv_path, index=False)
    unclipped_path = DATA_DIR / "grid_sdg_multiyear_unclipped_sensitivity.gpkg"
    unclipped_result.to_file(unclipped_path, driver="GPKG")
    unclipped_csv_path = DATA_DIR / "grid_sdg_multiyear_unclipped_sensitivity.csv"
    unclipped_result.drop(columns=["geometry"]).to_csv(unclipped_csv_path, index=False)

    print("\nComplete")
    print(f"  {output_path}")
    print(f"  {csv_path}")
    print(f"  {weight_path}")
    print(f"  {fixed_weight_path}")
    print(f"  {yearly_diag_path}")
    print(f"  {sensitivity_path}")
    print(f"  {clip_compare_path}")
    print(f"  {unclipped_path}")


if __name__ == "__main__":
    main()
