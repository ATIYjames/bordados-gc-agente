"""
BORDADOS G&C — Sistema IA con Azure OpenAI
Autor: James Príncipe Veramendi — SENATI 2026
"""
import base64, json, pathlib, uuid
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import AzureOpenAI

import config, auth
import tools as T

# ── Cliente Azure OpenAI ─────────────────────────────────────────────────────
cliente = AzureOpenAI(
    api_key=config.AZURE_API_KEY,
    api_version=config.AZURE_API_VERSION,
    azure_endpoint=config.AZURE_ENDPOINT,
)

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="BORDADOS G&C — Sistema IA")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"], allow_credentials=True)

_img_dir = pathlib.Path(__file__).parent / "static" / "img"
if _img_dir.exists():
    app.mount("/img", StaticFiles(directory=str(_img_dir)), name="img")

# ── Sesiones en memoria ──────────────────────────────────────────────────────
sesiones: dict[str, list] = {}

# ── Cargar prompts desde archivo ─────────────────────────────────────────────
def load_prompt(rol: str) -> str:
    p = pathlib.Path(__file__).parent / "prompts" / f"{rol}.txt"
    return p.read_text(encoding="utf-8") if p.exists() else ""

# ── Pydantic models ──────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    mensaje: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    respuesta: str
    session_id: str

# ── Login ────────────────────────────────────────────────────────────────────
@app.post("/login")
def login(req: LoginRequest):
    user = auth.USERS.get(req.username)
    if not user or not auth.verify_password(req.password, user["password"]):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    token = auth.create_token({"sub": req.username, "rol": user["rol"], "nombre": user["nombre"]})
    return {"token": token, "rol": user["rol"], "nombre": user["nombre"]}

# ── Motor del agente (loop de herramientas) ──────────────────────────────────
def run_agent(mensaje: str, session_id: str, rol: str, imagen_b64: Optional[str] = None) -> str:
    system_prompt = load_prompt(rol)
    historial     = sesiones.get(session_id, [])
    tool_list     = T.TOOLS_ADMIN if rol == "admin" else T.TOOLS_EMPLEADO

    # Mensaje del usuario (con imagen opcional para facturas)
    if imagen_b64:
        user_content = [
            {"type": "text", "text": mensaje},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{imagen_b64}"}}
        ]
    else:
        user_content = mensaje

    messages = [{"role": "system", "content": system_prompt}] + historial + [{"role": "user", "content": user_content}]

    # Loop de herramientas (máx 5 iteraciones)
    last_msg = None
    for _ in range(5):
        resp    = cliente.chat.completions.create(model=config.AZURE_DEPLOYMENT, messages=messages, tools=tool_list, tool_choice="auto")
        last_msg = resp.choices[0].message
        messages.append(last_msg)

        if not last_msg.tool_calls:
            break

        for tc in last_msg.tool_calls:
            fn   = T.TOOL_MAP.get(tc.function.name)
            args = json.loads(tc.function.arguments)
            result = fn(**args) if fn else f"Función '{tc.function.name}' no disponible"
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    respuesta = (last_msg.content or "Sin respuesta") if last_msg else "Error interno"

    # Guardar historial (últimos 20 mensajes, sin imagen para no saturar memoria)
    historial.append({"role": "user", "content": mensaje})
    historial.append({"role": "assistant", "content": respuesta})
    sesiones[session_id] = historial[-20:]

    return respuesta

# ── Endpoints de chat ────────────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, usuario=Depends(auth.get_current_user)):
    sid = req.session_id or str(uuid.uuid4())
    try:
        respuesta = run_agent(req.mensaje, sid, usuario["rol"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error Azure OpenAI: {str(e)}")
    return ChatResponse(respuesta=respuesta, session_id=sid)

@app.post("/chat/factura")
async def chat_factura(
    mensaje: str = Form(default="Analiza esta factura: extrae proveedor, fecha, monto total, items y cualquier dato relevante"),
    session_id: Optional[str] = Form(default=None),
    imagen: UploadFile = File(...),
    usuario=Depends(auth.require_admin),
):
    sid      = session_id or str(uuid.uuid4())
    img_b64  = base64.b64encode(await imagen.read()).decode("utf-8")
    try:
        respuesta = run_agent(mensaje, sid, "admin", img_b64)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al analizar factura: {str(e)}")
    return {"respuesta": respuesta, "session_id": sid}

@app.delete("/chat/{session_id}")
def limpiar(session_id: str, usuario=Depends(auth.get_current_user)):
    sesiones.pop(session_id, None)
    return {"mensaje": "Sesión eliminada"}

@app.get("/estado")
def estado():
    return {"estado": "activo", "modelo": config.AZURE_DEPLOYMENT, "sesiones_activas": len(sesiones)}

# ── Páginas HTML ─────────────────────────────────────────────────────────────
def _page(name: str) -> HTMLResponse:
    p = pathlib.Path(__file__).parent / "templates" / f"{name}.html"
    return HTMLResponse(p.read_text(encoding="utf-8")) if p.exists() else HTMLResponse("<h1>404</h1>", 404)

@app.get("/",         response_class=HTMLResponse)
def root():           return RedirectResponse("/login")
@app.get("/login",    response_class=HTMLResponse)
def page_login():     return _page("login")
@app.get("/admin",    response_class=HTMLResponse)
def page_admin():     return _page("admin")
@app.get("/empleado", response_class=HTMLResponse)
def page_empleado():  return _page("empleado")

# ── Arranque ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("="*55)
    print("  BORDADOS G&C — Sistema IA con Azure OpenAI")
    print("  http://localhost:8000")
    print("  Usuarios: admin/admin123  |  empleado1/emp123")
    print("="*55)
    uvicorn.run(app, host="0.0.0.0", port=8000)
