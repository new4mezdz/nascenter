"""
节点分组功能 - 数据库迁移脚本 (修复版)
创建节点分组相关表
运行方式: python migrate_node_groups_v2.py
"""

import sqlite3
import json
from datetime import datetime
import os

def get_users_pk_column(cursor):
    """获取 users 表的主键列名"""
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()

    for col in columns:
        # col: (cid, name, type, notnull, dflt_value, pk)
        if col[5] == 1:  # pk == 1 表示主键
            return col[1]  # 返回列名

    # 如果没有找到,尝试常见的主键名
    col_names = [c[1] for c in columns]
    for possible_pk in ['id', 'user_id', 'ID', 'USER_ID']:
        if possible_pk in col_names:
            return possible_pk

    return None

def migrate():
    print("=" * 60)
    print("节点分组功能 - 数据库迁移 (修复版)")
    print("=" * 60)

    # 确定数据库路径
    db_path = 'nas_center.db'

    if not os.path.exists(db_path):
        print(f"❌ 错误: 找不到数据库文件 {db_path}")
        print(f"   当前目录: {os.getcwd()}")
        print(f"   请确保在管理端 backend 目录下运行此脚本")
        return

    print(f"数据库文件: {os.path.abspath(db_path)}")
    print("=" * 60)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 0. 检查 users 表结构
        print("\n🔍 步骤 0: 检查 users 表结构...")
        cursor.execute("PRAGMA table_info(users)")
        user_columns = cursor.fetchall()

        print(f"   users 表有 {len(user_columns)} 个字段:")
        for col in user_columns:
            print(f"     • {col[1]:20} {col[2]:15}")

        # 获取主键列名
        pk_column = get_users_pk_column(cursor)
        if pk_column:
            print(f"   ✅ 主键列: {pk_column}")
        else:
            print(f"   ❌ 警告: 未找到主键列,使用默认 'id'")
            pk_column = 'id'

        # 1. 创建节点分组表
        print("\n📋 步骤 1: 创建 node_groups 表...")

        # --- (修改点) ---
        # 在创建新表之前,强制删除旧表,防止因旧的、结构不正确的表存在而跳过创建
        print("   (正在清理旧的分组相关表,以便重建...)")
        try:
            # 必须先删除 members 表,因为它依赖 groups 表
            cursor.execute("DROP TABLE IF EXISTS node_group_members")
            cursor.execute("DROP TABLE IF EXISTS node_groups")
            print("   (旧表清理完毕)")
        except Exception as e:
            print(f"   (清理旧表时出错,可能是第一次运行: {e})")
        # --- (修改结束) ---

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS node_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                icon TEXT DEFAULT '📁',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ node_groups 表创建成功")

        # 2. 创建节点分组成员表
        print("\n📋 步骤 2: 创建 node_group_members 表...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS node_group_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                group_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES node_groups(id) ON DELETE CASCADE,
                UNIQUE(node_id, group_id)
            )
        ''')
        print("✅ node_group_members 表创建成功")

        # 3. 创建索引(提升查询性能)
        print("\n📋 步骤 3: 创建索引...")
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_node_group_members_node_id 
            ON node_group_members(node_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_node_group_members_group_id 
            ON node_group_members(group_id)
        ''')
        print("✅ 索引创建成功")

        # 4. 创建更新时间触发器
        print("\n📋 步骤 4: 创建 updated_at 触发器...")
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS update_node_groups_timestamp 
            AFTER UPDATE ON node_groups
            BEGIN
                UPDATE node_groups SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
        ''')
        print("✅ 触发器创建成功")

        # 5. 检查并更新 users 表的 node_access 字段
        print("\n📋 步骤 5: 检查 users 表的 node_access 字段...")

        col_names = [col[1] for col in user_columns]

        if 'node_access' not in col_names:
            print("⚠️  node_access 字段不存在,正在添加...")
            default_access = json.dumps({
                "type": "all",
                "allowed_groups": [],
                "allowed_nodes": [],
                "denied_nodes": []
            })
            cursor.execute(f'''
                ALTER TABLE users 
                ADD COLUMN node_access TEXT DEFAULT '{default_access}'
            ''')
            print("✅ node_access 字段添加成功")
        else:
            print("✅ node_access 字段已存在")

            # 更新现有用户的 node_access 为正确格式
            print("   正在更新现有用户的 node_access 格式...")
            cursor.execute(f"SELECT {pk_column}, node_access FROM users")
            users = cursor.fetchall()

            updated_count = 0
            for user_id, node_access in users:
                try:
                    # 尝试解析 JSON
                    if node_access:
                        access_data = json.loads(node_access)
                        needs_update = False

                        # 确保有所有必需字段
                        if 'type' not in access_data:
                            access_data['type'] = 'all'
                            needs_update = True
                        if 'allowed_groups' not in access_data:
                            access_data['allowed_groups'] = []
                            needs_update = True
                        if 'allowed_nodes' not in access_data:
                            access_data['allowed_nodes'] = []
                            needs_update = True
                        if 'denied_nodes' not in access_data:
                            access_data['denied_nodes'] = []
                            needs_update = True

                        # 如果需要更新
                        if needs_update:
                            cursor.execute(
                                f'UPDATE users SET node_access = ? WHERE {pk_column} = ?',
                                (json.dumps(access_data), user_id)
                            )
                            updated_count += 1
                    else:
                        # 如果为空,设置默认值
                        default_access = json.dumps({
                            "type": "all",
                            "allowed_groups": [],
                            "allowed_nodes": [],
                            "denied_nodes": []
                        })
                        cursor.execute(
                            f'UPDATE users SET node_access = ? WHERE {pk_column} = ?',
                            (default_access, user_id)
                        )
                        updated_count += 1
                except Exception as e:
                    print(f"   ⚠️  处理用户 {user_id} 时出错: {e}")
                    # 如果解析失败,设置为默认值
                    default_access = json.dumps({
                        "type": "all",
                        "allowed_groups": [],
                        "allowed_nodes": [],
                        "denied_nodes": []
                    })
                    cursor.execute(
                        f'UPDATE users SET node_access = ? WHERE {pk_column} = ?',
                        (default_access, user_id)
                    )
                    updated_count += 1

            if updated_count > 0:
                print(f"   ✅ 更新了 {updated_count} 个用户的 node_access 格式")
            else:
                print("   ✅ 所有用户的 node_access 格式已是最新")

        # 6. 创建示例分组(可选)
        print("\n📋 步骤 6: 创建示例分组...")

        # 检查是否已有分组
        cursor.execute("SELECT COUNT(*) FROM node_groups")
        count = cursor.fetchone()[0]

        if count == 0:
            print("   正在创建示例分组...")
            # 创建几个示例分组
            example_groups = [
                {
                    'name': '生产环境',
                    'description': '生产环境节点,需要特别授权访问',
                    'icon': '🏢'
                },
                {
                    'name': '开发环境',
                    'description': '开发和测试环境节点',
                    'icon': '💻'
                },
                {
                    'name': '测试环境',
                    'description': '用于测试和 QA 的节点',
                    'icon': '🧪'
                },
                {
                    'name': '备份节点',
                    'description': '用于数据备份和容灾的节点',
                    'icon': '💾'
                }
            ]

            for group in example_groups:
                cursor.execute('''
                    INSERT INTO node_groups (name, description, icon)
                    VALUES (?, ?, ?)
                ''', (group['name'], group['description'], group['icon']))
                print(f"      ✅ 创建示例分组: {group['name']}")

            print("\n   💡 提示: 示例分组已创建,请在管理界面中为分组添加节点")
        else:
            print(f"   ℹ️  已存在 {count} 个分组,跳过创建示例")

        # 提交更改
        conn.commit()

        print("\n" + "=" * 60)
        print("✅ 数据库迁移成功!")
        print("=" * 60)

        # 显示当前状态
        print("\n📊 当前数据统计:")

        cursor.execute("SELECT COUNT(*) FROM node_groups")
        group_count = cursor.fetchone()[0]
        print(f"  • 节点分组数: {group_count}")

        cursor.execute("SELECT COUNT(*) FROM node_group_members")
        member_count = cursor.fetchone()[0]
        print(f"  • 分组成员数: {member_count}")

        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"  • 用户总数: {user_count}")

        # 显示分组列表
        if group_count > 0:
            print("\n📁 现有分组:")
            cursor.execute('''
                SELECT id, name, description, icon, 
                       (SELECT COUNT(*) FROM node_group_members WHERE group_id = node_groups.id) as node_count
                FROM node_groups
                ORDER BY id
            ''')
            groups = cursor.fetchall()
            for g in groups:
                print(f"  {g[3]} ID:{g[0]} - {g[1]} ({g[4]} 个节点)")
                if g[2]:
                    print(f"     {g[2]}")

        print("\n" + "=" * 60)
        print("🎉 迁移完成! 可以开始使用节点分组功能了。")
        print("=" * 60)
        print("\n📝 下一步:")
        print("  1. 重启管理端服务器")
        print("  2. 登录管理端")
        print("  3. 打开 '权限管理' -> '节点分组' 标签页")
        print("  4. 为分组添加节点")
        print("  5. 为用户分配节点权限")
        print()

    except sqlite3.IntegrityError as e:
        print(f"\n❌ 完整性错误: {e}")
        print("   可能的原因: 分组名称重复或外键约束失败")
        conn.rollback()
    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    try:
        migrate()
    except KeyboardInterrupt:
        print("\n\n⚠️  迁移被用户中断")
    except Exception as e:
        print(f"\n❌ 发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()