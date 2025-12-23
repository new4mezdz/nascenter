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
            helpContent: helpContent,

            // 个人信息
showProfileDialog: false,
profileForm: {
    username: '',
    email: '',
    role: '',
    avatar: '',
    created_at: ''
},

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
            showSecretDialog: false, // 控制密钥弹窗显示
    newSecretValue: '',      // 绑定的新密钥输入值
    showSecretPlain: false,  // 控制密钥明文显示
            whitelistUsers: [],
allUsersForWhitelist: [],

            // 用户节点权限对话框
            showUserAccessDialog: false,
            currentEditUser: null,
            userAccessForm: {
                type: 'all',
                allowed_groups: [],
                allowed_nodes: [],
                denied_nodes: []
            },
                desktopBackground: localStorage.getItem('desktopBackground') || '',
            showBackgroundDialog: false,
            backgroundUrl: '',
            backgroundFile: null,
            // 关于和帮助
            showAboutDialog: false,
            showHelpDialog: false
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
    const isMobile = window.innerWidth <= 768;
    const win = {
        id: this.nextWindowId++,
        x: isMobile ? 0 : 100 + (this.windows.length * 30),
        y: isMobile ? 0 : 50 + (this.windows.length * 30),
        width: isMobile ? window.innerWidth : (config.width || 900),
        height: isMobile ? window.innerHeight - 100 : (config.height || 600),
        zIndex: this.maxZIndex++,
        maximized: isMobile, // 手机端默认最大化
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
            if (window.maximized || window.innerWidth <= 768) return; // 添加移动端判断
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



async renameNode(window, node) {
    const newName = prompt('请输入新的节点名称:', node.name);

    if (!newName) {
        return; // 用户取消
    }

    if (newName === node.name) {
        alert('名称未改变');
        return;
    }

    if (newName.trim().length === 0) {
        alert('节点名称不能为空');
        return;
    }

    try {
        const response = await axios.put(
            `${this.apiBaseUrl}/api/nodes/${node.id}/rename`,
            { new_name: newName }
        );

        if (response.data.success) {
            alert(`节点改名成功: ${response.data.old_name} → ${response.data.new_name}`);
            // 刷新节点列表
            this.loadNodesData(window);
        }
    } catch (error) {
        alert('改名失败: ' + (error.response?.data?.error || error.message));
    }
},
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




async deleteNode(window, node) {
    const confirmMsg = `确定要删除节点 "${node.name}" 吗？\n\n⚠️ 此操作将从管理中心移除该节点的配置信息。`;

    if (!confirm(confirmMsg)) {
        return;
    }

    // 二次确认
    const doubleConfirm = prompt(`请输入节点名称 "${node.name}" 以确认删除:`);
    if (doubleConfirm !== node.name) {
        alert('节点名称不匹配，取消删除');
        return;
    }

    try {
        const response = await axios.delete(
            `${this.apiBaseUrl}/api/nodes/${node.id}`
        );

        if (response.data.success) {
            alert(`✅ 节点 "${node.name}" 已成功删除`);
            this.loadNodesData(window);
        }
    } catch (error) {
        alert('删除失败: ' + (error.response?.data?.error || error.message));
    }
},

  async accessNode(node) {
    if (node.status === 'offline') {
        alert(`节点 ${node.name} 当前离线,无法访问`);
        return;
    }

    console.log('[DEBUG] 开始访问节点:', node.id);

    try {
        // 1. 向管理端请求生成访问令牌
        const response = await axios.post(`${this.apiBaseUrl}/api/generate-node-access-token`, {
            node_id: node.id
        }, {
            withCredentials: true
        });

        if (response.data.success) {
            const token = response.data.token;

            // 2. 👇 关键修改:通过管理端代理访问,而不是直接访问节点内网IP
            const proxyUrl = `${this.apiBaseUrl}/proxy/node/${node.id}/desktop?token=${token}`;

            console.log('[DEBUG] 代理访问URL:', proxyUrl);

            // 3. 检测设备类型
            const isMobile = window.innerWidth <= 768;

            // 4. 直接跳转
            if (isMobile) {
                window.location.href = proxyUrl;
            } else {
                const newWindow = window.open(proxyUrl, '_blank');
                if (!newWindow) {
                    alert('请允许浏览器弹窗,或点击地址栏的弹窗拦截图标允许弹窗后重试');
                }
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

                console.log('[DEBUG] 磁盘信息响应:', response.data);

                if (response.data && response.data.disks) {
                    window.selectedNodeDisks.disks = response.data.disks;
                    window.selectedNodeDisks.loading = false;
                } else {
                    throw new Error(response.data?.error || '获取磁盘信息失败');
                }
            } catch (error) {
                console.error('[ERROR] 获取磁盘信息失败:', error);
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
    const win = this.createWindow({
        type: 'space-allocation',
        title: '空间分配',
        icon: '📦',
        width: 1100,
        height: 750,
        spaceTab: 'cross-node',
        // 节点相关
        allNodes: [],
        selectedPoolNode: null,
        // 存储池相关
        poolStatus: null,
        poolVolumes: [],
        poolHealth: [],
        availableDisks: [],
        poolLoading: false,
        // 逻辑卷表单
        showVolumeDialog: false,
        volumeForm: { name: '', display_name: '', icon: '📁', strategy: 'largest_free' },
        volumeEditMode: false,
        // 添加磁盘
        showAddDiskDialog: false,
        selectedNewDisk: null
    });
    this.loadNodesForSpaceAllocation(win);
},

// 加载节点列表
async loadNodesForSpaceAllocation(win) {
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/nodes`);
        win.allNodes = res.data || [];
    } catch (e) {
        console.error('加载节点失败', e);
        win.allNodes = [];
    }
},

// 选择节点查看存储池
async selectNodeForPool(win, node) {
    win.selectedPoolNode = node;
    win.poolLoading = true;
    win.poolStatus = null;
    win.poolVolumes = [];
    try {
        const [statusRes, volumesRes, healthRes] = await Promise.all([
            axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/pool/status`),
            axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/pool/volumes`),
            axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/pool/health`)
        ]);
        win.poolStatus = statusRes.data;
        // 把字典转成数组
const volumesData = volumesRes.data || {};
win.poolVolumes = Object.entries(volumesData).map(([name, vol]) => ({
    name: name,
    ...vol
}));
        win.poolHealth = healthRes.data || [];
    } catch (e) {
        console.error('加载存储池数据失败', e);
        win.poolStatus = { error: e.response?.data?.error || '无法连接节点或该节点未配置存储池' };
    }
    win.poolLoading = false;
},

// 刷新当前节点存储池
async refreshNodePool(win) {
    if (win.selectedPoolNode) {
        await this.selectNodeForPool(win, win.selectedPoolNode);
    }
},

// 加载可用磁盘
async loadAvailableDisks(win) {
    if (!win.selectedPoolNode) return;
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/nodes/${win.selectedPoolNode.id}/proxy/pool/available-disks`);
        win.availableDisks = res.data || [];
    } catch (e) {
        console.error('加载可用磁盘失败', e);
        win.availableDisks = [];
    }
},

// 打开添加磁盘对话框
async openAddDiskDialog(win) {
    await this.loadAvailableDisks(win);
    win.selectedNewDisk = null;
    win.showAddDiskDialog = true;
},

// 添加磁盘到存储池
async addDiskToPool(win) {
    if (!win.selectedNewDisk) {
        alert('请选择要添加的磁盘');
        return;
    }
    try {
        await axios.post(`${this.apiBaseUrl}/api/nodes/${win.selectedPoolNode.id}/proxy/pool/disk/add`, { disk: win.selectedNewDisk });
        alert('磁盘添加成功');
        win.showAddDiskDialog = false;
        this.refreshNodePool(win);
    } catch (e) {
        alert('添加失败: ' + (e.response?.data?.error || e.message));
    }
},

// 移除磁盘
async removeDiskFromPool(win, diskPath) {
    if (!confirm(`确定要从存储池移除磁盘 ${diskPath} 吗？\n数据将自动迁移到其他磁盘。`)) return;
    try {
        await axios.post(`${this.apiBaseUrl}/api/nodes/${win.selectedPoolNode.id}/proxy/pool/disk/remove`, { disk: diskPath, migrate: true });
        alert('磁盘移除成功');
        this.refreshNodePool(win);
    } catch (e) {
        alert('移除失败: ' + (e.response?.data?.error || e.message));
    }
},

// 重平衡存储池
async rebalancePool(win, dryRun = true) {
    try {
        const res = await axios.post(`${this.apiBaseUrl}/api/nodes/${win.selectedPoolNode.id}/proxy/pool/rebalance`, { dry_run: dryRun });
        if (dryRun) {
            const msg = res.data.moves?.length
                ? `预计迁移 ${res.data.moves.length} 个文件，确定执行？`
                : '当前数据分布已平衡，无需迁移';
            if (res.data.moves?.length && confirm(msg)) {
                await this.rebalancePool(win, false);
            } else {
                alert(msg);
            }
        } else {
            alert('重平衡完成');
            this.refreshNodePool(win);
        }
    } catch (e) {
        alert('重平衡失败: ' + (e.response?.data?.error || e.message));
    }
},

// 打开创建逻辑卷对话框
openCreateVolumeDialog(win) {
    win.volumeForm = { name: '', display_name: '', icon: '📁', strategy: 'largest_free' };
    win.volumeEditMode = false;
    win.showVolumeDialog = true;
},

// 打开编辑逻辑卷对话框
openEditVolumeDialog(win, vol) {
    win.volumeForm = {
        name: vol.name,
        display_name: vol.display_name,
        icon: vol.icon || '📁',
        strategy: vol.strategy || 'largest_free'
    };
    win.volumeEditMode = true;
    win.showVolumeDialog = true;
},

// 保存逻辑卷
async saveVolume(win) {
    const form = win.volumeForm;
    if (!form.name || !form.display_name) {
        alert('请填写卷名和显示名称');
        return;
    }
    try {
        if (win.volumeEditMode) {
            await axios.patch(`${this.apiBaseUrl}/api/nodes/${win.selectedPoolNode.id}/proxy/pool/volume/${form.name}`, {
                display_name: form.display_name,
                icon: form.icon,
                strategy: form.strategy
            });
        } else {
            await axios.post(`${this.apiBaseUrl}/api/nodes/${win.selectedPoolNode.id}/proxy/pool/volume/create`, form);
        }
        alert(win.volumeEditMode ? '更新成功' : '创建成功');
        win.showVolumeDialog = false;
        this.refreshNodePool(win);
    } catch (e) {
        alert('操作失败: ' + (e.response?.data?.error || e.message));
    }
},

// 删除逻辑卷
async deleteVolume(win, volName) {
    if (!confirm(`确定删除逻辑卷 "${volName}" 吗？此操作不可恢复！`)) return;
    try {
        await axios.delete(`${this.apiBaseUrl}/api/nodes/${win.selectedPoolNode.id}/proxy/pool/volume/${volName}?confirm=true`);
        alert('删除成功');
        this.refreshNodePool(win);
    } catch (e) {
        alert('删除失败: ' + (e.response?.data?.error || e.message));
    }
},

// 加载节点列表
async loadNodesForSpaceAllocation(win) {
    try {
        const res = await axios.get('/api/nodes');
        win.allNodes = res.data || [];
    } catch (e) {
        console.error('加载节点失败', e);
        win.allNodes = [];
    }
},

// 选择节点查看存储池
async selectNodeForPool(win, node) {
    win.selectedPoolNode = node;
    win.poolLoading = true;
    win.poolStatus = null;
    win.poolVolumes = [];
    try {
        const [statusRes, volumesRes, healthRes] = await Promise.all([
            axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/proxy/pool/status`),
            axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/proxy/pool/volumes`),
            axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/proxy/pool/health`)
        ]);
        win.poolStatus = statusRes.data;
        win.poolVolumes = volumesRes.data || [];
        win.poolHealth = healthRes.data || [];
    } catch (e) {
        console.error('加载存储池数据失败', e);
        win.poolStatus = { error: e.response?.data?.error || '无法连接节点或该节点未配置存储池' };
    }
    win.poolLoading = false;
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

        const [usersRes, nodesRes, groupsRes, whitelistRes] = await Promise.all([
    axios.get(`${this.apiBaseUrl}/api/users`),
    axios.get(`${this.apiBaseUrl}/api/nodes`),
    axios.get(`${this.apiBaseUrl}/api/node-groups`),
    axios.get(`${this.apiBaseUrl}/api/admin/whitelist`)
]);

// 白名单数据
this.whitelistUsers = whitelistRes.data.whitelist;
this.allUsersForWhitelist = usersRes.data.filter(u => u.role !== 'admin');

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


        openSecretDialog() {
    this.showSecretDialog = true;
    this.newSecretValue = ''; // 打开时清空输入框
    this.showSecretPlain = false;
},

async saveSecret() {
    if (!this.newSecretValue) {
        alert("密钥不能为空！");
        return;
    }

    if (!confirm("确定要修改通信密钥吗？\n修改后请务必同步更新所有节点的配置！")) {
        return;
    }

    try {
        const res = await axios.post('/api/admin/update-secret', {
            secret: this.newSecretValue
        });

        if (res.data.success) {
            alert("✅ " + res.data.message);
            this.showSecretDialog = false;
        }
    } catch (e) {
        console.error(e);
        const errorMsg = e.response?.data?.error || "请求失败";
        alert("❌ 修改失败: " + errorMsg);
    }
},

    // ============ 纠删码配置 ============
    openECConfig() {
    const existing = this.windows.find(w => w.type === 'ec-config');
    if (existing) {
        this.focusWindow(existing.id);
        this.showStartMenu = false;
        return;
    }

    const win = this.createWindow({
        type: 'ec-config',
        title: '纠删码配置',
        icon: '🛡️',
        width: 1000,
        height: 700,
        currentTab: 'config',  // 'config', 'status', 'recovery'
        ecConfig: null,
        capacity: null,
        availableDisks: [],
        nodes: [],           // 👈 新增
        selectedNodeId: '',  // 👈 新增
        loading: true,

        // 配置表单
        configForm: {
            k: 4,
            m: 2,
            disks: []
        }
    });

    this.loadECConfig(win);
    this.showStartMenu = false;
},

async loadECConfig(win) {
    win.loading = true;
    try {
        // 👇 先加载节点列表(这样下拉框就有数据了)
        const nodesRes = await axios.get(`${this.apiBaseUrl}/api/nodes`);
       win.nodes = nodesRes.data || [];  // 👈 直接使用 data,不是 data.nodes

        // 加载所有策略
        const policiesRes = await axios.get(`${this.apiBaseUrl}/api/ec_policies`);
        win.policies = policiesRes.data.policies || [];

        // 如果有选中的节点,加载该节点的配置
        if (win.selectedNodeId) {
            const res = await axios.get(`${this.apiBaseUrl}/api/nodes/${win.selectedNodeId}/ec_config`);
            win.ecConfig = res.data.config;
            win.capacity = res.data.capacity;

            // 加载可用磁盘
            const diskRes = await axios.get(`${this.apiBaseUrl}/api/nodes/${win.selectedNodeId}/disks`);
            win.availableDisks = diskRes.data.disks || [];
        } else {
            // 如果没有选中节点,清空配置
            win.ecConfig = null;
            win.capacity = null;
            win.availableDisks = [];
        }
    } catch (error) {
        console.error('加载纠删码配置失败:', error);
        alert('加载失败: ' + (error.response?.data?.error || error.message));
    } finally {
        win.loading = false;
    }
},

// 如果没有选中节点,不能保存配置
async saveECConfig(win) {
    if (!win.selectedNodeId) {
        alert('请先选择要配置的节点');
        return;
    }

    if (win.configForm.disks.length < win.configForm.k + win.configForm.m) {
        alert(`至少需要选择 ${win.configForm.k + win.configForm.m} 个磁盘`);
        return;
    }

    try {
        await axios.post(`${this.apiBaseUrl}/api/nodes/${win.selectedNodeId}/ec_config`, {
            scheme: 'rs',
            k: win.configForm.k,
            m: win.configForm.m,
            disks: win.configForm.disks
        });
        alert('纠删码配置保存成功!');
        this.loadECConfig(win);
    } catch (error) {
        alert('保存失败: ' + (error.response?.data?.error || error.message));
    }
},

async deleteECConfig(win) {
    if (!win.selectedNodeId) {
        alert('请先选择要配置的节点');
        return;
    }

    if (!confirm('确定要删除纠删码配置吗?这将清除所有纠删码数据!')) return;

    try {
        await axios.delete(`${this.apiBaseUrl}/api/nodes/${win.selectedNodeId}/ec_config`);
        alert('纠删码配置已删除');
        this.loadECConfig(win);
    } catch (error) {
        alert('删除失败: ' + (error.response?.data?.error || error.message));
    }
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
        window.selectedNodeStats = { ...res.data };

        // 获取磁盘详细信息
        const disksRes = await axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/disks`);
        window.selectedNodeDisks = disksRes.data.disks || [];

        window.monitorView = 'detail';
        console.log('设置监控数据:', window.selectedNodeStats);
        console.log('磁盘数据:', window.selectedNodeDisks);
    } catch (error) {
        console.error('加载节点详细监控数据失败:', error);
        alert('加载节点详细监控数据失败');
        window.selectedNodeId = null;
    } finally {
        window.loading = false;
    }
},

        formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
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

    async updateNodePolicy(nodeId, policy) {
    try {
        const res = await axios.put(
            `${this.apiBaseUrl}/api/node-policies/${nodeId}`,
            { policy: policy }
        );

        if (res.data.success) {
            // 更新本地数据
            if (!this.windows.find(w => w.type === 'node-control')) {
                const window = this.windows.find(w => w.type === 'node-control');
                if (window && window.nodePolicies) {
                    window.nodePolicies[nodeId] = policy;
                }
            }
            alert('节点访问策略已更新');
        }
    } catch (error) {
        console.error('更新节点策略失败:', error);
        alert('更新节点策略失败: ' + (error.response?.data?.error || error.message));
    }
},
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


async loadWhitelist() {
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/admin/whitelist`);
        this.whitelistUsers = res.data.whitelist;
    } catch (error) {
        console.error('加载白名单失败:', error);
    }
},

async loadAllUsersForWhitelist() {
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/users`);
        this.allUsersForWhitelist = res.data.users.filter(u => u.role !== 'admin');
    } catch (error) {
        console.error('加载用户列表失败:', error);
    }
},

async addToWhitelist(userId) {
    try {
        await axios.post(`${this.apiBaseUrl}/api/admin/whitelist`, { user_id: userId });
        await this.loadWhitelist();
    } catch (error) {
        alert(error.response?.data?.error || '添加失败');
    }
},

async removeFromWhitelist(userId) {
    if (!confirm('确定移除该用户？')) return;
    try {
        await axios.delete(`${this.apiBaseUrl}/api/admin/whitelist/${userId}`);
        await this.loadWhitelist();
    } catch (error) {
        alert('移除失败');
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
    async openUserProfile() {
    this.showStartMenu = false;
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/profile`);
        this.profileForm = {
            username: res.data.username,
            email: res.data.email || '',
            role: res.data.role,
            avatar: res.data.avatar || '',
            created_at: res.data.created_at || ''
        };
        this.showProfileDialog = true;
    } catch (error) {
        alert('获取个人信息失败: ' + (error.response?.data?.error || error.message));
    }
},

        async handleAvatarUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
        alert('请选择图片文件');
        return;
    }

    const formData = new FormData();
    formData.append('avatar', file);

    try {
        const res = await axios.post(`${this.apiBaseUrl}/api/avatar`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        if (res.data.success) {
            this.profileForm.avatar = res.data.avatar;
            // 同步更新当前用户信息
            if (this.currentUser) {
                this.currentUser.avatar = res.data.avatar;
            }
            alert('头像上传成功');
        }
    } catch (error) {
        alert('上传失败: ' + (error.response?.data?.error || error.message));
    }
},

async saveProfile() {
    try {
        const res = await axios.put(`${this.apiBaseUrl}/api/profile`, {
            email: this.profileForm.email
        });
        if (res.data.success) {
            // 更新当前用户信息
            if (this.currentUser) {
                this.currentUser.email = this.profileForm.email;
            }
            alert('保存成功');
            this.showProfileDialog = false;
        }
    } catch (error) {
        alert('保存失败: ' + (error.response?.data?.error || error.message));
    }
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

openAboutDialog() {
    this.showAboutDialog = true;
    this.showStartMenu = false;
  },

  openHelpDialog() {
    this.showHelpDialog = true;
    this.showStartMenu = false;
  },

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
  },
       // 背景图片设置
  openBackgroundDialog() {
    this.backgroundUrl = this.desktopBackground.startsWith('data:') ? '' : this.desktopBackground;
    this.backgroundFile = null;
    this.showBackgroundDialog = true;
    this.showStartMenu = false;
  },

  handleBackgroundFile(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      alert('请选择图片文件');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      this.backgroundFile = e.target.result;
      this.backgroundUrl = '';
    };
    reader.readAsDataURL(file);
  },

  setBackground() {
    const bg = this.backgroundFile || this.backgroundUrl;
    if (bg) {
      this.desktopBackground = bg;
      localStorage.setItem('desktopBackground', bg);
    }
    this.showBackgroundDialog = false;
  },

  resetBackground() {
    this.desktopBackground = '';
    this.backgroundUrl = '';
    this.backgroundFile = null;
    localStorage.removeItem('desktopBackground');
    this.showBackgroundDialog = false;
  }

     }

}).mount('#app');