# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2021-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
import datetime
import errno
import ftplib
import json
import logging
import os
import tempfile
from datetime import timedelta

import paramiko
import requests
from requests.auth import HTTPBasicAuth
from werkzeug import urls

import odoo
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.service import db

_logger = logging.getLogger(__name__)

GOOGLE_AUTH_ENDPOINT = 'https://accounts.google.com/o/oauth2/auth'
GOOGLE_TOKEN_ENDPOINT = 'https://accounts.google.com/o/oauth2/token'
GOOGLE_API_BASE_URL = 'https://www.googleapis.com'

class AutoDatabaseBackup(models.Model):
    _name = 'db.backup.configure'
    _description = 'Automatic Database Backup'

    name = fields.Char(string='Name', required=True)
    db_name = fields.Char(string='Database Name', required=True)
    master_pwd = fields.Char(string='Master Password', required=True)
    backup_format = fields.Selection([
        ('zip', 'Zip'),
        ('dump', 'Dump')
    ], string='Backup Format', default='zip', required=True)
    backup_destination = fields.Selection([
        ('local', 'Local Storage'),
        ('google_drive', 'Google Drive'),
        ('ftp', 'FTP'),
        ('sftp', 'SFTP')
    ], string='Backup Destination')
    backup_path = fields.Char(string='Backup Path', help='Local storage directory path')
    sftp_host = fields.Char(string='SFTP Host')
    sftp_port = fields.Char(string='SFTP Port', default=22)
    sftp_user = fields.Char(string='SFTP User')
    sftp_password = fields.Char(string='SFTP Password')
    sftp_path = fields.Char(string='SFTP Path')
    ftp_host = fields.Char(string='FTP Host')
    ftp_port = fields.Char(string='FTP Port', default=21)
    ftp_user = fields.Char(string='FTP User')
    ftp_password = fields.Char(string='FTP Password')
    ftp_path = fields.Char(string='FTP Path')
    active = fields.Boolean(default=True)
    save_to_drive = fields.Boolean()
    auto_remove = fields.Boolean(string='Remove Old Backups')
    days_to_remove = fields.Integer(string='Remove After',
                                    help='Automatically delete stored backups after this specified number of days')
    google_drive_folder_key = fields.Char(string='Drive Folder ID')
    gdrive_refresh_token = fields.Char(string='Google drive Refresh Token',
                                       copy=False,
                                       help='Refresh token for google drive')
    gdrive_access_token = fields.Char(string='Google Drive Access Token',
                                      copy=False,
                                      help='Access token for google drive')
    is_google_drive_token_generated = fields.Boolean(
        string='Google drive Token Generated',
        compute='_compute_is_google_drive_token_generated', copy=False,
        help='Google drive token generated or not')
    gdrive_client_key = fields.Char(string='Google Drive Client ID', copy=False,
                                    help='Client id of the google drive')
    gdrive_client_secret = fields.Char(string='Google Drive Client Secret',
                                       copy=False,
                                       help='Client secret id of the google'
                                            ' drive')
    gdrive_token_validity = fields.Datetime(
        string='Google Drive Token Validity', copy=False,
        help='Token validity of the google drive')
    gdrive_redirect_uri = fields.Char(string='Google Drive Redirect URI',
                                      compute='_compute_redirect_uri',
                                      help='Redirect URI of the google drive')
    notify_user = fields.Boolean(string='Notify User',
                                 help='Send an email notification to user when the backup operation is successful or failed')
    user_id = fields.Many2one('res.users', string='User')
    backup_filename = fields.Char(string='Backup Filename', help='For Storing generated backup filename')
    generated_exception = fields.Char(string='Exception', help='Exception Encountered while Backup generation')
    gdrive_backup_error_test = fields.Boolean(string="Google Drive Error Test")

    @api.onchange('backup_destination')
    def _onchange_backup_destination(self):
        self.write({
            "gdrive_backup_error_test": False,
        })

    @api.onchange('gdrive_client_key', 'gdrive_client_secret',
                  'google_drive_folder')
    def _onchange_gdrive_backup_error_test(self):
        if self.backup_destination == 'google_drive':
            if self.gdrive_backup_error_test:
                self.write({
                    "gdrive_backup_error_test": False
                })


    def _compute_redirect_uri(self):
        """Compute the redirect URI Google Drive"""
        for rec in self:
            base_url = request.env['ir.config_parameter'].get_param(
                'web.base.url')
            rec.gdrive_redirect_uri = base_url + '/google_drive/authentication'

    @api.depends('gdrive_access_token', 'gdrive_refresh_token')
    def _compute_is_google_drive_token_generated(self):
        """Set True if the Google Drive refresh token is generated"""
        for rec in self:
            rec.is_google_drive_token_generated = bool(
                rec.gdrive_access_token) and bool(rec.gdrive_refresh_token)

    def action_get_gdrive_auth_code(self):
        """Generate google drive authorization code"""
        action = self.env.ref(
            "auto_database_backup.db_backup_configure_action")
        action_data = {
            'id': action.id,
            'name': action.name,
            'type': action.type,
            'xml_id': action.xml_id,
            'help': action.help,
            'binding_model_id': action.binding_model_id,
            'binding_type': action.binding_type,
            'binding_view_types': action.binding_view_types,
            'display_name': action.display_name,
            'res_model': action.res_model,
            'target': action.target,
            'view_mode': action.view_mode,
            'views': action.views,
            'groups_id': [(6, 0, action.groups_id.ids)],
            'search_view_id': action.search_view_id.id if action.search_view_id else False,
            'filter': action.filter,
            'search_view': action.search_view,
            'limit': action.limit,
        }
        base_url = request.env['ir.config_parameter'].get_param('web.base.url')
        url_return = base_url + \
                     '/web#id=%d&action=%d&view_type=form&model=%s' % (
                         self.id, action_data['id'], 'db.backup.configure')
        state = {
            'backup_config_id': self.id,
            'url_return': url_return
        }
        encoded_params = urls.url_encode({
            'response_type': 'code',
            'client_id': self.gdrive_client_key,
            'scope': 'https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/drive.file',
            'redirect_uri': base_url + '/google_drive/authentication',
            'access_type': 'offline',
            'state': json.dumps(state),
            'approval_prompt': 'force',
        })
        auth_url = "%s?%s" % (GOOGLE_AUTH_ENDPOINT, encoded_params)
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': auth_url,
        }
    
    def generate_gdrive_refresh_token(self):
        """Generate Google Drive access token from refresh token if expired"""
        headers = {"content-type": "application/x-www-form-urlencoded"}
        data = {
            'refresh_token': self.gdrive_refresh_token,
            'client_id': self.gdrive_client_key,
            'client_secret': self.gdrive_client_secret,
            'grant_type': 'refresh_token',
        }
        try:
            res = requests.post(GOOGLE_TOKEN_ENDPOINT, data=data,
                                headers=headers)
            res.raise_for_status()
            response = res.content and res.json() or {}
            if response:
                expires_in = response.get('expires_in')
                self.write({
                    'gdrive_access_token': response.get('access_token'),
                    'gdrive_token_validity': fields.Datetime.now() + timedelta(
                        seconds=expires_in) if expires_in else False,
                })
        except requests.HTTPError as error:
            error_key = error.response.json().get("error", "nc")
            error_msg = _(
                "An error occurred while generating the token. Your"
                "authorization code may be invalid or has already expired [%s]."
                "You should check your Client ID and secret on the Google APIs"
                " plateform or try to stop and restart your calendar"
                " synchronisation.",
                error_key)
            raise UserError(error_msg)

    def get_gdrive_tokens(self, authorize_code):
        """Generate onedrive tokens from authorization code."""
        base_url = request.env['ir.config_parameter'].get_param('web.base.url')
        headers = {"content-type": "application/x-www-form-urlencoded"}
        data = {
            'code': authorize_code,
            'client_id': self.gdrive_client_key,
            'client_secret': self.gdrive_client_secret,
            'grant_type': 'authorization_code',
            'redirect_uri': base_url + '/google_drive/authentication'
        }
        try:
            res = requests.post(GOOGLE_TOKEN_ENDPOINT, params=data,
                                headers=headers)
            res.raise_for_status()
            response = res.content and res.json() or {}
            if response:
                expires_in = response.get('expires_in')
                self.write({
                    'gdrive_access_token': response.get('access_token'),
                    'gdrive_refresh_token': response.get('refresh_token'),
                    'gdrive_token_validity': fields.Datetime.now() + timedelta(
                        seconds=expires_in) if expires_in else False,
                })
                if self.gdrive_backup_error_test:
                    self.write({
                        'gdrive_backup_error_test': False
                    })
        except Exception:
            if not self.gdrive_backup_error_test:
                self.write({"gdrive_backup_error_test": True})

    @api.constrains('db_name', 'master_pwd')
    def _check_db_credentials(self):
        """
        Validate enetered database name and master password
        """
        database_list = db.list_dbs()
        if self.db_name not in database_list:
            raise ValidationError(_("Invalid Database Name!"))
        try:
            odoo.service.db.check_super(self.master_pwd)
        except Exception:
            raise ValidationError(_("Invalid Master Password!"))

    def test_connection(self):
        """
        Test the sftp and ftp connection using entered credentials
        """
        if self.backup_destination == 'sftp':
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                client.connect(hostname=self.sftp_host, username=self.sftp_user, password=self.sftp_password, port=self.sftp_port)
                sftp = client.open_sftp()
                sftp.close()
            except Exception as e:
                raise UserError(_("SFTP Exception: %s", e))
            finally:
                client.close()
        elif self.backup_destination == 'ftp':
            try:
                ftp_server = ftplib.FTP()
                ftp_server.connect(self.ftp_host, int(self.ftp_port))
                ftp_server.login(self.ftp_user, self.ftp_password)
                ftp_server.quit()
            except Exception as e:
                raise UserError(_("FTP Exception: %s", e))
        title = _("Connection Test Succeeded!")
        message = _("Everything seems properly set up!")
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'sticky': False,
            }
        }

    def _schedule_auto_backup(self):
        """
        Function for generating and storing backup
        Database backup for all the active records in backup configuration model will be created
        """
        records = self.search([])
        mail_template_success = self.env.ref('auto_database_backup.mail_template_data_db_backup_successful')
        mail_template_failed = self.env.ref('auto_database_backup.mail_template_data_db_backup_failed')
        for rec in records:
            backup_time = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
            backup_filename = "%s_%s.%s" % (rec.db_name, backup_time, rec.backup_format)
            rec.backup_filename = backup_filename
            # Local backup
            if rec.backup_destination == 'local':
                try:
                    if not os.path.isdir(rec.backup_path):
                        os.makedirs(rec.backup_path)
                    backup_file = os.path.join(rec.backup_path, backup_filename)
                    f = open(backup_file, "wb")
                    odoo.service.db.dump_db(rec.db_name, f, rec.backup_format)
                    f.close()
                    # remove older backups
                    if rec.auto_remove:
                        for filename in os.listdir(rec.backup_path):
                            file = os.path.join(rec.backup_path, filename)
                            create_time = datetime.datetime.fromtimestamp(os.path.getctime(file))
                            backup_duration = datetime.datetime.utcnow() - create_time
                            if backup_duration.days >= rec.days_to_remove:
                                os.remove(file)
                    if rec.notify_user:
                        mail_template_success.send_mail(rec.id, force_send=True)
                except Exception as e:
                    rec.generated_exception = e
                    _logger.info('FTP Exception: %s', e)
                    if rec.notify_user:
                        mail_template_failed.send_mail(rec.id, force_send=True)
            # FTP backup
            elif rec.backup_destination == 'ftp':
                try:
                    ftp_server = ftplib.FTP()
                    ftp_server.connect(rec.ftp_host, int(rec.ftp_port))
                    ftp_server.login(rec.ftp_user, rec.ftp_password)
                    ftp_server.encoding = "utf-8"
                    temp = tempfile.NamedTemporaryFile(suffix='.%s' % rec.backup_format)
                    try:
                        ftp_server.cwd(rec.ftp_path)
                    except ftplib.error_perm:
                        ftp_server.mkd(rec.ftp_path)
                        ftp_server.cwd(rec.ftp_path)
                    with open(temp.name, "wb+") as tmp:
                        odoo.service.db.dump_db(rec.db_name, tmp, rec.backup_format)
                    ftp_server.storbinary('STOR %s' % backup_filename, open(temp.name, "rb"))
                    if rec.auto_remove:
                        files = ftp_server.nlst()
                        for f in files:
                            create_time = datetime.datetime.strptime(ftp_server.sendcmd('MDTM ' + f)[4:], "%Y%m%d%H%M%S")
                            diff_days = (datetime.datetime.now() - create_time).days
                            if diff_days >= rec.days_to_remove:
                                ftp_server.delete(f)
                    ftp_server.quit()
                    if rec.notify_user:
                        mail_template_success.send_mail(rec.id, force_send=True)
                except Exception as e:
                    rec.generated_exception = e
                    _logger.info('FTP Exception: %s', e)
                    if rec.notify_user:
                        mail_template_failed.send_mail(rec.id, force_send=True)
            # SFTP backup
            elif rec.backup_destination == 'sftp':
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                try:
                    client.connect(hostname=rec.sftp_host, username=rec.sftp_user, password=rec.sftp_password, port=rec.sftp_port)
                    sftp = client.open_sftp()
                    temp = tempfile.NamedTemporaryFile(suffix='.%s' % rec.backup_format)
                    with open(temp.name, "wb+") as tmp:
                        odoo.service.db.dump_db(rec.db_name, tmp, rec.backup_format)
                    try:
                        sftp.chdir(rec.sftp_path)
                    except IOError as e:
                        if e.errno == errno.ENOENT:
                            sftp.mkdir(rec.sftp_path)
                            sftp.chdir(rec.sftp_path)
                    sftp.put(temp.name, backup_filename)
                    if rec.auto_remove:
                        files = sftp.listdir()
                        expired = list(filter(lambda fl: (datetime.datetime.now() - datetime.datetime.fromtimestamp(sftp.stat(fl).st_mtime)).days >= rec.days_to_remove, files))
                        for file in expired:
                            sftp.unlink(file)
                    sftp.close()
                    if rec.notify_user:
                        mail_template_success.send_mail(rec.id, force_send=True)
                except Exception as e:
                    rec.generated_exception = e
                    _logger.info('SFTP Exception: %s', e)
                    if rec.notify_user:
                        mail_template_failed.send_mail(rec.id, force_send=True)
                finally:
                    client.close()
            # Google Drive backup
            elif rec.backup_destination == 'google_drive':
                try:
                    if rec.gdrive_token_validity <= fields.Datetime.now():
                        rec.generate_gdrive_refresh_token()
                    temp = tempfile.NamedTemporaryFile(
                        suffix='.%s' % rec.backup_format)
                    with open(temp.name, "wb+") as tmp:
                        odoo.service.db.dump_db(rec.db_name, tmp,
                                                rec.backup_format)
                    try:
                        headers = {
                            "Authorization": "Bearer %s" % rec.gdrive_access_token}
                        para = {
                            "name": backup_filename,
                            "parents": [rec.google_drive_folder_key],
                        }
                        files = {
                            'data': ('metadata', json.dumps(para),
                                     'application/json; charset=UTF-8'),
                            'file': open(temp.name, "rb")
                        }
                        _logger.info('before requests.post')
                        requests.post(
                            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
                            headers=headers,
                            files=files
                        )
                        _logger.info('requests.post')
                        if rec.auto_remove:
                            query = "parents = '%s'" % rec.google_drive_folder_key
                            files_req = requests.get(
                                "https://www.googleapis.com/drive/v3/files?q=%s" % query,
                                headers=headers)
                            files = files_req.json()['files']
                            _logger.info('requests.get')
                            for file in files:
                                file_date_req = requests.get(
                                    "https://www.googleapis.com/drive/v3/files/%s?fields=createdTime" %
                                    file['id'], headers=headers)
                                _logger.info('requests.get_createdTime')
                                create_time = file_date_req.json()[
                                                  'createdTime'][
                                              :19].replace('T', ' ')
                                diff_days = (
                                        fields.datetime.now() - fields.datetime.strptime(
                                    create_time, '%Y-%m-%d %H:%M:%S')).days
                                if diff_days >= rec.days_to_remove:
                                    requests.delete(
                                        "https://www.googleapis.com/drive/v3/files/%s" %
                                        file['id'], headers=headers)
                                    _logger.info('requests.delete')
                        if rec.notify_user:
                            mail_template_success.send_mail(rec.id,
                                                            force_send=True)
                    except Exception as e:
                        rec.generated_exception = e
                        _logger.info('Google Drive Exception: %s', e)
                        if rec.notify_user:
                            mail_template_failed.send_mail(rec.id,
                                                           force_send=True)
                except Exception:
                    if rec.notify_user:
                        mail_template_failed.send_mail(rec.id, force_send=True)
                        raise ValidationError(
                            'Please check the credentials before activation')
                    else:
                        raise ValidationError('Please check connection')
