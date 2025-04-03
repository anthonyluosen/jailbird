import os
import sys

# 添加项目根目录到 Python 路径
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_dir)

from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(
        port=8000,
        debug=True,
        use_reloader=False  # 禁用重载器
    ) 