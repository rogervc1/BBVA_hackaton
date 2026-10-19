# BBVA Hackathon 2026 — LOG-8092

Entrega para la prueba técnica de optimización de entregas de tarjetas.

La versión evaluable está en `submission/candidate_strategy.py`. La carpeta
`submission/` contiene la explicación, el manifiesto y el registro de uso de IA.

## Validación local

El kit exige Python 3.11 o superior:

```text
python -m unittest discover -s tests -v
python run.py
python run_150k.py
```

Los escenarios completos deben ejecutarse con el kit oficial, que incluye el
motor y los datasets públicos.
