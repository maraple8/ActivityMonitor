import requests
import time
import json
from datetime import datetime
import logging
from EmailNotifier import EmailNotifier
from TokenManager import TokenManager
import jwt

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('activity_monitor.log'),
        logging.StreamHandler()
    ]
)


class ActivityMonitor:
    def __init__(self, base_url, tokenfile, sno, smtp_config=None, check_interval=2):
        """
        初始化活动监控器

        Args:
            base_url: API基础URL
            jwt_token: JWT认证令牌
            check_interval: 检查间隔时间（秒）
        """
        self.base_url = base_url.rstrip('/')


        self.token_manager = TokenManager(tokenfile, headless=False)
        self.token = None
        self.sno = sno

        self.token = self.token_manager.get_token(sno)
        if self.token is None:
            logging.error(f"获取token失败, 学号：{sno}")
            raise RuntimeError(f"获取token失败, 学号：{sno}")

        self.token_exp = jwt.decode(self.token, options={"verify_signature": False}).get('exp')

        self.leeway = 60 * 60 * 24

        self.headers = {
            'Authorization': f'JWT {self.token}',
            'X-Access-Token': self.token,
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.check_interval = check_interval
        self.session = requests.Session()
        self.session.headers.update(self.headers)

        self.email_notifier = EmailNotifier(smtp_config) if smtp_config else None

        # 存储活动状态用于比较
        self.previous_activities = {}
        self.applied_activities = {}

    def should_refresh_token(self):
        # 获取当前时间戳
        current_timestamp = time.time()

        # 计算剩余时间
        remaining_time = self.token_exp - current_timestamp

        # 判断是否过期
        if remaining_time <= self.leeway:
            return True
        else:
            return False

    def refresh_token(self):
        self.token = self.token_manager.get_token_automatically(self.sno)
        if self.token is None:
            logging.error("获取token失败")
            raise RuntimeError("获取token失败")

        self.token_manager.write_token_to_file(self.token)

        payload = jwt.decode(self.token, options={"verify_signature": False})
        self.token_exp = payload.get('exp')

        self.headers['Authorization'] = f'JWT {self.token}'
        self.headers['X-Access-Token'] = self.token
        self.session.headers.update(self.headers)

    def fetch_activities(self, page=1, limit=10):
        """
        获取活动列表

        Args:
            page: 页码
            limit: 每页数量

        Returns:
            dict: 活动数据或None（如果请求失败）
        """
        try:
            url = f"{self.base_url}/xuefenapi/activity/"
            params = {'page': page, 'limit': limit}

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            logging.error(f"请求失败: {e}")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"JSON解析失败: {e}")
            return None

    def check_new_activity(self, activities):
        """
        检查活动容量变化并触发警报

        Args:
            activities: 活动列表
        """
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        res = []

        for activity in activities:
            status = activity['status']
            activity_id = activity['id']
            activity_name = activity['name']
            capacity = activity['capacity']
            used_capacity = activity['used_capacity']

            if status != '报名中':
                if activity_id in self.previous_activities:
                    self.previous_activities.pop(activity_id)
                continue

            # 记录当前状态
            current_status = {
                'used_capacity': used_capacity,
                'capacity': capacity,
                'name': activity_name,
                'check_time': current_time
            }

            # 不在缓存中
            if activity_id not in self.previous_activities:
                # 若有余量
                if used_capacity < capacity:
                    res.append(activity)
                self.previous_activities[activity_id] = current_status
                continue

            # 在缓存中，现在无余量
            if used_capacity >= capacity:
                # 若缓存中有余量，现在无余量，则更新缓存
                if self.previous_activities[activity_id]['used_capacity'] < self.previous_activities[activity_id][
                    'capacity']:
                    self.previous_activities[activity_id] = current_status
                continue

            # 在缓存中，现在有余量
            # 若之前就有余量
            if self.previous_activities[activity_id]['used_capacity'] < self.previous_activities[activity_id]['capacity']:
                continue

            # 在缓存中，现在有余量
            # 之前无余量
            # self.trigger_alert(activity, current_status)
            res.append(activity)

            # 更新前一次状态
            self.previous_activities[activity_id] = current_status

        return res

    def apply_activities(self, activities):
        """
        自动报名活动

        Args:
            activity: 活动信息字典
        """
        for activity in activities:
            activity_id = activity.get('id')
            activity_name = activity.get('name', '未知活动')

            # 检查是否已经尝试过报名
            if self.applied_activities.get(activity_id):
                continue

            try:
                # 构建报名请求数据
                apply_data = {
                    "activity": activity_id,  # 关键参数：活动ID
                    "student": self.sno
                }

                logging.info(f"尝试自动报名活动: {activity_name} (ID: {activity_id})")

                # 发送报名请求
                response = self.session.post(
                    f"{self.base_url}/xuefenapi/applysign/",
                    json=apply_data,
                    timeout=10
                )

                # 记录到已尝试集合

                # 解析响应
                if response.status_code // 100 == 2:
                    self.applied_activities[activity_id] = 1

                    success_msg = f"✅ 报名成功: {activity_name}"
                    logging.info(success_msg)
                    # 报名成功后发送确认邮件
                    self._send_apply_success_email(activity)

                else:
                    error_data = response.json()
                    self._send_apply_fail_email(activity, error_data)
                    fail_msg = f"报名请求失败，状态码: {response.status_code} 错误消息：{error_data }- {activity_name}"
                    logging.error(fail_msg)

            except Exception as e:
                error_msg = f"报名过程发生未知错误: {activity_name} - {str(e)}"
                logging.error(error_msg)

    def _send_apply_success_email(self, activity):
        """发送报名成功确认邮件"""
        if not self.email_notifier:
            return

        try:
            # 构建邮件内容
            subject = f"🎉 报名成功: {activity['name']}"
            html_content = self._generate_apply_success_email_content(activity)

            self.email_notifier.send_email(subject, html_content)


        except Exception as e:
            logging.error(f"发送报名成功邮件失败: {e}")

    def _send_apply_fail_email(self, activity, msg):
        """发送报名成功确认邮件"""
        if not self.email_notifier:
            return

        try:
            # 构建邮件内容
            subject = f"报名失败: {activity['name']} - {msg}"
            html_content = self._generate_apply_fail_email_content(activity, msg)

            self.email_notifier.send_email(subject, html_content)


        except Exception as e:
            logging.error(f"发送报名成功邮件失败: {e}")

    def _generate_apply_success_email_content(self, activity):
        """生成报名成功邮件内容"""
        start_time = activity['start_time'].replace('T', ' ').split('+')[0]
        end_time = activity['end_time'].replace('T', ' ').split('+')[0]

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
            <div style="max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #28a745, #20c997); color: white; padding: 20px; border-radius: 10px 10px 0 0;">
                    <h1>🎉 报名成功!</h1>
                    <p>您已成功报名以下活动</p>
                </div>

                <div style="background: #f8f9fa; padding: 20px; border-radius: 0 0 10px 10px;">
                    <div style="background: #d4edda; border: 1px solid #c3e6cb; padding: 15px; border-radius: 5px; margin: 15px 0;">
                        <strong>恭喜！</strong> 您已成功报名该活动，请按时参加。
                    </div>

                    <h2>{activity['name']}</h2>

                    <div style="margin: 10px 0;">
                        <strong>活动时间:</strong> {start_time} 至 {end_time}
                    </div>

                    <div style="margin: 10px 0;">
                        <strong>活动地点:</strong> {activity['address']}
                    </div>

                    <div style="margin: 10px 0;">
                        <strong>发布学院:</strong> {activity['college_txt']}
                    </div>

                    <div style="margin: 10px 0;">
                        <strong>活动类别:</strong> {', '.join(activity['category_txts'])}
                    </div>

                    <div style="margin: 25px 0; text-align: center;">
                        <a href="{self.base_url}/pc/activity/index" 
                           style="background: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                            📋 查看我的报名
                        </a>
                    </div>

                    <div style="margin-top: 20px; font-size: 12px; color: #666;">
                        <p>此邮件由自动报名系统发送</p>
                        <p>发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def _generate_apply_fail_email_content(self, activity, msg):
        """构建报名失败邮件内容"""

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        start_time = activity['start_time'].replace('T', ' ').split('+')[0]
        end_time = activity['end_time'].replace('T', ' ').split('+')[0]

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 10px 10px; }}
        .activity-info {{ background: white; padding: 15px; margin: 15px 0; border-left: 4px solid #667eea; }}
        .warning {{ background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; margin: 15px 0; border-radius: 5px; }}
        .action {{ background: #d4edda; border: 1px solid #c3e6cb; padding: 15px; margin: 15px 0; border-radius: 5px; }}
        .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚨 活动“{activity.get('name')}”报名失败</h1>
            <p>原因：{msg}</p>
        </div>

        <div class="content">
            <div class="activity-info">
                <h3>📋 活动信息</h3>
                <div style="margin: 10px 0;">
                    <strong>活动名称:</strong> {activity.get('name')}
                </div>

                <div style="margin: 10px 0;">
                    <strong>活动时间:</strong> {start_time} 至 {end_time}
                </div>

                <div style="margin: 10px 0;">
                    <strong>活动地点:</strong> {activity['address']}
                </div>

                <div style="margin: 10px 0;">
                    <strong>发布学院:</strong> {activity['college_txt']}
                </div>

                <div style="margin: 10px 0;">
                    <strong>活动类别:</strong> {', '.join(activity['category_txts'])}
                </div>
            </div>

            <div class="footer">
                <p>发送时间：{current_time}</p>
                <p>此为系统自动发送邮件，请勿直接回复</p>
            </div>
        </div>
    </div>
</body>
</html>
        """

        return html_content

    def test_apply(self):
        apply_data = {
            "activity": 4501,  # 关键参数：活动ID
            "student": self.sno
        }

        # 发送报名请求
        response = self.session.post(
            f"{self.base_url}/xuefenapi/applysign/",
            json=apply_data,
            timeout=10
        )

        if response.status_code == 400:
            error_data = response.json()
            fail_msg = f"❌ 报名请求错误:- {error_data}"
            logging.warning(fail_msg)

    def test_send_email(self):
        data = self.fetch_activities()
        activity = data['results'][0]
        self._send_apply_success_email(activity)

    def monitor_loop(self):
        """
        主监控循环
        """
        logging.info("开始监控活动名额...")
        print("🚀 活动名额监控器已启动")
        print(f"📊 每{self.check_interval}秒检查一次活动名额")
        print("⏸️  按 Ctrl+C 停止监控\n")

        try:
            while True:
                # 获取活动数据
                data = self.fetch_activities()

                if data and 'results' in data:
                    activities = data['results']
                    total_count = data.get('count', 0)

                    # 记录基础信息
                    logging.info(f"检测到 {len(activities)} 个活动 (总计: {total_count})")

                    # 检查活动容量
                    can_applies = self.check_new_activity(activities)

                    self.apply_activities(can_applies)


                else:
                    logging.error("获取活动数据失败或数据格式不正确")

                result = self.should_refresh_token()
                if result:
                    print('获取新token')
                    self.refresh_token()

                # 等待指定间隔
                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            logging.info("监控器被用户中断")
            print("\n👋 监控已停止")
        except Exception as e:
            logging.error(f"监控循环发生错误: {e}")