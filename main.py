import asyncio
from typing import Dict
import logging

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
    "v1.2.2",
    "https://github.com/Zhalslar/astrbot_plugin_reread",
)
class RereadPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.reread_group_whitelist = config.get("reread_group_whitelist", [])
        # 是否要求消息要来自不同人才复读
        self.require_different_people: bool = config.get(
            "require_different_people", False
        )
        # 违禁词
        self.banned_words: str = config.get("banned_words", [])
        # 各消息类型的复读阈值
        self.thresholds: Dict = config.get("thresholds", {
            "Plain": 3,
            "Image": 3, 
            "Face": 2,
            "At": 3
        })
        # 支持的消息类型
        self.supported_type: list = list(self.thresholds.keys())
        # 复读概率
        self.repeat_probability: float = config.get("repeat_probability", 0.5)
        # 打断复读概率
        self.interrupt_probability: float = config.get("interrupt_probability", 0.1)
        # 启用单条复读
        self.enable_single_repeat: bool = config.get("enable_single_repeat", False)
        # 单条复读概率
        self.single_repeat_probability: float = config.get("single_repeat_probability", 0.05)
        # 复读冷却时间（秒）
        self.cooldown_seconds = config.get("cooldown_seconds", 30)
        # 启用调试模式
        self.enable_debug: bool = config.get("enable_debug", False)
        
        # 初始化日志器
        self.logger = logging.getLogger(f"RereadPlugin_{id(self)}")
        if self.enable_debug and not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '[%(asctime)s] [复读插件] %(levelname)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.WARNING)
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
        
        # 输出初始化调试信息
        if self.enable_debug:
            self.logger.info("复读插件初始化完成")
            self.logger.debug(f"配置信息: 群聊白名单={self.reread_group_whitelist}, "
                           f"需要不同用户={self.require_different_people}, "
                           f"阈值设置={self.thresholds}, "
                           f"支持的消息类型={self.supported_type}, "
                           f"复读概率={self.repeat_probability}, "
                           f"单条复读={self.enable_single_repeat}({self.single_repeat_probability}), "
                           f"打断概率={self.interrupt_probability}, "
                           f"冷却时间={self.cooldown_seconds}秒")

    def debug_log(self, message: str, level: str = "debug"):
        """调试日志输出"""
        if not self.enable_debug:
            return
        
        if level == "info":
            self.logger.info(message)
        elif level == "warning":
            self.logger.warning(message)
        elif level == "error":
            self.logger.error(message)
        else:
            self.logger.debug(message)

    async def get_group_lock(self, group_id):
        if group_id not in self.group_locks:
            self.group_locks[group_id] = asyncio.Lock()
        return self.group_locks[group_id]

    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def reread_handle(self, event: AstrMessageEvent):
        """复读处理函数"""
        # 获取基本信息用于调试
        group_id = event.get_group_id()
        sender_id = event.get_sender_id()
        msg_text = event.message_str[:50] + "..." if len(event.message_str) > 50 else event.message_str
        
        self.debug_log(f"收到群 {group_id} 用户 {sender_id} 的消息: {msg_text}")
        
        # 过滤唤醒bot的消息
        if event.is_at_or_wake_command:
            self.debug_log(f"群 {group_id}: 跳过唤醒bot的消息")
            return
        # 群白名单
        if self.reread_group_whitelist and group_id not in self.reread_group_whitelist:
            self.debug_log(f"群 {group_id}: 不在白名单中，跳过处理")
            return
        # 过滤空消息
        chain = event.get_messages()
        if not chain:
            self.debug_log(f"群 {group_id}: 消息链为空，跳过处理")
            return
        # 过滤违禁词
        for word in self.banned_words:
            if word in event.message_str:
                self.debug_log(f"群 {group_id}: 消息包含违禁词 '{word}'，跳过处理")
                return

        # 取第一个消息段判断消息类型是否支持
        first_seg = chain[0]
        seg_type_raw = str(first_seg.type)
        # 提取类型名称，去掉 ComponentType. 前缀
        seg_type = seg_type_raw.replace("ComponentType.", "") if "ComponentType." in seg_type_raw else seg_type_raw
        
        self.debug_log(f"群 {group_id}: 原始消息类型: {seg_type_raw}, 处理后类型: {seg_type}")
        
        if seg_type not in self.supported_type:
            self.debug_log(f"群 {group_id}: 消息类型 '{seg_type}' 不支持，跳过处理")
            return
            
        self.debug_log(f"群 {group_id}: 处理 {seg_type} 类型消息")

        # 获取当前群组的锁
        lock = await self.get_group_lock(group_id)
        async with lock:  # 加锁，防止并发
            # 获取当前时间
            msg_time = event.message_obj.timestamp

            # 检查是否处于冷却期
            if group_id in self.repeat_cooldowns:
                last_time = self.repeat_cooldowns[group_id]
                cooldown_remaining = self.cooldown_seconds - (msg_time - last_time)
                if msg_time - last_time < self.cooldown_seconds:
                    self.debug_log(f"群 {group_id}: 处于冷却期，剩余 {cooldown_remaining:.1f} 秒")
                    return

            # 单条复读逻辑：如果启用了单条复读，按概率直接复读
            if self.enable_single_repeat:
                single_random = random.random()
                self.debug_log(f"群 {group_id}: 单条复读检查，随机值 {single_random:.3f}，阈值 {self.single_repeat_probability}")
                if single_random < self.single_repeat_probability:
                    self.debug_log(f"群 {group_id}: 触发单条复读！", "info")
                    # 打断复读机制
                    interrupt_random = random.random()
                    self.debug_log(f"群 {group_id}: 打断检查，随机值 {interrupt_random:.3f}，阈值 {self.interrupt_probability}")
                    if interrupt_random < self.interrupt_probability:
                        self.debug_log(f"群 {group_id}: 触发打断机制", "info")
                        chain = [Comp.Plain("打断！")]
                    else:
                        self.debug_log(f"群 {group_id}: 正常复读消息")
                    
                    await event.send(MessageChain(chain=chain))  # type: ignore
                    self.repeat_cooldowns[group_id] = msg_time
                    self.debug_log(f"群 {group_id}: 单条复读完成，设置冷却时间")
                    event.stop_event()
                    return
                else:
                    self.debug_log(f"群 {group_id}: 未触发单条复读")

            # 如果群组 ID 不在 msg_dict 中，初始化一个 deque 对象，最大长度为各自的阈值
            if group_id not in self.messages_dict:
                self.debug_log(f"群 {group_id}: 初始化消息记录")
                self.messages_dict[group_id] = {
                    key: deque(maxlen=self.thresholds.get(key))
                    for key in self.supported_type
                }

            # 获取该群组的消息记录
            group_messages = self.messages_dict[group_id]
            msg_list = group_messages[seg_type]

            # 检查消息是否来自同一个用户, 如果来自同一个用户，清空消息记录
            send_id = event.get_sender_id()
            if (
                self.require_different_people
                and msg_list
                and msg_list[-1]["send_id"] == send_id
            ):
                self.debug_log(f"群 {group_id}: 消息来自同一用户 {send_id}，清空消息记录")
                msg_list.clear()

            # 将当前消息和用户ID添加到该群组的消息记录中
            msg_list.append({"send_id": send_id, "chain": chain})
            self.debug_log(f"群 {group_id}: 添加消息到记录，当前记录数量: {len(msg_list)}/{self.thresholds.get(seg_type, 3)}")

            # 如果该群组的消息记录中有 threshold 条消息，并且满足复读概率，则复读
            threshold = self.thresholds.get(seg_type, 3)
            if len(msg_list) >= threshold:
                self.debug_log(f"群 {group_id}: 达到阈值 {threshold}，检查消息一致性")
                
                # 检查所有消息是否相等
                all_equal = all(
                    self.is_equal(msg_list[0]["chain"], msg["chain"])
                    for msg in msg_list
                )
                self.debug_log(f"群 {group_id}: 消息一致性检查结果: {all_equal}")
                
                if all_equal:
                    repeat_random = random.random()
                    self.debug_log(f"群 {group_id}: 阈值复读检查，随机值 {repeat_random:.3f}，阈值 {self.repeat_probability}")
                    
                    if repeat_random < self.repeat_probability:
                        self.debug_log(f"群 {group_id}: 触发阈值复读！", "info")
                        # 打断复读机制
                        interrupt_random = random.random()
                        self.debug_log(f"群 {group_id}: 打断检查，随机值 {interrupt_random:.3f}，阈值 {self.interrupt_probability}")
                        if interrupt_random < self.interrupt_probability:
                            self.debug_log(f"群 {group_id}: 触发打断机制", "info")
                            chain = [Comp.Plain("打断！")]
                        else:
                            self.debug_log(f"群 {group_id}: 正常复读消息")

                        await event.send(MessageChain(chain=chain))  # type: ignore
                        msg_list.clear()
                        self.repeat_cooldowns[group_id] = msg_time
                        self.debug_log(f"群 {group_id}: 阈值复读完成，设置冷却时间")
                        event.stop_event()
                    else:
                        self.debug_log(f"群 {group_id}: 未触发阈值复读")
                else:
                    self.debug_log(f"群 {group_id}: 消息不一致，无法复读")
            else:
                self.debug_log(f"群 {group_id}: 未达到阈值 {threshold}，继续收集消息")

    def is_equal(
        self,
        chain1: list[Comp.BaseMessageComponent],
        chain2: list[Comp.BaseMessageComponent],
    ):
        """判断两条消息链是否满足相等条件"""
        if len(chain1) != len(chain2):
            self.debug_log(f"消息链长度不匹配: {len(chain1)} vs {len(chain2)}")
            return False
        # 只取第一个seg进行判断
        seg1 = chain1[0]
        seg2 = chain2[0]
        
        result = False
        if isinstance(seg1, Comp.Plain) and isinstance(seg2, Comp.Plain):
            result = seg1.text == seg2.text
            self.debug_log(f"文本消息比较: '{seg1.text}' == '{seg2.text}' -> {result}")
        elif isinstance(seg1, Comp.Image) and isinstance(seg2, Comp.Image):
            result = seg1.file == seg2.file
            self.debug_log(f"图片消息比较: '{seg1.file}' == '{seg2.file}' -> {result}")
        elif isinstance(seg1, Comp.Face) and isinstance(seg2, Comp.Face):
            result = seg1.id == seg2.id
            self.debug_log(f"表情消息比较: '{seg1.id}' == '{seg2.id}' -> {result}")
        elif isinstance(seg1, Comp.At) and isinstance(seg2, Comp.At):
            result = seg1.qq == seg2.qq
            self.debug_log(f"At消息比较: '{seg1.qq}' == '{seg2.qq}' -> {result}")
        else:
            self.debug_log(f"消息类型不匹配或不支持: {type(seg1)} vs {type(seg2)}")

        return result
