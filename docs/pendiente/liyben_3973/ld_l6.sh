ld_l6() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD L6"
  sd() { sec "$RD" "$1"; }
  sa() { sec "$RA" "$1"; }
  ver() { echo "-- $2"; sd "$1" | sed 's/^/   /'; }
  igual() { chk "$2, = antes (L0)" "$(sd "$1" | una)" "$(sa "$1" | una)" ${3:-}; }
  [ "$(cd "$(dirname "$0")" && pwd)" = "$LD" ] || { echo "Lánzala desde $LD: bash $LD/ld_l6.sh"; exit 1; }
  O=$(nueva "$LD/l6" .txt) || exit 1
  A=$(nueva "$LD/l6_despues" .txt) || exit 1
  {
  echo "== $TANDA (VPS: «después» por SQL, contra el «antes» de L0 y el «después» de L4b; solo lectura): $(date -u '+%F %T') UTC"
  echo "== 1. Comprobaciones previas"
  L5=$(ultima "$LD/l5-*.txt")
  chk "última L5 (${L5##*/}) con TODO OK" "$(marca "$L5" '== LD L5: TODO OK. Web EN MARCHA. Sigue con L6.')" 1
  L0=$(ultima "$LD/l0-*.txt")
  chk "última L0 (${L0##*/}) con TODO OK" "$(marca "$L0" '== LD L0: TODO OK. Corte: pega la salida. Después L1 (interfaz) y L2, antes de una hora.')" 1
  AN=$(sed -n 's/^guardado: \(.*l0_antes-[0-9-]*\.txt\) (.*/\1/p' "$L0" | head -1)
  chk "«antes» de esa L0 completo (${AN##*/})" "$(grep -cx '## fin' "$AN" 2>/dev/null || true)" 1
  B=$(ultima "$LD/l4b-APLICAR_BP-*.txt")
  DB=$(printf '%s' "$B" | sed 's#/l4b-APLICAR_BP-#/l4b_despues-APLICAR_BP-#')
  chk "«después» del L4b APLICAR_BP (${DB##*/}) completo" "$(grep -cx '## fin' "$DB" 2>/dev/null || true)" 1
  T0U=$(cat "$LD/l4_t0.txt" 2>/dev/null)
  chk "inicio del -u de L4 (UTC)" "$(printf '%s' "$T0U" | grep -cxE '[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}' || true)" 1
  echo "   inicio del -u: $T0U UTC"
  corte "comprobaciones previas"
  RA=$(cat "$AN")

  echo "== 2. «Después» (l6_despues.sql = Y7; salida SQL completa en $A)"
  RD=$( { printf "\\\\set t0 '%s'\n" "$T0U"; cat "$LD/l6_despues.sql"; } | lysql )
  printf '%s\n' "$RD" > "$A"
  echo "guardado: $A ($(wc -l < "$A" | tr -d ' ') líneas, SHA-256 $(sha256sum "$A" | cut -d' ' -f1))"
  chk "consultas sin error" "$(printf '%s\n' "$RD" | grep -ciE 'ERROR:|psql: error' || true)" 0
  printf '%s\n' "$RD" | grep -iE 'ERROR:|psql: error' | head -5 | cut -c1-160 | sed 's/^/   /'
  chk "marcador final de la salida SQL" "$(printf '%s\n' "$RD" | grep -cx '## fin' || true)" 1
  corte "consultas"

  echo "== 3. Módulos, AI Administrators y proveedores"
  chk "versiones (nombre|estado|versión): las de la rama" "$(sd versiones | una)" "pns_ai_chatboo|installed|14.0.2.1.587 pns_ai_mcp|installed|14.0.3.1.973 pns_base|installed|14.0.1.2.69"
  chk "módulos a medio instalar o actualizar" "$(sd 'estados a medias')" 0
  chk "módulos instalados, = I0" "$(sd instalados)" 215
  igual dependientes "dependientes de los pns_* (ninguno)"
  chk "AI Administrators (id|activo|Ajustes|contraseña local|AI Conversational): el 2 lo ganó en el -u (D64)" "$(sd 'ai admins' | una)" "2|t|t|t|t 6|t|t|t|t 7|t|t|t|t"
  chk "P-11 (AI Administrators|sin AI Conversational)" "$(sd p11)" "3|0"
  chk "proveedores (id|activo|protocolo|modelo|sin failover externo), = antes sin las fit_*" "$(sd proveedores | una)" "$(sa proveedores | awk -F'|' '{ print $1 "|" $2 "|" $3 "|" $4 "|" $10 }' | una)"
  chk "roles por proveedor (id|activo|modelo|roles): Decisión fuera del 1 y Diseño dentro (D67)" "$(sd 'roles por proveedor' | una)" "1|f|models/gemini-3.5-flash|conversation,vision,design 2|t|Qwen3.5-9B|conversation,vision"
  chk "rol Diseño sin alternativa (xml_id|code|activo|use_fallback|alternativa)" "$(sd 'rol Diseño' | una)" "pns_ai_mcp.ai_provider_role_design|design|t|f|conversation"
  chk "rol Diseño solo en el proveedor 1, inactivo (D62)" "$(sd 'con Diseño' | una)" "1|f|f"
  chk "rol Decisión sin titulares" "$(sd 'con Decisión' | una)" ""
  ver roles "roles (code|activo|use_fallback|alternativa)"
  igual cadena "cadena de proveedores (id|agente|prioridad|activo|skip_sync_fallback|provider_id|proveedor activo)"

  echo "== 4. Crons"
  chk "crons de pns_* (xml_id|activo|intervalo|numbercall): los 6 de antes y el nuevo de la papelera del diario, todos activos" "$(sd crons | una)" "pns_ai_chatboo.ir_cron_chatboo_async_maintenance|t|5 minutes|-1 pns_ai_mcp.ir_cron_ai_api_result_cache_gc|t|1 hours|-1 pns_ai_mcp.ir_cron_ai_fetch_cache_gc|t|1 hours|-1 pns_ai_mcp.ir_cron_ai_journal_trash|t|1 days|-1 pns_ai_mcp.ir_cron_ai_log_retention|t|1 days|-1 pns_ai_mcp.ir_cron_ai_safe_operation_expire|t|5 minutes|-1 pns_base.ir_cron_pns_export_purge|t|1 hours|-1"
  chk "crons activos (todos los módulos) = los de L0 más el nuevo" "$(sd 'crons activos')" "$(( $(sa 'crons activos') + 1 ))"
  chk "crons creados en el -u (journal_trash_cron.xml, active=True)" "$(sd 'crons creados en el -u' | una)" "pns_ai_mcp.ir_cron_ai_journal_trash"
  chk "crons de NUEVO-2 corregidos por el parche 35" "$(sd 'crons nuevo2' | una)" "ir_cron_ai_api_result_cache_gc|model._gc_expired() ir_cron_ai_fetch_cache_gc|model._gc_expired()"

  echo "== 5. Parámetros, operaciones, diario, Chatboo y registro"
  igual parametros "parámetros (clave|valor)"
  chk "parámetro pns_ai_mcp.journal_trash_days (clave|valor)" "$(sd 'parametro papelera' | una)" "" info
  chk "operaciones pending o confirmed sin ejecutar" "$(sd 'operaciones no terminales' | una)" ""
  chk "operaciones no terminales con pasos sobre ai.trusted.action" "$(sd 'operaciones trusted')" 0
  igual 'operaciones por status' "ai_safe_operation por status (status|n)" info
  igual trusted "ai_trusted_action (n|max_id)" info
  chk "servidores ai.api.server (PNS-17)" "$(sd 'servidores api')" 0
  igual diario "diario (filas|unlink en papelera|reescritas por otro)" info
  igual chatboo "Chatboo (sesiones|id máximo|primera, mes|usuarios)" info
  chk "ai_log (filas|max_id; sin agent_id desde el -u)" "$(sd ai_log)" "0|0" info

  echo "== 6. Skills y contextos (P-21)"
  chk "skills (code): 6 retiradas y 6 nuevas, como en el staging" "$(sd skills | cut -d'|' -f1 | una)" "bill_draft billing customer_360 dashboard financial_health forecast pipeline sales_board top_sales users"
  chk "skills activas" "$(sd skills | awk -F'|' '$2 == "t"' | grep -c . || true)" 10
  ver skills "skills (code|activa|sistema|con xml_id)"
  ver 'skills detalle' "skills (id|code|command|source_module|rel_path|activa|write_uid|escrita en el -u)"
  chk "skills que P-21 reescribe (billing, financial_health, forecast) con write_date del -u" "$(sd 'skills reescritas' | una)" "billing financial_health forecast" info
  chk "contextos (total|activos)" "$(sd contextos | cut -d'|' -f1,2)" "59|59"
  echo "INFO    contextos con xml_id: $(sd contextos | cut -d'|' -f3) (antes: $(sa contextos | cut -d'|' -f3))"
  chk "contextos por módulo (source_module|n|activos)" "$(sd 'contextos por modulo' | una)" "pns_ai_chatboo|6|6 pns_ai_mcp|53|53"
  chk "contextos nuevos (code|módulo|rel_path|activo|creado en el -u)" "$(sd 'contextos nuevos' | una)" "discovery_page_tab|pns_ai_chatboo|contexts/discovery/discovery_page_tab.json|t|t discovery_page_tab_es_ES|pns_ai_chatboo|contexts/discovery/discovery_page_tab_es_ES.json|t|t page_tab|pns_ai_chatboo|contexts/domain/page_tab/page_tab.xml|t|t"
  chk "contextos creados antes del -u (los 56 de antes: ninguno retirado)" "$(sd 'contextos de antes')" 56
  chk "contextos escritos en el -u (de los 13 que P-21 reescribe|de los otros 43: el -u escribe los 56; ensayo, Y7)" "$(sd 'contextos reescritos')" "13|43" info
  chk "contextos y skills archivados" "$(sd archivadas | una)" ""

  echo "== 7. Idioma, traducciones, tokens e IAP"
  igual 'modulos iap' "módulos crm, iap, partner_autocomplete y sms (name|state)"
  chk "es_ES activo" "$(sd idioma)" "es_ES|t"
  chk "traducciones es_ES, = después de L4b (la recarga B′ no añade)" "$(sd 'traducciones es_ES')" "$(sec "$(cat "$DB")" traducciones | cut -d'|' -f1)"
  chk "traducciones fuera de los pns_* (n|huella), = después de L4b" "$(sd 'traducciones fuera de pns')" "$(sec "$(cat "$DB")" 'traducciones fuera de pns')"
  chk "traducciones de los pns_* (módulo|n), = después de L4b" "$(sd 'traducciones pns' | una)" "$(sec "$(cat "$DB")" 'traducciones pns' | una)"
  chk "tokens de registro (D50: vaciados en L4)" "$(sd tokens)" 0
  igual iap "iap_account (filas)"
  fin "Sigue con L7 (interfaz) y L8."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_l6
