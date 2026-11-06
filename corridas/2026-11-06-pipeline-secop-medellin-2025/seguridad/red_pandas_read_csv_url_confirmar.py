"""red_pandas_read_csv_url · impl_a.py:86 (_leer) le pasa a pd.read_csv la ruta que llega en datos: con una URL,
pandas la descarga. La «función pura» hace red según su entrada, y la compuerta no lo ve: seguridad.py solo
busca módulos de red (socket, urllib, http, requests…) y pd.read_csv con URL no importa ninguno. Hoy lo frenan
dos cosas ajenas al código: verificar.cargar_spec exige que la ruta exista y sandbox-exec niega la red; sin
sandbox-exec (otra máquina) caja.py y verificar.py corren sin caja.
El fragmento mínimo para la batería es red_pandas_read_csv_url.py. Esta prueba levanta un servidor HTTP en
127.0.0.1, le pasa su URL a impl_a.analizar() y cuenta los pedidos que llegan. Contraste: impl_b usa open().
Prueba de la revisión ciega (no es código de la IA). No escribe archivos.
"""
import http.server
import importlib.util
import os
import sys
import threading
from pathlib import Path

sys.dont_write_bytecode = True
os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost"
C = Path(__file__).resolve().parent.parent
H = C.parent.parent / "herramientas"
sys.path.insert(0, str(H))
import dependencias  # noqa: E402
import seguridad  # noqa: E402

CUERPO = ("id_contrato,nit_entidad,codigo_entidad,nombre_entidad,fecha_de_firma,valor_del_contrato\n"
          "C1,890905211,1,ENTIDAD REMOTA,2025-03-01T10:00:00.000,123\n").encode()
PEDIDOS = []


class Servidor(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        PEDIDOS.append(self.path)
        self.send_response(200)
        self.send_header("Content-Type", "text/csv")
        self.send_header("Content-Length", str(len(CUERPO)))
        self.end_headers()
        self.wfile.write(CUERPO)

    def log_message(self, *args):
        pass


srv = http.server.HTTPServer(("127.0.0.1", 0), Servidor)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}/contratos.csv"


def cargar(archivo):
    spec = importlib.util.spec_from_file_location(Path(archivo).stem + "_bajo_prueba", C / archivo)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


res_a = cargar("impl_a.py").analizar({"contratos": url})
try:
    cargar("impl_b.py").analizar({"contratos": url})
    b = "leyó la URL"
except OSError as e:
    b = f"no la lee ({type(e).__name__})"
srv.shutdown()
frag = Path(__file__).with_name("red_pandas_read_csv_url.py")
compuerta = seguridad.revisar([frag])[0][0]["bloquean"]
libs = dependencias.revisar(frag)
print(f"impl_a.analizar con una URL: {res_a} · pedidos HTTP recibidos: {PEDIDOS}")
print(f"impl_b con la misma URL: {b}")
print(f"compuerta sobre el fragmento: {'lo bloquea' if compuerta else 'no lo bloquea'} · librerías: "
      f"{libs.get('no_permitidas') or 'todas permitidas'}")
ok = PEDIDOS == ["/contratos.csv"] and res_a and res_a[0]["entidad"] == "ENTIDAD REMOTA" and not compuerta
print("CONFIRMADO" if ok else "NO SE REPRODUJO")
sys.exit(0 if ok else 1)
