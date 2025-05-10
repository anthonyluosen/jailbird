import os
import sys

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(current_dir)  # 回到上一级目录
sys.path.insert(0, project_dir)
sys.path.append(r"D:\\Project\\anthony\\jailbird-main\\front\\trading_platform")

from trading_platform.app import create_app
from trading_platform.app.models import User

def create_super_admin(username, password):
    app = create_app()
    
    with app.app_context():
        try:
            # 检查用户是否已存在
            user = User.query.filter_by(username=username).first()
            if user:
                print(f"用户 {username} 已存在")
                return
            
            # 创建新的超级管理员用户
            user = User(username=username, is_admin=True, is_super_admin=True)
            user.set_password(password)
            
            # 添加到数据库
            db.session.add(user)
            db.session.commit()
            print(f"超级管理员 {username} 创建成功！")
            
        except Exception as e:
            print(f"创建用户时出错: {str(e)}")
            db.session.rollback()

if __name__ == "__main__":
    # 设置超级管理员的用户名和密码
    admin_username = "admin"
    admin_password = "admin123"  # 建议使用更强的密码
    create_super_admin(admin_username, admin_password) 