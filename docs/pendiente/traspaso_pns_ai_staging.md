# Traspaso: módulos de IA `pns_*` — VPS preparado; siguiente, ejecutar el plan de staging

Fecha: 15/10/2026 (tarde) · Repo: `third_party` (Odoo 14.0) · Rama: `14.0-pns-ai-3` · Kit: v2.4.1

Sustituye al traspaso del 15/10/2026 (mañana), con el mismo nombre. Se guarda en `docs/pendiente/` de la
rama y en el proyecto de claude.ai (`claude/traspaso_pns_ai_staging.md`). Sin contraseñas ni claves.

---

## 1. Dónde lo dejamos

**Versión en análisis:** `pns_base` 1.2.32 · `pns_ai_mcp` 3.1.782 · `pns_ai_chatboo` 2.1.453, con los
parches de compatibilidad 1 a 4 en la rama (commit desplegado: `95d6b1a`).

| Fase | Estado |
|---|---|
| 0 a 5d | Hechas (13-15/10) |
| 6a. Preparación del VPS de staging | **Hecha (15/10)**: montado, comprobado y documentado (plan §2 y §7.1) |
| 6b. Ejecución del plan de staging | **Siguiente**: desde el plan §3.1, punto 2 (instalar los `pns_*` en `pns_demo`) |
| 7. Instalación en LIYBEN (objetivo final) | Después del staging, con plan propio (plan §8) |

**Resultado en una línea:** el VPS está listo y aislado; `pns_demo` existe sin ningún `pns_*`; LIYBEN ya
no tiene la versión antigua; decisiones N6 a N10 tomadas y documentadas.

## 2. El entorno (detalle en el plan §2)

**VPS:** `213.32.68.100`, SSH por el puerto **50050** (usuario `ubuntu`; con `scp` el puerto va con `-P`).
Sin swap, 4 núcleos, 7,6 GiB de RAM (unos 4,5 disponibles), disco al 86 %.

En el mismo VPS, **sin tocar**:
- `odoo14_server` (Odoo 14 de Seges, BD **LIYBEN**, `https://liyben.com`). Compose en `/opt/odoo`
  (servicio `web`), PostgreSQL `odoo14_db`.
- Instancias heredadas de dos clientes: Odoo 11 (REFRIMAR) y Odoo 8 (Fumihogar), cada una con su
  PostgreSQL y su sitio en Nginx.

**Staging (N10):**

| Pieza | Valor |
|---|---|
| Carpeta y proyecto | `/opt/odoo/pns_staging`, proyecto de Docker Compose `pns_staging` |
| Servicio Odoo | `odoo14_pns` (imagen `odoo-web`, la de `odoo14_server`), `127.0.0.1:8169` / `8172`, `mem_limit` 2g |
| PostgreSQL | `odoo14_pns_db` (`postgres:15-alpine`), propio, `mem_limit` 512m; contraseña en `.env` (600) |
| Código | Solo los tres `pns_*` del commit `95d6b1a`, en `addons/` (solo lectura). Huella del `.tar.gz`: `e6141b0edcae4e16d3bdb186736a18500316d78d3cd3c7b8ff15fac8332e2d0e` |
| Configuración | `config/odoo.conf` (solo lectura en el contenedor): `dbfilter ^pns_demo$`, `list_db False`, `workers 2`, `limit_time_real 900`, memoria 1 / 1,25 GiB |
| Dominio | `https://pns.liyben.com` (Nginx del host, `/etc/nginx/conf.d/pns_liyben_com.conf`; certificado hasta el 13/01/2027, renovación automática) |
| Base de datos | `pns_demo`: `base`, datos de demostración y `es_ES`; solo `admin` activo (contraseña en el gestor de Seges); demo y portal archivados |
| Imagen | Python **3.7.3**, openpyxl 3.1.3, reportlab 3.5.13, requests 2.31.0 |

**Cómo ejecutar órdenes en el staging** (desde `/opt/odoo/pns_staging`):
- **Órdenes de Odoo que usan la BD** (`shell`, `-i`, `-u`): `docker compose run --rm web odoo <orden> -d pns_demo`.
  Hay que usar `run` y no `exec`: `run` pasa por el entrypoint de la imagen, que añade la conexión a
  PostgreSQL (`HOST`, `USER`, `PASSWORD`); con `exec` no se conectaría. Para un script de `odoo shell`,
  `run --rm -T` con un *heredoc* (así se hizo el 15/10).
- **Log:** no hay archivo de log; `docker compose logs --tail=N web` (o `--since 10m`).
- **SQL de solo lectura:** `docker exec odoo14_pns_db psql -U odoo -d pns_demo -c "..."`.
- **Reiniciar Odoo:** `docker compose restart web`.
- **LIYBEN (solo lectura):** `docker exec odoo14_db sh -c 'psql -U "$POSTGRES_USER" -d LIYBEN -c "..."'`.

## 3. Hecho el 15/10/2026 (tarde)

1. **Datos del VPS recogidos** y montaje propuesto y aprobado (proyecto propio, sin imagen nueva, solo los
   tres módulos enviados desde el equipo de Sergio con `git archive` + `scp`).
2. **Hallazgo y desinstalación en LIYBEN:** tenía `pns_base` 1.2.10, `pns_ai_mcp` 3.1.486 y
   `pns_ai_chatboo` 2.1.322 instalados desde el 02/09 (pruebas internas de Seges; último uso el 13/10),
   publicados en `liyben.com`. Copia previa en `/opt/odoo/backups/`
   (`LIYBEN_antes_desinstalar_pns_20261015.dump`, 47 MB, 824 tablas con datos; y
   `LIYBEN_filestore_20261015.tar.gz`, 433 MB, 3366 archivos; el filestore estaba en
   `/opt/odoo/odoo-web-data/.local/share/Odoo/filestore/LIYBEN`, porque `odoo14_server` no tiene
   `data_dir`). Desinstalados desde Aplicaciones (los tres `uninstalled`, 0 tablas `ai_*`), reinicio de
   `odoo14_server` y `POST /mcp` en `liyben.com` → 404.
3. **Staging montado** (fases 4 a 8): carpeta, `.env`, `odoo.conf`, compose, comprobación de imagen y
   código (parches 1-4 conformes, revisados por un agente en local), `pns_demo` creada y protegida,
   servicio arrancado, Nginx y HTTPS.
4. **Aislamiento comprobado** (fase 9): otros servicios sin reiniciar y respondiendo; cada PostgreSQL
   solo ve sus bases; `GET /mcp` → 403, `/mcp/sse` → 404, `POST /mcp` → 404 (aún sin módulos); gestor
   de bases desactivado; `odoo14_pns` en unos 230 MiB.
5. **Documentación** (fase 10, agente): `plan_staging_pns_ai.md` (nuevo índice con §8 LIYBEN y §9
   limpieza) y `pns_ai_decisiones.md` (sección 9, N6-N10; observaciones en N1 y N5). Revisados en
   claude.ai: correctos. Las opciones descartadas de N6 a N10 las redactó el agente siguiendo el formato;
   son razonables (la b de N10 es la alternativa que se valoró).

## 4. Decisiones de Sergio del 15/10/2026 (en `pns_ai_decisiones.md`, sección 9)

- **N6 — Camino A:** primero el staging en `pns_demo`; después, como fase aparte, LIYBEN (objetivo final).
- **N7 — LIYBEN** con la 3.1.782, los parches 1-4 y las mitigaciones de N3, sin esperar al fabricante
  (LIYBEN es interna, con datos antiguos de la empresa antes del cambio de nombre).
- **N8 — Proveedor del staging: Gemini** (no hay clave de API de Anthropic; el plan Pro no la incluye).
  La prueba 9b no aplica en el staging. En LIYBEN, el proveedor lo decide el jefe en la demostración; si
  es Anthropic, allí se hace la 9b; si es Gemini, antes se comprueban las condiciones de uso de datos del
  nivel gratuito.
- **N9 — No se guardan copias de `pns_demo`.**
- **N10 — Staging con servicio, PostgreSQL y despliegue propios.**

## 5. Documentos de la rama

| Documento | Estado |
|---|---|
| `docs/pendiente/plan_staging_pns_ai.md` | Actualizado (fase 10). §2 hecho; §7.1 concretado; §8 LIYBEN; §9 limpieza |
| `docs/pendiente/pns_ai_decisiones.md` | Actualizado (fase 10). N6-N10; observaciones en N1 y N5 |
| `docs/pendiente/traspaso_pns_ai_staging.md` | Este documento (sustituye al de la mañana) |
| Resto (`guia_configuracion`, `seguimiento`, `informe_seguimiento_fabricante`, `verificacion`, `parches`) | Sin cambios |

**Commit pendiente de comprobar:** el de la fase 10 (los dos documentos y este traspaso). Si `git status`
muestra alguno, revisarlo y hacer el commit antes de seguir.

**Correcciones menores para la próxima sesión** (con un agente, antes de ejecutar el plan):
1. Plan §7.1: dice que las órdenes dentro del servicio se ejecutan con `docker compose exec`. Para las
   órdenes de Odoo con BD es `docker compose run --rm web` (ver §2 de este traspaso).
2. D3 («Información necesaria: versión exacta de Python»): añadir observación con Python 3.7.3 en el VPS.

## 6. Pendiente

**Antes de ejecutar el plan:**
1. Crear una **clave nueva de Gemini** solo para el staging, con cuota o límite (plan §4.2 y §7.2).
2. Comprobar que la **clave de Gemini del laboratorio** está revocada (Google AI Studio).
3. **Revocar las claves de los proveedores que tenía configurados LIYBEN.** Si no se anotaron antes de
   desinstalar, revisar en las consolas de los proveedores las claves creadas para esas pruebas (por
   fecha o nombre). Los registros borrados están en la copia `.dump` si hiciera falta consultarlos.
4. Preparar la **imagen JPEG con orientación EXIF 6** para la prueba 2 (plan §4.5), fuera del VPS.

**Ejecución:**
5. Ejecutar el plan desde el §3.1, punto 2, y rellenar su §6.1. Entre partes, revisar cada resultado en
   claude.ai.
6. Después: trasladar resultados a la verificación y al seguimiento; revisar N3, D29, D46 y N7 (plan
   §6.2); si cambia algún estado, nota breve para el fabricante.
7. Planificar la instalación en LIYBEN (plan §8). Dato: el `third_party` de `odoo14_server` está en
   `/opt/odoo/addons/custom/third_party`, rama `14.0`, commit `f63d5a1`, remoto HTTPS sin clave SSH en
   el VPS, y contiene los `pns_*` antiguos en disco (no instalados). Demostración con el jefe; proveedor;
   datos personales hacia el proveedor (D10).
8. Limpieza del plan §9 al terminar el staging.

**Arrastrados del traspaso anterior:**
9. Envío del informe al fabricante (lo decide Sergio; documento listo).
10. Decisiones abiertas: D7 (5 servidores heredados), D46 (tras las pruebas), recomendación para External API.
11. Kit (otro día, con su análisis): `odoo-dev arrancar` con el stack en marcha no recrea el contenedor ni
    recarga el código Python; comprobar si `parar` detiene también la BD.

**Fuera de este trabajo (observación):** `odoo14_server` no tiene límite de memoria en Docker; con el VPS
sin swap, convendría revisarlo algún día.

## 7. Reglas que siguen vigentes

- No se modifica el código del fabricante salvo los parches 1 a 4 (N2).
- Nada de `pip` en contenedores; librerías en la imagen.
- Escrituras en BD solo con autorización explícita (en `pns_demo` y, más adelante, en LIYBEN).
- En el VPS no se tocan `odoo14_server` ni las instancias de otros clientes salvo decisión expresa.
- Pruebas descritas, sin cargas ni pasos de explotación, ni en documentos ni en informes.
- Lo que se envíe al fabricante no menciona rutas locales, el kit, el laboratorio, clientes, personas ni
  decisiones internas. `verificacion_seguridad_pns_ai.md` no se envía.
- Los agentes no hacen commit ni push; ramas, commits y push, Sergio con GitHub Desktop.
- Entre fases, `/clear` en VS Code; en claude.ai se revisa cada resultado antes de seguir.
- Comandos para el VPS: copiar y pegar, con resultado esperado, avisando de lo que altera. Los bloques
  largos se pegan a veces mezclados en la terminal: comprobar el archivo resultante con `grep`.

## 8. Cómo empezar la conversación nueva

1. Conversación nueva en el proyecto **claude-odoo-kit** de claude.ai.
2. Adjuntar `docs/pendiente/plan_staging_pns_ai.md` (no está en el proyecto).
3. Primer mensaje, por ejemplo: *«Lee `claude/traspaso_pns_ai_staging.md`. Vamos a ejecutar el plan de
   staging desde el §3.1.»*
4. Traer:
   - si la clave nueva de Gemini está creada (sí o no; nunca la clave);
   - la salida de `cd /opt/odoo/pns_staging && docker compose ps`;
   - si se han hecho las dos correcciones menores del §5.
