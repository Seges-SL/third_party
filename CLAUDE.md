# third_party — contexto para Claude

## Datos del repositorio
- Tipo de repositorio: repositorio común de módulos propios
- Cliente: (no aplica)
- Versión de Odoo: 14.0
- Licencia para módulos nuevos: AGPL-3 (https://www.gnu.org/licenses/agpl-3.0)
- Autor en el manifest: Seges
- Código de referencia (solo lectura, para consultar; no sirve para ejecutar Odoo). Contiene
  todo el código de cada rama (solo faltan traducciones y estáticos); si un módulo no está,
  no existe en esa rama:
  - /opt/odoo-src/14.0
  (se crea y actualiza con `./preparar_equipo.sh referencias` desde el kit)

## Dependencias
- Repos compartidos: `vertical-instaladores` (rama 14.0).
- OCA: lista estándar de la empresa (`referencias.conf` del kit).
- Repos OCA adicionales de este cliente: (ninguno)
  <!-- Si hay alguno, añádelo aquí y también a OCA_EXTRA_14 en referencias.conf del kit. -->

## Convenciones de este repo
- Las especificaciones de módulos se guardan en `docs/specs/<modulo>.md`.
- Cualquier módulo nuevo sigue las skills `odoo-comun` y `odoo-14-conventions`.
- Módulos nuevos: `name` y `summary` del manifest en español; documentación en
  `readme/*.md` (en español) e icono de la empresa;
  `README.rst` y `static/description/index.html` se generan con `odoo-readme <modulo>`.
  En módulos existentes no se crea esa estructura salvo que se pida.
- No hagas `git commit` ni `git push`.
- IMPORTANTE: `/opt/odoo-src/14.0/third_party` es una copia de referencia de ESTE repo (la versión publicada). No la consultes: trabaja siempre con los archivos locales del repo.

## Pruebas
Dos etapas:

1. **Local, con `odoo-dev`** (entorno Docker del kit). Aquí se instala, se prueba y se depura.
   - Preparar el contexto: `odoo-dev 14 arrancar` desde la raíz de este repo
     (monta este repo, los compartidos y OCA; base de datos `third_party_14`).
   - Instalar / actualizar: `odoo-dev 14 instalar <modulo>` · `odoo-dev 14 actualizar <modulo>`
   - Tests: `odoo-dev 14 tests <modulo>` (base de datos de tests nueva cada vez)
   - Log del servidor: `odoo-dev 14 log` · Interfaz: http://localhost:8169
   - Lint de lo cambiado: `python3 ~/.claude/hooks/odoo_lint.py --revisar <modulo>/`
   - Con una copia de producción cargada: `odoo-dev 14 paridad` comprueba que el entorno
     puede ejecutarla (módulos sin código, librerías que faltan en la imagen).
   - No arranques Odoo de ninguna otra forma. Cargar, borrar o modificar bases de datos
     (`bd-cargar`, `bd-borrar`, `bd-neutralizar`, `bd-claves`) lo decide siempre el usuario.
2. **VPS de pruebas del cliente**: validación con datos reales. Al terminar una tarea, entrega
   un plan de prueba: qué módulos actualizar allí y qué casos comprobar en la interfaz.
