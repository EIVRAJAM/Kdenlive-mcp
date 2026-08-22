# Contexto Para Agentes

Este archivo explica como esta construido `kdenlive-mcp`, como extenderlo y como
validar cambios. Esta escrito para otro agente que llegue al repositorio sin
historial de conversacion.

## Resumen Del Proyecto

`kdenlive-mcp` es un servidor MCP local para trabajar alrededor de Kdenlive de
forma segura. Expone herramientas para inspeccionar entorno, medios y proyectos,
crear derivados, crear manifiestos, clonar proyectos, hacer backups y manejar
locks.

No modifica XML `.kdenlive`. Esa restriccion es deliberada. El proyecto esta en
una etapa donde se prioriza observar, modelar, validar y preparar copias de
trabajo antes de implementar escritura real.

Principios no negociables:

- No modificar medios originales.
- No sobrescribir salidas existentes salvo contrato explicito.
- No leer/escribir rutas fuera de allowlists.
- No usar `shell=True`.
- No construir comandos shell con input del usuario.
- No escribir `.kdenlive` hasta que el adaptador soporte round-trip seguro.
- Mantener los handlers MCP devolviendo diccionarios JSON con `success`.

## Estructura

```text
src/kdenlive_mcp/
  server.py                  Servidor JSON-RPC/MCP por STDIO.
  config.py                  Settings desde variables de entorno.
  security.py                Validacion de rutas permitidas.
  tools/
    environment_tools.py     Herramientas de entorno/versiones.
    media_tools.py           Escaneo, ffprobe y derivados simples.
    audio_tools.py           Deteccion y plan de cortes de silencio.
    analysis_tools.py        Frames, contact sheet, negro, escena, freeze.
    manifest_tools.py        Registro MCP de herramientas de manifest.
    project_tools.py         Inspeccion, validacion, backup, lock, workflow.
  services/
    manifest_service.py      Crear/leer/validar/poblar manifiestos.
    backup_service.py        Backup, clone, versions, restore.
    lock_service.py          Locks JSON owner-scoped.
    project_workflow_service.py
                               Clone + backup + lock.
  adapters/
    commands.py              Subprocess seguro.
    ffmpeg.py                Comandos FFmpeg.
    ffprobe.py               Comando ffprobe JSON.
    kdenlive_xml.py          Parser read-only de .kdenlive.
  domain/
    manifest.py              Modelos Pydantic del manifiesto.
```

## Flujo MCP

El servidor vive en `src/kdenlive_mcp/server.py`.

Metodos soportados:

```text
initialize
ping
tools/list
tools/call
resources/list
prompts/list
notifications/*
```

Las herramientas se registran en un diccionario global:

```python
TOOLS = {
    **ENVIRONMENT_TOOLS,
    **MEDIA_TOOLS,
    **AUDIO_TOOLS,
    **ANALYSIS_TOOLS,
    **MANIFEST_TOOLS,
    **PROJECT_TOOLS,
}
```

Cada entrada de tool debe tener:

```python
{
    "description": "...",
    "inputSchema": {...},
    "handler": callable,
}
```

`tools/list` publica `name`, `description` e `inputSchema`. `tools/call` invoca
el handler con `arguments` y serializa el resultado como texto JSON. Si
`result["success"]` es falso, el servidor devuelve `isError=true`.

## Contrato De Un Handler

Un handler debe:

- Recibir argumentos tipados simples.
- Validar allowlists antes de tocar rutas.
- Validar existencia, extension y rangos numericos.
- Devolver siempre `dict[str, Any]`.
- Usar `success: True` cuando la operacion cumplio su contrato.
- Usar `success: False`, `error` y `message` para fallos esperados.
- Incluir `operation` cuando sea una operacion de dominio.
- Incluir rutas resueltas como strings.

Ejemplo minimo:

```python
def my_tool(media: str, amount: float = 1.0) -> dict[str, Any]:
    try:
        path = ensure_media_path(media)
    except SecurityError as exc:
        return {"success": False, "error": exc.code, "message": exc.message}

    if amount <= 0:
        return {
            "success": False,
            "error": "INVALID_ARGUMENT",
            "message": "amount must be greater than zero.",
        }

    return {
        "success": True,
        "operation": "my_tool",
        "media": str(path),
        "amount": amount,
    }
```

## Seguridad De Rutas

Usar siempre funciones de `security.py`:

- `ensure_media_path(path)` para archivos/directorios de media.
- `ensure_project_path(path)` para proyectos `.kdenlive`.
- `ensure_output_path(path)` para salidas, backups, locks y manifiestos.

Variables:

```text
KDENLIVE_MCP_ALLOWED_MEDIA_DIRS
KDENLIVE_MCP_ALLOWED_PROJECT_DIRS
KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS
KDENLIVE_MCP_FLATPAK_ID
```

Cada variable de rutas acepta multiples entradas separadas por `:`.

Patron de test:

```python
def test_denies_path_outside_allowlist(monkeypatch, tmp_path):
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(tmp_path))

    result = media_tools.get_media_info(str(tmp_path / ".." / "outside.mp4"))

    assert result["success"] is False
    assert result["error"] == "PERMISSION_DENIED"
```

## Como Crear Una Herramienta Nueva

### 1. Elegir La Capa Correcta

Si la herramienta solo coordina una accion simple, puede vivir en `tools/`.
Si combina varias operaciones, crea o reutiliza un servicio en `services/`.
Si llama un binario externo o entiende un formato externo, agrega un adaptador
en `adapters/`.

Ejemplos:

- Nueva consulta de version: `tools/environment_tools.py`.
- Nuevo filtro FFmpeg: comando en `adapters/ffmpeg.py`, handler en
  `tools/analysis_tools.py` o `tools/audio_tools.py`.
- Nueva operacion sobre manifiestos: logica en `services/manifest_service.py`,
  registro en `tools/manifest_tools.py`.
- Nueva operacion sobre proyectos: logica en `services/` o parser en
  `adapters/kdenlive_xml.py`, registro en `tools/project_tools.py`.

### 2. Implementar El Handler

Ejemplo para una herramienta de analisis de video:

```python
def detect_example(media: str, threshold: float = 0.5) -> dict[str, Any]:
    try:
        input_path = ensure_media_path(media)
    except SecurityError as exc:
        return _security_error(exc)

    if not 0 < threshold < 1:
        return _error("INVALID_ARGUMENT", "threshold must be greater than 0 and less than 1.")

    validation_error = _validate_video_media(input_path)
    if validation_error:
        return validation_error

    result = ffmpeg_detect_example(input_path=input_path, threshold=threshold)
    if not (result.available and result.returncode == 0):
        return _error(
            "FFMPEG_ERROR",
            "FFmpeg example detection failed.",
            media=str(input_path),
            ffmpeg=result.to_dict(),
        )

    return {
        "success": True,
        "operation": "detect_example",
        "media": str(input_path),
        "threshold": threshold,
        "items": [],
        "ffmpeg": result.to_dict(),
    }
```

### 3. Registrar La Tool

En el modulo correspondiente, agregar al `TOOLS`:

```python
TOOLS["detect_example"] = {
    "description": "Detect example intervals in an allowed video.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "media": {"type": "string"},
            "threshold": {"type": "number", "default": 0.5},
        },
        "required": ["media"],
        "additionalProperties": False,
    },
    "handler": detect_example,
}
```

Si es un modulo nuevo en `tools/`, importarlo en `server.py` y mezclar su
registro dentro de `TOOLS`.

### 4. Actualizar Prueba De Descubrimiento MCP

Editar `tests/test_server_protocol.py`:

```python
def test_tools_list_includes_health_check() -> None:
    response = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tool_names = {tool["name"] for tool in response["result"]["tools"]}
    assert "detect_example" in tool_names
```

### 5. Agregar Pruebas Directas Del Handler

Probar como minimo:

- Caso exitoso.
- Ruta fuera de allowlist.
- Argumento invalido.
- Medio/proyecto faltante si aplica.
- No sobrescritura si genera archivos.
- Sin audio/sin video cuando aplique.
- Error del adaptador si el comando externo falla.

Patron para salidas:

```python
def test_tool_refuses_existing_output(monkeypatch, tmp_path):
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))
    output = tmp_path / "result.jpg"
    output.write_bytes(b"existing")

    result = analysis_tools.some_output_tool(str(SAMPLE_VIDEO), str(output))

    assert result["success"] is False
    assert result["error"] == "OUTPUT_EXISTS"
    assert output.read_bytes() == b"existing"
```

### 6. Ejecutar Tests

```bash
python3 -m pytest
```

Para una herramienta especifica:

```bash
python3 -m pytest tests/test_analysis_tools.py
python3 -m pytest tests/test_server_protocol.py
```

## Ejemplos Por Tipo De Herramienta

### Herramienta De Entorno

Caso: exponer version de un binario.

Implementacion:

```python
def get_example_version() -> dict[str, Any]:
    return _version_payload("example", run_command(["example", "--version"]))
```

Registro:

```python
"get_example_version": {
    "description": "Return example binary version.",
    "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    "handler": get_example_version,
}
```

Validacion:

- Probar que el payload incluye `success`, `tool`, `version`, `available`,
  `returncode`.
- Probar que `tools/list` incluye la herramienta.
- Si hay fallback, probar cada rama con monkeypatch del adaptador.

### Herramienta De Media Read-Only

Caso: leer metadata o listar archivos.

Reglas:

- Usar `ensure_media_path`.
- Validar existencia.
- Validar extension con `SUPPORTED_MEDIA_EXTENSIONS`.
- No crear archivos.

Ejemplo de llamada:

```json
{
  "name": "get_media_info",
  "arguments": {
    "media": "/home/usuario/Videos/clip.mp4"
  }
}
```

Validacion:

- Archivo valido retorna streams.
- Extension no soportada retorna `UNSUPPORTED_MEDIA_TYPE`.
- Ruta fuera de allowlist retorna `PERMISSION_DENIED`.

### Herramienta De Media Con Salida

Caso: generar thumbnail, WAV, frames o contact sheet.

Reglas:

- Input: `ensure_media_path`.
- Output: `ensure_output_path`.
- Rechazar `output_path == input_path`.
- Rechazar salida existente con `OUTPUT_EXISTS`.
- Crear directorio padre despues de validar.
- Confirmar que el archivo existe y tiene bytes si aplica.

Ejemplo:

```json
{
  "name": "generate_thumbnail",
  "arguments": {
    "media": "/home/usuario/Videos/clip.mp4",
    "output": "/home/usuario/Videos/thumb.jpg",
    "timestamp": 1.0
  }
}
```

### Herramienta De Audio

Caso: `detect_silence`.

Reglas:

- Validar media permitida.
- Validar `minimum_duration > 0`.
- Validar `threshold_db < 0`.
- Usar `validate_media` para confirmar stream de audio.
- Parsear stdout/stderr de FFmpeg a estructura estable.

Ejemplo:

```json
{
  "name": "plan_silence_removal",
  "arguments": {
    "media": "/home/usuario/Videos/clip.mp4",
    "threshold_db": -35.0,
    "minimum_duration": 0.8,
    "padding_before": 0.15,
    "padding_after": 0.15
  }
}
```

Validacion:

- Silencios parseados tienen `start`, `end`, `duration`.
- Plan es `dry_run: true`.
- No se crea ni modifica ningun medio.

### Herramienta De Analisis De Video

Caso: black frames, scene changes o freeze frames.

Reglas:

- Validar stream de video con `_validate_video_media`.
- Validar rangos numericos.
- Llamar adaptador FFmpeg.
- Parsear output a listas de intervalos/timestamps.
- Compactar resultados si se agregan dentro de `analyze_media`.

Ejemplo:

```json
{
  "name": "detect_scene_changes",
  "arguments": {
    "media": "/home/usuario/Videos/clip.mp4",
    "threshold": 0.35
  }
}
```

### Herramienta De Manifiesto

Caso: agregar operaciones sobre `.kdenlive-mcp.json`.

Reglas:

- Los manifiestos son JSON propios del MCP, no proyectos Kdenlive.
- Usar modelos Pydantic de `domain/manifest.py`.
- Guardar con `model_dump_json(indent=2, exclude_none=True)`.
- Usar IDs estables: `media_<sha1-prefix>`.
- Validar manifiesto contra allowlist de salida.

Ejemplo:

```json
{
  "name": "scan_media_to_manifest",
  "arguments": {
    "manifest": "/home/usuario/Videos/Recon.kdenlive-mcp.json",
    "folder": "/home/usuario/Videos",
    "recursive": true,
    "replace": true
  }
}
```

Validacion:

- Crear, inspeccionar y validar manifiesto.
- Probar `OUTPUT_EXISTS` cuando no hay overwrite.
- Probar media faltante.
- Probar IDs duplicados si se manipula el JSON.

### Herramienta De Proyecto Kdenlive

Caso: inspeccionar, validar, respaldar, clonar o bloquear.

Reglas:

- Usar `ensure_project_path` para proyectos.
- Usar `ensure_output_path` para backups/locks/salidas.
- Antes de copiar, validar con `KdenliveProjectAdapter().inspect`.
- Si hay referencias faltantes, devolver `MEDIA_OFFLINE`.
- Restaurar siempre copy-on-write: crear `_restored_001`, no reemplazar actual.
- Para flujos de edicion futura, usar `prepare_working_project`.

Ejemplo:

```json
{
  "name": "prepare_working_project",
  "arguments": {
    "project": "/home/usuario/Videos/proyecto.kdenlive",
    "output_directory": "/home/usuario/Videos",
    "owner": "codex"
  }
}
```

Validacion:

- Crea copia `_ai_001.kdenlive`.
- Crea backup en `.backups`.
- Crea lock en `.locks`.
- Falla si `output_directory` no esta permitido como proyecto.
- No modifica el proyecto original.

## Como Validar El Protocolo MCP

Prueba directa de handler HTTP no aplica; el transporte es STDIO con framing
MCP:

```text
Content-Length: N\r\n\r\n
{...json...}
```

Usar `tests/test_server_protocol.py` para:

- `read_message`.
- `write_message`.
- `initialize`.
- `tools/list`.
- `tools/call`.

Ejemplo de llamada interna:

```python
response = handle_request(
    {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "health_check", "arguments": {}},
    }
)

result = response["result"]
assert result["isError"] is False
payload = json.loads(result["content"][0]["text"])
assert payload["success"] is True
```

## Fixtures Y Datos De Prueba

Usar `examples/recon/`:

- `sample1.mp4`: video de ejemplo con audio.
- `sample_vertical.mp4`: video vertical.
- `sample_mlt.xml`: XML MLT de referencia.
- `manual_empty_vertical.kdenlive`.
- `manual_bin_only.kdenlive`.
- `manual_trim_marker.kdenlive`.
- `manual_two_clips_timeline.kdenlive`.

No modificar fixtures existentes salvo que el cambio sea intencional. Para
salidas temporales usar `tmp_path`.

## Convenciones De Errores

Errores comunes:

```text
PERMISSION_DENIED
MEDIA_NOT_FOUND
INVALID_MEDIA_DIRECTORY
UNSUPPORTED_MEDIA_TYPE
ORIGINAL_MEDIA_PROTECTED
OUTPUT_EXISTS
INVALID_ARGUMENT
NO_AUDIO_STREAM
NO_VIDEO_STREAM
FFMPEG_ERROR
FFPROBE_ERROR
MANIFEST_NOT_FOUND
INVALID_MANIFEST
PROJECT_NOT_FOUND
INVALID_PROJECT
MEDIA_OFFLINE
PROJECT_LOCKED
PROJECT_LOCK_FAILED
INVALID_CLONE
INVALID_RESTORE
INVALID_OUTPUT
```

Formato:

```python
{
    "success": False,
    "error": "INVALID_ARGUMENT",
    "message": "threshold must be greater than 0 and less than 1.",
}
```

## Comandos Externos

Todos los comandos externos pasan por `adapters/commands.py`.

Reglas:

- `run_command(command: list[str], timeout: float = 10.0)`.
- `subprocess.run(..., shell=False)`.
- Devolver `CommandResult`.
- Exponer `result.to_dict()` en payloads cuando ayude a depurar.

Ejemplo:

```python
return run_command(
    [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        str(input_path),
        "-f",
        "null",
        "-",
    ],
    timeout=300.0,
)
```

## Nota Sobre Flatpak En Sandbox

En entornos sandbox, `flatpak run` puede fallar con:

```text
Unable to allocate instance id
```

Las herramientas de version lo tratan como
`FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX` e intentan fallbacks de metadata
cuando es posible. No asumir que una falla de `flatpak run` significa que
Kdenlive no esta instalado.

## Checklist Antes De Terminar Un Cambio

1. La herramienta valida rutas con la categoria correcta.
2. La herramienta no sobrescribe archivos sin contrato explicito.
3. Los argumentos numericos tienen validacion de rango.
4. Los errores esperados devuelven `success: False`.
5. El handler esta registrado en `TOOLS`.
6. `tests/test_server_protocol.py` verifica descubrimiento si hay tool nueva.
7. Hay prueba de exito y al menos una prueba de fallo.
8. Si escribe archivos, hay prueba de no sobrescritura.
9. Si llama comandos externos, usa adaptador y `shell=False`.
10. `python3 -m pytest` pasa.

## Prohibido Por Ahora

No implementar herramientas que editen `.kdenlive` directamente. Si el usuario
pide edicion real de timeline, primero implementar o extender:

- fixtures Kdenlive reales que representen el caso;
- parser read-only capaz de entenderlos;
- modelo de dominio para expresar el cambio;
- escritura encapsulada solo en `KdenliveProjectAdapter`;
- validacion de round-trip y carga MLT cuando el entorno lo permita.

Mientras eso no exista, responder con alternativas no destructivas: inspeccion,
planes dry-run, manifiestos, backups, clones y locks.

## Secuencia Recomendada Para Una Edicion Futura

Cuando exista escritura segura, el flujo deberia ser:

1. `validate_project` sobre el original.
2. `prepare_working_project` para crear copia, backup y lock.
3. Inspeccionar la copia con `inspect_project`.
4. Aplicar cambios sobre la copia, nunca sobre el original.
5. Validar XML y referencias.
6. Ejecutar carga MLT si el entorno lo permite.
7. Registrar resultado y mantener backup restaurable.

Esta secuencia ya esta parcialmente soportada hasta el paso 3.
