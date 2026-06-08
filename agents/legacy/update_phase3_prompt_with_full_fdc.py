"""
使用完整2094样本的FDC分布数据更新Phase 3 prompt
"""

import json

# 读取完整的FDC分布数据
with open('outputs/feature_design/stepwise/fdc_field_distributions.json', 'r', encoding='utf-8') as f:
    fdc_data = json.load(f)

# 构建FDC数据字典字符串
FDC_DATA_DICT = """
## ⚠️ 强制约束：FDC真实字段和枚举值（基于**2094个样本**，**117,026条贷款记录**统计，必须遵守）

### 1. FDC - pinjaman（贷款记录）字段

**status_pinjaman** (贷款状态代码):
- ✅ 可用值: `{FDC['status_pinjaman']['values'].keys()}`
  - L = Fully Paid (已结清, {FDC['status_pinjaman']['values'].get('L', 0):,}条/{FDC['status_pinjaman']['values'].get('L', 0)/117026*100:.1f}%)
  - O = Outstanding (未结清, {FDC['status_pinjaman']['values'].get('O', 0):,}条/{FDC['status_pinjaman']['values'].get('O', 0)/117026*100:.1f}%)
  - W = Write-Off (核销, {FDC['status_pinjaman']['values'].get('W', 0):,}条/{FDC['status_pinjaman']['values'].get('W', 0)/117026*100:.1f}%)
  - R = Restructure (重组, {FDC['status_pinjaman']['values'].get('R', 0):,}条/{FDC['status_pinjaman']['values'].get('R', 0)/117026*100:.1f}%)
  - F = Full Payment (全额还款, {FDC['status_pinjaman']['values'].get('F', 0):,}条/{FDC['status_pinjaman']['values'].get('F', 0)/117026*100:.1f}%)
  - X = Deferred Loan (延期贷款, {FDC['status_pinjaman']['values'].get('X', 0):,}条/{FDC['status_pinjaman']['values'].get('X', 0)/117026*100:.1f}%)
  - S = Partial Payment (部分还款, {FDC['status_pinjaman']['values'].get('S', 0):,}条/{FDC['status_pinjaman']['values'].get('S', 0)/117026*100:.1f}%)
- ❌ 不能使用: approved, rejected, pending (这些状态不存在)

**status_pinjaman_ket** (贷款状态描述):
- ✅ 可用值: `{list(FDC['status_pinjaman_ket']['values'].keys())}`

**kualitas_pinjaman** (贷款质量代码):
- ✅ 可用值: `{list(FDC['kualitas_pinjaman']['values'].keys())}`
  - 1 = Lancar (正常, {FDC['kualitas_pinjaman']['values'].get('1', 0):,}条/{FDC['kualitas_pinjaman']['values'].get('1', 0)/117026*100:.1f}%)
  - 2 = Dalam Perhatian Khusus (关注, {FDC['kualitas_pinjaman']['values'].get('2', 0):,}条/{FDC['kualitas_pinjaman']['values'].get('2', 0)/117026*100:.1f}%)
  - 5 = Macet (呆账, {FDC['kualitas_pinjaman']['values'].get('5', 0):,}条/{FDC['kualitas_pinjaman']['values'].get('5', 0)/117026*100:.1f}%)
  - 4 = Diragukan (可疑, {FDC['kualitas_pinjaman']['values'].get('4', 0):,}条/{FDC['kualitas_pinjaman']['values'].get('4', 0)/117026*100:.1f}%)
  - 3 = Kurang Lancar (次正常, {FDC['kualitas_pinjaman']['values'].get('3', 0):,}条/{FDC['kualitas_pinjaman']['values'].get('3', 0)/117026*100:.1f}%)

**kualitas_pinjaman_ket** (贷款质量描述):
- ✅ 可用值: `{list(FDC['kualitas_pinjaman_ket']['values'].keys())}`

**penyelesaian_w_oleh** (违约解决方式):
- ✅ 可用值: `{list(FDC['penyelesaian_w_oleh']['values'].keys())}`
  - Default: {FDC['penyelesaian_w_oleh']['values'].get('Default', 0):,}条 ({FDC['penyelesaian_w_oleh']['values'].get('Default', 0)/117026*100:.1f}%)

**tipe_pinjaman** (贷款类型):
- ✅ 可用值: `{list(FDC['tipe_pinjaman']['values'].keys())}`
  - Multiguna (多用途): {FDC['tipe_pinjaman']['values'].get('Multiguna', 0):,}条 ({FDC['tipe_pinjaman']['values'].get('Multiguna', 0)/117026*100:.1f}%)
  - Produktif (生产性): {FDC['tipe_pinjaman']['values'].get('Produktif', 0):,}条 ({FDC['tipe_pinjaman']['values'].get('Produktif', 0)/117026*100:.1f}%)

**sub_tipe_pinjaman** (子贷款类型):
- ✅ 可用值 (Top 10):
{chr(10).join([f'  - {k}: {v:,}条 ({v/117026*100:.1f}%)' for k, v in list(FDC['sub_tipe_pinjaman']['values'].items())[:10]])}

**pendanaan_syariah** (是否伊斯兰金融):
- ✅ 可用值: `{list(FDC['pendanaan_syariah']['values'].keys())}`
  - False (非伊斯兰金融): {FDC['pendanaan_syariah']['values'].get('False', 0):,}条 ({FDC['pendanaan_syariah']['values'].get('False', 0)/117026*100:.1f}%)
  - True (伊斯兰金融): {FDC['pendanaan_syariah']['values'].get('True', 0):,}条 ({FDC['pendanaan_syariah']['values'].get('True', 0)/117026*100:.1f}%)
- 类型: Boolean (true/false字符串,不是数字)

**jenis_pengguna** (用户类型代码):
- ✅ 可用值: `[1]` (100%, Individual个人用户)

**jenis_pengguna_ket** (用户类型描述):
- ✅ 可用值: `{list(FDC['jenis_pengguna_ket']['values'].keys())}`
  - Individual: {FDC['jenis_pengguna_ket']['values'].get('Individual', 0):,}条
  - Company: {FDC['jenis_pengguna_ket']['values'].get('Company', 0):,}条

**dpd_max** (最大逾期天数):
- ✅ 范围: {int(FDC['dpd_max_stats']['stats']['min'])} - {int(FDC['dpd_max_stats']['stats']['max'])}天
- ✅ 均值: {FDC['dpd_max_stats']['stats']['mean']:.2f}天
- ✅ 分布:
  - DPD=0 (无逾期): {FDC['dpd_max_stats']['stats']['zero_count']:,}条 ({FDC['dpd_max_stats']['stats']['zero_count']/117026*100:.1f}%)
  - DPD>0 (有逾期): {FDC['dpd_max_stats']['stats']['positive_count']:,}条 ({FDC['dpd_max_stats']['stats']['positive_count']/117026*100:.1f}%)
- ✅ 类型: Integer

**其他可用字段**:
- `id_penyelenggara`: 机构ID ({len(FDC['id_penyelenggara']['values'])}个唯一值)
  - Top 10机构:
{chr(10).join([f'    - {k}: {v:,}条' for k, v in list(FDC['id_penyelenggara']['values'].items())[:10]])}
- `nilai_pendanaan`: 借款金额 (IDR印尼盾)
- `tgl_penyaluran_dana`: 放款日期 (YYYY-MM-DD格式)
- `tgl_jatuh_tempo_pinjaman`: 到期日
- `sisa_pinjaman_berjalan`: 未结清余额
- `dpd_terakhir`: 最后逾期天数
- `pendapatan`: 收入
- `agunan`: 抵押品

"""

print(FDC_DATA_DICT)
print("\n\n✅ 生成的FDC数据字典已输出，复制到 stepwise_framework_design.py 的 FDC_DATA_DICT 变量中")
