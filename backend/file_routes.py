# file_routes.py - 文件操作路由
from flask import Blueprint, jsonify, request, Response
import requests
from urllib.parse import quote
from auth import login_required, permission_required
from common import get_node_config_by_id

file_bp = Blueprint('file', __name__)


@file_bp.route('/api/files/<node_id>/list', methods=['GET'])
@login_required
@permission_required('readonly')
def list_files(node_id):
    """列出文件"""
    path = request.args.get('path', '/')
    node_config = get_node_config_by_id(node_id)
    if not node_config:
        return jsonify({"error": "节点不存在"}), 404

    try:
        url = f"http://{node_config['ip']}:{node_config['port']}/api/list?path={path}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": f"从节点 {node_config['name']} 获取文件列表失败", "message": str(e)}), 500


@file_bp.route('/api/nodes/<node_id>/upload', methods=['POST'])
@login_required
@permission_required('readwrite')
def upload_to_node(node_id):
    """上传文件到节点"""
    node_config = get_node_config_by_id(node_id)
    if not node_config:
        return jsonify({"error": "节点不存在"}), 404

    try:
        disk = request.form.get('disk', '')
        path = request.form.get('path', '')

        full_path = disk
        if path:
            full_path = f"{disk}/{path}".replace('//', '/')

        url = f"http://{node_config['ip']}:{node_config['port']}/api/upload"

        files = []
        for key in request.files:
            for f in request.files.getlist(key):
                files.append(('file', (f.filename, f.stream, f.content_type)))

        data = {'path': full_path}
        response = requests.post(url, files=files, data=data, timeout=120)

        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": f"上传失败: {str(e)}"}), 500


@file_bp.route('/api/nodes/<node_id>/download', methods=['GET'])
@login_required
@permission_required('readonly')
def download_from_node(node_id):
    """从节点下载文件"""
    node_config = get_node_config_by_id(node_id)
    if not node_config:
        return jsonify({"error": "节点不存在"}), 404

    try:
        disk = request.args.get('disk', '')
        path = request.args.get('path', '')

        full_path = disk
        if path:
            full_path = f"{disk}/{path}".replace('//', '/')

        url = f"http://{node_config['ip']}:{node_config['port']}/api/download?path={full_path}"
        response = requests.get(url, stream=True, timeout=300)

        if response.status_code != 200:
            return jsonify({"error": "下载失败"}), response.status_code

        filename = path.split('/')[-1] if path else 'download'
        encoded_filename = quote(filename)

        return Response(
            response.iter_content(chunk_size=8192),
            content_type=response.headers.get('Content-Type', 'application/octet-stream'),
            headers={
                'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}",
                'Content-Length': response.headers.get('Content-Length', '')
            }
        )
    except Exception as e:
        return jsonify({"error": f"下载失败: {str(e)}"}), 500


@file_bp.route('/api/nodes/<node_id>/mkdir', methods=['POST'])
@login_required
@permission_required('readwrite')
def mkdir_on_node(node_id):
    """在节点上创建文件夹"""
    node_config = get_node_config_by_id(node_id)
    if not node_config:
        return jsonify({"error": "节点不存在"}), 404

    try:
        data = request.json
        disk = data.get('disk', '')
        path = data.get('path', '')

        full_path = disk
        if path:
            full_path = f"{disk}/{path}".replace('//', '/')

        url = f"http://{node_config['ip']}:{node_config['port']}/api/mkdir"
        response = requests.post(url, json={"path": full_path}, timeout=10)

        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": f"创建文件夹失败: {str(e)}"}), 500


@file_bp.route('/api/nodes/<node_id>/delete', methods=['POST'])
@login_required
@permission_required('fullcontrol')
def delete_on_node(node_id):
    """删除节点上的文件"""
    node_config = get_node_config_by_id(node_id)
    if not node_config:
        return jsonify({"error": "节点不存在"}), 404

    try:
        data = request.json
        disk = data.get('disk', '')
        path = data.get('path', '')

        full_path = disk
        if path:
            full_path = f"{disk}/{path}".replace('//', '/')

        url = f"http://{node_config['ip']}:{node_config['port']}/api/delete"
        response = requests.post(url, json={"path": full_path}, timeout=30)

        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": f"删除失败: {str(e)}"}), 500


@file_bp.route('/api/nodes/<node_id>/preview', methods=['GET'])
@login_required
@permission_required('readonly')
def preview_on_node(node_id):
    """预览节点上的文件"""
    node_config = get_node_config_by_id(node_id)
    if not node_config:
        return jsonify({"error": "节点不存在"}), 404

    try:
        disk = request.args.get('disk', '')
        path = request.args.get('path', '')

        full_path = disk
        if path:
            full_path = f"{disk}/{path}".replace('//', '/')

        url = f"http://{node_config['ip']}:{node_config['port']}/api/preview?path={full_path}"
        response = requests.get(url, stream=True, timeout=60)

        if response.status_code != 200:
            return jsonify({"error": "预览失败"}), response.status_code

        return Response(
            response.iter_content(chunk_size=8192),
            content_type=response.headers.get('Content-Type', 'application/octet-stream')
        )
    except Exception as e:
        return jsonify({"error": f"预览失败: {str(e)}"}), 500


@file_bp.route('/api/files/<node_id>/delete', methods=['POST'])
@login_required
@permission_required('fullcontrol')
def delete_file(node_id):
    """删除文件（旧接口兼容）"""
    path = request.json.get('path')
    node_config = get_node_config_by_id(node_id)
    if not node_config:
        return jsonify({"error": "节点不存在"}), 404

    try:
        url = f"http://{node_config['ip']}:{node_config['port']}/api/files/delete"
        response = requests.post(url, json={"path": path}, timeout=10)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": f"在节点 {node_config['name']} 上删除文件失败", "message": str(e)}), 500


@file_bp.route('/api/files/<node_id>/mkdir', methods=['POST'])
@login_required
@permission_required('readwrite')
def mkdir(node_id):
    """创建文件夹（旧接口兼容）"""
    path = request.json.get('path')
    node_config = get_node_config_by_id(node_id)
    if not node_config:
        return jsonify({"error": "节点不存在"}), 404

    try:
        url = f"http://{node_config['ip']}:{node_config['port']}/api/files/mkdir"
        response = requests.post(url, json={"path": path}, timeout=5)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": f"在节点 {node_config['name']} 上创建文件夹失败", "message": str(e)}), 500