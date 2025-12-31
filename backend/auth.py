# auth.py - 认证装饰器
from functools import wraps
from flask import session, jsonify
import sqlite3
from common import PERMISSION_MAP


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
    """
    权限检查装饰器
    检查当前登录用户的 file_permission 是否满足要求
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({"error": "未登录"}), 401

            conn = None
            try:
                conn = sqlite3.connect('nas_center.db')
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT role, file_permission FROM users WHERE id = ?', (session['user_id'],))
                user = cursor.fetchone()

                if not user:
                    return jsonify({"error": "用户不存在"}), 401

                # 管理员自动放行
                if user['role'] == 'admin':
                    return f(*args, **kwargs)

                # 比较权限等级
                user_level = PERMISSION_MAP.get(user['file_permission'], 0)
                required_level = PERMISSION_MAP.get(required_level_name, 99)

                if user_level >= required_level:
                    return f(*args, **kwargs)
                else:
                    return jsonify({"error": "权限不足", "message": f"此操作需要 {required_level_name} 权限"}), 403

            except Exception as e:
                return jsonify({"error": "权限检查失败", "message": str(e)}), 500
            finally:
                if conn:
                    conn.close()

        return decorated_function
    return decorator