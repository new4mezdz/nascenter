# auth_routes.py - 登录/认证相关路由
from flask import Blueprint, jsonify, request, session, send_file
import sqlite3
import json
import jwt
import os
from datetime import datetime, timedelta
from auth import login_required
from common import ACCESS_TOKEN_SECRET

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def index():
    """根路由 - 检查登录状态"""
    from flask import current_app
    FRONTEND_DIR = current_app.config.get('FRONTEND_DIR')

    if 'user_id' not in session:
        login_path = os.path.join(FRONTEND_DIR, 'login.html')
        if os.path.exists(login_path):
            return send_file(login_path)
        else:
            return jsonify({"error": "登录页面未找到"}), 404

    html_path = os.path.join(FRONTEND_DIR, '1.html')
    if os.path.exists(html_path):
        return send_file(html_path)
    else:
        return jsonify({"error": "主页面未找到"}), 404


@auth_bp.route('/api/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"success": False, "message": "用户名和密码不能为空"}), 400

    conn = sqlite3.connect('nas_center.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ? AND status = "active"', (username,))
    user = cursor.fetchone()
    conn.close()

    if user and user['password_hash'] == password:
        session.permanent = True
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']

        if user['role'] == 'admin':
            session['file_permission'] = 'fullcontrol'
        elif user['file_permission']:
            session['file_permission'] = user['file_permission']
        else:
            if user['role'] == 'user':
                session['file_permission'] = 'readwrite'
            else:
                session['file_permission'] = 'readonly'

        # 更新最后登录时间
        conn = sqlite3.connect('nas_center.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET last_login = ? WHERE id = ?',
                       (datetime.now().isoformat(), user['id']))
        conn.commit()
        conn.close()

        print(f"✅ 登录成功: {username}, Session ID: {session.get('user_id')}")

        return jsonify({
            "success": True,
            "message": "登录成功",
            "user": {
                "id": user['id'],
                "username": user['username'],
                "role": user['role'],
                "email": user['email']
            }
        })
    else:
        return jsonify({"success": False, "message": "用户名或密码错误"}), 401


@auth_bp.route('/api/logout', methods=['POST'])
def logout():
    """用户登出"""
    session.clear()
    return jsonify({"success": True, "message": "已退出登录"})


@auth_bp.route('/api/check-auth', methods=['GET'])
def check_auth():
    """检查登录状态"""
    if 'user_id' in session:
        return jsonify({
            "authenticated": True,
            "user": {
                "id": session['user_id'],
                "username": session['username'],
                "role": session['role']
            }
        })
    else:
        return jsonify({"authenticated": False}), 401


@auth_bp.route('/api/internal/authenticate-user', methods=['POST'])
def internal_authenticate_user():
    """内部认证 API - 供 NAS 节点客户端调用"""
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"success": False, "message": "用户名和密码不能为空"}), 400

    conn = sqlite3.connect('nas_center.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ? AND status = "active"', (username,))
    user = cursor.fetchone()
    conn.close()

    if user and user['password_hash'] == password:
        return jsonify({
            "success": True,
            "user": {
                "id": user['id'],
                "username": user['username'],
                "role": user['role'],
                "email": user['email'],
                "file_permission": user['file_permission'],
                "node_access": json.loads(user['node_access'])
            }
        })
    else:
        return jsonify({"success": False, "message": "用户名或密码错误"}), 401


@auth_bp.route('/api/generate-node-access-token', methods=['POST'])
@login_required
def generate_node_access_token():
    """生成临时访问令牌"""
    data = request.json
    node_id = data.get('node_id')

    if not node_id:
        return jsonify({'error': '缺少节点ID'}), 400

    user_id = session['user_id']
    conn = sqlite3.connect('nas_center.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT avatar FROM users WHERE id = ?', (user_id,))
    user_row = cursor.fetchone()
    conn.close()

    avatar = user_row['avatar'] if user_row and user_row['avatar'] else ''

    token = jwt.encode({
        'user_id': session['user_id'],
        'username': session['username'],
        'role': session.get('role', 'user'),
        'file_permission': session.get('file_permission', 'readonly'),
        'avatar': avatar,
        'node_id': node_id,
        'exp': datetime.utcnow() + timedelta(hours=1)
    }, ACCESS_TOKEN_SECRET, algorithm='HS256')

    return jsonify({
        'success': True,
        'token': token
    })


@auth_bp.route('/api/verify-access-token', methods=['POST'])
def verify_access_token():
    """验证访问令牌"""
    try:
        data = request.json
        token = data.get('token')

        if not token:
            return jsonify({'success': False, 'error': '缺少令牌'}), 400

        payload = jwt.decode(token, ACCESS_TOKEN_SECRET, algorithms=['HS256'])

        role = payload.get('role', 'user')
        is_admin = (role == 'admin')

        new_token = jwt.encode({
            'user_id': payload['user_id'],
            'username': payload['username'],
            'role': role,
            'file_permission': payload.get('file_permission', 'readonly'),
            'avatar': payload.get('avatar', ''),
            'exp': datetime.utcnow() + timedelta(days=7)
        }, ACCESS_TOKEN_SECRET, algorithm='HS256')

        return jsonify({
            'success': True,
            'user': {
                'id': payload['user_id'],
                'username': payload['username'],
                'role': role,
                'file_permission': payload.get('file_permission', 'readonly'),
                'avatar': payload.get('avatar', ''),
                'is_admin': is_admin
            },
            'token': new_token
        })

    except jwt.ExpiredSignatureError:
        return jsonify({'success': False, 'error': '令牌已过期'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'success': False, 'error': '无效的令牌'}), 401
    except Exception as e:
        print(f"[验证令牌失败] {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@auth_bp.route('/api/change_password', methods=['POST'])
def api_change_password():
    """用户修改密码"""
    from config import NAS_SHARED_SECRET
    from common import get_db

    try:
        data = request.get_json()
        user_id = data.get('user_id')
        old_password = data.get('old_password')
        new_password = data.get('new_password')

        secret = request.headers.get('X-NAS-Secret')
        if secret != NAS_SHARED_SECRET:
            if 'user_id' not in session:
                return jsonify({'error': '未授权'}), 401
            user_id = session['user_id']

        if not old_password or not new_password:
            return jsonify({'error': '请提供旧密码和新密码'}), 400

        if len(new_password) < 6:
            return jsonify({'error': '新密码长度至少6位'}), 400

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({'error': '用户不存在'}), 404

        if user['password_hash'] != old_password:
            return jsonify({'error': '旧密码错误'}), 400

        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_password, user_id))
        db.commit()

        return jsonify({'success': True, 'message': '密码修改成功'})

    except Exception as e:
        print(f"[ERROR] change_password: {e}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500




