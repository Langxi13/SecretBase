"""工具函数"""


def djb2_hash(text: str) -> int:
    """
    DJB2 哈希算法
    
    Args:
        text: 输入字符串
    
    Returns:
        哈希值
    """
    hash_value = 5381
    for char in text:
        hash_value = ((hash_value << 5) + hash_value) + ord(char)
        hash_value = hash_value & 0xFFFFFFFF  # 转换为 32 位整数
    return hash_value


def get_tag_color(tag_name: str) -> str:
    """
    根据标签名生成颜色
    
    Args:
        tag_name: 标签名称
    
    Returns:
        HSL 颜色字符串
    """
    hash_value = djb2_hash(tag_name)
    hue = hash_value % 360
    return f"hsl({hue}, 65%, 55%)"


def format_datetime(iso_string: str) -> str:
    """
    格式化 ISO 时间字符串为友好的显示格式
    
    Args:
        iso_string: ISO 8601 格式的时间字符串
    
    Returns:
        友好的时间字符串
    """
    from datetime import datetime
    
    try:
        dt = datetime.fromisoformat(iso_string)
        now = datetime.now()
        diff = now - dt
        
        # 1 分钟内
        if diff.total_seconds() < 60:
            return "刚刚"
        
        # 1 小时内
        if diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes} 分钟前"
        
        # 24 小时内
        if diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() / 3600)
            return f"{hours} 小时前"
        
        # 7 天内
        if diff.days < 7:
            return f"{diff.days} 天前"
        
        # 超过 7 天
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return iso_string
