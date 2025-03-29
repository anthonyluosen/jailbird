from flask.cli import FlaskGroup
from app import create_app, db
from app.models import User
import click

cli = FlaskGroup(create_app=create_app)

@cli.command('create-user')
@click.argument('username')
@click.argument('password')
def create_user(username, password):
    """创建新用户"""
    try:
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f'成功创建用户: {username}')
    except Exception as e:
        click.echo(f'创建用户失败: {str(e)}')
        db.session.rollback()

if __name__ == '__main__':
    cli() 