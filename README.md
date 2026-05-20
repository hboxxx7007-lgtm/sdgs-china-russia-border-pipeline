# 中俄东北-远东经济走廊 SDGs 时空演变研究

本工作区用于管理本科毕业论文/设计项目：**中俄东北-远东经济走廊 SDGs 时空演变与协同发展研究**。

当前唯一主线为 `2010/2015/2020/2024` 四期 10km 网格评价：

```text
去洞研究区
→ ESRI:102025 下生成 10km 网格
→ GEE 四期年度或准年度遥感数据
→ 网格指标计算
→ 全时期合并极差标准化
→ 逐年无约束熵权法
→ TOPSIS 相对贴近度 SDG 综合指数
→ 趋势、热点类型区、GADM 国别/省州分组统计
→ QGIS 正式制图
→ 论文第三至六章据实写作
```

## 快速入口

- 📋 **项目结构说明**：`项目结构说明.md`  ⬅️ 新！查看完整项目组织
- 📋 **项目规则**：`AGENTS.md`
- 📋 **研究主线**：`RESEARCH_MAINLINE.md`
- 📋 **执行框架**：`CLAUDE_SKILL_EXECUTION_FRAMEWORK.md`
- 📋 **核心配置**：`scripts/workflow_config.py`

## 环境

固定使用项目虚拟环境：

```bash
source .venv312/bin/activate
python scripts/check_environment.py
```

后续脚本不要依赖系统 `python`。QGIS/GDAL 相关命令在 macOS 上通常需要：

```bash
export PROJ_LIB=/Applications/QGIS.app/Contents/Resources/qgis/proj
```

## 常用复现命令

```bash
source .venv312/bin/activate
python scripts/generate_10km_grid.py
python scripts/calculate_multiyear_indicators.py
python scripts/calculate_multiyear_index.py
python scripts/analyze_trends_and_hotspots.py
python scripts/add_admin_grouping.py
python scripts/generate_quality_report.py
python scripts/create_qgis_project.py
```

如需重新从 GEE 导出数据：

```bash
source .venv312/bin/activate
export EARTHENGINE_PROJECT=sdgs-china-russia-border
FORCE_GEE_EXPORT=1 python scripts/gee_download_multiyear.py
python scripts/check_gee_tasks.py
```

## 关键口径

- 2010 模型年夜光使用 2012 年 VIIRS 起始期近似替代，不能写成 2010 年实测夜光。
- 2024 年人口指标沿用 2020 人口基线，不能写成 2024 年实测人口。
- 面积、距离、网格尺度、口岸距离和 QGIS 正式制图使用 `ESRI:102025`。
- 原始数据、GEE 导出边界和 Web 预览使用 `EPSG:4326`。
- 热点类型区是"发展水平 × 变化趋势"的描述性分位数分类，不是 Getis-Ord Gi* 等空间统计热点检验。

## 目录结构（2026-05-16 更新）

```text
毕业/
├── 📄 项目结构说明.md           ⭐ 查看此文件了解完整组织
├── 📄 AGENTS.md                 项目规则和自动推进入口
├── 📄 RESEARCH_MAINLINE.md      研究主线
├── 📄 CLAUDE_SKILL_EXECUTION_FRAMEWORK.md 执行框架
├── 📄 README.md                 本文件
│
├── 📂 scripts/                  核心Python脚本（37个）
│   ├── workflow_config.py       配置文件
│   ├── check_environment.py     环境检查
│   ├── generate_10km_grid.py    生成网格
│   ├── calculate_multiyear_indicators.py 计算指标
│   ├── calculate_multiyear_index.py 计算SDG指数
│   ├── analyze_trends_and_hotspots.py 趋势热点分析
│   └── ... [其他脚本]
│
├── 📂 data/                     ⭐ 所有数据（完整保留）
│   ├── accessibility/           可达性数据
│   ├── admin_boundaries/        行政区划
│   ├── cartographic_base/       制图基础数据
│   ├── gee_multiyear/           GEE下载的GeoTIFF
│   ├── results/                 分析结果CSV
│   ├── *.gpkg                   网格、指数、趋势等空间数据
│   └── *.csv                    统计结果
│
├── 📂 thesis/                   论文资源
│   └── chapter4_assets/         第4章图件和说明
│
├── 📂 arcmap_package/           ArcGIS制图包
├── 📂 qgis_package/             QGIS制图包
│
├── 📂 毕设文件2025版参考模板/    ⭐ 学校模板（完整保留）
│   ├── 附件1-15.docx            任务书、开题、论文模板等
│   └── ...
│
├── 📂 参考文献/                 ⭐ 参考文献PDF（完整保留）
│
├── 📂 workplace/                ArcGIS工作区
│
└── 📄 [论文文件.docx]
```

---

*项目最后整理：2026-05-16*
