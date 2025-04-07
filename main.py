from typing import Dict

from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core import AstrBotConfig
import astrbot.core.message.components as Comp
from astrbot.core.platform import AstrMessageEvent
import random
from collections import deque

from astrbot.core.star.filter.event_message_type import EventMessageType

# 使用字典存储每个群组的消息记录，值为 deque 对象
messages_dict = {}


@register("astrbot_plugin_reread", "Zhalslar", "复读插件", "1.0.0")
class RereadPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.require_different_people: bool = config.get('require_different_people') # 是否要求消息要来自不同人才复读
        self.banned_words: str = config.get('banned_words')  # 违禁词
        self.thresholds: Dict = config.get('thresholds',{}) # 各消息类型的复读阈值
        self.supported_type: list = list(self.thresholds.keys())
        self.repeat_probability: float = config.get('repeat_probability')  # 复读概率


    @filter.event_message_type(EventMessageType.ALL)
    async def reread_handle(self, event: AstrMessageEvent):
        """复读处理函数"""
        # 如果消息包含违禁词，则不进行复读
        message_str = event.get_message_str()
        for word in self.banned_words:
            if word in message_str:
                return

        chain = event.get_messages()
        if not chain:
            return

        # 取第一个消息段判断消息类型是否支持
        first_seg = chain[0]
        seg_type = str(first_seg.type)
        if seg_type not in self.supported_type:
            return

        # 不复读@bot开头的消息
        if isinstance(first_seg, Comp.At):
            self_id = event.get_self_id()
            if first_seg.qq == self_id:
                return

        group_id = event.get_group_id()
        send_id = event.get_sender_id()
        self.bot_id = event.get_self_id()

        global messages_dict

        """
        msg_dict = {
            "group_id": {
                "seg_type": [
                    {"send_id": send_id, "chain": chain}
                ]
            }
        }
        """
        # 如果群组 ID 不在 msg_dict 中，初始化一个 deque 对象，最大长度为各自的阈值
        if group_id not in messages_dict:
            messages_dict[group_id] = {
                key: deque(maxlen=self.thresholds.get(key)) for key in self.supported_type
            }

        # 获取该群组的消息记录
        group_messages = messages_dict[group_id]
        msg_list = group_messages[seg_type]

        # 检查消息是否来自同一个用户, 如果来自同一个用户，清空消息记录
        if (self.require_different_people
                and msg_list
                and msg_list[-1]["send_id"] == send_id
        ):
            msg_list.clear()

        # 将当前消息和用户ID添加到该群组的消息记录中
        msg_list.append({"send_id": send_id, "chain": chain})

        # 如果该群组的消息记录中有 threshold 条消息，并且满足复读概率，则复读
        if  (len(msg_list) >= self.thresholds.get(seg_type, 3)
                and random.random() < self.repeat_probability
                and all(self.is_equal(msg_list[0]["chain"], msg["chain"]) for msg in msg_list)
        ):
            yield event.chain_result(chain)
            msg_list.clear()


    def is_equal(self, chain: list[Comp.BaseMessageComponent], chain2: list[Comp.BaseMessageComponent]):
        """判断两条消息链是否满足相等条件"""
        if len(chain) != len(chain2):
            return False
        # 只取第一个seg进行判断
        seg = chain[0]
        seg2 = chain2[0]
        if seg.type != seg2.type:
            return False
        if isinstance(seg, Comp.Plain):
            if seg.text == seg2.text:
                return True
        if isinstance(seg, Comp.Image):
            if seg.file == seg2.file:
                return True
        if isinstance(seg, Comp.Face):
            if seg.id == seg2.id:
                return True
        if isinstance(seg, Comp.At):
            if seg.qq == seg2.qq:
                return True
        return False

