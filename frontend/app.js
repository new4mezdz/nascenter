// 安全的存储包装器
const safeStorage = (function() {
    const fallback = {};
    let isAvailable = null;
    
    function checkAvailable() {
        if (isAvailable !== null) return isAvailable;
        try {
            const storage = window.localStorage;
            if (!storage) {
                isAvailable = false;
                return false;
            }
            const test = '__storage_test__';
            storage.setItem(test, test);
            storage.removeItem(test);
            isAvailable = true;
        } catch (e) {
            isAvailable = false;
        }
        return isAvailable;
    }
    
    return {
        getItem: function(key) {
            try {
                if (checkAvailable()) {
                    return window.localStorage.getItem(key);
                }
            } catch (e) {}
            return fallback[key] || null;
        },
        setItem: function(key, value) {
            try {
                if (checkAvailable()) {
                    window.localStorage.setItem(key, value);
                    return;
                }
            } catch (e) {}
            fallback[key] = value;
        },
        removeItem: function(key) {
            try {
                if (checkAvailable()) {
                    window.localStorage.removeItem(key);
                    return;
                }
            } catch (e) {}
            delete fallback[key];
        }
    };
})();
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
            excludedDrives: ['C:', 'D:', 'c:', 'd:', '/c', '/d', 'C', 'D'],
            // 跨节点池对话框
showCreatePoolDialog: false,
poolForm: { name: '', display_name: '', strategy: 'largest_free', disks: [] },
poolEditMode: false,
currentHelpChapter: 'quickstart',  // 当前选中的章节
            // 个人信息
showProfileDialog: false,
profileForm: {
    username: '',
    email: '',
    role: '',
    avatar: '',
    created_at: ''
},
            // 桌面图标
desktopIcons: JSON.parse(safeStorage.getItem('adminDesktopIcons')) || [
    { id: 'nodes', emoji: '🖥️', label: '节点管理', action: 'openNodeManagement', order: 0 },
    { id: 'space', emoji: '📦', label: '空间分配', action: 'openSpaceAllocation', order: 1 },
    { id: 'permission', emoji: '🔒', label: '权限设置', action: 'openPermissionSettings', order: 2 },
    { id: 'encryption', emoji: '🔐', label: '加密管理', action: 'openEncryptionManager', order: 3 },
    { id: 'ec', emoji: '🛡️', label: '纠删码配置', action: 'openECConfig', order: 4 },
    { id: 'files', emoji: '📁', label: '文件管理', action: 'openFileManager', order: 5 },
    { id: 'monitor', emoji: '📊', label: '系统监控', action: 'openSystemMonitor', order: 6 },
],
iconEditMode: false,
draggedIcon: null,
longPressTimer: null,

            // 客户端同步相关
showSyncClientDialog: false,
syncAvailableNodes: [],
syncFileList: [],
syncForm: {
    sourceNode: '',
    targetNodes: [],
    mode: 'full',
    selectedFiles: [],
    backup: true
},
syncProgress: {
    show: false,
    status: '',
    current: 0,
    total: 0,
    results: []
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

            // 跨节点EC相关
crossEcConfig: null,
crossEcForm: {
    k: 4,
    m: 2,
    selectedDisks: {}  // { nodeId: [disk1, disk2], ... }
},
            desktopBackground: safeStorage.getItem('desktopBackground') || '',
showBackgroundDialog: false,
backgroundUrl: '',
backgroundFile: null,

bgPresets: [
    { name: '紫罗兰', value: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' },
    { name: '海洋', value: 'linear-gradient(135deg, #2193b0 0%, #6dd5ed 100%)' },
    { name: '日落', value: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)' },
    { name: '森林', value: 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)' },
    { name: '暖阳', value: 'linear-gradient(135deg, #f2994a 0%, #f2c94c 100%)' },
    { name: '深空', value: 'linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%)' },
    { name: '玫瑰', value: 'linear-gradient(135deg, #ee9ca7 0%, #ffdde1 100%)' },
    { name: '极光', value: 'linear-gradient(135deg, #43cea2 0%, #185a9d 100%)' },
],
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

    // 每5秒刷新监控统计
    setInterval(() => {
        this.refreshNodeMonitorStats();
    }, 5000);

    // 每10秒自动刷新节点列表
    setInterval(() => {
        this.refreshAllWindowsData();
    }, 10000);
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



// 自动刷新所有窗口数据
refreshAllWindowsData() {
    this.windows.forEach(win => {
        if (win.minimized || win.loading) return;

        switch (win.type) {
            case 'nodes':
                this.loadNodesData(win);
                break;
            case 'permissions':
                this.loadPermissionData(win);
                break;
            case 'space-allocation':
                this.loadNodesForSpaceAllocation(win);
                this.loadCrossPools(win);
                break;
            case 'encryption':

                break;
            case 'ec-config':

                break;
            case 'file-manager':
    // 文件管理器不自动刷新，避免干扰用户操作
    // this.loadFmNodes(win);
    // if (win.selectedFmNode) {
    //     this.selectFmNode(win, win.selectedFmNode);
    // }
    break;
            case 'user-management':
                this.loadUsers(win);
                break;
        }
    });
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


// ========== 跨节点EC方法 ==========
countSelectedCrossDisks(window) {
    let count = 0;
    for (let nodeId in window.crossEcForm.selectedDisks) {
        count += window.crossEcForm.selectedDisks[nodeId].length;
    }
    return count;
},

getNodeSelectedDisks(window, nodeId) {
    return window.crossEcForm.selectedDisks[nodeId] || [];
},

getNodeName(window, nodeId) {
    const node = (window.allNodes || []).find(n => n.id === nodeId);
    return node ? node.name : nodeId;
},

async selectNodeForCrossEc(win, node) {
    win.selectedCrossEcNode = node;
    win.crossEcLoading = true;
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/disks`);
        win.crossEcNodeDisks = (res.data.disks || res.data || []).filter(d =>
            d.mount && !['C:/', 'D:/', '/'].includes(d.mount.toUpperCase().replace('\\', '/'))
        );
    } catch (e) {
        console.error('获取磁盘失败:', e);
        win.crossEcNodeDisks = [];
    }
    win.crossEcLoading = false;
},

isDiskSelectedForCrossEc(window, nodeId, diskObj) {
    const mount = typeof diskObj === 'string' ? diskObj : diskObj.mount;
    const selected = window.crossEcForm.selectedDisks[nodeId] || [];
    return selected.some(d => (typeof d === 'string' ? d : d.mount) === mount);
},

toggleDiskForCrossEc(window, nodeId, diskObj) {
    // diskObj 现在是完整的磁盘对象，包含 mount, volume_serial 等
    if (!window.crossEcForm.selectedDisks[nodeId]) {
        window.crossEcForm.selectedDisks[nodeId] = [];
    }

    const mount = typeof diskObj === 'string' ? diskObj : diskObj.mount;
    const serial = typeof diskObj === 'string' ? '' : (diskObj.volume_serial || diskObj.serial || '');

    const idx = window.crossEcForm.selectedDisks[nodeId].findIndex(d =>
        (typeof d === 'string' ? d : d.mount) === mount
    );

    if (idx >= 0) {
        window.crossEcForm.selectedDisks[nodeId].splice(idx, 1);
        if (window.crossEcForm.selectedDisks[nodeId].length === 0) {
            delete window.crossEcForm.selectedDisks[nodeId];
        }
    } else {
        window.crossEcForm.selectedDisks[nodeId].push({
            mount: mount,
            serial: serial
        });
    }
    // 触发响应式更新
    window.crossEcForm.selectedDisks = { ...window.crossEcForm.selectedDisks };
},
toggleAllDisksForNode(window, nodeId) {
    const allDisks = (window.crossEcNodeDisks || []).map(d => ({
        mount: d.mount,
        serial: d.volume_serial || d.serial || ''
    }));
    const selected = window.crossEcForm.selectedDisks[nodeId] || [];
    if (selected.length === allDisks.length) {
        delete window.crossEcForm.selectedDisks[nodeId];
    } else {
        window.crossEcForm.selectedDisks[nodeId] = [...allDisks];
    }
    window.crossEcForm.selectedDisks = { ...window.crossEcForm.selectedDisks };
},

async saveCrossEcConfig(window) {
    const nodes = [];
    for (let nodeId in window.crossEcForm.selectedDisks) {
        const node = (window.allNodes || []).find(n => n.id === nodeId);
        const diskList = window.crossEcForm.selectedDisks[nodeId] || [];

        // 转换磁盘格式，确保包含序列号
        const disks = diskList.map(d => {
            if (typeof d === 'string') {
                return { mount: d, serial: '' };
            }
            return { mount: d.mount, serial: d.serial || '' };
        });

        nodes.push({
            node_id: nodeId,
            nodeName: node?.name || nodeId,
            ip: node?.ip || '',
            disks: disks  // 现在是 [{ mount: 'F:', serial: 'xxx' }, ...]
        });
    }

    const totalDisks = this.countSelectedCrossDisks(window);
    if (totalDisks < window.crossEcForm.k + window.crossEcForm.m) {
        alert(`总磁盘数(${totalDisks})必须 >= k+m(${window.crossEcForm.k + window.crossEcForm.m})`);
        return;
    }

    try {
        const res = await axios.post('/api/cross_ec_config', {
            k: window.crossEcForm.k,
            m: window.crossEcForm.m,
            nodes
        });

        if (res.data.success) {
            window.crossEcConfig = {
                k: window.crossEcForm.k,
                m: window.crossEcForm.m,
                nodes,
                totalDisks,
                createdAt: new Date().toISOString()
            };
            alert('跨节点EC配置已保存！');
            await this.loadEcWindowData(window);
        } else {
            alert(res.data.error || '保存失败');
        }
    } catch (e) {
        alert('保存失败: ' + (e.response?.data?.error || e.message));
    }
},

        async loadCrossEcConfig(window) {
    try {
        const res = await axios.get('/api/cross_ec_config');
        if (res.data.success && res.data.config) {
            window.crossEcConfig = res.data.config;
        }
    } catch (e) {
        console.error('加载跨节点EC配置失败:', e);
    }
},
async deleteCrossEcConfig(window) {
    try {
        // 先检查是否有文件
        const filesRes = await axios.get(`${this.apiBaseUrl}/api/ec_files?type=cross`);
        const files = filesRes.data.files || [];
        const fileCount = files.length;

        let confirmMsg = '确定删除跨节点EC配置？';
        if (fileCount > 0) {
            confirmMsg = `⚠️ EC池中有 ${fileCount} 个文件！\n\n删除配置后这些文件的分片数据仍保留在各磁盘上，但将无法正常读取。\n\n建议先导出文件再删除配置。\n\n是否继续删除？`;
        }

        if (!confirm(confirmMsg)) return;

        // 询问是否导出文件
        if (fileCount > 0) {
            const exportFirst = confirm('是否先一键导出所有文件？\n\n点击"确定"开始导出，点击"取消"跳过导出');
            if (exportFirst) {
                await this.exportAllEcFiles('cross', null);
            }
        }

        // 询问是否删除分片
        let deleteShards = false;
        if (fileCount > 0) {
            deleteShards = confirm('是否同时删除各节点上的分片文件？\n\n点击"确定"删除分片（释放磁盘空间）\n点击"取消"仅删除配置（保留分片）');
        }

        const res = await axios.delete(`/api/cross_ec_config?delete_shards=${deleteShards}`);
        if (res.data.success) {
            window.crossEcConfig = null;
            let msg = '配置已删除';
            if (res.data.deleted_shards !== undefined) {
                msg += `\n已删除 ${res.data.deleted_shards} 个分片`;
            }
            if (res.data.shard_errors && res.data.shard_errors.length > 0) {
                msg += `\n${res.data.shard_errors.length} 个分片删除失败`;
            }
            if (res.data.pending_nodes && res.data.pending_nodes.length > 0) {
                msg += `\n${res.data.pending_nodes.length} 个离线节点将在上线后自动删除分片`;
            }
            alert(msg);
            await this.loadEcWindowData(window);
        }
    } catch (e) {
        alert('删除失败: ' + (e.response?.data?.error || e.message));
    }
},
// ========== 单节点EC方法 ==========
async selectNodeForSingleEc(win, node) {
    win.selectedSingleEcNode = node;
    win.singleEcLoading = true;
    win.singleEcConfig = null;
    win.singleEcForm = { k: 4, m: 2, disks: [] };
    win.singleEcDiskStatus = [];
    win.singleEcHealthReport = null;
    win.singleEcNodeDisks = [];

    try {
        // 并行请求EC配置和磁盘列表
        const [cfgRes, diskRes] = await Promise.allSettled([
            axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/ec_config`, { timeout: 10000 }),
            axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/disks`, { timeout: 10000 })
        ]);

        // 处理EC配置
        if (cfgRes.status === 'fulfilled' && cfgRes.value.data?.config?.k) {
            win.singleEcConfig = cfgRes.value.data.config;

            // 获取磁盘状态
            try {
                const statusRes = await axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/proxy/ec_status`, { timeout: 10000 });
                win.singleEcDiskStatus = statusRes.data.disk_status || [];
            } catch (e) {
                console.error('获取磁盘状态失败:', e);
            }
        }

        // 处理磁盘列表
        if (diskRes.status === 'fulfilled') {
            const disks = diskRes.value.data.disks || diskRes.value.data || [];
            win.singleEcNodeDisks = disks.filter(d =>
                d.mount && !['C:/', 'D:/', '/'].includes(d.mount.toUpperCase().replace('\\', '/'))
            );
        }
    } catch (e) {
        console.error('获取节点配置失败:', e);
    }

    win.singleEcLoading = false;
},


        getDiskStatus(win, disk) {
    if (!win.singleEcDiskStatus) return null;
    const status = win.singleEcDiskStatus.find(d => d.disk === disk);
    return status ? status.status : null;
},

getDiskStatusText(win, disk) {
    const status = this.getDiskStatus(win, disk);
    const map = {
        'online': '正常',
        'offline': '离线',
        'replaced': '已更换',
        'empty': '空盘'
    };
    return map[status] || '未知';
},
        triggerEcFileInput(win) {
    const input = document.getElementById('ecFileInput' + win.id);
    if (input) input.click();
},

async saveSingleEcConfig(win) {
    try {
        await axios.post(`${this.apiBaseUrl}/api/nodes/${win.selectedSingleEcNode.id}/ec_config`, {
            scheme: 'rs',
            k: win.singleEcForm.k,
            m: win.singleEcForm.m,
            disks: win.singleEcForm.disks
        });
        alert('EC配置已保存！');
        this.selectNodeForSingleEc(win, win.selectedSingleEcNode);
    } catch (e) {
        alert('保存失败: ' + (e.response?.data?.error || e.message));
    }
},



async deleteSingleEcConfig(win) {
    try {
        const nodeId = win.selectedSingleEcNode.id;
        const nodeName = win.selectedSingleEcNode.name;

        // 先检查是否有文件
        let files = [];
        try {
            const filesRes = await axios.get(`${this.apiBaseUrl}/api/nodes/${nodeId}/proxy/ec_files`);
            files = filesRes.data.files || [];
        } catch (e) {}

        const fileCount = files.length;

        let confirmMsg = '确定删除该节点的EC配置？';
        if (fileCount > 0) {
            confirmMsg = `⚠️ EC池中有 ${fileCount} 个文件！\n\n删除配置后这些文件的分片数据仍保留在磁盘上，但将无法正常读取。\n\n建议先导出文件再删除配置。\n\n是否继续删除？`;
        }

        if (!confirm(confirmMsg)) return;

        if (fileCount > 0) {
            const exportFirst = confirm('是否先一键导出所有文件？\n\n点击"确定"开始导出，点击"取消"直接删除配置');
            if (exportFirst) {
                await this.exportAllEcFiles('node', nodeId);
                // 导出完成后再次确认是否删除
                if (!confirm('文件已导出完成，是否继续删除配置？')) return;
            }
        }

        await axios.delete(`${this.apiBaseUrl}/api/nodes/${nodeId}/ec_config`);
        win.singleEcConfig = null;
        alert('配置已删除');
        await this.loadEcStatus(win);
        await this.selectNodeForSingleEc(win, win.selectedSingleEcNode);
    } catch (e) {
        alert('删除失败: ' + (e.response?.data?.error || e.message));
    }
},


// 一键导出所有EC文件
async exportAllEcFiles(type, nodeId) {
    try {
        let url;
        if (type === 'cross') {
            url = `${this.apiBaseUrl}/api/ec_export_all`;
        } else {
            url = `${this.apiBaseUrl}/api/nodes/${nodeId}/proxy/ec_export_all`;
        }

        // 触发下载
        const link = document.createElement('a');
        link.href = url;
        link.download = `ec_export_${Date.now()}.zip`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // 等待一下让下载开始
        await new Promise(resolve => setTimeout(resolve, 1000));

    } catch (e) {
        alert('导出失败: ' + (e.response?.data?.error || e.message));
        throw e;
    }
},
// ========== EC上传方法 ==========
handleEcFileDrop(e, window) {
    const files = Array.from(e.dataTransfer.files);
    if (!window) {
        window = this.windows.find(w => w.type === 'ec-config');
    }
    if (window) {
        window.ecUploadFiles = window.ecUploadFiles || [];
        window.ecUploadFiles.push(...files);
    }
},
// ========== EC状态监控方法 ==========
async loadEcStatus(window) {
    window.ecStatusLoading = true;
    window.ecStatus = { cross_ec: null, single_ec_nodes: [] };

    try {
        // 先刷新节点列表，获取最新在线状态
        try {
            const nodesRes = await axios.get(`${this.apiBaseUrl}/api/nodes`);
            window.allNodes = nodesRes.data || [];
        } catch (e) {
            console.warn('刷新节点列表失败:', e.message);
        }

        // 加载跨节点EC配置，并检测各节点真实状态
        if (window.crossEcConfig) {
            const nodesWithStatus = [];
            for (const nodeInfo of (window.crossEcConfig.nodes || [])) {
    const node = (window.allNodes || []).find(n => n.id === (nodeInfo.node_id || nodeInfo.nodeId));
                const isOnline = node && node.status === 'online';
                nodesWithStatus.push({
                    ...nodeInfo,
                    online: isOnline
                });
            }
            const onlineCount = nodesWithStatus.filter(n => n.online).length;
            const totalCount = nodesWithStatus.length;
            const minRequired = window.crossEcConfig.k;

            window.ecStatus.cross_ec = {
                ...window.crossEcConfig,
                nodes: nodesWithStatus,
                health: onlineCount >= minRequired ? 'healthy' : (onlineCount > 0 ? 'degraded' : 'offline'),
                onlineNodes: onlineCount,
                totalNodes: totalCount
            };
        }

        // 遍历节点获取单节点EC状态
        for (const node of (window.allNodes || [])) {
            const isOnline = node.status === 'online';
            if (!isOnline) continue;

            try {
                const res = await axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/ec_config`);
                if (res.data && res.data.config && (res.data.config.scheme || res.data.config.k)) {
                    window.ecStatus.single_ec_nodes.push({
                        node_id: node.id,
                        node_name: node.name,
                        ip: node.ip,
                        config: res.data.config,
                        health: 'healthy',
                        online: true
                    });
                }
            } catch (e) {
                console.warn(`节点 ${node.name} EC配置获取失败:`, e.message);
            }
        }
    } catch (e) {
        console.error('加载EC状态失败:', e);
    }
    window.ecStatusLoading = false;
},

startEcStatusPolling(window) {
    this.stopEcStatusPolling(window);
    this.loadEcStatus(window, true);  // 首次加载显示loading
    window.ecStatusTimer = setInterval(() => {
        if (window.ecTab === 'status') {
            this.loadEcStatus(window, false);  // 轮询时不显示loading
        }
    }, 5000);
},
stopEcStatusPolling(window) {
    if (window.ecStatusTimer) {
        clearInterval(window.ecStatusTimer);
        window.ecStatusTimer = null;
    }
},


        // 获取节点在线状态
getNodeOnlineStatus(window, nodeId) {
    const node = (window.allNodes || []).find(n => n.id === nodeId);
    return node && node.status === 'online';
},

// 导出所有跨节点EC文件
async exportAllCrossEcFiles(window) {
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/ec_files?type=cross`);
        const files = res.data.files || [];

        if (files.length === 0) {
            alert('EC池中没有文件');
            return;
        }

        if (!confirm(`确定导出全部 ${files.length} 个文件？`)) return;

        window.exportProgress = { show: true, current: 0, total: files.length, status: '准备导出...' };

        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            window.exportProgress.current = i + 1;
            window.exportProgress.status = `正在导出: ${file.filename}`;

            try {
                const downloadRes = await axios.get(`${this.apiBaseUrl}/api/ec_download/cross/${encodeURIComponent(file.filename)}`, {
                    responseType: 'blob'
                });

                // 触发下载
                const url = URL.createObjectURL(downloadRes.data);
                const a = document.createElement('a');
                a.href = url;
                a.download = file.filename;
                a.click();
                URL.revokeObjectURL(url);

                // 间隔一下避免浏览器卡顿
                await new Promise(r => setTimeout(r, 500));
            } catch (e) {
                console.error(`导出 ${file.filename} 失败:`, e);
            }
        }

        window.exportProgress.show = false;
        alert('导出完成！');
    } catch (e) {
        alert('导出失败: ' + (e.response?.data?.error || e.message));
    }
},

// 打开替换磁盘对话框
openAddDiskToCrossEc(window) {
    window.showAddCrossEcDiskDialog = true;
    window.replaceDiskForm = {
        oldDisk: null,
        newNodeId: null,
        newDisk: null
    };
    window.replaceNodeDisks = [];

    // 找出离线的磁盘
    this.detectOfflineDisks(window);
},

// 检测离线磁盘
detectOfflineDisks(window) {
    const offlineDisks = [];
    const onlineNodeIds = (window.allNodes || [])
        .filter(n => n.status === 'online')
        .map(n => n.id);

    for (const nodeInfo of (window.crossEcConfig?.nodes || [])) {
        const nodeId = nodeInfo.node_id || nodeInfo.nodeId;
        const nodeName = nodeInfo.nodeName || nodeId;
        const isNodeOnline = onlineNodeIds.includes(nodeId);

        for (const disk of (nodeInfo.disks || [])) {
            const diskMount = typeof disk === 'string' ? disk : disk.mount || disk;

            // 检查节点是否离线，或者磁盘是否在健康检查中被标记为离线
            if (!isNodeOnline) {
                offlineDisks.push({
                    node_id: nodeId,
                    nodeName: nodeName,
                    disk: diskMount,
                    reason: '节点离线'
                });
            }
        }
    }

    // 也从健康检查结果中获取离线磁盘
    if (window.crossEcHealthReport?.files) {
        for (const file of window.crossEcHealthReport.files) {
            for (const shard of (file.shards || [])) {
                if (!shard.exists && shard.node_id && shard.disk) {
                    const exists = offlineDisks.some(d =>
                        d.node_id === shard.node_id && d.disk === shard.disk
                    );
                    if (!exists) {
                        offlineDisks.push({
                            node_id: shard.node_id,
                            nodeName: shard.node_id,
                            disk: shard.disk,
                            reason: shard.reason || '磁盘离线'
                        });
                    }
                }
            }
        }
    }

    window.offlineDisks = offlineDisks;
},

// 加载节点可用磁盘（用于替换）
async loadNodeDisksForReplace(window) {
    if (!window.replaceDiskForm.newNodeId) {
        window.replaceNodeDisks = [];
        return;
    }

    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/nodes/${window.replaceDiskForm.newNodeId}/disks`);
        const allDisks = res.data.disks || [];

        // 过滤掉已在EC池中的磁盘
        const usedDisks = new Set();
        for (const nodeInfo of (window.crossEcConfig?.nodes || [])) {
            if ((nodeInfo.node_id || nodeInfo.nodeId) === window.replaceDiskForm.newNodeId) {
                for (const d of (nodeInfo.disks || [])) {
                    const mount = typeof d === 'string' ? d : d.mount || d;
                    usedDisks.add(mount.toUpperCase());
                }
            }
        }

        window.replaceNodeDisks = allDisks.filter(d => {
            const mount = (d.mount || d.drive || '').toUpperCase();
            return !usedDisks.has(mount);
        });
    } catch (e) {
        window.replaceNodeDisks = [];
    }
},

// 确认替换磁盘
async confirmReplaceDisk(window) {
    const { oldDisk, newNodeId, newDisk } = window.replaceDiskForm;

    if (!oldDisk || !newNodeId || !newDisk) {
        alert('请完整选择要替换的磁盘和新磁盘');
        return;
    }

    if (!confirm(`确定要将 ${oldDisk.nodeName}:${oldDisk.disk} 替换为 ${newNodeId}:${newDisk} 吗？\n\n替换后需要执行"重建分片"来恢复数据。`)) {
        return;
    }

    try {
        const res = await axios.post(`${this.apiBaseUrl}/api/cross_ec_config/replace_disk`, {
            old_node_id: oldDisk.node_id,
            old_disk: oldDisk.disk,
            new_node_id: newNodeId,
            new_disk: newDisk
        });

        if (res.data.success) {
            alert(`替换成功！已更新 ${res.data.updated_files} 个文件的分片信息。\n\n请点击"重建分片"来恢复数据到新磁盘。`);
            window.showAddCrossEcDiskDialog = false;
            await this.loadEcWindowData(window);
        } else {
            alert(res.data.error || '替换失败');
        }
    } catch (e) {
        alert('替换失败: ' + (e.response?.data?.error || e.message));
    }
},
async openExportCrossEcDialog(window) {
    window.showExportCrossEcDialog = true;
    window.exportForm = {
        selectedNode: null,
        selectedDisk: null,
        exportPath: 'ec_export'
    };
    window.exportNodeDisks = [];
    window.exportProgress = { show: false };

    // 获取文件数量
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/ec_files?type=cross`);
        window.exportFileCount = (res.data.files || []).length;
        window.exportFiles = res.data.files || [];
    } catch (e) {
        window.exportFileCount = 0;
        window.exportFiles = [];
    }
},

        async loadNodeDisksForExport(window) {
    if (!window.exportForm.selectedNode) {
        window.exportNodeDisks = [];
        return;
    }

    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/nodes/${window.exportForm.selectedNode}/disks`);
        window.exportNodeDisks = res.data.disks || [];
    } catch (e) {
        window.exportNodeDisks = [];
    }
},

        // 执行导出
async executeExportCrossEcFiles(window) {
    if (!window.exportForm.selectedNode || !window.exportForm.selectedDisk) {
        alert('请选择目标节点和磁盘');
        return;
    }

    const files = window.exportFiles || [];
    if (files.length === 0) {
        alert('EC池中没有文件');
        return;
    }

    if (!confirm(`确定导出全部 ${files.length} 个文件到 ${window.exportForm.selectedDisk}/${window.exportForm.exportPath || 'ec_export'}/ ?`)) return;

    window.exportProgress = { show: true, current: 0, total: files.length, status: '准备导出...' };

    let successCount = 0;
    let failCount = 0;

    for (let i = 0; i < files.length; i++) {
    const file = files[i];
    window.exportProgress.current = i + 1;
    window.exportProgress.status = `正在导出: ${file.name}`;

    try {
        await axios.post(`${this.apiBaseUrl}/api/cross_ec_export`, {
            filename: file.name,
            target_node: window.exportForm.selectedNode,
            target_disk: window.exportForm.selectedDisk,
            target_path: window.exportForm.exportPath || 'ec_export'
        });
        successCount++;
    } catch (e) {
        console.error(`导出 ${file.name} 失败:`, e);
        failCount++;
    }
}

    window.exportProgress.show = false;
    window.showExportCrossEcDialog = false;

    if (failCount === 0) {
        alert(`导出完成！共 ${successCount} 个文件`);
    } else {
        alert(`导出完成！成功 ${successCount} 个，失败 ${failCount} 个`);
    }
},
// 打开重建分片对话框
openRebuildShards(window) {
    window.showRebuildShardsDialog = true;
    window.rebuildForm = {
        mode: 'auto',  // auto: 自动检测丢失分片, manual: 手动选择文件
        selectedFiles: [],
        targetDisk: null
    };
    this.loadEcFilesForRebuild(window);
},

// 加载EC文件列表用于重建
async loadEcFilesForRebuild(window) {
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/ec_files?type=cross`);
        window.rebuildFiles = res.data.files || [];
    } catch (e) {
        window.rebuildFiles = [];
    }
},

// 检测跨节点EC磁盘状态
async checkCrossEcDiskStatus(win) {
    if (!win.crossEcConfig?.nodes) return;

    // 初始化状态
    win.crossEcDiskStatus = {};

    for (const nodeInfo of win.crossEcConfig.nodes) {
        const nodeId = nodeInfo.node_id || nodeInfo.nodeId;
        const node = (win.allNodes || []).find(n => n.id === nodeId);

        if (!node || node.status !== 'online') {
            // 节点离线，所有磁盘标记为离线
            for (const diskInfo of (nodeInfo.disks || [])) {
                const mount = typeof diskInfo === 'string' ? diskInfo : diskInfo.mount;
                win.crossEcDiskStatus[`${nodeId}:${mount}`] = 'offline';
            }
            continue;
        }

        try {
            const res = await axios.get(`${this.apiBaseUrl}/api/nodes/${nodeId}/disks`);
            const currentDisks = res.data.disks || res.data || [];

            for (const diskInfo of (nodeInfo.disks || [])) {
                const mount = typeof diskInfo === 'string' ? diskInfo : diskInfo.mount;
                const expectedSerial = typeof diskInfo === 'string' ? '' : (diskInfo.serial || '');

                const currentDisk = currentDisks.find(d => d.mount === mount);

                if (currentDisk) {
                    const currentSerial = currentDisk.volume_serial || currentDisk.serial || '';

                    // 检查序列号是否匹配
                    if (expectedSerial && currentSerial && expectedSerial !== currentSerial) {
                        // 挂载点存在但序列号不匹配 = 磁盘已更换
                        win.crossEcDiskStatus[`${nodeId}:${mount}`] = 'replaced';
                    } else {
                        win.crossEcDiskStatus[`${nodeId}:${mount}`] = 'online';
                    }
                } else {
                    win.crossEcDiskStatus[`${nodeId}:${mount}`] = 'missing';
                }
            }
        } catch (e) {
            for (const diskInfo of (nodeInfo.disks || [])) {
                const mount = typeof diskInfo === 'string' ? diskInfo : diskInfo.mount;
                win.crossEcDiskStatus[`${nodeId}:${mount}`] = 'unknown';
            }
        }
    }
},

// 获取磁盘状态
getDiskStatus(win, nodeId, disk) {
    const mount = typeof disk === 'string' ? disk : disk.mount;
    const key = `${nodeId}:${mount}`;
    return win.crossEcDiskStatus?.[key] || 'unknown';
},
// 获取单节点EC磁盘状态
getSingleEcDiskStatus(win, disk) {
    if (!win.singleEcDiskStatus || !win.singleEcDiskStatus.length) return null;
    const found = win.singleEcDiskStatus.find(d => d.disk === disk);
    return found ? found.status : null;
},

// 获取单节点EC磁盘状态文本
getSingleEcDiskStatusText(win, disk) {
    const status = this.getSingleEcDiskStatus(win, disk);
    const map = {
        'online': '正常',
        'offline': '离线',
        'replaced': '已更换',
        'empty': '空盘'
    };
    return map[status] || '检测中...';
},
// 检测丢失的分片
async detectLostShards(window) {
    try {
        window.detectingShards = true;
        const res = await axios.get(`${this.apiBaseUrl}/api/cross_ec_config/check_shards`);
        window.lostShards = res.data.lost_shards || [];
        window.detectingShards = false;

        if (window.lostShards.length === 0) {
            alert('所有分片完整，无需重建');
        }
    } catch (e) {
        window.detectingShards = false;
        alert('检测失败: ' + (e.response?.data?.error || e.message));
    }
},

// 执行分片重建
// 执行分片重建
async executeRebuildShards(window) {
    const filesToRebuild = window.rebuildForm.mode === 'auto'
        ? (window.lostShards || []).map(s => s.filename)
        : (window.rebuildForm.selectedFiles || []);

    if (filesToRebuild.length === 0) {
        alert('没有需要重建的文件');
        return;
    }

    if (!confirm(`确定重建 ${filesToRebuild.length} 个文件的分片？`)) return;

    try {
        window.rebuildProgress = { show: true, current: 0, total: filesToRebuild.length, status: '开始重建...' };

        let successCount = 0;
        let failedFiles = [];

        for (let i = 0; i < filesToRebuild.length; i++) {
            const filename = filesToRebuild[i];
            window.rebuildProgress.current = i + 1;
            window.rebuildProgress.status = `正在重建: ${filename}`;

            try {
                await axios.post(`${this.apiBaseUrl}/api/cross_ec_config/rebuild_shard`, {
                    filename
                });
                successCount++;
            } catch (e) {
                console.error(`重建 ${filename} 失败:`, e);
                failedFiles.push(filename);
            }
        }

        window.rebuildProgress.show = false;
        window.showRebuildShardsDialog = false;

        if (failedFiles.length > 0) {
            alert(`重建完成！成功 ${successCount} 个，失败 ${failedFiles.length} 个`);
        } else {
            alert('重建完成！');
        }

        await this.loadEcWindowData(window);
    } catch (e) {
        window.rebuildProgress = { show: false };
        alert('重建失败: ' + (e.response?.data?.error || e.message));
    }
},

async loadEcFiles(win) {
    win.ecFilesLoading = true;
    win.ecFiles = [];

    try {
        // 加载跨节点EC文件
        if (win.crossEcConfig) {
            try {
                const res = await axios.get(`${this.apiBaseUrl}/api/ec_files?type=cross`);
                const crossFiles = (res.data.files || []).map(f => ({
                    ...f,
                    source: 'cross',
                    sourceName: '跨节点EC'
                }));
                win.ecFiles.push(...crossFiles);
            } catch (e) {}
        }

        // 加载各节点的单节点EC文件
        for (const node of (win.allNodes || [])) {
            if (node.status !== 'online') continue;
            try {
                const res = await axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/proxy/ec_files`);
                const nodeFiles = (res.data.files || []).map(f => ({
                    ...f,
                    source: node.id,
                    sourceName: node.name
                }));
                win.ecFiles.push(...nodeFiles);
            } catch (e) {}
        }
    } catch (e) {
        console.error('加载EC文件失败:', e);
    }
    win.ecFilesLoading = false;
},

getFileIcon(filename) {
    const ext = (filename || '').split('.').pop().toLowerCase();
    const icons = {
        'pdf': '📕', 'doc': '📘', 'docx': '📘',
        'xls': '📗', 'xlsx': '📗', 'csv': '📗',
        'ppt': '📙', 'pptx': '📙',
        'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️', 'webp': '🖼️',
        'mp4': '🎬', 'avi': '🎬', 'mkv': '🎬', 'mov': '🎬',
        'mp3': '🎵', 'wav': '🎵', 'flac': '🎵',
        'zip': '📦', 'rar': '📦', '7z': '📦', 'tar': '📦', 'gz': '📦',
        'txt': '📄', 'md': '📄', 'json': '📄', 'xml': '📄',
        'js': '📜', 'py': '📜', 'java': '📜', 'cpp': '📜', 'c': '📜'
    };
    return icons[ext] || '📄';
},

formatFileSize(bytes) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    while (bytes >= 1024 && i < units.length - 1) {
        bytes /= 1024;
        i++;
    }
    return bytes.toFixed(i > 0 ? 2 : 0) + ' ' + units[i];
},

handleEcFileSelect(e, window) {
    const files = Array.from(e.target.files);
    if (!window) {
        window = this.windows.find(w => w.type === 'ec-config');
    }
    if (window) {
        window.ecUploadFiles = window.ecUploadFiles || [];
        window.ecUploadFiles.push(...files);
    }
    e.target.value = '';  // 清空input以便再次选择相同文件
},

async startEcUpload(window) {
    if (!window.uploadTargetEc || !window.ecUploadFiles?.length) return;

    window.uploadingEc = true;
    window.uploadedCount = 0;

    for (let i = 0; i < window.ecUploadFiles.length; i++) {
        const file = window.ecUploadFiles[i];
        file.progress = 0;
        file.status = 'uploading';

        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('target', window.uploadTargetEc);

            await axios.post(`${this.apiBaseUrl}/api/ec_upload`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                onUploadProgress: (e) => {
                    file.progress = Math.round((e.loaded / e.total) * 100);
                }
            });

            file.status = 'success';
            file.progress = 100;
        } catch (e) {
            file.status = 'error';
            console.error('上传失败:', file.name, e);
        }

        window.uploadedCount = i + 1;
    }

    window.uploadingEc = false;

    // 刷新文件列表
    this.loadEcFiles(window);
},



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
        volumeForm: { name: '', display_name: '', icon: '📁', strategy: 'largest_free', quota: 0, quotaUnit: 'GB' },
        volumeEditMode: false,
        // 添加磁盘
        showAddDiskDialog: false,
        selectedNewDisk: null,
        // ===== 跨节点池相关 =====
        crossPools: [],
        crossPoolsLoading: false,
        selectedCrossPool: null,
crossPoolVolumes: [],           // 新增
showCrossVolumeDialog: false,   // 新增
crossVolumeForm: { name: '', display_name: '', icon: '📁', strategy: 'largest_free', quota: 0, quotaUnit: 'GB' },
crossVolumeEditMode: false,     // 新增
        showCreatePoolDialog: false,
        rebuildingIndex: false,  // 新增
rebuildProgress: null,   // 新增
        poolForm: { name: '', display_name: '', strategy: 'largest_free', disks: [] },
        poolEditMode: false,
        // 选择磁盘
        selectedNodeForDisk: null,
        nodeDisksLoading: false,
        nodeDisks: []
    });
    this.loadNodesForSpaceAllocation(win);
    this.loadCrossPools(win);
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


// ========== 跨节点池管理 ==========

// 加载跨节点池列表
async loadCrossPools(win) {
    win.crossPoolsLoading = true;
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/cross-pools`);
        win.crossPools = res.data || [];
    } catch (e) {
        console.error('加载跨节点池失败', e);
        win.crossPools = [];
    }
    win.crossPoolsLoading = false;
},

// 打开创建池对话框
openCreatePoolDialog(win) {
    win.poolForm = { name: '', display_name: '', strategy: 'largest_free', disks: [] };
    win.poolEditMode = false;
    win.selectedNodeForDisk = null;
    win.nodeDisks = [];
    win.showCreatePoolDialog = true;
},

// 打开编辑池对话框
// 打开编辑池对话框
async openEditPoolDialog(win, pool) {
    win.poolForm = {
        id: pool.id,
        name: pool.name,
        display_name: pool.display_name,
        strategy: pool.strategy,
        disks: pool.disks || []
    };
    win.poolEditMode = true;
    win.selectedNodeForDisk = null;
    win.nodeDisks = [];

    // 加载节点列表
    try {
        const nodesRes = await axios.get(`${this.apiBaseUrl}/api/nodes`);
        win.allNodes = nodesRes.data || [];
    } catch (e) {
        console.error('加载节点列表失败', e);
        win.allNodes = [];
    }

    win.showCreatePoolDialog = true;
},

// 保存跨节点池
async saveCrossPool(win) {
    const form = win.poolForm;
    if (!form.name || !form.name.trim()) {
        alert('请输入池名称');
        return;
    }
    if (!form.disks || form.disks.length === 0) {
        alert('请至少添加一个磁盘');
        return;
    }

    try {
        if (win.poolEditMode) {
            await axios.put(`${this.apiBaseUrl}/api/cross-pools/${form.id}`, {
                display_name: form.display_name,
                strategy: form.strategy,
                disks: form.disks
            });
            alert('更新成功');
        } else {
            await axios.post(`${this.apiBaseUrl}/api/cross-pools`, form);
            alert('创建成功');
        }
        win.showCreatePoolDialog = false;
        this.loadCrossPools(win);
    } catch (e) {
        alert('操作失败: ' + (e.response?.data?.error || e.message));
    }
},

// 删除跨节点池
async deleteCrossPool(win, pool) {
    if (!confirm(`确定要删除存储池「${pool.display_name || pool.name}」吗？`)) {
        return;
    }

    // 询问是否保留文件
    const keepFiles = confirm('是否保留实际文件？\n\n点击「确定」保留文件\n点击「取消」完全删除');

    try {
        await axios.delete(`${this.apiBaseUrl}/api/cross-pools/${pool.id}?keep_files=${keepFiles}`);
        alert('删除成功');
        win.selectedCrossPool = null;  // 重置选中状态，回到列表页
        win.crossPoolVolumes = [];     // 清空逻辑卷
        await this.loadCrossPools(win);
    } catch (e) {
        alert('删除失败: ' + (e.response?.data?.error || e.message));
    }
},


async selectCrossPool(win, pool) {
    win.selectedCrossPool = pool;

    // 加载池的统计信息
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/cross-pools/${pool.id}/stats`);
        win.selectedCrossPool.stats = res.data;
    } catch (e) {
        console.error('加载池统计失败', e);
    }

    // 确保节点列表已加载
    if (!win.allNodes || win.allNodes.length === 0) {
        try {
            const nodesRes = await axios.get(`${this.apiBaseUrl}/api/nodes`);
            win.allNodes = nodesRes.data || [];
        } catch (e) {
            console.error('加载节点列表失败', e);
        }
    }

    // 刷新成员磁盘的实时容量信息和状态
    if (win.selectedCrossPool.disks && win.selectedCrossPool.disks.length > 0) {
        const nodeIds = [...new Set(win.selectedCrossPool.disks.map(d => d.nodeId))];
        const diskInfoCache = {};
        const nodeStatusCache = {};

        for (const nodeId of nodeIds) {
            // 先检查节点是否在线
            const node = (win.allNodes || []).find(n => n.id === nodeId);
            nodeStatusCache[nodeId] = node?.status || 'offline';

            if (node?.status === 'online') {
                try {
                    const diskRes = await axios.get(`${this.apiBaseUrl}/api/nodes/${nodeId}/disks`);
                    const disks = diskRes.data?.disks || diskRes.data || [];
                    diskInfoCache[nodeId] = disks;
                } catch (e) {
                    console.error(`加载节点 ${nodeId} 磁盘信息失败`, e);
                    nodeStatusCache[nodeId] = 'error';
                }
            }
        }

        // 更新每个磁盘的容量信息和状态
        for (const disk of win.selectedCrossPool.disks) {
            disk.nodeStatus = nodeStatusCache[disk.nodeId] || 'offline';

            if (disk.nodeStatus === 'online') {
                const nodeDisks = diskInfoCache[disk.nodeId] || [];
                // 先按盘符找磁盘
                const latestDisk = nodeDisks.find(d => d.mount === disk.disk);

                if (latestDisk) {
                    // 如果有卷序列号，验证是否匹配
                    const savedSerial = disk.volumeSerial;
                    const currentSerial = latestDisk.volume_serial || latestDisk.serial || '';

                    if (savedSerial && currentSerial && savedSerial !== currentSerial) {
                        // 盘符相同但序列号不同，说明是不同的磁盘
                        disk.diskStatus = 'replaced';
                        disk.warning = '磁盘已被替换（序列号不匹配）';
                    } else {
                        disk.free = latestDisk.free_gb || latestDisk.free;
                        disk.total = latestDisk.total_gb || latestDisk.total;
                        disk.diskStatus = 'online';
                    }
                } else {
                    disk.diskStatus = 'missing';  // 节点在线但磁盘不存在
                }
            } else {
                disk.diskStatus = 'offline';
            }
        }

        // 计算池健康状态
        const totalDisks = win.selectedCrossPool.disks.length;
        const onlineDisks = win.selectedCrossPool.disks.filter(d => d.diskStatus === 'online').length;
        const replacedDisks = win.selectedCrossPool.disks.filter(d => d.diskStatus === 'replaced').length;
        win.selectedCrossPool.health = {
            total: totalDisks,
            online: onlineDisks,
            offline: totalDisks - onlineDisks - replacedDisks,
            replaced: replacedDisks,
            status: onlineDisks === totalDisks ? 'healthy' :
                    (replacedDisks > 0 ? 'error' : (onlineDisks > 0 ? 'degraded' : 'offline'))
        };
    }

    // 加载逻辑卷
    this.loadCrossPoolVolumes(win);
},


// 重建跨节点池索引
async rebuildCrossPoolIndex(win) {
    if (!win.selectedCrossPool) return;

    const pool = win.selectedCrossPool;
    const onlineDisks = (pool.disks || []).filter(d => d.diskStatus === 'online');

    if (onlineDisks.length === 0) {
        alert('没有在线的磁盘，无法重建索引');
        return;
    }

    if (!confirm(`确定要重建存储池 "${pool.display_name || pool.name}" 的索引吗？\n\n这将扫描所有在线磁盘（${onlineDisks.length}个）上的文件并更新数据库索引。\n\n注意：此操作可能需要一些时间，取决于文件数量。`)) {
        return;
    }

    win.rebuildingIndex = true;
    win.rebuildProgress = { current: 0, total: onlineDisks.length, status: '正在扫描...', results: [] };

    try {
        const res = await axios.post(`${this.apiBaseUrl}/api/cross-pools/${pool.id}/rebuild-index`);

        if (res.data.success) {
            win.rebuildProgress.status = '完成';
            win.rebuildProgress.results = res.data.results || [];

            const added = res.data.added || 0;
            const removed = res.data.removed || 0;
            const errors = res.data.errors || 0;

            alert(`索引重建完成！\n\n新增: ${added} 个文件\n移除: ${removed} 条失效记录\n错误: ${errors} 个`);

            // 刷新数据
            await this.selectCrossPool(win, pool);
        } else {
            alert('重建索引失败: ' + (res.data.error || '未知错误'));
        }
    } catch (e) {
        alert('重建索引失败: ' + (e.response?.data?.error || e.message));
    } finally {
        win.rebuildingIndex = false;
    }
},

        // 加载跨节点池逻辑卷
async loadCrossPoolVolumes(win) {
    if (!win.selectedCrossPool) return;
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/cross-pools/${win.selectedCrossPool.id}/volumes`);
        win.crossPoolVolumes = res.data || [];
    } catch (e) {
        console.error('加载逻辑卷失败', e);
        win.crossPoolVolumes = [];
    }
},

// 打开创建跨节点逻辑卷对话框
openCreateCrossVolumeDialog(win) {
    win.crossVolumeForm = { name: '', display_name: '', icon: '📁', strategy: 'largest_free', quota: 0, quotaUnit: 'GB' };
    win.crossVolumeEditMode = false;
    win.showCrossVolumeDialog = true;
},

// 打开编辑跨节点逻辑卷对话框
openEditCrossVolumeDialog(win, vol) {
    // 将后端返回的字节数转换为 GB 或 TB 显示
let quotaValue = 0;
let quotaUnit = 'GB';
if (vol.quota && vol.quota > 0) {
    if (vol.quota >= 1024 * 1024 * 1024 * 1024) {
        quotaValue = vol.quota / (1024 * 1024 * 1024 * 1024);
        quotaUnit = 'TB';
    } else {
        quotaValue = vol.quota / (1024 * 1024 * 1024);
        quotaUnit = 'GB';
    }
}
win.crossVolumeForm = {
    name: vol.name,
    display_name: vol.display_name || '',
    icon: vol.icon || '📁',
    strategy: vol.strategy || 'largest_free',
    quota: quotaValue,
    quotaUnit: quotaUnit
};
    win.crossVolumeEditMode = true;
    win.showCrossVolumeDialog = true;
},

// 保存跨节点逻辑卷
async saveCrossVolume(win) {
    const form = win.crossVolumeForm;
    if (!form.name) return alert('请输入逻辑卷名称');

    // 计算配额字节数
    const quotaBytes = form.quota > 0
        ? form.quota * (form.quotaUnit === 'TB' ? 1024 * 1024 * 1024 * 1024 : 1024 * 1024 * 1024)
        : 0;

    try {
        if (win.crossVolumeEditMode) {
            await axios.patch(`${this.apiBaseUrl}/api/cross-pools/${win.selectedCrossPool.id}/volumes/${form.name}`, {
                display_name: form.display_name,
                icon: form.icon,
                strategy: form.strategy,
                quota: quotaBytes
            });
        } else {
            await axios.post(`${this.apiBaseUrl}/api/cross-pools/${win.selectedCrossPool.id}/volumes`, {
                name: form.name,
                display_name: form.display_name,
                icon: form.icon,
                strategy: form.strategy,
                quota: quotaBytes
            });
        }
        alert(win.crossVolumeEditMode ? '更新成功' : '创建成功');
        win.showCrossVolumeDialog = false;
        this.loadCrossPoolVolumes(win);
    } catch (e) {
        alert('操作失败: ' + (e.response?.data?.detail || e.message));
    }
},


// 删除跨节点逻辑卷
async deleteCrossVolume(win, volName) {
    if (!confirm(`确定要删除逻辑卷 "${volName}" 吗？`)) return;

    // 询问是否删除实际文件
    const deleteFiles = confirm('是否同时删除磁盘上的实际文件？\n\n点击"确定"删除文件（释放磁盘空间）\n点击"取消"仅删除卷配置（保留文件）');

    try {
        const res = await axios.delete(
            `${this.apiBaseUrl}/api/cross-pools/${win.selectedCrossPool.id}/volumes/${volName}?delete_files=${deleteFiles}`
        );
        let msg = '删除成功';
        if (res.data.deleted_file_records) {
            msg += `\n清理了 ${res.data.deleted_file_records} 条文件记录`;
        }
        alert(msg);
        this.loadCrossPoolVolumes(win);
    } catch (e) {
        alert('删除失败: ' + (e.response?.data?.error || e.response?.data?.detail || e.message));
    }
},

// 选择节点加载其磁盘
// 选择节点加载其磁盘
async selectNodeForDiskSelection(win, node) {
    win.selectedNodeForDisk = node;
    win.nodeDisksLoading = true;
    win.nodeDisks = [];
    win.nodeDisksError = null;  // 添加错误状态
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/disks`);
        win.nodeDisks = res.data?.disks || res.data || [];
    } catch (e) {
        console.error('加载节点磁盘失败', e);
        win.nodeDisks = [];
        // 添加用户可见的错误提示
        const errorMsg = e.response?.data?.error || e.response?.data?.detail || e.message || '未知错误';
        win.nodeDisksError = `无法加载磁盘列表: ${errorMsg}`;
        alert(`节点 ${node.name} 磁盘加载失败！\n\n错误信息: ${errorMsg}\n\n请检查：\n1. 该节点是否真的在线\n2. 后端日志中的详细错误`);
    }
    win.nodeDisksLoading = false;
},

// 切换磁盘选择
toggleDiskSelection(win, node, disk) {
    const existing = win.poolForm.disks.findIndex(d => d.nodeId === node.id && d.disk === disk.mount);

    if (existing >= 0) {
        win.poolForm.disks.splice(existing, 1);
    } else {
        win.poolForm.disks.push({
            nodeId: node.id,
            nodeName: node.name,
            nodeIp: node.ip,
            nodePort: node.port,
            disk: disk.mount,
            volumeSerial: disk.volume_serial || disk.serial || '',  // 保存卷序列号
            total: disk.total_gb || disk.total,
            free: disk.free_gb || disk.free,
             nodeStatus: 'online',
    diskStatus: 'online'
        });
    }
},

// 检查磁盘是否已选择
isDiskSelected(win, nodeId, diskMount) {
    return win.poolForm.disks.some(d => d.nodeId === nodeId && d.disk === diskMount);
},

// 从已选列表移除磁盘
removeDiskFromSelection(win, index) {
    win.poolForm.disks.splice(index, 1);
},

// 获取策略显示名称
getStrategyName(strategy) {
    const map = {
        'largest_free': '最大空间优先',
        'round_robin': '轮询分配',
        'balanced': '按比例加权'
    };
    return map[strategy] || strategy;
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
    win.volumeForm = { name: '', display_name: '', icon: '📁', strategy: 'largest_free', quota: 0, quotaUnit: 'GB' };
    win.volumeEditMode = false;
    win.showVolumeDialog = true;
},

// 打开编辑逻辑卷对话框
openEditVolumeDialog(win, vol) {
   // 将后端返回的字节数转换为 GB 或 TB 显示
let quotaValue = 0;
let quotaUnit = 'GB';
if (vol.quota && vol.quota > 0) {
    if (vol.quota >= 1024 * 1024 * 1024 * 1024) {
        quotaValue = vol.quota / (1024 * 1024 * 1024 * 1024);
        quotaUnit = 'TB';
    } else {
        quotaValue = vol.quota / (1024 * 1024 * 1024);
        quotaUnit = 'GB';
    }
}
win.volumeForm = {
    name: vol.name,
    display_name: vol.display_name,
    icon: vol.icon || '📁',
    strategy: vol.strategy || 'largest_free',
    quota: quotaValue,
    quotaUnit: quotaUnit
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

    // 计算配额字节数
    const quotaBytes = form.quota > 0
        ? form.quota * (form.quotaUnit === 'TB' ? 1024 * 1024 * 1024 * 1024 : 1024 * 1024 * 1024)
        : 0;

    try {
        if (win.volumeEditMode) {
            await axios.patch(`${this.apiBaseUrl}/api/nodes/${win.selectedPoolNode.id}/proxy/pool/volume/${form.name}`, {
                display_name: form.display_name,
                icon: form.icon,
                strategy: form.strategy,
                quota: quotaBytes
            });
        } else {
            await axios.post(`${this.apiBaseUrl}/api/nodes/${win.selectedPoolNode.id}/proxy/pool/volume/create`, {
                name: form.name,
                display_name: form.display_name,
                icon: form.icon,
                strategy: form.strategy,
                quota: quotaBytes
            });
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

 const [usersRes, nodesRes, groupsRes, whitelistRes, policiesRes] = await Promise.all([
    axios.get(`${this.apiBaseUrl}/api/users`),
    axios.get(`${this.apiBaseUrl}/api/nodes`),
    axios.get(`${this.apiBaseUrl}/api/node-groups`),
    axios.get(`${this.apiBaseUrl}/api/admin/whitelist`),
    axios.get(`${this.apiBaseUrl}/api/node-policies`)  // 新增
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
        // 节点列表 - 合并策略数据
const policies = policiesRes.data || {};
window.nodes = nodesRes.data.map(node => ({
    ...node,
    access_policy: policies[node.id] || 'all_users'
}));
window.nodePolicies = policies;
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
    const win = this.createWindow({
        type: 'ec-config',
        title: '纠删码配置',
        icon: '🛡️',
        width: 1100,
        height: 700,
        ecTab: 'cross-node',
        allNodes: [],
        crossEcConfig: null,
        crossEcForm: { k: 4, m: 2, selectedDisks: {} },
        selectedCrossEcNode: null,
        crossEcNodeDisks: [],
        crossEcLoading: false,
        selectedSingleEcNode: null,
        singleEcConfig: null,
        singleEcForm: { k: 4, m: 2, disks: [] },
        singleEcNodeDisks: [],
        singleEcLoading: false,
        // 状态监控
        ecStatus: null,
        ecStatusLoading: false,
        // 上传相关
        uploadTargetEc: '',
        ecUploadFiles: [],
        uploadingEc: false,
        uploadedCount: 0,
        dragOver: false,
        ecFiles: [],
        ecFilesLoading: false
    });
    this.loadEcWindowData(win);
},

async loadEcWindowData(win) {
    // 加载节点列表
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/nodes`);
        win.allNodes = res.data || [];

        // 检查每个在线节点是否已配置EC
        for (const node of win.allNodes) {
            if (node.status !== 'online') {
                node.ecConfigured = false;
                continue;
            }
            try {
                const ecRes = await axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/ec_config`);
                node.ecConfigured = !!(ecRes.data && ecRes.data.config && (ecRes.data.config.scheme || ecRes.data.config.k));
            } catch (e) {
                node.ecConfigured = false;
            }
        }
    } catch (e) {
        win.allNodes = [];
    }
    // 先加载跨节点EC配置
    await this.loadCrossEcConfig(win);
    // 检测磁盘实际状态
    await this.checkCrossEcDiskStatus(win);
    // 启动EC状态轮询（包含首次加载）
    await this.loadEcStatus(win);
},
async loadNodesForECConfig(win) {
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/nodes`);
        win.allNodes = res.data || [];
    } catch (e) {
        console.error('加载节点失败', e);
        win.allNodes = [];
    }
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


// ============ 客户端同步 ============
async openSyncClientDialog() {
    this.showStartMenu = false;

    // 加载在线节点
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/nodes`);
        this.syncAvailableNodes = res.data.filter(n => n.status === 'online');
    } catch (e) {
        alert('获取节点列表失败');
        return;
    }

    // 重置表单
    this.syncForm = {
        sourceNode: '',
        targetNodes: [],
        mode: 'full',
        selectedFiles: [],
        backup: true
    };
    this.syncFileList = [];
    this.syncProgress = { show: false, status: '', current: 0, total: 0, results: [] };

    this.showSyncClientDialog = true;
},

selectAllTargetNodes() {
    const available = this.syncAvailableNodes.filter(n => n.status === 'online' && n.id !== this.syncForm.sourceNode);
    if (this.syncForm.targetNodes.length === available.length) {
        this.syncForm.targetNodes = [];
    } else {
        this.syncForm.targetNodes = available.map(n => n.id);
    }
},

async loadSourceFiles() {
    if (!this.syncForm.sourceNode) return;

    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/admin/node-files/${this.syncForm.sourceNode}`);
        this.syncFileList = res.data.files || [];
    } catch (e) {
        alert('获取文件列表失败: ' + (e.response?.data?.error || e.message));
    }
},

async startSyncClient() {
    if (!this.syncForm.sourceNode || this.syncForm.targetNodes.length === 0) {
        alert('请选择源节点和目标节点');
        return;
    }

    if (this.syncForm.mode === 'selective' && this.syncForm.selectedFiles.length === 0) {
        alert('请选择要同步的文件');
        return;
    }

    if (!confirm(`确定要将 ${this.syncForm.targetNodes.length} 个节点同步为源节点的版本吗？`)) {
        return;
    }

    this.syncProgress = {
        show: true,
        status: '正在同步...',
        current: 0,
        total: this.syncForm.targetNodes.length,
        results: []
    };

    try {
        const res = await axios.post(`${this.apiBaseUrl}/api/admin/sync-client`, {
            source_node: this.syncForm.sourceNode,
            target_nodes: this.syncForm.targetNodes,
            mode: this.syncForm.mode,
            selected_files: this.syncForm.selectedFiles,
            backup: this.syncForm.backup
        });

        if (res.data.success) {
            this.syncProgress.results = Object.entries(res.data.results).map(([nodeId, result]) => ({
                nodeId,
                success: result.success,
                error: result.error || result.message
            }));
            this.syncProgress.current = this.syncProgress.total;
            this.syncProgress.status = '同步完成';

            const successCount = this.syncProgress.results.filter(r => r.success).length;
            alert(`同步完成！成功: ${successCount}/${this.syncProgress.total}`);
        }
    } catch (e) {
        this.syncProgress.status = '同步失败';
        alert('同步失败: ' + (e.response?.data?.error || e.message));
    }
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
            // 调用 oldapp.py 中新的 /api/files/.../list 接口
            const res = await axios.get(`${this.apiBaseUrl}/api/files/${window.selectedNodeId}/list`, {
                params: {path: path}
            });
            window.files = res.data.files;
        } catch (error) {
            console.error("加载文件列表失败:", error);
            // 这将显示来自 oldapp.py 的 "权限不足" 错误
            window.error = error.response?.data?.message || "加载文件列表失败";
        } finally {
            window.loading = false;
        }
    },




    // ========== 文件管理 ==========
openFileManager() {
    const existing = this.windows.find(w => w.type === 'file-manager');
    if (existing) {
        this.focusWindow(existing);
        return;
    }

    const win = {

        crossPoolVolumes: [],          // 跨节点池的逻辑卷
selectedCrossPoolVolume: null, // 选中的跨节点池逻辑卷
        crossPools: [],           // 跨节点存储池列表
selectedCrossPool: null,  // 选中的跨节点池
crossPoolVolumes: [],     // 跨节点池的逻辑卷
        showPreview: false,
        previewFile: null,
        id: Date.now(),
        type: 'file-manager',
        title: '📁 文件管理',
        width: 1000,
        height: 600,
        x: 120,
        y: 60,
        zIndex: this.nextZIndex++,
        isMaximized: false,
        // 数据
        fmNodes: [],
        fmDisks: [],
        fmFiles: [],
        fmEcVolume: null,        // 单节点EC卷
        fmPoolVolumes: [],       // 存储池逻辑卷
        crossEcVolume: null,     // 跨节点EC卷
        selectedFmNode: null,
        selectedFmDisk: null,
        selectedVolumeType: null, // 'disk', 'single-ec', 'pool', 'cross-ec'
        selectedPoolVolume: null,
        currentPath: '',
        selectedFiles: [],
        // 加载状态
        fmDisksLoading: false,
        fmFilesLoading: false
    };

    this.windows.push(win);
    this.loadFmNodes(win);
    this.loadCrossEcVolume(win);
    this.loadFmCrossPools(win);
},

        async loadCrossEcVolume(win) {
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/cross_ec_config`);
        if (res.data && res.data.config) {
            win.crossEcVolume = res.data.config;
        }
    } catch (e) {
        win.crossEcVolume = null;
    }
},
async loadFmCrossPools(win) {
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/cross-pools`);
        win.crossPools = res.data || [];
    } catch (e) {
        win.crossPools = [];
    }
},

   async selectCrossPoolVolume(win, vol) {
    win.selectedCrossPoolVolume = vol;
    win.currentPath = '';
    win.fmFilesLoading = true;

    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/cross-pools/${win.selectedCrossPool.id}/files`, {
            params: { subpath: vol.name }
        });
        win.fmFiles = (res.data.files || []).map(f => ({
            id: f.id,              // 添加这行
            name: f.filename,
            is_dir: false,
            size: f.file_size,
            path: f.filepath,
            type: 'cross-pool-file',
            nodeId: f.node_id,
            mtime: f.created_at    // 添加这行（用于显示时间）
        }));
    } catch (e) {
        win.fmFiles = [];
    }
    win.fmFilesLoading = false;
},

   async selectFmCrossPool(win, pool) {
    win.selectedFmNode = null;
    win.selectedFmDisk = null;
    win.selectedVolumeType = 'cross-pool';
    win.selectedCrossPool = pool;
    win.selectedPoolVolume = null;
    win.currentPath = '';
    win.fmFiles = [];
    win.fmDisks = [];
    win.fmEcVolume = null;
    win.fmPoolVolumes = [];

    // 加载跨节点池的逻辑卷列表
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/cross-pools/${pool.id}/volumes`);
        win.crossPoolVolumes = res.data || [];
    } catch (e) {
        win.crossPoolVolumes = [];
    }
},

async loadCrossPoolFiles(win, pool) {
    win.fmFilesLoading = true;
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/cross-pools/${pool.id}/files`);
        win.fmFiles = (res.data.files || []).map(f => ({
            name: f.filename,
            isDir: false,
            size: f.file_size,
            path: f.filepath,
            type: 'cross-pool-file',
            nodeId: f.node_id
        }));
    } catch (e) {
        win.fmFiles = [];
    }
    win.fmFilesLoading = false;
},

 async selectCrossEcVolume(win) {
    win.selectedFmNode = null;
    win.selectedFmDisk = null;
    win.selectedVolumeType = 'cross-ec';
    win.currentPath = '';
    win.fmFiles = [];
    win.fmDisks = [];
    win.fmEcVolume = null;
    win.fmPoolVolumes = [];

    // 加载跨节点EC卷的文件列表
    await this.loadCrossEcFiles(win);
},



  async loadCrossEcFiles(win) {
    win.fmFilesLoading = true;
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/ec_files`);
        win.fmFiles = (res.data.files || []).map(f => ({
    name: f.name,
    isDir: false,
    size: f.size,
    type: 'ec-file',
    health: f.health,
    availableShards: f.availableShards,
    totalShards: f.totalShards
}));
    } catch (e) {
        win.fmFiles = [];
    }
    win.fmFilesLoading = false;
},


async loadFmNodes(win) {
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/nodes`);
        win.fmNodes = res.data || [];
    } catch (e) {
        console.error('加载节点失败', e);
        win.fmNodes = [];
    }
},

async selectFmNode(win, node) {
    if (node.status === 'offline') {
        alert(`节点 ${node.name} 当前离线，无法访问`);
        return;
    }

    win.selectedFmNode = node;
    win.selectedFmDisk = null;
    win.selectedVolumeType = null;
    win.selectedPoolVolume = null;
    win.currentPath = '';
    win.fmFiles = [];
    win.selectedFiles = [];
    win.fmDisksLoading = true;
    win.fmEcVolume = null;
    win.fmPoolVolumes = [];
    win.fmHasPool = false;

    try {
        // 并行请求所有数据
        const [disksRes, ecRes, poolRes, volRes] = await Promise.allSettled([
            axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/disks`),
            axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/ec_config`),
            axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/proxy/pool/status`),
            axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/proxy/pool/volumes`)
        ]);

        // 处理磁盘列表
        const disksArray = disksRes.status === 'fulfilled'
            ? (disksRes.value.data.disks || disksRes.value.data || [])
            : [];

        // 处理EC配置
        let ecDisks = [];
        if (ecRes.status === 'fulfilled' && ecRes.value.data?.config?.disks) {
            win.fmEcVolume = ecRes.value.data.config;
            ecDisks = ecRes.value.data.config.disks.map(d => {
                const path = typeof d === 'string' ? d : (d.path || d.mount || '');
                return path.toUpperCase().replace(/\\/g, '/').replace(/\/+$/, '');
            }).filter(Boolean);
        }

        // 处理存储池状态
        let poolDisks = [];
        if (poolRes.status === 'fulfilled' && poolRes.value.data?.disks) {
            win.fmHasPool = poolRes.value.data.disks.length > 0;
            poolDisks = poolRes.value.data.disks.map(d => {
                const path = typeof d === 'string' ? d : (d.disk || d.path || d.mount || '');
                return path.toUpperCase().replace(/\\/g, '/').replace(/\/+$/, '');
            }).filter(Boolean);
        }

        // 处理逻辑卷列表
        if (volRes.status === 'fulfilled') {
            win.fmPoolVolumes = volRes.value.data || [];
        }

        // 过滤磁盘
        win.fmDisks = disksArray.filter(d => {
            if (!d.mount) return false;
            const mount = d.mount.toUpperCase().replace(/\\/g, '/').replace(/\/+$/, '');
            if (['C:', 'C:/', '/'].includes(mount)) return false;
            if (ecDisks.includes(mount)) return false;
            if (poolDisks.includes(mount)) return false;
            return true;
        });
    } catch (e) {
        console.error('加载磁盘失败', e);
        win.fmDisks = [];
    }
    win.fmDisksLoading = false;
},

   async loadEcVolumeFiles(win) {
    win.fmFilesLoading = true;
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/nodes/${win.selectedFmNode.id}/proxy/ec_files`);
        win.fmFiles = (res.data.files || []).map(f => ({
            name: f.name,
            isDir: false,
            size: f.size,
            type: 'ec-file'
        }));
    } catch (e) {
        win.fmFiles = [];
    }
    win.fmFilesLoading = false;
},


        async loadPoolVolumeFiles(win, volume) {
    win.fmFilesLoading = true;
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/nodes/${win.selectedFmNode.id}/proxy/pool/list?volume=${volume.name}&subpath=${win.currentPath}`);
        win.fmFiles = res.data.items || [];
    } catch (e) {
        win.fmFiles = [];
    }
    win.fmFilesLoading = false;
},

async selectFmVolume(win, type, volume) {
    win.selectedFiles = [];
    win.currentPath = '';

    if (type === 'ec') {
        win.selectedVolumeType = 'single-ec';
        win.selectedPoolVolume = null;
        win.selectedFmDisk = null;
        await this.loadEcVolumeFiles(win);
    } else if (type === 'pool') {
        win.selectedVolumeType = 'pool';
        win.selectedPoolVolume = volume;
        win.selectedFmDisk = null;
        await this.loadPoolVolumeFiles(win, volume);
    }
},

async selectFmDisk(win, disk) {
    const mountPath = typeof disk === 'string' ? disk : disk.mount;
    win.selectedFmDisk = mountPath.replace(/\\/g, '/');
    win.selectedVolumeType = 'disk';
    win.selectedPoolVolume = null;
    win.currentPath = '';
    win.selectedFiles = [];
    await this.loadFmFiles(win);
},

async loadFmFiles(win) {
    if (!win.selectedFmNode || !win.selectedFmDisk) return;

    win.fmFilesLoading = true;
    win.fmFiles = [];

    try {
        // 拼接完整路径，确保使用正斜杠
        let fullPath = win.selectedFmDisk.replace(/\\/g, '/');
        if (win.currentPath) {
            fullPath = `${fullPath}/${win.currentPath}`.replace(/\/+/g, '/');
        }

        const res = await axios.get(`${this.apiBaseUrl}/api/files/${win.selectedFmNode.id}/list`, {
            params: { path: fullPath }
        });

        // 兼容多种返回格式
        win.fmFiles = res.data.items || res.data.files || res.data || [];
    } catch (e) {
        console.error('加载文件失败', e);
        win.fmFiles = [];
    }
    win.fmFilesLoading = false;
},
async refreshFileList(win) {
    if (win.selectedVolumeType === 'cross-pool' && win.selectedCrossPoolVolume) {
        await this.selectCrossPoolVolume(win, win.selectedCrossPoolVolume);
    } else if (win.selectedVolumeType === 'cross-ec') {
        await this.loadCrossEcFiles(win);
    } else if (win.selectedVolumeType === 'single-ec') {
        await this.loadEcVolumeFiles(win);
    } else if (win.selectedVolumeType === 'pool') {
        await this.loadPoolVolumeFiles(win, win.selectedPoolVolume);
    } else if (win.selectedFmDisk) {
        await this.loadFmFiles(win);
    }
},
openFileOrFolder(win, file) {
    if (file.is_dir) {
        win.currentPath = win.currentPath ? `${win.currentPath}/${file.name}` : file.name;
        win.selectedFiles = [];
        this.loadFmFiles(win);
    } else {
        // 双击文件 - 预览
        this.previewFile(win, file);
    }
},

goUpFolder(win) {
    if (!win.currentPath) return;
    const parts = win.currentPath.split('/');
    parts.pop();
    win.currentPath = parts.join('/');
    win.selectedFiles = [];
    this.loadFmFiles(win);
},

toggleFileSelect(win, file) {
    if (!win.selectedFiles) win.selectedFiles = [];
    const idx = win.selectedFiles.indexOf(file.name);
    if (idx >= 0) {
        win.selectedFiles.splice(idx, 1);
    } else {
        win.selectedFiles.push(file.name);
    }
},

getFileIcon(filename) {
    const ext = filename.split('.').pop()?.toLowerCase();
    const icons = {
        'pdf': '📕', 'doc': '📘', 'docx': '📘', 'xls': '📗', 'xlsx': '📗',
        'ppt': '📙', 'pptx': '📙', 'txt': '📄', 'md': '📝',
        'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️', 'webp': '🖼️',
        'mp4': '🎬', 'avi': '🎬', 'mkv': '🎬', 'mov': '🎬',
        'mp3': '🎵', 'wav': '🎵', 'flac': '🎵',
        'zip': '📦', 'rar': '📦', '7z': '📦', 'tar': '📦', 'gz': '📦',
        'js': '📜', 'py': '🐍', 'html': '🌐', 'css': '🎨', 'json': '📋'
    };
    return icons[ext] || '📄';
},

formatDate(timestamp) {
    if (!timestamp) return '';
    // 兼容 Unix 时间戳和日期字符串
    let d;
    if (typeof timestamp === 'number') {
        d = new Date(timestamp * 1000);
    } else {
        d = new Date(timestamp);
    }
    if (isNaN(d.getTime())) return '';
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString().slice(0, 5);
},
async handleFmUpload(event, win) {
    const files = event.target.files;
    if (!files.length) return;

    // 跨节点存储池上传
    if (win.selectedVolumeType === 'cross-pool' && win.selectedCrossPool && win.selectedCrossPoolVolume) {
        for (const file of files) {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('subpath', win.selectedCrossPoolVolume.name + (win.currentPath ? '/' + win.currentPath : ''));

            try {
                await axios.post(`${this.apiBaseUrl}/api/cross-pools/${win.selectedCrossPool.id}/upload`, formData, {
                    headers: { 'Content-Type': 'multipart/form-data' }
                });
            } catch (e) {
                alert(`上传 ${file.name} 失败: ${e.response?.data?.error || e.message}`);
            }
        }
        await this.selectCrossPoolVolume(win, win.selectedCrossPoolVolume);
        event.target.value = '';
        return;
    }

    // 跨节点EC上传
    if (win.selectedVolumeType === 'cross-ec') {
        for (const file of files) {
            const formData = new FormData();
            formData.append('file', file);

            try {
                await axios.post(`${this.apiBaseUrl}/api/ec_upload`, formData, {
                    headers: { 'Content-Type': 'multipart/form-data' }
                });
            } catch (e) {
                alert(`上传 ${file.name} 失败: ${e.response?.data?.error || e.message}`);
            }
        }
        alert('上传成功！');
        await this.loadCrossEcFiles(win);
        event.target.value = '';
        return;
    }

    // 单节点EC上传
   // 单节点EC上传
if (win.selectedVolumeType === 'single-ec' && win.selectedFmNode) {
    for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('target', win.selectedFmNode.id);  // 添加这行

        try {
            await axios.post(`${this.apiBaseUrl}/api/ec_upload`, formData, {  // 修改这行
                headers: { 'Content-Type': 'multipart/form-data' }
            });
        } catch (e) {
            alert(`上传 ${file.name} 失败: ${e.response?.data?.error || e.message}`);
        }
    }
    alert('上传成功！');
    await this.loadEcVolumeFiles(win);  // 修改这行，使用正确的刷新方法
    event.target.value = '';
    return;
}

    // 普通磁盘上传
    if (!win.selectedFmNode || !win.selectedFmDisk) {
        alert('请先选择目标节点和磁盘');
        return;
    }

    const formData = new FormData();
    for (let f of files) {
        formData.append('files', f);
    }
    formData.append('disk', win.selectedFmDisk);
    formData.append('path', win.currentPath || '');

    try {
        await axios.post(
            `${this.apiBaseUrl}/api/nodes/${win.selectedFmNode.id}/upload`,
            formData,
            { headers: { 'Content-Type': 'multipart/form-data' } }
        );
        alert('上传成功！');
        this.loadFmFiles(win);
    } catch (e) {
        alert('上传失败: ' + (e.response?.data?.error || e.message));
    }
    event.target.value = '';
},

// 执行跨节点EC健康检查
async performCrossEcHealthCheck(win) {
    win.crossEcHealthChecking = true;
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/cross_ec_config/health_check`);
        win.crossEcHealthReport = {
            healthy: res.data.healthy_files || 0,
            at_risk: res.data.at_risk_files || 0,
            corrupted: res.data.corrupted_files || 0,
            total: res.data.total_files || 0,
            files: res.data.files || []
        };
    } catch (e) {
        alert('健康检查失败: ' + (e.response?.data?.error || e.message));
    }
    win.crossEcHealthChecking = false;
},
// ========== 单节点EC方法 ==========
async openExportSingleEcDialog(win) {
    win.showExportSingleEcDialog = true;
    win.singleExportForm = { selectedDisk: null, exportPath: 'ec_export' };
    win.singleExportProgress = { show: false };
    const nodeId = win.selectedSingleEcNode?.id;
    if (!nodeId) return;

    // 获取非EC磁盘
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/nodes/${nodeId}/disks`);
        const ecDisks = win.singleEcConfig?.disks || [];
        win.singleExportDisks = (res.data.disks || []).filter(d => !ecDisks.includes(d.mount || d.drive));
    } catch (e) { win.singleExportDisks = []; }

    // 通过代理获取EC文件列表
    try {
        const res = await axios.get(`${this.apiBaseUrl}/api/nodes/${nodeId}/proxy/ec/files`);
        win.singleExportFileCount = (res.data.files || []).length;
        win.singleExportFiles = res.data.files || [];
    } catch (e) { win.singleExportFileCount = 0; win.singleExportFiles = []; }
},

async executeExportSingleEcFiles(win) {
    if (!win.singleExportForm.selectedDisk) { alert('请选择目标磁盘'); return; }
    const nodeId = win.selectedSingleEcNode?.id;
    const files = win.singleExportFiles || [];
    if (files.length === 0) { alert('没有文件'); return; }
    if (!confirm(`确定导出 ${files.length} 个文件?`)) return;

    win.singleExportProgress = { show: true, current: 0, total: files.length, status: '准备...' };
    let success = 0, fail = 0;

    for (let i = 0; i < files.length; i++) {
        win.singleExportProgress.current = i + 1;
        win.singleExportProgress.status = `导出: ${files[i].name}`;
        try {
            // 通过代理调用客户端的导出接口
            await axios.post(`${this.apiBaseUrl}/api/nodes/${nodeId}/proxy/ec/export`, {
                filename: files[i].name,
                target_disk: win.singleExportForm.selectedDisk,
                target_path: win.singleExportForm.exportPath || 'ec_export'
            });
            success++;
        } catch (e) { fail++; }
    }

    win.singleExportProgress.show = false;
    win.showExportSingleEcDialog = false;
    alert(`完成！成功 ${success}，失败 ${fail}`);
},

async performSingleEcHealthCheck(win) {
    const nodeId = win.selectedSingleEcNode?.id;
    if (!nodeId) return;
    win.singleEcHealthChecking = true;
    try {
        // 通过代理调用客户端的健康检查接口
        const res = await axios.get(`${this.apiBaseUrl}/api/nodes/${nodeId}/proxy/ec_health_check`);
        win.singleEcHealthReport = {
            healthy: res.data.healthy_files || 0,
            at_risk: res.data.at_risk_files || 0,
            corrupted: res.data.corrupted_files || 0
        };
    } catch (e) { alert('检查失败: ' + (e.response?.data?.error || e.message)); }
    win.singleEcHealthChecking = false;
},

async rebuildSingleEcShards(win) {
    const nodeId = win.selectedSingleEcNode?.id;
    if (!nodeId) return;

    if (!confirm('确定要重建损坏的分片吗？这可能需要一些时间。')) return;

    win.singleEcRebuilding = true;
    try {
        const res = await axios.post(`${this.apiBaseUrl}/api/nodes/${nodeId}/proxy/ec/rebuild`);
        alert(`重建完成！修复 ${res.data.repaired || 0} 个文件`);
        // 重建后刷新健康检查
        this.performSingleEcHealthCheck(win);
    } catch (e) {
        alert('重建失败: ' + (e.response?.data?.error || e.message));
    }
    win.singleEcRebuilding = false;
},
// 获取离线的节点列表
getCrossEcOfflineNodes(win) {
    if (!win.crossEcConfig?.nodes) return [];
    return win.crossEcConfig.nodes.filter(nodeInfo => {
        const nodeId = nodeInfo.node_id || nodeInfo.nodeId;
        return !this.getNodeOnlineStatus(win, nodeId);
    });
},
      hasCrossEcOfflineDisks(win) {
    if (!win.crossEcConfig?.nodes) return false;
    // 检查是否有节点离线或磁盘状态异常
    for (const nodeInfo of win.crossEcConfig.nodes) {
        const nodeId = nodeInfo.node_id || nodeInfo.nodeId;
        if (!this.getNodeOnlineStatus(win, nodeId)) {
            return true; // 节点离线
        }
        // 检查每个磁盘状态
        for (const disk of (nodeInfo.disks || [])) {
            const status = this.getDiskStatus(win, nodeId, disk);
            if (status === 'offline' || status === 'missing' || status === 'replaced') {
                return true;
            }
        }
    }
    return false;
},

async createFolder(win) {
    // 跨节点存储池
    if (win.selectedVolumeType === 'cross-pool') {
        alert('跨节点存储池暂不支持创建文件夹，文件夹会在上传时自动创建');
        return;
    }

    if (!win.selectedFmNode || !win.selectedFmDisk) {
        alert('请先选择节点和磁盘');
        return;
    }
    const name = prompt('请输入文件夹名称:');
    if (!name) return;

    try {
        await axios.post(`${this.apiBaseUrl}/api/nodes/${win.selectedFmNode.id}/mkdir`, {
            disk: win.selectedFmDisk,
            path: win.currentPath ? `${win.currentPath}/${name}` : name
        });
        this.loadFmFiles(win);
    } catch (e) {
        alert('创建失败: ' + (e.response?.data?.error || e.message));
    }
},

async downloadFile(win, file) {
    // 跨节点存储池下载
    if (win.selectedVolumeType === 'cross-pool' && win.selectedCrossPool) {
        const url = `${this.apiBaseUrl}/api/cross-pools/${win.selectedCrossPool.id}/download?filepath=${encodeURIComponent(file.path || file.name)}`;
        window.open(url, '_blank');
        return;
    }

    // 跨节点EC文件下载
if (win.selectedVolumeType === 'cross-ec') {
    if (file.health === 'corrupted') {
        alert(`文件 "${file.name}" 已损坏（可用分片 ${file.availableShards}/${file.totalShards}），无法下载`);
        return;
    }
    const url = `${this.apiBaseUrl}/api/ec_download?name=${encodeURIComponent(file.name)}`;
    window.open(url, '_blank');
    return;
}

    // 普通文件下载
    const url = `${this.apiBaseUrl}/api/nodes/${win.selectedFmNode.id}/download?disk=${encodeURIComponent(win.selectedFmDisk)}&path=${encodeURIComponent(win.currentPath ? `${win.currentPath}/${file.name}` : file.name)}`;
    window.open(url, '_blank');
},

// 预览文件
previewFile(win, file) {
    const ext = file.name.split('.').pop()?.toLowerCase();
    const previewExts = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg', 'pdf', 'mp4', 'webm', 'mp3', 'wav', 'txt', 'json', 'md', 'html', 'css', 'js'];
    const clientPreviewExts = ['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'];

    if (clientPreviewExts.includes(ext)) {
        alert(`"${file.name}" 是 Office 文档，暂不支持在线预览。`);
        return;
    }

    if (!previewExts.includes(ext)) {
        if (confirm(`"${file.name}" 暂不支持预览，是否直接下载？`)) {
            this.downloadFile(win, file);
        }
        return;
    }

    let url;
    // 跨节点存储池预览
    if (win.selectedVolumeType === 'cross-pool' && win.selectedCrossPool) {
        url = `${this.apiBaseUrl}/api/cross-pools/${win.selectedCrossPool.id}/download?filepath=${encodeURIComponent(file.path || file.name)}`;
    }
    // 跨节点EC文件预览
else if (win.selectedVolumeType === 'cross-ec') {
    if (file.health === 'corrupted') {
        alert(`文件 "${file.name}" 已损坏（可用分片 ${file.availableShards}/${file.totalShards}），无法预览`);
        return;
    }
    url = `${this.apiBaseUrl}/api/ec_download?name=${encodeURIComponent(file.name)}`;
}
    // 普通文件预览
    else {
        const path = win.currentPath ? `${win.currentPath}/${file.name}` : file.name;
        url = `${this.apiBaseUrl}/api/nodes/${win.selectedFmNode.id}/preview?disk=${encodeURIComponent(win.selectedFmDisk)}&path=${encodeURIComponent(path)}`;
    }

    win.previewFile = { name: file.name, ext: ext, url: url };
    win.showPreview = true;
},
// 预览选中的第一个文件
previewSelected(win) {
    if (!win.selectedFiles?.length) {
        alert('请先选择文件');
        return;
    }

    // 找到第一个非文件夹的选中项
    for (let name of win.selectedFiles) {
        const file = win.fmFiles.find(f => f.name === name);
        if (file && !file.is_dir) {
            this.previewFile(win, file);
            return;
        }
    }

    alert('请选择一个文件进行预览（不能是文件夹）');
},
// 关闭预览
closePreview(win) {
    win.showPreview = false;
    win.previewFile = null;
},


async downloadSelected(win) {
    for (let name of win.selectedFiles) {
        const file = win.fmFiles.find(f => f.name === name);
        if (file && !file.is_dir) {
            await this.downloadFile(win, file);
        }
    }
},

async deleteFile(win, file) {
    if (!confirm(`确定删除 "${file.name}" 吗？`)) return;

    try {
        // 跨节点存储池删除
        if (win.selectedVolumeType === 'cross-pool' && win.selectedCrossPool) {
            await axios.delete(`${this.apiBaseUrl}/api/cross-pools/${win.selectedCrossPool.id}/files/${file.id || 0}`, {
                params: { filepath: file.path }
            });
            await this.selectCrossPoolVolume(win, win.selectedCrossPoolVolume);
            return;
        }

        // 原有逻辑
        await axios.post(`${this.apiBaseUrl}/api/nodes/${win.selectedFmNode.id}/delete`, {
            disk: win.selectedFmDisk,
            path: win.currentPath ? `${win.currentPath}/${file.name}` : file.name
        });
        this.loadFmFiles(win);
    } catch (e) {
        alert('删除失败: ' + (e.response?.data?.error || e.message));
    }
},

async deleteSelected(win) {
    if (!confirm(`确定删除选中的 ${win.selectedFiles.length} 项吗？`)) return;

    for (let name of win.selectedFiles) {
        try {
            // 跨节点存储池删除
            if (win.selectedVolumeType === 'cross-pool' && win.selectedCrossPool) {
                const file = win.fmFiles.find(f => f.name === name);
                if (file) {
                    await axios.delete(`${this.apiBaseUrl}/api/cross-pools/${win.selectedCrossPool.id}/files/${file.id || 0}`, {
                        params: { filepath: file.path }
                    });
                }
            }
            // 跨节点EC文件删除
            else if (win.selectedVolumeType === 'cross-ec') {
                await axios.delete(`${this.apiBaseUrl}/api/ec_file?name=${encodeURIComponent(name)}`);
            }
            // 单节点EC文件删除
// 单节点EC文件删除
else if (win.selectedVolumeType === 'single-ec') {
    await axios.post(`${this.apiBaseUrl}/api/nodes/${win.selectedFmNode.id}/proxy/batch_delete`, {
        paths: [`ec_volume/${name}`]
    });
}
            // 普通文件删除
            else {
                await axios.delete(`${this.apiBaseUrl}/api/nodes/${win.selectedFmNode.id}/file`, {
                    data: {
                        disk: win.selectedFmDisk,
                        path: win.currentPath ? `${win.currentPath}/${name}` : name
                    }
                });
            }
        } catch (e) {
            console.error('删除失败', name, e);
        }
    }
    win.selectedFiles = [];

    // 刷新文件列表
    if (win.selectedVolumeType === 'cross-pool') {
        await this.selectCrossPoolVolume(win, win.selectedCrossPoolVolume);
    } else if (win.selectedVolumeType === 'cross-ec') {
        this.loadCrossEcFiles(win);
    } else {
        this.loadFmFiles(win);
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
            // 调用 oldapp.py 中新的 /api/files/.../mkdir 接口
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


    // ========== 桌面图标拖拽 ==========
handleIconDblClick(icon) {
    if (this.iconEditMode) return;
    if (icon.action && typeof this[icon.action] === 'function') {
        this[icon.action]();
    }
},

startLongPress(icon) {
    this.cancelLongPress();
    this.longPressTimer = setTimeout(() => {
        this.iconEditMode = true;
    }, 500);
},

cancelLongPress() {
    if (this.longPressTimer) {
        clearTimeout(this.longPressTimer);
        this.longPressTimer = null;
    }
},

exitIconEditMode() {
    if (this.iconEditMode) {
        this.iconEditMode = false;
        this.saveIconLayout();
    }
},

onIconDragStart(event, icon) {
    if (!this.iconEditMode) {
        event.preventDefault();
        return;
    }
    this.draggedIcon = icon.id;
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', icon.id);
},

onIconDragEnd() {
    this.draggedIcon = null;
},

onIconDragOver(event, icon) {
    if (!this.iconEditMode || this.draggedIcon === icon.id) return;
    event.preventDefault();
},

onIconDrop(event, targetIcon) {
    if (!this.iconEditMode) return;
    event.preventDefault();

    const draggedId = event.dataTransfer.getData('text/plain');
    if (draggedId === targetIcon.id) return;

    const draggedIndex = this.desktopIcons.findIndex(i => i.id === draggedId);
    const targetIndex = this.desktopIcons.findIndex(i => i.id === targetIcon.id);

    if (draggedIndex < 0 || targetIndex < 0) return;

    // 交换顺序
    const draggedOrder = this.desktopIcons[draggedIndex].order;
    this.desktopIcons[draggedIndex].order = this.desktopIcons[targetIndex].order;
    this.desktopIcons[targetIndex].order = draggedOrder;

    // 重新排序数组
    this.desktopIcons.sort((a, b) => a.order - b.order);

    // 重置order值
    this.desktopIcons.forEach((icon, idx) => {
        icon.order = idx;
    });

    this.saveIconLayout();
    this.draggedIcon = null;
},

saveIconLayout() {
    safeStorage.setItem('adminDesktopIcons', JSON.stringify(this.desktopIcons));
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
            // 更新本地节点数据
            const permWindow = this.windows.find(w => w.type === 'permissions');
            if (permWindow && permWindow.nodes) {
                const node = permWindow.nodes.find(n => n.id === nodeId);
                if (node) {
                    node.access_policy = policy;
                }
                if (permWindow.nodePolicies) {
                    permWindow.nodePolicies[nodeId] = policy;
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
    // 为每个磁盘添加 selected 属性
    window.encryptionDisks = res.data.disks.map(disk => ({
      ...disk,
      selected: false
    }));
  } catch (err) {
    console.error('加载磁盘加密状态失败:', err);
    alert('加载磁盘加密状态失败');
  } finally {
    window.loading = false;
  }
},
// 判断磁盘是否被排除
isDiskExcluded(mount) {
  if (!mount) return false;
  const m = mount.toUpperCase();
  return m === 'C:' || m === 'D:' || m.startsWith('C:') || m.startsWith('D:') || m === '/C' || m === '/D';
},

// 获取已选中的磁盘数量
getSelectedDisksCount(window) {
  if (!window.encryptionDisks) return 0;
  return window.encryptionDisks.filter(d => d.selected && !this.isDiskExcluded(d.mount) && !d.is_encrypted).length;
},

// 判断是否全选了可加密磁盘
isAllEncryptableSelected(window) {
  if (!window.encryptionDisks) return false;
  const encryptable = window.encryptionDisks.filter(d => !this.isDiskExcluded(d.mount) && !d.is_encrypted);
  if (encryptable.length === 0) return false;
  return encryptable.every(d => d.selected);
},

// 切换全选可加密磁盘
toggleSelectAllEncryptable(window) {
  const allSelected = this.isAllEncryptableSelected(window);
  window.encryptionDisks.forEach(disk => {
    if (!this.isDiskExcluded(disk.mount) && !disk.is_encrypted) {
      disk.selected = !allSelected;
    }
  });
},

// 批量加密磁盘
async batchEncryptDisks(window) {
  const selectedDisks = window.encryptionDisks.filter(d => d.selected && !this.isDiskExcluded(d.mount) && !d.is_encrypted);
  if (selectedDisks.length === 0) {
    alert('请选择要加密的磁盘');
    return;
  }

  const password = prompt(`请输入为 ${selectedDisks.length} 个磁盘设置的统一密码：`);
  if (!password) return;

  const confirmPassword = prompt('请再次确认密码：');
  if (password !== confirmPassword) {
    alert('两次密码不一致');
    return;
  }

  const diskList = selectedDisks.map(d => d.mount).join(', ');
  if (!confirm(`确认要加密以下磁盘？\n${diskList}\n\n此操作将对选中的 ${selectedDisks.length} 个磁盘启用加密。`)) return;

  let successCount = 0;
  let failCount = 0;

  for (const disk of selectedDisks) {
    try {
      const res = await axios.post(`${this.apiBaseUrl}/api/encryption/disk/encrypt`, {
        node_id: window.selectedNodeId,
        mount: disk.mount,
        password
      });
      if (res.data.success) {
        successCount++;
      } else {
        failCount++;
      }
    } catch (err) {
      failCount++;
      console.error(`加密磁盘 ${disk.mount} 失败:`, err);
    }
  }

  alert(`批量加密完成！\n成功: ${successCount} 个\n失败: ${failCount} 个`);
  await this.loadEncryptionDisks(window);
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
      // 先立即更新本地状态
      const disk = window.encryptionDisks.find(d => d.mount === mount);
      if (disk) {
        disk.is_encrypted = true;
        disk.is_locked = false;
      }
      // 再刷新最新数据
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


// 修改磁盘加密密码
async changePassword(window, nodeId, mount) {
  const newPassword = prompt(`请输入磁盘 ${mount} 的新密码：`);
  if (!newPassword) return;

  const confirmPassword = prompt('请再次确认新密码：');
  if (newPassword !== confirmPassword) {
    alert('两次输入的密码不一致');
    return;
  }

  try {
    const res = await axios.post(`${this.apiBaseUrl}/api/encryption/disk/change-password`, {
      node_id: nodeId,
      mount: mount,
      new_password: newPassword
    });
    if (res.data.success) {
      alert('密码修改成功');
    }
  } catch (err) {
    alert('修改密码失败: ' + (err.response?.data?.error || err.message));
  }
},

// 创建节点存储池
async createNodePool(win) {
    if (!win.selectedPoolNode) return;

    try {
        const disksRes = await axios.get(`${this.apiBaseUrl}/api/nodes/${win.selectedPoolNode.id}/proxy/pool/available-disks`);
        let availableDisks = disksRes.data || [];

        // 排除C盘和D盘
        const excludedDrives = ['C:', 'D:', 'c:', 'd:', '/c', '/d', 'C', 'D'];
        availableDisks = availableDisks.filter(disk => {
            const path = typeof disk === 'string' ? disk : (disk.drive || disk.path || disk.mount || '');
            return !excludedDrives.some(ex => path.toUpperCase().startsWith(ex.toUpperCase()));
        });

        // 格式化磁盘数据
        win.createPoolDisks = availableDisks.map(disk => {
            if (typeof disk === 'string') return { drive: disk, total: 0, free: 0 };
            return {
                drive: disk.drive || disk.path || disk.mount || '未知',
                total: disk.total || 0,
                free: disk.free || 0
            };
        });
        win.createPoolSelected = [];
        win.showCreatePoolDialog = true;
    } catch (e) {
        alert('获取磁盘列表失败: ' + (e.response?.data?.error || e.message));
    }
},

toggleCreatePoolDisk(win, drive) {
    const idx = win.createPoolSelected.indexOf(drive);
    if (idx >= 0) {
        win.createPoolSelected.splice(idx, 1);
    } else {
        win.createPoolSelected.push(drive);
    }
},

async confirmCreateNodePool(win) {
    if (!win.createPoolSelected?.length) return;

    try {
        await axios.post(`${this.apiBaseUrl}/api/nodes/${win.selectedPoolNode.id}/proxy/pool/create`, {
            name: '主存储池',
            disks: win.createPoolSelected
        });
        alert('存储池创建成功！');
        win.showCreatePoolDialog = false;
        this.refreshNodePool(win);
    } catch (e) {
        alert('创建失败: ' + (e.response?.data?.error || e.message));
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
      this.setBackground(e.target.result);
    };
    reader.readAsDataURL(file);
  },

 setBackground(preset) {
    const bg = preset || this.backgroundFile || this.backgroundUrl;
    if (bg) {
      this.desktopBackground = bg;
      safeStorage.setItem('desktopBackground', bg);
    }
    this.showBackgroundDialog = false;
  },
  resetBackground() {
    this.desktopBackground = '';
    this.backgroundUrl = '';
    this.backgroundFile = null;
    safeStorage.removeItem('desktopBackground');
    this.showBackgroundDialog = false;
  }

     }

}).mount('#app');