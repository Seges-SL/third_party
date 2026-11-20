SELECT id, coalesce(type, ''), coalesce(module, ''), md5(coalesce(name, '')), coalesce(state, ''), md5(coalesce(comments, '')), md5(coalesce(value, ''))
  FROM ir_translation WHERE lang = 'es_ES' ORDER BY id;
