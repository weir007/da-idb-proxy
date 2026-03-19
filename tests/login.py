from flask import Flask, request, redirect, session
import requests
from jose import jwt
from urllib.parse import quote


app = Flask(__name__)
app.secret_key = "anything-secret"  # 仅用于 Flask Session
# --- 配置参数 ---
KEYCLOAK_BASE = "http://localhost:8080"
REALM = "da-huaxi"

# 禁用代理（根据你的公司网络情况）
PROXIES = {"http": None, "https": None}

CLIENT_ID = "sp-data-agent-oidc-client"
CLIENT_SECRET = "04950d9e-e4d0-4049-85ca-62a5e293b03e"

IDP_HINT = "huaxi-saml"  # 你在 Broker 配的 IDP 别名
REDIRECT_URI = "http://localhost:5000/callback"


@app.route('/')
def index():
    # 首页：点击登录，直接跳转到 Broker 并指定 IDP
    login_url = (
        f"{oidc_config['auth_endpoint']}?client_id={CLIENT_ID}&response_type=code"
        f"&scope=openid&redirect_uri={REDIRECT_URI}&kc_idp_hint={IDP_HINT}"
    )
    return f'<h1>ID Broker Demo</h1><a href="{login_url}"><button style="padding:10px">点击登录 (跳转客户IDP)</button></a>'


def verify_keycloak_token(access_token, jwks_uri, client_id, issuer_url):
    """
    封装的 JWK 鉴权函数
    :param access_token: 待验证的 JWT 字符串
    :param jwks_uri: Keycloak 的 certs 端点
    :param client_id: OIDC Client ID (校验 Audience)
    :param issuer_url: Keycloak Realm URL (校验 Issuer)
    :return: dict (payload) or None
    """
    print("access_token:", access_token["access_token"])
    try:
        # 1. 获取公钥集（禁用代理防止 504）
        jwks = requests.get(jwks_uri, proxies=PROXIES, timeout=5).json()
        print("jwks:", jwks)

        # 2. 从 Token Header 中提取 kid (密钥 ID)
        header = jwt.get_unverified_header(access_token['access_token'])
        print("header:", header)
        kid = header.get('kid')

        # 3. 匹配对应的 RSA 公钥
        rsa_key = next((k for k in jwks['keys'] if k['kid'] == kid), None)
        if not rsa_key:
            print("❌ 无法匹配 JWK 公钥")
            return None
        else:
            print("rsa_key:", rsa_key)

        # 4. 验证签名、有效期、颁发者和受众
        payload = jwt.decode(
            access_token['access_token'],
            rsa_key,
            algorithms=['RS256'],
            audience='account',
            issuer=issuer_url
        )
        print("payload:", payload)
        return payload
    except Exception as e:
        print(f"❌ JWK 验证失败: {str(e)}")
        return None


@app.route('/callback')
def callback():
    # 1. 接收从 Broker 回传的 Authorization Code
    code = request.args.get('code')
    if not code:
        return "未获取到 Code", 400

    # 2. 调用 idb-proxy 的 token 端点换取 Token（增强版，包含 realm_id 和 role_ids）
    proxy_token_url = f"http://localhost:8090/api/v1/{REALM}/token/exchange"
    data = {
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    token_res_raw = requests.post(proxy_token_url, json=data, proxies={"http": None, "https": None})

    # --- 调试代码：如果报错，直接看原文 ---
    if token_res_raw.status_code != 200:
        print(f"状态码: {token_res_raw.status_code}")
        print(f"内容: {token_res_raw.text}")
        return f"<h3>换取 Token 失败</h3><pre>{token_res_raw.text}</pre>", 400

    token_response = token_res_raw.json()
    access_token = {
        "access_token": token_response.get("access_token"),
        "token_type": token_response.get("token_type"),
        "expires_in": token_response.get("expires_in"),
        "refresh_token": token_response.get("refresh_token"),
        "scope": token_response.get("scope")
    }

    # 保存 id_token 到 session，用于登出时传递 id_token_hint
    id_token = token_response.get("id_token")
    if id_token:
        session['id_token'] = id_token

    # 打印增强信息
    print(f"resp: {token_response}")
    print(f"tenant: {token_response.get('tenant')}")
    print(f"roles: {token_response.get('roles')}")

    # 调用封装函数
    user_info = verify_keycloak_token(access_token, oidc_config['jwks_uri'], CLIENT_ID, oidc_config['issuer'])

    if user_info:
        # 在页面显示增强信息
        enhanced_info = f"""
        <h1>✅ 欢迎, {user_info.get('preferred_username')}</h1>
        <p><b>Tenant: </b>{user_info.get('tenant', 'N/A')}</p>
        <p><b>Roles: </b>{user_info.get('roles', [])}</p>
        <p><b>Details: </b>{user_info}</p>
        <a href="/logout"><button style="padding:10px">登出</button></a>
        """
        return enhanced_info
    else:
        return "<h1>❌ 鉴权未通过</h1>", 401


@app.route('/logout')
def logout():
    """登出端点：调用 Keycloak 的 end_session_endpoint 清除用户会话"""
    end_session_url = oidc_config.get('end_session_endpoint')
    if end_session_url:
        # 构造登出 URL，包含 id_token_hint 和 post_logout_redirect_uri
        logout_url = f"{end_session_url}?post_logout_redirect_uri={REDIRECT_URI}"
        
        # 从 session 中获取 id_token 作为 id_token_hint
        id_token = session.pop('id_token', None)
        if id_token:
            # 对 id_token 进行 URL 编码，确保特殊字符正确传递
            logout_url += f"&id_token_hint={quote(id_token, safe='')}"
        
        return redirect(logout_url)
    else:
        # 如果没有配置 end_session_endpoint，直接重定向到首页
        return redirect('/')


def load_oidc_config(broker_url, realm):
    """
    通过 Discovery Endpoint 自动加载所有配置
    """
    discovery_url = f"{broker_url}/realms/{realm}/.well-known/openid-configuration"
    try:
        print(f"正在从 {discovery_url} 加载配置...")
        config = requests.get(discovery_url, proxies=PROXIES, timeout=5).json()

        return {
            "auth_endpoint": config.get("authorization_endpoint"),
            "token_endpoint": config.get("token_endpoint"),
            "jwks_uri": config.get("jwks_uri"),
            "issuer": config.get("issuer"),
            "end_session_endpoint": config.get("end_session_endpoint")
        }
    except Exception as e:
        print(f"❌ 无法加载 OIDC 配置: {e}")
        return None


oidc_config = load_oidc_config(KEYCLOAK_BASE, REALM)


if __name__ == '__main__':
    # 运行在 5000 端口
    app.run(port=5000, debug=True)
