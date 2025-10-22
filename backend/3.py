"""
检查数据库结构
"""
import sqlite3
import os

db_path = 'nas_center.db'

if not os.path.exists(db_path):
    print(f"❌ 找不到数据库文件: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 60)
print("数据库结构检查")
print("=" * 60)

# 获取所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()

print(f"\n📊 数据库中的表 (共 {len(tables)} 个):")
for table in tables:
    print(f"  • {table[0]}")

# 检查 users 表结构
print("\n" + "=" * 60)
print("users 表结构:")
print("=" * 60)

cursor.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()

if columns:
    print("\n字段列表:")
    for col in columns:
        print(f"  {col[1]:20} | {col[2]:15} | 默认值: {col[4]}")
else:
    print("❌ users 表不存在或没有字段")

# 查看示例数据
print("\n" + "=" * 60)
print("users 表示例数据:")
print("=" * 60)

try:
    cursor.execute("SELECT * FROM users LIMIT 3")
    users = cursor.fetchall()

    if users:
        # 获取列名
        col_names = [description[0] for description in cursor.description]
        print("\n列名:", col_names)
        print("\n数据:")
        for user in users:
            print(f"  {user}")
    else:
        print("表为空")
except Exception as e:
    print(f"❌ 查询失败: {e}")

# 检查是否已有分组相关表
print("\n" + "=" * 60)
print("检查节点分组相关表:")
print("=" * 60)

for table_name in ['node_groups', 'node_group_members']:
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    exists = cursor.fetchone()

    if exists:
        print(f"✅ {table_name} 表已存在")
        cursor.execute(f"PRAGMA table_info({table_name})")
        cols = cursor.fetchall()
        for col in cols:
            print(f"    {col[1]:20} | {col[2]:15}")
    else:
        print(f"❌ {table_name} 表不存在")

conn.close()

print("\n" + "=" * 60)
print("检查完成")
print("=" * 60)