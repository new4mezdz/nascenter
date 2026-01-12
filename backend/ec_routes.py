# ec_routes.py - 纠删码策略路由
from flask import Blueprint, jsonify, request, send_file
import json
import requests
import hashlib
import time
import os
from io import BytesIO
from auth import login_required, admin_required
from common import get_db_connection, get_node_config_by_id
from config import NAS_SHARED_SECRET

# 导入EC编解码引擎
from ec_engine import rs_encode, rs_decode

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

    # 跨节点EC文件索引表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cross_ec_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            size INTEGER NOT NULL,
            k INTEGER NOT NULL,
            m INTEGER NOT NULL,
            shard_size INTEGER NOT NULL,
            sha256 TEXT,
            disks TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()


# ==================== EC策略管理 ====================

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
@login_required
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
@login_required
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
@login_required
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


# ==================== 节点EC配置代理 ====================

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
    conn.close()

    try:
        response = requests.get(
            f"http://{node_ip}:{node_port}/api/ec_config",
            headers={'X-NAS-Secret': NAS_SHARED_SECRET},
            timeout=5
        )

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            # 节点可能未配置EC，返回空配置而不是500错误
            return jsonify({'config': None, 'capacity': None})

    except Exception as e:
        return jsonify({'error': f'请求节点失败: {str(e)}'}), 500


@ec_bp.route('/api/nodes/<node_id>/ec_config', methods=['POST'])
@login_required
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
    conn.close()

    try:
        response = requests.post(
            f"http://{node_ip}:{node_port}/api/ec_config",
            json=request.json,
            headers={'X-NAS-Secret': NAS_SHARED_SECRET},
            timeout=10
        )

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': response.json().get('error', '保存失败')}), 500

    except Exception as e:
        return jsonify({'error': f'请求节点失败: {str(e)}'}), 500


@ec_bp.route('/api/nodes/<node_id>/ec_config', methods=['DELETE'])
@login_required
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
    conn.close()

    try:
        response = requests.delete(
            f"http://{node_ip}:{node_port}/api/ec_config",
            headers={'X-NAS-Secret': NAS_SHARED_SECRET},
            timeout=10
        )

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': response.json().get('error', '删除失败')}), 500

    except Exception as e:
        return jsonify({'error': f'请求节点失败: {str(e)}'}), 500


@ec_bp.route('/api/nodes/<node_id>/disks', methods=['GET'])
@login_required
def proxy_node_disks(node_id):
    """代理转发磁盘列表请求到对应节点"""
    node = get_node_config_by_id(node_id)

    if not node:
        return jsonify({"error": "节点不存在"}), 404

    if node.get('status') != 'online':
        return jsonify({"error": "节点离线"}), 503

    node_url = f"http://{node['ip']}:{node.get('port', 5000)}/api/disks"

    try:
        resp = requests.get(node_url, timeout=10)
        return jsonify(resp.json()), resp.status_code

    except requests.exceptions.Timeout:
        return jsonify({"error": "节点响应超时"}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "无法连接到节点"}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==================== 跨节点EC配置 ====================

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

    nodes = json.loads(row[4]) if row[4] else []
    total_disks = sum(len(n.get('disks', [])) for n in nodes)

    config = {
        'id': row[0],
        'name': row[1],
        'k': row[2],
        'm': row[3],
        'nodes': nodes,
        'totalDisks': total_disks,
        'status': row[5],
        'created_at': row[6]
    }

    return jsonify({'success': True, 'config': config})


@ec_bp.route('/api/cross_ec_config', methods=['POST'])
@login_required
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



    total_disks = sum(len(n.get('disks', [])) for n in nodes)
    if total_disks < k + m:
        return jsonify({'error': f'总磁盘数({total_disks})必须 >= k+m({k + m})'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE cross_ec_config SET status = 'inactive'")

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
@login_required
@admin_required
def delete_cross_ec_config():
    """删除跨节点EC配置"""
    delete_shards = request.args.get('delete_shards', 'false').lower() == 'true'

    conn = get_db_connection()
    cursor = conn.cursor()

    deleted_shards = 0
    shard_errors = []
    pending_nodes = []

    # 如果需要删除分片，先收集所有分片信息并删除
    if delete_shards:
        # 获取所有节点状态
        cursor.execute('SELECT node_id, ip, port, status FROM nodes')
        nodes_map = {}
        for row in cursor.fetchall():
            nodes_map[str(row[0])] = {'ip': row[1], 'port': row[2], 'status': row[3]}

        cursor.execute('SELECT filename, disks FROM cross_ec_files')
        files = cursor.fetchall()

        # 收集离线节点需要删除的分片
        offline_shards = {}  # { node_id: [{ filename, shard_index, disk }, ...] }

        for filename, disks_json in files:
            try:
                disks = json.loads(disks_json) if disks_json else []
                for i, disk_info in enumerate(disks):
                    if not isinstance(disk_info, dict):
                        continue

                    node_id = str(disk_info.get('node_id') or disk_info.get('nodeId') or '')
                    node_ip = disk_info.get('ip')
                    node_port = disk_info.get('port')
                    disk = disk_info.get('disk')

                    if not disk:
                        continue

                    # 检查节点状态
                    node_info = nodes_map.get(node_id)
                    if node_info:
                        node_ip = node_info['ip']
                        node_port = node_info['port']
                        is_online = node_info['status'] == 'online'
                    else:
                        is_online = False

                    if not is_online:
                        # 节点离线，收集待处理任务
                        if node_id not in offline_shards:
                            offline_shards[node_id] = []
                        offline_shards[node_id].append({
                            'filename': filename,
                            'shard_index': i,
                            'disk': disk
                        })
                        continue

                    if not node_ip or not node_port:
                        continue

                    # 节点在线，立即删除
                    try:
                        resp = requests.delete(
                            f"http://{node_ip}:{node_port}/api/ec_shard",
                            params={
                                'filename': filename,
                                'shard_index': i,
                                'disk': disk
                            },
                            headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                            timeout=5
                        )
                        if resp.status_code == 200:
                            deleted_shards += 1
                    except Exception as e:
                        # 删除失败，加入离线待处理
                        if node_id not in offline_shards:
                            offline_shards[node_id] = []
                        offline_shards[node_id].append({
                            'filename': filename,
                            'shard_index': i,
                            'disk': disk
                        })
                        shard_errors.append(f"{filename}[{i}]: {str(e)}")
            except Exception as e:
                shard_errors.append(f"{filename}: {str(e)}")

        # 为离线节点创建待处理任务
        for node_id, shards in offline_shards.items():
            if shards:
                pending_nodes.append(node_id)
                cursor.execute('''
                    INSERT INTO pending_tasks (task_type, node_id, params)
                    VALUES (?, ?, ?)
                ''', ('delete_ec_shards', node_id, json.dumps({
                    'shards': shards
                })))

    # 1. 删除配置（标记为deleted）
    cursor.execute("UPDATE cross_ec_config SET status = 'deleted'")

    # 2. 清理文件记录表
    cursor.execute("DELETE FROM cross_ec_files")

    conn.commit()
    conn.close()

    result = {
        'success': True,
        'message': '跨节点EC配置已删除'
    }

    if delete_shards:
        result['deleted_shards'] = deleted_shards
        if shard_errors:
            result['shard_errors'] = shard_errors[:10]
            result['message'] += f'，已删除{deleted_shards}个分片，{len(shard_errors)}个失败'
        else:
            result['message'] += f'，已删除{deleted_shards}个分片'

        if pending_nodes:
            result['pending_nodes'] = pending_nodes
            result['message'] += f'，{len(pending_nodes)}个离线节点将在上线后删除'

    return jsonify(result)


# ==================== EC状态监控 ====================

@ec_bp.route('/api/ec_status', methods=['GET'])
@login_required
def get_ec_status():
    """获取所有EC配置的状态"""
    conn = get_db_connection()
    cursor = conn.cursor()

    result = {
        'cross_ec': None,
        'single_ec_nodes': []
    }

    # 获取跨节点EC状态
    cursor.execute('''
        SELECT id, name, k, m, nodes, status, created_at 
        FROM cross_ec_config 
        WHERE status = 'active'
        ORDER BY created_at DESC
        LIMIT 1
    ''')
    row = cursor.fetchone()
    if row:
        nodes_data = json.loads(row[4])
        total_disks = sum(len(n.get('disks', [])) for n in nodes_data)
        result['cross_ec'] = {
            'id': row[0],
            'name': row[1],
            'k': row[2],
            'm': row[3],
            'nodes': nodes_data,
            'total_disks': total_disks,
            'status': row[5],
            'created_at': row[6],
            'health': 'healthy'
        }

    # 获取所有节点的单节点EC状态
    cursor.execute('SELECT node_id, ip, port, name FROM nodes')
    nodes = cursor.fetchall()

    for node in nodes:
        node_id, ip, port, name = node
        try:
            response = requests.get(
                f"http://{ip}:{port}/api/ec_config",
                headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                timeout=3
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('config') and (data['config'].get('scheme') or data['config'].get('k')):
                    result['single_ec_nodes'].append({
                        'node_id': node_id,
                        'node_name': name,
                        'ip': ip,
                        'config': data['config'],
                        'health': 'healthy',
                        'online': True
                    })
        except:
            pass

    conn.close()
    return jsonify({'success': True, 'data': result})


# ==================== EC文件管理 ====================

@ec_bp.route('/api/ec_files', methods=['GET'])
@login_required
def get_ec_files():
    """获取跨节点EC池中的文件列表（含健康状态）"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 获取在线节点
    online_nodes = {}
    cursor.execute('SELECT node_id, ip, port FROM nodes WHERE status = ?', ('online',))
    for r in cursor.fetchall():
        online_nodes[str(r[0])] = {'ip': r[1], 'port': r[2]}

    cursor.execute('SELECT filename, size, k, m, sha256, created_at, disks FROM cross_ec_files')
    rows = cursor.fetchall()
    conn.close()

    files = []
    for row in rows:
        filename, size, k, m, sha256, ctime, disks_json = row

        # 计算健康状态
        health_status = 'healthy'
        available_shards = 0
        total_shards = k + m

        if disks_json:
            disks = json.loads(disks_json) if isinstance(disks_json, str) else disks_json
            for idx, disk_info in enumerate(disks[:total_shards]):
                if not isinstance(disk_info, dict):
                    continue
                node_id = str(disk_info.get('node_id') or disk_info.get('nodeId') or '')
                shard_path = disk_info.get('path', '')

                if node_id in online_nodes and shard_path:
                    try:
                        resp = requests.get(
                            f"http://{online_nodes[node_id]['ip']}:{online_nodes[node_id]['port']}/api/file_exists",
                            params={'path': shard_path},
                            headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                            timeout=3
                        )
                        if resp.status_code == 200 and resp.json().get('exists'):
                            available_shards += 1
                    except:
                        pass

            missing = total_shards - available_shards
            if missing == 0:
                health_status = 'healthy'
            elif missing <= m:
                health_status = 'at_risk'
            else:
                health_status = 'corrupted'

        files.append({
            'name': filename,
            'size': size,
            'k': k,
            'm': m,
            'sha256': sha256,
            'ctime': ctime,
            'source': 'cross',
            'sourceName': '跨节点EC',
            'health': health_status,
            'availableShards': available_shards,
            'totalShards': total_shards
        })

    return jsonify({'success': True, 'files': files})


@ec_bp.route('/api/nodes/<node_id>/proxy/ec_files', methods=['GET'])
@login_required
def proxy_node_ec_files(node_id):
    """代理获取节点EC文件列表"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT ip, port FROM nodes WHERE node_id = ?', (node_id,))
    node = cursor.fetchone()
    conn.close()

    if not node:
        return jsonify({'error': '节点不存在'}), 404

    ip, port = node

    try:
        response = requests.get(
            f"http://{ip}:{port}/api/ec_files",
            headers={'X-NAS-Secret': NAS_SHARED_SECRET},
            timeout=10
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({'error': f'获取EC文件列表失败: {str(e)}'}), 500
@ec_bp.route('/api/ec_upload', methods=['POST'])
@login_required
@admin_required
def upload_ec_file():
    """上传文件到EC池"""
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400

    file = request.files['file']
    target = request.form.get('target', 'cross')

    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    if target == 'cross':
        # ==================== 跨节点EC上传 ====================
        cursor.execute('''
            SELECT k, m, nodes FROM cross_ec_config 
            WHERE status = 'active' LIMIT 1
        ''')
        config = cursor.fetchone()
        if not config:
            conn.close()
            return jsonify({'error': '未配置跨节点EC'}), 400

        k, m, nodes_json = config
        nodes = json.loads(nodes_json)

        # 收集所有磁盘信息
        all_disks = []
        for node in nodes:
            node_id = node.get('node_id')
            cursor.execute('SELECT ip, port FROM nodes WHERE node_id = ?', (node_id,))
            node_info = cursor.fetchone()
            if node_info:
                for disk in node.get('disks', []):
                    # 兼容新旧格式：disk 可能是字符串 'F:' 或对象 { mount: 'F:', serial: 'xxx' }
                    disk_mount = disk if isinstance(disk, str) else disk.get('mount', disk)
                    all_disks.append({
                        'node_id': node_id,
                        'ip': node_info[0],
                        'port': node_info[1],
                        'disk': disk_mount
                    })

        if len(all_disks) < k + m:
            conn.close()
            return jsonify({'error': f'磁盘数量不足，需要{k+m}个，只有{len(all_disks)}个'}), 400

        try:
            # 读取文件
            data = file.read()
            filename = file.filename
            file_sha = hashlib.sha256(data).hexdigest()
            original_size = len(data)

            print(f"[CROSS_EC] 开始编码文件: {filename}, 大小: {original_size}, k={k}, m={m}")

            # RS编码
            shards = rs_encode(data, k, m)
            shard_size = len(shards[0]) if shards else 0

            print(f"[CROSS_EC] 编码完成，分片数: {len(shards)}, 分片大小: {shard_size}")

            meta = {
                'k': k, 'm': m,
                'shard_size': shard_size,
                'original_size': original_size,
                'sha256': file_sha
            }

            # 分发分片到各节点
            used_disks = []
            for i, disk_info in enumerate(all_disks[:k + m]):
                shard_data = shards[i]
                print(f"[CROSS_EC] 发送分片 {i} 到 {disk_info['node_id']}:{disk_info['disk']}")

                resp = requests.post(
                    f"http://{disk_info['ip']}:{disk_info['port']}/api/ec_shard",
                    json={
                        'filename': filename,
                        'shard_index': i,
                        'shard_data': shard_data.hex(),
                        'disk': disk_info['disk'],
                        'meta': meta
                    },
                    headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                    timeout=60
                )
                if resp.status_code != 200:
                    raise Exception(f"节点{disk_info['node_id']}存储分片失败: {resp.text}")

                resp_data = resp.json()
                used_disks.append({
                    'node_id': disk_info['node_id'],
                    'ip': disk_info['ip'],
                    'port': disk_info['port'],
                    'disk': disk_info['disk'],
                    'path': resp_data.get('path', '')  # 从节点响应获取分片路径
                })

            # 保存文件索引
            cursor.execute('''
                INSERT OR REPLACE INTO cross_ec_files 
                (filename, size, k, m, shard_size, sha256, disks, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (filename, original_size, k, m, shard_size, file_sha, json.dumps(used_disks)))
            conn.commit()
            conn.close()

            print(f"[CROSS_EC] 文件上传成功: {filename}")

            return jsonify({
                'success': True,
                'message': f'文件 {filename} 已上传到跨节点EC池',
                'name': filename
            })

        except Exception as e:
            conn.close()
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'上传失败: {str(e)}'}), 500

    else:
        # ==================== 单节点EC上传 - 转发到客户端 ====================
        cursor.execute('SELECT ip, port FROM nodes WHERE node_id = ?', (target,))
        node = cursor.fetchone()
        if not node:
            conn.close()
            return jsonify({'error': '节点不存在'}), 404

        ip, port = node
        conn.close()

        try:
            file.seek(0)
            files = {'file': (file.filename, file.stream, file.content_type)}
            response = requests.post(
                f"http://{ip}:{port}/api/ec_upload",
                files=files,
                headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                timeout=60
            )

            if response.status_code == 200:
                return jsonify({'success': True, 'message': '文件已上传到节点EC池'})
            else:
                return jsonify({'error': response.json().get('error', '上传失败')}), 500
        except Exception as e:
            return jsonify({'error': f'上传失败: {str(e)}'}), 500

@ec_bp.route('/api/ec_export_all', methods=['GET'])
@login_required
def export_all_cross_ec():
    """一键导出所有跨节点EC文件"""
    import zipfile

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT filename, size, k, m, shard_size, disks FROM cross_ec_files')
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return jsonify({'error': '没有文件可导出'}), 400

    try:
        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for row in rows:
                filename, original_size, k, m, shard_size, disks_json = row
                disks = json.loads(disks_json)

                try:
                    print(f"[CROSS_EC_EXPORT] 开始导出: {filename}")

                    # 从各节点收集分片
                    shards = [None] * (k + m)

                    for i, disk_info in enumerate(disks[:k + m]):
                        try:
                            resp = requests.get(
                                f"http://{disk_info['ip']}:{disk_info['port']}/api/ec_shard",
                                params={
                                    'filename': filename,
                                    'shard_index': i,
                                    'disk': disk_info['disk']
                                },
                                headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                                timeout=10
                            )

                            if resp.status_code == 200:
                                data = resp.json()
                                shards[i] = bytes.fromhex(data['shard_data'])
                                print(f"[CROSS_EC_EXPORT] 获取分片 {i} 成功")
                        except Exception as e:
                            print(f"[CROSS_EC_EXPORT] 获取分片失败 {filename} shard {i}: {e}")
                            continue

                    # 检查可用分片数
                    available = sum(1 for s in shards if s is not None)
                    print(f"[CROSS_EC_EXPORT] 可用分片: {available}/{k}")

                    if available >= k:
                        decoded = rs_decode(shards, k, m, shard_size, original_size)
                        zf.writestr(filename, decoded)
                        print(f"[CROSS_EC_EXPORT] 已导出: {filename}")
                    else:
                        print(f"[CROSS_EC_EXPORT] 跳过(分片不足 {available}/{k}): {filename}")

                except Exception as e:
                    print(f"[CROSS_EC_EXPORT] 导出失败 {filename}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue

        zip_buffer.seek(0)

        return send_file(
            zip_buffer,
            mimetype='application/zip',
            download_name=f'cross_ec_export_{int(time.time())}.zip',
            as_attachment=True
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'导出失败: {str(e)}'}), 500


@ec_bp.route('/api/ec_file', methods=['DELETE'])
@login_required
@admin_required
def delete_cross_ec_file():
    """删除跨节点EC文件"""
    filename = request.args.get('name')
    if not filename:
        return jsonify({'error': '缺少文件名'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT disks, k, m FROM cross_ec_files WHERE filename = ?', (filename,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({'error': '文件不存在'}), 404

    disks_json, k, m = row
    disks = json.loads(disks_json)

    # 删除各节点上的分片
    for i, disk_info in enumerate(disks[:k + m]):
        try:
            requests.delete(
                f"http://{disk_info['ip']}:{disk_info['port']}/api/ec_shard",
                params={
                    'filename': filename,
                    'shard_index': i,
                    'disk': disk_info['disk']
                },
                headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                timeout=10
            )
        except Exception as e:
            print(f"[CROSS_EC] 删除分片失败 {filename} shard {i}: {e}")

    # 从数据库删除记录
    cursor.execute('DELETE FROM cross_ec_files WHERE filename = ?', (filename,))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': '文件已删除'})



@ec_bp.route('/api/ec_download', methods=['GET'])
@login_required
def download_cross_ec_file():
    """下载跨节点EC文件"""
    filename = request.args.get('name')
    if not filename:
        return jsonify({'error': '缺少文件名'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT size, k, m, shard_size, disks FROM cross_ec_files WHERE filename = ?', (filename,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({'error': '文件不存在'}), 404

    original_size, k, m, shard_size, disks_json = row
    disks = json.loads(disks_json)

    # 收集分片
    shards = [None] * (k + m)
    for i, disk_info in enumerate(disks[:k + m]):
        try:
            resp = requests.get(
                f"http://{disk_info['ip']}:{disk_info['port']}/api/ec_shard",
                params={'filename': filename, 'shard_index': i, 'disk': disk_info['disk']},
                headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                timeout=10
            )
            if resp.status_code == 200:
                shards[i] = bytes.fromhex(resp.json()['shard_data'])
        except:
            continue

    available = sum(1 for s in shards if s is not None)
    if available < k:
        return jsonify({'error': f'分片不足，需要{k}个，只有{available}个'}), 500

    # 解码
    decoded = rs_decode(shards, k, m, shard_size, original_size)

    return send_file(
        BytesIO(decoded),
        download_name=filename,
        as_attachment=True
    )


# ==================== 跨节点EC扩展功能 ====================

@ec_bp.route('/api/cross_ec_config/add_disk', methods=['POST'])
@login_required
@admin_required
def add_disk_to_cross_ec():
    """添加磁盘到跨节点EC池"""
    data = request.json
    node_id = data.get('node_id')
    new_disks = data.get('disks', [])

    if not node_id or not new_disks:
        return jsonify({'error': '缺少节点ID或磁盘列表'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # 获取当前配置
    cursor.execute('''
        SELECT id, k, m, nodes FROM cross_ec_config 
        WHERE status = 'active' ORDER BY created_at DESC LIMIT 1
    ''')
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({'error': '没有活跃的跨节点EC配置'}), 404

    config_id, k, m, nodes_json = row
    nodes = json.loads(nodes_json)

    # 获取节点信息 - 修改：name 改成 node_id
    cursor.execute('SELECT ip, port, node_id FROM nodes WHERE node_id = ?', (node_id,))
    node_row = cursor.fetchone()
    if not node_row:
        conn.close()
        return jsonify({'error': '节点不存在'}), 404

    node_ip, node_port, node_name = node_row  # node_name 实际上就是 node_id

    # 查找或创建节点条目
    node_entry = None
    for n in nodes:
        if n.get('node_id') == node_id:
            node_entry = n
            break

    if node_entry:
        # 已有该节点，添加新磁盘
        # 兼容新旧格式：提取现有磁盘的 mount 点
        existing_mounts = set()
        for d in node_entry.get('disks', []):
            mount = d if isinstance(d, str) else d.get('mount', d)
            existing_mounts.add(mount)

        for disk in new_disks:
            disk_mount = disk if isinstance(disk, str) else disk.get('mount', disk)
            if disk_mount not in existing_mounts:
                node_entry['disks'].append(disk)
    else:
        # 新节点
        nodes.append({
            'node_id': node_id,
            'nodeName': node_name,
            'ip': node_ip,
            'disks': new_disks
        })

    # 更新数据库
    cursor.execute('''
        UPDATE cross_ec_config SET nodes = ?, updated_at = datetime('now')
        WHERE id = ?
    ''', (json.dumps(nodes), config_id))

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': '磁盘添加成功'})

@ec_bp.route('/api/cross_ec_config/check_shards', methods=['GET'])
@login_required
def cross_ec_check_shards():
    """检测跨节点EC丢失的分片"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 获取EC配置
        cursor.execute('SELECT k, m, nodes FROM cross_ec_config WHERE status = ?', ('active',))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'error': '未配置跨节点EC'}), 404

        k, m = row[0], row[1]

        # 获取在线节点
        online_nodes = {}
        cursor.execute('SELECT node_id, ip, port FROM nodes WHERE status = ?', ('online',))
        for r in cursor.fetchall():
            online_nodes[str(r[0])] = {'ip': r[1], 'port': r[2]}

        # 获取所有EC文件
        cursor.execute('SELECT filename, size, disks FROM cross_ec_files')
        files = cursor.fetchall()
        conn.close()

        lost_shards = []

        for filename, size, disks_json in files:
            if not disks_json:
                continue

            disks = json.loads(disks_json) if isinstance(disks_json, str) else disks_json
            if not isinstance(disks, list):
                continue

            file_lost = []
            available_count = 0

            for idx, disk_info in enumerate(disks):
                if not isinstance(disk_info, dict):
                    continue

                node_id = str(disk_info.get('node_id') or disk_info.get('nodeId') or '')
                shard_path = disk_info.get('path', '')

                # 检查节点是否在线
                if node_id not in online_nodes:
                    file_lost.append({
                        'index': idx,
                        'node_id': node_id,
                        'path': shard_path,
                        'reason': '节点离线'
                    })
                    continue

                # 检查分片文件是否存在
                node_conn = online_nodes[node_id]
                try:
                    resp = requests.get(
                        f"http://{node_conn['ip']}:{node_conn['port']}/api/file_exists",
                        params={'path': shard_path},
                        headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                        timeout=5
                    )
                    if resp.status_code == 200 and resp.json().get('exists'):
                        available_count += 1
                    else:
                        file_lost.append({
                            'index': idx,
                            'node_id': node_id,
                            'path': shard_path,
                            'reason': '分片不存在'
                        })
                except Exception as e:
                    file_lost.append({
                        'index': idx,
                        'node_id': node_id,
                        'path': shard_path,
                        'reason': f'检查失败: {str(e)}'
                    })

            # 有丢失的分片才加入列表
            if file_lost:
                lost_shards.append({
                    'filename': filename,
                    'size': size,
                    'total_shards': len(disks),
                    'available_shards': available_count,
                    'lost': file_lost,
                    'can_rebuild': available_count >= k,
                    'k': k,
                    'm': m
                })

        return jsonify({
            'success': True,
            'lost_shards': lost_shards,
            'total_files_with_loss': len(lost_shards)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@ec_bp.route('/api/cross_ec_config/rebuild_shard', methods=['POST'])
@login_required
@admin_required
def cross_ec_rebuild_shard():
    """重建跨节点EC分片 - 读取现有分片→解码→重新编码→写回所有磁盘"""
    try:
        data = request.json
        filename = data.get('filename')

        if not filename:
            return jsonify({'error': '缺少文件名'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # 获取文件信息
        cursor.execute('SELECT filename, size, k, m, shard_size, sha256, disks FROM cross_ec_files WHERE filename = ?', (filename,))
        file_row = cursor.fetchone()
        if not file_row:
            conn.close()
            return jsonify({'error': '文件不存在'}), 404

        original_size = file_row[1]
        file_k = file_row[2]
        file_m = file_row[3]
        shard_size = file_row[4]
        file_sha256 = file_row[5]
        disks_json = file_row[6]

        disks = json.loads(disks_json) if isinstance(disks_json, str) else disks_json

        # 获取在线节点
        online_nodes = {}
        cursor.execute('SELECT node_id, ip, port FROM nodes WHERE status = ?', ('online',))
        for r in cursor.fetchall():
            online_nodes[str(r[0])] = {'ip': r[1], 'port': r[2]}

        conn.close()

        # 辅助函数：生成默认分片路径
        def get_shard_path(disk_info, idx):
            path = disk_info.get('path', '')
            if path:
                return path
            # path为空时，使用默认路径
            disk = disk_info.get('disk', '')
            if disk:
                return os.path.join(disk, 'cross_encoded', f'{filename}.blk_{idx}')
            return ''

        # 1. 收集现有分片
        shards = [None] * (file_k + file_m)
        for idx, disk_info in enumerate(disks):
            if not isinstance(disk_info, dict):
                continue

            node_id = str(disk_info.get('node_id') or disk_info.get('nodeId') or '')
            shard_path = get_shard_path(disk_info, idx)

            if node_id not in online_nodes or not shard_path:
                continue

            node_conn = online_nodes[node_id]
            try:
                resp = requests.get(
                    f"http://{node_conn['ip']}:{node_conn['port']}/api/read_shard",
                    params={'path': shard_path},
                    headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                    timeout=30
                )
                if resp.status_code == 200:
                    shard_data = bytes.fromhex(resp.json()['shard_data'])
                    shards[idx] = shard_data
            except:
                continue

        # 检查是否有足够的分片
        available = sum(1 for s in shards if s is not None)
        if available < file_k:
            return jsonify({'error': f'分片不足，需要{file_k}个，只有{available}个，无法重建'}), 400

        # 2. 解码还原原文件
        try:
            decoded_data = rs_decode(shards, file_k, file_m, shard_size, original_size)
        except Exception as e:
            return jsonify({'error': f'解码失败: {str(e)}'}), 500

        # 验证SHA256
        if file_sha256:
            actual_sha256 = hashlib.sha256(decoded_data).hexdigest()
            if actual_sha256 != file_sha256:
                return jsonify({'error': 'SHA256校验失败，数据可能已损坏'}), 500

        # 3. 重新编码
        try:
            new_shards = rs_encode(decoded_data, file_k, file_m)
        except Exception as e:
            return jsonify({'error': f'重新编码失败: {str(e)}'}), 500

        # 4. 写回所有磁盘
        write_success = 0
        write_errors = []
        updated_disks = []  # 用于更新数据库

        for idx, disk_info in enumerate(disks):
            if not isinstance(disk_info, dict):
                updated_disks.append(disk_info)
                continue

            node_id = str(disk_info.get('node_id') or disk_info.get('nodeId') or '')
            disk = disk_info.get('disk', '')
            shard_path = get_shard_path(disk_info, idx)

            if node_id not in online_nodes:
                write_errors.append(f'节点{node_id}离线')
                updated_disks.append(disk_info)
                continue

            if not shard_path:
                write_errors.append(f'分片{idx}路径为空')
                updated_disks.append(disk_info)
                continue

            node_conn = online_nodes[node_id]
            try:
                resp = requests.post(
                    f"http://{node_conn['ip']}:{node_conn['port']}/api/write_shard",
                    json={
                        'path': shard_path,
                        'shard_data': new_shards[idx].hex(),
                        'meta': {
                            'k': file_k,
                            'm': file_m,
                            'shard_size': shard_size,
                            'original_size': original_size,
                            'sha256': file_sha256
                        }
                    },
                    headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                    timeout=30
                )
                if resp.status_code == 200:
                    write_success += 1
                    # 更新disk_info的path
                    updated_disk_info = dict(disk_info)
                    updated_disk_info['path'] = shard_path
                    updated_disks.append(updated_disk_info)
                else:
                    write_errors.append(f'节点{node_id}写入失败: {resp.text}')
                    updated_disks.append(disk_info)
            except Exception as e:
                write_errors.append(f'节点{node_id}写入异常: {str(e)}')
                updated_disks.append(disk_info)

        # 5. 更新数据库中的disks信息（补全path）
        if write_success > 0:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE cross_ec_files SET disks = ? WHERE filename = ?',
                          (json.dumps(updated_disks), filename))
            conn.commit()
            conn.close()

        return jsonify({
            'success': True,
            'filename': filename,
            'write_success': write_success,
            'write_total': len(disks),
            'errors': write_errors if write_errors else None
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@ec_bp.route('/api/cross_ec_export', methods=['POST'])
@login_required
def export_cross_ec_to_node():
    """导出跨节点EC文件到指定节点磁盘"""
    data = request.json
    filename = data.get('filename')
    target_node = data.get('target_node')
    target_disk = data.get('target_disk')
    target_path = data.get('target_path', 'ec_export')

    if not filename or not target_node or not target_disk:
        return jsonify({'error': '缺少必要参数'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # 获取文件信息
    cursor.execute('SELECT size, k, m, shard_size, disks FROM cross_ec_files WHERE filename = ?', (filename,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({'error': '文件不存在'}), 404

    original_size, k, m, shard_size, disks_json = row
    disks = json.loads(disks_json)

    # 获取目标节点信息
    cursor.execute('SELECT ip, port FROM nodes WHERE node_id = ?', (target_node,))
    node_row = cursor.fetchone()

    if not node_row:
        conn.close()
        return jsonify({'error': '目标节点不存在'}), 404

    target_ip, target_port = node_row
    conn.close()

    # 收集分片
    shards = [None] * (k + m)
    for i, disk_info in enumerate(disks[:k + m]):
        try:
            resp = requests.get(
                f"http://{disk_info['ip']}:{disk_info['port']}/api/ec_shard",
                params={
                    'filename': filename,
                    'shard_index': i,
                    'disk': disk_info['disk']
                },
                headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                timeout=10
            )
            if resp.status_code == 200:
                shards[i] = bytes.fromhex(resp.json()['shard_data'])
        except:
            continue

    available = sum(1 for s in shards if s is not None)
    if available < k:
        return jsonify({'error': f'分片不足，需要{k}个，只有{available}个'}), 500

    # 解码还原
    try:
        decoded = rs_decode(shards, k, m, shard_size, original_size)
    except Exception as e:
        return jsonify({'error': f'解码失败: {str(e)}'}), 500

    # 发送到目标节点保存
    try:
        # 构建完整路径
        full_path = os.path.join(target_disk, target_path, filename)

        resp = requests.post(
            f"http://{target_ip}:{target_port}/api/write_file",
            json={
                'path': full_path,
                'data': decoded.hex(),
                'create_dirs': True
            },
            headers={'X-NAS-Secret': NAS_SHARED_SECRET},
            timeout=120
        )

        if resp.status_code == 200:
            return jsonify({
                'success': True,
                'message': f'文件已导出到 {full_path}',
                'path': full_path
            })
        else:
            return jsonify({'error': f'写入失败: {resp.text}'}), 500
    except Exception as e:
        return jsonify({'error': f'导出失败: {str(e)}'}), 500


@ec_bp.route('/api/cross_ec_config/health_check', methods=['GET'])
@login_required
def cross_ec_health_check():
    """跨节点EC健康检查"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 获取EC配置
        cursor.execute('SELECT k, m, nodes FROM cross_ec_config WHERE status = ?', ('active',))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'error': '未配置跨节点EC'}), 404

        k = row[0]
        m = row[1]
        nodes = json.loads(row[2]) if row[2] else []

        # 获取所有在线节点
        online_nodes = {}
        cursor.execute('SELECT node_id, ip, port FROM nodes WHERE status = ?', ('online',))
        for r in cursor.fetchall():
            online_nodes[str(r[0])] = {'ip': r[1], 'port': r[2]}

        def normalize_disk(d):
            """统一磁盘格式"""
            return d.upper().replace('\\', '/').rstrip('/') if d else ''

        # 构建在线磁盘集合
        online_disks = set()
        for node_info in nodes:
            node_id = str(node_info.get('node_id') or node_info.get('nodeId') or '')
            if node_id not in online_nodes:
                continue

            node_conn = online_nodes[node_id]
            try:
                url = f"http://{node_conn['ip']}:{node_conn['port']}/api/disks"
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    actual_disks = resp.json()
                    actual_mounts = set()
                    for d in actual_disks:
                        mount = normalize_disk(d.get('mount') or d.get('path') or '')
                        actual_mounts.add(mount)

                    for disk in node_info.get('disks', []):
                        disk_mount = disk if isinstance(disk, str) else disk.get('mount', disk)
                        normalized_disk_mount = normalize_disk(disk_mount)
                        if normalized_disk_mount in actual_mounts:
                            online_disks.add(f"{node_id}:{normalized_disk_mount}")
            except Exception as e:
                print(f"获取节点 {node_id} 磁盘失败: {e}")
                continue

        # 获取所有EC文件
        cursor.execute('SELECT filename, size, disks FROM cross_ec_files')
        files = cursor.fetchall()
        conn.close()

        healthy_files = 0
        at_risk_files = 0
        corrupted_files = 0
        file_details = []

        for filename, size, disks_json in files:
            try:
                if not disks_json:
                    corrupted_files += 1
                    file_details.append({
                        'filename': filename,
                        'size': size or 0,
                        'status': 'corrupted',
                        'online_shards': 0,
                        'total_shards': 0,
                        'reason': 'disks_json为空'
                    })
                    continue

                disks = json.loads(disks_json) if isinstance(disks_json, str) else disks_json

                if not isinstance(disks, list):
                    corrupted_files += 1
                    file_details.append({
                        'filename': filename,
                        'size': size or 0,
                        'status': 'corrupted',
                        'online_shards': 0,
                        'total_shards': 0,
                        'reason': 'disks不是列表'
                    })
                    continue

                # 统计在线的分片数
                online_shards = 0
                total_shards = len(disks)
                shards_detail = []

                for idx, disk_info in enumerate(disks):
                    # 处理非dict情况
                    if not isinstance(disk_info, dict):
                        shards_detail.append({
                            'index': idx,
                            'exists': False,
                            'reason': f'分片信息格式错误: {type(disk_info).__name__}'
                        })
                        continue

                    node_id = str(disk_info.get('node_id') or disk_info.get('nodeId') or '')
                    disk = disk_info.get('disk', '')
                    shard_path = disk_info.get('path', '')

                    normalized_key = f"{node_id}:{normalize_disk(disk)}"

                    # 简化磁盘在线检查
                    disk_online = normalized_key in online_disks

                    if not disk_online:
                        shards_detail.append({
                            'index': idx, 'node_id': node_id, 'disk': disk,
                            'path': shard_path, 'exists': False, 'reason': '节点或磁盘离线'
                        })
                        continue

                    # 磁盘在线，再检查分片文件是否真实存在
                    node_conn = online_nodes.get(node_id)
                    shard_exists = False
                    reason = ''

                    if node_conn and shard_path:
                        try:
                            check_url = f"http://{node_conn['ip']}:{node_conn['port']}/api/file_exists"
                            resp = requests.get(
                                check_url,
                                params={'path': shard_path},
                                headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                                timeout=5
                            )
                            if resp.status_code == 200:
                                shard_exists = resp.json().get('exists', False)
                                if not shard_exists:
                                    reason = '分片文件不存在'
                            else:
                                reason = f'检查失败: {resp.status_code}'
                        except Exception as e:
                            reason = f'请求异常: {str(e)}'
                    else:
                        reason = '缺少路径信息'

                    if shard_exists:
                        online_shards += 1

                    shards_detail.append({
                        'index': idx, 'node_id': node_id, 'disk': disk,
                        'path': shard_path, 'exists': shard_exists, 'reason': reason
                    })

                # 判断文件状态
                if online_shards >= k + m:
                    healthy_files += 1
                    status = 'healthy'
                elif online_shards >= k:
                    at_risk_files += 1
                    status = 'at_risk'
                else:
                    corrupted_files += 1
                    status = 'corrupted'

                file_details.append({
                    'filename': filename,
                    'size': size or 0,
                    'status': status,
                    'online_shards': online_shards,
                    'total_shards': total_shards,
                    'shards': shards_detail
                })

            except Exception as e:
                print(f"检查文件 {filename} 失败: {e}")
                import traceback
                traceback.print_exc()
                corrupted_files += 1
                file_details.append({
                    'filename': filename,
                    'size': size if size else 0,
                    'status': 'corrupted',
                    'online_shards': 0,
                    'total_shards': 0,
                    'error': str(e)
                })

        return jsonify({
            'success': True,
            'total_files': len(files),
            'healthy_files': healthy_files,
            'at_risk_files': at_risk_files,
            'corrupted_files': corrupted_files,
            'online_disks': len(online_disks),
            'total_disks': sum(len(n.get('disks', [])) for n in nodes),
            'k': k,
            'm': m,
            'files': file_details
        })

    except Exception as e:
        print(f"健康检查失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@ec_bp.route('/api/nodes/<node_id>/proxy/batch_delete', methods=['POST'])
@login_required
def proxy_node_batch_delete(node_id):
    """代理批量删除请求到节点"""
    node = get_node_config_by_id(node_id)
    if not node:
        return jsonify({'error': '节点不存在'}), 404

    try:
        resp = requests.post(
            f"http://{node['ip']}:{node.get('port', 5000)}/api/batch_delete",
            json=request.json,
            headers={'X-NAS-Secret': NAS_SHARED_SECRET},
            timeout=30
        )
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({'error': f'删除失败: {str(e)}'}), 500


@ec_bp.route('/api/cross_ec_config/replace_disk', methods=['POST'])
@login_required
@admin_required
def replace_disk_in_cross_ec():
    """替换跨节点EC池中的离线磁盘"""
    data = request.json
    old_node_id = data.get('old_node_id')
    old_disk = data.get('old_disk')
    new_node_id = data.get('new_node_id')
    new_disk = data.get('new_disk')

    if not all([old_node_id, old_disk, new_node_id, new_disk]):
        return jsonify({'error': '缺少必要参数'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1. 获取当前EC配置
        cursor.execute('''
            SELECT id, k, m, nodes FROM cross_ec_config 
            WHERE status = 'active' ORDER BY created_at DESC LIMIT 1
        ''')
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'error': '没有活跃的跨节点EC配置'}), 404

        config_id, k, m, nodes_json = row
        nodes = json.loads(nodes_json)

        # 2. 获取新节点信息
        cursor.execute('SELECT ip, port, node_id FROM nodes WHERE node_id = ?', (new_node_id,))
        new_node_row = cursor.fetchone()
        if not new_node_row:
            conn.close()
            return jsonify({'error': '新节点不存在'}), 404
        new_ip, new_port, _ = new_node_row

        # 3. 在EC配置中替换磁盘
        old_disk_normalized = old_disk.upper().replace('\\', '/').rstrip('/')
        new_disk_normalized = new_disk.upper().replace('\\', '/').rstrip('/')

        replaced_in_config = False
        for node_info in nodes:
            if str(node_info.get('node_id') or node_info.get('nodeId')) == str(old_node_id):
                for i, d in enumerate(node_info.get('disks', [])):
                    disk_mount = d if isinstance(d, str) else d.get('mount', d)
                    if disk_mount.upper().replace('\\', '/').rstrip('/') == old_disk_normalized:
                        # 替换为新磁盘
                        node_info['disks'][i] = new_disk
                        replaced_in_config = True
                        break

        # 如果旧磁盘不在原节点，可能需要添加新节点的磁盘
        if not replaced_in_config:
            # 查找新节点
            new_node_entry = None
            for n in nodes:
                if str(n.get('node_id') or n.get('nodeId')) == str(new_node_id):
                    new_node_entry = n
                    break

            if new_node_entry:
                new_node_entry['disks'].append(new_disk)
            else:
                nodes.append({
                    'node_id': new_node_id,
                    'nodeName': new_node_id,
                    'ip': new_ip,
                    'disks': [new_disk]
                })

        # 4. 更新EC配置
        cursor.execute('''
            UPDATE cross_ec_config SET nodes = ?, updated_at = datetime('now')
            WHERE id = ?
        ''', (json.dumps(nodes), config_id))

        # 5. 更新所有文件的分片位置
        cursor.execute('SELECT filename, disks FROM cross_ec_files')
        files = cursor.fetchall()

        updated_files = 0
        for filename, disks_json in files:
            disks = json.loads(disks_json) if isinstance(disks_json, str) else disks_json
            modified = False

            for i, disk_info in enumerate(disks):
                if not isinstance(disk_info, dict):
                    continue

                d_node = str(disk_info.get('node_id') or disk_info.get('nodeId') or '')
                d_disk = (disk_info.get('disk') or '').upper().replace('\\', '/').rstrip('/')

                if d_node == str(old_node_id) and d_disk == old_disk_normalized:
                    # 替换分片信息
                    disks[i] = {
                        'node_id': new_node_id,
                        'ip': new_ip,
                        'port': new_port,
                        'disk': new_disk,
                        'path': os.path.join(new_disk, 'cross_encoded', f'{filename}.blk_{i}')
                    }
                    modified = True

            if modified:
                cursor.execute('UPDATE cross_ec_files SET disks = ? WHERE filename = ?',
                               (json.dumps(disks), filename))
                updated_files += 1

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'磁盘替换成功，已更新 {updated_files} 个文件的分片信息',
            'updated_files': updated_files
        })

    except Exception as e:
        conn.close()
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

