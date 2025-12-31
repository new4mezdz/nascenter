# common.py - 公共模块
import sqlite3
import json
from flask import g
from datetime import datetime

# ========== 常量 ==========
DATABASE = 'nas_center.db'
ACCESS_TOKEN_SECRET = 'your-access-token-secret-key'
NODES_CONFIG_FILE = 'nodes_config.json'

# 存储活跃节点信息(内存中)
ACTIVE_NODES = {}  # {node_id: {name, ip, port, stats, last_heartbeat}}

# 权限级别
PERM_READONLY = 1
PERM_READWRITE = 2
PERM_FULLCONTROL = 3

PERMISSION_MAP = {
    'readonly': PERM_READONLY,
    'readwrite': PERM_READWRITE,
    'fullcontrol': PERM_FULLCONTROL
}


# ========== 数据库连接 ==========
def get_db():
    """获取数据库连接（Flask 请求上下文）"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


def get_db_connection():
    """获取独立数据库连接（非请求上下文）"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# ========== 节点配置函数 ==========
def load_nodes_config():
    """从数据库加载节点配置"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT node_id, ip, port, status FROM nodes')
        nodes = cursor.fetchall()
        conn.close()

        return [
            {
                "id": node['node_id'],
                "name": node['node_id'],
                "ip": node['ip'],
                "port": node['port'],
                "type": "remote",
                "status": node['status']
            }
            for node in nodes
        ]
    except Exception as e:
        print(f"加载节点配置失败: {e}")
        return []


def save_nodes_config(config):
    """不再需要保存到文件，数据已经在数据库中"""
    pass


def get_node_config_by_id(node_id):
    """从数据库获取节点配置"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT node_id, ip, port, status FROM nodes WHERE node_id = ?', (node_id,))
        row = cursor.fetchone()

        if row:
            return {
                'id': row['node_id'],
                'name': row['node_id'],
                'ip': row['ip'],
                'port': row['port'],
                'status': row['status']
            }
        return None
    except Exception as e:
        print(f"[ERROR] 获取节点配置失败: {e}")
        return None


def get_node_from_db(node_id):
    """从数据库获取节点信息"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT node_id, ip, port, status FROM nodes WHERE node_id = ?', (node_id,))
        row = cursor.fetchone()
        if row:
            return {
                'id': row['node_id'],
                'name': row['node_id'],
                'ip': row['ip'],
                'port': row['port'],
                'status': row['status']
            }
        return None
    except Exception as e:
        print(f"[ERROR] get_node_from_db: {e}")
        return None


def get_all_nodes_from_db():
    """获取所有节点"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT node_id, ip, port, status FROM nodes')
        rows = cursor.fetchall()
        return [
            {
                'id': row['node_id'],
                'name': row['node_id'],
                'ip': row['ip'],
                'port': row['port'],
                'status': row['status']
            }
            for row in rows
        ]
    except Exception as e:
        print(f"[ERROR] get_all_nodes_from_db: {e}")
        return []


def update_node_config(node_id, data):
    """更新或添加节点配置"""
    config = load_nodes_config()
    existing = next((n for n in config if n['id'] == node_id), None)

    if existing:
        existing['name'] = data.get('name', existing.get('name'))
        existing['ip'] = data.get('ip', existing.get('ip'))
        existing['port'] = data.get('port', existing.get('port'))
    else:
        config.append({
            'id': node_id,
            'name': data.get('name', '未命名节点'),
            'ip': data.get('ip'),
            'port': data.get('port'),
            'type': 'auto'
        })

    save_nodes_config(config)


# ========== 节点数据获取 ==========
def fetch_node_data(node_config, timeout=3):
    """从真实节点获取数据"""
    import requests
    try:
        base_url = f"http://{node_config['ip']}:{node_config['port']}"

        info_response = requests.get(f"{base_url}/api/node-info", timeout=timeout)
        if info_response.status_code != 200:
            raise Exception("节点信息获取失败")

        stats_response = requests.get(f"{base_url}/api/system-stats", timeout=timeout)
        if stats_response.status_code != 200:
            raise Exception("系统统计获取失败")

        info_data = info_response.json()
        stats_data = stats_response.json()

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
        "cpu_temp": 0,
        "last_updated": datetime.now().isoformat(),
        "offline_reason": reason
    }


# ========== 访问申请相关 ==========
def save_access_request(request_data):
    """保存访问申请到数据库"""
    conn = get_db_connection()
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
    conn = get_db_connection()
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