import React from 'react';
import ReactEChartsCore from 'echarts-for-react';
import type { FeatureMetric } from '@/types';

interface Props {
  data: FeatureMetric[];
  height?: number;
}

const CoveragePieChart: React.FC<Props> = ({ data, height = 250 }) => {
  const high = data.filter((d) => d.coverage >= 0.5).length;
  const medium = data.filter((d) => d.coverage >= 0.2 && d.coverage < 0.5).length;
  const low = data.filter((d) => d.coverage >= 0.05 && d.coverage < 0.2).length;
  const veryLow = data.filter((d) => d.coverage < 0.05).length;

  const option = {
    tooltip: {
      trigger: 'item' as const,
      formatter: (p: any) =>
        `${p.name}: ${p.value} 个 (${((p.value / data.length) * 100).toFixed(1)}%)`,
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['50%', '55%'],
        avoidLabelOverlap: false,
        label: {
          show: true,
          formatter: (p: any) => `${p.name}\n${p.value}个`,
          fontSize: 11,
        },
        emphasis: {
          label: { show: true, fontWeight: 'bold' },
        },
        data: [
          { value: high, name: '≥50%', itemStyle: { color: '#52c41a' } },
          { value: medium, name: '20-50%', itemStyle: { color: '#1677ff' } },
          { value: low, name: '5-20%', itemStyle: { color: '#faad14' } },
          { value: veryLow, name: '<5%', itemStyle: { color: '#ff4d4f' } },
        ],
      },
    ],
  };

  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ marginBottom: 4, fontSize: 13 }}>
        覆盖率分布 · 共 {data.length} 个特征
      </div>
      <ReactEChartsCore option={option} style={{ height }} notMerge />
    </div>
  );
};

export default CoveragePieChart;
