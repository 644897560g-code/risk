import React, { useState } from 'react';
import ReactEChartsCore from 'echarts-for-react';
import { Card, Row, Col, Empty, Spin, Segmented } from 'antd';

interface FeatureData {
  feature_name: string;
  iv: number;
  psi: number;
  coverage: number;
  status?: string;
}

interface Props {
  totalFeatures?: number;
  passedFeatures?: number;
  features?: FeatureData[];
  loading?: boolean;
}

const FeatureCharts: React.FC<Props> = ({ totalFeatures, passedFeatures, features, loading }) => {
  const [filterStatus, setFilterStatus] = useState<'all' | 'passed' | 'failed'>('all');
  const chartTextColor = '#cbd5e1';
  const chartSubtleColor = 'rgba(148, 163, 184, 0.26)';
  const tooltipStyle = {
    backgroundColor: 'rgba(8, 13, 21, 0.94)',
    borderColor: 'rgba(55, 231, 255, 0.26)',
    textStyle: { color: '#e5f6ff' },
  };

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>;
  }

  if (!features || features.length === 0) {
    // Show simple stats even without feature-level data
    if (totalFeatures != null && passedFeatures != null) {
      return renderSimpleStats(totalFeatures, passedFeatures);
    }
    return <Empty description="暂无特征数据" />;
  }

  // Use task-recorded totals for pass rate (matches task list display)
  const passRatePassed = passedFeatures ?? features.filter((f) => f.iv >= 0.02 && f.psi <= 0.25 && f.coverage > 0.05).length;
  const passRateTotal = totalFeatures ?? features.length;

  // Filter features based on selected status
  const filteredFeatures = features.filter((f) => {
    const passed = f.iv >= 0.02 && f.psi <= 0.25 && f.coverage > 0.05;
    if (filterStatus === 'all') return true;
    return filterStatus === 'passed' ? passed : !passed;
  });

  // ---- IV Distribution ----
  const ivBuckets = [0, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 1, Infinity];
  const ivLabels = ['0-0.02', '0.02-0.05', '0.05-0.1', '0.1-0.2', '0.2-0.3', '0.3-0.5', '0.5-1', '>1'];
  const ivCounts = ivBuckets.map((_, i) =>
    filteredFeatures.filter((f) => {
      const lower = ivBuckets[i];
      const upper = ivBuckets[i + 1];
      return f.iv >= lower && (upper === Infinity ? true : f.iv < upper);
    }).length
  );

  const ivTotal = filteredFeatures.length;
  const ivOption = {
    title: { text: 'IV 分布', textStyle: { fontSize: 14, color: chartTextColor } },
    tooltip: { trigger: 'axis' as const, formatter: (params: any) => {
      const p = Array.isArray(params) ? params[0] : params;
      const val = p.value;
      const pct = ((val / ivTotal) * 100).toFixed(1);
      return `${p.axisValue}<br/>数量: ${val}<br/>占比: ${pct}%`;
    }, ...tooltipStyle },
    grid: { left: 50, right: 20, top: 40, bottom: 60 },
    xAxis: {
      type: 'category' as const,
      data: ivLabels,
      axisLine: { lineStyle: { color: chartSubtleColor } },
      axisLabel: { rotate: 30, fontSize: 11, margin: 8, color: chartTextColor },
    },
    yAxis: {
      type: 'value' as const,
      axisLabel: { color: chartTextColor },
      splitLine: { lineStyle: { color: chartSubtleColor } },
    },
    series: [
      {
        type: 'bar',
        data: ivCounts.map((v, i) => ({
          value: v,
          itemStyle: { color: i >= 2 ? '#52c41a' : i >= 1 ? '#faad14' : '#ff4d4f' },
        })),
        label: { show: false },
      },
    ],
  };

  // ---- PSI Distribution ----
  const psiBuckets = [0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, Infinity];
  const psiLabels = ['0-0.05', '0.05-0.1', '0.1-0.15', '0.15-0.2', '0.2-0.25', '0.25-0.3', '>0.3'];
  const psiTotal = filteredFeatures.length;
  const psiCounts = psiBuckets.map((_, i) =>
    filteredFeatures.filter((f) => {
      const lower = psiBuckets[i];
      const upper = psiBuckets[i + 1];
      return f.psi >= lower && (upper === Infinity ? true : f.psi < upper);
    }).length
  );

  const psiOption = {
    title: { text: 'PSI 分布', textStyle: { fontSize: 14, color: chartTextColor } },
    tooltip: { trigger: 'axis' as const, formatter: (params: any) => {
      const p = Array.isArray(params) ? params[0] : params;
      const val = p.value;
      const pct = ((val / psiTotal) * 100).toFixed(1);
      return `${p.axisValue}<br/>数量: ${val}<br/>占比: ${pct}%`;
    }, ...tooltipStyle },
    grid: { left: 50, right: 20, top: 40, bottom: 60 },
    xAxis: {
      type: 'category' as const,
      data: psiLabels,
      axisLine: { lineStyle: { color: chartSubtleColor } },
      axisLabel: { rotate: 30, fontSize: 11, margin: 8, color: chartTextColor },
    },
    yAxis: {
      type: 'value' as const,
      axisLabel: { color: chartTextColor },
      splitLine: { lineStyle: { color: chartSubtleColor } },
    },
    series: [
      {
        type: 'bar',
        data: psiCounts.map((v, i) => ({
          value: v,
          itemStyle: { color: i <= 4 ? '#52c41a' : '#ff4d4f' },
        })),
        label: { show: false },
      },
    ],
  };

  // ---- Pass/Fail Pie (use filtered set) ----
  const filteredPassed = filteredFeatures.filter((f) => f.iv >= 0.02 && f.psi <= 0.25 && f.coverage > 0.05).length;
  const filteredFailed = filteredFeatures.length - filteredPassed;
  const pieOption = {
    title: { text: `通过率 (${filteredPassed}/${filteredFeatures.length})`, textStyle: { fontSize: 14, color: chartTextColor }, left: 'center' },
    tooltip: { trigger: 'item' as const, formatter: '{b}: {c} ({d}%)', ...tooltipStyle },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['50%', '55%'],
        data: [
          { value: filteredPassed, name: '通过', itemStyle: { color: '#52c41a' } },
          { value: filteredFailed, name: '未通过', itemStyle: { color: '#ff4d4f' } },
        ],
        label: { show: true, formatter: '{b}\n{d}%', color: chartTextColor },
      },
    ],
  };

  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col span={12}>
          <Card size="small" title="IV 分布">
            <ReactEChartsCore option={ivOption} style={{ height: 250 }} notMerge />
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" title="PSI 分布">
            <ReactEChartsCore option={psiOption} style={{ height: 250 }} notMerge />
          </Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={8}>
          <Card size="small" title="通过率">
            <ReactEChartsCore option={pieOption} style={{ height: 250 }} notMerge />
          </Card>
        </Col>
        <Col span={16}>
          <Card size="small" title={
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
              <span>Top 特征 (IV)</span>
              <Segmented
                options={[
                  { label: `全部 (${features.length})`, value: 'all' },
                  { label: `通过 (${features.filter(f => f.iv >= 0.02 && f.psi <= 0.25 && f.coverage > 0.05).length})`, value: 'passed' },
                  { label: `未通过 (${features.filter(f => !(f.iv >= 0.02 && f.psi <= 0.25 && f.coverage > 0.05)).length})`, value: 'failed' },
                ]}
                value={filterStatus}
                onChange={(val) => setFilterStatus(val as 'all' | 'passed' | 'failed')}
                size="small"
              />
            </div>
          }>
            <table className="feature-top-table">
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>特征名</th>
                  <th style={{ textAlign: 'right' }}>IV</th>
                  <th style={{ textAlign: 'right' }}>PSI</th>
                  <th style={{ textAlign: 'right' }}>覆盖率</th>
                </tr>
              </thead>
              <tbody>
                {filteredFeatures
                  .sort((a, b) => b.iv - a.iv)
                  .slice(0, 10)
                  .map((f) => (
                    <tr key={f.feature_name}>
                      <td>{f.feature_name}</td>
                      <td style={{ textAlign: 'right', color: f.iv >= 0.02 ? '#34d399' : '#fb7185' }}>
                        {f.iv.toFixed(4)}
                      </td>
                      <td style={{ textAlign: 'right', color: f.psi <= 0.25 ? '#34d399' : '#fb7185' }}>
                        {f.psi.toFixed(4)}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        {(f.coverage * 100).toFixed(1)}%
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

/** Fallback when only counts are available */
const renderSimpleStats = (total: number, passed: number) => {
  const failed = total - passed;
  const tooltipStyle = {
    backgroundColor: 'rgba(8, 13, 21, 0.94)',
    borderColor: 'rgba(55, 231, 255, 0.26)',
    textStyle: { color: '#e5f6ff' },
  };
  const pieOption = {
    title: { text: '通过率', textStyle: { fontSize: 14, color: '#cbd5e1' }, left: 'center' },
    tooltip: { trigger: 'item' as const, formatter: '{b}: {c} ({d}%)', ...tooltipStyle },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['50%', '55%'],
        data: [
          { value: passed, name: '通过', itemStyle: { color: '#52c41a' } },
          { value: failed, name: '未通过', itemStyle: { color: '#ff4d4f' } },
        ],
        label: { show: true, formatter: '{b}\n{d}%', color: '#cbd5e1' },
      },
    ],
  };

  return (
    <div style={{ maxWidth: 400, margin: '0 auto' }}>
      <ReactEChartsCore option={pieOption} style={{ height: 300 }} notMerge />
    </div>
  );
};

export default FeatureCharts;
