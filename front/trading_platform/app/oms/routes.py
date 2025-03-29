from flask import render_template, jsonify, current_app
from app.oms import bp
from flask_login import login_required
from flask_socketio import emit
from datetime import datetime
from app.oms.storage import DataStorage
import traceback
# 全局的交易系统实例
trading_system = None
main_engine = None

# 创建数据库连接
storage = DataStorage("trading_data.db")

# def init_oms():
#     """初始化OMS"""
#     global trading_system, main_engine
#     if trading_system is None:
#         trading_system, main_engine = init_trading_system()

@bp.route('/orders')
@login_required
def orders_page():
    """订单管理页面"""
    # init_oms()
    return render_template('oms/orders.html')

@bp.route('/api/orders')
@login_required
def get_orders():
    """获取所有活动订单"""
    try:
        orders = []
        active_orders = storage.get_active_orders()
        # print(f"从数据库获取到 {len(active_orders)} 个活动订单")
        
        for order in active_orders:
            order_data = {
                'order_id': order.order_id,
                'parent_id': getattr(order, 'parent_id', None),
                'symbol': order.symbol,
                'direction': order.direction.value,
                'price': order.price,
                'volume': order.volume,
                'status': order.status.value,
                'filled_volume': order.filled_volume,
                'create_time': order.create_time.isoformat(),
                'trader_platform': order.trader_platform,
                'is_active': order.is_active,
                'strategy_name': order.strategy_name,
                'execution_strategy': getattr(order, 'execution_strategy', None),
                'traded_price': getattr(order, 'traded_price', None)
            }
            orders.append(order_data)
            
            # 添加调试信息，打印每个订单的关键字段
            # print(f"订单ID: {order_data['order_id']}, 成交价: {order_data['traded_price']}")
        print(orders)
        return jsonify(orders)
    except Exception as e:
        print(f"获取订单失败: {e}{traceback.format_exc()}")
        return jsonify([])

# @bp.route('/api/place_order', methods=['POST'])
# @login_required
# def place_order():
#     """下单接口"""
#     if trading_system:
#         data = request.json
#         try:
#             trading_system.place_order(
#                 symbol=data['symbol'],
#                 direction=data['direction'],
#                 price=float(data['price']),
#                 volume=float(data['volume'])
#             )
#             return jsonify({'status': 'success'})
#         except Exception as e:
#             return jsonify({'status': 'error', 'message': str(e)})
#     return jsonify({'status': 'error', 'message': 'Trading system not initialized'})

# def handle_order_update(event: Event):
#     """处理订单更新事件"""
#     order = event.data
#     socketio.emit('order_update', {
#         'order_id': order.order_id,
#         'symbol': order.symbol,
#         'direction': order.direction,
#         'price': order.price,
#         'volume': order.volume,
#         'status': order.status.value,
#         'filled_volume': order.filled_volume,
#         'create_time': order.create_time.isoformat(),
#         'trader_platform': order.trader_platform,
#         'is_active': order.is_active
#     }, namespace='/ws/orders')

# # 在初始化时注册事件处理函数
# def register_handlers():
#     if main_engine:
#         main_engine.event_engine.register(EventType.ORDER, handle_order_update) 