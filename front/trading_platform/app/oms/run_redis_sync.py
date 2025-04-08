import sys
import os

# 获取当前脚本所在目录的父目录
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../"))

# 将项目根目录添加到Python路径
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入并运行Redis同步
from trading_platform.app.oms.redis_sync import RedisSyncManager
from trading_platform.app.oms.storage import DataStorage

if __name__ == "__main__":
    # 初始化存储
    storage = DataStorage()
    
    # 初始化Redis同步管理器
    redis_sync = RedisSyncManager(
        storage=storage,
        redis_host="localhost",  # 替换为实际的Redis服务器地址
        redis_port=6379,
        redis_password="your_password",  # 替换为实际的Redis密码
        redis_db=0
    )
    
    try:
        # 启动同步
        redis_sync.start_sync(is_cloud=False)
        
        # 等待一段时间观察同步效果
        import time
        time.sleep(30)
        
    finally:
        # 停止同步
        redis_sync.stop_sync() 