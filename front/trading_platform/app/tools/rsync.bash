# 创建rsync同步脚本
#!/bin/bash

# 配置
LOCAL_DATA_PATH="/path/to/local/data"
REMOTE_SERVER="user@server.example.com"
REMOTE_DATA_PATH="/path/to/remote/data"
INTERVAL=60  # 秒

# 循环同步
while true; do
    # 使用rsync同步数据
    rsync -avz --delete $LOCAL_DATA_PATH/ $REMOTE_SERVER:$REMOTE_DATA_PATH/
    
    # 打印同步时间
    echo "数据同步完成: $(date)"
    
    # 等待下一次同步
    sleep $INTERVAL
done