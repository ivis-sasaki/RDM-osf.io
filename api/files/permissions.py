from rest_framework import permissions

from api.base.utils import get_user_auth
from osf.models import BaseFileNode
from api.preprints.permissions import PreprintPublishedOrAdmin

class CheckedOutOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        assert isinstance(obj, BaseFileNode), 'obj must be a BaseFileNode, got {}'.format(obj)

        if request.method in permissions.SAFE_METHODS:
            return True

        auth = get_user_auth(request)
        # Limited to osfstorage for the moment
        if obj.provider != 'osfstorage':
            return False
        return obj.checkout is None \
            or obj.checkout == auth.user \
            or obj.target.has_permission(auth.user, 'admin')


class IsPreprintFile(PreprintPublishedOrAdmin):
    def has_object_permission(self, request, view, obj):
        assert isinstance(obj, BaseFileNode), 'obj must be a BaseFileNode, got {}'.format(obj)
        if (hasattr(obj.target, 'primary_file') and obj.target.primary_file == obj):
            if request.method == 'DELETE' and not obj.target._has_abandoned_preprint:
                return False

            # If object is a primary_file on a preprint, need PreprintPublishedOrAdmin permissions to view
            return super(IsPreprintFile, self).has_object_permission(request, view, obj.target)

        return True
