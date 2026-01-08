# cross_pool_routes.py - 跨节点存储池路由
from flask import Blueprint, request, jsonify, session
import sqlite3
import json
import requests
import random
from datetime import datetime
from auth import login_required, admin_required
from common import get_db_connection
from config import NAS_SHARED_SECRET

cross_pool_bp = Blueprint('cross_pool', __name__)


def init_cross_pool_tables():
    """初始化跨节点存储池相关表"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 跨节点存储池配置表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cross_node_pools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            display_name TEXT,
            strategy TEXT DEFAULT 'largest_free',
            disks TEXT,
            round_robin_index INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 文件元数据表（记录文件存在哪个节点哪个磁盘）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cross_pool_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pool_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            filepath TEXT,
            node_id TEXT NOT NULL,
            node_ip TEXT,
            node_port INTEGER,
            disk_path TEXT NOT NULL,
            real_path TEXT,
            file_size INTEGER DEFAULT 0,
            created_by TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pool_id) REFERENCES cross_node_pools(id)
        )
    ''')

    # 跨节点池逻辑卷表
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS cross_pool_volumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pool_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                display_name TEXT,
                icon TEXT DEFAULT '📁',
                strategy TEXT DEFAULT 'largest_free',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pool_id) REFERENCES cross_node_pools(id),
                UNIQUE(pool_id, name)
            )
        ''')
    # 待处理任务表（用于离线节点的延迟操作）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,
            node_id TEXT NOT NULL,
            params TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            retry_count INTEGER DEFAULT 0,
            last_error TEXT,
            completed_at DATETIME
        )
    ''')
    conn.commit()
    conn.close()
    print("[跨节点池] 数据表初始化完成")


# ========== 池管理 API ==========

@cross_pool_bp.route('/api/cross-pools', methods=['GET'])
@login_required
def list_pools():
    """列出所有跨节点池"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, name, display_name, strategy, disks, status, created_at
        FROM cross_node_pools
        WHERE status != 'deleted'
        ORDER BY created_at DESC
    ''')
    rows = cursor.fetchall()
    conn.close()

    pools = []
    for row in rows:
        pools.append({
            'id': row[0],
            'name': row[1],
            'display_name': row[2],
            'strategy': row[3],
            'disks': json.loads(row[4]) if row[4] else [],
            'status': row[5],
            'created_at': row[6]
        })

    return jsonify(pools)


@cross_pool_bp.route('/api/cross-pools', methods=['POST'])
@login_required
@admin_required
def create_pool():
    """创建跨节点池"""
    data = request.json
    name = data.get('name')
    display_name = data.get('display_name', name)
    strategy = data.get('strategy', 'largest_free')
    disks = data.get('disks', [])

    if not name:
        return jsonify({'error': '池名称不能为空'}), 400

    # 验证策略
    valid_strategies = ['largest_free', 'round_robin', 'balanced']
    if strategy not in valid_strategies:
        return jsonify({'error': f'无效的策略，可选: {valid_strategies}'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # 检查重名
    # 检查重名（包括已删除的）
    cursor.execute('SELECT id, status FROM cross_node_pools WHERE name = ?', (name,))
    existing = cursor.fetchone()
    if existing:
        if existing[1] == 'deleted':
            # 复用已删除的记录
            cursor.execute('''
                    UPDATE cross_node_pools 
                    SET display_name = ?, strategy = ?, disks = ?, status = 'active', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (display_name, strategy, json.dumps(disks), existing[0]))
            pool_id = existing[0]
        else:
            conn.close()
            return jsonify({'error': '池名称已存在'}), 400
    else:
        cursor.execute('''
                INSERT INTO cross_node_pools (name, display_name, strategy, disks)
                VALUES (?, ?, ?, ?)
            ''', (name, display_name, strategy, json.dumps(disks)))
        pool_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return jsonify({'success': True, 'id': pool_id, 'message': '跨节点池创建成功'})


@cross_pool_bp.route('/api/cross-pools/<int:pool_id>', methods=['GET'])
@login_required
def get_pool(pool_id):
    """获取单个池详情"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, name, display_name, strategy, disks, status, created_at
        FROM cross_node_pools
        WHERE id = ? AND status != 'deleted'
    ''', (pool_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({'error': '池不存在'}), 404

    return jsonify({
        'id': row[0],
        'name': row[1],
        'display_name': row[2],
        'strategy': row[3],
        'disks': json.loads(row[4]) if row[4] else [],
        'status': row[5],
        'created_at': row[6]
    })


@cross_pool_bp.route('/api/cross-pools/<int:pool_id>', methods=['PUT'])
@login_required
@admin_required
def update_pool(pool_id):
    """更新跨节点池"""
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()

    # 检查池是否存在
    cursor.execute('SELECT id FROM cross_node_pools WHERE id = ? AND status != "deleted"', (pool_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': '池不存在'}), 404

    updates = []
    params = []

    if 'display_name' in data:
        updates.append('display_name = ?')
        params.append(data['display_name'])

    if 'strategy' in data:
        valid_strategies = ['largest_free', 'round_robin', 'balanced']
        if data['strategy'] not in valid_strategies:
            conn.close()
            return jsonify({'error': f'无效的策略'}), 400
        updates.append('strategy = ?')
        params.append(data['strategy'])

    if 'disks' in data:
        updates.append('disks = ?')
        params.append(json.dumps(data['disks']))

    if updates:
        updates.append('updated_at = CURRENT_TIMESTAMP')
        params.append(pool_id)
        cursor.execute(f'''
            UPDATE cross_node_pools SET {', '.join(updates)} WHERE id = ?
        ''', params)
        conn.commit()

    conn.close()
    return jsonify({'success': True, 'message': '更新成功'})


@cross_pool_bp.route('/api/cross-pools/<int:pool_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_pool(pool_id):
    """删除跨节点池"""
    keep_files = request.args.get('keep_files', 'true').lower() == 'true'

    conn = get_db_connection()
    cursor = conn.cursor()

    # 获取池信息
    cursor.execute('SELECT id, name, disks FROM cross_node_pools WHERE id = ? AND status != "deleted"', (pool_id,))
    pool = cursor.fetchone()
    if not pool:
        conn.close()
        return jsonify({'error': '池不存在'}), 404

    pool_name = pool[1]
    disks = json.loads(pool[2]) if pool[2] else []

    # 获取所有节点状态
    cursor.execute('SELECT node_id, ip, port, status FROM nodes')
    nodes_map = {row[0]: {'ip': row[1], 'port': row[2], 'status': row[3]} for row in cursor.fetchall()}

    # 如果不保留文件，删除实际文件
    deleted_results = []
    pending_nodes = []

    if not keep_files and disks:
        for disk in disks:
            node_id = disk.get('nodeId')
            disk_path = disk.get('disk')
            node_info = nodes_map.get(node_id)

            if not node_info:
                continue

            if node_info['status'] != 'online':
                # 节点离线，记录待处理任务
                pending_nodes.append(node_id)
                cursor.execute('''
                    INSERT INTO pending_tasks (task_type, node_id, params)
                    VALUES (?, ?, ?)
                ''', ('delete_pool_files', node_id, json.dumps({
                    'pool_id': pool_id,
                    'pool_name': pool_name,
                    'disk_path': disk_path,
                    'target_dir': f"{disk_path}/cross_pool"
                })))
                continue

            # 节点在线，立即删除
            try:
                resp = requests.post(
                    f"http://{node_info['ip']}:{node_info['port']}/api/internal/delete-dir",
                    json={'path': f"{disk_path}/cross_pool"},
                    headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                    timeout=60
                )
                deleted_results.append({
                    'node_id': node_id,
                    'success': resp.status_code == 200,
                    'message': resp.json().get('message', '') if resp.status_code == 200 else resp.text
                })
            except Exception as e:
                # 删除失败也记录待处理任务
                cursor.execute('''
                    INSERT INTO pending_tasks (task_type, node_id, params, last_error)
                    VALUES (?, ?, ?, ?)
                ''', ('delete_pool_files', node_id, json.dumps({
                    'pool_id': pool_id,
                    'pool_name': pool_name,
                    'disk_path': disk_path,
                    'target_dir': f"{disk_path}/cross_pool"
                }), str(e)))
                deleted_results.append({
                    'node_id': node_id,
                    'success': False,
                    'message': str(e),
                    'pending': True
                })

    # 删除文件索引
    cursor.execute('DELETE FROM cross_pool_files WHERE pool_id = ?', (pool_id,))

    # 删除逻辑卷
    cursor.execute('DELETE FROM cross_pool_volumes WHERE pool_id = ?', (pool_id,))

    # 标记池为已删除
    cursor.execute('UPDATE cross_node_pools SET status = "deleted", updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                   (pool_id,))

    conn.commit()
    conn.close()

    result = {'success': True, 'message': '池已删除'}
    if pending_nodes:
        result['pending_nodes'] = pending_nodes
        result['message'] = f'池已删除，{len(pending_nodes)} 个离线节点的文件将在上线后清理'

    return jsonify(result)

# ========== 池状态/统计 ==========

@cross_pool_bp.route('/api/cross-pools/<int:pool_id>/stats', methods=['GET'])
@login_required
def pool_stats(pool_id):
    """获取池的统计信息"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 获取池配置
    cursor.execute('SELECT disks FROM cross_node_pools WHERE id = ? AND status != "deleted"', (pool_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '池不存在'}), 404

    disks = json.loads(row[0]) if row[0] else []

    # 获取文件统计
    cursor.execute('SELECT COUNT(*), COALESCE(SUM(file_size), 0) FROM cross_pool_files WHERE pool_id = ?', (pool_id,))
    file_count, total_size = cursor.fetchone()

    conn.close()

    return jsonify({
        'disk_count': len(disks),
        'file_count': file_count,
        'total_size': total_size
    })


@cross_pool_bp.route('/api/cross-pools/<int:pool_id>/disk-status', methods=['GET'])
@login_required
def pool_disk_status(pool_id):
    """获取池内各磁盘的实时状态（向节点查询）"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT disks FROM cross_node_pools WHERE id = ? AND status != "deleted"', (pool_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '池不存在'}), 404

    disks = json.loads(row[0]) if row[0] else []
    conn.close()

    # 按节点分组查询
    disk_status = []
    nodes_cache = {}

    for disk_info in disks:
        node_id = disk_info.get('nodeId')
        disk_path = disk_info.get('disk')

        # 获取节点信息（缓存）
        if node_id not in nodes_cache:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT ip, port FROM nodes WHERE node_id = ?', (node_id,))
            node = cursor.fetchone()
            conn.close()
            nodes_cache[node_id] = node

        node = nodes_cache.get(node_id)
        if not node:
            disk_status.append({
                **disk_info,
                'status': 'error',
                'error': '节点不存在'
            })
            continue

        # 向节点查询磁盘状态
        try:
            resp = requests.get(
                f"http://{node[0]}:{node[1]}/api/disk-info",
                params={'path': disk_path},
                headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                timeout=5
            )
            if resp.status_code == 200:
                info = resp.json()
                disk_status.append({
                    **disk_info,
                    'status': 'online',
                    'total': info.get('total', 0),
                    'used': info.get('used', 0),
                    'free': info.get('free', 0)
                })
            else:
                disk_status.append({
                    **disk_info,
                    'status': 'error',
                    'error': '查询失败'
                })
        except Exception as e:
            disk_status.append({
                **disk_info,
                'status': 'offline',
                'error': str(e)
            })

    return jsonify({'disks': disk_status})


# ========== 分配策略 ==========

def select_disk_by_strategy(pool_id):
    """根据策略选择目标磁盘"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT strategy, disks, round_robin_index
        FROM cross_node_pools
        WHERE id = ? AND status = 'active'
    ''', (pool_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None, '池不存在或未激活'

    strategy = row[0]
    disks = json.loads(row[1]) if row[1] else []
    rr_index = row[2] or 0

    if not disks:
        conn.close()
        return None, '池中没有磁盘'

    selected = None

    if strategy == 'largest_free':
        # 最大剩余空间优先：查询各磁盘可用空间，选最大的
        max_free = -1
        for disk_info in disks:
            try:
                node_id = disk_info.get('nodeId')
                cursor.execute('SELECT ip, port FROM nodes WHERE node_id = ?', (node_id,))
                node = cursor.fetchone()
                if not node:
                    continue

                resp = requests.get(
                    f"http://{node[0]}:{node[1]}/api/disk-info",
                    params={'path': disk_info.get('disk')},
                    headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                    timeout=3
                )
                if resp.status_code == 200:
                    free = resp.json().get('free', 0)
                    if free > max_free:
                        max_free = free
                        selected = disk_info
            except:
                continue

        if not selected:
            selected = disks[0]  # 降级：选第一个

    elif strategy == 'round_robin':
        # 轮询分配
        selected = disks[rr_index % len(disks)]
        cursor.execute(
            'UPDATE cross_node_pools SET round_robin_index = ? WHERE id = ?',
            ((rr_index + 1) % len(disks), pool_id)
        )
        conn.commit()

    elif strategy == 'balanced':
        # 按剩余空间比例加权随机
        weights = []
        for disk_info in disks:
            try:
                node_id = disk_info.get('nodeId')
                cursor.execute('SELECT ip, port FROM nodes WHERE node_id = ?', (node_id,))
                node = cursor.fetchone()
                if not node:
                    weights.append(1)
                    continue

                resp = requests.get(
                    f"http://{node[0]}:{node[1]}/api/disk-info",
                    params={'path': disk_info.get('disk')},
                    headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                    timeout=3
                )
                if resp.status_code == 200:
                    weights.append(max(resp.json().get('free', 1), 1))
                else:
                    weights.append(1)
            except:
                weights.append(1)

        selected = random.choices(disks, weights=weights, k=1)[0]

    else:
        selected = disks[0]

    conn.close()
    return selected, None


# ========== 上传/下载指路 ==========

@cross_pool_bp.route('/api/cross-pools/<int:pool_id>/upload-request', methods=['POST'])
@login_required
def request_upload(pool_id):
    """请求上传文件 - 返回目标节点信息"""
    data = request.json
    filename = data.get('filename')
    file_size = data.get('size', 0)
    subpath = data.get('subpath', '')

    if not filename:
        return jsonify({'error': '缺少文件名'}), 400

    # 根据策略选择目标磁盘
    disk_info, error = select_disk_by_strategy(pool_id)
    if error:
        return jsonify({'error': error}), 400

    node_id = disk_info.get('nodeId')
    disk_path = disk_info.get('disk')

    # 获取节点连接信息
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT ip, port FROM nodes WHERE node_id = ?', (node_id,))
    node = cursor.fetchone()
    conn.close()

    if not node:
        return jsonify({'error': '目标节点不存在'}), 404

    # 生成上传路径
    upload_path = f"{disk_path}/cross_pool/{subpath}".replace('//', '/')

    return jsonify({
        'success': True,
        'node_id': node_id,
        'node_ip': node[0],
        'node_port': node[1],
        'disk_path': disk_path,
        'upload_path': upload_path,
        'filename': filename
    })


@cross_pool_bp.route('/api/cross-pools/<int:pool_id>/upload-complete', methods=['POST'])
@login_required
def upload_complete(pool_id):
    """上传完成回调 - 记录文件元数据"""
    data = request.json
    filename = data.get('filename')
    node_id = data.get('node_id')
    node_ip = data.get('node_ip')
    node_port = data.get('node_port')
    disk_path = data.get('disk_path')
    real_path = data.get('real_path')
    file_size = data.get('file_size', 0)
    filepath = data.get('filepath', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO cross_pool_files 
        (pool_id, filename, filepath, node_id, node_ip, node_port, disk_path, real_path, file_size, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (pool_id, filename, filepath, node_id, node_ip, node_port, disk_path, real_path, file_size, session.get('username')))

    file_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'file_id': file_id})


@cross_pool_bp.route('/api/cross-pools/<int:pool_id>/download-request', methods=['GET'])
@login_required
def request_download(pool_id):
    """请求下载文件 - 返回文件所在节点"""
    file_id = request.args.get('file_id')
    filepath = request.args.get('filepath')

    conn = get_db_connection()
    cursor = conn.cursor()

    if file_id:
        cursor.execute('''
            SELECT node_id, node_ip, node_port, disk_path, real_path, filename
            FROM cross_pool_files
            WHERE id = ? AND pool_id = ?
        ''', (file_id, pool_id))
    elif filepath:
        cursor.execute('''
            SELECT node_id, node_ip, node_port, disk_path, real_path, filename
            FROM cross_pool_files
            WHERE filepath = ? AND pool_id = ?
        ''', (filepath, pool_id))
    else:
        conn.close()
        return jsonify({'error': '请指定 file_id 或 filepath'}), 400

    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({'error': '文件不存在'}), 404

    return jsonify({
        'success': True,
        'node_id': row[0],
        'node_ip': row[1],
        'node_port': row[2],
        'disk_path': row[3],
        'real_path': row[4],
        'filename': row[5]
    })


# ========== 文件列表 ==========

@cross_pool_bp.route('/api/cross-pools/<int:pool_id>/files', methods=['GET'])
@login_required
def list_files(pool_id):
    """列出池中的文件"""
    subpath = request.args.get('subpath', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    if subpath:
        cursor.execute('''
            SELECT id, filename, filepath, node_id, disk_path, file_size, created_at, created_by
            FROM cross_pool_files
            WHERE pool_id = ? AND (filepath LIKE ? OR filepath LIKE ?)
            ORDER BY created_at DESC
        ''', (pool_id, f'{subpath}/%', f'{subpath}\\%'))
    else:
        cursor.execute('''
            SELECT id, filename, filepath, node_id, disk_path, file_size, created_at, created_by
            FROM cross_pool_files
            WHERE pool_id = ?
            ORDER BY created_at DESC
        ''', (pool_id,))

    rows = cursor.fetchall()
    conn.close()

    files = []
    for row in rows:
        files.append({
            'id': row[0],
            'filename': row[1],
            'filepath': row[2],
            'node_id': row[3],
            'disk_path': row[4],
            'file_size': row[5],
            'created_at': row[6],
            'created_by': row[7]
        })

    return jsonify({'files': files})


@cross_pool_bp.route('/api/cross-pools/<int:pool_id>/files/<int:file_id>', methods=['DELETE'])
@login_required
def delete_file(pool_id, file_id):
    """删除文件"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 获取文件信息
    cursor.execute('''
        SELECT node_id, real_path FROM cross_pool_files
        WHERE id = ? AND pool_id = ?
    ''', (file_id, pool_id))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({'error': '文件不存在'}), 404

    node_id, real_path = row

    # 获取节点信息
    cursor.execute('SELECT ip, port FROM nodes WHERE node_id = ?', (node_id,))
    node = cursor.fetchone()

    if node:
        # 请求节点删除实际文件
        try:
            requests.post(
                f"http://{node[0]}:{node[1]}/api/internal/delete",
                json={'path': real_path},
                headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                timeout=10
            )
        except Exception as e:
            print(f"[跨节点池] 删除节点文件失败: {e}")

    # 删除元数据
    cursor.execute('DELETE FROM cross_pool_files WHERE id = ?', (file_id,))
    conn.commit()
    conn.close()

    return jsonify({'success': True})


# ========== 逻辑卷管理 ==========

@cross_pool_bp.route('/api/cross-pools/<int:pool_id>/volumes', methods=['GET'])
@login_required
def list_volumes(pool_id):
    """列出池的逻辑卷"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 检查池是否存在
    cursor.execute('SELECT id FROM cross_node_pools WHERE id = ? AND status != "deleted"', (pool_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': '池不存在'}), 404

    cursor.execute('''
        SELECT name, display_name, icon, strategy, created_at
        FROM cross_pool_volumes
        WHERE pool_id = ?
        ORDER BY created_at
    ''', (pool_id,))
    rows = cursor.fetchall()
    conn.close()

    volumes = [{
        'name': row[0],
        'display_name': row[1],
        'icon': row[2],
        'strategy': row[3],
        'created_at': row[4]
    } for row in rows]

    return jsonify(volumes)


@cross_pool_bp.route('/api/cross-pools/<int:pool_id>/volumes', methods=['POST'])
@login_required
@admin_required
def create_volume(pool_id):
    """创建逻辑卷"""
    data = request.json
    name = data.get('name')
    display_name = data.get('display_name', name)
    icon = data.get('icon', '📁')
    strategy = data.get('strategy', 'largest_free')

    if not name:
        return jsonify({'error': '卷名称不能为空'}), 400

    valid_strategies = ['largest_free', 'round_robin', 'balanced']
    if strategy not in valid_strategies:
        return jsonify({'error': '无效的策略'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # 检查池是否存在
    cursor.execute('SELECT id FROM cross_node_pools WHERE id = ? AND status != "deleted"', (pool_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': '池不存在'}), 404

    # 检查重名
    cursor.execute('SELECT name FROM cross_pool_volumes WHERE pool_id = ? AND name = ?', (pool_id, name))
    if cursor.fetchone():
        conn.close()
        return jsonify({'error': '卷名称已存在'}), 400

    cursor.execute('''
        INSERT INTO cross_pool_volumes (pool_id, name, display_name, icon, strategy)
        VALUES (?, ?, ?, ?, ?)
    ''', (pool_id, name, display_name, icon, strategy))

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': '逻辑卷创建成功'})


@cross_pool_bp.route('/api/cross-pools/<int:pool_id>/volumes/<volume_name>', methods=['PATCH'])
@login_required
@admin_required
def update_volume(pool_id, volume_name):
    """更新逻辑卷"""
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()

    # 检查卷是否存在
    cursor.execute('SELECT name FROM cross_pool_volumes WHERE pool_id = ? AND name = ?', (pool_id, volume_name))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': '逻辑卷不存在'}), 404

    updates = []
    params = []

    if 'display_name' in data:
        updates.append('display_name = ?')
        params.append(data['display_name'])

    if 'icon' in data:
        updates.append('icon = ?')
        params.append(data['icon'])

    if 'strategy' in data:
        valid_strategies = ['largest_free', 'round_robin', 'balanced']
        if data['strategy'] not in valid_strategies:
            conn.close()
            return jsonify({'error': '无效的策略'}), 400
        updates.append('strategy = ?')
        params.append(data['strategy'])

    if updates:
        params.extend([pool_id, volume_name])
        cursor.execute(f'''
            UPDATE cross_pool_volumes SET {', '.join(updates)}
            WHERE pool_id = ? AND name = ?
        ''', params)
        conn.commit()

    conn.close()
    return jsonify({'success': True, 'message': '更新成功'})


@cross_pool_bp.route('/api/cross-pools/<int:pool_id>/volumes/<volume_name>', methods=['DELETE'])
@login_required
@admin_required
def delete_volume(pool_id, volume_name):
    """删除逻辑卷"""
    delete_files = request.args.get('delete_files', 'false').lower() == 'true'

    conn = get_db_connection()
    cursor = conn.cursor()

    # 获取池信息
    cursor.execute('SELECT disks FROM cross_node_pools WHERE id = ? AND status != "deleted"', (pool_id,))
    pool_row = cursor.fetchone()
    if not pool_row:
        conn.close()
        return jsonify({'error': '池不存在'}), 404

    disks = json.loads(pool_row[0]) if pool_row[0] else []

    # 检查是否有文件记录
    cursor.execute('''
        SELECT COUNT(*) FROM cross_pool_files 
        WHERE pool_id = ? AND filepath LIKE ?
    ''', (pool_id, f'{volume_name}/%'))
    file_count = cursor.fetchone()[0]

    # 删除实际文件（如果需要）
    deleted_results = []
    pending_nodes = []

    if delete_files and disks:
        # 获取节点信息
        cursor.execute('SELECT node_id, ip, port, status FROM nodes')
        nodes_map = {row[0]: {'ip': row[1], 'port': row[2], 'status': row[3]} for row in cursor.fetchall()}

        for disk in disks:
            node_id = disk.get('nodeId')
            disk_path = disk.get('disk')
            node_info = nodes_map.get(node_id)

            if not node_info:
                continue

            target_path = f"{disk_path}/cross_pool/{volume_name}"

            if node_info['status'] != 'online':
                # 节点离线，记录待处理任务
                pending_nodes.append(node_id)
                cursor.execute('''
                    INSERT INTO pending_tasks (task_type, node_id, params)
                    VALUES (?, ?, ?)
                ''', ('delete_volume_files', node_id, json.dumps({
                    'pool_id': pool_id,
                    'volume_name': volume_name,
                    'target_path': target_path
                })))
                continue

            # 节点在线，立即删除
            try:
                resp = requests.post(
                    f"http://{node_info['ip']}:{node_info['port']}/api/internal/delete-dir",
                    json={'path': target_path},
                    headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                    timeout=30
                )
                deleted_results.append({
                    'node_id': node_id,
                    'path': target_path,
                    'success': resp.status_code == 200
                })
            except Exception as e:
                # 删除失败，记录待处理任务
                cursor.execute('''
                    INSERT INTO pending_tasks (task_type, node_id, params, last_error)
                    VALUES (?, ?, ?, ?)
                ''', ('delete_volume_files', node_id, json.dumps({
                    'pool_id': pool_id,
                    'volume_name': volume_name,
                    'target_path': target_path
                }), str(e)))
                deleted_results.append({
                    'node_id': node_id,
                    'success': False,
                    'error': str(e),
                    'pending': True
                })

    # 删除文件记录
    cursor.execute('''
        DELETE FROM cross_pool_files 
        WHERE pool_id = ? AND filepath LIKE ?
    ''', (pool_id, f'{volume_name}/%'))

    # 删除卷记录
    cursor.execute('DELETE FROM cross_pool_volumes WHERE pool_id = ? AND name = ?', (pool_id, volume_name))
    conn.commit()
    conn.close()

    result = {'success': True, 'message': '删除成功'}
    if delete_files:
        result['deleted_results'] = deleted_results
    if file_count > 0:
        result['deleted_file_records'] = file_count
    if pending_nodes:
        result['pending_nodes'] = pending_nodes
        result['message'] += f'，{len(pending_nodes)}个离线节点将在上线后删除'

    return jsonify(result)

@cross_pool_bp.route('/api/cross-pools/<int:pool_id>/upload', methods=['POST'])
@login_required
def upload_file(pool_id):
    """直接上传文件到跨节点池"""
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400

    file = request.files['file']
    subpath = request.form.get('subpath', '')

    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400

    # 根据策略选择目标磁盘
    disk_info, error = select_disk_by_strategy(pool_id)
    if error:
        return jsonify({'error': error}), 400

    node_id = disk_info.get('nodeId')
    disk_path = disk_info.get('disk')

    # 获取节点连接信息
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT ip, port FROM nodes WHERE node_id = ?', (node_id,))
    node = cursor.fetchone()

    if not node:
        conn.close()
        return jsonify({'error': '目标节点不存在'}), 404

    node_ip, node_port = node[0], node[1]

    # 生成存储路径
    upload_dir = f"cross_pool/{subpath}".strip('/')
    target_path = f"{disk_path}/{upload_dir}".replace('//', '/')
    real_path = f"{target_path}/{file.filename}".replace('//', '/')

    # 读取文件内容
    file_data = file.read()
    file_size = len(file_data)

    # 代理上传到目标节点
    try:
        resp = requests.post(
            f"http://{node_ip}:{node_port}/api/internal/upload",
            files={'file': (file.filename, file_data)},
            data={'path': target_path},
            headers={'X-NAS-Secret': NAS_SHARED_SECRET},
            timeout=120
        )
        if resp.status_code != 200:
            conn.close()
            return jsonify({'error': f'上传到节点失败: {resp.text}'}), 500
    except Exception as e:
        conn.close()
        return jsonify({'error': f'连接节点失败: {str(e)}'}), 500

    # 记录文件元数据
    filepath = f"{subpath}/{file.filename}".strip('/')
    cursor.execute('''
        INSERT INTO cross_pool_files 
        (pool_id, filename, filepath, node_id, node_ip, node_port, disk_path, real_path, file_size, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (pool_id, file.filename, filepath, node_id, node_ip, node_port, disk_path, real_path, file_size, session.get('username')))

    file_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'file_id': file_id, 'message': '上传成功'})


@cross_pool_bp.route('/api/cross-pools/<int:pool_id>/download', methods=['GET'])
@login_required
def download_file(pool_id):
    """下载跨节点池文件"""
    filepath = request.args.get('filepath')
    file_id = request.args.get('file_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    if file_id:
        cursor.execute('''
            SELECT node_id, real_path, filename FROM cross_pool_files
            WHERE id = ? AND pool_id = ?
        ''', (file_id, pool_id))
    elif filepath:
        cursor.execute('''
            SELECT node_id, real_path, filename FROM cross_pool_files
            WHERE filepath = ? AND pool_id = ?
        ''', (filepath, pool_id))
    else:
        conn.close()
        return jsonify({'error': '请指定 file_id 或 filepath'}), 400

    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '文件不存在'}), 404

    node_id, real_path, filename = row

    # 获取节点信息
    cursor.execute('SELECT ip, port FROM nodes WHERE node_id = ?', (node_id,))
    node = cursor.fetchone()
    conn.close()

    if not node:
        return jsonify({'error': '节点不存在'}), 404

    # 从节点获取文件
    try:
        resp = requests.get(
            f"http://{node[0]}:{node[1]}/api/internal/download",
            params={'path': real_path},
            headers={'X-NAS-Secret': NAS_SHARED_SECRET},
            timeout=120,
            stream=True
        )
        if resp.status_code != 200:
            return jsonify({'error': '获取文件失败'}), 500

        from flask import Response
        return Response(
            resp.iter_content(chunk_size=8192),
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': resp.headers.get('Content-Type', 'application/octet-stream')
            }
        )
    except Exception as e:
        return jsonify({'error': f'下载失败: {str(e)}'}), 500


@cross_pool_bp.route('/api/cross-pools/<int:pool_id>/rebuild-index', methods=['POST'])
@login_required
@admin_required
def rebuild_pool_index(pool_id):
    """重建跨节点池索引 - 扫描所有在线磁盘，同步文件索引"""
    import os

    conn = get_db_connection()
    cursor = conn.cursor()

    # 获取池信息
    cursor.execute('SELECT id, name, disks FROM cross_node_pools WHERE id = ? AND status != "deleted"', (pool_id,))
    pool = cursor.fetchone()
    if not pool:
        conn.close()
        return jsonify({'error': '池不存在'}), 404

    pool_name = pool[1]
    disks = json.loads(pool[2]) if pool[2] else []

    if not disks:
        conn.close()
        return jsonify({'error': '池没有配置磁盘'}), 400

    # 获取该池的所有逻辑卷名称
    cursor.execute('SELECT name FROM cross_pool_volumes WHERE pool_id = ?', (pool_id,))
    valid_volumes = set(row[0] for row in cursor.fetchall())

    # 获取所有在线节点
    cursor.execute('SELECT node_id, ip, port, status FROM nodes')
    nodes_map = {row[0]: {'ip': row[1], 'port': row[2], 'status': row[3]} for row in cursor.fetchall()}

    # 获取现有索引
    cursor.execute('SELECT id, filepath, node_id, disk_path, real_path FROM cross_pool_files WHERE pool_id = ?',
                   (pool_id,))
    existing_files = {row[2] + ':' + row[4]: {'id': row[0], 'filepath': row[1], 'node_id': row[2], 'disk_path': row[3],
                                              'real_path': row[4]} for row in cursor.fetchall()}

    added = 0
    removed = 0
    skipped = 0
    errors = 0
    scanned_files = set()
    results = []

    # 遍历每个磁盘
    for disk in disks:
        node_id = disk.get('nodeId')
        disk_path = disk.get('disk')
        node_info = nodes_map.get(node_id)

        if not node_info or node_info['status'] != 'online':
            results.append({'node': node_id, 'disk': disk_path, 'status': 'skipped', 'reason': '节点离线'})
            continue

        node_ip = node_info['ip']
        node_port = node_info['port']

        try:
            resp = requests.get(
                f"http://{node_ip}:{node_port}/api/internal/scan-dir",
                params={'path': f"{disk_path}/cross_pool"},
                headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                timeout=60
            )

            if resp.status_code == 404:
                results.append({'node': node_id, 'disk': disk_path, 'status': 'ok', 'files': 0, 'reason': '目录不存在'})
                continue

            if resp.status_code != 200:
                errors += 1
                results.append(
                    {'node': node_id, 'disk': disk_path, 'status': 'error', 'reason': f'扫描失败: {resp.status_code}'})
                continue

            files_on_disk = resp.json().get('files', [])
            disk_added = 0
            disk_skipped = 0

            for file_info in files_on_disk:
                real_path = file_info.get('path')
                filename = file_info.get('name')
                file_size = file_info.get('size', 0)
                is_dir = file_info.get('is_dir', False)

                if is_dir:
                    continue

                # 从 real_path 提取 filepath
                # 统一路径格式（处理 Windows 和 Linux 路径）
                real_path_normalized = real_path.replace('\\', '/').replace('//', '/')
                disk_path_normalized = disk_path.replace('\\', '/').replace('//', '/')

                # 尝试多种前缀格式
                cross_pool_prefix = f"{disk_path_normalized}/cross_pool/"
                if real_path_normalized.startswith(cross_pool_prefix):
                    filepath = real_path_normalized[len(cross_pool_prefix):]
                elif '/cross_pool/' in real_path_normalized:
                    # 备用方案：直接从 cross_pool/ 后截取
                    filepath = real_path_normalized.split('/cross_pool/', 1)[1]
                else:
                    filepath = filename

                # 检查是否属于有效的逻辑卷
                parts = filepath.split('/')
                volume_name = parts[0] if parts else ''

                # 必须属于某个有效逻辑卷才能添加索引
                if not volume_name or volume_name not in valid_volumes:
                    # 跳过不属于任何现有逻辑卷的文件
                    disk_skipped += 1
                    skipped += 1
                    continue

                file_key = node_id + ':' + real_path
                scanned_files.add(file_key)

                if file_key not in existing_files:
                    cursor.execute('''
                        INSERT INTO cross_pool_files 
                        (pool_id, filename, filepath, node_id, node_ip, node_port, disk_path, real_path, file_size, created_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (pool_id, filename, filepath, node_id, node_ip, node_port, disk_path, real_path, file_size,
                          'system_rebuild'))
                    added += 1
                    disk_added += 1

            results.append({
                'node': node_id,
                'disk': disk_path,
                'status': 'ok',
                'files': len(files_on_disk),
                'added': disk_added,
                'skipped': disk_skipped
            })

        except Exception as e:
            errors += 1
            results.append({'node': node_id, 'disk': disk_path, 'status': 'error', 'reason': str(e)})

    # 清理失效索引
    for file_key, file_info in existing_files.items():
        node_id = file_info['node_id']
        node_info = nodes_map.get(node_id)

        if node_info and node_info['status'] == 'online':
            if file_key not in scanned_files:
                cursor.execute('DELETE FROM cross_pool_files WHERE id = ?', (file_info['id'],))
                removed += 1

    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'added': added,
        'removed': removed,
        'skipped': skipped,
        'errors': errors,
        'results': results
    })

@cross_pool_bp.route('/api/cross-pools/<int:pool_id>/clean-invalid', methods=['POST'])
@login_required
@admin_required
def clean_invalid_index(pool_id):
    """清理失效索引 - 删除指向离线节点/磁盘的索引记录"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 获取池信息
    cursor.execute('SELECT id, disks FROM cross_node_pools WHERE id = ? AND status != "deleted"', (pool_id,))
    pool = cursor.fetchone()
    if not pool:
        conn.close()
        return jsonify({'error': '池不存在'}), 404

    disks = json.loads(pool[1]) if pool[1] else []

    # 构建有效的 node_id:disk_path 组合
    valid_disk_keys = set()
    for disk in disks:
        key = disk.get('nodeId') + ':' + disk.get('disk')
        valid_disk_keys.add(key)

    # 获取所有索引记录
    cursor.execute('SELECT id, node_id, disk_path FROM cross_pool_files WHERE pool_id = ?', (pool_id,))
    files = cursor.fetchall()

    removed = 0
    for file_id, node_id, disk_path in files:
        key = node_id + ':' + disk_path
        if key not in valid_disk_keys:
            cursor.execute('DELETE FROM cross_pool_files WHERE id = ?', (file_id,))
            removed += 1

    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'removed': removed,
        'message': f'已清理 {removed} 条失效索引'
    })


# ========== 待处理任务 ==========

@cross_pool_bp.route('/api/pending-tasks', methods=['GET'])
@login_required
@admin_required
def list_pending_tasks():
    """获取待处理任务列表"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, task_type, node_id, params, created_at, status, retry_count, last_error
        FROM pending_tasks
        WHERE status = 'pending'
        ORDER BY created_at ASC
    ''')

    tasks = []
    for row in cursor.fetchall():
        tasks.append({
            'id': row[0],
            'task_type': row[1],
            'node_id': row[2],
            'params': json.loads(row[3]) if row[3] else {},
            'created_at': row[4],
            'status': row[5],
            'retry_count': row[6],
            'last_error': row[7]
        })

    conn.close()
    return jsonify(tasks)


@cross_pool_bp.route('/api/pending-tasks/process', methods=['POST'])
@login_required
@admin_required
def process_pending_tasks():
    """处理待处理任务（通常在节点上线时调用）"""
    node_id = request.json.get('node_id')  # 可选，指定只处理某个节点的任务

    conn = get_db_connection()
    cursor = conn.cursor()

    # 获取待处理任务
    if node_id:
        cursor.execute('''
            SELECT id, task_type, node_id, params FROM pending_tasks
            WHERE status = 'pending' AND node_id = ?
        ''', (node_id,))
    else:
        cursor.execute('''
            SELECT id, task_type, node_id, params FROM pending_tasks
            WHERE status = 'pending'
        ''')

    tasks = cursor.fetchall()

    # 获取节点信息
    cursor.execute('SELECT node_id, ip, port, status FROM nodes')
    nodes_map = {row[0]: {'ip': row[1], 'port': row[2], 'status': row[3]} for row in cursor.fetchall()}

    results = []

    for task_id, task_type, task_node_id, params_json in tasks:
        params = json.loads(params_json) if params_json else {}
        node_info = nodes_map.get(task_node_id)

        # 检查节点是否在线
        if not node_info or node_info['status'] != 'online':
            results.append({
                'task_id': task_id,
                'success': False,
                'reason': '节点不在线'
            })
            continue

        # 执行任务
        success = False
        error_msg = None

        try:
            if task_type == 'delete_pool_files':
                target_dir = params.get('target_dir')
                resp = requests.post(
                    f"http://{node_info['ip']}:{node_info['port']}/api/internal/delete-dir",
                    json={'path': target_dir},
                    headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                    timeout=60
                )
                success = resp.status_code == 200
                if not success:
                    error_msg = resp.text

            elif task_type == 'delete_volume_files':
                # 删除逻辑卷文件
                target_path = params.get('target_path')
                resp = requests.post(
                    f"http://{node_info['ip']}:{node_info['port']}/api/internal/delete-dir",
                    json={'path': target_path},
                    headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                    timeout=60
                )
                success = resp.status_code == 200
                if not success:
                    error_msg = resp.text

            elif task_type == 'delete_ec_shards':
                # 删除EC分片
                shards = params.get('shards', [])
                success_count = 0
                for shard in shards:
                    try:
                        resp = requests.delete(
                            f"http://{node_info['ip']}:{node_info['port']}/api/ec_shard",
                            params={
                                'filename': shard.get('filename'),
                                'shard_index': shard.get('shard_index'),
                                'disk': shard.get('disk')
                            },
                            headers={'X-NAS-Secret': NAS_SHARED_SECRET},
                            timeout=10
                        )
                        if resp.status_code == 200:
                            success_count += 1
                    except:
                        pass
                success = success_count == len(shards)
                if not success:
                    error_msg = f'删除了 {success_count}/{len(shards)} 个分片'

            else:
                error_msg = f'未知任务类型: {task_type}'
        except Exception as e:
            error_msg = str(e)

        # 更新任务状态
        if success:
            cursor.execute('''
                UPDATE pending_tasks 
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (task_id,))
        else:
            cursor.execute('''
                UPDATE pending_tasks 
                SET retry_count = retry_count + 1, last_error = ?
                WHERE id = ?
            ''', (error_msg, task_id))

        results.append({
            'task_id': task_id,
            'task_type': task_type,
            'node_id': task_node_id,
            'success': success,
            'error': error_msg
        })

    conn.commit()
    conn.close()

    return jsonify({
        'processed': len(results),
        'results': results
    })


@cross_pool_bp.route('/api/pending-tasks/<int:task_id>', methods=['DELETE'])
@login_required
@admin_required
def cancel_pending_task(task_id):
    """取消/删除待处理任务"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM pending_tasks WHERE id = ?', (task_id,))

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': '任务已取消'})