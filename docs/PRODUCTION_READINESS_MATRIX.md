# Production Readiness Matrix

Matrix de cumplimiento del contrato de producción
(`docs/PRODUCTION_CONTRACT.md`) para el target
`production-local-agent-single-user`.

- Fecha de revisión: 2026-09-01
- Fuentes: `docs/PRODUCTION_CONTRACT.md`, `docs/RELEASE_EVIDENCE.md`,
  `docs/RELEASE_CHECKLIST.md`, `docs/UNDO_VERSIONING.md`, `docs/SCHEMAS.md`,
  `README.md`, `tests/`, `src/kdenlive_mcp/server.py`, `scripts/dev_check.sh`.
- Clasificación por requisito MUST:

```text
DONE     implementado, probado y con evidencia registrada
PARTIAL  existe, pero incompleto o no reproducible en el entorno actual
MISSING  no existe evidencia ni implementación
BLOCKED  bloqueado por un principio no negociable o rediseño pendiente
```

## Requisitos MUST

| Requisito | Estado | Evidencia en código/tests/docs | Riesgo residual | Siguiente acción concreta |
|---|---|---|---|---|
| MCP STDIO protocol stability | DONE | `src/kdenlive_mcp/server.py` (framing `Content-Length`, `initialize`, `ping`, `tools/list`, `tools/call`, JSON-RPC errors); `tests/test_server_protocol.py` | No hay prueba de conformidad contra un cliente MCP oficial | Smoke test de descubrimiento con un cliente MCP real por STDIO |
| Security allowlists and path traversal rejection | DONE | `src/kdenlive_mcp/security.py` (`ensure_media/project/output_path`); `tests/test_server_protocol.py` (PERMISSION_DENIED, non-object args); `tests/test_media_tools.py` (OUTPUT_EXISTS) | Roots de allowlist amplios y symlinks no cubiertos por test | Test de resolución de symlink y traversal con `..` contra cada categoría |
| Stable tool response/error shapes | DONE | `server.py` `_validate_tool_arguments_schema`, `_invalid_tool_response`, inyección de `operation`; `tests/test_tool_response_contract.py` | Array `warnings` aún inconsistente entre tools (SHOULD) | Unificar campo `warnings` a nivel de contrato |
| Media scan and ffprobe validation | DONE | `tools/media_tools.py`, `adapters/ffprobe.py`; `tests/test_media_tools.py` | VFR y layouts inusuales no cubiertos | Ampliar fixtures con VFR y streams poco comunes |
| Kdenlive project inspect/validate | DONE | `adapters/kdenlive_xml.py`, `tools/project_tools.py`; `tests/test_kdenlive_project_adapter.py`, `test_kdenlive_project_fixtures.py` | Formato Kdenlive puede cambiar entre versiones | Re-verificar con la versión instalada en cada release |
| Template-based .kdenlive draft generation | DONE | `services/timeline_service.py` `export_timeline_to_kdenlive_template`; `tests/test_timeline_service.py` (export tests); RELEASE_EVIDENCE 2026-08-25/26 | Sólo un par plantilla/perfil (vertical HD) validado | Ampliar plantillas a más perfiles (SHOULD) |
| Internal TimelineDocument validation | DONE | `domain/timeline.py` (validators); `tests/test_timeline_service.py` | Ninguno mayor | — |
| Copy-on-write project versioning | DONE | `services/backup_service.py`, `docs/UNDO_VERSIONING.md`; `tests/test_backup_service.py` | Restore probado a nivel unitario, no en workflow completo | Test e2e de restore en flujo de edición real |
| Project lock handling | DONE | `services/lock_service.py`, `services/project_workflow_service.py`; `tests/test_lock_service.py`, `test_project_workflow_service.py` | Conflicto de lock no ejercitado end-to-end (multi-proceso) | Test MCP de `PROJECT_LOCKED` sobre proyecto bloqueado |
| Rough-cut workflow from folder to .kdenlive | DONE | `services/vlog_workflow_service.py`, `tools/rough_cut_tools.py`; `tests/test_vlog_workflow_service.py` | Depende de la plantilla fixture | — |
| Automated end-to-end workflow test | DONE | `tests/test_vlog_workflow_service.py`; `scripts/dev_check.sh` (`KDENLIVE_MCP_RUN_FIXTURE_WORKFLOW`); RELEASE_EVIDENCE (20 runs) | Gate opt-in por env, no CI permanente | Documentar ejecución en CI/release reproducible |
| Original media checksum test | DONE | `scripts/fixture_reliability_check.py` (sha256); RELEASE_EVIDENCE `media_checksums_unchanged: true` | Evidencia puntual (2026-08-25), no por-release | Re-ejecutar por release y registrar checksum |
| Generated .kdenlive inspect validation | DONE | RELEASE_EVIDENCE (export validation, clip/marker/guide counts); `tests/test_timeline_service.py` | — | — |
| Optional workflow-level MLT load validation | PARTIAL | `tools/project_tools.py` `check_mlt`; `scripts/dev_check.sh` `KDENLIVE_MCP_RUN_MLT_CHECK`; tests con `melt` mockeado; evidencia real única 2026-08-25 (`MLT load check: valid true`) | La carga real por melt sólo se registró una vez en una máquina; en sandbox degrada a `unavailable` y no es reproducible | Re-ejecutar `KDENLIVE_MCP_RUN_MLT_CHECK=1 scripts/dev_check.sh` con proyecto real en la máquina objetivo y registrar por release |
| Partial-output cleanup or explicit partial-output reporting | DONE | `services/vlog_workflow_service.py` `_failed_step`/`partial_outputs`; `scripts/fixture_reliability_check.py` (assert partial_outputs) | Sólo reporting, sin cleanup (permitido por el contrato "or") | — |
| Persistent structured logging | DONE | `src/kdenlive_mcp/logging.py` (JSONL, redacción, error_type/message); `tests/test_server_protocol.py` (logging tests) | Log default a `logs/` si no se configura | — |
| Reproducible dev/release check command | DONE | `scripts/dev_check.sh`, `docs/RELEASE_CHECKLIST.md`; RELEASE_EVIDENCE (comandos exactos) | Checks de fiabilidad/MLT opt-in por env | Documentar la cadena completa de release en un único comando |
| Schema documentation for persisted JSON files | DONE | `docs/SCHEMAS.md` (rough-cut plan, timeline, manifest) | Política de migración explícita aún SHOULD | Añadir política de migración versionada a SCHEMAS.md |
| Codex MCP registration example | DONE | `examples/codex_mcp_config.toml`, `docs/CODEX_SETUP.md`, `README.md` | Sin smoke test de descubrimiento Codex real | Smoke test `tools/list` con la config oficial por STDIO |
| Known limitations documented | DONE | `README.md` ("Limite importante"), `docs/PRODUCTION_CONTRACT.md` (Known Accepted Risks) | Las limitaciones crecen con cada feature | Actualizar README al expandir superficie de edición |

## Atención especial a pendientes señalados

- Validación real de carga Kdenlive/MLT fuera del sandbox: **PARTIAL**.
  Implementada (`check_mlt`), probada con mock y registrada una vez (2026-08-25,
  `MLT load check: valid true`, carpeta de usuario real). No reproducible en el
  entorno actual; requiere evidencia por-release en la máquina objetivo.
- Checklist release reproducible: **DONE** (`docs/RELEASE_CHECKLIST.md`,
  `scripts/dev_check.sh`, RELEASE_EVIDENCE registra comandos exactos). Falta
  automatizar la parte manual Kdenlive-open (SHOULD).
- Cobertura de project locks/versioning en workflow real: **PARTIAL**.
  Unit-tests y docs (`UNDO_VERSIONING.md`) sólidos, pero no hay workflow e2e que
  ejercite un `PROJECT_LOCKED` real ni un restore completo.
- Límites de Flatpak: **DONE**. Detección de sandbox
  (`FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX`), tests y docs (`context.md`).
- Limpieza/reporting de outputs parciales: **DONE**. `partial_outputs` explícito en
  `_failed_step`; la fiabilidad valida que `partial_outputs == artifacts` en éxito.
- Documentación de schemas: **DONE** (`docs/SCHEMAS.md`).
- Registro Codex MCP: **DONE** (`examples/codex_mcp_config.toml`,
  `docs/CODEX_SETUP.md`). Falta smoke test de descubrimiento real.
- Pruebas con fixtures reales múltiples: **PARTIAL** (SHOULD). `examples/recon/`
  tiene 4 proyectos manuales + 1 carpeta de sesión real; falta generar más
  variantes desde la versión instalada (trims, gaps, transiciones, efectos).

## Production Gate Verdict

```text
VERDICTO PROVISIONAL: NOT_READY
```

Razón: 19/20 requisitos MUST están en DONE y el contrato declara evidencia P0/P1
registrada, pero un MUST crítico queda en **PARTIAL**: la validación real de carga
por Kdenlive/MLT sólo tiene evidencia puntual (2026-08-25, una máquina) y no es
reproducible en el entorno actual. Dos gates adicionales (fiabilidad 20-runs y
checksum de medios) también son registros puntuales, no verificación por-release.
El target `production-local-agent-single-user` se puede cerrar, pero la
reproducibilidad de la evidencia debe re-confirmarse en cada release.

Conteo: DONE 19 · PARTIAL 1 · MISSING 0 · BLOCKED 0.

## Top 5 acciones siguientes

1. Re-ejecutar la validación real de MLT/Kdenlive en la máquina objetivo
   (`KDENLIVE_MCP_RUN_MLT_CHECK=1 scripts/dev_check.sh` con un proyecto real) y
   registrar la evidencia por-release. Mueve el MUST #14 de PARTIAL a DONE.
2. Re-ejecutar el gate de fiabilidad (20 runs + checksum) por-release y registrar
   en RELEASE_EVIDENCE para hacer reproducible la evidencia de gates #4/#5.
3. Agregar un test e2e que ejercite `PROJECT_LOCKED` y restore completo a través
   del límite MCP (cierra el hueco de locks/versioning en workflow real).
4. Generar más fixtures Kdenlive reales desde la versión instalada (trims, gaps,
   transiciones, efectos, multi-secuencia) para robustecer #5/#6/#14.
5. Agregar un smoke test de registro Codex (`tools/list` por STDIO con la config
   oficial) para cerrar el checklist "MCP tool discovery works from Codex".