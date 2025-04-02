from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from app.auth import bp
from app.auth.forms import LoginForm
from app.models import User

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