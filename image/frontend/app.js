const { createApp, ref, reactive, computed, onMounted } = Vue;

const API_BASE = '/api';

const app = createApp({
    setup() {
        // 状态管理
        const STORAGE_ACTIVE_MENU_KEY = 'activeMenu';
        const isLoggedIn = ref(false);
        const username = ref('');
        const token = ref('');
        const loading = ref(false);
        const loginLoading = ref(false);
        const savedMenu = typeof localStorage !== 'undefined' ? localStorage.getItem(STORAGE_ACTIVE_MENU_KEY) : null;
        const activeMenu = ref(savedMenu || 'users');
        
        // 数据
        const users = ref([]);
        const clusterRoles = ref([]);
        const namespaces = ref([]);
        
        // 登录表单
        const loginForm = reactive({
            username: '',
            password: ''
        });
        
        // 用户对话框
        const userDialogVisible = ref(false);
        const userDialogTitle = ref('创建用户');
        const isEditMode = ref(false);
        const userForm = reactive({
            name: '',
            namespace: 'kube-system',
            roles: []
        });
        
        // 角色对话框
        const roleDialogVisible = ref(false);
        const roleDialogTitle = ref('创建角色');
        const isEditRoleMode = ref(false);
        const roleForm = reactive({
            name: '',
            description: '',
            rules: [],
            rulesYaml: ''
        });
        
        // 角色查看对话框
        const roleViewDialogVisible = ref(false);
        const viewingRole = ref({});
        
        // Kubeconfig 预览对话框
        const kubeconfigPreviewVisible = ref(false);
        const kubeconfigContent = ref('');
        const currentDownloadUser = ref(null);
        
        // 计算属性
        const pageTitle = computed(() => {
            return activeMenu.value === 'users' ? '用户管理' : '角色管理';
        });
        
        // API 请求辅助函数
        const apiRequest = async (url, options = {}) => {
            const headers = {
                'Content-Type': 'application/json',
                ...options.headers
            };
            
            if (token.value) {
                headers['Authorization'] = `Bearer ${token.value}`;
            }
            
            const response = await fetch(url, {
                ...options,
                headers
            });
            
            if (!response.ok) {
                if (response.status === 401) {
                    handleLogout();
                    throw new Error('认证失败，请重新登录');
                }
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || '请求失败');
            }
            
            return response.json();
        };
        
        // 登录
        const handleLogin = async () => {
            if (!loginForm.username || !loginForm.password) {
                ElementPlus.ElMessage.warning('请输入用户名和密码');
                return;
            }
            
            loginLoading.value = true;
            try {
                const data = await apiRequest(`${API_BASE}/login`, {
                    method: 'POST',
                    body: JSON.stringify(loginForm)
                });
                
                token.value = data.access_token;
                username.value = loginForm.username;
                isLoggedIn.value = true;
                localStorage.setItem('token', token.value);
                localStorage.setItem('username', username.value);
                localStorage.setItem(STORAGE_ACTIVE_MENU_KEY, activeMenu.value);
                
                ElementPlus.ElMessage.success('登录成功');
                await Promise.all([loadUsers(), loadClusterRoles(), loadNamespaces()]);
            } catch (error) {
                ElementPlus.ElMessage.error(error.message || '登录失败');
            } finally {
                loginLoading.value = false;
            }
        };
        
        // 登出
        const handleLogout = () => {
            isLoggedIn.value = false;
            token.value = '';
            username.value = '';
            localStorage.removeItem('token');
            localStorage.removeItem('username');
            localStorage.removeItem(STORAGE_ACTIVE_MENU_KEY);
            ElementPlus.ElMessage.success('已退出登录');
        };
        
        // 菜单选择
        const handleMenuSelect = async (index) => {
            activeMenu.value = index;
            localStorage.setItem(STORAGE_ACTIVE_MENU_KEY, index);
            if (index === 'users') {
                await loadUsers();
            } else if (index === 'roles') {
                await loadClusterRoles();
            }
        };
        
        // 命令处理
        const handleCommand = (command) => {
            if (command === 'logout') {
                handleLogout();
            }
        };
        
        // ==================== 用户管理 ====================
        
        const loadUsers = async () => {
            loading.value = true;
            try {
                const data = await apiRequest(`${API_BASE}/lensusers`);
                users.value = data.data || [];
                console.log('用户列表数据:', users.value);
                console.log('第一个用户:', users.value[0]);
            } catch (error) {
                ElementPlus.ElMessage.error(error.message || '加载用户列表失败');
                users.value = [];
            } finally {
                loading.value = false;
            }
        };
        
        const showCreateUserDialog = async () => {
            isEditMode.value = false;
            userDialogTitle.value = '创建用户';
            userForm.name = '';
            userForm.namespace = 'kube-system';
            userForm.roles = [{ name: 'admin', namespace: 'kube-system' }];
            userDialogVisible.value = true;
            
            // 确保加载了角色和命名空间
            if (clusterRoles.value.length === 0) {
                await loadClusterRoles();
            }
            if (namespaces.value.length === 0) {
                await loadNamespaces();
            }
        };
        
        const editUser = async (user) => {
            isEditMode.value = true;
            userDialogTitle.value = '编辑用户';
            userForm.name = user.metadata.name;
            userForm.namespace = user.metadata.namespace;
            userForm.roles = JSON.parse(JSON.stringify(user.spec.roles));
            userDialogVisible.value = true;
            
            if (clusterRoles.value.length === 0) {
                await loadClusterRoles();
            }
            if (namespaces.value.length === 0) {
                await loadNamespaces();
            }
        };
        
        const saveUser = async () => {
            if (!userForm.name) {
                ElementPlus.ElMessage.warning('请输入用户名');
                return;
            }
            if (userForm.roles.length === 0) {
                ElementPlus.ElMessage.warning('请至少添加一个权限角色');
                return;
            }
            const invalidRole = userForm.roles.find(role => !role.name || !role.namespace);
            if (invalidRole) {
                ElementPlus.ElMessage.warning('请确保每个权限条目的角色与命名空间均已填写');
                return;
            }
            
            loading.value = true;
            try {
                if (isEditMode.value) {
                    await apiRequest(`${API_BASE}/lensusers/${userForm.name}?namespace=${userForm.namespace}`, {
                        method: 'PUT',
                        body: JSON.stringify({ roles: userForm.roles })
                    });
                    ElementPlus.ElMessage.success('用户更新成功');
                } else {
                    await apiRequest(`${API_BASE}/lensusers`, {
                        method: 'POST',
                        body: JSON.stringify(userForm)
                    });
                    ElementPlus.ElMessage.success('用户创建成功');
                }
                
                userDialogVisible.value = false;
                await loadUsers();
            } catch (error) {
                ElementPlus.ElMessage.error(error.message || '保存用户失败');
            } finally {
                loading.value = false;
            }
        };
        
        const deleteUser = async (user) => {
            try {
                await ElementPlus.ElMessageBox.confirm(
                    `确定要删除用户 ${user.metadata.name} 吗？此操作不可撤销！`,
                    '警告',
                    {
                        confirmButtonText: '确定',
                        cancelButtonText: '取消',
                        type: 'warning'
                    }
                );
                
                loading.value = true;
                await apiRequest(`${API_BASE}/lensusers/${user.metadata.name}?namespace=${user.metadata.namespace}`, {
                    method: 'DELETE'
                });
                ElementPlus.ElMessage.success('用户删除成功');
                // 立即从列表中移除
                const index = users.value.findIndex(u => 
                    u.metadata.name === user.metadata.name && 
                    u.metadata.namespace === user.metadata.namespace
                );
                if (index > -1) {
                    users.value.splice(index, 1);
                }
                // 重新加载确保同步
                await loadUsers();
            } catch (error) {
                if (error !== 'cancel') {
                    ElementPlus.ElMessage.error(error.message || '删除用户失败');
                }
            } finally {
                loading.value = false;
            }
        };
        
        const previewKubeconfig = async (user) => {
            try {
                const data = await apiRequest(`${API_BASE}/lensusers/${user.metadata.name}/kubeconfig?namespace=${user.metadata.namespace}`);
                const config = data.data;
                
                kubeconfigContent.value = jsyaml.dump(config, { indent: 2 });
                currentDownloadUser.value = user;
                kubeconfigPreviewVisible.value = true;
            } catch (error) {
                ElementPlus.ElMessage.error(error.message || '获取 Kubeconfig 失败');
            }
        };
        
        const downloadKubeconfig = () => {
            if (!kubeconfigContent.value) {
                ElementPlus.ElMessage.error('配置内容为空');
                return;
            }
            
            // 从 kubeconfig 内容中解析 current-context 作为文件名
            let filename = 'kubeconfig.yaml';
            try {
                const config = jsyaml.load(kubeconfigContent.value);
                if (config && config['current-context']) {
                    filename = `${config['current-context']}.yaml`;
                }
            } catch (error) {
                console.warn('解析 kubeconfig 失败，使用默认文件名', error);
            }
            
            const blob = new Blob([kubeconfigContent.value], { type: 'application/x-yaml' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
            
            ElementPlus.ElMessage.success(`配置文件已下载为: ${filename}`);
        };
        
        const addRole = () => {
            const defaultNamespace = userForm.namespace || (namespaces.value && namespaces.value[0]) || '';
            userForm.roles.push({ name: '', namespace: defaultNamespace });
        };
        
        const removeRole = (index) => {
            userForm.roles.splice(index, 1);
        };
        
        // ==================== 角色管理 ====================
        
        const loadClusterRoles = async () => {
            loading.value = true;
            try {
                const data = await apiRequest(`${API_BASE}/clusterroles`);
                clusterRoles.value = data.data || [];
                console.log('角色列表数据:', clusterRoles.value);
                console.log('第一个角色:', clusterRoles.value[0]);
            } catch (error) {
                console.error('加载角色列表失败:', error);
                ElementPlus.ElMessage.error(error.message || '加载角色列表失败');
                clusterRoles.value = [];
            } finally {
                loading.value = false;
            }
        };
        
        const showCreateRoleDialog = () => {
            isEditRoleMode.value = false;
            roleDialogTitle.value = '创建角色';
            roleForm.name = '';
            roleForm.description = '';
            roleForm.rules = [];
            roleForm.rulesYaml = `- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]`;
            roleDialogVisible.value = true;
        };
        
        const viewRole = (role) => {
            viewingRole.value = role;
            roleViewDialogVisible.value = true;
        };
        
        const editRole = (role) => {
            isEditRoleMode.value = true;
            roleDialogTitle.value = '编辑角色';
            roleForm.name = role.name;
            roleForm.description = role.labels.description || '';
            roleForm.rules = JSON.parse(JSON.stringify(role.rules));
            // 将 rules 转换为 YAML
            roleForm.rulesYaml = jsyaml.dump(role.rules, { indent: 2 });
            roleDialogVisible.value = true;
        };
        
        const saveRole = async () => {
            if (!roleForm.name) {
                ElementPlus.ElMessage.warning('请输入角色名称');
                return;
            }
            
            // 从 YAML 解析 rules
            try {
                const parsedRules = jsyaml.load(roleForm.rulesYaml);
                if (!Array.isArray(parsedRules)) {
                    ElementPlus.ElMessage.warning('权限规则必须是数组格式');
                    return;
                }
                roleForm.rules = parsedRules;
            } catch (error) {
                ElementPlus.ElMessage.error('YAML 格式错误: ' + error.message);
                return;
            }
            
            if (roleForm.rules.length === 0) {
                ElementPlus.ElMessage.warning('请至少添加一个权限规则');
                return;
            }
            
            loading.value = true;
            try {
                if (isEditRoleMode.value) {
                    await apiRequest(`${API_BASE}/clusterroles/${roleForm.name}`, {
                        method: 'PUT',
                        body: JSON.stringify({
                            description: roleForm.description,
                            rules: roleForm.rules
                        })
                    });
                    ElementPlus.ElMessage.success('角色更新成功');
                } else {
                    await apiRequest(`${API_BASE}/clusterroles`, {
                        method: 'POST',
                        body: JSON.stringify(roleForm)
                    });
                    ElementPlus.ElMessage.success('角色创建成功');
                }
                
                roleDialogVisible.value = false;
                await loadClusterRoles();
            } catch (error) {
                ElementPlus.ElMessage.error(error.message || '保存角色失败');
            } finally {
                loading.value = false;
            }
        };
        
        const deleteRole = async (role) => {
            try {
                await ElementPlus.ElMessageBox.confirm(
                    `确定要删除角色 ${role.name} 吗？此操作不可撤销！`,
                    '警告',
                    {
                        confirmButtonText: '确定',
                        cancelButtonText: '取消',
                        type: 'warning'
                    }
                );
                
                loading.value = true;
                await apiRequest(`${API_BASE}/clusterroles/${role.name}`, {
                    method: 'DELETE'
                });
                ElementPlus.ElMessage.success('角色删除成功');
                await loadClusterRoles();
            } catch (error) {
                if (error !== 'cancel') {
                    ElementPlus.ElMessage.error(error.message || '删除角色失败');
                }
            } finally {
                loading.value = false;
            }
        };
        
        const addRule = () => {
            roleForm.rules.push({
                apiGroups: [],
                resources: [],
                verbs: [],
                resourceNames: []
            });
        };
        
        const removeRule = (index) => {
            roleForm.rules.splice(index, 1);
        };
        
        // ==================== 其他 ====================
        
        const loadNamespaces = async () => {
            try {
                const data = await apiRequest(`${API_BASE}/namespaces`);
                namespaces.value = data.data;
            } catch (error) {
                ElementPlus.ElMessage.error(error.message || '加载命名空间失败');
            }
        };
        
        // 初始化
        onMounted(() => {
            const savedToken = localStorage.getItem('token');
            const savedUsername = localStorage.getItem('username');
            
            if (savedToken && savedUsername) {
                token.value = savedToken;
                username.value = savedUsername;
                isLoggedIn.value = true;
                
                const initialLoads = [loadNamespaces()];
                // 根据当前菜单加载对应数据，其余懒加载
                if (activeMenu.value === 'roles') {
                    initialLoads.push(loadClusterRoles());
                } else {
                    initialLoads.push(loadUsers());
                }
                Promise.all(initialLoads);
            }
        });
        
        return {
            isLoggedIn,
            username,
            token,
            loading,
            loginLoading,
            activeMenu,
            users,
            clusterRoles,
            namespaces,
            loginForm,
            userDialogVisible,
            userDialogTitle,
            isEditMode,
            userForm,
            roleDialogVisible,
            roleDialogTitle,
            isEditRoleMode,
            roleForm,
            roleViewDialogVisible,
            viewingRole,
            kubeconfigPreviewVisible,
            kubeconfigContent,
            currentDownloadUser,
            pageTitle,
            handleLogin,
            handleLogout,
            handleMenuSelect,
            handleCommand,
            showCreateUserDialog,
            editUser,
            saveUser,
            deleteUser,
            previewKubeconfig,
            downloadKubeconfig,
            addRole,
            removeRole,
            showCreateRoleDialog,
            viewRole,
            editRole,
            saveRole,
            deleteRole,
            addRule,
            removeRule
        };
    }
});

// 注册 Element Plus 图标
if (typeof ElementPlusIconsVue !== 'undefined') {
    for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
        app.component(key, component);
    }
}

app.use(ElementPlus);
app.mount('#app');

