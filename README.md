# 房地产客户跟进同步（测试版）

飞书继续作为唯一正式客户数据库。当前优先开发飞书 ↔ Apple 提醒事项同步，暂不开发语音功能。

## 可运行的离线演示

需要 Python 3.10+，无第三方依赖：

```sh
python3 -B -m crm_sync.main demo
python3 -B -m unittest discover -s tests -v
```

演示使用虚构数据，不访问飞书或 Apple。

## Mac 实机测试

[分步运行指南与测试结果](docs/MAC_SYNC_GUIDE.md)。Mac 桥接使用 Swift/EventKit，必须在你的 Mac 上编译和授权；Linux 云端未验证其运行。只允许 CRM-SYNC-TEST 专用列表和独立飞书测试文件/表，正式客户连接保持只读。

[最终产品需求](docs/FINAL_SYNC_REQUIREMENTS.md) · [整体规划](PLAN.md)

不要提交密钥、客户资料、本地配置或状态数据库。每次只按指导执行一个实机步骤。
