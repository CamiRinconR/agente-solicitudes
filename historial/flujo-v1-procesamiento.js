export const meta = {
  name: 'solicitud-verificada',
  description: 'Convierte una petición de datos en una solicitud con reglas, genera dos implementaciones independientes y las verifica sin leer código',
  whenToUse: 'Análisis de datos donde importa que la cifra sea correcta: una petición en una frase, archivos CSV y, si existe, el glosario del negocio',
  phases: [
    { title: 'Especificar', detail: 'perfil de los datos, definiciones, supuestos, preguntas, reglas y caso conocido; revisión independiente y sello' },
    { title: 'Generar', detail: 'dos implementaciones independientes: pandas y Python puro' },
    { title: 'Verificar', detail: 'código determinista: reglas, caso con respuesta conocida y A = B' },
    { title: 'Reparar', detail: 'hasta 2 rondas; el criterio sellado no se toca' },
  ],
}

// args: { peticion, datos: {tabla: ruta}, corrida, glosario?, python?, herramientas?, rondas? }
const A = args || {}
const PETICION = A.peticion
const DATOS = A.datos
const C = A.corrida
if (!PETICION || !DATOS || !C) {
  throw new Error('Faltan args: peticion (texto), datos ({tabla: ruta}) y corrida (carpeta nueva)')
}
const RAIZ = '/Users/macbookair/agente-solicitudes'
const H = A.herramientas || `${RAIZ}/herramientas`
const PY = A.python || `${RAIZ}/.venv/bin/python`
const GLOSARIO = A.glosario || null
const RONDAS = typeof A.rondas === 'number' ? A.rondas : 2

const datosTxt = Object.entries(DATOS).map(([t, r]) => `- ${t} = ${r}`).join('\n')
const tablasArg = Object.entries(DATOS).map(([t, r]) => `${t}=${r}`).join(' ')
const glosarioTxt = GLOSARIO
  ? `${GLOSARIO} (léelo completo; manda sobre cualquier suposición tuya)`
  : 'no hay. Todo significado de negocio que cambie la cifra va como pregunta, con un valor por defecto.'
const contexto = `PETICIÓN: «${PETICION}»
DATOS (tabla = ruta):
${datosTxt}
GLOSARIO DEL NEGOCIO: ${glosarioTxt}
CARPETA DE LA CORRIDA: ${C}
PYTHON: ${PY}
HERRAMIENTAS: ${H}
Trabaja solo con estas rutas. No le preguntes nada al usuario.`

const lista = (xs) => (xs || []).map((x) => `- ${x}`).join('\n') || '- (ninguna)'

const S_ESPEC = {
  type: 'object',
  properties: {
    listo: { type: 'boolean' },
    interpretacion: { type: 'string' },
    reglas: { type: 'array', items: { type: 'string' } },
    supuestos: { type: 'array', items: { type: 'string' } },
    preguntas: { type: 'array', items: { type: 'string' } },
    autoprueba_pasa: { type: 'boolean' },
    notas: { type: 'string' },
  },
  required: ['listo', 'reglas', 'autoprueba_pasa'],
}
const S_REVISION = {
  type: 'object',
  properties: {
    cambios: { type: 'array', items: { type: 'string' } },
    riesgos: { type: 'array', items: { type: 'string' } },
    autoprueba_pasa: { type: 'boolean' },
    sellada: { type: 'boolean' },
  },
  required: ['cambios', 'autoprueba_pasa', 'sellada'],
}
const S_GEN = {
  type: 'object',
  properties: { ok: { type: 'boolean' }, filas: { type: 'number' }, notas: { type: 'string' } },
  required: ['ok'],
}
const S_VER = {
  type: 'object',
  properties: {
    estado: { type: 'string' },
    motivos: { type: 'array', items: { type: 'string' } },
    fallas_a: { type: 'array', items: { type: 'string' } },
    fallas_b: { type: 'array', items: { type: 'string' } },
    concuerdan: { type: 'boolean' },
    preguntas_abiertas: { type: 'number' },
    reglas_rotas: { type: 'array', items: { type: 'string' } },
  },
  required: ['estado', 'fallas_a', 'fallas_b', 'concuerdan'],
}
const S_REP = {
  type: 'object',
  properties: { cambios: { type: 'string' }, regla_sospechosa: { type: 'string' } },
  required: ['cambios'],
}

const pEspecificar = `Eres el ESPECIFICADOR de un sistema que produce análisis de datos verificados. Conviertes una petición de una frase en una solicitud precisa y comprobable. No escribes el análisis: escribes QUÉ debe salir, CÓMO se tratan los datos y CÓMO se comprueba el resultado. Después, dos generadores independientes escribirán el código solo a partir de tu spec.json, sin ver tus reglas.

${contexto}

1. PERFIL. Crea la carpeta de la corrida y corre: ${PY} ${H}/perfilar.py ${tablasArg} --json ${C}/perfil.json
   El perfil es la fuente de hechos sobre los datos. Cada hallazgo que pueda mover la cifra (formatos de fecha mezclados, filas repetidas, claves repetidas, variantes de escritura, espacios, códigos que no cruzan, vacíos, valores fuera del período) tiene que terminar en un tratamiento de datos de la spec Y quedar cubierto por una regla o por el caso conocido. Lo que el perfil demuestra (por ejemplo, «día primero» porque hay fechas con barras cuyo primer número es mayor que 12) es fuente «datos», no un supuesto.

2. ${C}/spec.json con estas claves:
   peticion (texto); datos ({tabla: ruta absoluta}); glosario (ruta o null);
   interpretacion (un párrafo en palabras sencillas: qué cifra sale, qué incluye y qué excluye);
   definiciones: [{termino, definicion, fuente: "glosario" | "datos" | "supuesto"}];
   tratamiento_de_datos: [{hallazgo (con la cifra del perfil), tratamiento, fuente}];
   supuestos: [{id: "S1", decision, alternativa, impacto}] — solo decisiones tuyas que no salen del glosario ni de los datos;
   preguntas: [{id: "P1", pregunta, por_defecto, por_que_importa}] — solo lo que ni el glosario ni los datos resuelven y que cambia la cifra; nunca preguntes lo que el glosario ya dice;
   salida: {claves: [columnas de agrupación], valores: [columnas numéricas], tolerancia: 0.5, orden, descripcion};
   reglas: [{id, tipo, descripcion}] — las mismas de reglas.py, solo el texto.

3. ${C}/reglas.py con 4 a 8 reglas ejecutables. Empieza con «from reglas_base import regla, leer_csv, aprox, suma» (está en ${H}; léelo antes). Cada regla es una función (datos, resultado) -> (ok, mensaje), donde datos = {tabla: ruta_csv} y resultado = lista de filas. Catálogo (usa los que apliquen):
   - conservacion: el total del resultado = el total calculado directo de la fuente, SIN unir tablas (si la unión duplica o pierde filas, se nota).
   - cobertura: el valor que no cruza con la otra tabla aparece donde la spec dice; no se pierde.
   - cardinalidad / unicidad: claves del resultado sin repetir; claves de unión únicas tras el tratamiento.
   - dominio: claves del resultado dentro de la lista cerrada; valores en rango.
   - completitud: están los grupos que deben estar; ninguno partido por diferencias de escritura.
   - otra que el glosario o el perfil pidan.
   Las reglas son más simples que el análisis y se calculan de forma independiente: pueden repetir un tratamiento puntual (leer fechas, quitar repetidos), nunca la unión ni la agrupación que verifican. Deben funcionar con CUALQUIER datos que tengan esas columnas (también se corren sobre el caso conocido) y su mensaje muestra las cifras comparadas. Solo biblioteca estándar, nada de pandas: así una trampa de pandas no se cuela en el criterio.

4. CASO CON RESPUESTA CONOCIDA. ${C}/caso_conocido/<tabla>.csv por cada tabla (mismas columnas que los reales, 8 a 25 filas) con al menos un ejemplo de CADA tratamiento de datos de la spec y de cada definición del glosario que aplique, y ${C}/caso_conocido/esperado.json (lista de filas con las columnas de salida) calculado a mano. Escribe la cuenta fila por fila en ${C}/caso_conocido/cuentas.md y compruébala una segunda vez con un script tuyo aparte.

5. AUTOPRUEBA: ${PY} ${H}/verificar.py ${C} --autoprueba
   Todas las reglas deben pasar sobre el caso conocido con su resultado esperado. Si una falla, corrige lo que esté mal (la regla o la cuenta) y repite.

No escribas impl_a.py ni impl_b.py. No selles la corrida: eso lo hace el revisor.`

const pRevisar = `Eres el REVISOR de una especificación, independiente de quien la escribió. Tu trabajo es encontrar lo que falta o está mal ANTES de que se escriba el código: si el criterio está mal, todo lo que venga después se aprueba mal.

${contexto}

Lee ${C}/spec.json, ${C}/reglas.py, ${C}/perfil.json y todo ${C}/caso_conocido/ (incluido cuentas.md). Revisa en este orden:
1. Glosario → spec: cada definición del glosario que aplica a la petición está en la spec y dice lo mismo que el glosario. Nada de la spec lo contradice.
2. Perfil → spec: cada hallazgo del perfil que puede mover la cifra tiene tratamiento en la spec y lo cubre una regla o el caso conocido. Si dudas, corre tú el perfil.
3. Reglas: para cada error típico que aplica a estos datos (unión que duplica filas, devoluciones sumadas o ignoradas, impuestos incluidos, fechas leídas al revés, repetidos contados dos veces, códigos sin normalizar, grupos partidos por la escritura, valores descartados sin avisar), imagina un análisis que lo comete: ¿lo atrapa alguna regla o el caso conocido con ESTOS datos? Si ninguno lo atrapa, agrega o mejora una regla.
4. Caso conocido: rehaz la cuenta desde los CSV con tu propio código y compárala con esperado.json.
5. Preguntas y supuestos: quita las preguntas que el glosario ya responde; agrega como supuesto o pregunta toda decisión que cambie la cifra y no esté resuelta.
Corrige directamente spec.json, reglas.py o el caso conocido, y mantén spec.reglas igual a reglas.py. Después corre:
   ${PY} ${H}/verificar.py ${C} --autoprueba   (debe pasar completa)
   ${PY} ${H}/verificar.py ${C} --sellar
No escribas impl_a.py ni impl_b.py.`

const herramientaDe = (x) => x === 'a'
  ? 'Herramienta obligatoria: pandas (está instalado en ese Python).'
  : 'Herramienta obligatoria: solo biblioteca estándar de Python (csv, datetime, collections, re, unicodedata); nada de pandas. Es a propósito: un enfoque distinto al del generador A.'

const pGenerar = (x) => `Eres el GENERADOR ${x.toUpperCase()}. Escribe ${C}/impl_${x}.py con una función analizar(datos) -> list[dict], donde datos = {tabla: ruta_csv}. Devuelve una fila por grupo con las columnas de salida de la spec (claves y valores), con los valores como números.

${contexto}

Lee SOLO ${C}/spec.json, el glosario, ${C}/perfil.json si te sirve y los CSV de datos. NO abras reglas.py, caso_conocido/, sellos.json, informe.* ni la implementación del otro generador: la verificación tiene que ser independiente de tu código.
${herramientaDe(x)}
- Debe funcionar con CUALQUIER datos que tengan las mismas columnas: también se correrá sobre archivos pequeños distintos. Nada de rutas fijas ni de valores del resultado escritos a mano.
- Sigue spec.json al pie de la letra: interpretacion, definiciones, tratamiento_de_datos y supuestos. Si algo te parece contradictorio, síguela igual y anótalo en notas.
- Pruébala: ${PY} -c "import importlib.util,json; s=importlib.util.spec_from_file_location('m','${C}/impl_${x}.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(json.dumps(m.analizar(json.load(open('${C}/spec.json'))['datos']), ensure_ascii=False))"`

const pVerificar = `Ejecuta exactamente este comando y ningún otro: ${PY} ${H}/verificar.py ${C}
La última línea de la salida empieza con «RESUMEN » y sigue un JSON. Devuelve sus campos tal cual: estado, motivos, fallas_a, fallas_b, concuerdan, preguntas_abiertas, reglas_rotas. No modifiques archivos, no corrijas nada y no resumas ni interpretes los textos.`

const pReparar = (x, ver, ronda) => `Eres el REPARADOR de ${C}/impl_${x}.py (ronda ${ronda}). La verificación determinista encontró esto en tu implementación:
${lista(ver[`fallas_${x}`])}
${ver.concuerdan === false ? `Además, las dos implementaciones independientes no dan lo mismo. Revisa tu lógica contra la spec; no copies a la otra.\n${lista((ver.motivos || []).filter((m) => m.includes('no dan lo mismo')))}` : ''}

${contexto}

Lee ${C}/spec.json, la sección implementaciones.${x} de ${C}/informe.json (el mensaje de cada regla con sus cifras y, si aplica, el caso conocido: obtenido frente a esperado) y el glosario.
Corrige SOLO ${C}/impl_${x}.py. Prohibido: modificar spec.json, reglas.py, caso_conocido/ o sellos.json; abrir reglas.py o la otra implementación; escribir valores fijos o casos especiales para los datos de prueba. ${herramientaDe(x)}
Si estás seguro de que lo que está mal es el criterio (una regla o el resultado esperado) y no tu código, no cambies nada y explícalo en regla_sospechosa: eso lo decide un humano.
Antes de terminar corre ${PY} ${H}/verificar.py ${C} y revisa tu sección del resultado.`

// ---------------- orquestación ----------------
phase('Especificar')
const esp = await agent(pEspecificar, { label: 'especificador', phase: 'Especificar', schema: S_ESPEC, effort: 'high' })
if (!esp || !esp.listo) {
  return { corrida: C, estado: 'sin_especificacion', especificador: esp }
}
log(`Especificación: ${esp.reglas.length} reglas, ${(esp.supuestos || []).length} supuestos, ${(esp.preguntas || []).length} preguntas`)
const rev = await agent(pRevisar, { label: 'revisor de la especificación', phase: 'Especificar', schema: S_REVISION, effort: 'high' })
if (!rev || !rev.sellada || !rev.autoprueba_pasa) {
  return { corrida: C, estado: 'criterio_sin_sellar', especificador: esp, revisor: rev }
}
log(`Criterio sellado tras la revisión (${rev.cambios.length} cambios)`)

phase('Generar')
const generadores = await parallel(['a', 'b'].map((x) => () =>
  agent(pGenerar(x), { label: `generador ${x.toUpperCase()}`, phase: 'Generar', schema: S_GEN })))

phase('Verificar')
let ver = await agent(pVerificar, { label: 'verificación inicial', phase: 'Verificar', schema: S_VER, model: 'haiku' })
const historial = [ver]
const sospechas = []
for (let ronda = 1; ronda <= RONDAS && ver && ver.estado !== 'aprobado'; ronda++) {
  let reparables = ['a', 'b'].filter((x) => (ver[`fallas_${x}`] || []).length > 0)
  if (!reparables.length && ver.concuerdan === false) reparables = ['a', 'b']
  if (!reparables.length) {
    log('Lo que queda es del criterio (sello o reglas con error): lo decide un humano')
    break
  }
  phase('Reparar')
  const reps = await parallel(reparables.map((x) => () =>
    agent(pReparar(x, ver, ronda), { label: `reparador ${x.toUpperCase()} · ronda ${ronda}`, phase: 'Reparar', schema: S_REP })))
  reps.forEach((r, i) => {
    if (r && r.regla_sospechosa) sospechas.push({ implementacion: reparables[i], ronda, explicacion: r.regla_sospechosa })
  })
  phase('Verificar')
  ver = await agent(pVerificar, { label: `verificación tras la ronda ${ronda}`, phase: 'Verificar', schema: S_VER, model: 'haiku' })
  historial.push(ver)
}

log(`Estado final: ${ver ? ver.estado : 'desconocido'}`)
return {
  corrida: C,
  estado: ver ? ver.estado : 'desconocido',
  informe: `${C}/informe.md`,
  verificacion_final: ver,
  rondas_de_reparacion: historial.length - 1,
  historial_estados: historial.map((v) => (v ? v.estado : null)),
  especificador: esp,
  revisor: rev,
  generadores,
  sospechas_sobre_el_criterio: sospechas,
}
