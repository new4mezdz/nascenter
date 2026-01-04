// helpContent.js - 帮助文档内容配置（说明书风格）
const helpContent = {
    // 目录
    chapters: [
        { id: 'quickstart', title: '快速入门', icon: '🚀' },
        { id: 'nodes', title: '节点管理', icon: '🖥️' },
        { id: 'space', title: '空间分配', icon: '📦' },
        { id: 'permission', title: '权限设置', icon: '🔒' },
        { id: 'encryption', title: '加密管理', icon: '🔐' },
        { id: 'ec', title: '纠删码配置', icon: '🛡️' },
        { id: 'files', title: '文件管理', icon: '📁' },
        { id: 'monitor', title: '系统监控', icon: '📊' },
        { id: 'settings', title: '系统设置', icon: '⚙️' },
        { id: 'faq', title: '常见问题', icon: '💡' }
    ],

    // 各章节内容
    sections: {
        // ========== 快速入门 ==========
        quickstart: {
            title: '快速入门',
            blocks: [
                { type: 'text', content: '欢迎使用 NAS Center 管理系统！本章将引导您快速了解系统的基本操作流程。' },
                { type: 'image', src: '/images/help/1.png', caption: '系统主界面概览' },

               { type: 'heading', content: '第一步：配置节点' },
{ type: 'text', content: '节点是您的NAS存储设备。首先需要在节点设备上完成配置，使其注册到管理系统。' },
{ type: 'steps', items: [
    { title: '启动节点服务', text: '在NAS设备上安装并启动节点服务', image: '/images/help/2.png' },
    { title: '访问配置页面', text: '浏览器打开节点地址，进入配置向导', image: '/images/help/3.png' },
    { title: '填写配置信息', text: '输入管理端地址、节点ID和共享密钥，点击保存', }
]},
{ type: 'tip', content: '配置成功后，节点会自动出现在管理端的"节点管理"中。' },
                { type: 'tip', content: '确保节点设备已开机，且与管理端在同一网络中。' },

                { type: 'heading', content: '第二步：访问节点' },
                { type: 'text', content: '节点添加成功并显示"在线"状态后，即可访问节点。' },
                { type: 'list', items: [
                    { label: '双击节点', desc: '在节点列表中双击在线节点，进入节点桌面' },
                    { label: '点击访问按钮', desc: '或点击节点右侧的"访问"按钮' }
                ]},

                { type: 'heading', content: '第三步：配置权限' },
                { type: 'text', content: '如果需要让其他用户访问节点，请在"权限设置"中进行配置。' },
                { type: 'warning', content: '默认情况下，只有管理员可以访问所有节点。普通用户需要单独授权。' }
            ]
        },

        // ========== 节点管理 ==========
        nodes: {
            title: '节点管理',
            blocks: [
                { type: 'text', content: '节点管理是系统的核心功能，用于管理所有连接的NAS存储设备。您可以添加、删除、重命名节点，以及查看节点状态。' },
                { type: 'image', src: '/images/help/4.png', caption: '节点管理界面' },

                { type: 'heading', content: '节点状态说明' },
                { type: 'list', items: [
                    { label: '🟢 在线', desc: '节点运行正常，可以访问' },
                    { label: '🔴 离线', desc: '节点无法连接，请检查网络和设备状态' },
                    { label: '🟡 警告', desc: '节点存在异常，如磁盘空间不足等' }
                ]},

                { type: 'heading', content: '添加节点' },
{ type: 'text', content: '节点需要在节点设备上进行配置，主动注册到管理端。' },
{ type: 'steps', items: [
    { title: '启动节点服务', text: '在NAS设备上首次启动节点服务' },
    { title: '打开配置向导', text: '浏览器访问节点地址，自动进入配置向导页面' },
    { title: '填写管理端地址', text: '输入管理端的URL地址，如 http://192.168.1.100:8080' },
    { title: '设置节点ID', text: '输入节点的唯一标识，如 node-1、办公室NAS 等' },
    { title: '输入共享密钥', text: '输入与管理端配置一致的通信密钥' },
    { title: '测试并保存', text: '点击"测试连接"确认无误后，保存配置完成注册' }
]},
{ type: 'image', src: '/images/help/3.png', caption: '节点配置向导' },
{ type: 'tip', content: '配置成功后，节点会自动出现在管理端的节点列表中。' },
{ type: 'warning', content: '共享密钥必须与管理端配置的密钥完全一致，否则无法连接。' },
                { type: 'tip', content: '添加前请确保节点已安装并运行 NAS Center 节点服务。' },

                { type: 'heading', content: '节点操作' },
                { type: 'text', content: '每个节点右侧提供以下操作按钮：' },
                { type: 'list', items: [
                    { label: '访问', desc: '进入节点桌面环境，管理节点文件和设置' },
                    { label: '磁盘', desc: '查看节点的磁盘列表、容量和加密状态' },
                    { label: '重命名', desc: '修改节点的显示名称，便于识别' },
                    { label: '删除', desc: '从管理系统中移除该节点' }
                ]},
                { type: 'image', src: '/images/help/5.png', caption: '节点操作按钮' },
                { type: 'warning', content: '删除节点只是从管理系统中移除，不会影响节点设备上的数据。' }
            ]
        },

        // ========== 空间分配 ==========
        // ========== 空间分配 ==========
space: {
    title: '空间分配',
    blocks: [
        { type: 'text', content: '空间分配功能允许您管理存储资源，包括单节点存储池和跨节点存储池的配置与管理。' },
        { type: 'image', src: '/images/help/6.png', caption: '空间分配界面' },

        { type: 'heading', content: '存储池类型' },
        { type: 'list', items: [
            { label: '单节点存储池', desc: '将单个节点内的多块磁盘组合，适合小规模使用' },
            { label: '跨节点存储池', desc: '将多个节点的磁盘组合成统一存储空间，支持容量扩展和节点级容错' }
        ]},

        { type: 'heading', content: '单节点存储池' },
        { type: 'text', content: '在单个节点内创建存储池，将多块磁盘合并管理。' },
        { type: 'steps', items: [
            { title: '进入节点', text: '访问目标节点的桌面环境' },
            { title: '打开空间池', text: '双击"空间池"图标' },
            { title: '创建存储池', text: '选择磁盘并创建存储池' },
            { title: '创建逻辑卷', text: '在存储池中创建逻辑卷（如电影、文档等）' }
        ]},

        { type: 'heading', content: '跨节点存储池' },
        { type: 'text', content: '跨节点存储池将多个节点的存储空间整合为统一的存储池，实现容量扩展和数据保护。' },
        { type: 'image', src: '/images/help/7.png', caption: '跨节点存储池架构' },

        { type: 'heading', content: '创建跨节点存储池' },
        { type: 'steps', items: [
            { title: '确保节点在线', text: '所有参与的节点必须处于在线状态' },
            { title: '打开空间分配', text: '在管理端双击"空间分配"图标' },
            { title: '选择节点和磁盘', text: '从各节点中选择要加入池的磁盘' },
            { title: '设置分配策略', text: '选择数据分布策略（空间优先/轮询等）' },
            { title: '创建存储池', text: '确认配置后创建存储池' }
        ]},

        { type: 'heading', content: '数据分布策略' },
        { type: 'list', items: [
            { label: '空间优先', desc: '优先使用剩余空间最大的节点/磁盘，适合大文件存储' },
            { label: '轮询分布', desc: '依次在各节点间轮流存储，均衡写入负载' },
            { label: '按比例分配', desc: '根据各磁盘剩余空间比例分配' }
        ]},

        { type: 'heading', content: '扩容跨节点存储池' },
        { type: 'list', items: [
            { label: '添加节点', desc: '将新节点的磁盘加入现有存储池' },
            { label: '添加磁盘', desc: '向已有节点添加新磁盘到池中' },
            { label: '数据重平衡', desc: '添加容量后执行数据重平衡，均匀分布数据' }
        ]},
        { type: 'tip', content: '扩容操作不会中断服务，但数据重平衡期间性能可能受影响。' },

        { type: 'heading', content: '用户专属空间' },
{ type: 'text', content: '可以为用户创建专属的存储空间，通过逻辑卷+加密实现隔离。' },
{ type: 'steps', items: [
    { title: '创建逻辑卷', text: '在存储池中创建以用户名命名的逻辑卷（如 zhangsan、lisi）' },
    { title: '设置容量', text: '指定逻辑卷大小，即该用户可用的存储空间' },
    { title: '启用加密', text: '对逻辑卷进行加密，确保数据隔离和安全' }
]},
{ type: 'tip', content: '通过逻辑卷大小控制用户可用空间，加密确保其他用户无法访问。' },
    ]
},

        // ========== 权限设置 ==========
        permission: {
            title: '权限设置',
            blocks: [
                { type: 'heading', content: '用户管理' },
{ type: 'text', content: '在用户管理标签页中，您可以查看所有用户、创建新用户、修改用户信息或删除用户。' },

{ type: 'heading', content: '用户角色' },
{ type: 'list', items: [
    { label: '👑 管理员', desc: '拥有系统全部权限，可访问所有节点、管理用户、修改系统设置' },
    { label: '👤 普通用户', desc: '根据权限配置访问指定节点，可进行文件操作' },
    { label: '👁️ 访客', desc: '受限访问，通常只能查看，不能修改' }
]},

{ type: 'heading', content: '文件权限' },
{ type: 'list', items: [
    { label: '👁️ 只读', desc: '只能浏览和下载文件，不能上传、删除或修改' },
    { label: '✏️ 读写', desc: '可以浏览、下载、上传文件，可以创建文件夹' },
    { label: '🔓 完全控制', desc: '拥有所有文件操作权限，包括删除、重命名、移动等' }
]},

{ type: 'heading', content: '节点权限' },
{ type: 'list', items: [
    { label: '✓ 所有节点', desc: '用户可访问系统中的所有节点' },
    { label: '📁 按分组', desc: '用户只能访问指定分组内的节点' },
    { label: '🎯 自定义', desc: '手动指定用户可访问的具体节点列表' }
]},

                { type: 'heading', content: '节点分组' },
                { type: 'text', content: '您可以将节点按用途或位置分组，便于批量授权。' },
                { type: 'steps', items: [
                    { title: '创建分组', text: '点击"新建分组"，输入分组名称和描述' },
                    { title: '添加节点', text: '选择要加入该分组的节点' },
                    { title: '保存分组', text: '点击保存完成分组创建' }
                ]},
                { type: 'image', src: '/images/help/9.png', caption: '节点分组管理' },

                { type: 'heading', content: '用户权限类型' },
                { type: 'text', content: '为用户分配节点访问权限时，有以下三种模式：' },
                { type: 'list', items: [
                    { label: '全部节点', desc: '用户可访问系统中的所有节点' },
                    { label: '按分组', desc: '用户可访问指定分组内的所有节点' },
                    { label: '自定义', desc: '手动指定用户可访问的具体节点' }
                ]},
                { type: 'tip', content: '推荐使用"按分组"模式，便于统一管理和后续维护。' },

                { type: 'heading', content: '节点控制' },
{ type: 'text', content: '节点控制允许管理员为每个节点单独设置访问策略，控制哪些用户可以访问该节点。' },
{ type: 'image', src: '/images/help/10.png', caption: '节点控制界面' },
{ type: 'list', items: [
    { label: '所有用户', desc: '任何已登录用户都可以访问该节点' },
    { label: '仅管理员', desc: '只有管理员角色可以访问' },
    { label: '白名单用户', desc: '只有白名单中的用户可以访问' },
    { label: '禁止访问', desc: '所有用户都无法访问该节点' },
        { type: 'image', src: '/images/help/11.png', caption: '访问策略界面' },
]},

{ type: 'heading', content: '白名单管理' },
{ type: 'text', content: '当节点设置为"白名单用户"策略时，只有在白名单中的用户才能访问。' },
{ type: 'steps', items: [
    { title: '添加用户', text: '在下拉菜单中选择要加入白名单的用户' },
    { title: '查看列表', text: '右侧显示当前白名单中的所有用户' },
    { title: '移除用户', text: '点击用户旁的"移除"按钮可将其从白名单删除' }
]},
{ type: 'tip', content: '白名单是全局的，加入白名单的用户可以访问所有设置为"白名单用户"策略的节点。' },
            ]
        },

        // ========== 加密管理 ==========
        encryption: {
    title: '加密管理',
    blocks: [
        { type: 'text', content: '加密管理功能用于保护节点磁盘数据安全，支持对磁盘进行加密、解密、锁定和解锁操作。' },

        { type: 'heading', content: '总览页面' },
        { type: 'text', content: '进入加密管理后首先看到节点总览页面，显示所有节点的加密状态概览。' },
        { type: 'image', src: '/images/help/12.png', caption: '加密管理总览' },
        { type: 'list', items: [
            { label: '总节点数', desc: '系统中所有已添加的节点数量' },
            { label: '在线节点', desc: '当前处于在线状态的节点数量' },
            { label: '已加密节点', desc: '至少有一个磁盘已加密的节点数量' },
            { label: '已锁定磁盘', desc: '所有节点中处于锁定状态的磁盘总数' }
        ]},
        { type: 'tip', content: '点击任意节点卡片可进入该节点的磁盘加密管理页面。' },

        { type: 'heading', content: '磁盘加密管理' },
        { type: 'text', content: '选择节点后进入磁盘加密管理页面，可查看和操作该节点的所有磁盘。' },
        { type: 'image', src: '/images/help/13.png', caption: '磁盘加密管理' },

        { type: 'heading', content: '磁盘状态说明' },
        { type: 'list', items: [
            { label: '系统保护', desc: '系统盘（C:、D:）自动排除，不可进行加密操作' },
            { label: '未加密', desc: '磁盘未启用加密保护，可点击"启用加密"' },
            { label: '✅ 已加密', desc: '磁盘已加密且已解锁，可正常读写' },
            { label: '🔒 已锁定', desc: '磁盘已加密且已锁定，需输入密码解锁后才能访问' }
        ]},

       { type: 'heading', content: '磁盘操作' },
{ type: 'list', items: [
    { label: '🔐 启用加密', desc: '对未加密的磁盘进行加密，设置密码后磁盘数据将被保护' },
    { label: '🔓 解锁', desc: '输入密码解锁磁盘，密码保存在内存中实时解密，重启后需重新解锁' },
    { label: '🔒 锁定', desc: '清除内存中的密码，磁盘立即变为不可访问，文件管理中无法浏览' },
    { label: '🧹 永久解密', desc: '彻底移除加密保护，磁盘恢复为普通状态，数据变为明文存储' },
    { label: '🔑 改密码', desc: '修改加密密码，需要先输入旧密码验证身份' }
]},

{ type: 'heading', content: '锁定与解锁原理' },
{ type: 'text', content: '磁盘加密采用实时加解密机制，解锁时密码保存在内存中，读写数据时自动进行加解密操作。' },
{ type: 'list', items: [
    { label: '已锁定状态', desc: '文件管理中无法浏览该磁盘内容，显示为不可访问' },
    { label: '已解锁状态', desc: '可正常浏览和读写文件，与普通磁盘使用体验一致' },
    { label: '重启后', desc: '节点重启后加密磁盘自动变为锁定状态，需重新输入密码解锁' }
]},
{ type: 'tip', content: '建议在不使用时锁定加密磁盘，即使设备被盗也无法读取数据。' },

        { type: 'heading', content: '批量操作' },
        { type: 'text', content: '可以勾选多个未加密磁盘，点击"批量启用加密"一次性加密多个磁盘。' },
        { type: 'tip', content: '批量加密时所有选中的磁盘将使用相同的密码。' },

        { type: 'warning', content: '加密密码非常重要！遗忘密码将无法恢复数据，请务必妥善保管。' }
    ]
},

        // ========== 纠删码配置 ==========
        // ========== 纠删码配置 ==========
ec: {
    title: '纠删码配置',
    blocks: [
        { type: 'text', content: '纠删码（Erasure Coding，简称EC）是一种数据保护技术，将数据分散存储到多个磁盘或节点，即使部分故障也能恢复完整数据。' },
        { type: 'image', src: '/images/help/14.png', caption: '纠删码配置界面' },

        { type: 'heading', content: '基本概念' },
        { type: 'list', items: [
            { label: 'K值（数据块）', desc: '原始数据被分割成的块数' },
            { label: 'M值（校验块）', desc: '额外生成的冗余校验块数' },
            { label: '容错能力', desc: '最多可容忍M个磁盘/节点同时故障' }
        ]},
        { type: 'text', content: '例如：K=4, M=2 表示数据分成4块，加上2块校验，共6块。任意丢失2块都能恢复完整数据。' },

        { type: 'heading', content: '单节点纠删码' },
        { type: 'text', content: '在单个节点内配置纠删码，保护数据免受磁盘故障影响。' },
        { type: 'list', items: [
            { label: '适用场景', desc: '单节点多磁盘环境，防止单块磁盘故障导致数据丢失' },
            { label: '容错级别', desc: '磁盘级容错，无法防护节点整体故障' }
        ]},

        { type: 'heading', content: '跨节点纠删码' },
        { type: 'text', content: '跨节点纠删码将数据分散存储到多个节点，提供节点级容错能力。' },
        { type: 'image', src: '/images/help/15.png', caption: '跨节点纠删码架构' },
        { type: 'list', items: [
            { label: '适用场景', desc: '多节点环境，需要高可用性和数据安全' },
            { label: '容错级别', desc: '节点级容错，即使整个节点故障数据仍可访问' },
            { label: '最低要求', desc: '至少需要 K+M 个节点参与' }
        ]},

        { type: 'heading', content: '配置跨节点纠删码' },
        { type: 'steps', items: [
            { title: '打开纠删码配置', text: '在管理端双击"纠删码配置"图标' },
            { title: '设置K和M值', text: '根据节点数量和容错需求设置参数' },
            { title: '选择节点磁盘', text: '从各节点中选择参与纠删码的磁盘' },
            { title: '确认配置', text: '检查容量预估，确认后保存配置' }
        ]},

        { type: 'heading', content: '推荐配置' },
        { type: 'list', items: [
            { label: '3节点', desc: 'K=2, M=1，容忍1个节点故障，存储效率67%' },
            { label: '6节点', desc: 'K=4, M=2，容忍2个节点故障，存储效率67%' },
            { label: '10+节点', desc: 'K=8, M=2，容忍2个节点故障，存储效率80%' }
        ]},
        { type: 'tip', content: 'K值越大存储效率越高，但需要更多节点。M值决定容错能力。' },

        { type: 'heading', content: '容量计算' },
        { type: 'text', content: '跨节点纠删码的可用容量计算公式：' },
        { type: 'text', content: '可用容量 = 最小磁盘容量 × K' },
        { type: 'text', content: '例如：6块1TB磁盘，K=4, M=2，可用容量约为 4TB（而非6TB）。' },

        { type: 'heading', content: '故障恢复' },
        { type: 'list', items: [
            { label: '自动检测', desc: '系统自动检测节点/磁盘故障' },
            { label: '降级运行', desc: '在M个以内节点故障时，数据仍可正常读写' },
            { label: '数据重建', desc: '故障节点恢复或替换后，自动重建丢失的数据块' }
        ]},
        { type: 'warning', content: '如果同时故障超过M个节点，数据将无法访问！请确保及时处理故障节点。' },

        { type: 'heading', content: '性能影响' },
        { type: 'text', content: '纠删码需要额外的计算资源：' },
        { type: 'list', items: [
            { label: '写入性能', desc: '需要计算校验块，写入速度略有下降' },
            { label: '读取性能', desc: '正常情况下读取性能基本不受影响' },
            { label: '恢复性能', desc: '数据恢复时需要读取K块数据进行重建' }
        ]},
        { type: 'tip', content: '现代CPU的纠删码计算速度很快，通常瓶颈在网络和磁盘IO。' }
    ]
},

        // ========== 文件管理 ==========
        files: {
            title: '文件管理',
            blocks: [
                { type: 'text', content: '文件管理功能允许您浏览和管理节点上的文件，支持上传、下载、删除、重命名等常用操作。' },
                { type: 'image', src: '/images/help/16.png', caption: '文件管理界面' },

                { type: 'heading', content: '浏览文件' },
                { type: 'text', content: '选择节点和目录后，即可查看该目录下的所有文件和文件夹。支持双击进入子目录。' },

                { type: 'heading', content: '文件操作' },
                { type: 'list', items: [
                    { label: '上传', desc: '将本地文件上传到当前目录' },
                    { label: '下载', desc: '将选中的文件下载到本地' },
                    { label: '删除', desc: '删除选中的文件或文件夹' },
                    { label: '重命名', desc: '修改文件或文件夹名称' },
                    { label: '新建文件夹', desc: '在当前目录创建新文件夹' }
                ]},
                { type: 'tip', content: '支持批量选择文件进行操作，按住Ctrl键可多选。' }
            ]
        },

        // ========== 系统监控 ==========
        monitor: {
            title: '系统监控',
            blocks: [
                { type: 'text', content: '系统监控提供各节点的实时运行状态，包括CPU、内存、磁盘、网络等资源使用情况。' },
                { type: 'image', src: '/images/help/17.png', caption: '系统监控界面' },

                { type: 'heading', content: '监控指标' },
                { type: 'list', items: [
                    { label: 'CPU使用率', desc: '处理器负载情况，过高可能影响性能' },
                    { label: '内存使用', desc: '已用内存和可用内存' },
                    { label: '磁盘IO', desc: '磁盘读写速度和队列情况' },
                    { label: '网络流量', desc: '上传和下载带宽使用情况' }
                ]},

                { type: 'heading', content: '告警提示' },
                { type: 'text', content: '当资源使用超过阈值时，系统会显示告警提示：' },
                { type: 'list', items: [
                    { label: '黄色警告', desc: '资源使用偏高，建议关注' },
                    { label: '红色告警', desc: '资源使用过高，需要及时处理' }
                ]},
                { type: 'tip', content: '监控数据每5秒自动刷新一次。' }
            ]
        },

        // ========== 系统设置 ==========
        settings: {
            title: '系统设置',
            blocks: [
                { type: 'text', content: '系统设置包含一些全局配置选项，如桌面背景、通信密钥等。' },
                { type: 'image', src: '/images/help/18.png', caption: '系统设置界面' },

                { type: 'heading', content: '桌面背景' },
                { type: 'text', content: '您可以自定义管理端的桌面背景，支持预设渐变色或上传自定义图片。' },
                { type: 'list', items: [
                    { label: '预设背景', desc: '选择系统提供的渐变色背景' },
                    { label: '自定义图片', desc: '上传自己喜欢的图片作为背景' }
                ]},

                { type: 'heading', content: '通信密钥' },
                { type: 'text', content: '通信密钥用于管理端与节点之间的安全通信。' },
                { type: 'warning', content: '修改密钥后，所有节点将立即离线！需要手动更新每个节点的密钥配置才能重新连接。' },
                { type: 'steps', items: [
                    { title: '打开设置', text: '点击开始菜单 → 系统设置 → 修改密钥' },
                    { title: '输入新密钥', text: '输入新的通信密钥' },
                    { title: '更新节点', text: '在每个节点上同步更新密钥配置' }
                ]},

                { type: 'heading', content: '桌面图标管理' },
                { type: 'text', content: '长按桌面图标可进入编辑模式，拖拽图标可调整位置。' }
            ]
        },

        // ========== 常见问题 ==========
        faq: {
            title: '常见问题',
            blocks: [
               { type: 'heading', content: '如何修改通信密钥？' },
{ type: 'text', content: '点击开始菜单 → 设置 → 通信密钥，输入新密钥后保存。' },
{ type: 'warning', content: '修改后需同步更新所有节点配置文件中的密钥，否则节点将无法连接。' },

{ type: 'heading', content: '用户角色有什么区别？' },
{ type: 'list', items: [
    { label: 'admin', desc: '管理员，拥有完全控制权限，可管理所有功能' },
    { label: 'user', desc: '普通用户，拥有读写权限' },
    { label: 'guest', desc: '访客，仅有只读权限' }
]},

{ type: 'heading', content: '如何限制用户只能访问特定节点？' },
{ type: 'text', content: '在权限设置中，点击用户的"节点访问"列，可设置：' },
{ type: 'list', items: [
    { label: '全部节点', desc: '用户可访问所有节点' },
    { label: '按分组', desc: '用户只能访问指定分组内的节点' },
    { label: '自定义', desc: '精确控制允许/禁止访问的节点' }
]},

{ type: 'heading', content: '什么是跨节点纠删码？' },
{ type: 'text', content: '跨节点纠删码将数据分片存储在多个节点的磁盘上。即使部分节点离线，仍可恢复完整数据。配置时需选择至少2个节点，总磁盘数需≥k+m。' },

{ type: 'heading', content: '如何修改账户密码？' },
{ type: 'text', content: '点击右上角用户头像 → 修改密码，输入新密码后确认。修改成功后需重新登录。' },
            ]
        }
    }
};