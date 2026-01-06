# proxy_routes.py - 代理转发路由
from flask import Blueprint, jsonify, request, Response, stream_with_context, session
import requests
from auth import login_required
from common import get_db, get_node_config_by_id
from config import NAS_SHARED_SECRET

proxy_bp = Blueprint('proxy', __name__)


@proxy_bp.route('/share/<node_id>/<local_token>', methods=['GET', 'POST'])
def proxy_share_request(node_id, local_token):
    """代理公网分享链接到局域网节点"""
    print(f"[DEBUG] 收到分享请求: node_id={node_id}, token={local_token}")

    node_config = get_node_config_by_id(node_id)
    print(f"[DEBUG] 节点配置: {node_config}")

    if not node_config:
        print(f"[DEBUG] 节点不存在: {node_id}")
        return jsonify({"error": "分享节点不存在"}), 404

    target_url = f"http://{node_config['ip']}:{node_config['port']}/share/{local_token}"

    print(f"[SHARE PROXY] 代理分享请求: {node_id} -> {target_url}")

    try:
        req_headers = {key: value for (key, value) in request.headers if key.lower() != 'host'}
        req_headers['X-Forwarded-For'] = request.remote_addr

        if request.method == 'GET':
            resp = requests.get(
                target_url,
                params=request.args,
                headers=req_headers,
                stream=True,
                timeout=30
            )
        elif request.method == 'POST':
            resp = requests.post(
                target_url,
                params=request.args,
                data=request.get_data(),
                headers=req_headers,
                stream=True,
                timeout=30
            )

        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [
            (name, value) for (name, value) in resp.raw.headers.items()
            if name.lower() not in excluded_headers
        ]

        return Response(stream_with_context(resp.iter_content(chunk_size=8192)),
                        resp.status_code,
                        headers)

    except requests.exceptions.Timeout:
        return jsonify({"error": f"节点 {node_config['name']} 响应超时"}), 504
    except requests.exceptions.ConnectionError:
        print(f"[ERROR] 无法连接到节点 {node_config['name']} (URL: {target_url})")
        return jsonify({"error": f"无法连接到节点 {node_config['name']}"}), 503
    except Exception as e:
        print(f"[ERROR] 代理分享请求失败: {e}")
        return jsonify({"error": f"请求节点失败: {str(e)}"}), 500


@proxy_bp.route('/proxy/node/<node_id>/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_to_node_page(node_id, subpath):
    """代理到客户端节点的页面请求"""
    try:
        print(f"[页面代理] {request.method} /proxy/node/{node_id}/{subpath}")

        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT ip, port, status FROM nodes WHERE node_id = ?', (node_id,))
        node = cursor.fetchone()

        if not node:
            return jsonify({'error': '节点不存在'}), 404

        if node['status'] != 'online':
            return jsonify({'error': '节点已离线'}), 503

        target_url = f"http://{node['ip']}:{node['port']}/{subpath}"

        if request.query_string:
            target_url += '?' + request.query_string.decode('utf-8')

        print(f"[页面代理转发] {target_url}")

        headers = {}
        excluded_headers = ['host', 'connection', 'content-length', 'content-encoding', 'transfer-encoding', 'if-modified-since', 'if-none-match']
        for key, value in request.headers:
            if key.lower() not in excluded_headers:
                headers[key] = value

        try:
            if 'convert-pdf' in subpath or 'preview' in subpath:
                timeout = 120
            else:
                timeout = 30

            if request.method == 'GET':
                response = requests.get(target_url, headers=headers, timeout=timeout)
            elif request.method == 'POST':
                response = requests.get(target_url, headers=headers, timeout=timeout)
            elif request.method == 'PUT':
                response = requests.get(target_url, headers=headers, timeout=timeout)
            elif request.method == 'DELETE':
                response = requests.get(target_url, headers=headers, timeout=timeout)
            else:
                return jsonify({'error': '不支持的请求方法'}), 405

            excluded_response_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
            response_headers = []
            for key, value in response.headers.items():
                if key.lower() not in excluded_response_headers:
                    response_headers.append((key, value))

            print(f"[页面代理响应] 状态码: {response.status_code}, 类型: {response.headers.get('Content-Type', 'unknown')}")

            return response.content, response.status_code, response_headers

        except requests.Timeout:
            print(f"[页面代理超时] 节点 {node_id} 响应超时")
            return jsonify({'error': '节点响应超时'}), 504
        except requests.ConnectionError as e:
            print(f"[页面代理连接错误] 无法连接到节点 {node_id}: {e}")
            return jsonify({'error': f'无法连接到节点: {str(e)}'}), 502

    except Exception as e:
        print(f"[页面代理异常] {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'代理请求失败: {str(e)}'}), 500


@proxy_bp.route('/api/nodes/<node_id>/proxy/<path:api_path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def proxy_to_node(node_id, api_path):
    """代理所有到客户端的请求"""
    node_config = get_node_config_by_id(node_id)
    if not node_config:
        return jsonify({"error": "节点不存在"}), 404

    target_url = f"http://{node_config['ip']}:{node_config['port']}/api/{api_path}"

    headers = {
        'X-NAS-Username': session['username'],
        'X-NAS-Secret': NAS_SHARED_SECRET,
        'Content-Type': 'application/json'
    }

    print(f"[PROXY] {request.method} {target_url} (user: {session['username']})")

    try:
        if request.method == 'GET':
            response = requests.get(
                target_url,
                params=request.args,
                headers=headers,
                timeout=30
            )
        elif request.method == 'POST':
            response = requests.post(
                target_url,
                json=request.get_json() if request.is_json else None,
                data=request.get_data() if not request.is_json else None,
                headers=headers,
                timeout=30
            )
        elif request.method == 'PUT':
            response = requests.put(
                target_url,
                json=request.get_json(),
                headers=headers,
                timeout=30
            )
        elif request.method == 'DELETE':
            response = requests.delete(
                target_url,
                json=request.get_json() if request.is_json else None,
                headers=headers,
                timeout=30
            )

        return response.content, response.status_code, dict(response.headers)

    except requests.exceptions.Timeout:
        return jsonify({"error": f"节点 {node_config['name']} 响应超时"}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({"error": f"无法连接到节点 {node_config['name']}"}), 503
    except Exception as e:
        print(f"[ERROR] 代理请求失败: {e}")
        return jsonify({"error": f"请求节点失败: {str(e)}"}), 500