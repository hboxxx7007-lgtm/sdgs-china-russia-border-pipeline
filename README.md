# 中国东北-俄罗斯远东跨境区域SDGs空间支撑条件评估与发展对策

本科毕业论文项目。详细流程说明见 [项目流程说明.md](项目流程说明.md)。

## 快速复现

```bash
source .venv312/bin/activate
python scripts/generate_10km_grid.py
FORCE_GEE_EXPORT=1 python scripts/gee_download_multiyear.py
python scripts/check_gee_tasks.py
python scripts/calculate_multiyear_indicators.py
python scripts/calculate_multiyear_index.py
python scripts/analyze_trends_and_hotspots.py
python scripts/analyze_esda_spatial_clustering.py
python scripts/analyze_lisa_dimension_shortboards.py
python scripts/add_admin_grouping.py
python scripts/generate_quality_report.py
```

## 关键口径

- 四期：2010/2015/2020/2024 | 网格：10km | 投影：ESRI:102025
- 四维十二指标：D1人类活动/D2通达性/D3生态状态/D4环境本底
- 2010年夜光→2012年VIIRS近似替代 | 2024年人口→2020基线
- ESDA空间集聚（LISA）≠Gi*空间统计检验

---

*最后更新：2026-05-20*
