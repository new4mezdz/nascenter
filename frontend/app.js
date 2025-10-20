const { createApp } = Vue;

    createApp({
      data() {
        return {
          windows: [],
          nextWindowId: 1,
          maxZIndex: 100,
          currentTime: '',
          dragWindow: null,
          dragOffset: { x: 0, y: 0 },
          apiBaseUrl: 'http://127.0.0.1:8080',
          showStartMenu: false,
    showNavbar: false,
    currentNodeName: 'NAS Center 主控'
        };
      },
      mounted() {
        this.updateTime();
        setInterval(() => this.updateTime(), 1000);
        this.openNodeManagement();
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

    accessNode(node) {
  const url = `http://${node.ip}:${node.port}`;

  if (node.status === 'offline') {
    alert(`节点 ${node.name} 当前离线,无法访问`);
    return;
  }

  const confirmed = confirm(
    `访问节点后将在新窗口打开\n顶部导航栏可帮助您返回主控中心\n\n` +
    `节点名称: ${node.name}\n` +
    `访问地址: ${url}\n\n` +
    `是否继续?`
  );

  if (confirmed) {
    // 显示导航栏
    this.showNavbar = true;
    this.currentNodeName = node.name;

    // 在新窗口打开
    window.open(url, '_blank');
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
      const texts = { online: '在线', offline: '离线', warning: '警告' };
      return texts[status] || '未知';
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
      this.createWindow({
        type: 'permissions',
        title: '权限管理',
        icon: '🔒',
        width: 1100,
        height: 700
      });
    },

    // ============ 加密管理 ============
    openEncryptionManager() {
      this.createWindow({
        type: 'encryption',
        title: '加密管理',
        icon: '🔐',
        width: 1000,
        height: 700,
        encryptionTab: 'disk'  // 默认显示磁盘加密标签页
      });
    },

    // ============ 纠删码配置 ============
    openECConfig() {
      alert('纠删码配置功能开发中...');
    },

    // ============ 系统监控 ============
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
  window.title = `系统监控 - ${node.name}`; // 动态改变窗口标题
  try {
    const res = await axios.get(`${this.apiBaseUrl}/api/nodes/${node.id}/monitor-stats`);
    window.selectedNodeStats = res.data;
    window.monitorView = 'detail'; // 切换到详情视图
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

refreshCurrentNode() {
  alert(`刷新节点: ${this.currentNodeName}`);
}

  }
}).mount('#app');