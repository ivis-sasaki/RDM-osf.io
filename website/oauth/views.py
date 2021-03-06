# -*- coding: utf-8 -*-

import httplib as http

from flask import redirect, request

from framework.auth.decorators import must_be_logged_in
from framework.exceptions import HTTPError, PermissionsError
from framework.sessions import session
from osf.models import ExternalAccount
from website.oauth.utils import get_service
from website.oauth.signals import oauth_complete
from admin.rdm_addons.utils import validate_rdm_addons_allowed


@must_be_logged_in
def oauth_disconnect(external_account_id, auth):
    account = ExternalAccount.load(external_account_id)
    user = auth.user

    if account is None:
        raise HTTPError(http.NOT_FOUND)

    if not user.external_accounts.filter(id=account.id).exists():
        raise HTTPError(http.FORBIDDEN)

    # iterate AddonUserSettings for addons
    for user_settings in user.get_oauth_addons():
        if user_settings.oauth_provider.short_name == account.provider:
            user_settings.revoke_oauth_access(account)
            user_settings.save()

    # ExternalAccount.delete(account)
    # # only after all addons have been dealt with can we remove it from the user
    user.external_accounts.remove(account)
    user.save()

@must_be_logged_in
def oauth_connect(service_name, auth):
    try:
        validate_rdm_addons_allowed(auth, service_name)
    except PermissionsError as e:
        raise HTTPError(
            http.FORBIDDEN,
            data=dict(message_long=e.message)
        )

    service = get_service(service_name)

    return redirect(service.auth_url)


@must_be_logged_in
def osf_oauth_callback(service_name, auth):
    try:
        validate_rdm_addons_allowed(auth, service_name)
    except PermissionsError as e:
        raise HTTPError(
            http.FORBIDDEN,
            data=dict(message_long=e.message)
        )

    user = auth.user
    provider = get_service(service_name)

    # Retrieve permanent credentials from provider
    if not provider.auth_callback(user=user):
        return {}

    if provider.account and not user.external_accounts.filter(id=provider.account.id).exists():
        user.external_accounts.add(provider.account)
        user.save()

    oauth_complete.send(provider, account=provider.account, user=user)

    return {}

def oauth_callback(service_name):
    try:
        session_oauth_state = session.data['oauth_states'][service_name]['state']
    except KeyError:
        session_oauth_state = None

    request_oauth_state = request.args.get('state')
    if session_oauth_state is not None and request_oauth_state is not None and \
            session_oauth_state in request_oauth_state:
        # Request was created from web
        return osf_oauth_callback(service_name)

    # Not from web, so let's consider it was from admin
    return redirect(osfadmin_oauth_callback(service_name))

def osfadmin_oauth_callback(service_name):
    from furl import furl
    from website.settings import ADMIN_URL
    f = furl(ADMIN_URL)
    f.path = '/addons/oauth/callback/{}/'.format(service_name)
    f.args = request.args.to_dict(flat=False)
    return f.url
