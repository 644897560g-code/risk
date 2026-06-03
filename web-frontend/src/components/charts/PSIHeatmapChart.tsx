import React from 'react';
import ReactEChartsCore from 'echarts-for-react';
import type { FeatureMetric } from '@/types';

interface Props {
  data: FeatureMetric[];
  height?: number;
}

const PSIHeatmapChart: React.FC<Props> = ({ data, height = 200 }) => {
  const threshold = 0.25;
  const passed = data.filter((d) => d.psi <= threshold).length;
  const failed = data.filter((d) => d.psi > threshold).length;

  // Group by PSI ranges
  const ranges = [
    { label: '0-0.05', value: data.filter((d) => d.psi <= 0.05).length },
    { label: '0.05-0.1', value: data.filter((d) => d.psi > 0.05 && d.psi <= 0.1).length },
    { label: '0.1-0.15', value: data.filter((d) => d.psi > 0.1 && d.psi <= 0.15).length },
    { label: '0.15-0.2', value: data.filter((d) => d.psi > 0.15 && d.psi <= 0.2).length },
    { label: '0.2-0.25', value: data.filter((d) => d.psi > 0.2 && d.psi <= 0.25).length },
    { label: '>0.25', value: data.filter((d) => d.psi > 0.25).length },
  ];

  const option = {
    tooltip: {
      trigger: 'item' as const,
      formatter: (p: any) =>
        `${p.name}: ${p.value} 个特征 (${((p.value / data.length) * 100).toFixed(1)}%)`,
    },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: ranges.map((r) => r.label),
      axisLabel: { fontSize: 11 },
    },
    yAxis: { type: 'value', name: '特征数' },
    series: [
      {
        type: 'bar',
        data: ranges.map((r, i) => ({
          value: r.value,
          itemStyle: {
            color: i < 4 ? '#1677ff' : i < 5 ? '#faad14' : '#ff4d4f',
          },
        })),
        barMaxWidth: 50,
        label: {
          show: true,
          position: 'top',
          formatter: (p: any) => `${p.value}个`,
        },
      },
    ],
  };

  return (
    <div>
      <div style={{ marginBottom: 8, display: 'flex', gap: 16, fontSize: 13 }}>
        <span>PSI ≤ 0.25: <strong style={{ color: '#52c41a' }}>{passed}</strong> 个</span>
        <span>PSI &gt; 0.25: <strong style={{ color: '#ff4d4f' }}>{failed}</strong> 个</span>
      </div>
      <ReactEChartsCore option={option} style={{ height }} notMerge />
    </div>
  );
};

export default PSIHeatmapChart;
