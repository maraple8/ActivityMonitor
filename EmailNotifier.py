import requests
import time
import json
from datetime import datetime
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import threading
import ssl

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('activity_monitor.log'),
        logging.StreamHandler()
    ]
)


class EmailNotifier:
    """邮件通知器"""

    def __init__(self, smtp_config):
        """
        初始化邮件配置

        Args:
            smtp_config: SMTP服务器配置字典
        """
        self.smtp_config = smtp_config
        self.last_sent_time = {}  # 记录每个活动的最后发送时间，避免重复发送

    def send_email(self, subject, html_content):
        try:
            recipient = self.smtp_config.get('recipient')
            # 发送邮件
            self._send_single_email(recipient, subject, html_content)
            return True

        except Exception as e:
            logging.error(f"发送邮件时发生错误: {e}")
            return False

    def _send_single_email(self, recipient, subject, html_content):
        """发送单封邮件 - 忽略QUIT异常版本"""
        server = None
        try:
            # 创建简单邮件
            message = MIMEText(html_content, 'html', 'utf-8')
            message['From'] = self.smtp_config['sender_email']
            message['To'] = recipient
            message['Subject'] = Header(subject, 'utf-8')

            # 连接SMTP
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(
                self.smtp_config['smtp_server'],
                self.smtp_config['smtp_port'],
                context=context,
                timeout=30
            )

            server.login(self.smtp_config['sender_email'], self.smtp_config['password'])

            # 发送邮件
            text = message.as_string()
            server.sendmail(self.smtp_config['sender_email'], [recipient], text)

            logging.info(f"邮件成功发送给: {recipient}")
            return True

        except smtplib.SMTPDataError as e:
            # 如果错误码是250，说明邮件发送成功，只是QUIT有问题
            if hasattr(e, 'smtp_code') and e.smtp_code == 250:
                logging.info(f"邮件发送成功（QUIT异常可忽略）: {recipient}")
                return True
            else:
                logging.error(f"SMTP数据错误: {e}")
                return False

        except smtplib.SMTPException as e:
            logging.error(f"SMTP错误: {e}")
            return False

        except Exception as e:
            logging.error(f"发送邮件时发生错误: {e}")
            return False

        finally:
            # 安全关闭连接
            if server:
                try:
                    server.quit()  # 优雅关闭
                except:
                    try:
                        server.close()  # 强制关闭
                    except:
                        pass  # 忽略所有关闭异常