"""Mutante m07_maestro_primer_registro: la referencia con un solo error típico."""
import re, unicodedata
import pandas as pd
OF = ["Antioquia","Bogotá D.C.","Caldas","Risaralda","Valle del Cauca"]
def k(s): return re.sub(r"[^0-9a-z]","","".join(c for c in unicodedata.normalize("NFD",s) if unicodedata.category(c)!="Mn").casefold())
AL = {k(r): r for r in OF} | {"bogota": "Bogotá D.C.", "valle": "Valle del Cauca"}
def _base(datos):
    v = pd.read_csv(datos["ventas"], dtype=str, keep_default_na=False).drop_duplicates()
    c = pd.read_csv(datos["clientes"], dtype=str, keep_default_na=False)
    v["fecha_d"] = pd.to_datetime(v["fecha"], format="%Y-%m-%d", errors="coerce").fillna(pd.to_datetime(v["fecha"], format="%d/%m/%Y", errors="coerce"))
    v = v[(v.fecha_d >= "2026-01-01") & (v.fecha_d <= "2026-06-30")].copy()
    v["neto"] = v.subtotal.astype(int) * v.tipo_documento.map({"FV": 1, "NC": -1})
    v["cid"] = v.cliente_id.str.strip().str.upper()
    c["cid"] = c.cliente_id.str.strip().str.upper()
    c = c.drop_duplicates("cid", keep="first")
    c["reg"] = c.region.map(lambda s: AL[k(s)])
    m = v.merge(c[["cid","reg"]], on="cid", how="left")
    m["reg"] = m["reg"].fillna("Sin región")
    g = m.groupby("reg", as_index=False)["neto"].sum()
    return [{"region": r, "ventas": int(n)} for r, n in zip(g.reg, g.neto)]


# Adaptador a la salida de la spec de la corrida (columna ventas_netas, siempre 6 filas, en su orden).
OFICIALES = ["Antioquia", "Bogotá D.C.", "Caldas", "Risaralda", "Valle del Cauca"]


def analizar(datos):
    d = {}
    for f in _base(datos):
        d[str(f["region"])] = d.get(str(f["region"]), 0) + f["ventas"]
    for r in OFICIALES + ["Sin región"]:
        d.setdefault(r, 0)
    of = sorted([k for k in d if k != "Sin región"], key=lambda k: -d[k])
    return [{"region": k, "ventas_netas": d[k]} for k in of] + [{"region": "Sin región", "ventas_netas": d["Sin región"]}]
