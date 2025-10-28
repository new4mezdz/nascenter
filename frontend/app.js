// 配置 axios 默认设置
axios.defaults.withCredentials = true;
axios.defaults.baseURL = '';
axios.interceptors.request.use(config => {
    config.withCredentials = true;
    return config;
}, error => {
    return Promise.reject(error);
});
const { createApp } = Vue;
createApp({
    data() {
        return {
            windows: [],
            nextWindowId: 1,
            maxZIndex: 100,
            currentTime: '',
            dragWindow: null,
            dragOffset: {x: 0, y: 0},
            apiBaseUrl: '',
            showStartMenu: false,
            showNavbar: false,
            currentNodeName: 'NAS Center 主控',
            currentUser: null,  // 当前登录用户
            showUserMenu: false, // 用户菜单显示状态

            // 节点分组相关
            showGroupDialog: false,
            groupDialogMode: 'create',  // 'create' | 'edit'
            groupForm: {
                id: null,
                name: '',
                description: '',
                icon: '📁',
                nodes: []
            },
            availableNodes: [],  // 所有可用节点列表

            // 用户节点权限对话框
            showUserAccessDialog: false,
            currentEditUser: null,
            userAccessForm: {
                type: 'all',
                allowed_groups: [],
                allowed_nodes: [],
                denied_nodes: []
            }
        };
    },
    mounted() {
        this.updateTime();
        setInterval(() => this.updateTime(), 1000);
        this.openNodeManagement();
        this.checkAuth();

          setInterval(() => {
    this.refreshNodeMonitorStats();
  }, 5000);
    },
    methods: {


        updateTime() {
            const now = new Date();
            this.currentTime = now.toLocaleTimeString('zh-CN');
        },

        createWindow(config) {
            const win = {
                id: this.nextWindowId++,
                x: 100 + (this.windows.length * 30),
                y: 50 + (this.windows.length * 30),
                width: config.width || 900,
                height: config.height || 600,
                zIndex: this.maxZIndex++,
                maximized: false,
                minimized: false,
                ...config
            };
            this.windows.push(win);
            return win;
        },

        closeWindow(id) {
            const index = this.windows.findIndex(w => w.id === id);
            if (index !== -1) {
                this.windows.splice(index, 1);
            }
        },

        minimizeWindow(id) {
            const win = this.windows.find(w => w.id === id);
            if (win) win.minimized = true;
        },

        toggleMaximize(id) {
            const win = this.windows.find(w => w.id === id);
            if (win) win.maximized = !win.maximized;
        },

        focusWindow(id) {
            const win = this.windows.find(w => w.id === id);
            if (win) {
                win.minimized = false;
                win.zIndex = this.maxZIndex++;
            }
        },

        startDrag(event, window) {
            if (window.maximized) return;
            this.dragWindow = window;
            this.dragOffset.x = event.clientX - window.x;
            this.dragOffset.y = event.clientY - window.y;

            document.addEventListener('mousemove', this.onDrag);
            document.addEventListener('mouseup', this.stopDrag);
        },

        onDrag(event) {
            if (!this.dragWindow) return;
            this.dragWindow.x = event.clientX - this.dragOffset.x;
            this.dragWindow.y = event.clientY - this.dragOffset.y;
        },

        stopDrag() {
            this.dragWindow = null;
            document.removeEventListener('mousemove', this.onDrag);
            document.removeEventListener('mouseup', this.stopDrag);
        },

        closeAllMenus() {
            this.showStartMenu = false;
        },
        // ============ 节点管理 ============
        openNodeManagement() {
            const win = this.createWindow({
                type: 'nodes',
                title: '节点管理',
                icon: '🖥️',
                width: 1200,
                height: 700,
                nodes: [],
                stats: null,
                loading: false,
                selectedNodeDisks: null
            });
            this.loadNodesData(win);
        },

        async loadNodesData(window) {
            window.loading = true;
            try {
                const nodesRes = await axios.get(`${this.apiBaseUrl}/api/nodes`);
                window.nodes = nodesRes.data;
                const statsRes = await axios.get(`${this.apiBaseUrl}/api/stats`);
                window.stats = {
                    total: statsRes.data.total_nodes,
                    online: statsRes.data.online_nodes,
                    offline: statsRes.data.offline_nodes,
                    warning: statsRes.data.warning_nodes
                };
            } catch (error) {
                console.error('加载失败:', error);
                alert('无法连接到后端 API,请确保 Flask 服务运行在 http://127.0.0.1:8080');
            } finally {
                window.loading = false;
            }
        },

        refreshNodes(window) {
            this.loadNodesData(window);
        },

        // nascenter/frontend/app.js


        async accessNode(node) {
    if (node.status === 'offline') {
        alert(`节点 ${node.name} 当前离线,无法访问`);
        return;
    }

    try {
        // 1. 向管理端请求生成访问令牌
        const response = await axios.post(`${this.apiBaseUrl}/api/generate-node-access-token`, {
            node_id: node.id
        }, {
            withCredentials: true  // 确保发送 Cookie
        });

        if (response.data.success) {
            const token = response.data.token;

            // 2. 构建客户端访问 URL (携带 token)
            const clientUrl = `http://${node.ip}:${node.port}/desktop?token=${token}`;

            // 3. 在新标签页打开客户端
            const confirmed = confirm(
                `🔐 即将访问节点\n\n` +
                `节点名称: ${node.name}\n` +
                `访问地址: http://${node.ip}:${node.port}\n` +
                `您的权限: ${response.data.file_permission || '只读'}\n\n` +
                `⏰ 访问令牌有效期: 1 小时\n\n` +
                `是否继续?`
            );

            if (confirmed) {
                window.open(clientUrl, '_blank');
            }
        } else {
            alert(`❌ 生成访问令牌失败: ${response.data.error}`);
        }
    } catch (error) {
        console.error('生成访问令牌失败:', error);
        alert('❌ 生成访问令牌失败: ' + (error.response?.data?.error || error.message));
    }
},

        async viewNodeDisks(window, node) {
            if (node.status === 'offline') {
                alert(`节点 ${node.name} 当前离线,无法查看磁盘信息`);
                return;
            }

            window.selectedNodeDisks = {
                name: node.name,
                loading: true,
                error: null,
                disks: []
            };

            try {
                const response = await axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/disks`);

                if (response.data.success) {
                    window.selectedNodeDisks.disks = response.data.disks;
                    window.selectedNodeDisks.loading = false;
                } else {
                    throw new Error(response.data.error || '获取磁盘信息失败');
                }
            } catch (error) {
                console.error('获取磁盘信息失败:', error);
                window.selectedNodeDisks.error = error.response?.data?.error || error.message || '无法连接到节点';
                window.selectedNodeDisks.loading = false;
            }
        },

        getStatusClass(status) {
            const classes = {
                online: 'bg-green-100 text-green-700 border border-green-300',
                offline: 'bg-gray-100 text-gray-700 border border-gray-300',
                warning: 'bg-yellow-100 text-yellow-700 border border-yellow-300'
            };
            return classes[status] || classes.offline;
        },

        getStatusText(status) {
            const texts = {online: '在线', offline: '离线', warning: '警告'};
            return texts[status] || '未知';
        },

        getPermissionByRole(role) {
            const permissionMap = {
                'admin': 'fullcontrol', // 管理员 -> 完全控制
                'user': 'readwrite',    // 普通用户 -> 读写
                'guest': 'readonly'     // 访客 -> 只读
            };
            return permissionMap[role] || 'readonly'; // 默认只读
        },
        async updateUserPermissions(user) {
    // 核心逻辑：根据用户选择的新角色，自动设置文件权限
    // 这一步会立即更新 user 对象，由于 1.html 中的 select 元素
    // 都使用了 v-model 绑定，文件权限的下拉框会立即显示新的权限。
    user.file_permission = this.getPermissionByRole(user.role);

    // 准备发送给后端的数据
    const userData = {
        id: user.id,
        role: user.role,
        file_permission: user.file_permission,
        email: user.email,
        status: user.status
        // ... 包含所有需要更新的字段
    };

    try {
        // 假设这是更新用户权限的 API
        const res = await axios.put(
            `${this.apiBaseUrl}/api/users/${user.id}`,
            userData
        );

        if (res.data.success) {
            // console.log(`用户 ${user.username} 权限已更新。`);
        }
    } catch (error) {
        console.error('更新用户权限失败:', error);
        alert(error.response?.data?.error || '更新用户权限失败');
        // 可选：如果更新失败，可以考虑回滚 user 对象的数据
    }
},

        // ============ 空间分配 ============
        openSpaceAllocation() {
            this.createWindow({
                type: 'space-allocation',
                title: '空间分配',
                icon: '📦',
                width: 1000,
                height: 700
            });
        },

        // ============ 权限设置 ============
        openPermissionSettings() {
            const win = this.createWindow({
                type: 'permissions',
                title: '权限管理',
                icon: '🔒',
                width: 1100,
                height: 700,
                users: [],
                nodes: [],
                groups: [],
                nodePolicies: {}, // 用于存储节点访问策略
                permissionTab: 'users', // 默认显示用户权限标签页
                loading: true
            });
            this.loadPermissionData(win);
        },


        async loadPermissionData(window) {
    try {
        window.loading = true;

        const [usersRes, nodesRes, groupsRes] = await Promise.all([
            axios.get(`${this.apiBaseUrl}/api/users`),
            axios.get(`${this.apiBaseUrl}/api/nodes`),
            axios.get(`${this.apiBaseUrl}/api/node-groups`)
        ]);

        // 用户列表
        window.users = usersRes.data.map(user => {
            const mappedUser = {
                ...user,
                node_access: typeof user.node_access === 'string'
                    ? JSON.parse(user.node_access)
                    : user.node_access
            };

            // 【新增的关键逻辑】在数据加载时，如果文件权限为空，则根据角色设置默认权限
            // 这解决了在用户列表第一次加载时，“文件权限”下拉菜单显示空白的问题。
            if (!mappedUser.file_permission) {
                 // 假设 this.getPermissionByRole(role) 方法已存在于 Vue 实例的 methods 中
                 mappedUser.file_permission = this.getPermissionByRole(mappedUser.role);
            }

            return mappedUser;
        });


        // 节点列表
        window.nodes = nodesRes.data;
        // 同时更新到 availableNodes 供对话框使用
        this.availableNodes = window.nodes;

        // 分组列表
       // 分组列表 - 统一字段名
window.groups = groupsRes.data.map(group => ({
    id: group.group_id,           // 统一为 id
    group_id: group.group_id,     // 保留原字段供删除用
    name: group.group_name,       // 统一为 name
    description: group.description,
    icon: group.icon,
    nodes: group.node_ids || []   // 统一为 nodes
}));

        // 初始化标签页
        if (!window.permissionTab) {
            window.permissionTab = 'users';
        }

        window.loading = false;
    } catch (error) {
        console.error('加载权限数据失败:', error);
        window.error = '加载数据失败';
        window.loading = false;
    }

},

// 用于保存 "角色" 和 "文件权限"
    async updateUserPermissions(user) {
        try {
            await axios.put(`${this.apiBaseUrl}/api/users/${user.id}`, {
                role: user.role,
                email: user.email, // 确保其他数据也一并提交
                status: user.status,
                file_permission: user.file_permission // 提交新字段
            });
            // 可以在这里加一个小的成功提示
        } catch (error) {
            console.error('更新用户权限失败:', error);
            alert('更新失败');
        }
    },


    // ============ 加密管理 ============
   openEncryptionManager() {
  const win = this.createWindow({
    type: 'encryption',
    title: '加密管理',
    icon: '🔐',
    width: 1100,
    height: 700,
    encryptionView: 'overview',  // 新增: 当前视图层级
    nodes: [],
    selectedNodeId: null,
    selectedNodeName: null,
    encryptionDisks: [],
    loading: false,
  });

  this.loadEncryptionNodes(win); // 加载节点
},

// 点击节点，进入磁盘加密页
async openEncryptionDetail(window, node) {
  window.encryptionView = 'detail';
  window.selectedNodeId = node.id;
  window.selectedNodeName = node.name;
  await this.loadEncryptionDisks(window);
},

// 返回节点列表
returnToEncryptionOverview(window) {
  window.encryptionView = 'overview';
  window.selectedNodeId = null;
  window.encryptionDisks = [];
},



    // ============ 纠删码配置 ============
    openECConfig() {
        alert('纠删码配置功能开发中...');
    },


    // ============ 系统监控 ============
    openSystemMonitor() {
        const win = this.createWindow({
            type: 'system-monitor',
            title: '系统监控',
            icon: '📊',
            width: 1000,
            height: 700,
            // 👇 新增状态
            monitorView: 'overview', // 'overview' 或 'detail'
            nodes: [],
            selectedNodeId: null,
            selectedNodeStats: null,
            loading: true,
        });
        this.loadMonitorOverview(win); // 调用新的加载函数
        this.showStartMenu = false;
    },


async fetchNodeMonitorStats(nodeId) {
    try {
        console.log('=== (自动刷新) 获取节点监控数据 ===', nodeId);
        const response = await axios.get(`${this.apiBaseUrl}/api/nodes/${nodeId}/monitor-stats`);
        const data = response.data;
        console.log('返回数据:', data);

        const monitorWindow = this.windows.find(w => w.type === 'system-monitor' && w.monitorView === 'detail');
        if (monitorWindow && monitorWindow.selectedNodeId === nodeId) {
            monitorWindow.selectedNodeStats = { ...data };  // 使用展开运算符
            monitorWindow.loading = false;
            console.log('已更新窗口数据:', monitorWindow.selectedNodeStats); // 添加调试日志
        }
    } catch (error) {
        console.error('获取失败:', error);
    }
},

refreshNodeMonitorStats() {
  const monitorWindow = this.windows.find(w => w.type === 'monitor' && w.monitorView === 'detail');
  if (monitorWindow && monitorWindow.selectedNode) {
    this.fetchNodeMonitorStats(monitorWindow.selectedNode);
  }
},

// [新] 打开文件管理器
    openFileExplorer() {
        const win = this.createWindow({
            type: 'file-explorer',
            title: '文件管理器',
            icon: '🗂️',
            width: 900,
            height: 600,
            // 窗口状态
            loading: true,
            nodes: [], // 用于节点选择
            selectedNodeId: null, // 当前选择的节点
            currentPath: '/',
            files: [],
            error: null
        });
        // 加载节点列表, 然后加载文件
        this.loadNodesForFileExplorer(win);
    },

// [新] 为文件管理器加载节点列表 (复用 /api/nodes 接口)
    async loadNodesForFileExplorer(window) {
        window.loading = true;
        try {
            // 复用您已有的 /api/nodes 接口
            const res = await axios.get(`${this.apiBaseUrl}/api/nodes`);
            // 我们只显示在线的节点
            window.nodes = res.data.filter(n => n.status === 'online');

            if (window.nodes.length > 0) {
                // 自动选择第一个在线节点
                window.selectedNodeId = window.nodes[0].id;
                // 加载根目录文件
                await this.loadFiles(window, '/');
            } else {
                window.error = "没有在线的节点";
                window.loading = false;
            }
        } catch (e) {
            window.error = "加载节点列表失败";
            window.loading = false;
        }
    },

// [新] 加载文件列表 (调用我们的新网关API)
    async loadFiles(window, path) {
        window.loading = true;
        window.error = null;
        window.currentPath = path;
        try {
            // 调用 app.py 中新的 /api/files/.../list 接口
            const res = await axios.get(`${this.apiBaseUrl}/api/files/${window.selectedNodeId}/list`, {
                params: {path: path}
            });
            window.files = res.data.files;
        } catch (error) {
            console.error("加载文件列表失败:", error);
            // 这将显示来自 app.py 的 "权限不足" 错误
            window.error = error.response?.data?.message || "加载文件列表失败";
        } finally {
            window.loading = false;
        }
    },

// [新] 删除文件 (调用我们的新网关API)
    async deleteFile(window, file) {
        // 拼接完整路径
        const path = (window.currentPath === '/' ? '' : window.currentPath) + '/' + file.name;

        if (!confirm(`确定要删除 ${path} 吗？\n\n此操作将根据您的 '完全控制' 权限 来决定是否成功。`)) return;

        try {
            // 调用 app.py 中新的 /api/files/.../delete 接口
            await axios.post(`${this.apiBaseUrl}/api/files/${window.selectedNodeId}/delete`, {
                path: path
            });
            alert('删除成功');
            await this.loadFiles(window, window.currentPath); // 刷新
        } catch (error) {
            console.error("删除失败:", error);
            // 显示 "权限不足"
            alert('删除失败: ' + (error.response?.data?.message || error.message));
        }
    },

// [新] 创建文件夹 (调用我们的新网关API)
    async mkdirInFileExplorer(window) {
        const folderName = prompt("请输入新文件夹名称:");
        if (!folderName) return;

        // 检查非法字符 (简化版)
        if (folderName.includes('/') || folderName.includes('\\')) {
            alert('文件夹名称不能包含 / 或 \\');
            return;
        }

        const path = (window.currentPath === '/' ? '' : window.currentPath) + '/' + folderName;

        try {
            // 调用 app.py 中新的 /api/files/.../mkdir 接口
            await axios.post(`${this.apiBaseUrl}/api/files/${window.selectedNodeId}/mkdir`, {
                path: path
            });
            alert('文件夹创建成功');
            await this.loadFiles(window, window.currentPath); // 刷新
        } catch (error) {
            console.error("创建文件夹失败:", error);
            // 显示 "权限不足" (如果您设置为 'readwrite')
            alert('创建失败: ' + (error.response?.data?.message || error.message));
        }
    },

    async loadMonitorOverview(window) {
        window.loading = true;
        try {
            const res = await axios.get(`${this.apiBaseUrl}/api/nodes`);
            // 只显示在线的节点
            window.nodes = res.data.filter(n => n.status === 'online');
        } catch (error) {
            console.error('加载监控节点列表失败:', error);
            alert('加载监控节点列表失败');
        } finally {
            window.loading = false;
        }
    },

    async selectNodeForMonitor(window, node) {
    window.loading = true;
    window.selectedNodeId = node.id;
    window.title = `系统监控 - ${node.name}`;
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/monitor-stats`);
        // 使用 Vue.set 或者直接赋值触发响应式更新
        window.selectedNodeStats = { ...res.data };  // 使用展开运算符创建新对象
        window.monitorView = 'detail';
        console.log('设置监控数据:', window.selectedNodeStats); // 添加调试日志
    } catch (error) {
        console.error('加载节点详细监控数据失败:', error);
        alert('加载节点详细监控数据失败');
        window.selectedNodeId = null;
    } finally {
        window.loading = false;
    }
},

    returnToMonitorOverview(window) {
        window.monitorView = 'overview';
        window.selectedNodeId = null;
        window.selectedNodeStats = null;
        window.title = '系统监控'; // 恢复窗口标题
    },
    toggleStartMenu() {
        this.showStartMenu = !this.showStartMenu;
    },

    returnToMainCenter() {
        this.showNavbar = false;
        this.currentNodeName = 'NAS Center 主控';
        alert('已返回主控中心');
    },
    async checkAuth() {
        try {
            const response = await axios.get(`${this.apiBaseUrl}/api/check-auth`);
            if (response.data.authenticated) {
                this.currentUser = response.data.user;
            } else {
                window.location.href = '/login.html';
            }
        } catch (error) {
            window.location.href = '/login.html';
        }
    },
// 用户管理相关方法
    async openUserManagement() {
        if (this.currentUser?.role !== 'admin') {
            alert('您没有权限访问用户管理');
            return;
        }

        const win = this.createWindow({
            type: 'user-management',
            title: '用户管理',
            icon: '👥',
            width: 1100,
            height: 600,
            users: [],
            loading: false
        });

        await this.loadUsers(win);
    },


    async loadUsers(window) {
        window.loading = true;
        try {
            const response = await axios.get(`${this.apiBaseUrl}/api/users`);
            window.users = response.data;
        } catch (error) {
            console.error('加载用户失败:', error);
            alert('加载用户列表失败');
        } finally {
            window.loading = false;
        }
    },


    async createUser(window) {
        const username = prompt('请输入新用户名:');
        if (!username) return;

        const password = prompt(`请输入 ${username} 的密码:`);
        if (!password) return;

        const email = prompt(`(可选) 请输入 ${username} 的邮箱:`);

        // 👇 【修改】允许选择 'guest' 角色
        const role = prompt("请输入角色 (admin, user 或 guest):", "user");
        if (role !== 'admin' && role !== 'user' && role !== 'guest') {
            alert("角色必须是 'admin', 'user' 或 'guest'");
            return;
        }

        const userData = {
            username: username,
            password: password,
            email: email || '',
            role: role,
            // 👇 【新增】根据角色自动设置文件权限
            file_permission: this.getPermissionByRole(role)
        };

        try {
            await axios.post(`${this.apiBaseUrl}/api/users`, userData);
            alert('用户创建成功');
            await this.loadUsers(window); // 重新加载用户
        } catch (error) {
            alert('创建用户失败: ' + (error.response?.data?.message || error.message));
        }
    },

// 👇 [替换] 使用这个新的 updateUser 方法
    async updateUser(window, user) {
        const email = prompt(`请输入 ${user.username} 的新邮箱:`, user.email);
        // 👇 【修改】允许输入 'guest'
        const role = prompt(`请输入 ${user.username} 的新角色 (admin, user 或 guest):`, user.role);
        const status = prompt(`请输入 ${user.username} 的状态 (active 或 deleted):`, user.status);

        // 👇 【修改】校验角色
        if (!role || (role !== 'admin' && role !== 'user' && role !== 'guest')) {
            alert("角色必须是 'admin', 'user' 或 'guest'");
            return;
        }

        if (!status || (status !== 'active' && status !== 'deleted')) {
            alert("状态必须是 'active' 或 'deleted'");
            return;
        }

        const userData = {
            email: email || '',
            role: role,
            status: status,
            // 👇 【新增】根据新角色自动设置文件权限
            file_permission: this.getPermissionByRole(role)
        };

        try {
            await axios.put(`${this.apiBaseUrl}/api/users/${user.id}`, userData);
            alert('用户更新成功');
            await this.loadUsers(window); // 重新加载用户
        } catch (error) {
            alert('更新用户失败: ' + (error.response?.data?.message || error.message));
        }
    },

    async deleteUser(window, user) {
        if (!confirm(`确定要删除用户 ${user.username} 吗？`)) return;

        try {
            await axios.delete(`${this.apiBaseUrl}/api/users/${user.id}`);
            alert('用户已删除');
            await this.loadUsers(window);
        } catch (error) {
            alert('删除用户失败: ' + (error.response?.data?.message || error.message));
        }
    },

// 修改密码功能
    async openChangePassword() {
        const newPassword = prompt('请输入新密码:');
        if (!newPassword) return;

        const confirmPassword = prompt('请再次确认新密码:');
        if (newPassword !== confirmPassword) {
            alert('两次输入的密码不一致');
            return;
        }

        try {
            await axios.put(`${this.apiBaseUrl}/api/users/${this.currentUser.id}/password`, {
                password: newPassword
            });
            alert('密码修改成功，请重新登录');
            this.logout();
        } catch (error) {
            alert('修改密码失败: ' + (error.response?.data?.message || error.message));
        }
    },
    openUserProfile() {
        alert('个人信息功能开发中...');
        // 您也可以在这里调用 this.createWindow(...) 来打开一个新窗口
        this.showStartMenu = false; // 确保菜单关闭
    },
    async logout() {
        if (confirm('确定要退出登录吗？')) {
            try {
                await axios.post(`${this.apiBaseUrl}/api/logout`);
                window.location.href = '/login.html';
            } catch (error) {
                console.error('退出失败:', error);
            }
        }
    },



// ============ 加密管理逻辑 ============
// 加载节点列表
async loadEncryptionNodes(window) {
  try {
    const res = await axios.get(`${this.apiBaseUrl}/api/nodes`);
    window.nodes = res.data;
    if (window.nodes.length > 0) {
      window.selectedNodeId = window.nodes[0].id;
      await this.loadEncryptionDisks(window);
    }
  } catch (err) {
    alert('加载节点列表失败');
  }
},

// 根据节点加载磁盘
async loadEncryptionDisks(window) {
  if (!window.selectedNodeId) return;
  window.loading = true;
  try {
    const res = await axios.get(`${this.apiBaseUrl}/api/encryption/disks`, {
      params: { node_id: window.selectedNodeId }
    });
    window.encryptionDisks = res.data.disks;
  } catch (err) {
    console.error('加载磁盘加密状态失败:', err);
    alert('加载磁盘加密状态失败');
  } finally {
    window.loading = false;
  }
},



// 执行磁盘加密
async encryptDisk(window, nodeId, mount) {
  const password = prompt(`请输入为磁盘 ${mount} 设置的密码：`);
  if (!password) return;
  try {
    const res = await axios.post(`${this.apiBaseUrl}/api/encryption/disk/encrypt`, {
      node_id: nodeId,
      mount,
      password
    });
    if (res.data.success) {
      alert('磁盘加密已启用');
      await this.loadEncryptionDisks(window);
    }
  } catch (err) {
    alert('加密失败: ' + (err.response?.data?.error || err.message));
  }
},

// 解锁磁盘
async unlockDisk(window, nodeId, mount) {
  const password = prompt(`请输入磁盘 ${mount} 的解锁密码：`);
  if (!password) return;
  try {
    const res = await axios.post(`${this.apiBaseUrl}/api/encryption/disk/unlock`, {
      node_id: nodeId,
      mount,
      password
    });
    if (res.data.success) {
      alert('磁盘已解锁');
      await this.loadEncryptionDisks(window);
    }
  } catch (err) {
    alert('解锁失败: ' + (err.response?.data?.error || err.message));
  }
},

async lockDisk(window, nodeId, mount) {
  try {
    const res = await axios.post(`${this.apiBaseUrl}/api/encryption/disk/lock`, {
      node_id: nodeId,
      mount: mount
    });
    if (res.data.success) {
      alert('磁盘已锁定');
      await this.loadEncryptionDisks(window);
    } else {
      alert(res.data.error || '锁定失败');
    }
  } catch (error) {
    alert('请求失败');
  }
},

async decryptDisk(window, nodeId, mount) {
  // 1. 先提示用户输入密码
  const password = prompt("⚠️ 请输入加密密码以永久解密此磁盘:\n\n解密后数据将不再受加密保护！");
  if (!password) return;  // 用户取消

  // 2. 确认操作
  if (!confirm(`确认要使用密码永久解密磁盘 ${mount} 吗？\n\n此操作不可逆！`)) return;

  try {
    const res = await axios.post(`${this.apiBaseUrl}/api/encryption/disk/decrypt`, {
      node_id: nodeId,
      mount: mount,
      password: password  // ✅ 现在有定义了
    });
    if (res.data.success) {
      alert('✅ 磁盘已永久解密');
      await this.loadEncryptionDisks(window);
    } else {
      alert('❌ ' + (res.data.error || '解密失败'));
    }
  } catch (error) {
    console.error('解密请求失败:', error);
    alert('❌ 请求失败: ' + (error.response?.data?.error || error.message));
  }
},


openCreateGroupDialog() {
    // 1. 重置 groupForm 为初始创建状态
    this.groupForm = {
        id: null,
        name: '',
        description: '',
        icon: '📁', // 默认图标
        nodes: [] // 清空已选择的节点
    };

    // 2. 设置对话框模式
    this.groupDialogMode = 'create';

    // 3. 准备可用节点列表
    // 从 permissions 窗口中获取所有节点列表。
    // loadPermissionData 应该已经将数据加载到这个 window 对象中。
    const window = this.windows.find(w => w.type === 'permissions');
    if (window) {
        // 使用 || [] 确保即使 window.nodes 尚未加载或为 null/undefined，
        // availableNodes 也能安全地初始化为一个空数组，防止错误。
        this.availableNodes = window.nodes || [];
    } else {
        // 如果权限窗口没找到，也确保 availableNodes 是一个空数组
        this.availableNodes = [];
        console.warn('未找到权限管理窗口 (type: permissions)');
    }

    // 4. 显示对话框
    this.showGroupDialog = true;
},

// ... 其他 methods ...


    openEditGroupDialog(window, group) {
        this.groupDialogMode = 'edit';
        this.groupForm = {
            id: group.group_id || group.id,
            name: group.name,
            description: group.description || '',
            icon: group.icon || '📁',
            nodes: Array.isArray(group.nodes) ? [...group.nodes] : (group.nodes ? JSON.parse(group.nodes) : [])
        };
        this.availableNodes = window.nodes || [];
        this.showGroupDialog = true;
    },


    closeGroupDialog() {
        this.showGroupDialog = false;
        this.groupForm = {
            id: null,
            name: '',
            description: '',
            icon: '📁',
            nodes: []
        };
    },


    async saveNodeGroup() {
        if (!this.groupForm.name || !this.groupForm.name.trim()) {
            alert('请输入分组名称');
            return;
        }

        try {
            if (this.groupDialogMode === 'create') {
                // 创建分组
                // 创建分组
// 创建分组
const res = await axios.post(`${this.apiBaseUrl}/api/node-groups`, {
    group_name: this.groupForm.name,
    description: this.groupForm.description,
    icon: this.groupForm.icon,
    node_ids: this.groupForm.nodes  // 改成 node_ids
});

                if (res.data.success) {
                    alert('分组创建成功');
                    this.closeGroupDialog();

                    // 刷新分组列表
                    const window = this.windows.find(w => w.type === 'permissions');
                    if (window) {
                        await this.loadPermissionData(window);
                    }
                }
            } else {
            // 更新分组
const res = await axios.put(
    `${this.apiBaseUrl}/api/node-groups/${this.groupForm.id}`,
    {
        group_name: this.groupForm.name,
        description: this.groupForm.description,
        icon: this.groupForm.icon,
        node_ids: this.groupForm.nodes  // 改成 node_ids
    }
);

                if (res.data.success) {
                    alert('分组更新成功');
                    this.closeGroupDialog();

                    // 刷新分组列表
                    const window = this.windows.find(w => w.type === 'permissions');
                    if (window) {
                        await this.loadPermissionData(window);
                    }
                }
            }
        } catch (error) {
            console.error('保存分组失败:', error);
            alert(error.response?.data?.error || '保存分组失败');
        }
    },

    async deleteNodeGroup(window, group) {
        if (!confirm(`确定要删除分组 "${group.name}" 吗?\n\n删除后,使用此分组的用户将无法访问相关节点。`)) {
            return;
        }

        try {
            const res = await axios.delete(`${this.apiBaseUrl}/api/node-groups/${group.group_id || group.id}`);

            if (res.data.success) {
                alert('分组删除成功');
                await this.loadPermissionData(window);
            }
        } catch (error) {
            console.error('删除分组失败:', error);
            alert(error.response?.data?.error || '删除分组失败');
        }
    },


    getNodeName(nodeId) {
        const node = this.availableNodes.find(n => n.id === nodeId);
        return node ? node.name : nodeId;
    },

    // ============================================
    // 用户节点权限管理
    // ============================================


    async openUserAccessDetail(user) {
        this.currentEditUser = user;

        // 解析用户的 node_access
        const nodeAccess = user.node_access;
        this.userAccessForm = {
            type: nodeAccess.type || 'all',
            allowed_groups: nodeAccess.allowed_groups || [],
            allowed_nodes: nodeAccess.allowed_nodes || [],
            denied_nodes: nodeAccess.denied_nodes || []
        };

        // 获取所有分组和节点
        const window = this.windows.find(w => w.type === 'permissions');
        if (window) {
            this.availableNodes = window.nodes || [];
        }

        this.showUserAccessDialog = true;
    },


    closeUserAccessDialog() {
        this.showUserAccessDialog = false;
        this.currentEditUser = null;
        this.userAccessForm = {
            type: 'all',
            allowed_groups: [],
            allowed_nodes: [],
            denied_nodes: []
        };
    },


    async saveUserNodeAccess() {
        if (!this.currentEditUser) return;

        try {
            const res = await axios.put(
                `${this.apiBaseUrl}/api/users/${this.currentEditUser.id}/node-access`,
                this.userAccessForm
            );

            if (res.data.success) {
                alert('权限更新成功');

                // 更新本地数据
                this.currentEditUser.node_access = {...this.userAccessForm};

                this.closeUserAccessDialog();
            }
        } catch (error) {
            console.error('更新权限失败:', error);
            alert(error.response?.data?.error || '更新权限失败');
        }
    },

    async updateUserNodeAccess(user) {
        // 如果改为 'all',清空其他配置
        if (user.node_access.type === 'all') {
            user.node_access.allowed_groups = [];
            user.node_access.allowed_nodes = [];
            user.node_access.denied_nodes = [];
        }

        // 如果改为 'groups',打开详细配置
        if (user.node_access.type === 'groups' || user.node_access.type === 'custom') {
            this.openUserAccessDetail(user);
        } else {
            // 直接保存
            try {
                await axios.put(
                    `${this.apiBaseUrl}/api/users/${user.id}/node-access`,
                    user.node_access
                );
            } catch (error) {
                console.error('更新节点访问权限失败:', error);
            }
        }
    },

    toggleUserMenu() {
    this.showUserMenu = !this.showUserMenu;
  },

  refreshCurrentNode() {
    alert(`刷新节点: ${this.currentNodeName}`);
  }

     }

}).mount('#app');