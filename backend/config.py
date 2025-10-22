# config.py
import os

# 节点间通信的共享密钥（生产环境应该使用环境变量）
NAS_SHARED_SECRET = os.getenv('NAS_SHARED_SECRET', 'your-very-secure-secret-key-change-in-production')

# 其他配置
DATABASE_PATH = 'nas_center.db'