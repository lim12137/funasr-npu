# UPLOAD_IO_FAILED 分支修复测试报告

- 日期：2026-03-23
- 目标：验证上传写入失败时返回 `UPLOAD_IO_FAILED`，并对已创建临时文件执行清理或清理尝试。

## TDD 过程

1. 新增失败测试：`test_asr_cleans_temp_file_when_upload_write_fails`
2. 先运行该单测，确认在修复前失败。
3. 修复 `server/app.py` 的 `UPLOAD_IO_FAILED` 分支，补充异常路径清理逻辑。
4. 重新运行单测与全量测试，确认通过。

## 测试命令与结果摘要

### 1) 修复前失败验证

命令：

```bash
pytest tests/test_api.py -k "cleans_temp_file_when_upload_write_fails" -q
```

结果摘要：

- 退出码：`1`
- 失败断言：`assert unlink_attempted or not expected_temp_audio_path.exists()`
- 说明：写入失败后临时文件仍存在，且未触发清理尝试。

### 2) 修复后目标用例验证

命令：

```bash
pytest tests/test_api.py -k "cleans_temp_file_when_upload_write_fails" -q
```

结果摘要：

- 退出码：`0`
- `1 passed, 7 deselected`

### 3) 全量测试验证

命令：

```bash
pytest -q
```

结果摘要：

- 退出码：`0`
- `8 passed in 1.07s`
