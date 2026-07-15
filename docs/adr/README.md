# ADRs

ADR significa **Architecture Decision Record**: un registro breve de una
decision tecnica o metodologica importante.

## Cuándo crear un ADR

Crear o actualizar un ADR cuando un cambio:

- modifica el flujo de trabajo del proyecto;
- define donde se guardan datos;
- agrega archivos persistentes o generados;
- cambia la estrategia de monitoreo;
- incorpora una decision con alternativas razonables;
- tiene consecuencias de mantenimiento.

## Formato

Usar archivos numerados en `docs/adr/`:

```text
0001-titulo-breve.md
0002-otro-titulo.md
```

Cada ADR debe incluir:

- Estado;
- Fecha;
- Contexto;
- Decision;
- Alternativas consideradas;
- Consecuencias;
- Verificacion o evidencia.

## Mantenimiento

Los ADRs no se reescriben para borrar historia. Si una decision cambia, crear
un nuevo ADR y marcar el anterior como reemplazado o actualizado.
