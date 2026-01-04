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
    conn = get_db_connection()
    cursor = conn.cursor()

    # 检查是否有文件
    cursor.execute('SELECT COUNT(*) FROM cross_pool_files WHERE pool_id = ?', (pool_id,))
    file_count = cursor.fetchone()[0]

    if file_count > 0:
        conn.close()
        return jsonify({'error': f'池中还有 {file_count} 个文件，请先清空'}), 400

    cursor.execute('UPDATE cross_node_pools SET status = "deleted" WHERE id = ?', (pool_id,))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': '删除成功'})


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
            WHERE pool_id = ? AND filepath LIKE ?
            ORDER BY created_at DESC
        ''', (pool_id, f'{subpath}%'))
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
                f"http://{node[0]}:{node[1]}/api/delete",
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
    conn = get_db_connection()
    cursor = conn.cursor()

    # 检查是否有文件
    cursor.execute('''
        SELECT COUNT(*) FROM cross_pool_files 
        WHERE pool_id = ? AND filepath LIKE ?
    ''', (pool_id, f'{volume_name}/%'))
    file_count = cursor.fetchone()[0]

    if file_count > 0:
        conn.close()
        return jsonify({'error': f'卷中还有 {file_count} 个文件，请先清空'}), 400

    cursor.execute('DELETE FROM cross_pool_volumes WHERE pool_id = ? AND name = ?', (pool_id, volume_name))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': '删除成功'})