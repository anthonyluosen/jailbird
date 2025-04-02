from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, ValidationError
from app.models import User

class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired()])
    password = PasswordField('密码', validators=[DataRequired()])
    remember_me = BooleanField('记住我')
    submit = SubmitField('登录')

# 添加用户管理表单
class UserForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(min=2, max=64)])
    password = PasswordField('密码', validators=[Length(min=0, max=128)])
    is_admin = BooleanField('管理员权限')
    is_super_admin = BooleanField('超级管理员权限')
    submit = SubmitField('保存')
    
    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        # 存储原始用户对象，用于验证重名
        self.original_username = kwargs.get('obj', None)
    
    def validate_username(self, username):
        # 检查用户名是否已存在
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            # 如果是编辑现有用户且用户名没变，跳过验证
            if self.original_username and self.original_username.username == username.data:
                return
            raise ValidationError('该用户名已被使用，请选择其他用户名') 