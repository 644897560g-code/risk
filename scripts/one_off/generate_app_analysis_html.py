"""
生成完整应用分析HTML报告

包含所有2272个样本的全部应用分析结果，按风险类别分类展示
"""

import pandas as pd
import json
import os
from collections import defaultdict

def generate_html_report():
    """生成HTML报告"""

    # 1. 读取所有数据
    print("读取数据...")

    # 读取完整分析结果
    with open('outputs/app_analysis/app_analysis_summary.json', 'r', encoding='utf-8') as f:
        summary = json.load(f)

    # 读取LLM分类结果
    with open('outputs/app_analysis/app_classification_result.json', 'r', encoding='utf-8') as f:
        classification = json.load(f)

    # 读取三类应用列表
    good_only_df = pd.read_csv('outputs/app_analysis/good_only_apps.csv')
    high_risk_df = pd.read_csv('outputs/app_analysis/high_risk_apps.csv')
    common_df = pd.read_csv('outputs/app_analysis/common_apps.csv')

    # 读取分类详情
    classification_df = pd.read_csv('outputs/app_analysis/app_classification_by_category.csv')

    classifications = classification.get('classifications', {})

    print(f"数据加载完成:")
    print(f"  好客户独有应用: {len(good_only_df)} 个")
    print(f"  坏客户独有应用: {len(high_risk_df)} 个")
    print(f"  共有应用: {len(common_df)} 个")
    print(f"  LLM分类应用: {len(classifications)} 个")

    # 2. 对所有应用进行分类
    print("\n对所有应用进行分类...")

    # 创建应用 -> 类别映射
    app_category_map = {}
    for _, row in classification_df.iterrows():
        app_category_map[row['app']] = {
            'category': row['category'],
            'confidence': row['confidence'],
            'reason': row['reason']
        }

    # 3. 按类别统计
    category_stats = defaultdict(lambda: {
        'apps': [],
        'good_count': 0,
        'bad_count': 0,
        'total_count': 0
    })

    # 处理坏客户独有应用
    bad_only_classified = 0
    bad_only_unclassified = 0

    for _, row in high_risk_df.iterrows():
        app = row['app']
        bad_count = int(row['bad_count'])

        if app in app_category_map:
            cat = app_category_map[app]['category']
            category_stats[cat]['apps'].append({
                'app': app,
                'bad_count': bad_count,
                'good_count': 0,
                'total_count': bad_count,  # 坏客户独有，total = bad
                'confidence': app_category_map[app]['confidence'],
                'reason': app_category_map[app]['reason']
            })
            category_stats[cat]['bad_count'] += bad_count
            category_stats[cat]['total_count'] += bad_count
            bad_only_classified += 1
        else:
            category_stats['unknown']['apps'].append({
                'app': app,
                'bad_count': bad_count,
                'good_count': 0,
                'total_count': bad_count,
                'confidence': 'N/A',
                'reason': '未分类应用'
            })
            category_stats['unknown']['bad_count'] += bad_count
            category_stats['unknown']['total_count'] += bad_count
            bad_only_unclassified += 1

    # 处理共有应用
    common_classified = 0
    for _, row in common_df.iterrows():
        app = row['app']
        good_count = int(row.get('good_count', 0))
        bad_count = int(row.get('bad_count', 0))
        total_count = good_count + bad_count

        if app in app_category_map:
            cat = app_category_map[app]['category']
            category_stats[cat]['apps'].append({
                'app': app,
                'good_count': good_count,
                'bad_count': bad_count,
                'total_count': total_count,
                'confidence': app_category_map[app]['confidence'],
                'reason': app_category_map[app]['reason']
            })
            category_stats[cat]['good_count'] += good_count
            category_stats[cat]['bad_count'] += bad_count
            category_stats[cat]['total_count'] += total_count
            common_classified += 1

    # 处理好客户独有应用
    good_only_classified = 0
    for _, row in good_only_df.iterrows():
        app = row['app']
        good_count = int(row.get('good_count', 0))

        if app in app_category_map:
            cat = app_category_map[app]['category']
            category_stats[cat]['apps'].append({
                'app': app,
                'good_count': good_count,
                'bad_count': 0,
                'total_count': good_count,  # 好客户独有，total = good
                'confidence': app_category_map[app]['confidence'],
                'reason': app_category_map[app]['reason']
            })
            category_stats[cat]['good_count'] += good_count
            category_stats[cat]['total_count'] += good_count
            good_only_classified += 1

    print(f"\n分类统计:")
    for cat, stats in sorted(category_stats.items(), key=lambda x: x[1]['total_count'], reverse=True):
        print(f"  {cat}: {len(stats['apps'])} 个应用，总安装{stats['total_count']}次")

    # 4. 定义高风险类别
    high_risk_categories = ['cash_loan', 'fintech_lending', 'gambling', 'installment']

    # 5. 生成HTML
    print("\n生成HTML报告...")

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>印尼现金贷应用分析报告 - 2272个样本</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border-radius: 8px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 32px;
            margin-bottom: 10px;
        }}
        .header .subtitle {{
            font-size: 16px;
            opacity: 0.9;
        }}
        .summary {{
            padding: 30px 40px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .summary-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}
        .summary-card .label {{
            color: #6c757d;
            font-size: 14px;
            margin-bottom: 8px;
        }}
        .summary-card .value {{
            color: #212529;
            font-size: 28px;
            font-weight: bold;
        }}
        .section {{
            padding: 30px 40px;
            border-bottom: 1px solid #e9ecef;
        }}
        .section:last-child {{
            border-bottom: none;
        }}
        .section h2 {{
            font-size: 24px;
            margin-bottom: 20px;
            color: #333;
        }}
        .insight-box {{
            background: #e7f3ff;
            border-left: 4px solid #2196F3;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .insight-box.good {{
            background: #e8f5e9;
            border-left-color: #4CAF50;
        }}
        .insight-box.bad {{
            background: #ffebee;
            border-left-color: #f44336;
        }}
        .insight-box h3 {{
            font-size: 18px;
            margin-bottom: 10px;
        }}
        .category-section {{
            margin: 30px 0;
        }}
        .category-header {{
            background: #f8f9fa;
            padding: 15px 20px;
            border-radius: 6px;
            margin-bottom: 15px;
        }}
        .category-header h3 {{
            font-size: 20px;
            margin-bottom: 5px;
        }}
        .category-header .meta {{
            color: #6c757d;
            font-size: 14px;
        }}
        .category-header.high-risk {{
            background: #ffebee;
            border: 1px solid #ffcdd2;
        }}
        .category-header.high-risk h3 {{
            color: #c62828;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        thead th {{
            background: #f8f9fa;
            padding: 12px 15px;
            text-align: left;
            font-weight: 600;
            color: #495057;
            border-bottom: 2px solid #dee2e6;
            font-size: 14px;
        }}
        tbody td {{
            padding: 12px 15px;
            border-bottom: 1px solid #e9ecef;
            font-size: 14px;
        }}
        tbody tr:hover {{
            background: #f8f9fa;
        }}
        .app-name {{
            font-family: monospace;
            font-size: 13px;
            color: #495057;
        }}
        .confidence-badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }}
        .confidence-badge.high {{
            background: #d4edda;
            color: #155724;
        }}
        .confidence-badge.medium {{
            background: #fff3cd;
            color: #856404;
        }}
        .confidence-badge.low {{
            background: #f8d7da;
            color: #721c24;
        }}
        .count-badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 13px;
            font-weight: 500;
            margin-right: 8px;
        }}
        .count-badge.good {{
            background: #d4edda;
            color: #155724;
        }}
        .count-badge.bad {{
            background: #f8d7da;
            color: #721c24;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #6c757d;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>印尼现金贷应用分析报告</h1>
            <div class="subtitle">基于2272个样本的完整应用分析 | LLM科学分类</div>
        </div>

        <div class="summary">
            <h2 style="margin-bottom: 15px;">样本概览</h2>
            <div class="summary-grid">
                <div class="summary-card">
                    <div class="label">总样本数</div>
                    <div class="value">{summary['total_samples']}</div>
                </div>
                <div class="summary-card">
                    <div class="label">好客户数</div>
                    <div class="value">{summary['good_customers']}</div>
                </div>
                <div class="summary-card">
                    <div class="label">坏客户数</div>
                    <div class="value">{summary['bad_customers']}</div>
                </div>
                <div class="summary-card">
                    <div class="label">逾期率</div>
                    <div class="value">{summary['bad_customers']/summary['total_samples']*100:.2f}%</div>
                </div>
            </div>
            <div class="summary-grid" style="margin-top: 20px;">
                <div class="summary-card">
                    <div class="label">好客户应用记录</div>
                    <div class="value">{summary['good_app_records']:,}</div>
                </div>
                <div class="summary-card">
                    <div class="label">坏客户应用记录</div>
                    <div class="value">{summary['bad_app_records']:,}</div>
                </div>
                <div class="summary-card">
                    <div class="label">独立应用总数</div>
                    <div class="value">{summary['unique_apps']['total']:,}</div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>关键洞察</h2>
            <div class="insight-box good">
                <h3>✓ 好客户应用特征</h3>
                <p>{classification['summary']['good_only_summary']}</p>
            </div>
            <div class="insight-box bad">
                <h3>⚠ 坏客户应用特征</h3>
                <p>{classification['summary']['bad_apps_summary']}</p>
            </div>
            <div class="insight-box">
                <h3>💡 核心发现</h3>
                <p>{classification['summary']['key_insights']}</p>
            </div>
        </div>

        <div class="section">
            <h2>应用类别分布</h2>
"""

    # 生成类别统计表格
    html_content += """
            <table>
                <thead>
                    <tr>
                        <th style="width: 200px;">类别</th>
                        <th style="width: 120px;">应用数量</th>
                        <th style="width: 120px;">好客户安装</th>
                        <th style="width: 120px;">坏客户安装</th>
                        <th style="width: 120px;">总安装数</th>
                        <th>风险等级</th>
                    </tr>
                </thead>
                <tbody>
"""

    risk_categories = ['cash_loan', 'fintech_lending', 'gambling', 'installment']

    for cat in sorted(category_stats.keys(), key=lambda x: category_stats[x]['total_count'], reverse=True):
        stats = category_stats[cat]
        is_risk = cat in risk_categories
        risk_label = '<span style="color: #c62828; font-weight: bold;">⚠ 高风险</span>' if is_risk else '普通'

        html_content += f"""
                    <tr>
                        <td><strong>{cat}</strong></td>
                        <td>{len(stats['apps'])}</td>
                        <td>{stats['good_count']}</td>
                        <td>{stats['bad_count']}</td>
                        <td>{stats['total_count']}</td>
                        <td>{risk_label}</td>
                    </tr>
"""

    html_content += """
                </tbody>
            </table>
        </div>
"""

    # 生成每个高风险类别的详细列表
    html_content += """
        <div class="section">
            <h2>高风险应用详细列表</h2>
"""

    for cat in risk_categories:
        if cat in category_stats and len(category_stats[cat]['apps']) > 0:
            stats = category_stats[cat]
            # 按坏客户安装数排序
            sorted_apps = sorted(stats['apps'], key=lambda x: x['bad_count'], reverse=True)

            html_content += f"""
            <div class="category-section">
                <div class="category-header high-risk">
                    <h3>⚠ {cat} 类别</h3>
                    <div class="meta">共 {len(sorted_apps)} 个应用，坏客户安装 {stats['bad_count']} 次，好客户安装 {stats['good_count']} 次</div>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th style="width: 50px;">#</th>
                            <th>应用包名</th>
                            <th style="width: 120px;">好客户安装</th>
                            <th style="width: 120px;">坏客户安装</th>
                            <th style="width: 120px;">LLM置信度</th>
                            <th>分类理由</th>
                        </tr>
                    </thead>
                    <tbody>
"""

            for i, app_info in enumerate(sorted_apps, 1):
                confidence_class = app_info['confidence'].lower()
                html_content += f"""
                        <tr>
                            <td>{i}</td>
                            <td><span class="app-name">{app_info['app']}</span></td>
                            <td><span class="count-badge good">{app_info['good_count']}</span></td>
                            <td><span class="count-badge bad">{app_info['bad_count']}</span></td>
                            <td><span class="confidence-badge {confidence_class}">{app_info['confidence']}</span></td>
                            <td>{app_info['reason']}</td>
                        </tr>
"""

            html_content += """
                    </tbody>
                </table>
            </div>
"""

    # 添加其他类别（非高风险）
    html_content += """
        <div class="section">
            <h2>其他应用类别</h2>
"""

    other_categories = [cat for cat in category_stats.keys() if cat not in risk_categories and cat != 'unknown']

    for cat in sorted(other_categories, key=lambda x: category_stats[x]['total_count'], reverse=True):
        stats = category_stats[cat]
        sorted_apps = sorted(stats['apps'], key=lambda x: x['total_count'], reverse=True)

        html_content += f"""
            <div class="category-section">
                <div class="category-header">
                    <h3>{cat} 类别</h3>
                    <div class="meta">共 {len(sorted_apps)} 个应用，总安装 {stats['total_count']} 次</div>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th style="width: 50px;">#</th>
                            <th>应用包名</th>
                            <th style="width: 120px;">好客户安装</th>
                            <th style="width: 120px;">坏客户安装</th>
                            <th style="width: 120px;">LLM置信度</th>
                            <th>分类理由</th>
                        </tr>
                    </thead>
                    <tbody>
"""

        for i, app_info in enumerate(sorted_apps[:50], 1):  # 只显示前50个
            confidence_class = app_info['confidence'].lower()
            html_content += f"""
                        <tr>
                            <td>{i}</td>
                            <td><span class="app-name">{app_info['app']}</span></td>
                            <td><span class="count-badge good">{app_info['good_count']}</span></td>
                            <td><span class="count-badge bad">{app_info['bad_count']}</span></td>
                            <td><span class="confidence-badge {confidence_class}">{app_info['confidence']}</span></td>
                            <td>{app_info['reason']}</td>
                        </tr>
"""

        if len(sorted_apps) > 50:
            html_content += f"""
                        <tr>
                            <td colspan="6" style="text-align: center; color: #6c757d;">... 还有 {len(sorted_apps) - 50} 个应用</td>
                        </tr>
"""

        html_content += """
                    </tbody>
                </table>
            </div>
"""

    # 添加未分类应用
    if 'unknown' in category_stats and len(category_stats['unknown']['apps']) > 0:
        unknown_stats = category_stats['unknown']
        sorted_unknown = sorted(unknown_stats['apps'], key=lambda x: x['bad_count'], reverse=True)

        html_content += """
            <div class="category-section">
                <div class="category-header">
                    <h3>⚠ 未分类应用（需要人工审核）</h3>
                    <div class="meta">共 %d 个应用，全部来自坏客户</div>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th style="width: 50px;">#</th>
                            <th>应用包名</th>
                            <th style="width: 120px;">坏客户安装</th>
                            <th>备注</th>
                        </tr>
                    </thead>
                    <tbody>
""" % unknown_stats['bad_count']

        for i, app_info in enumerate(sorted_unknown[:100], 1):
            html_content += f"""
                        <tr>
                            <td>{i}</td>
                            <td><span class="app-name">{app_info['app']}</span></td>
                            <td><span class="count-badge bad">{app_info['bad_count']}</span></td>
                            <td>需要LLM分类或人工审核</td>
                        </tr>
"""

        if len(sorted_unknown) > 100:
            html_content += f"""
                        <tr>
                            <td colspan="4" style="text-align: center; color: #6c757d;">... 还有 {len(sorted_unknown) - 100} 个应用</td>
                        </tr>
"""

        html_content += """
                    </tbody>
                </table>
            </div>
"""

    html_content += """
        </div>

        <div class="footer">
            <p>报告生成时间: """ + pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
            <p>数据来源: 2272个印尼现金贷样本 | LLM分类: qwen/qwen3.6-plus</p>
        </div>
    </div>
</body>
</html>
"""

    # 保存HTML
    output_path = 'outputs/app_analysis/app_analysis_full_report.html'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\n✓ HTML报告已保存到: {output_path}")
    print(f"  文件大小: {len(html_content):,} 字符")

    return output_path


if __name__ == '__main__':
    generate_html_report()
