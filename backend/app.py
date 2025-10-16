from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 模拟数据存储
nas_nodes = {
    "node-1": {
        "id": "node-1",
        "name": "NAS-主节点",
        "ip": "192.168.1.100",
        "port": 8000,
        "status": "online",
        "cpu_usage": 45.5,
        "memory_usage": 62.3,
        "disk_usage": 78.9,
        "total_storage": 2000,
        "used_storage": 1578,
        "network_speed": 125.6,
        "last_updated": datetime.now().isoformat()
    },
    "node-2": {
        "id": "node-2",
        "name": "NAS-备份节点",
        "ip": "192.168.1.101",
        "port": 8000,
        "status": "online",
        "cpu_usage": 23.8,
        "memory_usage": 45.2,
        "disk_usage": 56.4,
        "total_storage": 4000,
        "used_storage": 2256,
        "network_speed": 89.3,
        "last_updated": datetime.now().isoformat()
    },
    "node-3": {
        "id": "node-3",
        "name": "NAS-测试节点",
        "ip": "192.168.1.102",
        "port": 8000,
        "status": "warning",
        "cpu_usage": 87.2,
        "memory_usage": 91.5,
        "disk_usage": 45.3,
        "total_storage": 1000,
        "used_storage": 453,
        "network_speed": 45.7,
        "last_updated": datetime.now().isoformat()
    },
    "node-4": {
        "id": "node-4",
        "name": "NAS-离线节点",
        "ip": "192.168.1.103",
        "port": 8000,
        "status": "offline",
        "cpu_usage": 0,
        "memory_usage": 0,
        "disk_usage": 0,
        "total_storage": 2000,
        "used_storage": 0,
        "network_speed": 0,
        "last_updated": datetime.now().isoformat()
    }
}


@app.route('/')
def index():
    """根路由"""
    return jsonify({
        "message": "NAS Center API",
        "version": "1.0.0",
        "framework": "Flask"
    })


@app.route('/api/nodes', methods=['GET'])
def get_all_nodes():
    """获取所有 NAS 节点"""
    return jsonify(list(nas_nodes.values()))


@app.route('/api/nodes/<node_id>', methods=['GET'])
def get_node(node_id):
    """获取指定 NAS 节点"""
    if node_id not in nas_nodes:
        return jsonify({"error": "节点不存在"}), 404
    return jsonify(nas_nodes[node_id])


@app.route('/api/nodes', methods=['POST'])
def create_node():
    """创建新的 NAS 节点"""
    data = request.get_json()

    if not data or 'name' not in data or 'ip' not in data or 'port' not in data:
        return jsonify({"error": "缺少必要参数"}), 400

    node_id = f"node-{len(nas_nodes) + 1}"
    new_node = {
        "id": node_id,
        "name": data['name'],
        "ip": data['ip'],
        "port": data['port'],
        "status": "offline",
        "cpu_usage": 0,
        "memory_usage": 0,
        "disk_usage": 0,
        "total_storage": 0,
        "used_storage": 0,
        "network_speed": 0,
        "last_updated": datetime.now().isoformat()
    }

    nas_nodes[node_id] = new_node
    return jsonify(new_node), 201


@app.route('/api/nodes/<node_id>', methods=['PUT'])
def update_node(node_id):
    """更新 NAS 节点信息"""
    if node_id not in nas_nodes:
        return jsonify({"error": "节点不存在"}), 404

    data = request.get_json()
    node = nas_nodes[node_id]

    # 更新允许的字段
    allowed_fields = ['name', 'ip', 'port', 'status', 'cpu_usage',
                      'memory_usage', 'disk_usage', 'total_storage',
                      'used_storage', 'network_speed']

    for field in allowed_fields:
        if field in data:
            node[field] = data[field]

    node['last_updated'] = datetime.now().isoformat()
    return jsonify(node)


@app.route('/api/nodes/<node_id>', methods=['DELETE'])
def delete_node(node_id):
    """删除 NAS 节点"""
    if node_id not in nas_nodes:
        return jsonify({"error": "节点不存在"}), 404

    del nas_nodes[node_id]
    return jsonify({"message": "节点删除成功"})


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取整体统计信息"""
    total_nodes = len(nas_nodes)
    online_nodes = sum(1 for node in nas_nodes.values() if node['status'] == 'online')
    offline_nodes = sum(1 for node in nas_nodes.values() if node['status'] == 'offline')
    warning_nodes = sum(1 for node in nas_nodes.values() if node['status'] == 'warning')

    total_storage = sum(node['total_storage'] for node in nas_nodes.values())
    used_storage = sum(node['used_storage'] for node in nas_nodes.values())

    online_node_list = [node for node in nas_nodes.values() if node['status'] == 'online']
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


@app.route('/api/nodes/<node_id>/refresh', methods=['POST'])
def refresh_node(node_id):
    """刷新节点数据（模拟）"""
    if node_id not in nas_nodes:
        return jsonify({"error": "节点不存在"}), 404

    node = nas_nodes[node_id]

    # 模拟数据更新
    if node['status'] == 'online':
        import random
        node['cpu_usage'] = round(random.uniform(20, 90), 1)
        node['memory_usage'] = round(random.uniform(30, 95), 1)
        node['network_speed'] = round(random.uniform(50, 150), 1)

    node['last_updated'] = datetime.now().isoformat()
    return jsonify(node)


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
    print("🚀 NAS Center API 服务启动中...")
    print("=" * 50)
    print("📡 API 地址: http://localhost:8080")
    print("📚 文档:")
    print("  - GET  /api/nodes          获取所有节点")
    print("  - GET  /api/nodes/<id>     获取指定节点")
    print("  - POST /api/nodes          创建节点")
    print("  - PUT  /api/nodes/<id>     更新节点")
    print("  - DELETE /api/nodes/<id>   删除节点")
    print("  - GET  /api/stats          获取统计信息")
    print("  - POST /api/nodes/<id>/refresh  刷新节点数据")
    print("=" * 50)

    app.run(host='0.0.0.0', port=8080, debug=True)