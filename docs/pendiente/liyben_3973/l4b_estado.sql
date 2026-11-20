\echo '## rol Diseño'
SELECT d.module || '.' || d.name, r.code, r.active, r.use_fallback, coalesce(fb.code, '')
  FROM ai_provider_role r
  LEFT JOIN ir_model_data d ON d.model = 'ai.provider.role' AND d.res_id = r.id
  LEFT JOIN ai_provider_role fb ON fb.id = r.fallback_id
 WHERE r.code = 'design';
\echo '## con Diseño'
SELECT p.id, p.active, r.use_fallback
  FROM ai_provider_role r
  JOIN ai_provider_role_rel rr ON rr.role_id = r.id
  JOIN ai_provider p ON p.id = rr.provider_id
 WHERE r.code = 'design' ORDER BY p.id;
\echo '## con Decisión'
SELECT p.id, p.active, p.protocol
  FROM ai_provider_role r
  JOIN ai_provider_role_rel rr ON rr.role_id = r.id
  JOIN ai_provider p ON p.id = rr.provider_id
 WHERE r.code = 'decision' ORDER BY p.id;
\echo '## roles por proveedor'
SELECT p.id, p.active, p.model_name, coalesce(string_agg(r.code, ',' ORDER BY r.sequence, r.id), '')
  FROM ai_provider p
  LEFT JOIN ai_provider_role_rel rr ON rr.provider_id = p.id
  LEFT JOIN ai_provider_role r ON r.id = rr.role_id
 GROUP BY p.id, p.active, p.model_name ORDER BY p.id;
\echo '## roles'
SELECT code, active, use_fallback FROM ai_provider_role ORDER BY sequence, id;
\echo '## es_ES'
SELECT code, active FROM res_lang WHERE code = 'es_ES';
\echo '## traducciones'
SELECT count(*), md5(coalesce(string_agg(id || ':' || md5(coalesce(value, '')), ',' ORDER BY id), ''))
  FROM ir_translation WHERE lang = 'es_ES';
\echo '## traducciones fuera de pns'
SELECT count(*), md5(coalesce(string_agg(id || ':' || md5(coalesce(value, '')), ',' ORDER BY id), ''))
  FROM ir_translation WHERE lang = 'es_ES' AND coalesce(module, '') NOT LIKE 'pns\_%';
\echo '## traducciones pns'
SELECT module, count(*) FROM ir_translation WHERE lang = 'es_ES' AND module LIKE 'pns\_%' GROUP BY 1 ORDER BY 1;
\echo '## fin'
