# wechat-business

Local WeChat messaging via ItChat (个人号接口)。

> 注意：ItChat 属于非官方个人号接口，可能存在封号风险，且微信更新可能导致失效。

## 功能
- 扫码登录并缓存登录态
- 通过昵称/备注/微信号搜索好友
- 发送文本消息

## 快速开始

### WeChat（ItChat）
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/send_message.py --to "刘敏" --text "你好"
```
首次运行会弹出二维码，扫码登录后会在 `storage/` 保存登录态。

### 钉钉每日天气 + 穿衣建议
1) 创建钉钉自定义机器人，拿到 webhook URL
2) 运行脚本：
```bash
python src/dingtalk_daily.py --webhook "https://oapi.dingtalk.com/robot/send?access_token=..." --city "上海"
```

#### 定时任务（cron）示例
每天 08:00 发送：
```bash
# 编辑 crontab
crontab -e

# 添加：
0 8 * * * /Users/cliff/workspace/wechat-business/.venv/bin/python /Users/cliff/workspace/wechat-business/src/dingtalk_daily.py --webhook "https://oapi.dingtalk.com/robot/send?access_token=..." --city "上海" >> /Users/cliff/workspace/wechat-business/logs/dingtalk_daily.log 2>&1
```
> 注意：确保已创建 .venv 且路径正确；首次建议手动运行确认正常。
