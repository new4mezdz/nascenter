# auth.py - 认证装饰器
from functools import wraps
from flask import session, jsonify, request
import jwt
import sqlite3
from common import PERMISSION_MAP


ACCESS_TOKEN_SECRET = 'your-access-token-secret-key'  # 与管理端一致

def login_required(f):
    """要求登录的装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print(f"🔍 检查登录: session.user_id = {session.get('user_id')}")

        if 'user_id' not in session:
            print(f"❌ 未登录,Session内容: {dict(session)}")
            return jsonify({"error": "未登录,请先登录"}), 401
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    """要求管理员权限的装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "未登录,请先登录"}), 401
        if session.get('role') != 'admin':
            return jsonify({"error": "权限不足", "message": "此操作需要管理员权限"}), 403
        return f(*args, **kwargs)
    return decorated_function


def permission_required(required_level_name):
    """权限检查装饰器 - 支持 session 和 URL token"""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = None
            file_permission = None
            role = None

            # 方式1: 检查 session
            if 'user_id' in session:
                user_id = session['user_id']
                file_permission = session.get('file_permission', 'readonly')
                role = session.get('role', 'user')

            # 方式2: 检查 URL token
            if not user_id:
                token = request.args.get('token')
                if token:
                    try:
                        payload = jwt.decode(token, ACCESS_TOKEN_SECRET, algorithms=['HS256'])
                        user_id = payload.get('user_id')
                        file_permission = payload.get('file_permission', 'readonly')
                        role = payload.get('role', 'user')
                    except:
                        pass

            if not user_id:
                return jsonify({"error": "未登录"}), 401

            # 管理员自动放行
            if role == 'admin':
                return f(*args, **kwargs)

            # 比较权限等级
            user_level = PERMISSION_MAP.get(file_permission, 0)
            required_level = PERMISSION_MAP.get(required_level_name, 99)

            if user_level >= required_level:
                return f(*args, **kwargs)
            else:
                return jsonify({"error": "权限不足"}), 403

        return decorated_function

    return decorator