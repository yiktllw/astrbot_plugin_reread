from typing import Dict

from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core import AstrBotConfig
import astrbot.core.message.components as Comp
from astrbot.core.platform import AstrMessageEvent
import random
from collections import deque

from astrbot.core.star.filter.event_message_type import EventMessageType


@register(
    "astrbot_plugin_reread",
    "Zhalslar",
    "复读插件",
    "1.0.3",
    "https://github.com/Zhalslar/astrbot_plugin_reread",
)
class RereadPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.require_different_people: bool = config.get(
            "require_different_people", False
        )  # 是否要求消息要来自不同人才复读
        self.banned_words: str = config.get("banned_words", [])  # 违禁词
        self.thresholds: Dict = config.get("thresholds", {})  # 各消息类型的复读阈值
        self.supported_type: list = list(self.thresholds.keys())
        self.repeat_probability: float = config.get(
            "repeat_probability", 0.5
        )  # 复读概率
        self.messages_dict = {}  # 使用字典存储每个群组的消息记录，值为 deque 对象
        self.bot_id: str = ""

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
        if group_id not in self.messages_dict:
            self.messages_dict[group_id] = {
                key: deque(maxlen=self.thresholds.get(key))
                for key in self.supported_type
            }

        # 获取该群组的消息记录
        group_messages = self.messages_dict[group_id]
        msg_list = group_messages[seg_type]

        # 检查消息是否来自同一个用户, 如果来自同一个用户，清空消息记录
        if (
            self.require_different_people
            and msg_list
            and msg_list[-1]["send_id"] == send_id
        ):
            msg_list.clear()

        # 将当前消息和用户ID添加到该群组的消息记录中
        msg_list.append({"send_id": send_id, "chain": chain})

        # 如果该群组的消息记录中有 threshold 条消息，并且满足复读概率，则复读
        if (
            len(msg_list) >= self.thresholds.get(seg_type, 3)
            and random.random() < self.repeat_probability
            and all(
                self.is_equal(msg_list[0]["chain"], msg["chain"]) for msg in msg_list
            )
        ):
            yield event.chain_result(chain)
            msg_list.clear()

    def is_equal(
        self,
        chain1: list[Comp.BaseMessageComponent],
        chain2: list[Comp.BaseMessageComponent],
    ):
        """判断两条消息链是否满足相等条件"""
        if len(chain1) != len(chain2):
            return False
        # 只取第一个seg进行判断
        seg1 = chain1[0]
        seg2 = chain2[0]
        if isinstance(seg1, Comp.Plain) and isinstance(seg2, Comp.Plain):
            return seg1.text == seg2.text

        if isinstance(seg1, Comp.Image) and isinstance(seg2, Comp.Image):
            return seg1.file == seg2.file

        if isinstance(seg1, Comp.Face) and isinstance(seg2, Comp.Face):
            return seg1.id == seg2.id

        if isinstance(seg1, Comp.At) and isinstance(seg2, Comp.At):
            return seg1.qq == seg2.qq and seg1 != self.bot_id

        return False
