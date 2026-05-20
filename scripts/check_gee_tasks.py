#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查GEE导出任务状态
"""

import ee
import json
import os
from pathlib import Path
from datetime import datetime
from workflow_config import GEE_MULTIYEAR_DIR, TARGET_YEARS, YEAR_MAPPING, year_label

# 初始化GEE
try:
    project_id = os.environ.get('EARTHENGINE_PROJECT', 'sdgs-china-russia-border')
    ee.Initialize(project=project_id, opt_url='https://earthengine-highvolume.googleapis.com')
except Exception as e:
    print(f"[错误] GEE认证失败: {e}")
    print("请运行: python -c \"import ee; ee.Authenticate()\"")
    print("或设置环境变量: export EARTHENGINE_PROJECT=your-project-id")
    exit(1)

def check_tasks():
    """检查所有GEE任务状态"""
    print("=" * 60)
    print("GEE任务状态检查")
    print("=" * 60)
    print(f"目标年份: {year_label()}")
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 获取所有任务
    tasks = ee.batch.Task.list()

    expected = set()
    for year in TARGET_YEARS:
        pop_year = YEAR_MAPPING[year]['pop']
        expected.add(f'I1_1_population_density_{pop_year}')
        viirs_year = YEAR_MAPPING[year]['viirs']
        if viirs_year is not None:
            expected.add(f'I2_1_nightlight_intensity_{viirs_year}')
        modis_year = YEAR_MAPPING[year]['modis']
        expected.add(f'I4_2_natural_cover_{modis_year}')
        expected.add(f'I5_2_built_density_{modis_year}')
        ndvi_year = YEAR_MAPPING[year]['ndvi']
        expected.add(f'I4_1_NDVI_{ndvi_year}')
        climate_year = YEAR_MAPPING[year]['climate']
        expected.add(f'I6_1_climate_water_deficit_{climate_year}')
    expected.add('I5_1_slope_static')

    # 只过滤当前主线预期任务，避免旧实验失败任务污染状态判断。
    sdgs_tasks = [t for t in tasks if t.config.get('description', '') in expected]

    if not sdgs_tasks:
        print("未找到SDGs相关任务")
        return

    # 统计各状态任务数
    status_count = {}
    for task in sdgs_tasks:
        state = task.status()['state']
        status_count[state] = status_count.get(state, 0) + 1

    print(f"任务总数: {len(sdgs_tasks)}")
    print(f"状态统计: {status_count}\n")

    # 显示每个任务详情
    print("-" * 60)
    ordered = sorted(sdgs_tasks, key=lambda t: (t.status()['state'], t.config.get('description', '')))
    for i, task in enumerate(ordered[:40], 1):
        status = task.status()
        desc = task.config.get('description', 'Unknown')
        state = status['state']

        # 状态图标
        icon = {
            'READY': '⏳',
            'RUNNING': '▶️',
            'COMPLETED': '✅',
            'FAILED': '❌',
            'CANCELLED': '🚫'
        }.get(state, '❓')

        print(f"{i:2d}. [{icon}] {desc:30s} - {state}")

        # 如果失败，显示错误信息
        if state == 'FAILED' and 'error_message' in status:
            print(f"     错误: {status['error_message']}")

    if len(sdgs_tasks) > 40:
        print(f"\n... 还有 {len(sdgs_tasks) - 40} 个任务未显示")

    print("-" * 60)

    # 给出建议
    if status_count.get('COMPLETED', 0) == len(sdgs_tasks):
        print("\n所有任务已完成！")
        print(f"下一步: 从Google Drive下载数据到本地 {GEE_MULTIYEAR_DIR}")
    elif status_count.get('FAILED', 0) > 0:
        print(f"\n警告: {status_count['FAILED']} 个任务失败")
        print("建议: 检查失败原因并重新提交")
    elif status_count.get('RUNNING', 0) > 0:
        print(f"\n{status_count['RUNNING']} 个任务正在运行中...")
        print("建议: 等待5-10分钟后再次检查")
    else:
        print("\n任务正在队列中等待...")
        print("建议: 等待5-10分钟后再次检查")

if __name__ == '__main__':
    check_tasks()
