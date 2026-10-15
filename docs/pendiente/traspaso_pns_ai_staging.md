# Traspaso: módulos de IA `pns_*` — fase 5 cerrada; siguiente, staging

Fecha: 15/10/2026 · Repo: `third_party` (Odoo 14.0) · Rama: `14.0-pns-ai-3` · Kit: v2.4.1

Continúa `traspaso_pns_ai_fase5.md` (14/10/2026). Se guarda en `docs/pendiente/` de la rama y en el
proyecto de claude.ai (`claude/traspaso_pns_ai_staging.md`).

---

## 1. Dónde lo dejamos

**Versión en análisis:** `pns_base` 1.2.32 · `pns_ai_mcp` 3.1.782 · `pns_ai_chatboo` 2.1.453, con los
parches de compatibilidad 1 a 4 en la rama.

| Fase | Estado |
|---|---|
| 0 a 4, 3c y parche 4 | Hechas (13-14/10) |
| 5a. Revisión de decisiones (N1 a N5) | Hecha (14/10) |
| 5b. Guía de configuración | Hecha (15/10) |
| 5c. Plan de staging | Hecha (15/10) |
| 5d. Informe de seguimiento al fabricante + revisión independiente | Hecha (15/10): 0 bloqueantes; las 12 observaciones, corregidas |
| 6. Ejecución del plan de staging | **Siguiente** (cuando el VPS esté listo) |

**Resultado en una línea:** de los 80 hallazgos, 31 corregidos, 33 parciales, 13 sin cambios, 2 ya no
aplican y 1 dudoso; 12 nuevos (PNS-81 a 92). Apta solo para staging (N3) hasta que el fabricante
corrija PNS-82, 83, 85, 90 y 91.

## 2. Documentos de la rama

| Documento | Estado |
|---|---|
| `docs/specs/guia_configuracion_pns_ai.md` | Actualizada a 3.1.782 (5b). Incluye la nota de §4.3 sobre `dbfilter` y el parche de `http_patch.py` |
| `docs/pendiente/plan_staging_pns_ai.md` | Nuevo (5c). Instalación nueva en `<bd_demo>` con servicio de Odoo propio; 11 pruebas (9 de la 3b-2 + PNS-12 y PNS-46); registro en §6.1; lo que depende del VPS, en §7.1 |
| `docs/pendiente/informe_seguimiento_fabricante_pns_ai.md` | Nuevo (5d). Listo para enviar: sin nota de borrador y revisado por `odoo-reviewer` |
| `docs/pendiente/seguimiento_informe_pns_ai.md` | Corregido con lo que salió en la revisión del informe; observación nueva en PNS-31 (parche de `Root.get_request`); PNS-14 sin prueba en staging |
| `docs/pendiente/pns_ai_decisiones.md` | Observación añadida en D9 (parche de `http_patch.py` y servicio propio) |
| `docs/pendiente/verificacion_seguridad_pns_ai.md` | Sin cambios. Interno: **no se envía** |
| `docs/pendiente/parches_pns_ai.md` | Sin cambios |

**Último commit pendiente de comprobar:** el de la fase 5d (informe, seguimiento y plan). Si
`git status` muestra alguno de esos archivos, revisarlo y hacer el commit antes de seguir.

## 3. Decisiones tomadas hoy (Sergio, 15/10/2026)

- **Staging = instalación nueva**, no actualización: ningún cliente tiene hoy los `pns_*`. Se hace en
  el VPS de pruebas de un cliente, en una base de datos de demostración (`<bd_demo>`).
- **Servicio de Odoo propio para `<bd_demo>`:** el parche de `http_patch.py` sustituye
  `Root.get_request` para todo el proceso, sin mirar la base de datos (PNS-31, D9). La base de pruebas
  del cliente no comparte servicio con `<bd_demo>` y en ella no se instala ningún `pns_*`. Instalarlos
  en la base del cliente con datos reales es una decisión aparte.
- **Proveedor externo: Anthropic** (el módulo activa la caché de prompt; necesario para la prueba 9b).
- **Política `open` solo durante las pruebas 3 y 9a**, como excepción documentada a la guía §9.3.
- **Prueba 4b:** segundo proveedor sin clave, fuera de la cadena, archivado al terminar.
- **Lista blanca:** los dominios que sobren se borran, no se archivan; revisión periódica, incluidos
  los archivados.
- **Al terminar staging:** borrar `<bd_demo>`, eliminar el servicio propio y revocar la clave del
  proveedor.
- **No se prueban en staging:** el resto de PNS-01/02 (queda para la reverificación, guía §15);
  PNS-14 (`api_call`, necesita un servidor externo); la secuencia de N1, D17 y la medida real de las
  purgas (no aplican a ningún cliente actual; N1 se podría validar aparte en local con la copia del
  laboratorio previa a la actualización).
- **Informe al fabricante:** las correcciones sin fuente van redactadas como propuesta; se mantiene
  la denominación «pruebas A-D» (está en el informe original).

## 4. Pendiente

1. **Envío del informe al fabricante:** lo decide Sergio. El documento está listo. Si se envía como
   PDF o Word, convertir el Markdown sin tocar el contenido.
2. **Preparar el VPS:** concretar los puntos de §7.1 del plan (servicio propio, `dbfilter` de los dos
   servicios, despliegue de la rama, archivo de configuración, proxy, creación de `<bd_demo>`).
3. **Ejecutar el plan de staging** y rellenar su §6.1. Después, trasladar los resultados a la
   verificación y al seguimiento, revisar N3, D29 y D46 (§6.2 del plan) y, si cambia algún estado,
   preparar una nota breve para el fabricante.
4. **Decisiones abiertas:** D7 (borrar o no los 5 servidores heredados), D46 (a quién se da el chat,
   tras las pruebas), recomendación para el grupo External API.
5. **Laboratorio:** comprobar que la clave de Gemini está revocada en Google AI Studio (si no se hizo).
6. **Kit (otro día, con su propio análisis):** `odoo-dev arrancar` con el stack en marcha no recrea el
   contenedor ni recarga el código Python; comprobar si `parar` detiene también la BD y si
   `actualizar` y `shell` la levantan solos. No está en el MANUAL.

## 5. Reglas que siguen vigentes

- No se modifica el código del fabricante salvo los parches 1 a 4 (N2).
- Nada de `pip` en contenedores; librerías en la imagen.
- Escrituras en BD solo con autorización explícita.
- Pruebas descritas, sin cargas ni pasos de explotación, ni en documentos ni en informes.
- Lo que se envíe al fabricante no menciona rutas locales, el kit, el laboratorio, clientes, personas
  ni decisiones internas. `verificacion_seguridad_pns_ai.md` no se envía.
- Los agentes no hacen commit ni push; ramas, commits y push, Sergio con GitHub Desktop.
- Entre fases, `/clear` en VS Code; en claude.ai se revisa cada resultado antes de seguir.

## 6. Cómo empezar la conversación nueva

1. Conversación nueva en el proyecto **claude-odoo-kit** de claude.ai.
2. Primer mensaje, por ejemplo: *«Lee `claude/traspaso_pns_ai_staging.md`. Vamos a preparar el VPS de
   staging.»*
3. Traer los datos del VPS que pide el §7.1 del plan:
   - cómo está montado hoy el servicio de la base de pruebas del cliente (`docker-compose.yml`,
     nombre del servicio, imagen);
   - su archivo de configuración de Odoo (sin contraseñas), en particular `dbfilter`;
   - qué bases de datos hay en el PostgreSQL;
   - cómo llega `third_party` al contenedor (clon, volumen, copia) y en qué commit está;
   - el proxy (Nginx u otro) delante de Odoo.
