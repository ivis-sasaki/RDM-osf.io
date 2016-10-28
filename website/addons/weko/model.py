# -*- coding: utf-8 -*-
import httplib as http

from modularodm import fields

from framework.auth.decorators import Auth
from framework.exceptions import HTTPError

from website.addons.base import (
    AddonOAuthNodeSettingsBase, AddonOAuthUserSettingsBase, exceptions,
)
from website.addons.base import StorageAddonBase
from website.oauth.models import ExternalProvider

from website.addons.weko.client import connect_from_settings_or_401
from website.addons.weko.serializer import DataverseSerializer
from website.addons.weko.utils import DataverseNodeLogger
from website.addons.weko import settings as weko_settings


class WEKOProvider(ExternalProvider):
    """An alternative to `ExternalProvider` not tied to OAuth"""

    name = 'WEKO'
    short_name = 'weko'
    serializer = DataverseSerializer

    client_id = weko_settings.CLIENT_ID
    client_secret = weko_settings.CLIENT_SECRET

    auth_url_base = weko_settings.OAUTH_AUTHORIZE_URL
    callback_url = weko_settings.OAUTH_ACCESS_TOKEN_URL

    def handle_callback(self, response):
        """View called when the OAuth flow is completed.
        """
        return {
            'provider_id': 'test',
            'display_name': 'test'
        }


class AddonWEKOUserSettings(AddonOAuthUserSettingsBase):
    oauth_provider = WEKOProvider
    serializer = DataverseSerializer

class AddonWEKONodeSettings(StorageAddonBase, AddonOAuthNodeSettingsBase):
    oauth_provider = WEKOProvider
    serializer = DataverseSerializer

    weko_alias = fields.StringField()
    weko = fields.StringField()
    dataset_doi = fields.StringField()
    _dataset_id = fields.StringField()
    dataset = fields.StringField()

    _api = None

    @property
    def api(self):
        """authenticated ExternalProvider instance"""
        if self._api is None:
            self._api = WEKOProvider(self.external_account)
        return self._api

    @property
    def folder_name(self):
        return self.dataset

    @property
    def dataset_id(self):
        if self._dataset_id is None and (self.weko_alias and self.dataset_doi):
            connection = connect_from_settings_or_401(self)
            weko = connection.get_weko(self.weko_alias)
            dataset = weko.get_dataset_by_doi(self.dataset_doi)
            self._dataset_id = dataset.id
            self.save()
        return self._dataset_id

    @property
    def complete(self):
        return bool(self.has_auth and self.dataset_doi is not None)

    @property
    def folder_id(self):
        return self.dataset_id

    @property
    def folder_path(self):
        pass

    @property
    def nodelogger(self):
        # TODO: Use this for all log actions
        auth = None
        if self.user_settings:
            auth = Auth(self.user_settings.owner)
        return DataverseNodeLogger(
            node=self.owner,
            auth=auth
        )

    def set_folder(self, weko, dataset, auth=None):
        self.weko_alias = weko[1]
        self.weko = weko[1]

        self.dataset_doi = dataset['href']
        self._dataset_id = dataset['href']
        self.dataset = dataset['title']

        self.save()

        if auth:
            self.owner.add_log(
                action='weko_dataset_linked',
                params={
                    'project': self.owner.parent_id,
                    'node': self.owner._id,
                    'dataset': dataset['title'],
                },
                auth=auth,
            )

    def _get_fileobj_child_metadata(self, filenode, user, cookie=None, version=None):
        try:
            return super(AddonDataverseNodeSettings, self)._get_fileobj_child_metadata(filenode, user, cookie=cookie, version=version)
        except HTTPError as e:
            # The Dataverse API returns a 404 if the dataset has no published files
            if e.code == http.NOT_FOUND and version == 'latest-published':
                return []
            raise

    def clear_settings(self):
        """Clear selected Dataverse and dataset"""
        self.weko_alias = None
        self.weko = None
        self.dataset_doi = None
        self._dataset_id = None
        self.dataset = None

    def deauthorize(self, auth=None, add_log=True):
        """Remove user authorization from this node and log the event."""
        self.clear_settings()
        self.clear_auth()  # Also performs a save

        # Log can't be added without auth
        if add_log and auth:
            node = self.owner
            self.owner.add_log(
                action='weko_node_deauthorized',
                params={
                    'project': node.parent_id,
                    'node': node._id,
                },
                auth=auth,
            )

    def serialize_waterbutler_credentials(self):
        if not self.has_auth:
            raise exceptions.AddonError('Addon is not authorized')
        return {'token': self.external_account.oauth_key}

    def serialize_waterbutler_settings(self):
        if not self.folder_id:
            raise exceptions.AddonError('Dataverse is not configured')
        return {
            'host': self.external_account.oauth_key,
            'doi': self.dataset_doi,
            'id': self.dataset_id,
            'name': self.dataset,
        }

    def create_waterbutler_log(self, auth, action, metadata):
        url = self.owner.web_url_for('addon_view_or_download_file', path=metadata['path'], provider='weko')
        self.owner.add_log(
            'weko_{0}'.format(action),
            auth=auth,
            params={
                'project': self.owner.parent_id,
                'node': self.owner._id,
                'dataset': self.dataset,
                'filename': metadata['materialized'].strip('/'),
                'urls': {
                    'view': url,
                    'download': url + '?action=download'
                },
            },
        )

    ##### Callback overrides #####

    def after_delete(self, node, user):
        self.deauthorize(Auth(user=user), add_log=True)
        self.save()

    def on_delete(self):
        self.deauthorize(add_log=False)
        self.save()
