import base64
import hashlib
import hmac
import json
import logging
import time

import requests

from ..models import SystemSetting

logger = logging.getLogger('inventory')

# DingTalk API 端点
TOKEN_URL = 'https://oapi.dingtalk.com/gettoken'
APP_MESSAGE_URL = 'https://oapi.dingtalk.com/topapi/message/corpconversation/asyncsend_v2'
ROBOT_WEBHOOK_URL_TEMPLATE = 'https://oapi.dingtalk.com/robot/send?access_token={}'


class DingTalkError(Exception):
    """钉钉推送异常"""


class DingTalkService:
    """钉钉消息推送服务，支持自定义机器人 webhook 和自建应用推送。"""

    @staticmethod
    def _get_setting(key, default=''):
        return SystemSetting.get_setting(f'dingtalk_{key}', default)

    # ── 应用凭证管理 ──

    @staticmethod
    def get_access_token():
        """获取自建应用的 access_token，优先从缓存读取。"""
        token = SystemSetting.get_setting('dingtalk_access_token', '')
        expire_time_str = SystemSetting.get_setting('dingtalk_token_expire', '0')
        if token and expire_time_str and time.time() < float(expire_time_str):
            return token

        app_key = DingTalkService._get_setting('app_key')
        app_secret = DingTalkService._get_setting('app_secret')
        if not app_key or not app_secret:
            raise DingTalkError('钉钉应用配置不完整：缺少 AppKey 或 AppSecret')

        try:
            resp = requests.get(TOKEN_URL, params={
                'appkey': app_key,
                'appsecret': app_secret,
            }, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get('errcode') != 0:
                raise DingTalkError(f'获取 access_token 失败: {data.get("errmsg", "未知错误")}')

            token = data['access_token']
            expires_in = data.get('expires_in', 7200)
            SystemSetting.set_setting('dingtalk_access_token', token, '钉钉 access_token')
            SystemSetting.set_setting(
                'dingtalk_token_expire', str(time.time() + expires_in - 60), '钉钉 token 过期时间'
            )
            return token
        except requests.RequestException as e:
            raise DingTalkError(f'请求钉钉接口失败: {e}')

    # ── 机器人 Webhook ──

    @staticmethod
    def _get_robot_webhook():
        """获取机器人 webhook URL（含签名）。"""
        token = DingTalkService._get_setting('robot_token')
        if not token:
            raise DingTalkError('钉钉机器人配置不完整：缺少 Webhook Token')
        url = ROBOT_WEBHOOK_URL_TEMPLATE.format(token)

        secret = DingTalkService._get_setting('robot_secret')
        if secret:
            timestamp = str(int(time.time() * 1000))
            sign_str = timestamp + '\n' + secret
            signature = base64.b64encode(
                hmac.new(secret.encode(), sign_str.encode(), hashlib.sha256).digest()
            ).decode()
            url += f'&timestamp={timestamp}&sign={requests.utils.quote(signature)}'

        return url

    @staticmethod
    def _call_robot(payload):
        """调用机器人 webhook。"""
        webhook = DingTalkService._get_robot_webhook()
        try:
            resp = requests.post(webhook, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get('errcode') != 0:
                raise DingTalkError(f'机器人消息推送失败: {data.get("errmsg", "未知错误")}')
            return data
        except requests.RequestException as e:
            raise DingTalkError(f'请求钉钉机器人接口失败: {e}')

    @staticmethod
    def send_robot_text(content, at_mobiles=None, at_all=False):
        """通过机器人发送文本消息。"""
        payload = {
            'msgtype': 'text',
            'text': {'content': content},
            'at': {'atMobiles': at_mobiles or [], 'isAtAll': at_all},
        }
        return DingTalkService._call_robot(payload)

    @staticmethod
    def send_robot_markdown(title, text, at_mobiles=None, at_all=False):
        """通过机器人发送 Markdown 消息。"""
        payload = {
            'msgtype': 'markdown',
            'markdown': {'title': title, 'text': text},
            'at': {'atMobiles': at_mobiles or [], 'isAtAll': at_all},
        }
        return DingTalkService._call_robot(payload)

    @staticmethod
    def send_robot_action_card(title, text, single_title, single_url, btn_orientation='0'):
        """通过机器人发送 ActionCard 消息（整体跳转）。"""
        payload = {
            'msgtype': 'actionCard',
            'actionCard': {
                'title': title,
                'text': text,
                'singleTitle': single_title,
                'singleURL': single_url,
                'btnOrientation': btn_orientation,
            },
        }
        return DingTalkService._call_robot(payload)

    # ── 自建应用推送 ──

    @staticmethod
    def send_app_text(user_ids, content):
        """通过自建应用发送文本消息给指定用户。"""
        token = DingTalkService.get_access_token()
        agent_id = DingTalkService._get_setting('agent_id')
        if not agent_id:
            raise DingTalkError('钉钉应用配置不完整：缺少 AgentId')

        user_list = user_ids if isinstance(user_ids, str) else '|'.join(user_ids)
        payload = {
            'agent_id': int(agent_id),
            'userid_list': user_list,
            'msg': {
                'msgtype': 'text',
                'text': {'content': content},
            },
        }
        return DingTalkService._call_app(token, payload)

    @staticmethod
    def send_app_markdown(user_ids, title, text):
        """通过自建应用发送 Markdown 消息给指定用户。"""
        token = DingTalkService.get_access_token()
        agent_id = DingTalkService._get_setting('agent_id')
        if not agent_id:
            raise DingTalkError('钉钉应用配置不完整：缺少 AgentId')

        user_list = user_ids if isinstance(user_ids, str) else '|'.join(user_ids)
        payload = {
            'agent_id': int(agent_id),
            'userid_list': user_list,
            'msg': {
                'msgtype': 'markdown',
                'markdown': {'title': title, 'text': text},
            },
        }
        return DingTalkService._call_app(token, payload)

    @staticmethod
    def _call_app(token, payload):
        """调用自建应用消息接口。"""
        try:
            resp = requests.post(
                APP_MESSAGE_URL, params={'access_token': token},
                json=payload, timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get('errcode') != 0:
                raise DingTalkError(f'应用消息推送失败: {data.get("errmsg", "未知错误")}')
            return data
        except requests.RequestException as e:
            raise DingTalkError(f'请求钉钉应用接口失败: {e}')

    # ── 便捷调用（带开关检查，不抛异常） ──

    @staticmethod
    def notify_if_enabled(notification_type, **kwargs):
        """检查推送配置是否启用，如是则发送通知。静默处理异常，不干扰主流程。"""
        push_mode = DingTalkService._get_setting('push_mode')
        if push_mode not in ('robot', 'app'):
            return

        method_map = {
            'material_plan_review': DingTalkService.notify_material_plan_review,
            'delivery_created': DingTalkService.notify_delivery_created,
            'settlement_created': DingTalkService.notify_settlement_created,
            'inbound_created': DingTalkService.notify_inbound_created,
            'purchase_plan_created': DingTalkService.notify_purchase_plan_created,
        }

        method = method_map.get(notification_type)
        if not method:
            return

        try:
            method(**kwargs)
        except Exception:
            logger.exception('钉钉通知发送失败（已静默处理）: %s', notification_type)

    # ── 便捷通知方法 ──

    @staticmethod
    def notify_material_plan_review(plan_no, project_name, material_name, url):
        """材料计划审批通知。"""
        DingTalkService.send_robot_markdown(
            title='材料计划审批通知',
            text=(
                f'### 材料计划审批通知\n\n'
                f'- **计划单号**: {plan_no}\n'
                f'- **项目**: {project_name}\n'
                f'- **材料**: {material_name}\n'
                f'- **状态**: 待审批\n\n'
                f'> 请及时处理。\n'
            ),
        )

    @staticmethod
    def notify_delivery_created(delivery_no, supplier_name, material_name, quantity, url):
        """发货通知。"""
        DingTalkService.send_robot_markdown(
            title='发货通知',
            text=(
                f'### 发货通知\n\n'
                f'- **发货单号**: {delivery_no}\n'
                f'- **供应商**: {supplier_name}\n'
                f'- **材料**: {material_name}\n'
                f'- **数量**: {quantity}\n'
                f'- **状态**: 待确认\n\n'
                f'> 请及时确认收货。\n'
            ),
        )

    @staticmethod
    def notify_settlement_created(settlement_no, subcontractor_name, amount, url):
        """结算通知。"""
        DingTalkService.send_robot_markdown(
            title='结算通知',
            text=(
                f'### 结算通知\n\n'
                f'- **结算单号**: {settlement_no}\n'
                f'- **分包商**: {subcontractor_name}\n'
                f'- **金额**: {amount}\n'
                f'- **状态**: 待审批\n\n'
                f'> 请及时处理。\n'
            ),
        )

    @staticmethod
    def notify_inbound_created(inbound_no, material_name, quantity, project_name, url):
        """入库通知。"""
        DingTalkService.send_robot_markdown(
            title='入库通知',
            text=(
                f'### 入库通知\n\n'
                f'- **入库单号**: {inbound_no}\n'
                f'- **材料**: {material_name}\n'
                f'- **数量**: {quantity}\n'
                f'- **项目**: {project_name}\n\n'
                f'> 请确认入库信息。\n'
            ),
        )

    @staticmethod
    def notify_purchase_plan_created(plan_no, material_name, quantity, project_name, supplier_name, url):
        """采购申请通知。"""
        DingTalkService.send_robot_markdown(
            title='采购申请通知',
            text=(
                f'### 采购申请通知\n\n'
                f'- **采购单号**: {plan_no}\n'
                f'- **材料**: {material_name}\n'
                f'- **数量**: {quantity}\n'
                f'- **项目**: {project_name}\n'
                f'- **供应商**: {supplier_name}\n'
                f'- **状态**: 待审批\n\n'
                f'> 请及时处理。\n'
            ),
        )
