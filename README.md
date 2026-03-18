# da-idb-proxy
Data Agent身份认证服务

## keycloak部署准备
### 安装Data Agent订制token插件
1. 在custom-token-mapper下打包：
    jar cvf data-agent-mapper.jar .\data-agent-mapper.js .\META-INF\keycloak-scripts.json
2. 将新生成的jar文件放入keycloak安装目录的providers下
3. 启动keycloak时附带参数 --features=scripts，示例（windows）：
    .\bin\kc.bat start-dev --features=scripts
