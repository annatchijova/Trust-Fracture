[English](README.md) · Español · [Arquitectura técnica](docs/ARCHITECTURE.md)

# Trust Fracture

Cuando un agente de IA lee contenido externo y puede invocar operaciones privilegiadas, quien investiga necesita saber por dónde podría influir ese contenido, qué se ejecutó y qué política aplica.

Trust Fracture es una herramienta de línea de comandos para investigar esas preguntas. Cargá una descripción del sistema y registrá las observaciones de traza que tengas. La herramienta guarda agentes, herramientas, fuentes, operaciones, permisos y políticas en un grafo de Relate. Podés explorar rutas con un límite de saltos, revisar la autoridad del actor y generar un hallazgo sellado con su evidencia y sus límites.

**En construcción.** El grafo, la CLI de investigación y el sellado de hallazgos ya se pueden usar. El corpus incluye seis controles negativos. El resto del corpus, el análisis de controles y la interfaz visual siguen en el plan de trabajo. [Plan de construcción](docs/LEVELS.md)

## Qué dice un hallazgo

| Resultado | Evidencia que encontró el motor |
| --- | --- |
| `POTENTIAL_PATH` | Una ruta estructural con respaldo de trazas parcial o ausente. |
| `OBSERVED_FLOW` | Las trazas identifican explícitamente cada relación observada de la ruta. |
| `VERIFIED_POLICY_VIOLATION` | Reservado para casos con evidencia explícita de ejecución e infracción de una política aplicable. El motor actual informa el flujo observado y las brechas de autoridad que encuentra. |
| `INSUFFICIENT_EVIDENCE` | La búsqueda acotada no encontró una ruta para evaluar. |

Las reglas se ejecutan sin un modelo de lenguaje. El JSON del hallazgo incluye la ruta seleccionada, los identificadores de las trazas que la respaldan, los motivos y las limitaciones. Un verificador independiente, escrito con la biblioteca estándar de Python, comprueba el SHA-256 del contenido canonizado. El digest cubre la integridad del contenido sellado y la procedencia de la traza depende de los registros de origen. [Modelo de evidencia](docs/EPISTEMIC_MODEL.md)

## Probá la CLI

Desde la raíz del repositorio, usá Python 3.12 o posterior en un entorno virtual. El ejemplo carga un catálogo sintético en una base temporal nueva y sella una ruta para la que no hay ejecución registrada.

```bash
python -m pip install -e '.[dev]'
workdir=$(mktemp -d)
trust-fracture load tests/fixtures/negative_controls.json --database "$workdir/catalog.rl"

trust-fracture seal-finding --database "$workdir/catalog.rl" \
  --source structural-only-source --target structural-only-target \
  --actor structural-only-actor --operation structural-only-operation \
  --finding-id catalog-route --out "$workdir/finding.json"

python scripts/verify_finding.py "$workdir/finding.json"
```

La CLI devuelve `POTENTIAL_PATH` y el verificador confirma que el digest coincide. Para ejecutar los seis controles con la CLI y el verificador, corré `python -m pytest -q tests/test_negative_controls.py`. [Casos de control](tests/test_negative_controls.py)

## Documentación técnica

- La [arquitectura](docs/ARCHITECTURE.md) recorre el flujo desde la carga hasta los hallazgos.
- El [modelo de grafo](docs/GRAPH_MODEL.md) define los tipos de nodos, sus relaciones y su procedencia.
- El [modelo de amenazas](docs/THREAT_MODEL.md) define los supuestos y las fronteras de confianza.
- El [registro de decisión sobre Relate](docs/decisions/ADR-001-language-selection.md) explica la elección del almacenamiento.

## Licencia

Trust Fracture se distribuye bajo la [Licencia Apache 2.0](LICENSE).
