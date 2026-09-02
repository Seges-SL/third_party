# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Functions for verifying dangerous write operations."""

import json
import logging
from odoo import SUPERUSER_ID
from odoo.http import request
from datetime import timedelta
from odoo import fields

_logger = logging.getLogger(__name__)


def requires_safe_operation(operation_type, model_name, records_count, search_domain=None):
    """
    Determina si una operaci├│n de escritura requiere verificaci├│n.
    
    :param operation_type: Tipo de operaci├│n ('create', 'write', 'unlink')
    :param model_name: Nombre del modelo
    :param records_count: N├║mero de registros afectados
    :param search_domain: Dominio de b├║squeda usado (opcional, para detectar operaciones masivas)
    :return: True si requiere verificaci├│n, False en caso contrario
    """
    # Borrados siempre requieren verificaci├│n
    if operation_type == 'unlink':
        return True
    
    # Creaciones masivas requieren verificaci├│n
    if operation_type == 'create' and records_count > 1:
        return True
    
    # Modificaciones masivas requieren verificaci├│n
    if operation_type == 'write' and records_count > 1:
        return True
    
    # Modificaciones con dominio de b├║squeda que pueda afectar m├║ltiples registros
    if operation_type == 'write' and search_domain:
        # Si el dominio no tiene limit=1 expl├¡cito, puede afectar m├║ltiples registros
        # Por ahora, si hay dominio y records_count > 0, requiere verificaci├│n
        if records_count > 0:
            return True
    
    return False


def check_massive_operation(controller, operation_type, model_name, tool_name, user_id, records_count=1, time_window_seconds=60):
    """
    Detecta si una operaci├│n es parte de una operaci├│n masiva (m├║ltiples llamadas sucesivas).
    Usa locks de base de datos para serializar el acceso y evitar condiciones de carrera.
    
    :param controller: Instancia del controlador
    :param operation_type: Tipo de operaci├│n ('create', 'write', 'unlink')
    :param model_name: Nombre del modelo
    :param tool_name: Nombre de la herramienta MCP
    :param user_id: ID del usuario
    :param records_count: N├║mero de registros de esta operaci├│n individual
    :param time_window_seconds: Ventana de tiempo en segundos para considerar operaciones agrupadas (default: 60)
    :return: tuple (is_massive, total_records, pending_operations)
        - is_massive: True si es una operaci├│n masiva
        - total_records: Total de registros acumulados en la ventana de tiempo
        - pending_operations: Lista de operaciones pendientes en la ventana
    """
    # Obtener entorno con superusuario
    env_su = request.env(user=SUPERUSER_ID)
    verification_model = env_su['ai.safe.operation']
    
    # Calcular fecha l├¡mite (ahora - ventana de tiempo)
    time_limit = fields.Datetime.now() - timedelta(seconds=time_window_seconds)
    
    # SERIALIZACI├ôN: Usar SELECT FOR UPDATE para lockear las filas y evitar condiciones de carrera
    # SELECT FOR UPDATE bloquea las filas seleccionadas hasta que la transacci├│n termine,
    # asegurando que solo un proceso a la vez pueda leer y procesar las verificaciones pendientes.
    # 
    # IMPORTANTE - LIBERACI├ôN AUTOM├üTICA:
    # Los locks de SELECT FOR UPDATE se liberan autom├íticamente cuando la transacci├│n termina:
    # - Al confirmar una operaci├│n: Odoo hace commit de la transacci├│n HTTP ÔåÆ lock liberado
    # - Al cancelar una operaci├│n: Odoo hace commit de la transacci├│n HTTP ÔåÆ lock liberado
    # - Al expirar tokens/per├¡odos: auto_cancel_expired_periods hace commit ÔåÆ lock liberado
    # - En caso de error: Odoo hace rollback autom├ítico ÔåÆ lock liberado
    # 
    # No es necesario liberar los locks manualmente, Odoo lo gestiona autom├íticamente.
    try:
        # Usar SELECT FOR UPDATE NOWAIT para evitar deadlocks, con reintento si es necesario
        # Si otra transacci├│n tiene el lock, esperar un momento y reintentar
        max_retries = 3
        retry_delay = 0.1  # 100ms
        locked_ids = []
        
        for attempt in range(max_retries):
            try:
                env_su.cr.execute("""
                    SELECT id FROM pns_ai_mcp_safe_operation
                    WHERE user_id = %s
                      AND model_name = %s
                      AND operation_type = %s
                      AND tool_name = %s
                      AND create_date >= %s
                      AND status IN ('pending', 'confirmed')
                    ORDER BY create_date DESC
                    FOR UPDATE NOWAIT
                """, (user_id, model_name, operation_type, tool_name, time_limit))
                
                locked_ids = [row[0] for row in env_su.cr.fetchall()]
                break  # ├ëxito, salir del bucle de reintentos
            except Exception as lock_error:
                if 'could not obtain lock' in str(lock_error).lower() or 'lock_not_available' in str(lock_error).lower():
                    if attempt < max_retries - 1:
                        # Esperar un momento antes de reintentar
                        import time
                        time.sleep(retry_delay * (attempt + 1))  # Backoff exponencial
                        continue
                    else:
                        # ├Ültimo intento fallido, usar b├║squeda normal sin lock
                        _logger.warning(f"MCP: No se pudo obtener lock despu├®s de {max_retries} intentos, usando b├║squeda normal: {lock_error}")
                        raise
                else:
                    # Otro tipo de error, propagar
                    raise
        
        # Buscar operaciones recientes usando los IDs bloqueados
        # Esto asegura que estamos trabajando con datos consistentes
        if locked_ids:
            recent_operations = verification_model.browse(locked_ids)
        else:
            recent_operations = verification_model.browse([])
    except Exception as e:
        # Si falla el lock despu├®s de reintentos, usar b├║squeda normal (fallback)
        # Esto puede ocurrir en casos extremos de concurrencia
        _logger.warning(f"MCP: Error obteniendo lock para verificaci├│n masiva, usando b├║squeda normal: {e}")
        recent_operations = verification_model.search([
            ('user_id', '=', user_id),
            ('model_name', '=', model_name),
            ('operation_type', '=', operation_type),
            ('tool_name', '=', tool_name),
            ('create_date', '>=', time_limit),
            ('status', 'in', ['pending', 'confirmed'])
        ], order='create_date desc')
    
    # Filtrar solo las pendientes para agrupar
    # IMPORTANTE: Excluir verificaciones masivas ya agrupadas para evitar duplicar el conteo
    # Las verificaciones masivas tienen operation_data con 'massive_operation': True
    pending_operations = recent_operations.filtered(lambda op: op.status == 'pending')
    
    # Filtrar verificaciones masivas ya agrupadas (para no contarlas como individuales)
    # IMPORTANTE: No usar total_records de verificaciones masivas porque ya incluyen operaciones anteriores
    # En su lugar, extraer todas las operaciones individuales y contarlas
    def extract_all_individual_operations_count(op_data_item):
        """Cuenta las operaciones individuales en una estructura de datos
        
        IMPORTANTE: El array 'operations' de una verificaci├│n masiva contiene
        las operaciones anteriores extra├¡das. La operaci├│n actual (arguments, event_info_preview)
        se a├▒ade despu├®s, as├¡ que el total es: len(operations) + 1 (operaci├│n actual)
        """
        count = 0
        if isinstance(op_data_item, dict):
            if op_data_item.get('massive_operation') and 'operations' in op_data_item:
                # Es masiva CON array operations: contar operaciones del array + 1 (operaci├│n actual)
                # El array operations contiene las operaciones anteriores
                # La operaci├│n actual (arguments, event_info_preview) se cuenta por separado
                nested_ops = op_data_item.get('operations', [])
                count = len(nested_ops) + 1  # Array operations + operaci├│n actual
            elif op_data_item.get('massive_operation') and 'operations' not in op_data_item:
                # Es masiva PERO sin array operations (primera verificaci├│n masiva): contar como 1
                current_op = {k: v for k, v in op_data_item.items() 
                            if k not in ('massive_operation', 'pending_verification_ids', 'total_records', 'first_verification_id')}
                if current_op:
                    count = 1
            else:
                # Es individual: contar como 1
                count = 1
        else:
            # No es dict, contar como 1
            count = 1
        return count
    
    individual_pending_operations = []
    all_pending_operations = []  # Incluir todas (individuales y masivas) para extraer operaciones
    total_individual_ops = 0  # Contador de operaciones individuales extra├¡das
    
    for op in pending_operations:
        is_massive_op = False
        if op.operation_data:
            try:
                op_data = json.loads(op.operation_data) if isinstance(op.operation_data, str) else op.operation_data
                if isinstance(op_data, dict) and op_data.get('massive_operation'):
                    is_massive_op = True
                    # Extraer y contar todas las operaciones individuales de esta verificaci├│n masiva
                    total_individual_ops += extract_all_individual_operations_count(op_data)
                else:
                    # Es individual, contar como 1
                    total_individual_ops += 1
            except:
                # Si hay error, contar como 1 (operaci├│n individual)
                total_individual_ops += 1
        
        # Todas las operaciones pendientes se incluyen para extraer operaciones individuales
        all_pending_operations.append(op)
        
        # Solo las individuales se marcan como individuales (las masivas se extraer├ín recursivamente)
        if not is_massive_op:
            individual_pending_operations.append(op)
    
    # Calcular total de registros acumulados
    # Usar el conteo de operaciones individuales extra├¡das + la operaci├│n actual
    total_records = total_individual_ops + records_count
    
    # Es masiva si hay operaciones pendientes (individuales o masivas) del mismo tipo
    # Esto indica que hay un patr├│n de operaciones masivas en curso
    # Las operaciones confirmadas no cuentan porque ya se ejecutaron
    is_massive = len(pending_operations) > 0
    
    # Usar todas las operaciones pendientes (individuales y masivas) para el retorno
    # La funci├│n recursiva se encargar├í de extraer todas las operaciones individuales
    pending_operations = all_pending_operations
    
    return is_massive, total_records, pending_operations


def has_recent_operations(operation_type, model_name, tool_name, user_id, time_window_seconds=30):
    """
    Verifica si hay operaciones recientes (de cualquier estado) para detectar patrones masivos.
    """
    env_su = request.env(user=SUPERUSER_ID)
    verification_model = env_su['ai.safe.operation']
    time_limit = fields.Datetime.now() - timedelta(seconds=time_window_seconds)
    
    recent_count = verification_model.search_count([
        ('user_id', '=', user_id),
        ('model_name', '=', model_name),
        ('operation_type', '=', operation_type),
        ('tool_name', '=', tool_name),
        ('create_date', '>=', time_limit),
    ])
    
    return recent_count > 0


def record_direct_operation(operation_type, model_name, tool_name, user_id, records_count):
    """
    Registra una operaci├│n que se ejecut├│ directamente (sin verificaci├│n) para poder detectar patrones masivos.
    Crea una verificaci├│n con estado 'confirmed' inmediatamente para rastrear el patr├│n.
    """
    try:
        env_su = request.env(user=SUPERUSER_ID)
        verification_model = env_su['ai.safe.operation']
        
        # Crear una verificaci├│n marcada como confirmada inmediatamente
        # Esto permite detectar el patr├│n en operaciones posteriores
        verification = verification_model.create({
            'operation_type': operation_type,
            'model_name': model_name,
            'records_count': records_count,
            'changes_info': json.dumps({'direct_execution': True}),
            'user_id': user_id,
            'tool_name': tool_name,
            'operation_data': json.dumps({'direct_execution': True}),
            'status': 'confirmed',  # Marcar como confirmada inmediatamente
            'resolved_at': fields.Datetime.now(),
        })
    except Exception as e:
        # Si falla el registro, no es cr├¡tico, solo logging
        _logger.warning(f"MCP: Error registrando operaci├│n directa: {e}")


def cancel_pending_verifications_for_user(user_id, reason="falta de permisos"):
    """
    Cancela autom├íticamente todas las verificaciones pendientes de un usuario
    dentro de la ventana de cancelaci├│n (CANCELATION_PERIOD_SECONDS).
    
    :param user_id: ID del usuario
    :param reason: Raz├│n de la cancelaci├│n (para logging)
    """
    try:
        env_su = request.env(user=SUPERUSER_ID)
        verification_model = env_su['ai.safe.operation']
        from odoo.addons.pns_ai_mcp.constants import PIN_EXPIRY_MINUTES
        
        time_limit = fields.Datetime.now() - timedelta(minutes=PIN_EXPIRY_MINUTES)
        pending_verifications = verification_model.search([
            ('user_id', '=', user_id),
            ('status', '=', 'pending'),
            ('create_date', '>=', time_limit),
        ])
        
        if pending_verifications:
            now = fields.Datetime.now()
            pending_verifications.write({
                'status': 'cancelled',
                'resolved_at': now
            })
            _logger.info(f"MCP: Canceladas autom├íticamente {len(pending_verifications)} verificaci├│n(es) pendiente(s) por {reason}")
            return len(pending_verifications)
    except Exception as e:
        _logger.warning(f"MCP: Error cancelando verificaciones pendientes: {e}")
    return 0

