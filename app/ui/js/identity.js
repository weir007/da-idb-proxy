// 租户内部页面逻辑

let currentRealm = '';
let currentModule = 'user';

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    // 从URL参数获取realm
    const urlParams = new URLSearchParams(window.location.search);
    currentRealm = urlParams.get('realm') || '';

    // 初始化租户选择器
    initTenantSelector();

    // 设置事件监听器
    setupEventListeners();

    // 加载当前模块数据
    loadCurrentModule();
});

// 初始化租户选择器
async function initTenantSelector() {
    try {
        const tenants = await listTenants();
        const selector = document.getElementById('tenantSelector');
        if (!selector) return;

        selector.innerHTML = tenants.map(tenant => `
            <option value="${tenant.realm}" ${tenant.realm === currentRealm ? 'selected' : ''}>
                ${tenant.displayName || tenant.realm}
            </option>
        `).join('');

        selector.addEventListener('change', (e) => {
            currentRealm = e.target.value;
            loadCurrentModule();
        });
    } catch (error) {
        showErrorToast('加载租户列表失败: ' + error.message);
    }
}

// 设置事件监听器
function setupEventListeners() {
    // 侧边栏导航
    const navItems = document.querySelectorAll('.sidebar nav ul li');
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            currentModule = item.dataset.module;
            loadCurrentModule();
        });
    });
}

// 加载当前模块数据
function loadCurrentModule() {
    if (!currentRealm) {
        showErrorToast('请先选择租户');
        return;
    }

    const contentPanel = document.getElementById('contentPanel');
    if (!contentPanel) return;

    switch (currentModule) {
        case 'user':
            loadUserModule();
            break;
        case 'group':
            loadGroupModule();
            break;
        case 'role':
            loadRoleModule();
            break;
        case 'idp':
            loadIdpModule();
            break;
    }
}

// ==================== User模块 ====================

async function loadUserModule() {
    const contentPanel = document.getElementById('contentPanel');
    contentPanel.innerHTML = `
        <div class="page-header">
            <h1>用户管理</h1>
        </div>
        <div id="userListContainer">
            <div class="loading">加载中</div>
        </div>
    `;

    try {
        const users = await listUsers(currentRealm);
        renderUserList(users);
    } catch (error) {
        showErrorToast('加载用户列表失败: ' + error.message);
        document.getElementById('userListContainer').innerHTML = `
            <div class="empty-state">
                <p>加载失败: ${error.message}</p>
            </div>
        `;
    }
}

function renderUserList(users) {
    const container = document.getElementById('userListContainer');
    if (!container) return;

    if (users.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>暂无用户</p>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>用户名</th>
                    <th>邮箱</th>
                    <th>姓名</th>
                    <th>启用状态</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>
                ${users.map(user => `
                    <tr>
                        <td>${user.username || '-'}</td>
                        <td>${user.email || '-'}</td>
                        <td>${user.firstName || ''} ${user.lastName || ''}</td>
                        <td>${user.enabled ? '启用' : '禁用'}</td>
                        <td>
                            <button class="btn btn-link" onclick="viewUser('${user.id}')">查看</button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

async function viewUser(userId) {
    try {
        const userDetails = await getUserDetails(currentRealm, userId);
        const content = `
            <ul class="detail-list">
                <li><strong>用户名:</strong> ${userDetails.username || '-'}</li>
                <li><strong>邮箱:</strong> ${userDetails.email || '-'}</li>
                <li><strong>姓名:</strong> ${userDetails.firstName || ''} ${userDetails.lastName || ''}</li>
                <li><strong>启用状态:</strong> ${userDetails.enabled ? '启用' : '禁用'}</li>
                <li><strong>所属组:</strong> ${userDetails.groups && userDetails.groups.length > 0 ? userDetails.groups.map(g => g.name).join(', ') : '无'}</li>
                <li><strong>所属角色:</strong> ${userDetails.roles && userDetails.roles.length > 0 ? userDetails.roles.join(', ') : '无'}</li>
            </ul>
        `;
        showModal('用户详情', content);
    } catch (error) {
        showErrorToast('获取用户详情失败: ' + error.message);
    }
}

// ==================== Group模块 ====================

async function loadGroupModule() {
    const contentPanel = document.getElementById('contentPanel');
    contentPanel.innerHTML = `
        <div class="page-header">
            <h1>组管理</h1>
        </div>
        <div id="groupListContainer">
            <div class="loading">加载中</div>
        </div>
        <div style="margin-top: 20px;">
            <button class="btn btn-primary" onclick="showCreateGroupModal()">添加组</button>
        </div>
    `;

    try {
        const groups = await listGroups(currentRealm);
        renderGroupList(groups);
    } catch (error) {
        showErrorToast('加载组列表失败: ' + error.message);
        document.getElementById('groupListContainer').innerHTML = `
            <div class="empty-state">
                <p>加载失败: ${error.message}</p>
            </div>
        `;
    }
}

function renderGroupList(groups) {
    const container = document.getElementById('groupListContainer');
    if (!container) return;

    if (groups.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>暂无组</p>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th><input type="checkbox" id="selectAllGroups" onchange="toggleSelectAllGroups()"></th>
                    <th>名称</th>
                    <th>路径</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>
                ${groups.map(group => `
                    <tr data-group-id="${group.id}">
                        <td><input type="checkbox" class="group-checkbox" value="${group.id}"></td>
                        <td>${group.name || '-'}</td>
                        <td>${group.path || '-'}</td>
                        <td>
                            <button class="btn btn-link" onclick="viewGroup('${group.id}')">查看</button>
                            <button class="btn btn-link" onclick="showEditGroupModal('${group.id}')">编辑</button>
                            <button class="btn btn-link" onclick="deleteGroupHandler('${group.id}')">删除</button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function toggleSelectAllGroups() {
    const selectAll = document.getElementById('selectAllGroups');
    const checkboxes = document.querySelectorAll('.group-checkbox');
    checkboxes.forEach(cb => cb.checked = selectAll.checked);
}

async function viewGroup(groupId) {
    try {
        const groupDetail = await getGroupDetail(currentRealm, groupId);
        if (!groupDetail) {
            showErrorToast('未找到该组');
            return;
        }

        const membersHtml = groupDetail.members && groupDetail.members.length > 0
            ? groupDetail.members.map(m => `<li>${m.username} (${m.id})</li>`).join('')
            : '<li>无成员</li>';

        const rolesHtml = groupDetail.roles && groupDetail.roles.length > 0
            ? groupDetail.roles.map(r => `<li>${r.name}</li>`).join('')
            : '<li>无角色</li>';

        const content = `
            <ul class="detail-list">
                <li><strong>名称:</strong> ${groupDetail.name || '-'}</li>
                <li><strong>成员:</strong></li>
                <ul>${membersHtml}</ul>
                <li><strong>角色:</strong></li>
                <ul>${rolesHtml}</ul>
            </ul>
        `;
        showModal('组详情', content);
    } catch (error) {
        showErrorToast('获取组详情失败: ' + error.message);
    }
}

async function showEditGroupModal(groupId) {
    try {
        const groups = await listGroups(currentRealm);
        const group = groups.find(g => g.id === groupId);
        if (!group) {
            showErrorToast('未找到该组');
            return;
        }

        const content = `
            <form id="editGroupForm">
                <div class="form-group">
                    <label for="groupName">组名称 *</label>
                    <input type="text" id="groupName" name="name" value="${group.name || ''}" required>
                </div>
                <div class="form-group">
                    <label for="groupPath">路径</label>
                    <input type="text" id="groupPath" name="path" value="${group.path || ''}">
                </div>
            </form>
        `;

        showModal('编辑组', content, async () => {
            const form = document.getElementById('editGroupForm');
            const formData = new FormData(form);
            const groupData = {
                name: formData.get('name'),
                path: formData.get('path'),
            };

            if (!groupData.name) {
                showErrorToast('请输入组名称');
                return;
            }

            try {
                await updateGroup(currentRealm, groupId, groupData);
                showSuccessToast('组更新成功');
                closeAllModals();
                loadGroupModule();
            } catch (error) {
                showErrorToast('更新组失败: ' + error.message);
            }
        });
    } catch (error) {
        showErrorToast('加载组信息失败: ' + error.message);
    }
}

function showCreateGroupModal() {
    const content = `
        <form id="createGroupForm">
            <div class="form-group">
                <label for="groupName">组名称 *</label>
                <input type="text" id="groupName" name="name" required placeholder="请输入组名称">
            </div>
            <div class="form-group">
                <label for="groupPath">路径</label>
                <input type="text" id="groupPath" name="path" placeholder="请输入路径">
            </div>
        </form>
    `;

    showModal('创建组', content, async () => {
        const form = document.getElementById('createGroupForm');
        const formData = new FormData(form);
        const groupData = {
            name: formData.get('name'),
            path: formData.get('path'),
        };

        if (!groupData.name) {
            showErrorToast('请输入组名称');
            return;
        }

        try {
            await createGroup(currentRealm, groupData);
            showSuccessToast('组创建成功');
            closeAllModals();
            loadGroupModule();
        } catch (error) {
            showErrorToast('创建组失败: ' + error.message);
        }
    });
}

function deleteGroupHandler(groupId) {
    showConfirmDialog('确定要删除该组吗？', async () => {
        try {
            await deleteGroup(currentRealm, groupId);
            showSuccessToast('组删除成功');
            loadGroupModule();
        } catch (error) {
            showErrorToast('删除组失败: ' + error.message);
        }
    });
}

// ==================== Role模块 ====================

async function loadRoleModule() {
    const contentPanel = document.getElementById('contentPanel');
    contentPanel.innerHTML = `
        <div class="page-header">
            <h1>角色管理</h1>
        </div>
        <div id="roleListContainer">
            <div class="loading">加载中</div>
        </div>
        <div style="margin-top: 20px;">
            <button class="btn btn-primary" onclick="showCreateRoleModal()">添加角色</button>
        </div>
    `;

    try {
        const roles = await listRoles(currentRealm);
        renderRoleList(roles);
    } catch (error) {
        showErrorToast('加载角色列表失败: ' + error.message);
        document.getElementById('roleListContainer').innerHTML = `
            <div class="empty-state">
                <p>加载失败: ${error.message}</p>
            </div>
        `;
    }
}

function renderRoleList(roles) {
    const container = document.getElementById('roleListContainer');
    if (!container) return;

    if (roles.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>暂无角色</p>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th><input type="checkbox" id="selectAllRoles" onchange="toggleSelectAllRoles()"></th>
                    <th>名称</th>
                    <th>描述</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>
                ${roles.map(role => `
                    <tr data-role-name="${role.name}">
                        <td><input type="checkbox" class="role-checkbox" value="${role.name}"></td>
                        <td>${role.name || '-'}</td>
                        <td>${role.description || '-'}</td>
                        <td>
                            <button class="btn btn-link" onclick="viewRole('${role.name}')">查看</button>
                            <button class="btn btn-link" onclick="showEditRoleModal('${role.name}')">编辑</button>
                            <button class="btn btn-link" onclick="deleteRoleHandler('${role.name}')">删除</button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function toggleSelectAllRoles() {
    const selectAll = document.getElementById('selectAllRoles');
    const checkboxes = document.querySelectorAll('.role-checkbox');
    checkboxes.forEach(cb => cb.checked = selectAll.checked);
}

async function viewRole(roleName) {
    try {
        const role = await getRole(currentRealm, roleName);
        const content = `
            <ul class="detail-list">
                <li><strong>名称:</strong> ${role.name || '-'}</li>
                <li><strong>描述:</strong> ${role.description || '-'}</li>
            </ul>
        `;
        showModal('角色详情', content);
    } catch (error) {
        showErrorToast('获取角色详情失败: ' + error.message);
    }
}

async function showEditRoleModal(roleName) {
    try {
        const role = await getRole(currentRealm, roleName);
        const content = `
            <form id="editRoleForm">
                <div class="form-group">
                    <label for="roleName">角色名称 *</label>
                    <input type="text" id="roleName" name="name" value="${role.name || ''}" required>
                </div>
                <div class="form-group">
                    <label for="roleDescription">描述</label>
                    <textarea id="roleDescription" name="description">${role.description || ''}</textarea>
                </div>
            </form>
        `;

        showModal('编辑角色', content, async () => {
            const form = document.getElementById('editRoleForm');
            const formData = new FormData(form);
            const roleData = {
                name: formData.get('name'),
                description: formData.get('description'),
            };

            if (!roleData.name) {
                showErrorToast('请输入角色名称');
                return;
            }

            try {
                await updateRole(currentRealm, roleName, roleData);
                showSuccessToast('角色更新成功');
                closeAllModals();
                loadRoleModule();
            } catch (error) {
                showErrorToast('更新角色失败: ' + error.message);
            }
        });
    } catch (error) {
        showErrorToast('加载角色信息失败: ' + error.message);
    }
}

function showCreateRoleModal() {
    const content = `
        <form id="createRoleForm">
            <div class="form-group">
                <label for="roleName">角色名称 *</label>
                <input type="text" id="roleName" name="name" required placeholder="请输入角色名称">
            </div>
            <div class="form-group">
                <label for="roleDescription">描述</label>
                <textarea id="roleDescription" name="description" placeholder="请输入描述"></textarea>
            </div>
        </form>
    `;

    showModal('创建角色', content, async () => {
        const form = document.getElementById('createRoleForm');
        const formData = new FormData(form);
        const roleData = {
            name: formData.get('name'),
            description: formData.get('description'),
        };

        if (!roleData.name) {
            showErrorToast('请输入角色名称');
            return;
        }

        try {
            await createRole(currentRealm, roleData);
            showSuccessToast('角色创建成功');
            closeAllModals();
            loadRoleModule();
        } catch (error) {
            showErrorToast('创建角色失败: ' + error.message);
        }
    });
}

function deleteRoleHandler(roleName) {
    showConfirmDialog(`确定要删除角色 "${roleName}" 吗？`, async () => {
        try {
            await deleteRole(currentRealm, roleName);
            showSuccessToast('角色删除成功');
            loadRoleModule();
        } catch (error) {
            showErrorToast('删除角色失败: ' + error.message);
        }
    });
}

// ==================== IDP模块 ====================

async function loadIdpModule() {
    const contentPanel = document.getElementById('contentPanel');
    contentPanel.innerHTML = `
        <div class="page-header">
            <h1>ID Provider管理</h1>
        </div>
        <div id="idpListContainer">
            <div class="loading">加载中</div>
        </div>
        <div style="margin-top: 20px;">
            <button class="btn btn-primary" onclick="showCreateIdpModal()">添加IDP</button>
        </div>
    `;

    try {
        const idps = await listIdpInstances(currentRealm);
        renderIdpList(idps);
    } catch (error) {
        showErrorToast('加载IDP列表失败: ' + error.message);
        document.getElementById('idpListContainer').innerHTML = `
            <div class="empty-state">
                <p>加载失败: ${error.message}</p>
            </div>
        `;
    }
}

function renderIdpList(idps) {
    const container = document.getElementById('idpListContainer');
    if (!container) return;

    if (idps.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>暂无IDP实例</p>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>别名</th>
                    <th>显示名称</th>
                    <th>启用状态</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>
                ${idps.map(idp => `
                    <tr>
                        <td>${idp.alias || '-'}</td>
                        <td>${idp.displayName || '-'}</td>
                        <td>${idp.enabled ? '启用' : '禁用'}</td>
                        <td>
                            <button class="btn btn-link" onclick="showEditIdpModal('${idp.alias}')">编辑</button>
                            <button class="btn btn-link" onclick="deleteIdpHandler('${idp.alias}')">删除</button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function showCreateIdpModal() {
    const content = `
        <form id="createIdpForm">
            <div class="form-group">
                <label for="samlFile">导入SAML Metadata（可选）</label>
                <div class="file-upload" onclick="document.getElementById('samlFile').click()">
                    <input type="file" id="samlFile" name="file" accept=".xml">
                    <span class="file-upload-label" id="fileLabel">点击选择文件</span>
                </div>
                <button type="button" class="btn btn-secondary" id="importBtn" style="margin-top: 10px;">导入并解析</button>
            </div>
            <hr style="margin: 20px 0;">
            <div class="form-group">
                <label for="idpAlias">别名 *</label>
                <input type="text" id="idpAlias" name="alias" required placeholder="请输入IDP别名">
            </div>
            <div class="form-group">
                <label for="idpDisplayName">显示名称</label>
                <input type="text" id="idpDisplayName" name="displayName" placeholder="请输入显示名称">
            </div>
            <div class="form-group">
                <label for="idpEnabled">启用状态</label>
                <select id="idpEnabled" name="enabled">
                    <option value="true">启用</option>
                    <option value="false">禁用</option>
                </select>
            </div>
            <div class="form-group">
                <label for="idpEntityId">Entity ID</label>
                <input type="text" id="idpEntityId" name="entityId" placeholder="请输入Entity ID">
            </div>
            <div class="form-group">
                <label for="idpSsoUrl">SSO URL</label>
                <input type="text" id="idpSsoUrl" name="ssoUrl" placeholder="请输入SSO URL">
            </div>
        </form>
    `;

    showModal('创建IDP实例', content, async () => {
        const form = document.getElementById('createIdpForm');
        const formData = new FormData(form);
        const idpData = {
            alias: formData.get('alias'),
            displayName: formData.get('displayName'),
            enabled: formData.get('enabled') === 'true',
            config: {
                entityId: formData.get('entityId'),
                singleSignOnServiceUrl: formData.get('ssoUrl'),
            },
        };

        if (!idpData.alias) {
            showErrorToast('请输入IDP别名');
            return;
        }

        try {
            await createIdpInstance(currentRealm, idpData);
            showSuccessToast('IDP实例创建成功');
            closeAllModals();
            loadIdpModule();
        } catch (error) {
            showErrorToast('创建IDP实例失败: ' + error.message);
        }
    });

    // 文件选择后更新显示
    document.getElementById('samlFile').addEventListener('change', (e) => {
        const fileLabel = document.getElementById('fileLabel');
        if (e.target.files.length > 0) {
            fileLabel.textContent = e.target.files[0].name;
        }
    });

    // 导入并解析SAML Metadata
    document.getElementById('importBtn').addEventListener('click', async () => {
        const fileInput = document.getElementById('samlFile');
        if (!fileInput.files || fileInput.files.length === 0) {
            showErrorToast('请先选择SAML Metadata文件');
            return;
        }

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        try {
            const result = await importSamlMetadata(currentRealm, formData);
            showSuccessToast('SAML Metadata解析成功');
            
            // 回填解析结果到表单
            if (result && result.config) {
                if (result.config.entityId) {
                    document.getElementById('idpEntityId').value = result.config.entityId;
                }
                if (result.config.singleSignOnServiceUrl) {
                    document.getElementById('idpSsoUrl').value = result.config.singleSignOnServiceUrl;
                }
                if (result.alias) {
                    document.getElementById('idpAlias').value = result.alias;
                }
                if (result.displayName) {
                    document.getElementById('idpDisplayName').value = result.displayName;
                }
            }
        } catch (error) {
            showErrorToast('解析SAML Metadata失败: ' + error.message);
        }
    });
}

async function showEditIdpModal(alias) {
    try {
        const idps = await listIdpInstances(currentRealm);
        const idp = idps.find(i => i.alias === alias);
        if (!idp) {
            showErrorToast('未找到该IDP实例');
            return;
        }

        const content = `
            <form id="editIdpForm">
                <div class="form-group">
                    <label for="samlFile">导入SAML Metadata（可选）</label>
                    <div class="file-upload" onclick="document.getElementById('samlFile').click()">
                        <input type="file" id="samlFile" name="file" accept=".xml">
                        <span class="file-upload-label" id="fileLabel">点击选择文件</span>
                    </div>
                    <button type="button" class="btn btn-secondary" id="importBtn" style="margin-top: 10px;">导入并解析</button>
                </div>
                <hr style="margin: 20px 0;">
                <div class="form-group">
                    <label for="idpAlias">别名 *</label>
                    <input type="text" id="idpAlias" name="alias" value="${idp.alias || ''}" required>
                </div>
                <div class="form-group">
                    <label for="idpDisplayName">显示名称</label>
                    <input type="text" id="idpDisplayName" name="displayName" value="${idp.displayName || ''}">
                </div>
                <div class="form-group">
                    <label for="idpEnabled">启用状态</label>
                    <select id="idpEnabled" name="enabled">
                        <option value="true" ${idp.enabled ? 'selected' : ''}>启用</option>
                        <option value="false" ${!idp.enabled ? 'selected' : ''}>禁用</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="idpEntityId">Entity ID</label>
                    <input type="text" id="idpEntityId" name="entityId" value="${idp.config?.entityId || ''}">
                </div>
                <div class="form-group">
                    <label for="idpSsoUrl">SSO URL</label>
                    <input type="text" id="idpSsoUrl" name="ssoUrl" value="${idp.config?.singleSignOnServiceUrl || ''}">
                </div>
            </form>
        `;

        showModal('编辑IDP实例', content, async () => {
            const form = document.getElementById('editIdpForm');
            const formData = new FormData(form);
            const idpData = {
                alias: formData.get('alias'),
                displayName: formData.get('displayName'),
                enabled: formData.get('enabled') === 'true',
                config: {
                    entityId: formData.get('entityId'),
                    singleSignOnServiceUrl: formData.get('ssoUrl'),
                },
            };

            if (!idpData.alias) {
                showErrorToast('请输入IDP别名');
                return;
            }

            try {
                await updateIdpInstance(currentRealm, idpData);
                showSuccessToast('IDP实例更新成功');
                closeAllModals();
                loadIdpModule();
            } catch (error) {
                showErrorToast('更新IDP实例失败: ' + error.message);
            }
        });

        // 文件选择后更新显示
        document.getElementById('samlFile').addEventListener('change', (e) => {
            const fileLabel = document.getElementById('fileLabel');
            if (e.target.files.length > 0) {
                fileLabel.textContent = e.target.files[0].name;
            }
        });

        // 导入并解析SAML Metadata
        document.getElementById('importBtn').addEventListener('click', async () => {
            const fileInput = document.getElementById('samlFile');
            if (!fileInput.files || fileInput.files.length === 0) {
                showErrorToast('请先选择SAML Metadata文件');
                return;
            }

            const formData = new FormData();
            formData.append('file', fileInput.files[0]);

            try {
                const result = await importSamlMetadata(currentRealm, formData);
                showSuccessToast('SAML Metadata解析成功');
                
                // 回填解析结果到表单
                if (result && result.config) {
                    if (result.config.entityId) {
                        document.getElementById('idpEntityId').value = result.config.entityId;
                    }
                    if (result.config.singleSignOnServiceUrl) {
                        document.getElementById('idpSsoUrl').value = result.config.singleSignOnServiceUrl;
                    }
                    if (result.alias) {
                        document.getElementById('idpAlias').value = result.alias;
                    }
                    if (result.displayName) {
                        document.getElementById('idpDisplayName').value = result.displayName;
                    }
                }
            } catch (error) {
                showErrorToast('解析SAML Metadata失败: ' + error.message);
            }
        });
    } catch (error) {
        showErrorToast('加载IDP信息失败: ' + error.message);
    }
}

function deleteIdpHandler(alias) {
    showConfirmDialog(`确定要删除IDP实例 "${alias}" 吗？`, async () => {
        try {
            await deleteIdpInstance(currentRealm, alias);
            showSuccessToast('IDP实例删除成功');
            loadIdpModule();
        } catch (error) {
            showErrorToast('删除IDP实例失败: ' + error.message);
        }
    });
}
