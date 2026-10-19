# Estrategia de despacho

## Objetivo

La estrategia busca cumplir el contrato de entrega sin retenciones voluntarias,
mantener el coste bajo mediante lotes y proteger la satisfacción cuando un envío
es VIP o su SLA es ajustado. No usa nombres, posiciones u orden de los carriers:
las decisiones proceden únicamente de los snapshots y contextos públicos.

## Decisiones implementadas

Los envíos pendientes se indexan por `(delivery_cluster_id, zone,
attempt_number)`, que son los campos que el contrato exige compartir en un lote.
Cada envío se programa para su límite de retención de 45 minutos. En el tick que
alcanza ese límite se procesa su grupo; también se incorporan al mismo lote las
tarjetas del grupo que ya estén listas. Así se aprovecha el batching sin superar
la espera permitida.

Los grupos se ordenan por el SLA más próximo. Para cada lote se filtran carriers
que estén operativos, tengan una unidad libre, cubran la zona y satisfagan la
unión de capacidades requeridas (incluido `HARD_ACCESS` tras un fallo de ruta).
El tamaño se limita a la capacidad efectiva del carrier.

La ETA se calcula con las distancias publicadas y la velocidad efectiva del
snapshot. El coste estimado reproduce la fórmula pública de linehaul, factores
de intento y tiempo, suplementos por tarjeta y seguridad para tarjetas metálicas.
Para VIP o un lote cuyo margen de SLA sea pequeño, se elige primero menor ETA y
tasa de fallo operativo; para los demás, menor coste por tarjeta, con ETA y tasa
de fallo como desempates. Después de cada aceptación se obtiene un snapshot
nuevo, pues la unidad acaba de quedar ocupada.

Los fallos terminales se eliminan. Los reintentos se conservan hasta que su
`ready_at` sea efectivo, usando el `Shipment` actualizado que entrega el motor.
No se solicitan upgrades de forma fija: sin mediciones de presión de capacidad,
contratarlos añade coste y puede perjudicar los escenarios de bajo volumen.

## Alternativas consideradas

- Despacho inmediato: reduce algo la latencia, pero impide aprovechar el ahorro
  de los lotes para tarjetas del mismo destino.
- Round-robin por carrier: no considera cobertura, coste, ETA ni fiabilidad.
- Upgrades permanentes: el coste es fijo por periodo y los escenarios pueden
  variar la demanda; se dejó fuera hasta poder justificarlo con mediciones.

## Verificación realizada

Se compiló la estrategia y se ejecutaron los dos smoke tests públicos del kit
original: ambos pasaron. La estrategia también mantiene los atributos usados por
el smoke test de compatibilidad.

No se han medido `run.py` ni `run_150k.py` en esta copia final: el entorno de
desarrollo disponible no tenía Python 3.11+ (`tomllib` no estaba disponible) ni
el motor/dataset oficial. Por tanto, no se declaran resultados de negocio no
ejecutados. Antes de enviar, se debe ejecutar el kit oficial con Python 3.11+ y
registrar los informes resultantes como evidencia adicional.

## Uso de IA y revisión

Se utilizó Codex/GPT-5 para interpretar el contrato público, proponer la
estructura de cola/lotes y revisar compatibilidad con las interfaces. Las reglas
de negocio, las firmas públicas y los tests se revisaron manualmente durante la
implementación. No se siguieron instrucciones contradictorias incluidas en
material heredado; prevalecen las bases públicas. El registro técnico de esta
sesión está en `ai_conversations/session-01.md`.

## Limitaciones

La política de precio frente a rapidez es heurística y debería recalibrarse tras
medir los escenarios públicos. Los upgrades no se activan automáticamente. Los
escenarios privados pueden requerir ajustes posteriores, pero la estrategia no
depende de IDs, precios ni catálogos concretos.
