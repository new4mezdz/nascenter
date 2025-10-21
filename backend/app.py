from flask import Flask, jsonify, request, send_file, session, redirect
from flask_cors import CORS
from datetime import datetime
import os
import requests
import sqlite3, json, time


# ✅ 获取项目根目录(nascenter 文件夹)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')

app = Flask(__name__,
            static_folder=FRONTEND_DIR,  # ✅ 指向 frontend 文件夹
            static_url_path='')  # ✅ 静态文件路径为根路径
CORS(app, supports_credentials=True)  # ← 修改这里,支持凭证
app.secret_key = 'your-secret-key-change-this-in-production'  # ← 添加密钥

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


# 文件: 主控中心 app.py

# ... (其他 import 和代码)

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

    # 👇 新增：插入默认管理员
    cursor.execute('''
            INSERT OR IGNORE INTO users (username, password_hash, role, email)
            VALUES ('admin', '123', 'admin', 'admin@nas.local')
        ''')

    # 👇 新增：插入默认分组
    groups_data = [
        ('group_core', '核心服务器组', '生产环境', '["node-1","node-2"]', '#ef4444', '🔥'),
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
        # 登录成功,保存到 session
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']

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


# 登录检查装饰器
def login_required(f):
    """要求登录的装饰器"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "未登录,请先登录"}), 401
        return f(*args, **kwargs)

    return decorated_function
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


# ❌ 缺少这个接口
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


@app.route('/api/node-groups/<group_id>', methods=['PUT'])
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


@app.errorhandler(404)
def not_found(error):
    """404 错误处理"""
    return jsonify({"error": "资源不存在"}), 404


@app.errorhandler(500)
def internal_error(error):
    """500 错误处理"""
    return jsonify({"error": "服务器内部错误"}), 500


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