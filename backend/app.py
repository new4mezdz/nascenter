from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from datetime import datetime
import os
import requests

# ✅ 获取项目根目录(nascenter 文件夹)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')

app = Flask(__name__,
            static_folder=FRONTEND_DIR,  # ✅ 指向 frontend 文件夹
            static_url_path='')  # ✅ 静态文件路径为根路径
CORS(app)

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
    """从真实节点获取数据"""
    try:
        base_url = f"http://{node_config['ip']}:{node_config['port']}"

        # 1. 获取节点基本信息
        info_response = requests.get(
            f"{base_url}/api/node-info",
            timeout=timeout
        )

        if info_response.status_code != 200:
            raise Exception("节点信息获取失败")

        # 2. 获取系统统计信息
        stats_response = requests.get(
            f"{base_url}/api/system-stats",
            timeout=timeout
        )

        if stats_response.status_code != 200:
            raise Exception("系统统计获取失败")

        info_data = info_response.json()
        stats_data = stats_response.json()

        # 3. 合并数据
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
            "network_speed": 0,
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
        "network_speed": 0,
        "last_updated": datetime.now().isoformat(),
        "offline_reason": reason
    }


@app.route('/')
def index():
    """根路由 - 返回前端页面"""
    html_path = os.path.join(FRONTEND_DIR, '1.html')

    if os.path.exists(html_path):
        return send_file(html_path)
    else:
        return jsonify({
            "message": "NAS Center API",
            "version": "1.0.0",
            "error": "前端页面未找到",
            "expected_path": html_path,
            "note": "请确保 frontend/1.html 文件存在"
        }), 404


@app.route('/api/nodes', methods=['GET'])
def get_all_nodes():
    """获取所有 NAS 节点的真实数据"""
    nodes_data = []

    for node_config in NODES_CONFIG:
        print(f"[INFO] 正在获取节点数据: {node_config['name']}")
        node_data = fetch_node_data(node_config)
        nodes_data.append(node_data)

    return jsonify(nodes_data)


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

    app.run(host='0.0.0.0', port=8080, debug=True)