"""
更新用户权限脚本
设置更细化的权限级别
"""

import sqlite3

# 连接数据库
conn = sqlite3.connect('nas_center.db')
cursor = conn.cursor()

print("更新用户权限...")

try:
    # 权限级别说明:
    # - fullcontrol: 完全控制(管理员) - 可以上传、下载、删除、管理
    # - readwrite: 读写权限 - 可以上传、下载、删除文件
    # - readonly: 只读权限 - 只能下载和查看

    # 1. 为管理员设置完全控制权限
    print("为管理员设置完全控制权限...")
    cursor.execute("""
        UPDATE users 
        SET file_permission = 'fullcontrol' 
        WHERE role = 'admin'
    """)

    # 2. 为 user 用户设置读写权限
    print("为 user 用户设置读写权限...")
    cursor.execute("""
        UPDATE users 
        SET file_permission = 'readwrite' 
        WHERE username = 'user'
    """)

    conn.commit()
    print("✅ 权限更新成功!")

    # 3. 显示更新后的权限
    cursor.execute("SELECT username, role, file_permission FROM users")
    users = cursor.fetchall()
    print("\n当前用户权限:")
    print("-" * 60)
    for user in users:
        permission_desc = {
            'fullcontrol': '完全控制 (上传/下载/删除/管理)',
            'readwrite': '读写权限 (上传/下载/删除)',
            'readonly': '只读权限 (仅下载/查看)'
        }.get(user[2], user[2])
        print(f"  {user[0]:15} | {user[1]:10} | {user[2]:15} ({permission_desc})")
    print("-" * 60)

except Exception as e:
    print(f"❌ 错误: {e}")
    conn.rollback()
finally:
    conn.close()

print("\n权限说明:")
print("  • fullcontrol - 完全控制: 管理员权限,可以管理系统和所有文件")
print("  • readwrite   - 读写权限: 可以上传、下载、删除文件")
print("  • readonly    - 只读权限: 只能下载和查看文件")