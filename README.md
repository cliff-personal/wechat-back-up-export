# wechat-business

Local WeChat messaging via ItChat (个人号接口)。

> 注意：ItChat 属于非官方个人号接口，可能存在封号风险，且微信更新可能导致失效。

## 功能
- 扫码登录并缓存登录态
- 通过昵称/备注/微信号搜索好友
- 发送文本消息

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/send_message.py --to "刘敏" --text "你好"
```

首次运行会弹出二维码，扫码登录后会在 `storage/` 保存登录态。
