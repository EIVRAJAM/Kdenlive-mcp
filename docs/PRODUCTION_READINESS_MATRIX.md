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
| Copy-on-write project versioning | DONE | `services/backup_service.py`, `docs/UNDO_VERSIONING.md`; `tests/test_backup_service.py`, `tests/test_project_mcp_workflow.py` (clone/restore/list e2e) | Restore e2e cubierto; falta ejercitar restore dentro de un flujo de edición real | — |
| Project lock handling | DONE | `services/lock_service.py`, `services/project_workflow_service.py`; `tests/test_lock_service.py`, `test_project_workflow_service.py`, `test_project_mcp_workflow.py` (`PROJECT_LOCKED` e2e) | Conflicto de lock multi-proceso no simulado (fuera del target single-user) | — |
| Rough-cut workflow from folder to .kdenlive | DONE | `services/vlog_workflow_service.py`, `tools/rough_cut_tools.py`; `tests/test_vlog_workflow_service.py` | Depende de la plantilla fixture | — |
| Automated end-to-end workflow test | DONE | `tests/test_vlog_workflow_service.py`; `scripts/dev_check.sh` (`KDENLIVE_MCP_RUN_FIXTURE_WORKFLOW`); RELEASE_EVIDENCE (20 runs) | Gate opt-in por env, no CI permanente | Documentar ejecución en CI/release reproducible |
| Original media checksum test | DONE | `scripts/fixture_reliability_check.py` (sha256); RELEASE_EVIDENCE `media_checksums_unchanged: true` | Evidencia puntual (2026-08-25), no por-release | Re-ejecutar por release y registrar checksum |
| Generated .kdenlive inspect validation | DONE | RELEASE_EVIDENCE (export validation, clip/marker/guide counts); `tests/test_timeline_service.py` | — | — |
| Optional workflow-level MLT load validation | DONE | `tools/project_tools.py` `check_mlt`; `scripts/dev_check.sh` `KDENLIVE_MCP_RUN_MLT_CHECK`; tests con `melt` mockeado; evidencia real 2026-08-25 (`MLT load check: valid true`) y 2026-09-01 (proyecto generado por MCP, melt Flatpak exit 0, `status: loaded`) | La carga real requiere Flatpak y acceso al filesystem en cada máquina | Re-ejecutar `KDENLIVE_MCP_RUN_MLT_CHECK=1 scripts/dev_check.sh` con un proyecto real y registrar por release |
| Partial-output cleanup or explicit partial-output reporting | DONE | `services/vlog_workflow_service.py` `_failed_step`/`partial_outputs`; `scripts/fixture_reliability_check.py` (assert partial_outputs) | Sólo reporting, sin cleanup (permitido por el contrato "or") | — |
| Persistent structured logging | DONE | `src/kdenlive_mcp/logging.py` (JSONL, redacción, error_type/message); `tests/test_server_protocol.py` (logging tests) | Log default a `logs/` si no se configura | — |
| Reproducible dev/release check command | DONE | `scripts/dev_check.sh`, `scripts/release_gate.sh` (dev + STDIO smoke + reliability + MLT opcional), `docs/RELEASE_CHECKLIST.md`; RELEASE_EVIDENCE (comandos exactos) | Checks de fiabilidad/MLT opt-in por env y MLT requiere Flatpak | — |
| Schema documentation for persisted JSON files | DONE | `docs/SCHEMAS.md` (rough-cut plan, timeline, manifest) | Política de migración explícita aún SHOULD | Añadir política de migración versionada a SCHEMAS.md |
| Generic MCP client registration example | DONE | `examples/mcp_client_config.toml`, `docs/MCP_CLIENT_SETUP.md`, `examples/codex_mcp_config.toml`, `docs/CODEX_SETUP.md`; smoke test STDIO real `scripts/mcp_stdio_smoke_test.py` (`initialize` + `tools/list`, 59 tools) | No probado contra todos los clientes MCP, pero sí contra el protocolo STDIO real | Smoke test `tools/list` desde un cliente MCP externo real |
| Known limitations documented | DONE | `README.md` ("Limite importante"), `docs/PRODUCTION_CONTRACT.md` (Known Accepted Risks) | Las limitaciones crecen con cada feature | Actualizar README al expandir superficie de edición |

## Atención especial a pendientes señalados

- Validación real de carga Kdenlive/MLT fuera del sandbox: **DONE**.
  Implementada (`check_mlt`) y verificada con melt real de Flatpak sobre un
  proyecto generado por el MCP (2026-09-01, exit 0, `status: loaded`, sin medios
  faltantes). Re-ejecutar por-release en la máquina objetivo.
- Checklist release reproducible: **DONE** (`docs/RELEASE_CHECKLIST.md`,
  `scripts/dev_check.sh`, RELEASE_EVIDENCE registra comandos exactos). Falta
  automatizar la parte manual Kdenlive-open (SHOULD).
- Cobertura de project locks/versioning en workflow real: **DONE**.
  Unit-tests, docs (`UNDO_VERSIONING.md`) y e2e por MCP
  (`tests/test_project_mcp_workflow.py`): `PROJECT_LOCKED` bloquea
  `prepare_working_project`, clone/_ai_001/_ai_002, list, restore `_restored_001`,
  y `PROJECT_NOT_FOUND` en restore de versión inexistente. `prepare_working_project`
  ahora rechaza clonar un proyecto bloqueado.
- Límites de Flatpak: **DONE**. Detección de sandbox
  (`FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX`), tests y docs (`context.md`).
- Limpieza/reporting de outputs parciales: **DONE**. `partial_outputs` explícito en
  `_failed_step`; la fiabilidad valida que `partial_outputs == artifacts` en éxito.
- Documentación de schemas: **DONE** (`docs/SCHEMAS.md`).
- Registro MCP genérico: **DONE** (`examples/mcp_client_config.toml`,
  `docs/MCP_CLIENT_SETUP.md`, `docs/CODEX_SETUP.md` como ejemplo específico) y
  smoke test real del canal STDIO (`scripts/mcp_stdio_smoke_test.py`,
  `initialize` + `tools/list`, 59 tools). Falta probar desde un cliente MCP
  externo real.
- Pruebas con fixtures reales múltiples: **PARTIAL** (SHOULD). `examples/recon/`
  tiene 4 proyectos manuales validados (well-formed, vertical HD 30, medios
  presentes) y 1 carpeta de sesión real. Los detectores de patrones
  (trim/gap/transition/effect) ya están en `tests/test_kdenlive_project_fixtures.py`
  con recetas manuales exactas en `docs/KDENLIVE_PROJECT_FORMAT.md`; los fixtures
  `manual_trimmed_clip`, `manual_gap_timeline`, `manual_transition_dissolve` y
  `manual_basic_effect` quedan pendientes de creación manual en Kdenlive y sus
  tests se saltan hasta que existan.
- Edición directa en sitio de un `.kdenlive` working copy: **SHOULD pendiente**.
  No existe tool MCP que edite un `.kdenlive` en sitio; la edición opera sobre
  `.timeline.json` (apply_timeline_edits) y se exporta vía
  `export_timeline_to_kdenlive_template` usando la working copy como template.
  El e2e `test_working_copy_edit_flow_restore` cubre el límite real existente;
  hay un test skipped con la razón explícita.

## Production Gate Verdict

```text
VERDICTO PROVISIONAL: READY
```

Razón: los 20 requisitos MUST del target `production-local-agent-single-user`
están en DONE. El único PARTIAL restante (validación real de carga MLT/Kdenlive)
quedó cubierto el 2026-09-01 con una validación real, no mockeada, de un proyecto
generado por el MCP a través del melt de Flatpak (exit 0, `status: loaded`, sin
medios faltantes). Los pendientes que siguen abiertos (locks/versioning e2e,
más fixtures reales, cliente MCP externo real, evidencia por-release) son SHOULD
o evidencia de mantenimiento, no bloqueos MUST del target.

Conteo: DONE 20 · PARTIAL 0 · MISSING 0 · BLOCKED 0.

## Top 5 acciones siguientes

1. Re-ejecutar el gate real de MLT/Kdenlive en cada release
   (`KDENLIVE_MCP_RUN_MLT_CHECK=1 scripts/dev_check.sh` con un proyecto generado)
   y registrar la evidencia en RELEASE_EVIDENCE para mantener el MUST #14 en DONE.
2. Re-ejecutar el gate de fiabilidad (20 runs + checksum) por-release y registrar
   en RELEASE_EVIDENCE para hacer reproducible la evidencia de gates #4/#5.
3. Implementar edición directa en sitio de una working copy `.kdenlive` (SHOULD
   pendiente). Hoy la edición pasa por `.timeline.json` +
   `export_timeline_to_kdenlive_template`; el e2e
   `test_working_copy_edit_flow_restore` ya cubre el flujo real con restore.
4. Crear los 4 fixtures manuales pendientes en Kdenlive (trim, gap, dissolve,
   efecto) siguiendo las recetas de `docs/KDENLIVE_PROJECT_FORMAT.md`; los
   detectores de test ya están listos y se activan al añadir cada archivo.
5. Probar el descubrimiento desde un cliente MCP externo real (ya existe el smoke
   test STDIO `scripts/mcp_stdio_smoke_test.py`; queda cerrar el checklist
   "MCP tool discovery works" con un cliente real).
