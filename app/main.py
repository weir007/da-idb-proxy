from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.core.keycloak import KeycloakError
from app.api.v1 import tenants, idp, identity, common


load_dotenv()

app = FastAPI(title="Keycloak Business Wrapper", version="1.0.0")

@app.exception_handler(KeycloakError)
async def global_kc_exception_handler(request: Request, exc: KeycloakError):
    # 错误处理逻辑（同上...）
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

# 挂载路由，注意顺序
app.include_router(tenants.router, prefix="/api/v1")
app.include_router(idp.router, prefix="/api/v1")
app.include_router(identity.router, prefix="/api/v1")
app.include_router(common.router, prefix="/api/v1")

@app.get("/api/v1/export-spec", include_in_schema=False)
def export_spec():
    """补全：导出 OpenAPI 规范"""
    return app.openapi()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8090, reload=True)
