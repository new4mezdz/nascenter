# user_routes.py - 用户管理路由
from flask import Blueprint, jsonify, request, session
import sqlite3
import json
import uuid
import os
from auth import login_required, admin_required

user_bp = Blueprint('user', __name__)


@user_bp.route('/api/users', methods=['GET'])
def get_users():
    """获取所有用户"""
    conn = sqlite3.connect('nas_center.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, role, email, node_access, status FROM users')
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()

    for user in users:
        user['node_access'] = json.loads(user['node_access'])

    return jsonify(users)


@user_bp.route('/api/users', methods=['POST'])
def create_user():
    """创建用户"""
    data = request.json
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO users (username, password_hash, role, email)
        VALUES (?, ?, ?, ?)
    ''', (data['username'], data['password'], data['role'], data.get('email', '')))

    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return jsonify({"success": True, "user_id": new_id})


@user_bp.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """更新用户"""
    data = request.json
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE users 
        SET role = ?, email = ?, status = ?, file_permission = ?
        WHERE id = ?
    ''', (
        data['role'],
        data.get('email', ''),
        data.get('status', 'active'),
        data.get('file_permission', 'readonly'),
        user_id
    ))

    conn.commit()
    conn.close()
    return jsonify({"success": True})


@user_bp.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """删除用户（软删除）"""
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET status = "deleted" WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@user_bp.route('/api/users/<int:user_id>/password', methods=['PUT'])
@login_required
def change_password(user_id):
    """修改密码"""
    data = request.json
    new_password = data.get('password')

    if session['user_id'] != user_id and session['role'] != 'admin':
        return jsonify({"error": "无权修改其他用户密码"}), 403

    if not new_password:
        return jsonify({"error": "密码不能为空"}), 400

    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_password, user_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "密码修改成功"})


@user_bp.route('/api/users/<int:user_id>/node-access', methods=['GET'])
def get_user_node_access(user_id):
    """获取用户节点访问权限"""
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()
    cursor.execute('SELECT node_access FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return jsonify(json.loads(row[0]))
    else:
        return jsonify({"error": "用户不存在"}), 404


@user_bp.route('/api/users/<int:user_id>/node-access', methods=['PUT'])
def update_user_node_access(user_id):
    """更新用户节点访问权限"""
    data = request.json
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()

    cursor.execute('UPDATE users SET node_access = ? WHERE id = ?',
                   (json.dumps(data), user_id))

    conn.commit()
    conn.close()
    return jsonify({"success": True})


@user_bp.route('/api/users/<int:user_id>/accessible-nodes', methods=['GET'])
@login_required
def get_user_accessible_nodes(user_id):
    """获取用户可访问的节点列表"""
    from common import load_nodes_config

    if session['user_id'] != user_id and session['role'] != 'admin':
        return jsonify({'error': '无权查看'}), 403

    conn = sqlite3.connect('nas_center.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('SELECT node_access, role FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({'error': '用户不存在'}), 404

    NODES_CONFIG = load_nodes_config()

    if user['role'] == 'admin':
        conn.close()
        return jsonify({
            'type': 'all',
            'nodes': [node['id'] for node in NODES_CONFIG]
        })

    node_access = json.loads(user['node_access'])
    access_type = node_access.get('type', 'all')

    accessible_nodes = []

    if access_type == 'all':
        accessible_nodes = [node['id'] for node in NODES_CONFIG]
    elif access_type == 'groups':
        allowed_groups = node_access.get('allowed_groups', [])
        if allowed_groups:
            placeholders = ','.join('?' * len(allowed_groups))
            cursor.execute(f'''
                SELECT DISTINCT node_id
                FROM node_group_members
                WHERE group_id IN ({placeholders})
            ''', allowed_groups)
            accessible_nodes = [row['node_id'] for row in cursor.fetchall()]
    elif access_type == 'custom':
        accessible_nodes = node_access.get('allowed_nodes', [])

    denied_nodes = node_access.get('denied_nodes', [])
    accessible_nodes = [nid for nid in accessible_nodes if nid not in denied_nodes]

    conn.close()

    return jsonify({
        'type': access_type,
        'nodes': accessible_nodes
    })


@user_bp.route('/api/profile', methods=['GET'])
@login_required
def get_profile():
    """获取当前用户个人资料"""
    user_id = session.get('user_id')
    conn = sqlite3.connect('nas_center.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, email, role, avatar, created_at FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return jsonify(dict(user))
    return jsonify({"error": "用户不存在"}), 404


@user_bp.route('/api/profile', methods=['PUT'])
@login_required
def update_profile():
    """更新当前用户个人资料"""
    user_id = session.get('user_id')
    data = request.json
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET email = ? WHERE id = ?', (data.get('email', ''), user_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@user_bp.route('/api/avatar', methods=['POST'])
@login_required
def upload_avatar():
    """上传用户头像"""
    from flask import current_app
    AVATAR_DIR = current_app.config.get('AVATAR_DIR')

    user_id = session.get('user_id')
    if 'avatar' not in request.files:
        return jsonify({"error": "没有文件"}), 400

    file = request.files['avatar']
    if file.filename == '':
        return jsonify({"error": "未选择文件"}), 400

    allowed_ext = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in allowed_ext:
        return jsonify({"error": "不支持的文件类型"}), 400

    filename = f"{user_id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(AVATAR_DIR, filename)
    file.save(filepath)

    avatar_url = f"/avatars/{filename}"
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET avatar = ? WHERE id = ?', (avatar_url, user_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "avatar": avatar_url})