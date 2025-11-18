# ActivityMonitor
监控北京交通大学”研究生素养实践学分管理系统“的新活动

## 配置
配置文件为Main.py
```
BASE_URL = "http://yjszhsy.bjtu.edu.cn"  # 基础URL
tokenfile = 'token.cfg'                  # token存放文件名，一般不用改
sno = '23xxxxxx'                         # 你的学号
SMTP_CONFIG = {
    'smtp_server': 'smtp.qq.com',      # QQ邮箱SMTP服务器
    'smtp_port': 465,                  # SSL端口（QQ邮箱为465，其他邮箱自行查阅）
    'sender_email': '123456@qq.com',   # 发件人邮箱（你自己的邮箱）
    'password': 'abc123',              # 邮箱授权码（不是登录密码）
    'recipient': '123456@qq.com'       # 收件人邮箱（还是你的邮箱）
}
```
## 启动
初次启动会自动获取网站令牌，需要等待chrome driver启动，时间大概几十秒，在弹出的网页手动登录一遍mis即可
`python Main.py`
