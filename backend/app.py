from flask import Flask, jsonify, request, send_file, session, redirect
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import requests
import sqlite3, json, time
from config import NAS_SHARED_SECRET


# ✅ 获取项目根目录(nascenter 文件夹)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')

app = Flask(__name__,
            static_folder=FRONTEND_DIR,  # ✅ 指向 frontend 文件夹
            static_url_path='')  # ✅ 静态文件路径为根路径
CORS(app, supports_credentials=True)  # ← 修改这里,支持凭证
app.secret_key = 'your-secret-key-change-this-in-production'  # ← 添加密钥


# ✅✅✅ 添加这 4 行 ✅✅✅
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # 开发环境用 False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # 7天有效期
# ✅✅✅ 添加结束 ✅✅✅

# nascenter/backend/app.py

import jwt
from datetime import datetime, timedelta

# 在文件开头添加
ACCESS_TOKEN_SECRET = 'your-access-token-secret-key'  # 应该和客户端共享

from functools import wraps

def admin_required(f):
    """要求管理员权限的装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. 检查是否登录
        if 'user_id' not in session:
            return jsonify({"error": "未登录,请先登录"}), 401
        # 2. 检查是否为 'admin'
        if session.get('role') != 'admin':
            return jsonify({"error": "权限不足", "message": "此操作需要管理员权限"}), 403
        # 3. 权限足够,执行函数
        return f(*args, **kwargs)
    return decorated_function
def login_required(f):
    """要求登录的装饰器"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "未登录,请先登录"}), 401
        return f(*args, **kwargs)

    return decorated_function
@app.route('/api/generate-node-access-token', methods=['POST'])
@login_required
def generate_node_access_token():
    """
    生成临时访问令牌
    用户点击"访问节点"时调用
    """
    data = request.json
    node_id = data.get('node_id')

    if not node_id:
        return jsonify({'error': '缺少节点ID'}), 400

    # 生成 JWT Token (有效期 1 小时)
    token = jwt.encode({
        'user_id': session['user_id'],
        'username': session['username'],
        'role': session.get('role', 'user'),
        'file_permission': session.get('file_permission', 'readonly'),
        'node_id': node_id,
        'exp': datetime.utcnow() + timedelta(hours=1)  # 1小时后过期
    }, ACCESS_TOKEN_SECRET, algorithm='HS256')

    return jsonify({
        'success': True,
        'token': token
    })
# 节点配置列表
NODES_CONFIG = [
    {
        "id": "node-1",
        "name": "NAS-主节点",
        "ip": "192.168.1.100",
        "port": 8000,
        "type": "remote"
    },
    {
        "id": "node-2",
        "name": "NAS-备份节点",
        "ip": "192.168.1.101",
        "port": 8000,
        "type": "remote"
    },
    {
        "id": "node-5",
        "name": "我的本地节点",
        "ip": "127.0.0.1",
        "port": 5000,
        "type": "local"
    }
]




def fetch_node_data(node_config, timeout=3):
    """从真实节点获取数据 - [增强版]"""
    try:
        base_url = f"http://{node_config['ip']}:{node_config['port']}"

        # 1. 获取节点基本信息 (这部分不变)
        info_response = requests.get(f"{base_url}/api/node-info", timeout=timeout)
        if info_response.status_code != 200:
            raise Exception("节点信息获取失败")

        # 2. 获取系统统计信息 (这部分不变)
        stats_response = requests.get(f"{base_url}/api/system-stats", timeout=timeout)
        if stats_response.status_code != 200:
            raise Exception("系统统计获取失败")

        info_data = info_response.json()
        stats_data = stats_response.json()

        # 3. 合并数据 (✅ 核心修改在这里)
        return {
            "id": node_config["id"],
            "name": info_data.get("name", node_config["name"]),
            "ip": node_config["ip"],
            "port": node_config["port"],
            "status": "online",
            "cpu_usage": stats_data.get("cpu_percent", 0),
            "memory_usage": stats_data.get("memory_percent", 0),
            "disk_usage": stats_data.get("disk_percent", 0),
            "total_storage": int(stats_data.get("disk_total_gb", 0)),
            "used_storage": int(stats_data.get("disk_used_gb", 0)),
            # 👇 [核心修改] 从节点的统计信息中读取 cpu_temp_celsius 字段
            #    并将其赋值给前端需要的 cpu_temp 字段
            "cpu_temp": stats_data.get("cpu_temp_celsius", 0),
            "last_updated": datetime.now().isoformat()
        }

    except requests.exceptions.Timeout:
        print(f"[WARNING] 节点 {node_config['name']} 连接超时")
        return create_offline_node(node_config, "timeout")

    except requests.exceptions.ConnectionError:
        print(f"[WARNING] 无法连接到节点 {node_config['name']}")
        return create_offline_node(node_config, "connection_error")

    except Exception as e:
        print(f"[ERROR] 获取节点 {node_config['name']} 数据失败: {e}")
        return create_offline_node(node_config, "error")

# (您文件里的 create_offline_node 函数也需要确保有 cpu_temp 字段)
def create_offline_node(node_config, reason="unknown"):
    """创建离线节点数据"""
    return {
        "id": node_config["id"],
        "name": node_config["name"],
        "ip": node_config["ip"],
        "port": node_config["port"],
        "status": "offline",
        "cpu_usage": 0,
        "memory_usage": 0,
        "disk_usage": 0,
        "total_storage": 0,
        "used_storage": 0,
        # 👇 确保离线时也有默认的温度字段
        "cpu_temp": 0,
        "last_updated": datetime.now().isoformat(),
        "offline_reason": reason
    }

# ... (您主控中心 app.py 的其他代码)

def init_db():
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()

    # 👇 新增：创建用户表
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

    # 👇 新增：创建节点分组表
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

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS node_policies (
            node_id TEXT PRIMARY KEY,
            policy TEXT NOT NULL DEFAULT 'all_users'
        )
    ''')

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

    # 👇 新增：插入默认管理员
    cursor.execute('''
            INSERT OR IGNORE INTO users (username, password_hash, role, email)
            VALUES ('admin', '123', 'admin', 'admin@nas.local')
        ''')

    # 👇 新增：插入默认分组
    groups_data = [
        ('group_core', '核心服务器组', '生产环境', '["node-1","node-2"]', '#ef4444', '🔥'),
        # ⬇️ 修正后，删掉多余的 '["node-5"]' ⬇️
        ('group_local', '本地节点组', '测试开发', '["node-5"]', '#8b5cf6', '🏠')
    ]

    for group_data in groups_data:
        cursor.execute('''
               INSERT OR IGNORE INTO node_groups 
               (group_id, group_name, description, node_ids, color, icon)
               VALUES (?, ?, ?, ?, ?, ?)
           ''', group_data)

    conn.commit()
    conn.close()





@app.route('/api/users/<int:user_id>/accessible-nodes', methods=['GET'])
@login_required
def get_user_accessible_nodes(user_id):
    """获取用户可访问的节点列表"""
    # 权限检查
    if session['user_id'] != user_id and session['role'] != 'admin':
        return jsonify({'error': '无权查看'}), 403

    conn = sqlite3.connect('nas_center.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 获取用户信息
    cursor.execute('SELECT node_access, role FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({'error': '用户不存在'}), 404

    # 管理员可以访问所有节点
    if user['role'] == 'admin':
        conn.close()
        return jsonify({
            'type': 'all',
            'nodes': [node['id'] for node in NODES_CONFIG]
        })

    # 解析 node_access
    node_access = json.loads(user['node_access'])
    access_type = node_access.get('type', 'all')

    accessible_nodes = []

    if access_type == 'all':
        # 所有节点
        accessible_nodes = [node['id'] for node in NODES_CONFIG]

    elif access_type == 'groups':
        # 按分组访问
        allowed_groups = node_access.get('allowed_groups', [])

        if allowed_groups:
            placeholders = ','.join('?' * len(allowed_groups))
            cursor.execute(f'''
                SELECT DISTINCT node_id
                FROM node_group_members
                WHERE group_id IN ({placeholders})
            ''', allowed_groups)

            accessible_nodes = [row['node_id'] for row in cursor.fetchall()]

    elif access_type == 'custom':
        # 自定义节点
        accessible_nodes = node_access.get('allowed_nodes', [])

    # 排除明确拒绝的节点
    denied_nodes = node_access.get('denied_nodes', [])
    accessible_nodes = [nid for nid in accessible_nodes if nid not in denied_nodes]

    conn.close()

    return jsonify({
        'type': access_type,
        'nodes': accessible_nodes
    })
@app.route('/')
def index():
    """根路由 - 检查登录状态"""
    # 如果未登录,返回登录页面
    if 'user_id' not in session:
        login_path = os.path.join(FRONTEND_DIR, 'login.html')
        if os.path.exists(login_path):
            return send_file(login_path)
        else:
            return jsonify({"error": "登录页面未找到"}), 404

    # 如果已登录,返回主界面
    html_path = os.path.join(FRONTEND_DIR, '1.html')
    if os.path.exists(html_path):
        return send_file(html_path)
    else:
        return jsonify({"error": "主页面未找到"}), 404



# ========== 登录相关 API ==========

@app.route('/api/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"success": False, "message": "用户名和密码不能为空"}), 400

    # 查询数据库
    conn = sqlite3.connect('nas_center.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ? AND status = "active"', (username,))
    user = cursor.fetchone()
    conn.close()

    # 验证密码
    if user and user['password_hash'] == password:
        # ✅ 添加这一行!
        session.permanent = True
        # 登录成功,保存到 session
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        # ✅ 正确
        session['file_permission'] = user['file_permission'] if user['file_permission'] else 'readonly'

        # 更新最后登录时间
        conn = sqlite3.connect('nas_center.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET last_login = ? WHERE id = ?',
                       (datetime.now().isoformat(), user['id']))
        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "message": "登录成功",
            "user": {
                "id": user['id'],
                "username": user['username'],
                "role": user['role'],
                "email": user['email']
            }
        })
    else:
        return jsonify({"success": False, "message": "用户名或密码错误"}), 401


@app.route('/api/logout', methods=['POST'])
def logout():
    """用户登出"""
    session.clear()
    return jsonify({"success": True, "message": "已退出登录"})


@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    """检查登录状态"""
    if 'user_id' in session:
        return jsonify({
            "authenticated": True,
            "user": {
                "id": session['user_id'],
                "username": session['username'],
                "role": session['role']
            }
        })
    else:
        return jsonify({"authenticated": False}), 401

@app.route('/api/internal/authenticate-user', methods=['POST'])
def internal_authenticate_user():
    """
    [新增] 内部认证 API
    此接口仅供 NAS 节点客户端调用。
    节点客户端将用户提交的用户名和密码发送到这里进行验证。
    """
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"success": False, "message": "用户名和密码不能为空"}), 400

    # 1. 查询主控中心的数据库
    conn = sqlite3.connect('nas_center.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ? AND status = "active"', (username,))
    user = cursor.fetchone()
    conn.close()

    # 2. 验证密码 (这里仍然是明文 '123'，生产环境应使用哈希)
    if user and user['password_hash'] == password:
        # 3. 验证成功，返回用户的详细信息和权限
        return jsonify({
            "success": True,
            "user": {
                "id": user['id'],
                "username": user['username'],
                "role": user['role'],
                "email": user['email'],
                # [核心] 返回该用户的文件权限
                "file_permission": user['file_permission'],
                # [核心] 返回该用户的节点访问策略 (虽然在此架构中可能用处不大，但可以一并返回)
                "node_access": json.loads(user['node_access'])
            }
        })
    else:
        # 4. 验证失败
        return jsonify({"success": False, "message": "用户名或密码错误"}), 401

# 登录检查装饰器


# ... (在 login_required 函数之后) ...


from functools import wraps

# 定义权限级别 (数字越大,权限越高)
PERM_READONLY = 1
PERM_READWRITE = 2
PERM_FULLCONTROL = 3

PERMISSION_MAP = {
    'readonly': PERM_READONLY,
    'readwrite': PERM_READWRITE,
    'fullcontrol': PERM_FULLCONTROL
}

def permission_required(required_level_name):
    """
    权限检查装饰器 (守卫)。
    检查当前登录用户的 file_permission 是否满足要求。
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. 确保已登录 (在管理端)
            if 'user_id' not in session:
                return jsonify({"error": "未登录"}), 401

            conn = None
            try:
                # 2. 从管理端的数据库获取当前用户的权限
                conn = sqlite3.connect('nas_center.db')
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT role, file_permission FROM users WHERE id = ?', (session['user_id'],))
                user = cursor.fetchone()

                if not user:
                    return jsonify({"error": "用户不存在"}), 401

                # 3. 管理员 'admin' 自动放行
                if user['role'] == 'admin':
                    return f(*args, **kwargs) # 执行 API

                # 4. 比较权限等级
                user_level = PERMISSION_MAP.get(user['file_permission'], 0) # 0 = 无权限
                required_level = PERMISSION_MAP.get(required_level_name, 99)

                if user_level >= required_level:
                    # 权限足够, 执行 API
                    return f(*args, **kwargs)
                else:
                    # 权限不足
                    return jsonify({"error": "权限不足", "message": f"此操作需要 {required_level_name} 权限"}), 403

            except Exception as e:
                return jsonify({"error": "权限检查失败", "message": str(e)}), 500
            finally:
                if conn:
                    conn.close()

        return decorated_function
    return decorator
@app.route('/api/nodes', methods=['GET'])
def get_all_nodes():
    """获取所有 NAS 节点的真实数据"""
    nodes_data = []

    for node_config in NODES_CONFIG:
        print(f"[INFO] 正在获取节点数据: {node_config['name']}")
        node_data = fetch_node_data(node_config)
        nodes_data.append(node_data)

    return jsonify(nodes_data)


# ========== 用户管理 API ==========
@app.route('/api/users', methods=['GET'])
def get_users():
    conn = sqlite3.connect('nas_center.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, role, email, node_access, status FROM users')
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()

    # 解析 node_access JSON
    for user in users:
        user['node_access'] = json.loads(user['node_access'])

    return jsonify(users)


@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.json
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()

    # 这里简化处理，实际应该用 bcrypt
    cursor.execute('''
        INSERT INTO users (username, password_hash, role, email)
        VALUES (?, ?, ?, ?)
    ''', (data['username'], data['password'], data['role'], data.get('email', '')))

    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return jsonify({"success": True, "user_id": new_id})


@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.json
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE users SET role = ?, email = ?, status = ?
        WHERE id = ?
    ''', (data['role'], data.get('email', ''), data.get('status', 'active'), user_id))
    data.get('file_permission', 'readonly'),
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET status = "deleted" WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ========== 节点分组 API ==========
@app.route('/api/node-groups', methods=['GET'])
@login_required
def get_node_groups():
    conn = sqlite3.connect('nas_center.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM node_groups')
    groups = [dict(row) for row in cursor.fetchall()]
    conn.close()

    # 解析 node_ids JSON
    for group in groups:
        group['node_ids'] = json.loads(group['node_ids'])

    return jsonify(groups)



@app.route('/api/users/<int:user_id>/node-access', methods=['GET'])
def get_user_node_access(user_id):
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()
    cursor.execute('SELECT node_access FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return jsonify(json.loads(row[0]))
    else:
        return jsonify({"error": "用户不存在"}), 404

@app.route('/api/audit-logs', methods=['GET'])
def get_audit_logs():
    # 简化版:返回空数组
    return jsonify([])

@app.route('/api/node-groups', methods=['POST'])
@login_required
@admin_required
def create_node_group():
    data = request.json
    group_id = f"group_{int(time.time())}"

    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO node_groups (group_id, group_name, description, node_ids, color, icon)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (group_id, data['group_name'], data.get('description', ''),
          json.dumps(data['node_ids']), data.get('color', '#3b82f6'), data.get('icon', '📁')))

    conn.commit()
    conn.close()
    return jsonify({"success": True, "group_id": group_id})


# 替换内存存储的版本

def save_access_request(request_data):
    """保存访问申请到数据库"""
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO access_requests 
        (request_id, user_id, username, node_id, node_name, permission, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        request_data['request_id'],
        request_data['user_id'],
        request_data['username'],
        request_data['node_id'],
        request_data['node_name'],
        request_data['permission'],
        'pending'
    ))
    conn.commit()
    conn.close()


def update_request_status(request_id, status, **kwargs):
    """更新申请状态"""
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()

    if status == 'approved':
        cursor.execute('''
            UPDATE access_requests 
            SET status = ?, approved_at = ?
            WHERE request_id = ?
        ''', ('approved', datetime.now().isoformat(), request_id))
    elif status == 'rejected':
        cursor.execute('''
            UPDATE access_requests 
            SET status = ?, rejected_at = ?, reject_reason = ?
            WHERE request_id = ?
        ''', ('rejected', datetime.now().isoformat(),
              kwargs.get('reason', ''), request_id))

    conn.commit()
    conn.close()


# 修改后的 API
@app.route('/api/node-groups/<group_id>', methods=['PUT'])
@login_required
@admin_required
def update_node_group(group_id):
    data = request.json
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE node_groups 
        SET group_name=?, description=?, node_ids=?, color=?, icon=?
        WHERE group_id=?
    ''', (data['group_name'], data.get('description', ''), json.dumps(data['node_ids']),
          data.get('color', '#3b82f6'), data.get('icon', '📁'), group_id))

    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route('/api/node-groups/<group_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_node_group(group_id):
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM node_groups WHERE group_id = ?', (group_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ========== 用户节点访问权限 API ==========
@app.route('/api/users/<int:user_id>/node-access', methods=['PUT'])
def update_user_node_access(user_id):
    data = request.json
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()

    cursor.execute('UPDATE users SET node_access = ? WHERE id = ?',
                   (json.dumps(data), user_id))

    conn.commit()
    conn.close()
    return jsonify({"success": True})

# 文件: 主控中心 app.py

@app.route('/api/nodes/<node_id>/monitor-stats', methods=['GET'])
def get_node_monitor_stats(node_id):
    """获取单个节点的完整系统监控数据"""
    node_config = next((config for config in NODES_CONFIG if config['id'] == node_id), None)
    if not node_config:
        return jsonify({"error": "节点不存在"}), 404

    try:
        base_url = f"http://{node_config['ip']}:{node_config['port']}"
        response = requests.get(f"{base_url}/api/system", timeout=5)

        # 检查节点是否返回了成功的状态码
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            # 如果节点返回了错误（比如500），我们解析它的错误信息并返回给前端
            error_details = response.json().get('error', '未知节点错误')
            return jsonify({
                "error": f"从节点获取监控数据失败: {error_details} (状态码: {response.status_code})"
            }), 500

    except requests.exceptions.RequestException as e:
        # 捕获所有 requests 相关的异常 (如连接超时, 无法解析主机等)
        print(f"[ERROR] 请求节点 {node_config['name']} 失败: {e}")
        return jsonify({
            "error": f"请求节点失败，请确保节点客户端正在运行且网络通畅。错误: {str(e)}"
        }), 500
    except Exception as e:
        # 捕获其他所有可能的未知错误
        print(f"[ERROR] 处理节点 {node_config['name']} 数据时发生未知错误: {e}")
        return jsonify({
            "error": f"处理节点数据时发生未知错误: {str(e)}"
        }), 500
@app.route('/api/nodes/<node_id>', methods=['GET'])
def get_node(node_id):
    """获取指定 NAS 节点的真实数据"""
    node_config = None
    for config in NODES_CONFIG:
        if config['id'] == node_id:
            node_config = config
            break

    if not node_config:
        return jsonify({"error": "节点不存在"}), 404

    node_data = fetch_node_data(node_config)
    return jsonify(node_data)


@app.route('/api/nodes/<node_id>/refresh', methods=['POST'])
def refresh_node(node_id):
    """刷新节点数据(获取最新数据)"""
    node_config = None
    for config in NODES_CONFIG:
        if config['id'] == node_id:
            node_config = config
            break

    if not node_config:
        return jsonify({"error": "节点不存在"}), 404

    node_data = fetch_node_data(node_config, timeout=5)
    return jsonify(node_data)


# ========== 访问申请管理 API ==========

# 存储访问申请（实际应用中应该用数据库）
access_requests = {}


# 文件: nascenter/backend/app.py

@app.route('/api/access-requests', methods=['POST'])
@login_required
def create_access_request():
    """
    [修改版] 用户申请访问某个节点 - 自动批准模式
    """
    data = request.json
    node_id = data.get('node_id')
    permission = data.get('permission', 'readonly')

    if not node_id:
        return jsonify({"success": False, "message": "缺少节点ID"}), 400

    # 查找节点配置
    node_config = get_node_config_by_id(node_id)
    if not node_config:
        return jsonify({"success": False, "message": "节点不存在"}), 404

    # 生成申请 ID
    import uuid
    request_id = str(uuid.uuid4())

    # 获取当前用户信息
    username = session.get('username')
    user_id = session.get('user_id')

    # ✅ 直接在管理端数据库中更新用户权限
    try:
        conn = sqlite3.connect('nas_center.db')
        cursor = conn.cursor()

        # 更新用户的 file_permission
        cursor.execute(
            'UPDATE users SET file_permission = ? WHERE id = ?',
            (permission, user_id)
        )

        conn.commit()
        conn.close()

        print(f"[自动批准] 用户 {username} 已自动获得节点 {node_config['name']} 的 {permission} 权限")

        return jsonify({
            "success": True,
            "message": f"访问权限已自动开通！您现在可以使用 {permission} 权限访问节点",
            "permission": permission,
            "auto_approved": True
        })

    except Exception as e:
        print(f"[错误] 自动批准失败: {e}")
        return jsonify({
            "success": False,
            "message": f"自动批准失败: {str(e)}"
        }), 500


# nascenter/backend/app.py (管理端)

# ========== [新增] 客户端权限查询接口 ==========

@app.route('/api/internal/get-user-permission', methods=['POST'])
def get_user_permission():
    """
    供客户端查询用户权限
    客户端每次处理请求时都会调用此接口验证用户
    """
    # 验证请求来源
    secret = request.headers.get('X-NAS-Secret')
    if secret != NAS_SHARED_SECRET:
        print(f"[WARN] 未授权的权限查询请求")
        return jsonify({"success": False, "message": "未授权的请求"}), 403

    data = request.json
    username = data.get('username')

    if not username:
        return jsonify({"success": False, "message": "缺少用户名"}), 400

    # 从数据库查询用户权限
    try:
        conn = sqlite3.connect('nas_center.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            'SELECT role, file_permission FROM users WHERE username = ? AND status = "active"',
            (username,)
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            print(f"[AUTH] 查询用户 {username} 权限: {user['file_permission']}")
            return jsonify({
                "success": True,
                "role": user['role'],
                "file_permission": user['file_permission']
            })
        else:
            print(f"[WARN] 用户 {username} 不存在或已禁用")
            return jsonify({"success": False, "message": "用户不存在"}), 404
    except Exception as e:
        print(f"[ERROR] 查询用户权限失败: {e}")
        return jsonify({"success": False, "message": "数据库错误"}), 500


# ========== [新增] 代理到客户端的请求 ==========

@app.route('/api/nodes/<node_id>/proxy/<path:api_path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def proxy_to_node(node_id, api_path):
    """
    代理所有到客户端的请求
    自动添加用户信息到请求头
    """
    # 获取节点配置
    node_config = get_node_config_by_id(node_id)
    if not node_config:
        return jsonify({"error": "节点不存在"}), 404

    # 构建目标 URL
    target_url = f"http://{node_config['ip']}:{node_config['port']}/api/{api_path}"

    # 🔥 添加用户信息到请求头
    headers = {
        'X-NAS-Username': session['username'],
        'X-NAS-Secret': NAS_SHARED_SECRET,
        'Content-Type': 'application/json'
    }

    print(f"[PROXY] {request.method} {target_url} (user: {session['username']})")

    try:
        # 转发请求
        if request.method == 'GET':
            response = requests.get(
                target_url,
                params=request.args,
                headers=headers,
                timeout=30
            )
        elif request.method == 'POST':
            response = requests.post(
                target_url,
                json=request.get_json() if request.is_json else None,
                data=request.get_data() if not request.is_json else None,
                headers=headers,
                timeout=30
            )
        elif request.method == 'PUT':
            response = requests.put(
                target_url,
                json=request.get_json(),
                headers=headers,
                timeout=30
            )
        elif request.method == 'DELETE':
            response = requests.delete(
                target_url,
                json=request.get_json() if request.is_json else None,
                headers=headers,
                timeout=30
            )

        # 返回响应
        return response.content, response.status_code, dict(response.headers)

    except requests.exceptions.Timeout:
        return jsonify({"error": f"节点 {node_config['name']} 响应超时"}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({"error": f"无法连接到节点 {node_config['name']}"}), 503
    except Exception as e:
        print(f"[ERROR] 代理请求失败: {e}")
        return jsonify({"error": f"请求节点失败: {str(e)}"}), 500
@app.route('/api/access-requests', methods=['GET'])
@login_required
def get_access_requests():
    """
    [新增] 获取当前用户的访问申请列表
    """
    user_id = session['user_id']

    # 过滤出当前用户的申请
    user_requests = [
        req for req in access_requests.values()
        if req['user_id'] == user_id
    ]

    return jsonify({
        "success": True,
        "requests": user_requests
    })


@app.route('/api/internal/access-approved', methods=['POST'])
def access_approved():
    """
    [新增] 接收来自节点的批准通知
    当节点管理员批准访问申请时，节点会调用这个 API
    """
    # 验证请求来源
    secret = request.headers.get('X-NAS-Secret')
    if secret != "your-shared-secret-key":
        return jsonify({"success": False, "message": "未授权的请求"}), 403

    data = request.json
    request_id = data.get('request_id')
    username = data.get('username')
    node_id = data.get('node_id')

    if request_id not in access_requests:
        return jsonify({"success": False, "message": "申请不存在"}), 404

    # 更新申请状态
    access_requests[request_id]['status'] = 'approved'
    access_requests[request_id]['approved_at'] = datetime.now().isoformat()

    print(f"[访问申请] 用户 {username} 对节点 {node_id} 的访问申请已被批准")

    # TODO: 这里可以发送通知给用户

    return jsonify({
        "success": True,
        "message": "已接收批准通知"
    })


@app.route('/api/internal/access-rejected', methods=['POST'])
def access_rejected():
    """
    [新增] 接收来自节点的拒绝通知
    当节点管理员拒绝访问申请时，节点会调用这个 API
    """
    # 验证请求来源
    secret = request.headers.get('X-NAS-Secret')
    if secret != "your-shared-secret-key":
        return jsonify({"success": False, "message": "未授权的请求"}), 403

    data = request.json
    request_id = data.get('request_id')
    username = data.get('username')
    node_id = data.get('node_id')
    reason = data.get('reason', '管理员拒绝')

    if request_id not in access_requests:
        return jsonify({"success": False, "message": "申请不存在"}), 404

    # 更新申请状态
    access_requests[request_id]['status'] = 'rejected'
    access_requests[request_id]['rejected_at'] = datetime.now().isoformat()
    access_requests[request_id]['reject_reason'] = reason

    print(f"[访问申请] 用户 {username} 对节点 {node_id} 的访问申请已被拒绝: {reason}")

    # TODO: 这里可以发送通知给用户

    return jsonify({
        "success": True,
        "message": "已接收拒绝通知"
    })
@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取整体统计信息(基于真实节点数据)"""
    all_nodes = []

    for node_config in NODES_CONFIG:
        node_data = fetch_node_data(node_config)
        all_nodes.append(node_data)

    total_nodes = len(all_nodes)
    online_nodes = sum(1 for node in all_nodes if node['status'] == 'online')
    offline_nodes = sum(1 for node in all_nodes if node['status'] == 'offline')
    warning_nodes = sum(1 for node in all_nodes if node['status'] == 'warning')

    total_storage = sum(node['total_storage'] for node in all_nodes)
    used_storage = sum(node['used_storage'] for node in all_nodes)

    online_node_list = [node for node in all_nodes if node['status'] == 'online']
    avg_cpu = sum(node['cpu_usage'] for node in online_node_list) / max(len(online_node_list), 1)
    avg_memory = sum(node['memory_usage'] for node in online_node_list) / max(len(online_node_list), 1)

    return jsonify({
        "total_nodes": total_nodes,
        "online_nodes": online_nodes,
        "offline_nodes": offline_nodes,
        "warning_nodes": warning_nodes,
        "total_storage_gb": total_storage,
        "used_storage_gb": used_storage,
        "storage_usage_percent": round((used_storage / total_storage * 100) if total_storage > 0 else 0, 2),
        "avg_cpu_usage": round(avg_cpu, 2),
        "avg_memory_usage": round(avg_memory, 2)
    })


@app.route('/api/nodes/<node_id>/disks', methods=['GET'])
def get_node_disks(node_id):
    """获取节点的真实磁盘信息"""
    node_config = None
    for config in NODES_CONFIG:
        if config['id'] == node_id:
            node_config = config
            break

    if not node_config:
        return jsonify({"error": "节点不存在"}), 404

    try:
        base_url = f"http://{node_config['ip']}:{node_config['port']}"
        response = requests.get(f"{base_url}/api/disks", timeout=5)

        if response.status_code == 200:
            disks_data = response.json()
            return jsonify({
                "success": True,
                "node_name": node_config['name'],
                "disks": disks_data
            })
        else:
            return jsonify({"error": "获取磁盘信息失败"}), 500

    except Exception as e:
        return jsonify({"error": f"请求失败: {str(e)}"}), 500


@app.route('/api/users/<int:user_id>/password', methods=['PUT'])
@login_required
def change_password(user_id):
    """修改密码"""
    data = request.json
    new_password = data.get('password')

    # 检查权限：只能修改自己的密码，除非是管理员
    if session['user_id'] != user_id and session['role'] != 'admin':
        return jsonify({"error": "无权修改其他用户密码"}), 403

    if not new_password:
        return jsonify({"error": "密码不能为空"}), 400

    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                   (new_password, user_id))  # 实际应用中应该加密
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "密码修改成功"})

@app.route('/api/node-policies', methods=['GET'])
@login_required
def get_node_policies():
    conn = sqlite3.connect('nas_center.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM node_policies')
    policies = {row['node_id']: row['policy'] for row in cursor.fetchall()}
    conn.close()
    return jsonify(policies)

@app.route('/api/node-policies/<node_id>', methods=['PUT'])
@login_required
def update_node_policy(node_id):
    data = request.json
    policy = data.get('policy', 'all_users')
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO node_policies (node_id, policy)
        VALUES (?, ?)
    ''', (node_id, policy))
    conn.commit()
    conn.close()
    return jsonify({"success": True})
@app.errorhandler(404)
def not_found(error):
    """404 错误处理"""
    return jsonify({"error": "资源不存在"}), 404


@app.errorhandler(500)
def internal_error(error):
    """500 错误处理"""
    return jsonify({"error": "服务器内部错误"}), 500


# ... (在 internal_error 函数之后) ...

# 辅助函数: 获取节点IP和端口 (使用您已有的 NODES_CONFIG)
def get_node_config_by_id(node_id):
    for config in NODES_CONFIG:
        if config['id'] == node_id:
            return config
    return None


# ========== 文件系统 API (权限网关) ==========

@app.route('/api/files/<node_id>/list', methods=['GET'])
@login_required  # 守卫1: 必须登录管理端
@permission_required('readonly')  # 守卫2: 必须有 '只读' 权限
def list_files(node_id):
    path = request.args.get('path', '/')
    node_config = get_node_config_by_id(node_id)
    if not node_config:
        return jsonify({"error": "节点不存在"}), 404

    try:
        # 转发请求到客户端 (nas-9debf778.../backend/filemanager.py)
        url = f"http://{node_config['ip']}:{node_config['port']}/api/files/list?path={path}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": f"从节点 {node_config['name']} 获取文件列表失败", "message": str(e)}), 500


@app.route('/api/files/<node_id>/delete', methods=['POST'])
@login_required
@permission_required('fullcontrol')  # 守卫2: 必须有 '完全控制' 权限
def delete_file(node_id):
    path = request.json.get('path')
    node_config = get_node_config_by_id(node_id)
    if not node_config:
        return jsonify({"error": "节点不存在"}), 404

    try:
        # 转发请求到客户端 (nas-9debf778.../backend/filemanager.py)
        url = f"http://{node_config['ip']}:{node_config['port']}/api/files/delete"
        response = requests.post(url, json={"path": path}, timeout=10)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": f"在节点 {node_config['name']} 上删除文件失败", "message": str(e)}), 500


@app.route('/api/files/<node_id>/mkdir', methods=['POST'])
@login_required
@permission_required('readwrite')  # 守卫2: 必须有 '读写' 权限
def mkdir(node_id):
    path = request.json.get('path')
    node_config = get_node_config_by_id(node_id)
    if not node_config:
        return jsonify({"error": "节点不存在"}), 404

    try:
        # 转发请求到客户端 (nas-9debf778.../backend/filemanager.py)
        url = f"http://{node_config['ip']}:{node_config['port']}/api/files/mkdir"
        response = requests.post(url, json={"path": path}, timeout=5)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": f"在节点 {node_config['name']} 上创建文件夹失败", "message": str(e)}), 500

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 NAS Center 启动中...")
    print("=" * 50)
    print(f"📁 前端文件夹: {FRONTEND_DIR}")
    print(f"📄 HTML 文件: {os.path.join(FRONTEND_DIR, '1.html')}")
    print("=" * 50)
    print("🌐 前端页面: http://127.0.0.1:8080")
    print("📡 API 地址: http://127.0.0.1:8080/api")
    print("=" * 50)
    print("📋 配置的节点:")
    for node in NODES_CONFIG:
        print(f"  - {node['name']}: {node['ip']}:{node['port']} ({node['type']})")
    print("=" * 50)
    print("💡 本地节点: http://127.0.0.1:5000")
    print("=" * 50)
    init_db()
    app.run(host='0.0.0.0', port=8080, debug=True)