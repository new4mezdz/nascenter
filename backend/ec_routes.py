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
            return jsonify({'error': '获取配置失败'}), 500

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

    config = {
        'id': row[0],
        'name': row[1],
        'k': row[2],
        'm': row[3],
        'nodes': json.loads(row[4]),
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

    if not nodes or len(nodes) < 2:
        return jsonify({'error': '跨节点EC至少需要2个节点'}), 400

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
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE cross_ec_config SET status = 'deleted'")
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': '跨节点EC配置已删除'})


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
    """获取跨节点EC池中的文件列表"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT filename, size, k, m, sha256, created_at FROM cross_ec_files')
    rows = cursor.fetchall()
    conn.close()

    files = [{
        'name': row[0],
        'size': row[1],
        'k': row[2],
        'm': row[3],
        'sha256': row[4],
        'ctime': row[5],
        'source': 'cross',
        'sourceName': '跨节点EC'
    } for row in rows]

    return jsonify({'success': True, 'files': files})


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
                    all_disks.append({
                        'node_id': node_id,
                        'ip': node_info[0],
                        'port': node_info[1],
                        'disk': disk
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

                used_disks.append({
                    'node_id': disk_info['node_id'],
                    'ip': disk_info['ip'],
                    'port': disk_info['port'],
                    'disk': disk_info['disk']
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