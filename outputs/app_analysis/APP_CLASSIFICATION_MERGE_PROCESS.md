# APP分类合并流程

**日期**: 2026-05-04
**问题**: 离线批量分类的新结果没有合并到历史完整文件中

## 完整流程

```
每天凌晨2点执行
    ↓
扫描 unknown APP
    ↓
LLM批量分类 (每批200个)
    ↓
保存到 classification_cache.json
    ↓
【关键步骤】合并到 classification_complete_XXXXX.json
    ↓
生成新文件: classification_complete_11860.json
    ↓
在线分类自动读取最新文件
```

## 代码实现

### 1. 合并函数

```python
def merge_into_complete_classification(self, new_results: Dict):
    """将新分类结果合并到历史完整分类文件中"""

    # 1. 加载历史文件
    history_files = [f for f in os.listdir('outputs/app_analysis')
                    if f.startswith('classification_complete_')]
    latest_history = max(history_files, key=lambda f: os.path.getmtime(f))

    # 2. 合并新结果
    history_classifications.update(new_results)
    total_apps = len(history_classifications)

    # 3. 生成新文件
    new_filename = f'classification_complete_{total_apps}.json'
    # 保存...

    # 4. 更新缓存
    self._save_cache()

    # 5. 更新CSV
    self._update_csv()
```

### 2. 文件命名规则

```
之前: classification_complete_11850.json  (11,850个APP)
新增: +10个APP
之后: classification_complete_11860.json  (11,860个APP)
```

### 3. 元数据记录

新生成的文件包含合并信息：

```json
{
  "total_apps": 11860,
  "classification_date": "2026-05-04 02:30:00",
  "model": "qwen/qwen3.6-plus",
  "merge_info": {
    "merged_at": "2026-05-04T02:30:00",
    "new_count": 10,
    "previous_count": 11850
  },
  "classifications": {
    "com.newapp.XXX": {...},
    ...
  }
}
```

## 相关文件

| 文件 | 作用 |
|------|------|
| `classification_complete_11850.json` | 历史完整分类 |
| `classification_complete_11860.json` | 合并后新完整分类 |
| `classification_cache.json` | 最新缓存（实时追加） |
| `app_classification_complete.csv` | CSV版本 |

## 主Agent集成

主Agent的`_load_app_cache`方法会自动读取最新文件：

```python
def _load_app_cache(self) -> Dict:
    """动态加载最新的分类缓存文件"""
    cache_dir = 'outputs/app_analysis'
    cache_files = [f for f in os.listdir(cache_dir)
                   if f.startswith('classification_complete_') and f.endswith('.json')]

    # 自动使用最新的
    latest_cache = max(cache_files,
                      key=lambda f: os.path.getmtime(os.path.join(cache_dir, f)))
```

这样每次离线批量分类完成后，在线分类会立即使用最新的分类结果。

## 执行方式

### 手动执行
```bash
python data/batch_classify_new_apps.py --input data/unknown_apps.json
```

### 定时任务
```bash
# macOS: launchd
# Linux: crontab
# 每天凌晨2点执行
0 2 * * * cd /path/to/project && python data/batch_classify_new_apps.py --input data/unknown_apps.json
```

## 输出示例

```
✅ 批量分类完成！
📊 分类总数: 10
🔀 已合并到: outputs/app_analysis/classification_complete_11860.json
📝 报告已保存到: outputs/app_analysis/batch_classification_report.md
```

## 好处

1. **版本追踪**: 每次合并生成新文件，文件名中的数字表示总数
2. **自动更新**: 在线分类自动读取最新文件
3. **可回溯**: 保留历史文件，可以回滚到任意版本
4. **一致性**: 所有地方都使用同一个最新的分类文件

## 之前的问题

❌ 旧实现只更新`classification_cache.json`，不合并到完整文件
❌ 在线分类读取旧的11850文件，不知道新分类的结果

## 现在的流程

✅ 离线批量分类 → 合并到完整文件 → 生成11860文件
✅ 在线分类 → 自动检测最新文件 → 读取11860

---

**相关修改**:
- 文件: `data/batch_classify_new_apps.py`
- 新增函数: `merge_into_complete_classification()`
- 修改: `__main__`部分调用合并函数
