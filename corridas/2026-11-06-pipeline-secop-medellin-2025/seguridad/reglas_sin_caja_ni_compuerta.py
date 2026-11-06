"""reglas_sin_caja_ni_compuerta · reglas.py (código de la IA) corre dentro del proceso del verificador.

verificar.py:98-117 (cargar_reglas) hace spec.loader.exec_module(reglas.py) directo: sin seguridad.py ni
dependencias.py, sin sandbox-exec (red y escritura libres) y sin alarma mientras se importa. impl_a/impl_b,
hipotesis.py y grafico.py sí pasan por la compuerta y la caja. El informe final dice que reglas.py también.

La prueba arma una corrida temporal cuya reglas.py, al importarse, escribe un archivo y se conecta a un
puerto local (127.0.0.1), y la carga con verificar.cargar_reglas(), igual que el verificador real. Después
corre ese mismo código de red en la caja (caja.correr) para mostrar que allí sí se niega.
Prueba de la revisión ciega (no es código de la IA). Solo escribe en una carpeta temporal.
"""
import os
import socket
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
C = Path(__file__).resolve().parent.parent
H = C.parent.parent / "herramientas"
sys.path.insert(0, str(H))
import caja  # noqa: E402
import seguridad  # noqa: E402
import verificar  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="seg-reglas-"))
marca = tmp / "escrito_al_importar.txt"
servidor = socket.socket()
servidor.bind(("127.0.0.1", 0))
servidor.listen(2)
servidor.settimeout(3)
puerto = servidor.getsockname()[1]
(tmp / "reglas.py").write_text(f'''
import os, signal, socket
from reglas_base import regla
open({str(marca)!r}, "w").write(str(os.getpid()))                    # escribe fuera de cualquier caja
socket.create_connection(("127.0.0.1", {puerto}), timeout=2).close()  # usa la red
ALARMA_AL_IMPORTAR = signal.getitimer(signal.ITIMER_REAL)[0]         # 0.0 = sin tope de tiempo

@regla("R1", "otra", "mide la alarma mientras corre una regla")
def r1(datos, resultado):
    return True, str(signal.getitimer(signal.ITIMER_REAL)[0])
''', encoding="utf-8")

reglas, problemas = verificar.cargar_reglas(tmp)
try:
    servidor.accept()[0].close()
    red_en_reglas = True
except OSError:
    red_en_reglas = False
escribio = marca.exists() and marca.read_text() == str(os.getpid())
alarma_import = reglas[0]["fn"].__globals__["ALARMA_AL_IMPORTAR"] if reglas else None
alarma_regla = float(verificar.correr_regla(reglas[0], {}, [])["mensaje"]) if reglas else None

# El mismo intento de red, dentro de la caja que sí usan impl_a/impl_b/hipotesis/grafico.
_, error_caja = caja.correr(f"import socket; socket.create_connection(('127.0.0.1', {puerto}), timeout=2)")
red_en_caja = error_caja is None

bloquearia = [h["regla"] for h in seguridad.revisar([tmp / "reglas.py"])[0][0]["bloquean"]]
fuente_verificar = (H / "verificar.py").read_text(encoding="utf-8")
cuerpo = fuente_verificar.split("def cargar_reglas", 1)[1].split("def cargar_caso", 1)[0]
aplica_compuerta = "compuertas(" in cuerpo or "seguridad." in cuerpo or "caja" in cuerpo.lower()
final = (H / "informe_final.py").read_text(encoding="utf-8")
promete = "revisados con compuertas" in final and "Todo se ejecuta en caja de arena" in final

print(f"reglas.py escribió un archivo desde el proceso del verificador (pid {os.getpid()}): {escribio}")
print(f"reglas.py se conectó a 127.0.0.1:{puerto}: {red_en_reglas} · el mismo código en la caja: "
      f"{'se conectó' if red_en_caja else 'bloqueado (' + str(error_caja)[:60] + ')'}")
print(f"alarma activa al importar reglas.py: {alarma_import} s · durante una regla: {alarma_regla:.0f} s")
print(f"la compuerta, si se aplicara a reglas.py, lo bloquearía por: {bloquearia}")
print(f"cargar_reglas aplica compuerta o caja: {aplica_compuerta} · el informe final afirma compuertas y caja "
      f"para todos los archivos de la IA: {promete}")
ok = escribio and red_en_reglas and not red_en_caja and alarma_import == 0 and bool(bloquearia) and not aplica_compuerta
print("CONFIRMADO" if ok else "NO SE REPRODUJO")
sys.exit(0 if ok else 1)
