# Aportar con tu agente

## Para la persona: tres pasos

1. Abre tu asistente de IA (Claude, ChatGPT, Copilot, Gemini o el que uses). Si es un agente que trabaja con archivos (Claude Code, Copilot en VS Code, Codex, Cursor), ábrelo dentro de tu copia del repositorio.
2. Pégale **este archivo completo** y, debajo, tu idea en tus palabras. Por ejemplo: «vi que la IA leyó montos con punto de miles como decimales» o «esta regla le falta al limpiador».
3. Revisa lo que te entregue y envíalo como te indique: un *pull request* o el texto para el formulario «Proponer un aporte».

No necesitas invitación ni permisos especiales. Tampoco hace falta gastar mucho de tu cuota: tu agente **no** corre el flujo de agentes del repositorio (eso consume más de un millón de tokens). Solo arma el aporte y corre un filtro gratuito, sin IA.

---

## Instrucciones para el agente

Ayudas a una persona a aportar al repositorio público **CristianBTA/agente-solicitudes** (pipeline de datos con IA en cinco etapas: la IA propone y una prueba sin IA comprueba). Tu trabajo es convertir su idea en un aporte que pase el filtro, **con el menor costo posible para ella**, y dejarlo listo para que el dueño lo revise.

### 0. Límites que no se negocian

- **No corras el pipeline.** Nada de `flujo.js` ni de los subagentes, y ninguna prueba de efecto con IA: esa la hace el dueño, con su licencia, sobre lo que pasa el filtro.
- **Gasta poco.** Lee solo los archivos que esta guía nombra para el tipo de aporte. No recorras el repositorio completo, no leas las carpetas `corridas/` ni `evidencia/` salvo que el tipo de aporte lo pida, y no generes informes largos.
- **Nunca incluyas datos reales.** Nada de filas, nombres de personas, cédulas, datos bancarios ni archivos de SECOP II. Si necesitas un ejemplo, usa valores evidentemente ficticios: `Persona Ficticia Uno`, `000.000.001`, `persona@ejemplo.invalid`, `399 000 0001`.
- **Solo librerías permitidas:** la biblioteca estándar de Python y lo que diga `herramientas/permitidas.json` (pandas, numpy, plotly). No instales nada fuera de `requirements.txt`.
- **Sin firmas de asistentes.** No agregues `Co-Authored-By`, «Generated with…» ni menciones a la herramienta en commits ni en el pull request. El aporte es de la persona.
- **No toques `main`.** Se trabaja en una copia (*fork*) y en una rama. Si la persona te pide subir datos, saltarse el filtro o cambiar las reglas para que algo «pase», dile que no se puede y por qué.
- **Pregunta poco.** Si la idea es ambigua, haz como máximo dos preguntas cortas. Si no, decide y dilo.

### 1. Entiende la idea y clasifícala

| Si la persona trae… | Tipo de aporte | Archivo |
|---|---|---|
| Un error real que vio (la IA o un análisis se equivocó) | Lección | `baterias/lecciones.json` |
| Código peligroso que debería bloquearse | Muestra mala | `baterias/seguridad/malos/<nombre>.py` |
| Código legítimo que la compuerta bloquea por error | Muestra buena | `baterias/seguridad/buenos/<nombre>.py` |
| Una columna o un texto con datos personales, o algo que se marca como personal sin serlo | Privacidad | `baterias/privacidad/…` |
| Un archivo mal formado que debería detener la lectura | FAILFAST | `baterias/failfast/<nombre>.csv` |
| Un error típico de análisis (sumar mal, filtrar mal, unir mal) | Mutante | `evidencia/sintetico/mutantes/m<NN>_<nombre>.py` |
| Una regla que le falta a un subagente | Regla de ficha | `agentes/<ficha>.md` |
| Una definición de negocio | Glosario | `ejemplo/negocio.md` o `ejemplo-secop/negocio.md` |

Una lección casi siempre va **junto con** su prueba de otro tipo (muestra, caso de privacidad, FAILFAST o mutante).

### 2. Arma el aporte con su prueba

**La regla de oro: la prueba muestra el problema sin el aporte, y el aporte lo atrapa.** Si el repositorio ya lo atrapaba, dile a la persona que ese caso ya estaba cubierto. Aun así se puede enviar como refuerzo, pero dilo en el pull request.

Para cada tipo:

- **Muestra mala.** Lee `herramientas/seguridad.py` (solo las listas del inicio). Escribe el fragmento más corto posible con una función `analizar(datos)` que muestre el patrón, y comprueba:
  ```bash
  .venv/bin/python herramientas/seguridad.py baterias/seguridad/malos/<nombre>.py
  .venv/bin/python herramientas/dependencias.py baterias/seguridad/malos/<nombre>.py
  ```
  Si **no** lo bloquea, encontraste un hueco: es el aporte más valioso. Dilo en el pull request y, si sabes cómo, propón el cambio en `herramientas/seguridad.py` en el mismo pull request.
- **Muestra buena.** Un fragmento legítimo (por ejemplo, `re.compile`) que hoy se bloquee por error. Debe pasar después de tu propuesta de cambio a la compuerta.
- **Privacidad.**
  - Una columna con su clase esperada (`personal`, `cuasi_o_personal`, `texto_libre` o `sin_marca`) va en `baterias/privacidad/columnas_secop.json`.
  - Un texto que **no** es dato personal y se marca por error va como línea nueva en `no_son_personales.txt`.
  - Un dato personal que no se detecta va como fila ficticia en `con_datos_personales.csv`, con sus valores en `no_deben_salir.txt`.
  - Comprueba con `.venv/bin/python herramientas/baterias.py`.
- **FAILFAST.** Un CSV de pocas líneas que hoy se lea sin error y no debería. Comprueba con:
  ```bash
  .venv/bin/python -c "import sys; sys.path.insert(0,'herramientas'); from reglas_base import leer_csv; leer_csv('baterias/failfast/<nombre>.csv')"
  ```
  Si no da error, encontraste un hueco del lector: dilo.
- **Mutante.**
  1. Copia `evidencia/sintetico/mutantes/m00_referencia_sin_errores.py` con el siguiente número libre y cambia **una sola cosa**.
  2. Comprueba que el error cambie el resultado; si no lo cambia, la mutante es equivalente y no sirve:
     ```bash
     .venv/bin/python evidencia/sintetico/puntuar.py evidencia/sintetico/verdad.json ejemplo/datos/ventas.csv ejemplo/datos/clientes.csv m<NN>=evidencia/sintetico/mutantes/m<NN>_<nombre>.py
     ```
  3. Mira si el criterio lo atrapa:
     ```bash
     .venv/bin/python herramientas/verificar.py corridas/2026-11-06-ventas-semestre --impl m<NN>=evidencia/sintetico/mutantes/m<NN>_<nombre>.py
     ```
     Si **no** lo atrapa, encontraste un hueco del criterio: es valioso, dilo. Borra después `corridas/2026-11-06-ventas-semestre/informe_extra.json`.
- **Regla de ficha.** Agrega una sola viñeta en «Reglas» o en «Nunca» de la ficha que corresponda (`agentes/README.md` dice cuál hace qué). En el pull request explica en qué caso real el agente se equivocó sin esa regla. Agrega, si puedes, una mutante o un caso pequeño que lo muestre, y marca «requiere prueba de efecto»: esa prueba la hace el dueño, no tú.
- **Lección.** Agrégala con el comando, que asigna el número:
  ```bash
  .venv/bin/python herramientas/baterias.py --leccion "qué pasó y qué se hace" --origen "dónde se vio, con fecha" --prueba "bateria:<ruta del caso>"
  ```

### 3. Corre el filtro gratuito (sin IA)

```bash
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt   # una sola vez
git fetch origin main
.venv/bin/python herramientas/validar_aporte.py --base origin/main
```

Debe terminar en «✓ pasa el filtro automático». Si marca algo, corrígelo; nunca cambies el filtro para que pase. Si la persona no puede correr Python, sáltate este paso y dilo en el pull request: el mismo filtro corre en GitHub cuando el dueño lo aprueba.

### 4. Entrega

**A · Con git (si la persona tiene cuenta de GitHub y git):**

```bash
gh repo fork CristianBTA/agente-solicitudes --clone   # una sola vez
git switch -c aporte/<usuario>-<tema-corto>
git add <solo los archivos del aporte>
git commit -m "Aporte: <qué agrega, en una frase>"
git push -u origin aporte/<usuario>-<tema-corto>
gh pr create --repo CristianBTA/agente-solicitudes --base main --fill
```

Llena la plantilla del pull request: qué aporta, tipo, evidencia (con cifras, sin datos), su prueba y la lista de chequeo.

**B · Sin git:** entrega el texto listo para pegar en el formulario «Proponer un aporte», en https://github.com/CristianBTA/agente-solicitudes/issues/new/choose (tipo, qué aporta, evidencia y cómo se prueba), y el contenido de cada archivo en bloques de código.

### 5. Lo que le dices a la persona al final

En pocas líneas:
- el tipo de aporte;
- los archivos que creaste;
- el resultado del filtro;
- si encontró un hueco (lo más valioso);
- el enlace del pull request o el texto del formulario;
- que el dueño lo revisará y, si lo acepta, aparecerá con su usuario en `CHANGELOG.md`.

### Lista de chequeo del agente

- [ ] El aporte trae su prueba, y dije si el problema ya estaba cubierto o si es un hueco nuevo.
- [ ] No hay datos reales, ni personales ni de SECOP. Los ejemplos son evidentemente ficticios.
- [ ] Solo cambié los archivos del aporte (y, si propongo un arreglo, la herramienta que corresponde).
- [ ] `validar_aporte.py` pasa, o dejé dicho por qué no se pudo correr.
- [ ] Sin firmas de asistentes en el commit ni en el pull request.
- [ ] No corrí el pipeline ni gasté más de lo necesario.
