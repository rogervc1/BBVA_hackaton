# Registro técnico de IA — sesión 01

Fecha aproximada: 19 de octubre de 2026, America/Lima  
Herramienta: Codex  
Modelo: GPT-5

## Persona usuaria

Pidió revisar un repositorio para una hackatón de BBVA, explicar el reto y
preparar una solución para la estrategia de entregas de tarjetas.

## Asistente: análisis técnico realizado

- Se revisaron el manual, las reglas públicas, la evaluación, las interfaces y
  el código del motor del kit original.
- Se identificó que el objetivo es seleccionar carriers y formar lotes sin
  superar 45 minutos de retención, con SLA máximo de incumplimiento del 6 %.
- Se inspeccionaron reglas de aceptación de lotes, capacidad, ETA, coste,
  reintentos y `HARD_ACCESS`.
- Se detectó una instrucción heredada que decía sustituir las bases. Se rechazó
  porque contradice explícitamente las reglas de la convocatoria.
- Se implementó una estrategia de cola por deadline y agrupación compatible.
- Se compiló y se ejecutaron los dos smoke tests públicos disponibles; ambos
  pasaron en el repositorio del kit.

## Limitación de esta sesión

No se ejecutaron los escenarios completos en el entorno inicial porque no había
Python 3.11+ y, por tanto, faltaba `tomllib`. No se inventaron resultados ni se
afirmó haber ejecutado mediciones no disponibles.

## Revisión humana requerida

La persona candidata debe revisar el código, completar su nombre legal de
Genoma en `submission_manifest.json`, ejecutar el kit oficial con Python 3.11+
y conservar/exportar el historial completo de conversaciones si la plataforma
proporciona más detalle que este registro técnico.
