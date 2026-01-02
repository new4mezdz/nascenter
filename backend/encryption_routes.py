# encryption_routes.py - 磁盘加密管理路由
from flask import Blueprint, jsonify, request
import sqlite3
import requests
from auth import login_required, admin_required
from common import get_node_from_db, load_nodes_config
from config import NAS_SHARED_SECRET

encryption_bp = Blueprint('encryption', __name__)


@encryption_bp.route('/api/encryption/disks', methods=['GET'])
@login_required
def list_encrypted_disks():
    """返回节点磁盘的加密状态信息（实时从节点获取，离线时用缓存）"""
    try:
        node_id = request.args.get('node_id')

        if node_id:
            node = get_node_from_db(node_id)
            if not node:
                return jsonify({"success": False, "error": "节点不存在"}), 404

            # 先检查节点是否在线
            node_url = f"http://{node['ip']}:{node['port']}/api/disks"
            headers = {"X-NAS-Secret": NAS_SHARED_SECRET}

            try:
                res = requests.get(node_url, headers=headers, timeout=5)
                if res.status_code == 200:
                    node_disks = res.json()
                    disks = []
                    for disk in node_disks:
                        disks.append({
                            "node_id": node_id,
                            "mount": disk.get("mount"),
                            "status": "online",
                            "capacity_gb": disk.get("total_gb", 0),
                            "is_encrypted": disk.get("is_encrypted", False),
                            "is_locked": disk.get("is_locked", False)
                        })
                    return jsonify({"success": True, "disks": disks, "source": "realtime"})
            except requests.exceptions.RequestException as e:
                print(f"[管理端] 节点 {node_id} 离线，使用缓存数据: {e}")

            # 节点离线，从数据库读取缓存
            conn = sqlite3.connect('nas_center.db')
            cursor = conn.cursor()
            cursor.execute('''
                SELECT node_id, mount, status, capacity_gb, is_encrypted, is_locked
                FROM node_disks WHERE node_id = ?
            ''', (node_id,))
            rows = cursor.fetchall()
            conn.close()

            disks = []
            for row in rows:
                disks.append({
                    "node_id": row[0],
                    "mount": row[1],
                    "status": "offline",
                    "capacity_gb": row[3],
                    "is_encrypted": bool(row[4]),
                    "is_locked": bool(row[5])
                })

            return jsonify({
                "success": True,
                "disks": disks,
                "source": "cache",
                "warning": "节点离线，显示缓存数据"
            })

        else:
            # 没有指定节点时，从本地数据库读取
            conn = sqlite3.connect('nas_center.db')
            cursor = conn.cursor()
            cursor.execute('''
                SELECT node_id, mount, status, capacity_gb, is_encrypted, is_locked
                FROM node_disks
            ''')
            rows = cursor.fetchall()
            conn.close()

            disks = []
            for row in rows:
                disks.append({
                    "node_id": row[0],
                    "mount": row[1],
                    "status": row[2],
                    "capacity_gb": row[3],
                    "is_encrypted": bool(row[4]),
                    "is_locked": bool(row[5])
                })

            return jsonify({"success": True, "disks": disks})

    except Exception as e:
        print(f"[管理端] 获取磁盘列表失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@encryption_bp.route('/api/encryption/disk/lock', methods=['POST'])
@login_required
@admin_required
def lock_disk():
    """锁定磁盘"""
    data = request.get_json()
    node_id = data.get('node_id')
    mount = data.get('mount')

    if not (node_id and mount):
        return jsonify({"success": False, "error": "参数不完整"}), 400

    node = get_node_from_db(node_id)
    if not node:
        return jsonify({"success": False, "error": "节点不存在"}), 404

    node_url = f"http://{node['ip']}:{node['port']}/api/internal/encryption/lock-disk"
    headers = {"X-NAS-Secret": NAS_SHARED_SECRET}

    print(f"[管理端] 请求节点 {node_id} 锁定磁盘 {mount}")

    try:
        res = requests.post(node_url, json={"drive": mount}, headers=headers, timeout=10)
        if res.status_code == 200 and res.json().get("success"):
            conn = sqlite3.connect('nas_center.db')
            cursor = conn.cursor()
            cursor.execute("UPDATE disks SET is_locked=1 WHERE node_id=? AND mount=?", (node_id, mount))
            conn.commit()
            conn.close()
            print(f"[管理端] 节点 {node_id} 磁盘 {mount} 锁定成功 ✅")
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": res.text}), 500
    except Exception as e:
        print(f"[管理端] 锁定磁盘异常: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@encryption_bp.route('/api/encryption/disk/unlock', methods=['POST'])
@login_required
@admin_required
def unlock_disk():
    """解锁磁盘"""
    data = request.get_json()
    node_id = data.get("node_id")
    mount = data.get("mount")
    password = data.get("password")

    if not (node_id and mount and password):
        return jsonify({"success": False, "error": "参数不完整"}), 400

    NODES_CONFIG = load_nodes_config()
    node = next((n for n in NODES_CONFIG if n.get("id") == node_id), None)
    if not node:
        return jsonify({"success": False, "error": f"未找到节点 {node_id}"}), 404

    node_ip = node["ip"]
    node_port = node["port"]
    node_url = f"http://{node_ip}:{node_port}/api/internal/encryption/unlock-disk"

    print(f"[管理端] 请求节点 {node_id} ({node_ip}:{node_port}) 解锁磁盘: {mount}")

    try:
        payload = {"drive": mount, "password": password}
        headers = {"X-NAS-Secret": NAS_SHARED_SECRET}

        res = requests.post(node_url, json=payload, headers=headers, timeout=20)

        if res.status_code == 200:
            result = res.json()
            if result.get("success"):
                conn = sqlite3.connect("nas_center.db")
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE disks SET is_locked = 0 WHERE node_id=? AND mount=?",
                    (node_id, mount),
                )
                conn.commit()
                conn.close()

                print(f"[管理端] 节点 {node_id} 磁盘 {mount} 解锁成功 ✅")
                return jsonify({"success": True, "message": result.get("message", "解锁成功")})
            else:
                print(f"[管理端] 节点执行失败: {result.get('error')}")
                return jsonify({"success": False, "error": result.get("error", "解锁失败")}), 500
        else:
            print(f"[管理端] 节点返回HTTP错误 {res.status_code}: {res.text}")
            return jsonify({"success": False, "error": f"节点HTTP错误: {res.text}"}), 500

    except requests.exceptions.RequestException as e:
        print(f"[管理端] 无法连接节点 {node_id}: {e}")
        return jsonify({"success": False, "error": f"无法连接节点 {node_ip}:{node_port}"}), 500
    except Exception as e:
        print(f"[管理端] 解锁磁盘异常: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@encryption_bp.route('/api/encryption/disk/encrypt', methods=['POST'])
@login_required
@admin_required
def encrypt_disk():
    """为磁盘启用加密"""
    data = request.get_json()
    node_id = data.get("node_id")
    mount = data.get("mount")
    password = data.get("password")

    if not (node_id and mount and password):
        return jsonify({"success": False, "error": "参数不完整"}), 400

    NODES_CONFIG = load_nodes_config()
    node = next((n for n in NODES_CONFIG if n.get("id") == node_id), None)
    if not node:
        return jsonify({"success": False, "error": f"未找到节点 {node_id}"}), 404

    node_ip = node["ip"]
    node_port = node["port"]
    node_url = f"http://{node_ip}:{node_port}/api/internal/encryption/encrypt-disk"

    print(f"[管理端] 请求节点 {node_id} ({node_ip}:{node_port}) 启用加密: {mount}")

    try:
        payload = {"drive": mount, "password": password}
        headers = {"X-NAS-Secret": NAS_SHARED_SECRET}

        res = requests.post(node_url, json=payload, headers=headers, timeout=300)

        if res.status_code == 200:
            result = res.json()
            if result.get("success"):
                conn = sqlite3.connect("nas_center.db")
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE disks
                    SET is_encrypted = 1, is_locked = 1
                    WHERE node_id = ? AND mount = ?
                    """,
                    (node_id, mount),
                )
                conn.commit()
                conn.close()

                print(f"[管理端] 节点 {node_id} 磁盘 {mount} 加密成功 ✅")
                return jsonify({
                    "success": True,
                    "message": result.get("message", "磁盘加密完成"),
                    "details": result.get("details", {})
                })
            else:
                print(f"[管理端] 节点执行失败: {result.get('error')}")
                return jsonify({
                    "success": False,
                    "error": result.get("error", "节点执行失败")
                }), 500
        else:
            print(f"[管理端] 节点返回异常状态: {res.status_code}, 内容: {res.text}")
            return jsonify({
                "success": False,
                "error": f"节点HTTP错误: {res.text}"
            }), 500

    except requests.exceptions.RequestException as e:
        print(f"[管理端] 无法连接节点 {node_id}: {e}")
        return jsonify({
            "success": False,
            "error": f"无法连接节点 {node_ip}:{node_port}"
        }), 500
    except Exception as e:
        print(f"[管理端] 启用加密异常: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@encryption_bp.route('/api/encryption/disk/decrypt', methods=['POST'])
@login_required
@admin_required
def decrypt_disk():
    """永久解密磁盘"""
    data = request.get_json()
    node_id = data.get('node_id')
    mount = data.get('mount')
    password = data.get('password')

    if not (node_id and mount and password):
        return jsonify({"success": False, "error": "参数不完整"}), 400

    node = get_node_from_db(node_id)
    if not node:
        return jsonify({"success": False, "error": "节点不存在"}), 404

    node_url = f"http://{node['ip']}:{node['port']}/api/internal/encryption/decrypt-disk"
    headers = {"X-NAS-Secret": NAS_SHARED_SECRET}

    print(f"[管理端] 请求节点 {node_id} 永久解密磁盘 {mount}")

    try:
        res = requests.post(node_url, json={"drive": mount, "password": password}, headers=headers, timeout=10)
        if res.status_code == 200 and res.json().get("success"):
            conn = sqlite3.connect('nas_center.db')
            cursor = conn.cursor()
            cursor.execute("UPDATE disks SET is_encrypted=0, is_locked=0 WHERE node_id=? AND mount=?", (node_id, mount))
            conn.commit()
            conn.close()
            print(f"[管理端] 节点 {node_id} 磁盘 {mount} 解密成功 ✅")
            return jsonify({"success": True})
        else:
            print(f"[管理端] 节点响应错误: {res.text}")
            return jsonify({"success": False, "error": res.text}), 500

    except Exception as e:
        print(f"[管理端] 永久解密异常: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@encryption_bp.route('/api/encryption/disk/change-password', methods=['POST'])
@login_required
@admin_required
def change_disk_password():
    """修改磁盘加密密码"""
    data = request.get_json()
    node_id = data.get('node_id')
    mount = data.get('mount')
    new_pw = data.get('new_password')

    if not (node_id and mount and new_pw):
        return jsonify({"success": False, "error": "参数不完整"}), 400

    node = get_node_from_db(node_id)
    if not node:
        return jsonify({"success": False, "error": "节点不存在"}), 404

    node_url = f"http://{node['ip']}:{node['port']}/api/internal/encryption/change-password"
    headers = {"X-NAS-Secret": NAS_SHARED_SECRET}

    print(f"[管理端] 请求节点 {node_id} 修改密码: {mount}")

    try:
        res = requests.post(node_url, json={"drive": mount, "new_password": new_pw}, headers=headers, timeout=10)
        if res.status_code == 200 and res.json().get("success"):
            print(f"[管理端] 节点 {node_id} 磁盘 {mount} 密码修改成功 ✅")
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": res.text}), 500
    except Exception as e:
        print(f"[管理端] 修改密码异常: {e}")
        return jsonify({"success": False, "error": str(e)}), 500