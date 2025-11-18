from ActivityMonitor import ActivityMonitor

if __name__ == '__main__':
    # 配置信息 - 请根据实际情况修改
    BASE_URL = "http://yjszhsy.bjtu.edu.cn"  # 基础URL
    tokenfile = 'token.cfg'  # token存放文件名，一般不用改
    sno = '23xxxxxx'  # 你的学号
    SMTP_CONFIG = {
        'smtp_server': 'smtp.qq.com',  # QQ邮箱SMTP服务器
        'smtp_port': 465,  # SSL端口（QQ邮箱为465，其他邮箱自行查阅）
        'sender_email': '123456@qq.com',  # 发件人邮箱（你自己的邮箱）
        'password': 'abc123',  # 邮箱授权码（不是登录密码）
        'recipient': '123456@qq.com'  # 收件人邮箱（还是你的邮箱）
    }
    # 创建监控器实例（每2秒检查一次）
    monitor = ActivityMonitor(BASE_URL, tokenfile, sno, smtp_config=SMTP_CONFIG, check_interval=5)

    # 开始监控
    monitor.monitor_loop()