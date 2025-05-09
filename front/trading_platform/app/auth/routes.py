import datetime
import json
import os
import random
import re

from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from app.auth import bp
from app.auth.forms import LoginForm
from app.models import User
from app.config import Config

import sys
sys.path.append("../../")

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # 根据用户角色重定向
        if current_user.is_super_admin:
            return redirect(url_for('auth.admin_panel'))
        elif current_user.is_admin:
            return redirect(url_for('main.index'))
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        # 分别处理不同的登录失败情况
        if user is None:
            flash('用户名不存在，请检查您的输入')
            return redirect(url_for('auth.login'))
        elif not user.check_password(form.password.data):
            flash('密码错误，请重新输入')
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=form.remember_me.data)
        
        # 根据用户角色重定向
        if user.is_super_admin:
            next_page = url_for('auth.admin_panel')
        else:
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('main.index')
        
        return redirect(next_page)
    
    return render_template('auth/login.html', title='登录', form=form)

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

# 添加管理员面板路由
@bp.route('/admin')
@login_required
def admin_panel():
    # 检查是否是超级管理员
    if not current_user.is_super_admin:
        flash('您没有访问该页面的权限，仅超级管理员可以管理用户')
        return redirect(url_for('main.index'))
    
    # 获取所有用户
    users = User.query.all()
    return render_template('auth/admin.html', title='管理员面板', users=users)

# 添加用户管理路由
@bp.route('/admin/add_user', methods=['GET', 'POST'])
@login_required
def add_user():
    if not current_user.is_super_admin:
        flash('您没有访问该页面的权限，仅超级管理员可以管理用户')
        return redirect(url_for('main.index'))
    
    from app.auth.forms import UserForm
    form = UserForm()
    
    if form.validate_on_submit():
        user = User(
            username=form.username.data, 
            is_admin=form.is_admin.data,
            is_super_admin=form.is_super_admin.data
        )
        user.set_password(form.password.data)
        from app import db
        db.session.add(user)
        db.session.commit()
        flash('用户已成功添加')
        return redirect(url_for('auth.admin_panel'))
    
    return render_template('auth/user_form.html', title='添加用户', form=form)

@bp.route('/admin/edit_user/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    if not current_user.is_super_admin:
        flash('您没有访问该页面的权限，仅超级管理员可以管理用户')
        return redirect(url_for('main.index'))
    
    user = User.query.get_or_404(id)
    from app.auth.forms import UserForm
    form = UserForm(obj=user)
    
    if form.validate_on_submit():
        user.username = form.username.data
        user.is_admin = form.is_admin.data
        user.is_super_admin = form.is_super_admin.data
        if form.password.data:
            user.set_password(form.password.data)
        from app import db
        db.session.commit()
        flash('用户已成功更新')
        return redirect(url_for('auth.admin_panel'))
    
    return render_template('auth/user_form.html', title='编辑用户', form=form)

@bp.route('/admin/delete_user/<int:id>', methods=['POST'])
@login_required
def delete_user(id):
    if not current_user.is_super_admin:
        flash('您没有访问该页面的权限，仅超级管理员可以管理用户')
        return redirect(url_for('main.index'))
    
    user = User.query.get_or_404(id)
    if user == current_user:
        flash('不能删除当前登录的用户')
        return redirect(url_for('auth.admin_panel'))
    
    from app import db
    db.session.delete(user)
    db.session.commit()
    flash('用户已成功删除')
    return redirect(url_for('auth.admin_panel'))


@bp.route('/sign_up', methods=['POST'])
def sign_up():
    """注册接口"""
    data = request.json
    email = data.get('email')
    password = data.get('password')

    # 验证邮箱格式
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        return jsonify({"error": "错误的邮件格式"}), 400

    if not password:
        return jsonify({"error": "密码是必填项"}), 400

    # 构建存储路径
    account_data_path = Config.ACCOUNT_DATA_PATH
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    file_path = os.path.join(account_data_path, today, "email_val_code.json")

    # 检查邮箱是否已经验证
    if not os.path.exists(file_path):
        return jsonify({"error": "邮箱未被验证"}), 400

    try:
        with open(file_path, 'r') as f:
            data = json.load(f)

        email_data = data.get(email)
        if not email_data or not email_data.get('verified', False):
            return jsonify({"error": "邮箱未被验证"}), 400

    except Exception as e:
        return jsonify({"error": "服务器错误"}), 500

    # print("注册成功" + email)
    try:
        user = User.query.filter_by(username=email).first()
        if user:
            return jsonify({"error": "邮箱已存在"}), 400
            return

        user = User(
            username=email,
            is_admin=False,
            is_super_admin=False
        )
        user.set_password(password)
        from app import db
        db.session.add(user)
        db.session.commit()
        return jsonify({"message": "注册成功"}), 200

    except Exception as e:
        return jsonify({"error": "注册时出错"}), 400


@bp.route('/sign_up/send_email', methods=['POST'])
def send_email():
    """发送邮箱验证码"""
    data = request.json
    uemail = data.get('email')

    # 验证邮箱格式
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, uemail):
        return jsonify({"error": "错误的邮件格式"}), 400

    # 生成验证码
    verification_code = str(random.randint(100000, 999999))

    # 构建存储路径
    account_data_path = Config.ACCOUNT_DATA_PATH
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    directory_path = os.path.join(account_data_path, today)
    file_path = os.path.join(directory_path, "email_val_code.json")

    # 确保目录存在
    os.makedirs(directory_path, exist_ok=True)

    # 保存验证码到 JSON 文件
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
        else:
            data = {}

        # 更新或创建邮箱数据
        expiration_time = (datetime.datetime.now() + datetime.timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
        data[uemail] = {"code": verification_code, "verified": False, "expires_at": expiration_time}
        with open(file_path, 'w') as f:
            json.dump(data, f)

    except Exception as e:
        return jsonify({"error": f"服务器错误"}), 500

    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    smtp_server = "gz-smtp.qcloudmail.com"
    smtp_port = 465
    sender_email = "mail@futural.cn"
    sender_password = "xcnU9DKL6h^hlr_z"
    receiver_email = uemail

    subject = "邮件验证码"  # 邮件主题
    body = f"您的邮箱验证码为：{verification_code}\n10分钟内有效！"  # 邮件正文

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject

    # 添加正文到邮件
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_password)  # 登录到 SMTP 服务器
            server.sendmail(sender_email, receiver_email, message.as_string())  # 发送邮件
            return jsonify({"message": "邮件验证码发送成功"}), 200
    except Exception as e:
        print(e)
        return jsonify({"message": "邮件验证码发送失败，请稍后再试或联系管理员"}), 500


@bp.route('/sign_up/verify_email', methods=['POST'])
def verify_email():
    """验证邮箱验证码"""
    data = request.json
    email = data.get('email')
    code = data.get('code')

    # 验证邮箱格式
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        return jsonify({"error": "错误的邮件格式"}), 400

    # 构建存储路径
    account_data_path = Config.ACCOUNT_DATA_PATH
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    file_path = os.path.join(account_data_path, today, "email_val_code.json")

    # 读取验证码
    if not os.path.exists(file_path):
        return jsonify({"error": "邮件验证码错误或已过期"}), 400

    try:
        with open(file_path, 'r') as f:
            data = json.load(f)

        email_data = data.get(email)
        if not email_data or email_data.get('code') != code:
            return jsonify({"error": "邮件验证码错误或已过期"}), 400

        # 检查验证码是否已过期
        expires_at = email_data.get('expires_at')
        if not expires_at or datetime.datetime.now() > datetime.datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S"):
            return jsonify({"error": "邮件验证码错误或已过期"}), 400

        # 验证成功，设置 verified 为 True
        email_data['verified'] = True
        data[email] = email_data
        with open(file_path, 'w') as f:
            json.dump(data, f)

        return jsonify({"message": "邮件验证成功"}), 200

    except Exception as e:
        return jsonify({"error": f"服务器错误"}), 500


@bp.route('/register', methods=['GET'])
def render_register_page():
    """渲染注册页面"""
    return render_template('auth/register.html')