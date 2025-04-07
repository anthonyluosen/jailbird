import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

class Config:
    """基础配置类"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data', 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True
    
    # 定义日志目录路径
    LOG_FOLDER = os.environ.get('LOG_FOLDER') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    
    # 定义数据目录路径
    DATA_FOLDER = os.environ.get('DATA_FOLDER') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    
    # 定义账户数据路径
    ACCOUNT_DATA_PATH = os.environ.get('ACCOUNT_DATA_PATH') or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'account_data_path')
    
    # 定义策略回测结果路径
    STRATEGY_RESULTS_PATH = os.environ.get('STRATEGY_RESULTS_PATH') or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'strategy_results')
    
    # 确保必要的目录存在
    @staticmethod
    def init_app(app):
        """初始化应用"""
        # 确保日志目录存在
        os.makedirs(app.config['LOG_FOLDER'], exist_ok=True)
        
        # 确保数据目录存在
        os.makedirs(app.config['DATA_FOLDER'], exist_ok=True)
    