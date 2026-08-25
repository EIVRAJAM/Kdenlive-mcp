# kdenlive-mcp

Servidor MCP local para automatizar tareas seguras alrededor de Kdenlive:
inspeccionar medios, analizar audio/video, construir manifiestos de trabajo,
leer proyectos `.kdenlive`, preparar copias de trabajo y protegerlas con locks.

El objetivo del proyecto no es reemplazar Kdenlive ni modificar su codigo
fuente. El objetivo es dar a un agente de IA una capa local, controlada y
auditable para razonar sobre material audiovisual y proyectos Kdenlive sin
destruir archivos originales.

Estado actual: servidor MCP por STDIO, herramientas de entorno, herramientas de
media, analisis de audio/video con FFmpeg, manifiestos JSON propios del MCP,
inspeccion/validacion de proyectos Kdenlive en modo solo lectura, backups,
clonado copy-on-write, listado/restauracion de versiones y locks por proyecto.

Limite importante: el proyecto todavia no escribe ni muta XML `.kdenlive`.

## Que Problema Resuelve

Kdenlive guarda sus proyectos como XML basado en MLT. Ese formato contiene
productores, cadenas, playlists, tractors, secuencias, propiedades propias de
Kdenlive, referencias a medios, marcadores, guias, tracks y relaciones internas
que no conviene editar a ciegas.

Este servidor crea una frontera segura:

- El agente puede descubrir el entorno local: Python, FFmpeg, ffprobe,
  Flatpak, Kdenlive y MLT.
- El agente puede inspeccionar medios permitidos con `ffprobe`.
- El agente puede generar derivados no destructivos, como thumbnails, WAV,
  frames y contact sheets.
- El agente puede detectar silencios, negros, congelados y cambios de escena.
- El agente puede crear manifiestos JSON con IDs estables antes de escribir
  proyectos Kdenlive reales.
- El agente puede inspeccionar proyectos `.kdenlive` existentes sin tocarlos.
- El agente puede preparar una copia de trabajo `_ai_001.kdenlive`, crear un
  backup previo y bloquear la copia para evitar ediciones concurrentes.

La regla de diseno central es simple: primero observar y copiar; escribir XML
de Kdenlive solo cuando el adaptador pueda preservar y validar el formato real.

## Arquitectura

Flujo actual:

```text
Codex / agente MCP
  -> servidor JSON-RPC 2.0 por STDIO
    -> herramientas de entorno
    -> herramientas de media
    -> herramientas de audio
    -> herramientas de analisis de video
    -> herramientas de manifiesto
    -> herramientas de proyecto
      -> servicios de manifest/backup/lock/workflow
      -> adaptadores ffmpeg/ffprobe/Kdenlive XML
```

Capas principales:

- `src/kdenlive_mcp/server.py`: transporte MCP compatible con JSON-RPC 2.0 y
  framing `Content-Length`.
- `src/kdenlive_mcp/tools/`: definiciones publicas MCP. Cada herramienta tiene
  `name`, `description`, `inputSchema` y `handler`.
- `src/kdenlive_mcp/services/`: coordinacion de operaciones con estado:
  manifiestos, backups, locks y preparacion de proyectos.
- `src/kdenlive_mcp/adapters/`: integracion con procesos externos y formatos:
  `ffmpeg`, `ffprobe`, comandos y parser XML de Kdenlive.
- `src/kdenlive_mcp/domain/`: modelos de dominio propios, actualmente el
  manifiesto JSON.
- `src/kdenlive_mcp/security.py`: resolucion de rutas y allowlists.
- `examples/recon/`: fixtures reales de Kdenlive 26.04.3 y medios de prueba.
- `tests/`: pruebas unitarias e integracion local para herramientas, servicios,
  protocolo MCP y parser Kdenlive.

## Seguridad

El servidor esta pensado para ejecutarse localmente y con acceso explicito a
directorios permitidos. Ninguna herramienta debe aceptar rutas arbitrarias sin
pasar por la capa de seguridad.

Variables de entorno:

```bash
export KDENLIVE_MCP_ALLOWED_MEDIA_DIRS=/home/usuario/Videos
export KDENLIVE_MCP_ALLOWED_PROJECT_DIRS=/home/usuario/Videos
export KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS=/home/usuario/Videos:/tmp
export KDENLIVE_MCP_FLATPAK_ID=org.kde.kdenlive
```

Categorias:

- `allowed_media_directories`: lectura de medios.
- `allowed_project_directories`: lectura de proyectos `.kdenlive` y ubicaciones
  consideradas validas para proyectos.
- `allowed_output_directories`: escritura de derivados, manifiestos, backups y
  locks.

Las rutas se expanden y resuelven antes de validarse. Intentos como
`../outside.mp4` quedan fuera del root permitido y devuelven:

```json
{
  "success": false,
  "error": "PERMISSION_DENIED"
}
```

Las herramientas de salida no deben sobrescribir archivos existentes salvo que
el contrato lo permita explicitamente, como `create_manifest(...,
overwrite=true)`.

## Instalacion

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

Requisitos principales:

- Python 3.11 o superior.
- `pydantic>=2`.
- `pytest>=8` para desarrollo.
- FFmpeg y ffprobe disponibles en `PATH` para herramientas de media.
- Kdenlive/MLT opcional para inspeccion de versiones y validacion MLT.

El paquete oficial Python `mcp` no es requisito actual. Este repositorio incluye
un servidor JSON-RPC compatible suficiente para la fase actual y migrable al SDK
oficial mas adelante.

## Ejecucion

Servidor directo:

```bash
python3 src/kdenlive_mcp/server.py
```

Comando instalado en modo editable:

```bash
kdenlive-mcp
```

Configuracion MCP para Codex:

```toml
[mcp_servers.kdenlive]
command = "python3"
args = ["/data/PROYECTOS/kdenlive-mcp/src/kdenlive_mcp/server.py"]
```

## Herramientas Disponibles

Entorno:

- `health_check`: estado basico del servidor.
- `get_environment`: Python, plataforma, binarios y allowlists.
- `get_kdenlive_version`: version de Kdenlive, prefiriendo Flatpak.
- `get_ffmpeg_version`: version de FFmpeg.
- `get_ffprobe_version`: version de ffprobe.
- `get_mlt_version`: version de MLT/melt.

Media:

- `scan_media`: escanea un directorio permitido y opcionalmente usa ffprobe.
- `list_media`: lista medios sin ffprobe.
- `get_media_info`: metadata de un medio.
- `validate_media`: verifica extension, existencia y streams audio/video.
- `generate_thumbnail`: genera una imagen desde un timestamp.
- `extract_audio`: extrae WAV PCM 48 kHz.

Audio y analisis:

- `detect_silence`: detecta intervalos de silencio con `silencedetect`.
- `plan_silence_removal`: produce un plan dry-run de cortes por silencio.
- `extract_frames`: extrae frames periodicos.
- `generate_contact_sheet`: genera una hoja de contacto.
- `detect_black_frames`: detecta intervalos negros.
- `detect_scene_changes`: detecta timestamps de cambios de escena.
- `detect_freeze_frames`: detecta intervalos congelados.
- `analyze_media`: ejecuta analisis seleccionados y resume resultados.
- `analyze_media_folder`: analiza un lote limitado de medios en una carpeta permitida.
- `plan_rough_cut`: crea un plan dry-run de segmentos para un rough cut.
- `save_rough_cut_plan`: guarda un plan dry-run como JSON.
- `inspect_rough_cut_plan`: carga y valida un plan dry-run guardado.
- `create_rough_cut_plan_file`: crea y guarda un plan dry-run en una llamada.

Manifiestos:

- `create_manifest`: crea un JSON `.kdenlive-mcp.json`.
- `inspect_manifest`: carga y devuelve el manifiesto.
- `validate_manifest`: valida estructura, referencias faltantes e IDs duplicados.
- `scan_media_to_manifest`: escanea medios y los guarda con IDs estables.

Proyectos:

- `inspect_project`: lee un `.kdenlive` y devuelve resumen estructurado.
- `validate_project`: valida XML, referencias y opcionalmente carga MLT.
- `backup_project`: copia timestamped de un proyecto validado.
- `clone_project`: crea una copia de trabajo `_ai_001.kdenlive`.
- `list_project_versions`: lista originales, copias y backups relacionados.
- `restore_project_version`: copia una version a `_restored_001.kdenlive`.
- `get_project_lock`: consulta lock.
- `lock_project`: crea lock por owner.
- `unlock_project`: libera lock.
- `prepare_working_project`: clona, respalda y bloquea una copia de trabajo.

Todas las herramientas devuelven JSON estructurado como texto dentro de
`tools/call`. El servidor marca `isError=true` cuando `success` es falso.

## Ejemplos

Escanear medios:

```json
{
  "name": "scan_media",
  "arguments": {
    "folder": "/home/usuario/Videos/vlog",
    "recursive": true,
    "probe": true
  }
}
```

Crear manifiesto y poblarlo:

```json
{
  "name": "create_manifest",
  "arguments": {
    "name": "Vlog Santa Marta",
    "output_directory": "/home/usuario/Videos/vlog",
    "description": "Inventario inicial"
  }
}
```

```json
{
  "name": "scan_media_to_manifest",
  "arguments": {
    "manifest": "/home/usuario/Videos/vlog/Vlog_Santa_Marta.kdenlive-mcp.json",
    "folder": "/home/usuario/Videos/vlog",
    "recursive": true,
    "replace": true
  }
}
```

Preparar proyecto antes de cualquier edicion futura:

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

Esto crea una copia de trabajo, un backup previo y un lock. La copia es la ruta
que debe usarse para cualquier operacion posterior.

## Validacion Y Pruebas

Ejecutar toda la suite:

```bash
python3 -m pytest
```

Pruebas por area:

```bash
python3 -m pytest tests/test_server_protocol.py
python3 -m pytest tests/test_media_tools.py
python3 -m pytest tests/test_analysis_tools.py
python3 -m pytest tests/test_manifest_tools.py
python3 -m pytest tests/test_kdenlive_project_adapter.py
python3 -m pytest tests/test_backup_service.py
python3 -m pytest tests/test_lock_service.py
python3 -m pytest tests/test_project_workflow_service.py
```

La suite usa fixtures de `examples/recon/` y `tmp_path` para salidas
temporales. Muchas pruebas configuran allowlists con `monkeypatch.setenv` para
probar tanto el caso permitido como el denegado.

## Documentacion Relacionada

- `docs/ARCHITECTURE.md`: arquitectura y fronteras.
- `docs/MCP_TOOLS.md`: contratos detallados de herramientas MCP.
- `docs/SECURITY.md`: modelo de seguridad y reglas de rutas.
- `docs/ENVIRONMENT.md`: reconocimiento del entorno local.
- `docs/KDENLIVE_PROJECT_FORMAT.md`: notas sobre el formato Kdenlive/MLT.
- `context.md`: guia para que otro agente entienda como extender y validar el
  proyecto.

## Roadmap Tecnico

Trabajo seguro antes de escribir `.kdenlive`:

1. Ampliar fixtures reales con mas trims, gaps, transiciones, efectos, proxies,
   multiples secuencias y audio/video desacoplado.
2. Fortalecer el parser read-only para cubrir esos casos.
3. Definir un modelo de dominio de timeline que no filtre XML al resto del
   sistema.
4. Implementar escritura solo en el adaptador Kdenlive, preservando propiedades
   desconocidas.
5. Validar cada escritura con parseo, referencias, carga MLT cuando sea posible
   y round-trip contra fixtures.

Hasta completar esos pasos, las herramientas deben seguir siendo
no destructivas.
