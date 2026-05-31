import json

# ── Datos mock (reemplazar con BD real en producción) ────────────────────────

PEDIDOS: dict = {
    "P001": {"id":"P001","cliente":"Empresa Textil Lima S.A.C.","descripcion":"50 polos con logo bordado talla M","estado":"En proceso","fecha_entrega":"2026-06-05","monto_total":750.00,"anticipo_pagado":375.00},
    "P002": {"id":"P002","cliente":"Colegio San Martín","descripcion":"100 gorras con escudo bordado","estado":"Completado - listo para recoger","fecha_entrega":"2026-05-15","monto_total":1200.00,"anticipo_pagado":1200.00},
    "P003": {"id":"P003","cliente":"Restaurante El Huarique","descripcion":"30 mandiles con nombre bordado","estado":"Pendiente de aprobación","fecha_entrega":"2026-06-10","monto_total":450.00,"anticipo_pagado":0.00},
    "P004": {"id":"P004","cliente":"Municipalidad de Puente Piedra","descripcion":"200 chalecos con logo institucional","estado":"En proceso","fecha_entrega":"2026-06-20","monto_total":3600.00,"anticipo_pagado":1800.00},
}

INVENTARIO: dict = {
    "hilos_polyester":    {"nombre":"Hilos Polyester","stock":45,"unidad":"conos","stock_minimo":10},
    "hilos_rayon":        {"nombre":"Hilos Rayón metálicos","stock":8,"unidad":"conos","stock_minimo":10},
    "bastidores_grandes": {"nombre":"Bastidores 30x40 cm","stock":12,"unidad":"unidades","stock_minimo":5},
    "bastidores_pequenos":{"nombre":"Bastidores 15x20 cm","stock":20,"unidad":"unidades","stock_minimo":5},
    "tela_entretela":     {"nombre":"Entretela estabilizadora","stock":3,"unidad":"rollos","stock_minimo":5},
}

PRECIOS: dict = {
    "bordado_pequeno": {"descripcion":"Bordado pequeño (hasta 5x5 cm)","precio_unit":3.50,"minimo":"10 piezas"},
    "bordado_mediano": {"descripcion":"Bordado mediano (hasta 10x10 cm)","precio_unit":6.00,"minimo":"5 piezas"},
    "bordado_grande":  {"descripcion":"Bordado grande (+10x10 cm)","precio_unit":12.00,"minimo":"5 piezas"},
    "digitalizacion":  {"descripcion":"Digitalización de logo o diseño","precio_unit":30.00,"minimo":"1 diseño"},
}

# ── Funciones de herramientas ────────────────────────────────────────────────

def consultar_pedido(numero_pedido: str) -> str:
    p = PEDIDOS.get(numero_pedido.upper().strip())
    if p:
        return json.dumps({**p, "saldo_pendiente": p["monto_total"] - p["anticipo_pagado"]}, ensure_ascii=False)
    return f"Pedido '{numero_pedido}' no encontrado. Pedidos disponibles: {', '.join(PEDIDOS.keys())}"

def listar_pedidos() -> str:
    resumen = [{"id":p["id"],"cliente":p["cliente"],"estado":p["estado"],
                "entrega":p["fecha_entrega"],"saldo":p["monto_total"]-p["anticipo_pagado"]}
               for p in PEDIDOS.values()]
    total_saldo = sum(p["monto_total"] - p["anticipo_pagado"] for p in PEDIDOS.values())
    return json.dumps({"pedidos": resumen, "total_saldo_pendiente": total_saldo}, ensure_ascii=False)

def registrar_pedido(cliente: str, descripcion: str, fecha_entrega: str, monto_total: float) -> str:
    nuevo_id = f"P{str(len(PEDIDOS)+1).zfill(3)}"
    PEDIDOS[nuevo_id] = {"id":nuevo_id,"cliente":cliente,"descripcion":descripcion,
                         "estado":"Nuevo - pendiente de inicio","fecha_entrega":fecha_entrega,
                         "monto_total":monto_total,"anticipo_pagado":0.0}
    return json.dumps({"mensaje":f"Pedido {nuevo_id} registrado correctamente.","pedido":PEDIDOS[nuevo_id]}, ensure_ascii=False)

def consultar_inventario(material: str = "todos") -> str:
    if material.lower() in ("todos","all",""):
        alertas = [v["nombre"] for v in INVENTARIO.values() if v["stock"] <= v["stock_minimo"]]
        return json.dumps({"inventario":INVENTARIO,"alertas_stock_bajo":alertas}, ensure_ascii=False)
    busqueda = material.lower()
    resultado = {k:v for k,v in INVENTARIO.items() if busqueda in k or busqueda in v["nombre"].lower()}
    return json.dumps(resultado or INVENTARIO, ensure_ascii=False)

def obtener_precios(tipo: str = "todos") -> str:
    if tipo.lower() in ("todos","all",""):
        return json.dumps(PRECIOS, ensure_ascii=False)
    busqueda = tipo.lower()
    resultado = {k:v for k,v in PRECIOS.items() if busqueda in k or busqueda in v["descripcion"].lower()}
    return json.dumps(resultado or PRECIOS, ensure_ascii=False)

def calcular_cotizacion(tipo_bordado: str, cantidad: int, urgente: bool = False) -> str:
    for k, v in PRECIOS.items():
        if tipo_bordado.lower() in k or tipo_bordado.lower() in v["descripcion"].lower():
            subtotal  = v["precio_unit"] * cantidad
            recargo   = subtotal * 0.30 if urgente else 0
            total     = subtotal + recargo
            return json.dumps({"servicio":v["descripcion"],"cantidad":cantidad,
                                "precio_unitario":v["precio_unit"],"subtotal":subtotal,
                                "recargo_urgente_30%":recargo,"TOTAL":total,
                                "anticipo_50%":total*0.5}, ensure_ascii=False)
    return "Tipo de bordado no encontrado. Opciones: bordado_pequeno, bordado_mediano, bordado_grande."

# ── Definiciones para Azure OpenAI ──────────────────────────────────────────

_tool = lambda name, desc, props, required=[]: {
    "type": "function",
    "function": {"name": name, "description": desc,
                 "parameters": {"type":"object","properties":props,"required":required}}
}

TOOLS_ADMIN = [
    _tool("consultar_pedido","Consulta estado de un pedido",{"numero_pedido":{"type":"string"}},["numero_pedido"]),
    _tool("listar_pedidos","Lista todos los pedidos con saldos pendientes",{}),
    _tool("registrar_pedido","Registra un nuevo pedido en el sistema",
          {"cliente":{"type":"string"},"descripcion":{"type":"string"},
           "fecha_entrega":{"type":"string","description":"YYYY-MM-DD"},"monto_total":{"type":"number"}},
          ["cliente","descripcion","fecha_entrega","monto_total"]),
    _tool("consultar_inventario","Consulta stock de materiales e incluye alertas de stock bajo",
          {"material":{"type":"string","description":"nombre del material o 'todos'"}}),
    _tool("obtener_precios","Obtiene precios de servicios de bordado",
          {"tipo":{"type":"string","description":"tipo de servicio o 'todos'"}}),
    _tool("calcular_cotizacion","Calcula cotización con subtotal, recargo urgente y anticipo",
          {"tipo_bordado":{"type":"string"},"cantidad":{"type":"integer"},"urgente":{"type":"boolean"}},
          ["tipo_bordado","cantidad"]),
]

# Empleado solo puede consultar, no registrar ni listar todo
TOOLS_EMPLEADO = [TOOLS_ADMIN[0], TOOLS_ADMIN[3], TOOLS_ADMIN[4], TOOLS_ADMIN[5]]

TOOL_MAP = {
    "consultar_pedido":   consultar_pedido,
    "listar_pedidos":     listar_pedidos,
    "registrar_pedido":   registrar_pedido,
    "consultar_inventario": consultar_inventario,
    "obtener_precios":    obtener_precios,
    "calcular_cotizacion": calcular_cotizacion,
}
