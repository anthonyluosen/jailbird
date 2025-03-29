# Trading Platform Web Application

## 项目概述
这是一个基于Flask的网页应用，用于展示交易策略和管理笔记。主要功能包括：
- 浏览和展示策略文件
- 实时笔记记录
- 动态时间显示
- 文件层级浏览

## 目录结构 
trading_platform/
├── wsgi.py
├── .env
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── config.py
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── forms.py
│   └── ...
└── commands.py
trading_platform/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── models.py
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── forms.py
│   ├── main/
│   │   └── ...
│   ├── notes/
│   │   └── ...
│   └── templates/
│       ├── auth/
│       │   └── login.html
│       └── ...
└── run.py
## 快速开始
### 1. 环境配置
创建虚拟环境（可选）
python -m venv venv
source venv/bin/activate # Linux/Mac
venv\Scripts\activate # Windows
### 2. 配置设置
编辑 `app/config.py` 文件：
class Config:
# 数据库配置
SQLALCHEMY_DATABASE_URI = 'sqlite:///path/to/app.db'
# 文件目录配置
DATA_FOLDER = 'path/to/thisday'
## API 参考

### 1. 笔记API
- `POST /notes/save`
  - 保存新笔记
  - 参数：`{"note": "笔记内容"}`
  - 返回：`{"success": true, "note": {...}}`

- `GET /notes/list`
  - 获取笔记列表
  - 返回：笔记数组

### 2. 文件API
- `GET /folder`
  - 获取目录内容
  - 参数：`path=目录路径`
  - 返回：目录和文件列表
用户名配置
python -m flask db init
python -m flask db migrate -m "users table"
python -m flask db upgrade
## 错误处理
- 404：页面未找到
- 500：服务器内部错误
- 文件访问错误
- 数据库错误

## 注意事项
1. 数据目录权限
   - 确保应用有读写权限
   - 定期备份数据库

2. 安全考虑
   - 限制文件访问路径
   - 验证用户输入

3. 性能优化
   - 大文件处理
   - 并发访问

## 常见问题
1. 数据库连接错误
   - 检查数据库文件路径
   - 确保目录存在且有权限

2. 文件访问错误
   - 检查文件路径配置
   - 确认文件权限

3. 页面显示问题
   - 清除浏览器缓存
   - 检查JavaScript错误

## 维护和更新
1. 定期任务
   - 数据库备份
   - 日志清理
   - 性能监控

2. 版本更新
   - 记录更改历史
   - 测试新功能
   - 平滑升级

## 联系方式
- 作者：[您的名字]
- 邮箱：[您的邮箱]
- 项目地址：[项目仓库地址]

## 许可证
[许可证类型]