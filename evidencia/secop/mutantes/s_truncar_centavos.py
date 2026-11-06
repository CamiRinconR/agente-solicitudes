"""Referencia que sigue la spec del sistema (SECOP), con un interruptor ERROR para cometer un error a la vez."""
import csv, os, unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
ERROR = "truncar_centavos"
ACTIVOS = {"en ejecución", "modificado", "aprobado", "suspendido", "cedido"}
def norm(s): return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").strip().upper()
def analizar(datos):
    filas = list(csv.DictReader(open(datos["contratos"], encoding="utf-8-sig", newline="")))
    vistos, unicas = set(), []
    for f in filas:
        k = f["id_contrato"].strip()
        if k in vistos: continue
        vistos.add(k); unicas.append(f)
    if ERROR == "sobre_depurar":
        v2, u2 = set(), []
        for f in unicas:
            k = (f["nit_entidad"], f["valor_del_contrato"], f["fecha_de_firma"][:10])
            if k not in v2: v2.add(k); u2.append(f)
        unicas = u2
    val, cnt, nombres, proc = defaultdict(Decimal), Counter(), defaultdict(Counter), defaultdict(set)
    for f in unicas:
        if norm(f["ciudad"]) != "MEDELLIN": continue
        firma = f["fecha_de_inicio_del_contrato"] if ERROR == "fecha_inicio" else f["fecha_de_firma"]
        if not firma: continue
        if ERROR == "corte_texto_31_dic": dentro = "2025-01-01" <= firma <= "2025-12-31"
        elif ERROR == "zona_horaria": dentro = (datetime.fromisoformat(firma[:19]) - timedelta(hours=5)).year == 2025
        else: dentro = firma[:4] == "2025"
        if not dentro: continue
        if ERROR == "excluir_credito_publico" and f["tipo_de_contrato"] == "Operaciones de Crédito Público": continue
        if ERROR == "solo_activos" and f["estado_contrato"].strip().lower() not in ACTIVOS: continue
        k = f["nombre_entidad"] if ERROR == "agrupar_por_nombre" else f["nit_entidad"].strip()
        v = Decimal((f["valor_pagado"] if ERROR == "valor_pagado" else f["valor_del_contrato"]) or "0")
        if ERROR == "truncar_centavos": v = Decimal(int(v))
        val[k] += v
        if not (ERROR == "sin_valor_cero_en_conteo" and v == 0): cnt[k] += 1
        proc[k].add(f["proceso_de_compra"]); nombres[k][f["nombre_entidad"].strip()] += 1
    out = []
    for k in val:
        nombre = sorted(nombres[k].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        out.append({"nit_entidad": k if ERROR != "agrupar_por_nombre" else "", "entidad": nombre if ERROR != "agrupar_por_nombre" else k,
                    "valor_contratado": float(val[k]), "numero_contratos": len(proc[k]) if ERROR == "contar_procesos" else cnt[k]})
    out.sort(key=lambda r: (-r["valor_contratado"], r["nit_entidad"]))
    return out
