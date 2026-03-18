var ArrayList = Java.type("java.util.ArrayList");
var HashMap = Java.type("java.util.HashMap");

// 1. 设置 Realm ID
token.setOtherClaims("realm_id", realm.getId());

// 2. 处理 Roles 结构
var rolesList = new ArrayList();
var builtInRoles = ["offline_access", "uma_authorization"];

// 获取 Realm Roles 流
var roleModelsStream = user.getRealmRoleMappingsStream();
var roleModelsArray = roleModelsStream.toArray();

for (var i = 0; i < roleModelsArray.length; i++) {
    var role = roleModelsArray[i];
    var roleName = role.getName();
    
    // 过滤内置角色
    if (builtInRoles.indexOf(roleName) === -1) {
        var roleObj = new HashMap();
        roleObj.put("id", role.getId());
        roleObj.put("name", roleName);
        rolesList.add(roleObj);
    }
}

// 注入重构后的 roles 字段
token.setOtherClaims("roles", rolesList);

// 3. (可选) 如果你想干掉原有的 realm_access 结构以防混淆
// 注意：这取决于 Keycloak 内部是否允许覆盖，通常直接注入新字段即可
// 注意：如果 Keycloak 锁定了这个 Key，这行代码可能无效，但不会导致崩溃
var fakeRealmAccess = new HashMap();
fakeRealmAccess.put("info", "overridden_by_script"); 
// 或者直接设为 null 尝试抹除，但建议给个对象，否则可能被 Keycloak 补回默认值
token.setOtherClaims("realm_access", null); 

// 3. 尝试抹除 resource_access (客户端级别角色)
token.setOtherClaims("resource_access", null);

//打包命令： jar cvf data-agent-mapper.jar .\data-agent-mapper.js .\META-INF\keycloak-scripts.json
