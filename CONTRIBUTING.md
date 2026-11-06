# Cómo aportar

Este repositorio crece con lo que aprende el grupo: errores reales, reglas y casos de prueba. Para que un aporte no dañe lo que ya funciona, **todo pasa por un filtro antes de entrar**, y nadie gasta su cuota de IA para aportar.

## Lo que necesitas (y lo que no)

- Una cuenta gratis de GitHub. **No** necesitas que te inviten como colaborador: en un repositorio público cualquiera puede proponer.
- **No** necesitas correr el flujo con agentes ni gastar tu cuota de ningún asistente. Una corrida completa consume más de un millón de tokens; la prueba con IA la hace el dueño del repositorio, con su licencia.
- **Nunca** subas datos: ni filas, ni nombres, ni cédulas, ni datos bancarios, ni archivos de SECOP.

## La forma más fácil: con tu agente

Pégale [`APORTAR-CON-TU-AGENTE.md`](APORTAR-CON-TU-AGENTE.md) a tu asistente (Claude, ChatGPT, Copilot, Gemini…) junto con tu idea. Él clasifica el aporte, arma los archivos con su prueba, corre el filtro gratuito y te deja listo el pull request o el texto del formulario, gastando lo mínimo de tu cuota.

## Dos maneras de proponer

1. **Sin git:** abre un *issue* con el formulario «Proponer un aporte». Si sirve, el dueño lo convierte en cambio y te da el crédito.
2. **Con git:** haz un *fork*, crea una rama, agrega tu aporte con su prueba y abre un *pull request* hacia `main`. La plantilla te pide lo necesario.

## Qué se puede aportar

| Aporte | Dónde va | Su prueba |
|---|---|---|
| Lección: un error real que viste | `baterias/lecciones.json` (con `herramientas/baterias.py --leccion`) | La lección apunta a la prueba que lo atrapa |
| Código peligroso que debería bloquearse | `baterias/seguridad/malos/<nombre>.py` | La compuerta debe bloquearlo; si hoy no lo bloquea, encontraste un hueco |
| Código legítimo que se bloquea por error | `baterias/seguridad/buenos/<nombre>.py` | Debe pasar la compuerta |
| Caso de privacidad | `baterias/privacidad/` | El barrido debe detectarlo, o no marcarlo si no es personal |
| Archivo mal formado (FAILFAST) | `baterias/failfast/<nombre>.csv` | La lectura debe detenerse con error |
| Mutante: un error típico de análisis | `evidencia/sintetico/mutantes/` | El criterio debe atraparlo sin dar falsas alarmas |
| Regla para la ficha de un subagente | `agentes/<ficha>.md` | Prueba de efecto con IA, que hace el dueño (nivel 3) |
| Definición del glosario | `ejemplo/negocio.md` o `ejemplo-secop/negocio.md` | La revisa el dueño |

La regla de oro: **tu prueba falla sin tu aporte y pasa con él.** Si ya pasaba antes, el aporte no agrega nada nuevo.

## El embudo

| Nivel | Quién | Costo para quien aporta | Qué se revisa |
|---|---|---|---|
| 0 | Tú propones | Ninguno | — |
| 1 | GitHub Actions (`validar-aporte`), sin IA y sin llaves | Ninguno | Archivos prohibidos, datos personales, seguridad del código, que no rompa las baterías ni la corrida sintética, que el criterio siga atrapando las 12 mutantes |
| 2 | El dueño, leyendo | Ninguno | ¿Es real, es nuevo, aporta? |
| 3 | El dueño, con su licencia, en lote y con tope de tokens | Ninguno | Solo para reglas de las fichas: el flujo con y sin la regla sobre el banco sintético, varias veces; se acepta si atrapa más errores o da menos falsas alarmas sin disparar el costo |
| 4 | El dueño acepta | Ninguno | Entra a `main` y queda en `CHANGELOG.md` con tu usuario |

El filtro del nivel 1 se puede correr en tu máquina antes de enviar (opcional y gratis, sin IA):

```bash
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python herramientas/validar_aporte.py --base origin/main
```

## Por qué así

- **`main` está protegida.** Solo entra lo que pasa el filtro automático y el dueño aprueba.
- **La primera vez que alguien envía un pull request, el dueño aprueba que corra el filtro.** Es una protección de GitHub para repositorios públicos.
- **El filtro automático no usa IA ni llaves**, así que no le cuesta nada a nadie y no puede filtrar secretos.
- **La prueba con IA cuesta, y la paga una sola licencia,** la del dueño, sobre aportes que ya pasaron los filtros gratuitos.
