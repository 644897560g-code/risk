import React from 'react';
import ReactEChartsCore from 'echarts-for-react';
import type { FeatureMetric } from '@/types';

interface Props {
  data: FeatureMetric[];
  height?: number;
}

const IVDistributionChart: React.FC<Props> = ({ data, height = 300 }) => {
  const sorted = [...data].sort((a, b) => b.iv - a.iv);
  const names = sorted.map((d) => d.feature_name);
  const values = sorted.map((d) => d.iv);
  const colors = sorted.map((d) => (d.iv >= 0.02 ? '#52c41a' : '#ff4d4f'));

  const option = {
    tooltip: {
      trigger: 'axis' as const,
      axisPointer: { type: 'shadow' as const },
    },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'value',
      name: 'IV',
      axisLabel: { fontSize: 11 },
      splitLine: { lineStyle: { type: 'dashed' } },
    },
    yAxis: {
      type: 'category',
      data: names,
      inverse: true,
      axisLabel: { fontSize: 10, width: 120, overflow: 'truncate' as const },
    },
    series: [
      {
        type: 'bar',
        data: values.map((v, i) => ({
          value: v,
          itemStyle: { color: colors[i] },
        })),
        barMaxWidth: 20,
        label: {
          show: true,
          position: 'right',
          formatter: (p: any) => p.value.toFixed(4),
          fontSize: 10,
        },
      },
    ],
  };

  return (
    <ReactEChartsCore option={option} style={{ height }} notMerge />
  );
};

export default IVDistributionChart;
