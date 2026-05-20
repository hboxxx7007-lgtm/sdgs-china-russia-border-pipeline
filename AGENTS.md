# Codex 自动推进入口

本项目是本科毕业论文/设计工作区。Codex 接手时，必须先按本文件和 `scripts/workflow_config.py` 的统一配置推进，不要从旧 OSM 路线、旧 `2000/2010/2020` 路线或单期轻量化路线直接开始。

## 必读顺序

1. `scripts/workflow_config.py`
   - 确认目标年份、投影、数据目录、指标字段和年份映射。
2. `output/progress/environment_check_2026-05-07.md`
   - 确认 Python、GEE、QGIS、投影和依赖环境。
3. `output/progress/review_gate_P0_2026-05-07.md`
   - 确认本科难度、数据可得性和误导风险边界。
4. `RESEARCH_MAINLINE.md`
   - 了解研究主线、方法链、最终产物和论文写作边界。
5. `CLAUDE_SKILL_EXECUTION_FRAMEWORK.md`
   - 了解 skill、脚本链、阶段门禁和执行顺序。
6. `output/progress/current_status.md`
   - 了解当前进展和下一步。
7. `output/progress/revised_methodology.md`
   - 确认第二章方法论口径。

## 当前唯一主线

最终实证路线采用：

```text
2010/2015/2020/2024 四期年度或准年度空间数据
→ 10km 网格指标计算
→ 全时期合并极差标准化
→ 逐年维度内熵权法与维度间等权
→ TOPSIS 相对贴近度 SDG 综合指数
→ 阶段变化、年均变化、空间相关性与热点类型区识别
→ GADM 国别/省州分组统计与跨境差异解释
→ QGIS 正式制图与论文写作
```

论文表述为“2010年以来至近年”，不把 2025 写成完整模型年份。当前模型最新完整年份为 2024；2025 只作为后续数据更新方向。

## 数据和投影规范

- 原始数据存储、GEE 裁剪边界和 Web 预览使用 `EPSG:4326`。
- 面积、距离、网格尺度、口岸距离和 QGIS 正式制图使用 `ESRI:102025`（Asia North Albers Equal Area Conic）。
- 不使用 `EPSG:3857` 做面积、距离或网格尺度分析。
- 2010 模型年夜光采用 2012 年 VIIRS 数据作为起始期近似替代，必须披露，不能解释为 2010 年实测值。
- 2024 年人口采用 2020 人口基线，必须在质量报告和论文方法中说明。
- 气候水分亏缺采用 TerraClimate 年累计 `def` 指标，作为气候韧性/水分胁迫的负向代理指标。
- 行政分组优先使用 GADM 4.1 ADM1，按 10km 网格质心匹配；未匹配网格单列说明。

## 最终指标体系

- D1 社会经济活力：`pop_density` 人口密度（正向）、`nightlight` 夜间灯光强度（正向）。
- D2 建设与区位联通：`builtup_ratio` 建成区密度（正向）、`dist_port` 距边境口岸距离（负向）。
- D3 生态环境质量：`ndvi` NDVI（正向）、`natural_cover_ratio` 自然覆盖率（正向）。
- D4 自然约束与气候韧性：`slope` 地形坡度（负向）、`climate_water_stress` 气候水分亏缺（负向）。

旧字段 `dist_city`、`road_density`、`pop_concentration`、`built_connectivity` 只作历史流程验证、方法审查或附录说明，不进入最终论文结论。

## 自动推进顺序

### P0：环境、文档和脚本对齐

1. 使用 `.venv312/bin/python`，不要依赖系统 `python`。
2. 运行 `scripts/check_environment.py`。
3. 确认 `scripts/workflow_config.py` 中的 `TARGET_YEARS = [2010, 2015, 2020, 2024]`、`METRIC_CRS = "ESRI:102025"`。
4. 运行 `scripts/generate_10km_grid.py`，确保 `output/data/study_area_grid_10km.gpkg` 由 `output/data/study_area_no_holes.gpkg` 在 `ESRI:102025` 下生成，且只保留质心落在去洞研究区内的 10km 网格。
5. 检查多年份脚本是否全部从统一配置读取年份、指标和路径。

### P1：数据链执行

```bash
source .venv312/bin/activate
export EARTHENGINE_PROJECT=sdgs-china-russia-border
python scripts/generate_10km_grid.py
FORCE_GEE_EXPORT=1 python scripts/gee_download_multiyear.py
python scripts/check_gee_tasks.py
```

GEE 导出完成并将 GeoTIFF 放入 `output/data/gee_multiyear/` 后运行：

```bash
python scripts/calculate_multiyear_indicators.py
python scripts/calculate_multiyear_index.py
python scripts/analyze_trends_and_hotspots.py
python scripts/add_admin_grouping.py
python scripts/generate_quality_report.py
python scripts/create_qgis_project.py
```

### P2：论文结果写作

只有最终四期指标、综合指数、趋势分析、质量报告和 QGIS 工程都生成并复核后，才能撰写第三、四、五、六章的确定性实证结论。

## 每步评审门禁

每次细致落实前都要快速检查：

1. 本科风格是否合适，是否过度复杂。
2. 数据是否真实可得，年份映射是否诚实。
3. 投影、分辨率和预处理是否规范。
4. 结果是否能够被图表和统计支撑。
5. 结论是否可能误导，尤其是缺失值和旧结果。

## 禁止事项

- 不要把旧 `grid_sdg_index.gpkg`、旧单期脚本输出或旧 `2000-2020` 图表当成终稿结论。
- 不要基于旧 OSM 样本写最终结论。
- 不要编造空间格局、热点类型区、分区结论。
- 不要删除学校模板、原始研究区数据、参考文献 PDF、开题报告和核心脚本。
- 不要把 2024 人口基线解释为 2024 年人口观测值。
- 不要把 2012 夜光近似替代解释为 2010 年实测观测值。
