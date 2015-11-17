
from rest_framework import status
from rest_framework.response import Response
from rest_framework_bulk import generics as bulk_generics
from rest_framework.exceptions import PermissionDenied, ValidationError

from website.project.model import Q
from api.base.settings import BULK_SETTINGS
from api.base.exceptions import Conflict, JSONAPIException
from api.base.utils import is_bulk_request


class ListBulkCreateJSONAPIView(bulk_generics.ListBulkCreateAPIView):
    """
    Custom ListBulkCreateAPIView that properly formats bulk create responses
    in accordance with the JSON API spec
    """

    # overrides ListBulkCreateAPIView
    def create(self, request, *args, **kwargs):
        """
        Correctly formats both bulk and single POST response
        """
        if is_bulk_request(request):
            if not request.data:
                raise ValidationError('Request must contain array of resource identifier objects.')

        response = super(ListBulkCreateJSONAPIView, self).create(request, *args, **kwargs)
        if 'data' not in response.data:
            response.data = {'data': response.data}
        return response

    # overrides ListBulkCreateAPIView
    def get_serializer(self, *args, **kwargs):
        """
        Adds many=True to serializer if bulk operation.
        """

        if is_bulk_request(self.request):
            kwargs['many'] = True

        return super(ListBulkCreateJSONAPIView, self).get_serializer(*args, **kwargs)


class BulkUpdateJSONAPIView(bulk_generics.BulkUpdateAPIView):
    """
    Custom BulkUpdateAPIView that properly formats bulk update responses in accordance with
    the JSON API spec
    """

    # overrides BulkUpdateAPIView
    def bulk_update(self, request, *args, **kwargs):
        """
        Correctly formats bulk PUT/PATCH response
        """
        if not request.data:
            raise ValidationError('Request must contain array of resource identifier objects.')

        response = super(BulkUpdateJSONAPIView, self).bulk_update(request, *args, **kwargs)
        meta = {}
        if 'errors' in response.data[1]:
            meta = response.data.pop(-1)
        response.data = {'data': response.data, 'meta': meta}
        return response


class BulkDestroyJSONAPIView(bulk_generics.BulkDestroyAPIView):
    """
    Custom BulkDestroyAPIView that handles validation and permissions for
    bulk delete
    """
    def get_requested_resources(self, request):
        """
        Retrieves resources in request body
        """
        model_cls = request.parser_context['view'].model_class
        requested_ids = [data['id'] for data in request.data]
        resource_object_list = model_cls.find(Q('_id', 'in', requested_ids))

        if len(resource_object_list) != len(request.data):
            raise ValidationError({'non_field_errors': 'Could not find all objects to delete.'})

        return resource_object_list

    def allow_bulk_destroy_resources(self, user, resource_list):
        """
        Ensures user has permission to bulk delete resources in request body. Override if not deleting relationships.
        """
        return True

    # Overrides BulkDestroyAPIView
    def bulk_destroy(self, request, *args, **kwargs):
        """
        Handles bulk destroy of resource objects.

        Handles some validation and enforces bulk limit.
        """
        num_items = len(request.data)
        bulk_limit = BULK_SETTINGS['DEFAULT_BULK_LIMIT']

        if num_items > bulk_limit:
            raise JSONAPIException(source={'pointer': '/data'},
                                   detail='Bulk operation limit is {}, got {}.'.format(bulk_limit, num_items))

        user = self.request.user
        object_type = self.serializer_class.Meta.type_

        if not request.data:
            raise ValidationError('Request must contain array of resource identifier objects.')

        resource_object_list = self.get_requested_resources(request)

        for item in request.data:
            item_type = item[u'type']
            if item_type != object_type:
                raise Conflict()

        if not self.allow_bulk_destroy_resources(user, resource_object_list):
            raise PermissionDenied

        self.perform_bulk_destroy(resource_object_list)

        return Response(status=status.HTTP_204_NO_CONTENT)
