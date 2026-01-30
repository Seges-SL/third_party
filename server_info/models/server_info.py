from odoo import api, fields, models, _
import logging
import psutil
import netifaces as ni
import socket

_logger = logging.getLogger(__name__)


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def _get_best_interface(self):
        """
        Detecta la interfaz de red principal automáticamente.
        Prioridad:
        1. La interfaz usada por la puerta de enlace predeterminada (Gateway).
        2. 'eth0' (Estándar Docker).
        3. 'ens3' (Tu estándar antiguo).
        4. La primera que no sea localhost.
        """
        try:
            # 1. Intentar obtener la interfaz del Default Gateway (La más fiable)
            gws = ni.gateways()
            default_gw = gws.get('default', {})
            # ni.AF_INET es la conexión IPv4 estándar
            if ni.AF_INET in default_gw:
                return default_gw[ni.AF_INET][1]
        except Exception:
            pass

        # 2. Lista de candidatos comunes si falla el gateway
        candidates = ['eth0', 'ens3', 'ens33', 'enp3s0', 'wlan0']
        available_ifaces = ni.interfaces()
        
        for cand in candidates:
            if cand in available_ifaces:
                return cand

        # 3. Último recurso: Primera interfaz que no sea localhost ('lo')
        for iface in available_ifaces:
            if iface != 'lo':
                return iface
        
        return None

    def session_info(self):
        result = super(IrHttp, self).session_info()

        try:
            # Busca la frecuencia, si falla usa fallback
            settings = self.env['res.config.settings'].search_read([], ['update_frequency'])
            if settings:
                result['interval'] = settings[-1]['update_frequency']
            else:
                result['interval'] = 5000
        except Exception as ex:
            _logger.error(f"Error reading settings: {ex}")
            result['interval'] = 5000

        # --- CPU ---
        try:
            result['cpu_usage'] = f'{psutil.cpu_percent()} %'
            result['cpu_count'] = psutil.cpu_count()
        except Exception:
            result['cpu_usage'] = "N/A"
            result['cpu_count'] = 0

        # --- MEMORY ---
        try:
            mem_info = psutil.virtual_memory()
            result['mem_total'] = f'{(mem_info.total/(1024*1024*1024)):.2f} GB'
            result['mem_used'] = f'{(mem_info.used/(1024*1024*1024)):.2f} GB'
            result['mem_used_percent'] = f'{mem_info.percent} %'
            result['mem_free'] = f'{(mem_info.free/(1024*1024)):.0f} Mb'
        except Exception:
            result['mem_total'] = "N/A"

        # --- DISK ---
        try:
            disk_mem_info = psutil.disk_usage('/')
            result['disk_mem_total'] = f'{(disk_mem_info.total/(1024*1024*1024)):.2f} GB'
            result['disk_mem_used'] = f'{(disk_mem_info.used/(1024*1024*1024)):.2f} GB'
            result['disk_mem_used_percent'] = f'{disk_mem_info.percent} %'
            result['disk_mem_free'] = f'{(disk_mem_info.free/(1024*1024*1024)):.2f} GB'
        except Exception:
            result['disk_mem_total'] = "N/A"

        # --- NETWORK (La parte crítica corregida) ---
        target_iface = self._get_best_interface()
        
        # IPv4
        try:
            if target_iface:
                ip4_info = ni.ifaddresses(target_iface)[ni.AF_INET][0]['addr']
                result['ip4_info'] = f'{ip4_info}'
            else:
                result['ip4_info'] = "No Interface"
        except Exception:
             result['ip4_info'] = "N/A"

        # IPv6 (En Docker suele fallar o estar desactivado, así que lo protegemos)
        try:
            if target_iface and ni.AF_INET6 in ni.ifaddresses(target_iface):
                ip6_info = ni.ifaddresses(target_iface)[ni.AF_INET6][0]['addr']
                result['ip6_info'] = f'{ip6_info}'
            else:
                result['ip6_info'] = "IPv6 Disabled"
        except Exception:
            result['ip6_info'] = "N/A"

        return result


class ServerInfoSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def _get_current_frequency(self):
        try:
            settings = self.env['res.config.settings'].search_read([], ['update_frequency'])
            if settings:
                return settings[-1]['update_frequency']
        except Exception as ex:
            _logger.error(f"Error getting frequency: {ex}")
        return '5000'
    
    def _get_host_name(self):
        try:
            host_name = self.env['ir.config_parameter'].get_param('host_name')
            if host_name:
                return f'La dirección IP de {host_name} es {socket.gethostbyname(host_name)}'
        except Exception as ex:
            _logger.error(f"Error getting hostname: {ex}")
        return ''

    update_frequency = fields.Selection(
        string='Time between updates',
        help='This value sets time between Server Info updates.',
        selection=[
            ('1000', '1 Sec'),
            ('2000', '2 Sec'),
            ('5000', '5 Sec'),
            ('10000', '10 Sec'),
            ('30000', '30 Sec'),
            ('60000', '1 Min'),
            ('300000', '5 Min')
        ],
        default=_get_current_frequency,
        required=True
    )
    host_name = fields.Char(
        default=_get_host_name,
        readonly=True
    )