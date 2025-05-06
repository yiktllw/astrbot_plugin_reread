import asyncio
from typing import Dict

from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core import AstrBotConfig
import astrbot.core.message.components as Comp
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.platform import AstrMessageEvent
import random
from collections import deque

from astrbot.core.star.filter.event_message_type import EventMessageType


@register(
    "astrbot_plugin_reread",
    "Zhalslar",
    "复读插件",
    "1.0.5",
    "https://github.com/Zhalslar/astrbot_plugin_reread",
)
class RereadPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        # 是否要求消息要来自不同人才复读
        self.require_different_people: bool = config.get(
            "require_different_people", False
        )
        # 违禁词
        self.banned_words: str = config.get("banned_words", [])
        # 各消息类型的复读阈值
        self.thresholds: Dict = config.get("thresholds", {})
        # 支持的消息类型
        self.supported_type: list = list(self.thresholds.keys())
        # 复读概率
        self.repeat_probability: float = config.get("repeat_probability", 0.5)
        # 打断复读概率
        self.interrupt_probability: float = config.get("interrupt_probability", 0.1)
        # 复读冷却时间（秒）
        self.cooldown_seconds = config.get("cooldown_seconds", 30)
        # 存储每个群组的上一次复读的时间点
        self.repeat_cooldowns = {}  # {group_id: timestamp}
        # 存储每个群组的lock
        self.group_locks = {}
        # 存储每个群组的消息记录，值为 deque 对象
        self.messages_dict = {}
        """
        messages_dict = {
            "group_id": {
                "seg_type": [
                    {"send_id": send_id, "chain": chain}
                ]
            }
        }
        """

    async def get_group_lock(self, group_id):
        if group_id not in self.group_locks:
            self.group_locks[group_id] = asyncio.Lock()
        return self.group_locks[group_id]

    @filter.event_message_type(EventMessageType.ALL)
    async def reread_handle(self, event: AstrMessageEvent):
        """复读处理函数"""
        chain = event.get_messages()
        if not chain:
            return

        for seg in chain:
            # 过滤@bot的消息
            if isinstance(seg, Comp.At) and str(seg.qq) == event.get_self_id():
                return
            # 过滤违禁词
            elif isinstance(seg, Comp.Plain) and self.banned_words:
                for word in self.banned_words:
                    if word in seg.text:
                        return

        # 取第一个消息段判断消息类型是否支持
        first_seg = chain[0]
        seg_type = str(first_seg.type)
        if seg_type not in self.supported_type:
            return

        group_id = event.get_group_id()
        send_id = event.get_sender_id()

        # 获取当前群组的锁
        lock = await self.get_group_lock(group_id)
        async with lock:  # 加锁，防止并发

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

            # 获取当前时间
            msg_time = event.message_obj.timestamp

            # 检查是否处于冷却期
            if group_id in self.repeat_cooldowns:
                last_time = self.repeat_cooldowns[group_id]
                if msg_time - last_time < self.cooldown_seconds:
                    return

            # 如果该群组的消息记录中有 threshold 条消息，并且满足复读概率，则复读
            if (
                len(msg_list) >= self.thresholds.get(seg_type, 3)
                and random.random() < self.repeat_probability
                and all(
                    self.is_equal(msg_list[0]["chain"], msg["chain"]) for msg in msg_list
                )
            ):
                # 打断复读机制
                if random.random() < self.interrupt_probability:
                    chain = [Comp.Plain("打断！")]

                await event.send(MessageChain(chain=chain)) # type: ignore
                msg_list.clear()
                self.repeat_cooldowns[group_id] = msg_time
                event.stop_event()

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
            return seg1.qq == seg2.qq

        return False
