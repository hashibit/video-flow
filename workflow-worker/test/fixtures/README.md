# Test Fixtures

这些是测试用的 Mock 数据样本，用于测试和开发。

## 文件说明

- `mock_get_task.json` - 通用任务样本数据（424 行）
- `mock_get_task_banwords.json` - 违禁词检测任务样本（82 行）
- `mock_get_task_human_tracking.json` - 人员追踪任务样本（74 行）
- `mock_get_task_script_match.json` - 脚本匹配任务样本（51 行）
- `mock_get_task_subtitle.json` - 字幕匹配任务样本（105 行）
- `mock_job_report.json` - 任务报告样本（394 行）

## 用途

这些 JSON 文件是各种任务的配置和结果样本，可以用于：

1. **本地测试** - 模拟真实的任务数据
2. **开发调试** - 快速测试特定任务类型
3. **文档参考** - 了解任务数据结构

## 使用示例

```python
import json

# 加载样本数据
with open('test/fixtures/mock_get_task.json', 'r') as f:
    task_data = json.load(f)

# 用于测试
test_task = Task(**task_data)
```

## 注意

这些文件是 **Mock 数据样本**，不是单元测试。
实际的测试代码在 `test/media_test.py`。
