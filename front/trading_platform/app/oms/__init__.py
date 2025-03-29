from flask import Blueprint

bp = Blueprint('oms', __name__)

from app.oms import routes 