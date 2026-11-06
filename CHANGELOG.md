# Registro de cambios

Cada aporte aceptado queda aquí, con el usuario de GitHub de quien lo propuso (si aceptó aparecer).

## v1 · 6 de noviembre de 2026 · semilla

- Pipeline de cinco etapas con once subagentes, herramientas sin IA, directrices, baterías (seguridad, privacidad, FAILFAST y lecciones), dos corridas selladas y evidencia de los experimentos.
- Primeras lecciones de la revisión ciega de seguridad (L15–L20): reglas en caja de arena, lectura estricta de CSV, mensajes saneados, URLs bloqueadas, enlaces solo locales y ejecución desde la fuente.

## v1.1 · 6 de noviembre de 2026 · prueba de la guía de aportes

- `APORTAR-CON-TU-AGENTE.md`, probada con tres participantes simulados (cerca de 110.000 tokens por aporte, 11 minutos).
- Lo que encontraron se integró: la familia exec/spawn de `os` y sus alias, el CSV con separador distinto de la coma (FAILFAST) y once arreglos de la guía y del filtro (orden de los pasos, `upstream/main`, filtro sin efectos sobre el repositorio, ids de lección sin choques).
- Corrida de cinco etapas con capa limpia, aprobada en las cinco.

## v1.2 · 6 de noviembre de 2026 · blindaje del pipeline

- `herramientas/blindaje.py`: 15 ataques al pipeline, con un control positivo. Línea base: resistía 5 de 14; ahora resiste 15 de 15.
- Caja de arena: sin lectura de la carpeta personal, entorno mínimo sin secretos y tope de memoria por huella física.
- Compuerta: 8 evasiones conocidas cerradas sin romper el código legítimo.
- Inyección de instrucciones: cuarentena en el perfil y la limpieza, rechazo en el filtro de aportes, batería `baterias/inyeccion/` y regla común 7.
- Integridad: manifiesto sellado antes de cualquier agente y comprobado al final; las baterías solo crecen.
- Cadena de suministro: dependencias con huella (`--require-hashes`) y acciones de GitHub fijadas a su commit.
- Auditoría de independencia: 16 agentes en 4 corridas, 0 accesos prohibidos. Lecciones L25 a L33.

## Aportes del grupo

_Todavía ninguno._
