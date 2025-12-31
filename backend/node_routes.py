# node_routes.py - 节点管理路由
from flask import Blueprint, jsonify, request, session
import sqlite3
import json
import time
import requests
from datetime import datetime
from auth import login_required, admin_required
from common import (
    get_db, ACTIVE_NODES, load_nodes_config, save_nodes_config,
    get_node_config_by_id, get_node_from_db, get_all_nodes_from_db,
    update_node_config, fetch_node_data
)
from config import NAS_SHARED_SECRET

node_bp = Blueprint('node', __name__)


@node_bp.route('/api/node-register', methods=['POST'])
def node_register():
    """接收节点注册/心跳"""
    data = request.json

    if data.get('secret') != NAS_SHARED_SECRET:
        return jsonify({'error': '密钥验证失败'}), 403

    node_id = data.get('node_id')

    ACTIVE_NODES[node_id] = {
        'id': node_id,
        'name': data.get('name', '未命名节点'),
        'ip': data.get('ip'),
        'port': data.get('port'),
        'status': 'online',
        'stats': data.get('stats', {}),
        'last_heartbeat': datetime.now().isoformat()
    }

    update_node_config(node_id, data)

    return jsonify({'success': True, 'message': '注册成功'})


@node_bp.route('/api/nodes', methods=['GET'])
@login_required
def get_all_nodes():
    """获取所有节点 - 从数据库读取，根据用户权限和节点策略过滤"""
    try:
        db = get_db()
        cursor = db.cursor()

        user_id = session.get('user_id')
        role = session.get('role')

        # 获取用户的节点访问权限
        cursor.execute('SELECT node_access FROM users WHERE id = ?', (user_id,))
        user_row = cursor.fetchone()

        accessible_node_ids = None

        if role == 'admin':
            accessible_node_ids = None
        elif user_row:
            node_access = json.loads(user_row['node_access'])
            access_type = node_access.get('type', 'all')

            if access_type == 'all':
                accessible_node_ids = None
            elif access_type == 'groups':
                allowed_groups = node_access.get('allowed_groups', [])
                if allowed_groups:
                    placeholders = ','.join('?' * len(allowed_groups))
                    cursor.execute(f'''
                        SELECT DISTINCT node_id
                        FROM node_group_members
                        WHERE group_id IN ({placeholders})
                    ''', allowed_groups)
                    accessible_node_ids = [row['node_id'] for row in cursor.fetchall()]
                else:
                    accessible_node_ids = []
            elif access_type == 'custom':
                accessible_node_ids = node_access.get('allowed_nodes', [])
            else:
                accessible_node_ids = []

            denied_nodes = node_access.get('denied_nodes', [])
            if accessible_node_ids is not None and denied_nodes:
                accessible_node_ids = [nid for nid in accessible_node_ids if nid not in denied_nodes]

        # 根据权限查询节点
        if accessible_node_ids is None:
            cursor.execute('''
                SELECT node_id, ip, port, status, last_seen, created_at
                FROM nodes
                ORDER BY created_at DESC
            ''')
        elif accessible_node_ids:
            placeholders = ','.join('?' * len(accessible_node_ids))
            cursor.execute(f'''
                SELECT node_id, ip, port, status, last_seen, created_at
                FROM nodes
                WHERE node_id IN ({placeholders})
                ORDER BY created_at DESC
            ''', accessible_node_ids)
        else:
            return jsonify([])

        nodes = []

        for row in cursor.fetchall():
            node_id = row['node_id']
            status = row['status']

            # 节点策略过滤
            cursor.execute('SELECT policy FROM node_policies WHERE node_id = ?', (node_id,))
            policy_row = cursor.fetchone()
            policy = policy_row['policy'] if policy_row else 'all_users'

            if policy == 'disabled':
                if role == 'admin':
                    pass
                else:
                    continue
            elif policy == 'admin_only' and role != 'admin':
                continue
            elif policy == 'whitelist':
                if role != 'admin':
                    cursor.execute('SELECT 1 FROM whitelist_users WHERE user_id = ?', (user_id,))
                    if not cursor.fetchone():
                        continue

            # 获取磁盘总容量
            cursor.execute('''
                SELECT SUM(capacity_gb) as total_storage
                FROM node_disks
                WHERE node_id = ?
            ''', (node_id,))
            disk_row = cursor.fetchone()
            total_storage = disk_row['total_storage'] if disk_row['total_storage'] else 0

            cpu_usage = 0
            memory_usage = 0
            disk_usage = 0
            used_storage = 0
            cpu_temp = 0

            # 实时检测节点状态
            if status == 'online':
                try:
                    stats_url = f"http://{row['ip']}:{row['port']}/api/system-stats"
                    stats_response = requests.get(stats_url, timeout=2)

                    if stats_response.status_code == 200:
                        stats = stats_response.json()
                        cpu_usage = stats.get('cpu_percent', 0)
                        memory_usage = stats.get('memory_percent', 0)
                        disk_usage = stats.get('disk_percent', 0)
                        used_storage = stats.get('disk_used_gb', 0)
                        cpu_temp = stats.get('cpu_temp_celsius', 0)
                    else:
                        status = 'offline'
                        cursor.execute('UPDATE nodes SET status = ? WHERE node_id = ?', ('offline', node_id))
                        db.commit()

                except Exception as e:
                    print(f"[DEBUG] 节点 {node_id} 离线: {e}")
                    status = 'offline'
                    cursor.execute('UPDATE nodes SET status = ? WHERE node_id = ?', ('offline', node_id))
                    db.commit()

            node_data = {
                'id': node_id,
                'name': node_id,
                'ip': row['ip'],
                'port': row['port'],
                'status': status,
                'cpu_usage': cpu_usage,
                'memory_usage': memory_usage,
                'disk_usage': disk_usage,
                'total_storage': total_storage,
                'used_storage': used_storage,
                'cpu_temp': cpu_temp,
                'last_updated': row['last_seen'] or row['created_at'],
                'policy': policy
            }

            if policy == 'disabled' and role == 'admin':
                node_data['is_disabled'] = True
                node_data['status'] = 'disabled'

            nodes.append(node_data)

        return jsonify(nodes)

    except Exception as e:
        print(f"[获取节点列表失败] {e}")
        import traceback
        traceback.print_exc()
        return jsonify([]), 500


@node_bp.route('/api/nodes/<node_id>', methods=['GET'])
def get_node(node_id):
    """获取指定节点信息"""
    node_config = None
    for config in get_all_nodes_from_db():
        if config['id'] == node_id:
            node_config = config
            break

    if not node_config:
        return jsonify({"error": "节点不存在"}), 404

    node_data = fetch_node_data(node_config)
    return jsonify(node_data)


@node_bp.route('/api/nodes/<node_id>/refresh', methods=['POST'])
def refresh_node(node_id):
    """刷新节点数据"""
    node_config = None
    for config in get_all_nodes_from_db():
        if config['id'] == node_id:
            node_config = config
            break

    if not node_config:
        return jsonify({"error": "节点不存在"}), 404

    node_data = fetch_node_data(node_config, timeout=5)
    return jsonify(node_data)


@node_bp.route('/api/nodes/<node_id>/rename', methods=['PUT'])
@admin_required
def rename_node(node_id):
    """修改节点名称"""
    data = request.json
    new_name = data.get('new_name', '').strip()

    if not new_name:
        return jsonify({'error': '节点名称不能为空'}), 400

    config = load_nodes_config()
    node_in_config = next((n for n in config if n['id'] == node_id), None)

    if not node_in_config:
        return jsonify({'error': '节点不存在于配置文件中'}), 404

    old_name = node_in_config['name']
    node_in_config['name'] = new_name
    save_nodes_config(config)

    print(f"[配置] 节点 {node_id} 已从 '{old_name}' 持久化重命名为 '{new_name}'")

    if node_id in ACTIVE_NODES:
        ACTIVE_NODES[node_id]['name'] = new_name
        print(f"[内存] 活跃节点 {node_id} 已同步重命名")

        try:
            node = ACTIVE_NODES[node_id]
            requests.post(
                f"http://{node['ip']}:{node['port']}/api/update-name",
                json={'name': new_name},
                timeout=5
            )
        except:
            pass

    return jsonify({
        'success': True,
        'message': '节点改名成功 (已持久化)',
        'old_name': old_name,
        'new_name': new_name
    })


@node_bp.route('/api/nodes/<node_id>', methods=['DELETE'])
@admin_required
def delete_node(node_id):
    """删除节点"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('SELECT node_id FROM nodes WHERE node_id = ?', (node_id,))
        node = cursor.fetchone()

        if not node:
            return jsonify({'success': False, 'error': '节点不存在'}), 404

        cursor.execute('DELETE FROM node_disks WHERE node_id = ?', (node_id,))
        cursor.execute('DELETE FROM node_group_members WHERE node_id = ?', (node_id,))
        cursor.execute('DELETE FROM ec_policy_applications WHERE node_id = ?', (node_id,))
        cursor.execute('DELETE FROM nodes WHERE node_id = ?', (node_id,))
        conn.commit()

        if node_id in ACTIVE_NODES:
            del ACTIVE_NODES[node_id]

        return jsonify({
            'success': True,
            'message': f'节点 {node_id} 已删除',
            'deleted_node': node_id
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@node_bp.route('/api/nodes/register', methods=['POST'])
def register_node():
    """客户端节点注册"""
    try:
        if request.headers.get('X-NAS-Secret') != NAS_SHARED_SECRET:
            return jsonify({'success': False, 'error': '认证失败'}), 401

        data = request.json
        node_id = data.get('node_id')
        ip = data.get('ip')
        port = data.get('port')

        if not node_id:
            return jsonify({'success': False, 'error': '缺少节点ID'}), 400

        db = get_db()
        cursor = db.cursor()

        cursor.execute('SELECT * FROM nodes WHERE node_id = ?', (node_id,))
        existing = cursor.fetchone()

        if existing:
            cursor.execute('''
                UPDATE nodes 
                SET ip = ?, port = ?, status = 'online', last_seen = CURRENT_TIMESTAMP
                WHERE node_id = ?
            ''', (ip, port, node_id))
            print(f"[节点更新] {node_id} - {ip}:{port}")
        else:
            cursor.execute('''
                INSERT INTO nodes (node_id, ip, port, status)
                VALUES (?, ?, ?, 'online')
            ''', (node_id, ip, port))
            print(f"[节点注册] {node_id} - {ip}:{port}")

        db.commit()

        return jsonify({
            'success': True,
            'node_id': node_id,
            'message': '注册成功'
        })

    except Exception as e:
        print(f"[节点注册失败] {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@node_bp.route('/api/nodes/initialize', methods=['POST'])
def initialize_node():
    """主控端通知节点身份"""
    data = request.json
    node_id = data.get('node_id')
    if not node_id:
        return jsonify({"success": False, "error": "缺少node_id"}), 400

    node = get_node_from_db(node_id)
    if not node:
        return jsonify({"success": False, "error": "节点不存在"}), 404

    node_url = f"http://{node['ip']}:{node['port']}/api/initialize"
    payload = {
        "node_id": node["id"],
        "master_ip": request.host.split(':')[0],
        "master_port": 8080
    }

    try:
        res = requests.post(node_url, json=payload, timeout=5)
        print(f"[主控] 已发送初始化给 {node['id']} → {res.status_code}")
        return jsonify({"success": True})
    except Exception as e:
        print(f"[主控] 初始化节点失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@node_bp.route('/api/nodes/<node_id>/monitor-stats', methods=['GET'])
def get_node_monitor_stats(node_id):
    """获取单个节点的完整系统监控数据"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT ip, port FROM nodes WHERE node_id = ?', (node_id,))
        node = cursor.fetchone()

        if not node:
            return jsonify({"error": "节点不存在"}), 404

        base_url = f"http://{node['ip']}:{node['port']}"

        sys_response = requests.get(f"{base_url}/api/system-stats", timeout=5)
        hw_response = requests.get(f"{base_url}/api/hardware-data", timeout=5)

        if sys_response.status_code == 200:
            sys_data = sys_response.json()
            hw_data = hw_response.json() if hw_response.status_code == 200 else {}

            result = {
                'temperatures': hw_data.get('temperatures', []),
                'fans': hw_data.get('fans', []),
                'voltages': hw_data.get('voltages', []),
                'powers': hw_data.get('powers', []),
                'clocks': hw_data.get('clocks', []),
                'disks_temp': hw_data.get('disks_temp', []),
                'memory_percent': sys_data.get('memory_percent', 0),
                'disk_total_gb': sys_data.get('disk_total_gb', 0),
                'disk_used_gb': sys_data.get('disk_used_gb', 0),
                'cpu_temp_celsius': sys_data.get('cpu_temp_celsius', 0),
                'cpu_freq': sys_data.get('cpu_freq', 0),
                'cpu_power': sys_data.get('cpu_power', 0),
                'network_download': sys_data.get('network_download', 0),
                'network_upload': sys_data.get('network_upload', 0)
            }

            return jsonify(result)
        else:
            return jsonify({"error": "节点返回错误"}), 500

    except requests.exceptions.Timeout:
        return jsonify({"error": "节点连接超时"}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "无法连接到节点"}), 503
    except Exception as e:
        print(f"[ERROR] 获取节点监控数据失败: {e}")
        return jsonify({"error": str(e)}), 500


@node_bp.route('/api/nodes/<node_id>/disks')
@login_required
def get_node_disks(node_id):
    """获取节点磁盘信息"""
    try:
        db = get_db()
        cursor = db.execute('SELECT node_id, ip, port FROM nodes WHERE node_id = ?', (node_id,))
        node = cursor.fetchone()

        if not node:
            return jsonify({'error': '节点不存在'}), 404

        base_url = f"http://{node['ip']}:{node['port']}"
        response = requests.get(f"{base_url}/api/disks", timeout=10)

        if response.status_code == 200:
            disks_data = response.json()
            return jsonify({
                "success": True,
                "disks": disks_data
            }), 200
        else:
            return jsonify({'error': f'获取磁盘信息失败: {response.text}'}), response.status_code

    except requests.RequestException as e:
        return jsonify({'error': f'请求节点失败: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@node_bp.route('/api/stats', methods=['GET'])
def get_stats():
    """获取系统统计信息"""
    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute('SELECT COUNT(*) as total FROM nodes')
        total_nodes = cursor.fetchone()['total']

        cursor.execute('''
            SELECT COUNT(*) as online 
            FROM nodes 
            WHERE status = 'online'
        ''')
        online_nodes = cursor.fetchone()['online']

        offline_nodes = total_nodes - online_nodes
        warning_nodes = 0

        return jsonify({
            'total_nodes': total_nodes,
            'online_nodes': online_nodes,
            'offline_nodes': offline_nodes,
            'warning_nodes': warning_nodes
        })

    except Exception as e:
        print(f"[获取统计信息失败] {e}")
        return jsonify({
            'total_nodes': 0,
            'online_nodes': 0,
            'offline_nodes': 0,
            'warning_nodes': 0
        }), 500


# ========== 节点分组 API ==========
@node_bp.route('/api/node-groups', methods=['GET'])
@login_required
def get_node_groups():
    """获取所有节点分组"""
    conn = sqlite3.connect('nas_center.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM node_groups')
    groups = [dict(row) for row in cursor.fetchall()]
    conn.close()

    for group in groups:
        group['node_ids'] = json.loads(group['node_ids'])

    return jsonify(groups)


@node_bp.route('/api/node-groups', methods=['POST'])
@login_required
@admin_required
def create_node_group():
    """创建节点分组"""
    data = request.json
    group_id = f"group_{int(time.time())}"

    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO node_groups (group_id, group_name, description, node_ids, color, icon)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (group_id, data['group_name'], data.get('description', ''),
          json.dumps(data['node_ids']), data.get('color', '#3b82f6'), data.get('icon', '📁')))

    node_ids = data.get('node_ids', [])
    for nid in node_ids:
        cursor.execute('''
            INSERT OR IGNORE INTO node_group_members (group_id, node_id)
            VALUES (?, ?)
        ''', (group_id, nid))

    conn.commit()
    conn.close()
    return jsonify({"success": True, "group_id": group_id})


@node_bp.route('/api/node-groups/<group_id>', methods=['PUT'])
@login_required
@admin_required
def update_node_group(group_id):
    """更新节点分组"""
    data = request.json
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE node_groups 
        SET group_name=?, description=?, node_ids=?, color=?, icon=?
        WHERE group_id=?
    ''', (data['group_name'], data.get('description', ''), json.dumps(data['node_ids']),
          data.get('color', '#3b82f6'), data.get('icon', '📁'), group_id))

    cursor.execute('DELETE FROM node_group_members WHERE group_id = ?', (group_id,))

    node_ids = data.get('node_ids', [])
    for nid in node_ids:
        cursor.execute('''
            INSERT OR IGNORE INTO node_group_members (group_id, node_id)
            VALUES (?, ?)
        ''', (group_id, nid))

    conn.commit()
    conn.close()
    return jsonify({"success": True})


@node_bp.route('/api/node-groups/<group_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_node_group(group_id):
    """删除节点分组"""
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()

    cursor.execute('DELETE FROM node_groups WHERE group_id = ?', (group_id,))
    cursor.execute('DELETE FROM node_group_members WHERE group_id = ?', (group_id,))

    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ========== 节点策略 API ==========
@node_bp.route('/api/node-policies', methods=['GET'])
@login_required
def get_node_policies():
    """获取所有节点策略"""
    conn = sqlite3.connect('nas_center.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM node_policies')
    policies = {row['node_id']: row['policy'] for row in cursor.fetchall()}
    conn.close()
    return jsonify(policies)


@node_bp.route('/api/node-policies/<node_id>', methods=['PUT'])
@login_required
def update_node_policy(node_id):
    """更新节点策略"""
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


@node_bp.route('/api/nodes/update-disks', methods=['POST'])
def update_node_disks():
    """更新节点磁盘信息"""
    try:
        if request.headers.get('X-NAS-Secret') != NAS_SHARED_SECRET:
            return jsonify({'success': False, 'error': '认证失败'}), 401

        data = request.json
        node_id = data.get('node_id')
        disks = data.get('disks', [])

        if not node_id:
            return jsonify({'success': False, 'error': '缺少节点ID'}), 400

        db = get_db()
        cursor = db.cursor()

        # 删除旧的磁盘记录
        cursor.execute('DELETE FROM node_disks WHERE node_id = ?', (node_id,))

        # 插入新的磁盘记录
        for disk in disks:
            cursor.execute('''
                INSERT INTO node_disks (node_id, mount, capacity_gb, status, is_encrypted, is_locked)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                node_id,
                disk.get('mount'),
                disk.get('capacity_gb'),
                disk.get('status', 'online'),
                disk.get('is_encrypted', 0),
                disk.get('is_locked', 0)
            ))

        db.commit()
        print(f"[磁盘更新] {node_id}: {len(disks)} 个磁盘")

        return jsonify({'success': True, 'message': '更新成功'})

    except Exception as e:
        print(f"[磁盘更新失败] {e}")
        return jsonify({'success': False, 'error': str(e)}), 500