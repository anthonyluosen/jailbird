from flask import Flask, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from app.config import Config
import os
from dotenv import load_dotenv

# # 加载环境变量
# load_dotenv()
# 加载环境变量
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
print(dotenv_path)
load_dotenv(dotenv_path)
# 创建扩展实例
db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'
login.login_message = '请先登录后再访问此页面'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 确保数据目录存在
    os.makedirs(os.path.dirname(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')), exist_ok=True)
    
    # 确保 thisday 目录存在
    os.makedirs(app.config['DATA_FOLDER'], exist_ok=True)

    # 初始化扩展
    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)

    # 注册蓝图
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.notes import bp as notes_bp
    app.register_blueprint(notes_bp, url_prefix='/notes')

    from app.oms import bp as oms_bp
    app.register_blueprint(oms_bp, url_prefix='/oms')

    # # 初始化OMS
    # with app.app_context():
    #     from app.oms.routes import init_oms, register_handlers
    #     init_oms()
    #     register_handlers()

    # 导入模型
    from app import models

    # 创建数据库表
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print(f"数据库初始化失败: {e}")

    # 初始化配置
    config_class.init_app(app)

    # 添加全局路由保护
    @app.before_request
    def require_login():
        # 允许访问静态文件和登录/注册相关路由，以及外部订单API
        allowed_routes = ['auth.login', 'auth.logout', 'auth.register', 'static']
        allowed_endpoints = ['oms.receive_external_orders']  # 允许外部订单API无需登录
        
        if not current_user.is_authenticated and \
           request.endpoint and \
           request.endpoint not in allowed_routes and \
           request.endpoint not in allowed_endpoints and \
           not request.endpoint.startswith('auth.'):
            return redirect(url_for('auth.login'))

    return app 