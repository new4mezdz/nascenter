# ec_routes.py - 纠删码策略路由
from flask import Blueprint, jsonify, request
import json
import requests
from auth import login_required, admin_required
from common import get_db_connection
from config import NAS_SHARED_SECRET

ec_bp = Blueprint('ec', __name__)


def init_ec_tables():
    """初始化纠删码相关表"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ec_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            policy_type TEXT NOT NULL,
            k INTEGER NOT NULL,
            m INTEGER NOT NULL,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cross_ec_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT DEFAULT 'default',
            k INTEGER NOT NULL,
            m INTEGER NOT NULL,
            nodes TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ec_policy_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_id INTEGER NOT NULL,
            node_id TEXT,
            node_group TEXT,
            disks TEXT,
            applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (policy_id) REFERENCES ec_policies(id)
        )
    ''')

    conn.commit()
    conn.close()


@ec_bp.route('/api/ec_policies', methods=['GET'])
@login_required
def get_ec_policies():
    """获取所有纠删码策略"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, name, description, policy_type, k, m, status, created_at
        FROM ec_policies
        ORDER BY created_at DESC
    ''')

    policies = []
    for row in cursor.fetchall():
        policy = {
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'policy_type': row[3],
            'k': row[4],
            'm': row[5],
            'status': row[6],
            'created_at': row[7]
        }

        cursor.execute('''
            SELECT COUNT(*) FROM ec_policy_applications 
            WHERE policy_id = ?
        ''', (policy['id'],))
        policy['application_count'] = cursor.fetchone()[0]

        policies.append(policy)

    conn.close()
    return jsonify({'success': True, 'policies': policies})


@ec_bp.route('/api/ec_policies', methods=['POST'])
@admin_required
def create_ec_policy():
    """创建纠删码策略"""
    data = request.json
    name = data.get('name')
    description = data.get('description', '')
    policy_type = data.get('policy_type', 'intra_node')
    k = data.get('k')
    m = data.get('m')

    if not name or not k or not m:
        return jsonify({'error': '缺少必要参数'}), 400

    if policy_type not in ['intra_node', 'inter_node']:
        return jsonify({'error': '策略类型无效'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO ec_policies (name, description, policy_type, k, m, status)
        VALUES (?, ?, ?, ?, ?, 'active')
    ''', (name, description, policy_type, k, m))

    policy_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': '策略创建成功', 'policy_id': policy_id})


@ec_bp.route('/api/ec_policies/<int:policy_id>', methods=['DELETE'])
@admin_required
def delete_ec_policy(policy_id):
    """删除纠删码策略"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM ec_policy_applications WHERE policy_id = ?', (policy_id,))
    app_count = cursor.fetchone()[0]

    if app_count > 0:
        conn.close()
        return jsonify({'error': f'该策略已被应用到{app_count}个位置,无法删除'}), 400

    cursor.execute('DELETE FROM ec_policies WHERE id = ?', (policy_id,))

    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'error': '策略不存在'}), 404

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': '策略删除成功'})


@ec_bp.route('/api/ec_policies/<int:policy_id>/apply', methods=['POST'])
@admin_required
def apply_ec_policy(policy_id):
    """将纠删码策略应用到节点"""
    data = request.json
    node_id = data.get('node_id')
    disks = data.get('disks', [])

    if not node_id:
        return jsonify({'error': '缺少节点ID'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT policy_type, k, m FROM ec_policies WHERE id = ?', (policy_id,))
    policy = cursor.fetchone()

    if not policy:
        conn.close()
        return jsonify({'error': '策略不存在'}), 404

    policy_type, k, m = policy[0], policy[1], policy[2]

    if policy_type != 'intra_node':
        conn.close()
        return jsonify({'error': '当前仅支持节点内策略'}), 400

    cursor.execute('SELECT ip, port FROM nodes WHERE node_id = ?', (node_id,))
    node = cursor.fetchone()

    if not node:
        conn.close()
        return jsonify({'error': '节点不存在'}), 404

    node_ip, node_port = node[0], node[1]

    try:
        node_url = f"http://{node_ip}:{node_port}/api/ec_config"
        response = requests.post(node_url, json={
            'scheme': 'rs',
            'k': k,
            'm': m,
            'disks': disks
        }, timeout=10)

        if response.status_code == 200:
            cursor.execute('''
                INSERT INTO ec_policy_applications (policy_id, node_id, disks)
                VALUES (?, ?, ?)
            ''', (policy_id, node_id, json.dumps(disks)))
            conn.commit()
            conn.close()

            return jsonify({'success': True, 'message': '策略应用成功'})
        else:
            conn.close()
            return jsonify({'error': f'节点返回错误: {response.text}'}), 500

    except Exception as e:
        conn.close()
        return jsonify({'error': f'应用策略失败: {str(e)}'}), 500


@ec_bp.route('/api/nodes/<node_id>/ec_config', methods=['GET'])
@login_required
def get_node_ec_config(node_id):
    """获取节点的纠删码配置"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT ip, port FROM nodes WHERE node_id = ?', (node_id,))
    node = cursor.fetchone()

    if not node:
        conn.close()
        return jsonify({'error': '节点不存在'}), 404

    node_ip, node_port = node[0], node[1]

    try:
        response = requests.get(
            f"http://{node_ip}:{node_port}/api/ec_config",
            headers={'X-NAS-Secret': NAS_SHARED_SECRET},
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            conn.close()
            return jsonify(data)
        else:
            conn.close()
            return jsonify({'error': '获取配置失败'}), 500

    except Exception as e:
        conn.close()
        return jsonify({'error': f'请求节点失败: {str(e)}'}), 500


@ec_bp.route('/api/nodes/<node_id>/ec_config', methods=['POST'])
@admin_required
def save_node_ec_config(node_id):
    """保存节点的纠删码配置"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT ip, port FROM nodes WHERE node_id = ?', (node_id,))
    node = cursor.fetchone()

    if not node:
        conn.close()
        return jsonify({'error': '节点不存在'}), 404

    node_ip, node_port = node[0], node[1]

    try:
        response = requests.post(
            f"http://{node_ip}:{node_port}/api/ec_config",
            json=request.json,
            headers={'X-NAS-Secret': NAS_SHARED_SECRET},
            timeout=10
        )

        conn.close()
        if response.status_code == 200:
            return jsonify({'success': True, 'message': '配置保存成功'})
        else:
            return jsonify({'error': response.json().get('error', '保存失败')}), response.status_code

    except Exception as e:
        conn.close()
        return jsonify({'error': f'请求节点失败: {str(e)}'}), 500


@ec_bp.route('/api/nodes/<node_id>/ec_config', methods=['DELETE'])
@admin_required
def delete_node_ec_config(node_id):
    """删除节点的纠删码配置"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT ip, port FROM nodes WHERE node_id = ?', (node_id,))
    node = cursor.fetchone()

    if not node:
        conn.close()
        return jsonify({'error': '节点不存在'}), 404

    node_ip, node_port = node[0], node[1]

    try:
        response = requests.delete(
            f"http://{node_ip}:{node_port}/api/ec_config",
            headers={'X-NAS-Secret': NAS_SHARED_SECRET},
            timeout=10
        )

        if response.status_code == 200:
            cursor.execute('DELETE FROM ec_policy_applications WHERE node_id = ?', (node_id,))
            conn.commit()
            conn.close()

            return jsonify({'success': True, 'message': '配置删除成功'})
        else:
            conn.close()
            return jsonify({'error': '删除配置失败'}), 500

    except Exception as e:
        conn.close()
        return jsonify({'error': f'请求节点失败: {str(e)}'}), 500


# ========== 跨节点EC配置 ==========

@ec_bp.route('/api/cross_ec_config', methods=['GET'])
@login_required
def get_cross_ec_config():
    """获取跨节点EC配置"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, name, k, m, nodes, status, created_at 
        FROM cross_ec_config 
        WHERE status = 'active'
        ORDER BY created_at DESC
        LIMIT 1
    ''')
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({'success': True, 'config': None})

    return jsonify({
        'success': True,
        'config': {
            'id': row[0],
            'name': row[1],
            'k': row[2],
            'm': row[3],
            'nodes': json.loads(row[4]),
            'status': row[5],
            'createdAt': row[6]
        }
    })


@ec_bp.route('/api/cross_ec_config', methods=['POST'])
@admin_required
def save_cross_ec_config():
    """保存跨节点EC配置"""
    data = request.json
    k = data.get('k')
    m = data.get('m')
    nodes = data.get('nodes', [])
    name = data.get('name', 'default')

    if not k or not m:
        return jsonify({'error': '缺少k或m参数'}), 400

    if not nodes or len(nodes) < 2:
        return jsonify({'error': '跨节点EC至少需要2个节点'}), 400

    # 计算总磁盘数
    total_disks = sum(len(n.get('disks', [])) for n in nodes)
    if total_disks < k + m:
        return jsonify({'error': f'总磁盘数({total_disks})必须 >= k+m({k + m})'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # 先将旧配置设为inactive
    cursor.execute("UPDATE cross_ec_config SET status = 'inactive'")

    # 插入新配置
    cursor.execute('''
        INSERT INTO cross_ec_config (name, k, m, nodes, status)
        VALUES (?, ?, ?, ?, 'active')
    ''', (name, k, m, json.dumps(nodes)))

    config_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'message': '跨节点EC配置保存成功',
        'config_id': config_id
    })


@ec_bp.route('/api/cross_ec_config', methods=['DELETE'])
@admin_required
def delete_cross_ec_config():
    """删除跨节点EC配置"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE cross_ec_config SET status = 'deleted'")
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': '跨节点EC配置已删除'})