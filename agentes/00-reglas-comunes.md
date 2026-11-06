# Reglas comunes a todos los subagentes

Estas reglas van en todas las fichas. Las hace cumplir código sin IA antes de ejecutar nada.

1. **La IA propone y una prueba sin IA comprueba.** Ningún subagente aprueba su propio trabajo: lo aprueba la herramienta de su ficha.
2. **Solo librerías permitidas.** Biblioteca estándar de Python y lo que diga `herramientas/permitidas.json` (pandas, numpy, plotly), con las versiones de `requirements.txt`. Nunca se instala nada ni se importa un paquete que no esté en la lista: un nombre inventado lo puede registrar un atacante (*slopsquatting*). Lo comprueba `herramientas/dependencias.py`.
3. **Función pura.** Sin red, sin escribir ni borrar archivos, sin ejecutar comandos, sin `eval`/`exec`/`compile`, sin `pickle` y sin importación dinámica. Lo comprueban `herramientas/seguridad.py` (reglas propias y Bandit) y la caja de arena (`herramientas/caja.py`), que corre el código sin red ni escritura.
4. **Nunca filas (R2).** Se trabaja con nombres, tipos y conteos. No se copian filas ni valores de columnas personales o de texto libre en las respuestas, ni se le piden al usuario.
5. **FAILFAST.** Los CSV se leen de forma estricta. Una comilla sin cerrar o una fila con campos de más o de menos detiene el trabajo con un error claro; nunca se lee a medias en silencio. Lo comprueba la batería `baterias/failfast/`.
6. **Solo lo que se recibe y sin invisibles literales.** El código lee únicamente las rutas que recibe en `datos`: nada de `.parent`, «..» ni rutas fijas. Los caracteres invisibles se escriben como escapes (`"\u200f"`): un control bidireccional pegado en el código es el patrón *Trojan Source*. Las dos cosas las bloquea la compuerta.
7. **Lo público no es de uso libre.** No se usan columnas personales (nombres de personas, documentos, datos bancarios, domicilios), cuasi-identificadoras ni de texto libre sin una justificación escrita (Ley 1581 de 2012).
8. **Las lecciones primero.** Antes de escribir, el subagente lee `baterias/lecciones.json`, los errores reales que ya pasaron, y no repite ninguno.
9. **Bitácora.** Al terminar, cada subagente deja `bitacora/<n>-<etapa>-<rol>.json` con `etapa`, `que_se_pidio`, `que_devolvio`, `como_se_probo`, `que_se_corrigio` y `sin_verificar`, en frases cortas y con cifras.
10. **No preguntar al usuario en medio del trabajo.** Lo que no se puede resolver se declara como pregunta o supuesto, con su valor por defecto y su impacto en la cifra.
11. **No inventar cifras.** Si no se corrió el código, no se dice el resultado. Nada se presenta como verificado sin una prueba.
