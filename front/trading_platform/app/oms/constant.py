from enum import Enum
from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import Any, Optional
from copy import deepcopy


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "PENDING"  # 待处理
    FILLED = "FILLED"    # 已成交
    CANCELLED = "CANCELLED"  # 已取消
    REJECTED = "REJECTED"  # 已拒绝
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # 部分成交
    
class OrderType(Enum):
    """订单类型"""
    MARKET = "MARKET"  # 市价单
    LIMIT = "LIMIT"    # 限价单
    
class OrderSide(Enum):
    """交易方向"""
    BUY = "BUY"    # 买入
    SELL = "SELL"  # 卖出
    
class SecurityType(Enum):
    """证券类型"""
    STOCK = "STOCK"  # 股票
    ETF = "ETF"      # ETF基金

# 数据频率类型
class FreqType(Enum):
    """数据频率类型"""
    M1 = "M1"    # 1分钟
    M5 = "M5"    # 5分钟
    M15 = "M15"  # 15分钟
    M30 = "M30"  # 30分钟
    M60 = "M60"  # 60分钟
    EOD = "EOD"  # 日线

# 价格类型
class PriceType(Enum):
    """价格类型"""
    OPEN = "OPEN"    # 开盘价
    HIGH = "HIGH"    # 最高价
    LOW = "LOW"      # 最低价
    CLOSE = "CLOSE"  # 收盘价


class EventType(Enum):
    """事件类型枚举"""
    ORDER = "ORDER"  # 订单事件
    TRADE = "TRADE"  # 成交事件
    POSITION = "POSITION"  # 持仓事件
    ACCOUNT = "ACCOUNT"  # 账户事件
    ERROR = "ERROR"  # 错误事件
    TIMER = "TIMER"  # 计时器事件

class OrderStatus(Enum):
    """订单状态"""
    SUBMITTING = "提交中"
    SUBMITTED = "已提交"
    PARTIAL_FILLED = "部分成交"
    FILLED = "全部成交"
    CANCELLED = "已撤销"
    REJECTED = "拒单"

@dataclass
class Event:
    """事件对象"""
    type: EventType  # 事件类型
    data: Any  # 事件数据
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """初始化后的类型检查"""
        self.data = deepcopy(self.data)

    def clone(self) -> 'Event':
        """创建事件的深拷贝"""
        # return Event(
        #     type=self.type,
        #     data=deepcopy(self.data),
        #     timestamp=self.timestamp
        # )
        """使用fields方法创建对象副本"""
        new_event = Event(type=self.type, data=None, timestamp=self.timestamp)
        
        if isinstance(self.data, Order):
            new_order = Order(
                order_id=None,
                symbol="",
                direction=OrderSide.BUY,
                price=0,
                volume=0,
                status=OrderStatus.SUBMITTING,
                create_time=datetime.now()
            )
            for field in fields(self.data):
                setattr(new_order, field.name, getattr(self.data, field.name))
            new_event.data = new_order
        else:
            new_event.data = deepcopy(self.data)  # 对于非Order对象，仍使用deepcopy
            
        return new_event
    
@dataclass
class Order:
    """订单对象"""
    
    order_id: Optional[str]
    symbol: str
    direction: OrderSide
    price: float # 想要交易的价格
    volume: float
    status: OrderStatus
    create_time: datetime
    filled_volume: float = 0
    trader_platform: str = ""
    is_active: bool = True
    order_type: OrderType = OrderType.MARKET
    is_finished: bool = False
    strategy_name: str = ""
    traded_price: Optional[float] = None
    execution_strategy: Optional[str] = None
    security_type: SecurityType = SecurityType.STOCK
    parent_id: str = None
    limit_price: Optional[float] = None
    # 届时会将算法单写入order

    def __post_init__(self):
        """初始化后的类型检查"""
        self.security_type = get_security_type(self.symbol)
    # def clone(self) -> 'Order':
    #     """创建订单的深拷贝"""
    #     new_order = Order(
    #         order_id=self.order_id,
    #         symbol=self.symbol,
    #         direction=self.direction,
    #         price=self.price,
    #         volume=self.volume,
    #         status=self.status,
    #         create_time=self.create_time
    #     )
        
    #     # 复制其余字段
    #     for field in fields(self):
    #         if field.name not in ['order_id', 'symbol', 'direction', 'price', 'volume', 'status', 'create_time']:
    #             setattr(new_order, field.name, getattr(self, field.name))
                
    #     return new_order
# 动态创建类
class DictToClass:
    def __init__(self, data):
        for key, value in data.items():
            setattr(self, key, value)
def get_security_type(symbol: str) -> SecurityType:
    """根据证券代码判断证券类型
    
    Args:
        symbol: str, 证券代码
        
    Returns:
        SecurityType: 证券类型
    """
    # ETF代码规则：
    # 上交所：510xxx, 511xxx, 512xxx, 513xxx, 518xxx
    # 深交所：159xxx
    etf_prefixes = ('510', '511', '512', '513', '518', '159')
    if symbol.startswith(etf_prefixes):
        return SecurityType.ETF
    return SecurityType.STOCK 