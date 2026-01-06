# app.py - 主入口文件
from flask import Flask, jsonify, g
from flask_cors import CORS
from datetime import timedelta
import os
import sqlite3
import time
import subprocess
import requests
from pathlib import Path
from flask import Flask, jsonify, g, send_from_directory  # 记得加这个
from config import NAS_SHARED_SECRET

# ========== 路径配置 ==========
NGROK_PATH = Path(__file__).with_name('ngrok.exe')
ngrok_url_global = None
FLASK_PORT = 8080

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')
AVATAR_DIR = os.path.join(FRONTEND_DIR, 'avatars')
os.makedirs(AVATAR_DIR, exist_ok=True)

# ========== Flask 应用初始化 ==========
app = Flask(__name__,
            static_folder=FRONTEND_DIR,
            static_url_path='')

CORS(app,
     supports_credentials=True,
     origins=['http://127.0.0.1:8080', 'http://localhost:8080',
              'http://127.0.0.1:5000', 'http://localhost:5000'],
     allow_headers=['Content-Type', 'Authorization'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])

app.secret_key = 'your-secret-key-change-this-in-production'

# Session 配置
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_PATH'] = '/'
app.config['SESSION_COOKIE_DOMAIN'] = None
app.config['SESSION_COOKIE_NAME'] = 'nas_session'

# 自定义配置
app.config['BASE_DIR'] = BASE_DIR
app.config['FRONTEND_DIR'] = FRONTEND_DIR
app.config['AVATAR_DIR'] = AVATAR_DIR

# ========== 数据库连接管理 ==========
from common import get_db


@app.teardown_appcontext
def close_connection(exception):
    """请求结束时关闭数据库连接"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


# ========== 注册蓝图 ==========
from auth_routes import auth_bp
from user_routes import user_bp
from node_routes import node_bp
from file_routes import file_bp
from encryption_routes import encryption_bp
from ec_routes import ec_bp, init_ec_tables
from proxy_routes import proxy_bp
from admin_routes import admin_bp
from cross_pool_routes import cross_pool_bp, init_cross_pool_tables

app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)
app.register_blueprint(node_bp)
app.register_blueprint(file_bp)
app.register_blueprint(encryption_bp)
app.register_blueprint(ec_bp)
app.register_blueprint(proxy_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(cross_pool_bp)


# ========== 错误处理 ==========
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "资源不存在"}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "服务器内部错误"}), 500


# ========== 数据库初始化 ==========
def init_db():
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()


    # 用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            file_permission TEXT DEFAULT 'readonly',
            email TEXT,
            node_access TEXT DEFAULT '{"type":"all","allowed_groups":[],"allowed_nodes":[],"denied_nodes":[]}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            status TEXT DEFAULT 'active'
        )
    ''')

    # 节点分组表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS node_groups (
            group_id TEXT PRIMARY KEY,
            group_name TEXT NOT NULL,
            description TEXT,
            node_ids TEXT NOT NULL,
            color TEXT DEFAULT '#3b82f6',
            icon TEXT DEFAULT '📁',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 节点策略表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS node_policies (
            node_id TEXT PRIMARY KEY,
            policy TEXT NOT NULL DEFAULT 'all_users'
        )
    ''')

    # 节点访问请求表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_requests (
            request_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            node_id TEXT NOT NULL,
            node_name TEXT NOT NULL,
            permission TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_at TIMESTAMP,
            rejected_at TIMESTAMP,
            reject_reason TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # 磁盘表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS disks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT,
            mount TEXT,
            status TEXT,
            capacity_gb REAL,
            is_encrypted INTEGER DEFAULT 0,
            is_locked INTEGER DEFAULT 0
        )
    ''')

    # 节点表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nodes (
            node_id TEXT PRIMARY KEY,
            ip TEXT NOT NULL,
            port INTEGER NOT NULL,
            status TEXT DEFAULT 'offline',
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 默认管理员
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, password_hash, role, email)
        VALUES ('admin', '123', 'admin', 'admin@nas.local')
    ''')

    # 节点分组成员表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS node_group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            FOREIGN KEY (group_id) REFERENCES node_groups(group_id),
            UNIQUE(group_id, node_id)
        )
    ''')

    # 白名单表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS whitelist_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # 节点磁盘表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS node_disks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL,
            mount TEXT NOT NULL,
            capacity_gb REAL,
            status TEXT DEFAULT 'online',
            is_encrypted INTEGER DEFAULT 0,
            is_locked INTEGER DEFAULT 0,
            UNIQUE(node_id, mount)
        )
    ''')

    # 检查 avatar 列
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'avatar' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT ""')

    conn.commit()
    conn.close()



# ========== ngrok 相关 ==========
def _cleanup_old_ngrok():
    """清理已遗留的 ngrok 进程"""
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/IM', 'ngrok.exe'],
                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(['killall', 'ngrok'],
                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def start_ngrok(silent=False):
    global ngrok_url_global

    if not NGROK_PATH.exists():
        if not silent:
            print(f"❌ 未找到 {NGROK_PATH.name}，请把它放在与 app.py 同目录：{NGROK_PATH}")
        return None, None

    _cleanup_old_ngrok()

    proc = subprocess.Popen(
        [str(NGROK_PATH), 'http', str(FLASK_PORT)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding='utf-8', errors='replace'
    )

    url = None
    for i in range(15):
        time.sleep(1)
        if proc.poll() is not None:
            break
        try:
            r = requests.get('http://127.0.0.1:4040/api/tunnels', timeout=2)
            r.raise_for_status()
            data = r.json()
            for t in data.get('tunnels', []):
                if t.get('proto') == 'https' and t.get('public_url'):
                    url = t['public_url']
                    break
            if url:
                break
        except:
            continue

    ngrok_url_global = url
    return url, proc

@app.route('/api/ngrok-url', methods=['GET'])
def get_ngrok_url():
    return jsonify({"url": ngrok_url_global})

# 🛠️ 强制服务图片文件的路由
@app.route('/images/<path:filename>')
def serve_custom_images(filename):
    image_folder = os.path.join(app.config['FRONTEND_DIR'], 'images')
    print(f"DEBUG: 尝试加载图片 -> {os.path.join(image_folder, filename)}") # 打印调试日志
    return send_from_directory(image_folder, filename)


# ========== 启动入口 ==========
if __name__ == '__main__':
    from common import load_nodes_config

    init_db()
    with app.app_context():
        init_ec_tables()
        init_cross_pool_tables()
    NODES_CONFIG = load_nodes_config()

    # 只在重载后的子进程打印一次
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        url, _ng = start_ngrok(silent=True)  # 静默启动
        print("\n" + "=" * 40)
        print(f"🏠 内网: http://127.0.0.1:{FLASK_PORT}")
        if url:
            print(f"🌍 公网: {url}")
        print("=" * 40 + "\n")

    app.run(host='0.0.0.0', port=FLASK_PORT, debug=True, use_reloader=True)