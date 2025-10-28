import sqlite3

def fix_database():
    """修复 nas_center.db 中的 disks 表,将 node_id 从 INTEGER 改为 TEXT"""

    conn = sqlite3.connect('nas_center.db')
    cursor = conn.cursor()

    try:
        print("🔧 开始修复数据库...")

        # 1. 备份旧表
        print("📦 备份旧表...")
        cursor.execute('ALTER TABLE disks RENAME TO disks_old')

        # 2. 创建新表 (node_id 改为 TEXT)
        print("🆕 创建新表结构...")
        cursor.execute('''
            CREATE TABLE disks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT,
                mount TEXT,
                status TEXT,
                capacity_gb REAL,
                is_encrypted INTEGER DEFAULT 0,
                is_locked INTEGER DEFAULT 0
            )
        ''')

        # 3. 迁移数据
        print("📋 迁移数据...")
        cursor.execute('INSERT INTO disks SELECT * FROM disks_old')

        # 4. 删除旧表
        print("🗑️  删除旧表...")
        cursor.execute('DROP TABLE disks_old')

        # 5. 验证
        cursor.execute('PRAGMA table_info(disks)')
        print("\n✅ 新表结构:")
        for row in cursor.fetchall():
            print(f"  {row}")

        cursor.execute('SELECT * FROM disks')
        rows = cursor.fetchall()
        print(f"\n✅ 数据迁移完成,共 {len(rows)} 条记录")

        conn.commit()
        print("\n🎉 数据库修复成功!")

    except Exception as e:
        print(f"\n❌ 修复失败: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    fix_database()