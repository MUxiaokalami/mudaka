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
GROUP_CONFIG_FILE = os.path.join(DATA_DIR, "group_configs.json")  # 群组独立配置


def _load_group_configs(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """加载群组配置"""
    config_file = cfg.get("group_config_file", GROUP_CONFIG_FILE)
    try:
        if os.path.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"加载群组配置失败: {e}")
        return {}


def _save_group_configs(cfg: Dict[str, Any], config: Dict[str, Any]) -> None:
    """保存群组配置"""
    config_file = cfg.get("group_config_file", GROUP_CONFIG_FILE)
    try:
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存群组配置失败: {e}")


def _load_lottery_items(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """加载抽奖物品配置"""
    config_file = cfg.get("lottery_config_file", LOTTERY_ITEMS_FILE)
    try:
        if os.path.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
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
                    "direct_to_account": True,
                    "description": "游戏积分"
                },
                {
                    "id": 2,
                    "name": "元宝",
                    "type": "ingots",
                    "min_amount": 5,
                    "max_amount": 50,
                    "probability": 0.4,
                    "direct_to_account": True,
                    "description": "游戏元宝"
                },
                {
                    "id": 3,
                    "name": "祝福宝石",
                    "type": "item",
                    "item_code": "bless",
                    "min_amount": 1,
                    "max_amount": 3,
                    "probability": 0.08,
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
                    "probability": 0.06,
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
                    "probability": 0.02,
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
            ],
            "version": "1.0.0"
        }
        
        # 保存默认配置
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(default_items, f, ensure_ascii=False, indent=2)
        
        return default_items
    except Exception as e:
        logger.error(f"加载抽奖物品配置失败: {e}")
        return {"items": [], "special_rewards": []}


def _get_group_db_config(group_id: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """获取群组特定的数据库配置"""
    enable_group_config = cfg.get("enable_group_config", True)
    
    if enable_group_config:
        group_configs = _load_group_configs(cfg)
        
        if group_id in group_configs and "db_config" in group_configs[group_id]:
            # 使用群组特定的配置
            group_db_cfg = group_configs[group_id]["db_config"]
            return {
                "server": group_db_cfg.get("db_server", "127.0.0.1"),
                "port": group_db_cfg.get("db_port", "1433"),
                "database": group_db_cfg.get("db_database", "MuOnline"),
                "username": group_db_cfg.get("db_username", "your_username"),
                "password": group_db_cfg.get("db_password", ""),
                "driver": group_db_cfg.get("db_driver", "FreeTDS")
            }
    
    # 使用默认配置（管理员需要在WebUI中配置）
    default_config = cfg.get("default_db_config", {})
    return {
        "server": default_config.get("db_server", "127.0.0.1"),
        "port": default_config.get("db_port", "1433"),
        "database": default_config.get("db_database", "MuOnline"),
        "username": default_config.get("db_username", "your_username"),
        "password": default_config.get("db_password", ""),
        "driver": default_config.get("db_driver", "FreeTDS")
    }


def _get_db_connection(group_id: str, cfg: Dict[str, Any]):
    """获取数据库连接（支持群组独立配置）"""
    try:
        db_config = _get_group_db_config(group_id, cfg)
        
        # 检查密码是否配置
        if not db_config["password"] or db_config["password"] == "your_password_here":
            logger.error(f"群组 {group_id} 数据库密码未配置")
            return None
            
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
        logger.error(f"加载签到数据失败: {e}")
        return {}


def _save_data(data: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存签到数据失败: {e}")


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
        "lottery_chances": 0,
        "lottery_history": [],
        "pending_items": []
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
        if conn:
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
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def _get_user_game_account(bind_data: Dict[str, Any], user_id: str) -> str:
    """根据用户ID获取绑定的游戏账号"""
    return bind_data.get(user_id, "")


def _get_random_signature(cfg: Dict[str, Any]) -> str:
    """获取随机签名"""
    signature_messages = cfg.get("signature_messages", [
        "奇迹世界因你而精彩！",
        "坚持签到，福利不断！",
        "勇者大陆欢迎你的到来！",
        "每日签到，战力飙升！",
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
        "签到信息": "📊 签到信息",
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
    """检查当前时间是否在允许的签到时间内"""
    try:
        now = datetime.datetime.now()
        current_hour = now.hour
        current_minute = now.minute
        current_time_minutes = current_hour * 60 + current_minute
        
        start_time_str = cfg.get("checkin_start_time", "08:00")
        end_time_str = cfg.get("checkin_end_time", "22:00")
        enable_time_limit = cfg.get("enable_time_limit", False)
        
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
            return False, f"当前时间不在签到时间内\n签到时间：{start_display} - {end_display}"
            
    except Exception as e:
        logger.error(f"检查签到时间失败: {e}")
        return True, ""


def _perform_lottery(group_id: str, cfg: Dict[str, Any], user_id: str, game_account: str) -> Tuple[Dict[str, Any], str, int]:
    """执行抽奖
    返回: (抽奖结果, 消息, 额外机会)
    """
    lottery_config = _load_lottery_items(cfg)
    items = lottery_config.get("items", [])
    special_rewards = lottery_config.get("special_rewards", [])
    
    if not items:
        return {}, "❌ 抽奖配置错误，请联系管理员", 0
    
    # 计算总概率
    total_prob = sum(item["probability"] for item in items)
    total_special_prob = sum(reward["probability"] for reward in special_rewards)
    total_all_prob = total_prob + total_special_prob
    
    if total_all_prob <= 0:
        return {}, "❌ 抽奖配置错误，概率总和为0", 0
    
    # 抽奖
    roll = random.random() * total_all_prob
    
    result = {}
    message = ""
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
        return {}, "❌ 抽奖失败，请稍后重试", 0
    
    # 处理结果
    result_type = result.get("type")
    
    if result_type == "points":
        amount = random.randint(result["min_amount"], result["max_amount"])
        if _update_game_account_assets(group_id, cfg, game_account, points_change=amount):
            result["actual_amount"] = amount
            message = f"🎉 恭喜！获得 {amount} 积分"
        else:
            return {}, "❌ 发放积分失败，请联系管理员", 0
    
    elif result_type == "ingots":
        amount = random.randint(result["min_amount"], result["max_amount"])
        if _update_game_account_assets(group_id, cfg, game_account, ingots_change=amount):
            result["actual_amount"] = amount
            message = f"🎉 恭喜！获得 {amount} 元宝"
        else:
            return {}, "❌ 发放元宝失败，请联系管理员", 0
    
    elif result_type == "item":
        amount = random.randint(result["min_amount"], result["max_amount"])
        result["actual_amount"] = amount
        message = f"🎁 恭喜！获得 {result['name']} × {amount}"
    
    elif result_type == "multiplier":
        multiplier = result.get("multiplier", 2.0)
        message = f"✨ 获得特殊奖励：{result['name']}"
        result["multiplier"] = multiplier
    
    elif result_type == "extra_chance":
        extra_chances = result.get("extra_chances", 1)
        message = f"🎊 获得特殊奖励：{result['name']}"
        result["extra_chances"] = extra_chances
    
    # 记录抽奖时间
    result["timestamp"] = datetime.datetime.now().isoformat()
    result["user_id"] = user_id
    
    return result, message, extra_chances


def _update_consecutive_days(info: Dict[str, Any], today: datetime.date) -> None:
    """更新连续签到天数"""
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


@register("astrbot_plugin_draw_checkin", "小卡拉米", "抽奖签到插件", "2.0.0")
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
        group_id = event.get_group_id()
        if not group_id:
            # 尝试从会话ID获取
            session_id = event.get_session_id()
            if session_id and session_id.isdigit():
                return session_id
            return "default"
        return str(group_id)

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

    def _test_database_connection(self, group_id: str, cfg: Dict[str, Any]) -> bool:
        """测试数据库连接"""
        try:
            conn = _get_db_connection(group_id, cfg)
            if conn:
                conn.close()
                return True
            return False
        except Exception as e:
            logger.error(f"数据库连接测试失败: {e}")
            return False

    @filter.command("签到", alias={"打卡"})
    async def checkin(self, event: AstrMessageEvent):
        """每日签到"""
        try:
            user_id = event.get_sender_id()
            group_id = self._get_group_id(event)
            
            # 检查时间
            cfg = self._curr_cfg()
            is_allowed, time_error_msg = _is_checkin_time_allowed(cfg)
            if not is_allowed:
                yield event.plain_result(f"❌ 签到失败：{time_error_msg}")
                return
            
            # 检查绑定
            game_account = _get_user_game_account(self.bind_data, user_id)
            if not game_account:
                yield event.plain_result(
                    "❌ 签到失败：您尚未绑定游戏账号！\n"
                    "请先使用命令：/绑定游戏账号 [你的游戏账号]\n"
                    "例如：/绑定游戏账号 mygame123"
                )
                return

            bucket, info = self._get_user_bucket(event)
            today = _today()

            if info.get("last_checkin") == today.isoformat():
                yield event.plain_result("今日已签到，请勿重复~")
                return

            # 检查游戏账号
            account_info = _get_game_account_info(group_id, cfg, game_account)
            if not account_info:
                yield event.plain_result("❌ 签到失败：游戏账号不存在，请检查账号是否正确或联系管理员")
                return

            # 更新连续签到天数
            _update_consecutive_days(info, today)

            # 发放抽奖机会
            base_chances = int(cfg.get("base_lottery_chances", 1))
            consecutive_days = info.get("consecutive_days", 0)
            consecutive_bonus = 0
            
            # 每连续签到7天额外获得1次机会，最多3次
            if consecutive_days >= 7:
                consecutive_bonus = min((consecutive_days // 7), 3)
            
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
                    "✅ 签到成功",
                    separator,
                    f"📅 累计签到：{info['total_days']}天",
                    f"🔥 连续签到：{consecutive_days}天",
                    f"🎯 获得抽奖机会：{total_chances}次",
                    f"💰 剩余抽奖机会：{info['lottery_chances']}次"
                ]
            else:
                lines = [
                    "✅ 签到成功",
                    separator,
                    f"累计签到：{info['total_days']}天",
                    f"连续签到：{consecutive_days}天",
                    f"获得抽奖机会：{total_chances}次",
                    f"剩余抽奖机会：{info['lottery_chances']}次"
                ]
                
            if consecutive_bonus > 0:
                if use_emoji:
                    lines.append(f"🎊 连续签到奖励：额外{consecutive_bonus}次抽奖机会")
                else:
                    lines.append(f"连续签到奖励：额外{consecutive_bonus}次抽奖机会")
            
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
            logger.error(f"签到失败: {e}")
            yield event.plain_result("❌ 签到出现异常，请稍后再试")

    @filter.command("抽奖")
    async def lottery(self, event: AstrMessageEvent, 次数: str = "1"):
        """抽奖命令"""
        try:
            user_id = event.get_sender_id()
            group_id = self._get_group_id(event)
            
            # 解析抽奖次数
            try:
                times = int(次数)
                if times <= 0:
                    yield event.plain_result("❌ 抽奖次数必须大于0")
                    return
                if times > 10:
                    yield event.plain_result("❌ 单次最多抽奖10次")
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
            multiplier_active = False
            multiplier_value = 1.0
            
            for i in range(times):
                result, message, extra_chances = _perform_lottery(group_id, cfg, user_id, game_account)
                if not result and not message:
                    yield event.plain_result("❌ 抽奖失败，请稍后重试")
                    return
                
                # 处理特殊效果
                result_type = result.get("type", "")
                
                if result_type == "multiplier":
                    multiplier_active = True
                    multiplier_value = result.get("multiplier", 2.0)
                    # 记录特殊奖励但不计入消耗
                    if message:
                        results.append((result, message))
                    continue
                elif result_type == "extra_chance":
                    extra_chances_total += result.get("extra_chances", 1)
                    # 记录特殊奖励但不计入消耗
                    if message:
                        results.append((result, message))
                    continue
                
                # 应用倍数效果
                if multiplier_active:
                    if result_type == "points":
                        original_amount = result.get("actual_amount", 0)
                        multiplied_amount = int(original_amount * multiplier_value)
                        if _update_game_account_assets(group_id, cfg, game_account, 
                                                      points_change=(multiplied_amount - original_amount)):
                            result["actual_amount"] = multiplied_amount
                            message = f"🎉 恭喜！获得 {multiplied_amount} 积分（{multiplier_value}倍奖励）"
                    elif result_type == "ingots":
                        original_amount = result.get("actual_amount", 0)
                        multiplied_amount = int(original_amount * multiplier_value)
                        if _update_game_account_assets(group_id, cfg, game_account,
                                                      ingots_change=(multiplied_amount - original_amount)):
                            result["actual_amount"] = multiplied_amount
                            message = f"🎉 恭喜！获得 {multiplied_amount} 元宝（{multiplier_value}倍奖励）"
                    multiplier_active = False
                
                results.append((result, message))
            
            # 计算实际消耗的机会（不包括特殊奖励）
            actual_used = len([r for r, _ in results if r.get("type") not in ["multiplier", "extra_chance"]])
            
            # 扣除抽奖机会
            info["lottery_chances"] = available_chances - actual_used
            
            # 添加额外机会
            if extra_chances_total > 0:
                info["lottery_chances"] += extra_chances_total
            
            # 记录抽奖历史
            lottery_history = info.get("lottery_history", [])
            for result, _ in results:
                if result.get("type") in ["points", "ingots", "item"]:
                    lottery_history.append({
                        "item": result.get("name"),
                        "type": result.get("type"),
                        "amount": result.get("actual_amount", 1),
                        "timestamp": result.get("timestamp")
                    })
            # 只保留最近50条记录
            info["lottery_history"] = lottery_history[-50:]
            
            # 处理道具物品
            item_results = [r for r, _ in results if r.get("type") == "item"]
            if item_results:
                pending_items = info.get("pending_items", [])
                for result in item_results:
                    pending_items.append({
                        "item": result.get("name"),
                        "amount": result.get("actual_amount", 1),
                        "timestamp": result.get("timestamp"),
                        "item_code": result.get("item_code", ""),
                        "description": result.get("description", "")
                    })
                info["pending_items"] = pending_items
            
            # 保存数据
            _save_data(self.data)
            
            # 生成消息
            if use_emoji:
                lines = ["🎰 抽奖结果", separator]
            else:
                lines = ["抽奖结果", separator]
            
            if len(results) == 0:
                lines.append("⚠️ 本次抽奖未获得任何奖励")
            else:
                for idx, (result, message) in enumerate(results, 1):
                    if len(results) > 1:
                        lines.append(f"第{idx}次：{message}")
                    else:
                        lines.append(message)
            
            if extra_chances_total > 0:
                lines.append(f"🎊 获得额外抽奖机会：{extra_chances_total}次")
            
            lines.append(separator)
            lines.append(f"消耗抽奖机会：{actual_used}次")
            lines.append(f"剩余抽奖机会：{info['lottery_chances']}次")
            
            # 如果有物品需要兑换
            if item_results:
                lines.append(separator)
                lines.append("📝 需要兑换的物品：")
                for result in item_results:
                    item_name = result.get("name")
                    amount = result.get("actual_amount", 1)
                    lines.append(f"- {item_name} × {amount}")
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
                        f"游戏账号：{account}",
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
                        content_lines.append(f"❌ 绑定状态：游戏账号不存在或数据库连接失败")
                    else:
                        content_lines.append(f"绑定状态：游戏账号不存在或数据库连接失败")
                    
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
                    f"📅 累计签到：{total_days}天",
                    f"🔥 连续签到：{consecutive_days}天",
                ]
            else:
                lines = [
                    f"用户：{info.get('username', user_id)}",
                    f"剩余抽奖机会：{chances}次",
                    f"累计签到：{total_days}天",
                    f"连续签到：{consecutive_days}天",
                ]
            
            # 显示连续签到奖励信息
            if consecutive_days >= 7:
                bonus = min(consecutive_days // 7, 3)
                if use_emoji:
                    lines.append(f"🎊 连续签到奖励：额外{bonus}次抽奖机会")
                else:
                    lines.append(f"连续签到奖励：额外{bonus}次抽奖机会")
            
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

    @filter.command("我的道具")
    async def my_items(self, event: AstrMessageEvent):
        """查看待兑换的道具"""
        try:
            _, info = self._get_user_bucket(event)
            user_id = event.get_sender_id()
            cfg = self._curr_cfg()
            use_emoji = cfg.get("use_emoji", True)
            
            pending_items = info.get("pending_items", [])
            
            if not pending_items:
                yield event.plain_result("📭 暂无待兑换道具")
                return
            
            if use_emoji:
                lines = [f"📦 {info.get('username', user_id)}的待兑换道具", "--------"]
            else:
                lines = [f"{info.get('username', user_id)}的待兑换道具", "--------"]
            
            # 按道具类型分组统计
            item_counts = {}
            for item in pending_items:
                item_name = item.get("item", "未知道具")
                amount = item.get("amount", 1)
                if item_name in item_counts:
                    item_counts[item_name] += amount
                else:
                    item_counts[item_name] = amount
            
            for item_name, total_amount in item_counts.items():
                lines.append(f"{item_name} × {total_amount}")
            
            lines.append("--------")
            lines.append("💡 请私聊GM兑换以上道具")
            
            yield event.plain_result("\n".join(lines))
            
        except Exception as e:
            logger.error(f"查询我的道具失败: {e}")
            yield event.plain_result("❌ 查询失败，请稍后再试")

    @filter.command("签到查询", alias={"查询签到", "我的签到"})
    async def query_assets(self, event: AstrMessageEvent):
        """查询签到信息"""
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
                    f"📅 累计签到：{info.get('total_days', 0)}天",
                    f"🔥 连续签到：{info.get('consecutive_days', 0)}天",
                    f"🎯 剩余抽奖机会：{info.get('lottery_chances', 0)}次",
                ]
            else:
                content_lines = [
                    f"用户：{info.get('username', user_id)}",
                    f"累计签到：{info.get('total_days', 0)}天",
                    f"连续签到：{info.get('consecutive_days', 0)}天",
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
                    content_lines.append(f"🎮 游戏账号：未绑定或数据库未配置")
                else:
                    content_lines.append(f"游戏账号：未绑定或数据库未配置")
        
            message = _format_message(cfg, "签到信息", content_lines)
            yield event.plain_result(message)
        except Exception as e:
            logger.error(f"查询资产失败: {e}")
            yield event.plain_result("❌ 查询失败，请稍后再试")

    @filter.command("群数据库状态")
    async def group_db_status(self, event: AstrMessageEvent):
        """查看群组数据库配置状态"""
        try:
            group_id = self._get_group_id(event)
            cfg = self._curr_cfg()
            
            # 加载群组配置
            group_configs = _load_group_configs(cfg)
            
            use_emoji = cfg.get("use_emoji", True)
            
            if use_emoji:
                lines = [f"📊 群组数据库状态（群ID：{group_id}）", "--------"]
            else:
                lines = [f"群组数据库状态（群ID：{group_id}）", "--------"]
            
            if group_id in group_configs and "db_config" in group_configs[group_id]:
                db_cfg = group_configs[group_id]["db_config"]
                lines.append("✅ 已配置独立数据库")
                lines.append(f"服务器：{db_cfg.get('db_server')}")
                lines.append(f"端口：{db_cfg.get('db_port')}")
                lines.append(f"数据库：{db_cfg.get('db_database')}")
                lines.append(f"用户名：{db_cfg.get('db_username')}")
                
                last_updated = db_cfg.get("last_updated", "")
                if last_updated:
                    try:
                        dt = datetime.datetime.fromisoformat(last_updated)
                        lines.append(f"最后更新：{dt.strftime('%Y-%m-%d %H:%M')}")
                    except:
                        pass
                
                # 测试连接
                lines.append("--------")
                if self._test_database_connection(group_id, cfg):
                    lines.append("✅ 数据库连接：正常")
                else:
                    lines.append("❌ 数据库连接：失败")
            else:
                lines.append("ℹ️ 使用默认数据库配置")
                lines.append("💡 请管理员使用 /设置群数据库 命令配置独立数据库")
            
            lines.append("--------")
            lines.append("📝 配置命令：/设置群数据库 [服务器] [端口] [数据库名] [用户名] [密码]")
            
            yield event.plain_result("\n".join(lines))
                
        except Exception as e:
            logger.error(f"查询群数据库状态失败: {e}")
            yield event.plain_result("❌ 查询失败，请稍后再试")

    @filter.command("设置群数据库")
    async def set_group_database(self, event: AstrMessageEvent):
        """设置群组数据库配置（管理员专用）"""
        try:
            if not self._is_group_admin(event):
                yield event.plain_result("❌ 仅群管理员可执行此操作")
                return
            
            group_id = self._get_group_id(event)
            cfg = self._curr_cfg()
            
            # 获取当前消息文本
            raw_text = event.get_plain_text()
            parts = raw_text.split()
            
            if len(parts) < 6:
                yield event.plain_result(
                    "❌ 请提供完整的数据库配置信息\n"
                    "格式：/设置群数据库 [服务器] [端口] [数据库名] [用户名] [密码]\n"
                    "示例：/设置群数据库 192.168.1.100 1433 MuOnline sa mypassword\n"
                    "💡 注意：密码不能包含空格"
                )
                return
            
            # 解析参数
            server = parts[1]
            port = parts[2]
            database = parts[3]
            username = parts[4]
            password = parts[5]
            
            # 验证端口
            if not port.isdigit():
                yield event.plain_result("❌ 端口必须是数字")
                return
            
            # 加载现有配置
            group_configs = _load_group_configs(cfg)
            
            if group_id not in group_configs:
                group_configs[group_id] = {}
            
            # 保存数据库配置
            group_configs[group_id]["db_config"] = {
                "db_server": server,
                "db_port": port,
                "db_database": database,
                "db_username": username,
                "db_password": password,
                "db_driver": "FreeTDS",
                "last_updated": datetime.datetime.now().isoformat()
            }
            
            _save_group_configs(cfg, group_configs)
            
            # 测试连接
            test_result = self._test_database_connection(group_id, cfg)
            
            if test_result:
                yield event.plain_result(
                    f"✅ 群组数据库配置已保存并测试成功！\n"
                    f"服务器：{server}:{port}\n"
                    f"数据库：{database}\n"
                    f"用户名：{username}\n"
                    "💡 配置已生效，现在可以正常使用签到功能"
                )
            else:
                yield event.plain_result(
                    f"⚠️ 群组数据库配置已保存，但连接测试失败！\n"
                    f"服务器：{server}:{port}\n"
                    f"数据库：{database}\n"
                    f"用户名：{username}\n"
                    "❌ 请检查配置信息，签到功能可能无法正常工作"
                )
                
        except Exception as e:
            logger.error(f"设置群数据库失败: {e}")
            yield event.plain_result("❌ 设置失败，请稍后再试")

    @filter.command("删除群数据库配置")
    async def remove_group_db_config(self, event: AstrMessageEvent):
        """删除群组数据库配置，恢复使用默认配置（管理员专用）"""
        try:
            if not self._is_group_admin(event):
                yield event.plain_result("❌ 仅群管理员可执行此操作")
                return
            
            group_id = self._get_group_id(event)
            cfg = self._curr_cfg()
            
            group_configs = _load_group_configs(cfg)
            
            if group_id in group_configs and "db_config" in group_configs[group_id]:
                del group_configs[group_id]["db_config"]
                
                # 如果配置为空，删除整个群组条目
                if not group_configs[group_id]:
                    del group_configs[group_id]
                
                _save_group_configs(cfg, group_configs)
                yield event.plain_result("✅ 群组数据库配置已删除，将使用默认配置")
            else:
                yield event.plain_result("✅ 当前已使用默认配置，无需删除")
                
        except Exception as e:
            logger.error(f"删除群数据库配置失败: {e}")
            yield event.plain_result("❌ 删除失败，请稍后再试")

    @filter.command("签到重置")
    async def reset_self(self, event: AstrMessageEvent):
        """重置自己的签到数据"""
        try:
            user_id = event.get_sender_id()
            bucket, info = self._get_user_bucket(event)
            
            # 重置用户数据
            username = info.get("username", user_id)
            bucket[user_id] = _default_user(user_id, username)
            _save_data(self.data)
            
            yield event.plain_result(f"✅ 已重置您的签到数据")
                
        except Exception as e:
            logger.error(f"重置签到数据失败: {e}")
            yield event.plain_result("❌ 重置失败，请稍后再试")

    @filter.command("管理员重置")
    async def admin_reset(self, event: AstrMessageEvent):
        """管理员重置指定用户数据"""
        try:
            if not self._is_group_admin(event):
                yield event.plain_result("❌ 仅群管理员可执行此操作")
                return
            
            # 尝试获取目标用户ID
            target_uid = None
            
            # 检查@消息
            try:
                for comp in event.get_messages():
                    if isinstance(comp, Comp.At) and comp.qq:
                        target_uid = str(comp.qq)
                        break
            except:
                pass
            
            # 如果没有@，尝试从文本中提取
            if not target_uid:
                raw_text = event.get_plain_text()
                parts = raw_text.split()
                if len(parts) > 1:
                    # 尝试提取数字作为QQ号
                    for part in parts[1:]:
                        if part.isdigit() and len(part) >= 5:
                            target_uid = part
                            break
            
            if not target_uid:
                yield event.plain_result(
                    "❌ 请指定要重置的用户\n"
                    "格式：/管理员重置 @用户\n"
                    "或：/管理员重置 [QQ号]"
                )
                return
            
            bucket = self._get_group_ctx_bucket(event)
            
            if target_uid in bucket:
                username = bucket[target_uid].get("username", target_uid)
                bucket[target_uid] = _default_user(target_uid, username)
                _save_data(self.data)
                yield event.plain_result(f"✅ 已重置用户 {username} 的签到数据")
            else:
                yield event.plain_result("❌ 未找到该用户的签到数据")
                
        except Exception as e:
            logger.error(f"管理员重置失败: {e}")
            yield event.plain_result("❌ 重置失败，请稍后再试")

    def _get_group_ctx_bucket(self, event: AstrMessageEvent) -> Dict[str, Any]:
        """获取当前群维度的bucket"""
        try:
            platform = event.get_platform_name()
            gid = self._get_group_id(event)
            ctx_id = f"{platform}:G:{gid}"
            return self.data.setdefault(ctx_id, {})
        except Exception:
            return self.data.setdefault("default", {})

    async def terminate(self):
        """插件终止时执行"""
        pass
