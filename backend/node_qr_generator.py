"""
节点二维码生成器
从 nas.db 的 nodes 表读取节点信息，生成访问二维码
"""
import os
import sys
import sqlite3
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer

# 默认数据库路径（和脚本同目录）
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nas_center.db")

def get_nodes(db_path: str) -> list:
    """从数据库获取节点列表"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 尝试获取节点信息
    try:
        cursor.execute("SELECT * FROM nodes")
        nodes = [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        print("❌ 数据库中没有 nodes 表")
        conn.close()
        return []
    
    conn.close()
    return nodes

def generate_qr(url: str, output: str = "qrcode.png"):
    """生成二维码"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer()
    )
    img.save(output)
    return output

def main():
    # 检查数据库路径
    db_path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        print(f"用法: python {sys.argv[0]} [数据库路径]")
        sys.exit(1)
    
    # 获取节点列表
    nodes = get_nodes(db_path)
    
    if not nodes:
        print("没有找到节点信息")
        sys.exit(1)
    
    # 显示节点列表
    print("\n" + "=" * 50)
    print("📡 可用节点列表")
    print("=" * 50)
    
    for i, node in enumerate(nodes, 1):
        # 尝试获取常见字段
        node_id = node.get('node_id') or node.get('id') or '?'
        ip = node.get('ip') or node.get('address') or '?'
        port = node.get('port', 5000)
        status = node.get('status', '未知')
        name = node.get('name') or node.get('node_name') or ''
        
        status_icon = '🟢' if status == 'online' else '🔴'
        name_str = f" ({name})" if name else ""
        
        print(f"  [{i}] {status_icon} {ip}:{port}{name_str}")
    
    print("=" * 50)
    print("  [0] 退出")
    print()
    
    # 用户选择
    while True:
        try:
            choice = input("请选择节点编号: ").strip()
            
            if choice == '0':
                print("👋 再见!")
                sys.exit(0)
            
            idx = int(choice) - 1
            if 0 <= idx < len(nodes):
                break
            else:
                print("❌ 无效的编号，请重新选择")
        except ValueError:
            print("❌ 请输入数字")
    
    # 获取选中的节点
    selected = nodes[idx]
    ip = selected.get('ip') or selected.get('address')
    port = selected.get('port', 5000)
    
    # 构建URL
    url = f"http://{ip}:{port}"
    
    # 询问是否使用HTTPS
    use_https = input(f"\n使用HTTPS? (y/N): ").strip().lower()
    if use_https == 'y':
        url = f"https://{ip}:{port}"
    
    # 生成二维码
    output_file = f"node_{ip.replace('.', '_')}.png"
    generate_qr(url, output_file)
    
    print(f"\n✅ 二维码已生成!")
    print(f"   网址: {url}")
    print(f"   文件: {output_file}")
    print()

if __name__ == "__main__":
    main()
