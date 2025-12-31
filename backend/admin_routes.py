# admin_routes.py - 管理员专用路由
from flask import Blueprint, jsonify, request, session
import sqlite3
import re
import os
import uuid
from datetime import datetime
from auth import login_required, admin_required
from common import get_db, get_node_config_by_id
from config import NAS_SHARED_SECRET

admin_bp = Blueprint('admin', __name__)

# 存储访问申请（内存）
access_requests = {}


@admin_bp.route('/api/admin/update-secret', methods=['POST'])
@login_required
@admin_required
def update_shared_secret():
    """更新 NAS 通信密钥"""
    from flask import current_app
    BASE_DIR = current_app.config.get('BASE_DIR')

    data = request.json
    new_secret = data.get('secret')

    if not new_secret:
        return jsonify({'success': False, 'error': '密钥不能为空'}), 400

    if len(new_secret) < 6:
        return jsonify({'success': False, 'error': '密钥长度建议至少6位'}), 400

    try:
        config_path = os.path.join(BASE_DIR, 'config.py')

        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()

        new_content = re.sub(
            r'NAS_SHARED_SECRET\s*=\s*["\'].*?["\']',
            f'NAS_SHARED_SECRET = "{new_secret}"',
            content
        )

        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        global NAS_SHARED_SECRET
        NAS_SHARED_SECRET = new_secret

        print(f"[系统] 通信密钥已由管理员更新")

        return jsonify({
            'success': True,
            'message': '密钥更新成功！请注意：您必须同步更新所有节点的配置，否则它们将无法连接。'
        })

    except Exception as e:
        print(f"[Update Secret Error] {e}")
        return jsonify({'success': False, 'error': f'写入配置文件失败: {str(e)}'}), 500


@admin_bp.route('/api/internal/test-connection', methods=['POST'])
def test_connection():
    """测试连接接口 - 供客户端配置向导使用"""
    try:
        data = request.json
        shared_secret = data.get('shared_secret')

        if shared_secret != NAS_SHARED_SECRET:
            return jsonify({'success': False, 'error': '共享密钥不正确'}), 401

        return jsonify({
            'success': True,
            'message': '连接成功',
            'server_time': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/internal/get-user-permission', methods=['POST'])
def get_user_permission():
    """供客户端查询用户权限"""
    secret = request.headers.get('X-NAS-Secret')
    if secret != NAS_SHARED_SECRET:
        print(f"[WARN] 未授权的权限查询请求")
        return jsonify({"success": False, "message": "未授权的请求"}), 403

    data = request.json
    username = data.get('username')

    if not username:
        return jsonify({"success": False, "message": "缺少用户名"}), 400

    try:
        conn = sqlite3.connect('nas_center.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            'SELECT role, file_permission FROM users WHERE username = ? AND status = "active"',
            (username,)
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            print(f"[AUTH] 查询用户 {username} 权限: {user['file_permission']}")
            return jsonify({
                "success": True,
                "role": user['role'],
                "file_permission": user['file_permission']
            })
        else:
            print(f"[WARN] 用户 {username} 不存在或已禁用")
            return jsonify({"success": False, "message": "用户不存在"}), 404
    except Exception as e:
        print(f"[ERROR] 查询用户权限失败: {e}")
        return jsonify({"success": False, "message": "数据库错误"}), 500


# ========== 白名单管理 API ==========
@admin_bp.route('/api/admin/whitelist', methods=['GET'])
@login_required
@admin_required
def get_whitelist():
    """获取白名单"""
    conn = sqlite3.connect('nas_center.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT w.id, w.user_id, u.username, w.added_at
        FROM whitelist_users w
        JOIN users u ON w.user_id = u.id
    ''')
    whitelist = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"whitelist": whitelist})


@admin_bp.route('/api/admin/whitelist', methods=['POST'])
@login_required
@admin_required
def add_to_whitelist():
    """添加用户到白名单"""
    user_id = request.json.get('user_id')
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO whitelist_users (user_id) VALUES (?)', (user_id,))
        conn.commit()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": "用户已在白名单中"}), 400
    finally:
        conn.close()


@admin_bp.route('/api/admin/whitelist/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def remove_from_whitelist(user_id):
    """从白名单移除用户"""
    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM whitelist_users WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ========== 访问申请管理 API ==========
@admin_bp.route('/api/access-requests', methods=['POST'])
@login_required
def create_access_request():
    """用户申请访问某个节点 - 自动批准模式"""
    data = request.json
    node_id = data.get('node_id')
    permission = data.get('permission', 'readonly')

    if not node_id:
        return jsonify({"success": False, "message": "缺少节点ID"}), 400

    node_config = get_node_config_by_id(node_id)
    if not node_config:
        return jsonify({"success": False, "message": "节点不存在"}), 404

    request_id = str(uuid.uuid4())
    username = session.get('username')
    user_id = session.get('user_id')

    try:
        conn = sqlite3.connect('nas_center.db')
        cursor = conn.cursor()

        cursor.execute(
            'UPDATE users SET file_permission = ? WHERE id = ?',
            (permission, user_id)
        )

        conn.commit()
        conn.close()

        print(f"[自动批准] 用户 {username} 已自动获得节点 {node_config['name']} 的 {permission} 权限")

        return jsonify({
            "success": True,
            "message": f"访问权限已自动开通！您现在可以使用 {permission} 权限访问节点",
            "permission": permission,
            "auto_approved": True
        })

    except Exception as e:
        print(f"[错误] 自动批准失败: {e}")
        return jsonify({
            "success": False,
            "message": f"自动批准失败: {str(e)}"
        }), 500


@admin_bp.route('/api/access-requests', methods=['GET'])
@login_required
def get_access_requests():
    """获取当前用户的访问申请列表"""
    user_id = session['user_id']

    user_requests = [
        req for req in access_requests.values()
        if req['user_id'] == user_id
    ]

    return jsonify({
        "success": True,
        "requests": user_requests
    })


@admin_bp.route('/api/internal/access-approved', methods=['POST'])
def access_approved():
    """接收来自节点的批准通知"""
    secret = request.headers.get('X-NAS-Secret')
    if secret != "your-shared-secret-key":
        return jsonify({"success": False, "message": "未授权的请求"}), 403

    data = request.json
    request_id = data.get('request_id')
    username = data.get('username')
    node_id = data.get('node_id')

    if request_id not in access_requests:
        return jsonify({"success": False, "message": "申请不存在"}), 404

    access_requests[request_id]['status'] = 'approved'
    access_requests[request_id]['approved_at'] = datetime.now().isoformat()

    print(f"[访问申请] 用户 {username} 对节点 {node_id} 的访问申请已被批准")

    return jsonify({
        "success": True,
        "message": "已接收批准通知"
    })


@admin_bp.route('/api/internal/access-rejected', methods=['POST'])
def access_rejected():
    """接收来自节点的拒绝通知"""
    secret = request.headers.get('X-NAS-Secret')
    if secret != "your-shared-secret-key":
        return jsonify({"success": False, "message": "未授权的请求"}), 403

    data = request.json
    request_id = data.get('request_id')
    username = data.get('username')
    node_id = data.get('node_id')
    reason = data.get('reason', '管理员拒绝')

    if request_id not in access_requests:
        return jsonify({"success": False, "message": "申请不存在"}), 404

    access_requests[request_id]['status'] = 'rejected'
    access_requests[request_id]['rejected_at'] = datetime.now().isoformat()
    access_requests[request_id]['reject_reason'] = reason

    print(f"[访问申请] 用户 {username} 对节点 {node_id} 的访问申请已被拒绝: {reason}")

    return jsonify({
        "success": True,
        "message": "已接收拒绝通知"
    })


@admin_bp.route('/api/audit-logs', methods=['GET'])
def get_audit_logs():
    """获取审计日志（简化版）"""
    return jsonify([])