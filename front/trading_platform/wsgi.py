import sys
sys.path.append(r"F:\workspace\code")
from app import create_app
# from app.oms.routes import socketio

app = create_app()

if __name__ == '__main__':
    # app.run() 
    app.run(
        host='0.0.0.0', 
        port=8000, 
        debug=True,
        use_reloader=False  # 禁用重载器
    ) 
    # socketio.run(app, debug=True,host='0.0.0.0', port=8000) 