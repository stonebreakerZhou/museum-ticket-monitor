# 国博余票监控

本地跑的 Python 脚本，定时查询国家博物馆基本陈列的余票状态，发现有可约日期就通知你。

只查不抢。收到通知后自己去官网或小程序手动下单。

## 不是什么

- 不是抢票工具
- 不登录、不绕过验证码、不模拟点击
- 不存个人信息
- 不向国博服务器发伪造请求

只用国博官方公开、不需登录的余票查询接口，普通浏览器请求就能拿到。

## 用法

需要 Python 3.10+。

```
pip install -r requirements.txt
cp config.ini.example config.ini
```

按需改 `config.ini`：

| 字段 | 说明 |
|---|---|
| `[monitor] target_dates` | 留空监控全部；填 `2026-08-23,2026-08-30` 只监控指定日期 |
| `[notifier] type` | `off` / `serverchan` / `email` / `both` |
| `serverchan_sendkey` | Server酱 SendKey，申请：https://sct.ftqq.com/ |
| `smtp_*` / `mail_to` | 邮件通知的 SMTP 配置和收件人 |

跑：

```
python main.py
```

Ctrl+C 退出。

## 调度

- 普通时段：每 10 分钟
- 16:30 - 17:30（放票前后）：每 30 秒

国博每天 17:00 放出第 8 天的票。

## 文件

```
config.py            配置加载
main.py              主入口
museum_api.py        公开 API 查询
notifier.py          Server酱 / 邮件通知
config.ini.example   配置模板
config.ini           你的配置（不进 git）
requirements.txt     依赖
logs/                运行日志
```

## 免责

仅用于个人余票提醒。禁止商用、抢票、黄牛、绕过风控。预约规则以国博官方为准（同一证件号每月最多 4 次、每周 1 次、每天 1 次）。

## License

MIT
