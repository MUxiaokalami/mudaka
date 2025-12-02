from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp

import os
import json
import random
import datetime
import pyodbc
from typing import Dict, Any, Tuple, List, Optional


PLUGIN_ID = "astrbot_plugin_draw_checkin"
# 新的数据目录
DATA_DIR = os.path.join("data", "plugin-data", PLUGIN_ID)
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, "checkin_data.json")
BIND_FILE = os.path.join(DATA_DIR, "account_bind.json")
LOTTERY_ITEMS_FILE = os.path.join(DATA_DIR, "lottery_items.json")  # 抽奖物品配置文件
GROUP_CONFIG_FILE = os.path.join(DATA_DIR, "group_config.json")  # 群组独立配置


def _load_group_config() -> Dict[str, Any]:
    """加载群组配置"""
    try:
        if os.path.exists(GROUP_CONFIG_FILE):
            with open(GROUP_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"加载群组配置失败: {e}")
        return {}


def _save_group_config(config: Dict[str, Any]) -> None:
    """保存群组配置"""
    try:
        os.makedirs(os.path.dirname(GROUP_CONFIG_FILE), exist_ok=True)
        with open(GROUP_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存群组配置失败: {e}")


def _load_lottery_items() -> Dict[str, Any]:
    """加载抽奖物品配置"""
    try:
        if os.path.exists(LOTTERY_ITEMS_FILE):
            with open(LOTTERY_ITEMS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        
        # 默认抽奖配置
        default_items = {
            "items": [
                {
                    "id": 1,
                    "name": "积分",
                    "type": "points",
                    "min_amount": 10,
                    "max_amount": 100,
                    "probability": 0.4,
                    "direct_to_account": True
                },
                {
                    "id": 2,
                    "name": "元宝",
                    "type": "ingots",
                    "min_amount": 5,
                    "max_amount": 50,
                    "probability": 0.4,
                    "direct_to_account": True
                },
                {
                    "id": 3,
                    "name": "祝福宝石",
                    "type": "item",
                    "item_code": "bless",
                    "min_amount": 1,
                    "max_amount": 3,
                    "probability": 0.1,
                    "direct_to_account": False,
                    "description": "用于装备强化"
                },
                {
                    "id": 4,
                    "name": "灵魂宝石",
                    "type": "item",
                    "item_code": "soul",
                    "min_amount": 1,
                    "max_amount": 2,
                    "probability": 0.05,
                    "direct_to_account": False,
                    "description": "用于装备强化"
                },
                {
                    "id": 5,
                    "name": "生命宝石",
                    "type": "item",
                    "item_code": "life",
                    "min_amount": 1,
                    "max_amount": 1,
                    "probability": 0.03,
                    "direct_to_account": False,
                    "description": "用于装备升级"
                },
                {
                    "id": 6,
                    "name": "创造宝石",
                    "type": "item",
                    "item_code": "create",
                    "min_amount": 1,
                    "max_amount": 1,
                    "probability": 0.01,
                    "direct_to_account": False,
                    "description": "用于装备合成"
                },
                {
                    "id": 7,
                    "name": "幸运宝箱",
                    "type": "item",
                    "item_code": "lucky_box",
                    "min_amount": 1,
                    "max_amount": 1,
                    "probability": 0.01,
                    "direct_to_account": False,
                    "description": "随机开出稀有物品"
                }
            ],
            "special_rewards": [
                {
                    "id": 100,
                    "name": "双倍奖励",
                    "type": "multiplier",
                    "multiplier": 2.0,
                    "probability": 0.02,
                    "description": "本次抽奖获得双倍奖励"
                },
                {
                    "id": 101,
                    "name": "再来一次",
                    "type": "extra_chance",
                    "extra_chances": 1,
                    "probability": 0.03,
                    "description": "获得额外抽奖机会"
                }
            ]
        }
        
        # 保存默认配置
        with open(LOTTERY_ITEMS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_items, f, ensure_ascii=False, indent=2)
        
        return default_items
    except Exception as e:
        logger.error(f"加载抽奖物品配置失败: {e}")
        return {"items": [], "special_rewards": []}


def _get_group_db_config(group_id: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """获取群组特定的数据库配置"""
    group_configs = _load_group_config()
    
    if group_id in group_configs and "db_config" in group_configs[group_id]:
        # 使用群组特定的配置
        group_db_cfg = group_configs[group_id]["db_config"]
        return {
            "server": group_db_cfg.get("db_server", cfg.get("db_server", "202.189.8.117")),
            "port": group_db_cfg.get("db_port", cfg.get("db_port", "1433")),
            "database": group_db_cfg.get("db_database", cfg.get("db_database", "MuOnline")),
            "username": group_db_cfg.get("db_username", cfg.get("db_username", "sa")),
            "password": group_db_cfg.get("db_password", cfg.get("db_password", "bvT9527zzvipFEG2ic4R0#b")),
            "driver": group_db_cfg.get("db_driver", cfg.get("db_driver", "FreeTDS"))
        }
    
    # 使用全局配置
    return {
        "server": cfg.get("db_server", "202.189.8.117"),
        "port": cfg.get("db_port", "1433"),
        "database": cfg.get("db_database", "MuOnline"),
        "username": cfg.get("db_username", "sa"),
        "password": cfg.get("db_password", "bvT9527zzvipFEG2ic4R0#b"),
        "driver": cfg.get("db_driver", "FreeTDS")
    }


def _get_db_connection(group_id: str, cfg: Dict[str, Any]):
    """获取数据库连接（支持群组独立配置）"""
    try:
        db_config = _get_group_db_config(group_id, cfg)
        connection_string = (
            f"DRIVER={db_config['driver']};"
            f"SERVER={db_config['server']},{db_config['port']};"
            f"DATABASE={db_config['database']};"
            f"UID={db_config['username']};"
            f"PWD={db_config['password']}"
        )
        conn = pyodbc.connect(connection_string)
        return conn
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return None


def _load_data() -> Dict[str, Any]:
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"加载打卡数据失败: {e}")
        return {}


def _save_data(data: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存打卡数据失败: {e}")


def _load_bind_data() -> Dict[str, Any]:
    """加载账号绑定数据"""
    try:
        if os.path.exists(BIND_FILE):
            with open(BIND_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"加载账号绑定数据失败: {e}")
        return {}


def _save_bind_data(data: Dict[str, Any]) -> None:
    """保存账号绑定数据"""
    try:
        os.makedirs(os.path.dirname(BIND_FILE), exist_ok=True)
        with open(BIND_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存账号绑定数据失败: {e}")


def _today() -> datetime.date:
    return datetime.date.today()


def _yesterday() -> datetime.date:
    return datetime.date.today() - datetime.timedelta(days=1)


def _get_ctx_id(event: AstrMessageEvent, cfg: Dict[str, Any]) -> str:
    """获取上下文ID（支持群组独立）"""
    try:
        scope = (cfg.get("storage_scope") or "group").lower()
        platform = event.get_platform_name()
        group_id = event.get_group_id() or "default"
        
        if scope == "global":
            return f"{platform}:GLOBAL"
        if scope == "user":
            key = event.get_sender_id()
            return f"{platform}:U:{key}"
        # default group
        return f"{platform}:G:{group_id}"
    except Exception:
        return "default"


def _default_user(user_id: str, username: str) -> Dict[str, Any]:
    return {
        "user_id": user_id,
        "username": username,
        "total_days": 0,
        "consecutive_days": 0,
        "last_checkin": "",
        "lottery_chances": 0,  # 抽奖机会
        "lottery_history": [],  # 抽奖历史
        "pending_items": []  # 待兑换物品
    }


def _get_game_account_info(group_id: str, cfg: Dict[str, Any], account_name: str):
    """获取游戏账号信息（支持群组独立数据库）"""
    conn = _get_db_connection(group_id, cfg)
    if not conn:
        return None
        
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT memb___id, jf, yb FROM MEMB_INFO WHERE memb___id = ?", 
            account_name
        )
        row = cursor.fetchone()
        
        if row:
            return {
                "account": row[0],
                "points": row[1] if row[1] is not None else 0,
                "ingots": row[2] if row[2] is not None else 0
            }
        return None
    except Exception as e:
        logger.error(f"查询游戏账号失败: {e}")
        return None
    finally:
        conn.close()


def _update_game_account_assets(group_id: str, cfg: Dict[str, Any], account_name: str, points_change: int = 0, ingots_change: int = 0):
    """更新游戏账号的积分和元宝（支持群组独立数据库）"""
    conn = _get_db_connection(group_id, cfg)
    if not conn:
        return False
        
    try:
        cursor = conn.cursor()
        
        update_sql = "UPDATE MEMB_INFO SET "
        params = []
        
        if points_change != 0:
            update_sql += "jf = jf + ?, "
            params.append(points_change)
            
        if ingots_change != 0:
            update_sql += "yb = yb + ?, "
            params.append(ingots_change)
            
        update_sql = update_sql.rstrip(", ")
        update_sql += " WHERE memb___id = ?"
        params.append(account_name)
        
        cursor.execute(update_sql, params)
        conn.commit()
        
        return cursor.rowcount > 0
        
    except Exception as e:
        logger.error(f"更新游戏账号资产失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def _get_user_game_account(bind_data: Dict[str, Any], user_id: str) -> str:
    """根据用户ID获取绑定的游戏账号"""
    return bind_data.get(user_id, "")


def _get_random_signature(cfg: Dict[str, Any]) -> str:
    """获取随机签名"""
    signature_messages = cfg.get("signature_messages", [
        "奇迹世界因你而精彩！",
        "坚持打卡，福利不断！",
        "勇者大陆欢迎你的到来！",
        "每日打卡，战力飙升！",
        "奇迹相伴，快乐相随！"
    ])
    return random.choice(signature_messages)


def _format_with_emoji(cfg: Dict[str, Any], text: str, emoji_dict: Dict[str, str]) -> str:
    """根据配置决定是否使用emoji格式化文本"""
    use_emoji = cfg.get("use_emoji", True)
    if use_emoji:
        for plain, emoji in emoji_dict.items():
            text = text.replace(plain, emoji)
    return text


def _format_message(cfg: Dict[str, Any], title: str, content_lines: list) -> str:
    """统一格式化消息"""
    separator = cfg.get("message_separator", "--------")
    use_emoji = cfg.get("use_emoji", True)
    
    emoji_map = {
        "✨": "✨",
        "打卡信息": "📊 打卡信息",
        "绑定信息": "🔗 绑定信息",
        "抽奖信息": "🎯 抽奖信息",
        "游戏账号信息": "🎮 游戏账号信息"
    }
    
    if use_emoji:
        formatted_title = _format_with_emoji(cfg, f"✨ {title}", emoji_map)
    else:
        formatted_title = f"* {title}"
    
    lines = [formatted_title, separator]
    lines.extend(content_lines)
    lines.append(separator)
    
    signature = _get_random_signature(cfg)
    if use_emoji:
        lines.append(f"💫 {signature}")
    else:
        lines.append(f"* {signature}")
    
    return "\n".join(lines)


def _is_checkin_time_allowed(cfg: Dict[str, Any]) -> Tuple[bool, str]:
    """检查当前时间是否在允许的打卡时间内"""
    try:
        now = datetime.datetime.now()
        current_hour = now.hour
        current_minute = now.minute
        current_time_minutes = current_hour * 60 + current_minute
        
        start_time_str = cfg.get("checkin_start_time", "00:00")
        end_time_str = cfg.get("checkin_end_time", "23:59")
        enable_time_limit = cfg.get("enable_checkin_time_limit", False)
        
        if not enable_time_limit:
            return True, ""
        
        start_hour, start_minute = map(int, start_time_str.split(':'))
        end_hour, end_minute = map(int, end_time_str.split(':'))
        
        start_time_minutes = start_hour * 60 + start_minute
        end_time_minutes = end_hour * 60 + end_minute
        
        if start_time_minutes <= current_time_minutes <= end_time_minutes:
            return True, ""
        else:
            start_display = f"{start_hour:02d}:{start_minute:02d}"
            end_display = f"{end_hour:02d}:{end_minute:02d}"
            return False, f"当前时间不在打卡时间内\n打卡时间：{start_display} - {end_display}"
            
    except Exception as e:
        logger.error(f"检查打卡时间失败: {e}")
        return True, ""


def _perform_lottery(group_id: str, cfg: Dict[str, Any], user_id: str, game_account: str) -> Tuple[Dict[str, Any], str]:
    """执行抽奖
    返回: (抽奖结果, 消息)
    """
    lottery_config = _load_lottery_items()
    items = lottery_config.get("items", [])
    special_rewards = lottery_config.get("special_rewards", [])
    
    if not items:
        return {}, "❌ 抽奖配置错误，请联系管理员"
    
    # 计算总概率
    total_prob = sum(item["probability"] for item in items)
    total_special_prob = sum(reward["probability"] for reward in special_rewards)
    
    # 抽奖
    roll = random.random() * (total_prob + total_special_prob)
    
    result = {}
    message_lines = []
    extra_chances = 0
    
    if roll <= total_prob:
        # 抽中普通物品
        cumulative_prob = 0
        for item in items:
            cumulative_prob += item["probability"]
            if roll <= cumulative_prob:
                result = item.copy()
                break
    else:
        # 抽中特殊奖励
        roll -= total_prob
        cumulative_prob = 0
        for reward in special_rewards:
            cumulative_prob += reward["probability"]
            if roll <= cumulative_prob:
                result = reward.copy()
                break
    
    if not result:
        return {}, "❌ 抽奖失败，请稍后重试"
    
    # 处理结果
    result_type = result.get("type")
    
    if result_type == "points":
        amount = random.randint(result["min_amount"], result["max_amount"])
        if _update_game_account_assets(group_id, cfg, game_account, points_change=amount):
            result["actual_amount"] = amount
            message_lines.append(f"🎉 恭喜！获得 {amount} 积分")
        else:
            return {}, "❌ 发放积分失败，请联系管理员"
    
    elif result_type == "ingots":
        amount = random.randint(result["min_amount"], result["max_amount"])
        if _update_game_account_assets(group_id, cfg, game_account, ingots_change=amount):
            result["actual_amount"] = amount
            message_lines.append(f"🎉 恭喜！获得 {amount} 元宝")
        else:
            return {}, "❌ 发放元宝失败，请联系管理员"
    
    elif result_type == "item":
        amount = random.randint(result["min_amount"], result["max_amount"])
        result["actual_amount"] = amount
        message_lines.append(f"🎁 恭喜！获得 {result['name']} × {amount}")
        message_lines.append(f"💡 请私聊GM兑换物品")
    
    elif result_type == "multiplier":
        multiplier = result.get("multiplier", 2.0)
        message_lines.append(f"✨ 获得特殊奖励：{result['name']}")
        # 实际使用时需要结合下一次抽奖
        result["multiplier"] = multiplier
    
    elif result_type == "extra_chance":
        extra_chances = result.get("extra_chances", 1)
        message_lines.append(f"🎊 获得特殊奖励：{result['name']}")
        result["extra_chances"] = extra_chances
    
    # 记录抽奖历史
    result["timestamp"] = datetime.datetime.now().isoformat()
    result["user_id"] = user_id
    
    return result, "\n".join(message_lines), extra_chances


def _update_consecutive_days(info: Dict[str, Any], today: datetime.date) -> None:
    """更新连续打卡天数"""
    last_checkin = info.get("last_checkin")
    
    if not last_checkin:
        info["consecutive_days"] = 1
        return
    
    try:
        last_date = datetime.date.fromisoformat(last_checkin)
        yesterday = _yesterday()
        
        if last_date == yesterday:
            info["consecutive_days"] = info.get("consecutive_days", 0) + 1
        elif last_date == today:
            pass
        else:
            info["consecutive_days"] = 1
    except ValueError:
        info["consecutive_days"] = 1


@register("astrbot_plugin_draw_checkin", "小卡拉米", "抽奖打卡插件", "2.0.0")
class DrawCheckinPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.data: Dict[str, Any] = _load_data()
        self.bind_data: Dict[str, Any] = _load_bind_data()
        self._cfg_obj = config
        self._cfg_cache: Dict[str, Any] = dict(config or {})

    def _curr_cfg(self) -> Dict[str, Any]:
        try:
            if self._cfg_obj is not None:
                return self._cfg_obj
        except Exception:
            pass
        return self._cfg_cache

    def _get_group_id(self, event: AstrMessageEvent) -> str:
        """获取群组ID"""
        return event.get_group_id() or "default"

    def _is_group_admin(self, event: AstrMessageEvent) -> bool:
        """检查用户是否为群管理员或群主"""
        user_id = event.get_sender_id()
        
        try:
            if event.is_admin():
                return True
        except Exception:
            pass
        
        try:
            raw = event.message_obj.raw_message
            if isinstance(raw, dict):
                sender = raw.get("sender", {}) or {}
                role = str(sender.get("role", "")).lower()
                if role in {"owner", "admin"}:
                    return True
        except Exception:
            pass
        
        return False

    def _get_user_bucket(self, event: AstrMessageEvent) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        ctx_id = _get_ctx_id(event, self._curr_cfg())
        user_id = event.get_sender_id()
        username = event.get_sender_name()
        bucket = self.data.setdefault(ctx_id, {})
        info = bucket.setdefault(user_id, _default_user(user_id, username))
        info["username"] = username
        return bucket, info

    @filter.command("打卡", alias={"打卡"})
    async def checkin(self, event: AstrMessageEvent):
        try:
            user_id = event.get_sender_id()
            group_id = self._get_group_id(event)
            
            # 检查时间
            cfg = self._curr_cfg()
            is_allowed, time_error_msg = _is_checkin_time_allowed(cfg)
            if not is_allowed:
                yield event.plain_result(f"❌ 打卡失败：{time_error_msg}")
                return
            
            # 检查绑定
            game_account = _get_user_game_account(self.bind_data, user_id)
            if not game_account:
                yield event.plain_result(
                    "❌ 打卡失败：您尚未绑定游戏账号！\n"
                    "请先使用命令：/绑定游戏账号 [你的游戏账号]\n"
                    "例如：/绑定游戏账号 mygame123"
                )
                return

            bucket, info = self._get_user_bucket(event)
            today = _today()

            if info.get("last_checkin") == today.isoformat():
                yield event.plain_result("今日已打卡，请勿重复~")
                return

            # 检查游戏账号
            account_info = _get_game_account_info(group_id, cfg, game_account)
            if not account_info:
                yield event.plain_result("❌ 打卡失败：游戏账号不存在，请检查账号是否正确或联系管理员")
                return

            # 更新连续打卡天数
            _update_consecutive_days(info, today)

            # 发放抽奖机会
            base_chances = int(cfg.get("base_lottery_chances", 1))
            consecutive_bonus = min(info.get("consecutive_days", 0) // 7, 3)  # 每7天多1次，最多3次
            total_chances = base_chances + consecutive_bonus
            
            info["lottery_chances"] = info.get("lottery_chances", 0) + total_chances
            info["total_days"] = info.get("total_days", 0) + 1
            info["last_checkin"] = today.isoformat()

            _save_data(self.data)

            # 生成消息
            use_emoji = cfg.get("use_emoji", True)
            separator = cfg.get("message_separator", "--------")
            
            if use_emoji:
                lines = [
                    "✅ 打卡成功",
                    separator,
                    f"📅 累计打卡：{info['total_days']}天",
                    f"🔥 连续打卡：{info.get('consecutive_days', 0)}天",
                    f"🎯 获得抽奖机会：{total_chances}次",
                    f"💰 剩余抽奖机会：{info['lottery_chances']}次"
                ]
            else:
                lines = [
                    "✅ 打卡成功",
                    separator,
                    f"累计打卡：{info['total_days']}天",
                    f"连续打卡：{info.get('consecutive_days', 0)}天",
                    f"获得抽奖机会：{total_chances}次",
                    f"剩余抽奖机会：{info['lottery_chances']}次"
                ]
                
            if consecutive_bonus > 0:
                lines.append(f"🎊 连续打卡奖励：额外{consecutive_bonus}次抽奖机会")
            
            signature = _get_random_signature(cfg)
            lines.append(separator)
            if use_emoji:
                lines.append(f"💫 {signature}")
            else:
                lines.append(f"* {signature}")
            
            body = "\n".join(lines)
            at = Comp.At(qq=user_id)
            yield event.chain_result([at, Comp.Plain("\n" + body)])
            
        except Exception as e:
            logger.error(f"打卡失败: {e}")
            yield event.plain_result("❌ 打卡出现异常，请稍后再试")

    @filter.command("抽奖")
    async def lottery(self, event: AstrMessageEvent, 次数: str = "1"):
        """抽奖命令"""
        try:
            user_id = event.get_sender_id()
            group_id = self._get_group_id(event)
            
            # 解析抽奖次数
            try:
                times = int(次数)
                if times <= 0 or times > 10:
                    yield event.plain_result("❌ 抽奖次数必须在1-10次之间")
                    return
            except ValueError:
                yield event.plain_result("❌ 请输入有效的抽奖次数，例如：/抽奖 3")
                return
            
            # 检查绑定
            game_account = _get_user_game_account(self.bind_data, user_id)
            if not game_account:
                yield event.plain_result(
                    "❌ 抽奖失败：您尚未绑定游戏账号！\n"
                    "请先使用命令：/绑定游戏账号 [你的游戏账号]"
                )
                return
            
            bucket, info = self._get_user_bucket(event)
            available_chances = info.get("lottery_chances", 0)
            
            if available_chances < times:
                yield event.plain_result(f"❌ 抽奖失败：抽奖机会不足\n剩余抽奖机会：{available_chances}次")
                return
            
            cfg = self._curr_cfg()
            use_emoji = cfg.get("use_emoji", True)
            separator = cfg.get("message_separator", "--------")
            
            # 执行抽奖
            results = []
            extra_chances_total = 0
            multiplier = 1.0
            
            for i in range(times):
                result, message, extra_chances = _perform_lottery(group_id, cfg, user_id, game_account)
                if not result:
                    yield event.plain_result(message)
                    return
                
                # 处理特殊效果
                if result.get("type") == "multiplier":
                    multiplier = result.get("multiplier", 2.0)
                    # 特殊奖励不计入消耗
                    continue
                elif result.get("type") == "extra_chance":
                    extra_chances_total += result.get("extra_chances", 1)
                    # 特殊奖励不计入消耗
                    continue
                
                results.append((result, message))
            
            # 扣除抽奖机会（只扣除实际抽奖次数，不包括特殊奖励）
            info["lottery_chances"] = available_chances - len(results)
            
            # 添加额外机会
            if extra_chances_total > 0:
                info["lottery_chances"] += extra_chances_total
            
            # 记录抽奖历史
            lottery_history = info.get("lottery_history", [])
            for result, _ in results:
                lottery_history.append({
                    "item": result.get("name"),
                    "type": result.get("type"),
                    "amount": result.get("actual_amount", 1),
                    "timestamp": result.get("timestamp")
                })
            info["lottery_history"] = lottery_history[-50:]  # 只保留最近50条
            
            # 保存数据
            _save_data(self.data)
            
            # 生成消息
            if use_emoji:
                lines = ["🎰 抽奖结果", separator]
            else:
                lines = ["抽奖结果", separator]
            
            for idx, (result, message) in enumerate(results, 1):
                if len(results) > 1:
                    lines.append(f"第{idx}次：{message}")
                else:
                    lines.append(message)
            
            if extra_chances_total > 0:
                lines.append(f"🎊 获得额外抽奖机会：{extra_chances_total}次")
            
            lines.append(separator)
            lines.append(f"剩余抽奖机会：{info['lottery_chances']}次")
            
            # 如果有物品需要兑换
            item_results = [r for r, _ in results if r.get("type") == "item"]
            if item_results:
                lines.append(separator)
                lines.append("📝 需要兑换的物品：")
                for result in item_results:
                    lines.append(f"- {result.get('name')} × {result.get('actual_amount', 1)}")
                lines.append("💡 请私聊GM兑换物品")
            
            signature = _get_random_signature(cfg)
            lines.append(separator)
            if use_emoji:
                lines.append(f"💫 {signature}")
            else:
                lines.append(f"* {signature}")
            
            body = "\n".join(lines)
            at = Comp.At(qq=user_id)
            yield event.chain_result([at, Comp.Plain("\n" + body)])
            
        except Exception as e:
            logger.error(f"抽奖失败: {e}")
            yield event.plain_result("❌ 抽奖出现异常，请稍后再试")

    @filter.command("绑定游戏账号")
    async def bind_game_account(self, event: AstrMessageEvent, 账号: str = ""):
        """绑定游戏账号"""
        try:
            if not 账号:
                yield event.plain_result("❌ 请提供游戏账号名称，格式：/绑定游戏账号 [账号]")
                return
                
            user_id = event.get_sender_id()
            group_id = self._get_group_id(event)
            cfg = self._curr_cfg()
            
            # 检查是否已绑定
            if user_id in self.bind_data:
                current_account = self.bind_data[user_id]
                yield event.plain_result(
                    f"❌ 您已绑定游戏账号：{current_account}\n"
                    f"如需更换绑定，请先使用「/解绑游戏账号」命令解除当前绑定"
                )
                return
            
            # 检查游戏账号是否存在
            game_account_info = _get_game_account_info(group_id, cfg, 账号)
            if not game_account_info:
                yield event.plain_result(f"❌ 绑定失败：游戏账号 '{账号}' 不存在，请检查账号名称")
                return
            
            # 检查是否已被绑定
            for uid, bound_account in self.bind_data.items():
                if bound_account == 账号 and uid != user_id:
                    yield event.plain_result(f"❌ 绑定失败：游戏账号 '{账号}' 已被其他用户绑定")
                    return
            
            # 绑定账号
            self.bind_data[user_id] = 账号
            _save_bind_data(self.bind_data)
            
            use_emoji = cfg.get("use_emoji", True)
            if use_emoji:
                content_lines = [
                    f"👤 QQ用户：{user_id}",
                    f"🎮 游戏账号：{账号}",
                    f"💎 当前积分：{game_account_info['points']}",
                    f"🪙 当前元宝：{game_account_info['ingots']}",
                ]
            else:
                content_lines = [
                    f"QQ用户：{user_id}",
                    f"游戏账号：{账号}",
                    f"当前积分：{game_account_info['points']}",
                    f"当前元宝：{game_account_info['ingots']}",
                ]
            
            message = _format_message(cfg, "绑定成功", content_lines)
            yield event.plain_result(message)
                
        except Exception as e:
            logger.error(f"绑定游戏账号失败: {e}")
            yield event.plain_result("❌ 绑定失败，请稍后再试")

    @filter.command("解绑游戏账号")
    async def unbind_game_account(self, event: AstrMessageEvent):
        """解绑游戏账号"""
        try:
            user_id = event.get_sender_id()
            
            if user_id in self.bind_data:
                account = self.bind_data[user_id]
                del self.bind_data[user_id]
                _save_bind_data(self.bind_data)
                yield event.plain_result(f"✅ 解绑成功！已解除游戏账号 '{account}' 的绑定")
            else:
                yield event.plain_result("❌ 解绑失败：您尚未绑定任何游戏账号")
                
        except Exception as e:
            logger.error(f"解绑游戏账号失败: {e}")
            yield event.plain_result("❌ 解绑失败，请稍后再试")

    @filter.command("我的绑定")
    async def my_binding(self, event: AstrMessageEvent):
        """查看我的绑定信息"""
        try:
            user_id = event.get_sender_id()
            group_id = self._get_group_id(event)
            cfg = self._curr_cfg()
            use_emoji = cfg.get("use_emoji", True)
            
            if user_id in self.bind_data:
                account = self.bind_data[user_id]
                game_account_info = _get_game_account_info(group_id, cfg, account)
                
                if use_emoji:
                    content_lines = [
                        f"👤 QQ用户：{user_id}",
                        f"🎮 游戏账号：{account}",
                    ]
                else:
                    content_lines = [
                        f"QQ用户：{user_id}",
                        f"游戏账号：{账号}",
                    ]
                
                if game_account_info:
                    if use_emoji:
                        content_lines.extend([
                            f"💎 当前积分：{game_account_info['points']}",
                            f"🪙 当前元宝：{game_account_info['ingots']}",
                            f"✅ 绑定状态：正常"
                        ])
                    else:
                        content_lines.extend([
                            f"当前积分：{game_account_info['points']}",
                            f"当前元宝：{game_account_info['ingots']}",
                            f"绑定状态：正常"
                        ])
                else:
                    if use_emoji:
                        content_lines.append(f"❌ 绑定状态：游戏账号不存在")
                    else:
                        content_lines.append(f"绑定状态：游戏账号不存在")
                    
                message = _format_message(cfg, "我的绑定信息", content_lines)
                yield event.plain_result(message)
            else:
                yield event.plain_result("❌ 您尚未绑定任何游戏账号\n💡 请使用：/绑定游戏账号 [账号]")
                
        except Exception as e:
            logger.error(f"查询绑定信息失败: {e}")
            yield event.plain_result("❌ 查询失败，请稍后再试")

    @filter.command("抽奖机会")
    async def lottery_chances(self, event: AstrMessageEvent):
        """查看抽奖机会"""
        try:
            _, info = self._get_user_bucket(event)
            user_id = event.get_sender_id()
            cfg = self._curr_cfg()
            use_emoji = cfg.get("use_emoji", True)
            
            chances = info.get("lottery_chances", 0)
            total_days = info.get("total_days", 0)
            consecutive_days = info.get("consecutive_days", 0)
            
            if use_emoji:
                lines = [
                    f"👤 用户：{info.get('username', user_id)}",
                    f"🎯 剩余抽奖机会：{chances}次",
                    f"📅 累计打卡：{total_days}天",
                    f"🔥 连续打卡：{consecutive_days}天",
                ]
            else:
                lines = [
                    f"用户：{info.get('username', user_id)}",
                    f"剩余抽奖机会：{chances}次",
                    f"累计打卡：{total_days}天",
                    f"连续打卡：{consecutive_days}天",
                ]
            
            # 显示连续打卡奖励信息
            if consecutive_days >= 7:
                bonus = min(consecutive_days // 7, 3)
                lines.append(f"🎊 连续打卡奖励：额外{bonus}次抽奖机会")
            
            message = _format_message(cfg, "抽奖机会信息", lines)
            yield event.plain_result(message)
            
        except Exception as e:
            logger.error(f"查询抽奖机会失败: {e}")
            yield event.plain_result("❌ 查询失败，请稍后再试")

    @filter.command("抽奖历史")
    async def lottery_history(self, event: AstrMessageEvent):
        """查看抽奖历史"""
        try:
            _, info = self._get_user_bucket(event)
            user_id = event.get_sender_id()
            cfg = self._curr_cfg()
            use_emoji = cfg.get("use_emoji", True)
            
            history = info.get("lottery_history", [])
            
            if not history:
                yield event.plain_result("📭 暂无抽奖历史")
                return
            
            if use_emoji:
                lines = [f"📜 {info.get('username', user_id)}的抽奖历史", "--------"]
            else:
                lines = [f"{info.get('username', user_id)}的抽奖历史", "--------"]
            
            # 显示最近10条记录
            for record in history[-10:]:
                item_name = record.get("item", "未知")
                amount = record.get("amount", 1)
                timestamp = record.get("timestamp", "")
                
                try:
                    dt = datetime.datetime.fromisoformat(timestamp)
                    time_str = dt.strftime("%m-%d %H:%M")
                except:
                    time_str = "未知时间"
                
                lines.append(f"{time_str} - {item_name} × {amount}")
            
            lines.append("--------")
            lines.append(f"共计 {len(history)} 条记录")
            
            yield event.plain_result("\n".join(lines))
            
        except Exception as e:
            logger.error(f"查询抽奖历史失败: {e}")
            yield event.plain_result("❌ 查询失败，请稍后再试")

    @filter.command("打卡查询", alias={"查询打卡", "我的打卡"})
    async def query_assets(self, event: AstrMessageEvent):
        try:
            _, info = self._get_user_bucket(event)
            user_id = event.get_sender_id()
            group_id = self._get_group_id(event)
            cfg = self._curr_cfg()
            use_emoji = cfg.get("use_emoji", True)
            
            game_account = _get_user_game_account(self.bind_data, user_id)
            account_info = _get_game_account_info(group_id, cfg, game_account) if game_account else None
            
            if use_emoji:
                content_lines = [
                    f"👤 用户：{info.get('username', user_id)}",
                    f"📅 累计打卡：{info.get('total_days', 0)}天",
                    f"🔥 连续打卡：{info.get('consecutive_days', 0)}天",
                    f"🎯 剩余抽奖机会：{info.get('lottery_chances', 0)}次",
                ]
            else:
                content_lines = [
                    f"用户：{info.get('username', user_id)}",
                    f"累计打卡：{info.get('total_days', 0)}天",
                    f"连续打卡：{info.get('consecutive_days', 0)}天",
                    f"剩余抽奖机会：{info.get('lottery_chances', 0)}次",
                ]
            
            if account_info:
                if use_emoji:
                    content_lines.extend([
                        f"💎 账号积分：{account_info['points']}",
                        f"🪙 账号元宝：{account_info['ingots']}",
                    ])
                else:
                    content_lines.extend([
                        f"账号积分：{account_info['points']}",
                        f"账号元宝：{account_info['ingots']}",
                    ])
            else:
                if use_emoji:
                    content_lines.append(f"🎮 游戏账号：未绑定")
                else:
                    content_lines.append(f"游戏账号：未绑定")
        
            message = _format_message(cfg, "打卡信息", content_lines)
            yield event.plain_result(message)
        except Exception as e:
            logger.error(f"查询资产失败: {e}")
            yield event.plain_result("❌ 查询失败，请稍后再试")

    @filter.command("群组配置")
    async def group_config(self, event: AstrMessageEvent):
        """查看或设置群组配置（管理员专用）"""
        try:
            if not self._is_group_admin(event):
                yield event.plain_result("❌ 仅群管理员可执行此操作")
                return
                
            group_id = self._get_group_id(event)
            group_configs = _load_group_config()
            
            cfg = self._curr_cfg()
            use_emoji = cfg.get("use_emoji", True)
            
            if use_emoji:
                lines = [f"⚙️ 群组配置（群ID：{group_id}）", "--------"]
            else:
                lines = [f"群组配置（群ID：{group_id}）", "--------"]
            
            if group_id in group_configs:
                group_cfg = group_configs[group_id]
                if "db_config" in group_cfg:
                    db_cfg = group_cfg["db_config"]
                    lines.append("数据库配置（自定义）：")
                    lines.append(f"- 服务器：{db_cfg.get('db_server', '默认')}")
                    lines.append(f"- 数据库：{db_cfg.get('db_database', '默认')}")
                else:
                    lines.append("数据库配置：使用全局配置")
            else:
                lines.append("数据库配置：使用全局配置")
            
            lines.append("--------")
            lines.append("💡 使用命令修改配置：")
            lines.append("/设置群组数据库 [服务器] [数据库] [用户名] [密码]")
            
            yield event.plain_result("\n".join(lines))
                
        except Exception as e:
            logger.error(f"查询群组配置失败: {e}")
            yield event.plain_result("❌ 查询失败，请稍后再试")

    @filter.command("设置群组数据库")
    async def set_group_database(self, event: AstrMessageEvent, 服务器: str = "", 数据库: str = "", 用户名: str = "", 密码: str = ""):
        """设置群组独立的数据库配置（管理员专用）"""
        try:
            if not self._is_group_admin(event):
                yield event.plain_result("❌ 仅群管理员可执行此操作")
                return
            
            if not 服务器 or not 数据库 or not 用户名 or not 密码:
                yield event.plain_result(
                    "❌ 请提供完整的数据库配置\n"
                    "格式：/设置群组数据库 [服务器] [数据库] [用户名] [密码]\n"
                    "示例：/设置群组数据库 192.168.1.100 MuOnline sa password123"
                )
                return
            
            group_id = self._get_group_id(event)
            group_configs = _load_group_config()
            
            if group_id not in group_configs:
                group_configs[group_id] = {}
            
            group_configs[group_id]["db_config"] = {
                "db_server": 服务器,
                "db_database": 数据库,
                "db_username": 用户名,
                "db_password": 密码,
                "db_port": "1433",
                "db_driver": "FreeTDS"
            }
            
            _save_group_config(group_configs)
            
            yield event.plain_result(f"✅ 群组数据库配置已更新\n服务器：{服务器}\n数据库：{数据库}")
                
        except Exception as e:
            logger.error(f"设置群组数据库失败: {e}")
            yield event.plain_result("❌ 设置失败，请稍后再试")

    @filter.command("重置群组配置")
    async def reset_group_config(self, event: AstrMessageEvent):
        """重置群组配置为全局配置（管理员专用）"""
        try:
            if not self._is_group_admin(event):
                yield event.plain_result("❌ 仅群管理员可执行此操作")
                return
            
            group_id = self._get_group_id(event)
            group_configs = _load_group_config()
            
            if group_id in group_configs:
                del group_configs[group_id]
                _save_group_config(group_configs)
                yield event.plain_result("✅ 群组配置已重置，将使用全局配置")
            else:
                yield event.plain_result("✅ 当前已使用全局配置")
                
        except Exception as e:
            logger.error(f"重置群组配置失败: {e}")
            yield event.plain_result("❌ 重置失败，请稍后再试")

    async def terminate(self):
        pass
