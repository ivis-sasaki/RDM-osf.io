# -*- coding: utf-8 -*-
"""Various node-related utilities."""
from django.apps import apps
from django.db.models import Q

from website import settings

from keen import KeenClient
from osf.models.layout_info import WidgetPosition

# Alias the project serializer

def serialize_node(*args, **kwargs):
    from website.project.views.node import _view_project
    return _view_project(*args, **kwargs)  # Not recommended practice

def recent_public_registrations(n=10):
    Registration = apps.get_model('osf.Registration')

    return Registration.objects.filter(
        is_public=True,
        is_deleted=False,
    ).filter(
        Q(Q(embargo__isnull=True) | ~Q(embargo__state='unapproved')) &
        Q(Q(retraction__isnull=True) | ~Q(retraction__state='approved'))
    ).get_roots().order_by('-registered_date')[:n]


def get_keen_activity():
    client = KeenClient(
        project_id=settings.KEEN['public']['project_id'],
        read_key=settings.KEEN['public']['read_key'],
    )

    node_pageviews = client.count(
        event_collection='pageviews',
        timeframe='this_7_days',
        group_by='node.id',
        filters=[
            {
                'property_name': 'node.id',
                'operator': 'exists',
                'property_value': True
            }
        ]
    )

    node_visits = client.count_unique(
        event_collection='pageviews',
        target_property='anon.id',
        timeframe='this_7_days',
        group_by='node.id',
        filters=[
            {
                'property_name': 'node.id',
                'operator': 'exists',
                'property_value': True
            }
        ]
    )

    return {'node_pageviews': node_pageviews, 'node_visits': node_visits}


def activity():
    """Generate analytics for most popular public projects and registrations.
    Called by `scripts/update_populate_projects_and_registrations`
    """
    Node = apps.get_model('osf.AbstractNode')
    popular_public_projects = []
    popular_public_registrations = []
    max_projects_to_display = settings.MAX_POPULAR_PROJECTS

    if settings.KEEN['public']['read_key']:
        keen_activity = get_keen_activity()
        node_visits = keen_activity['node_visits']

        node_data = [{'node': x['node.id'], 'views': x['result']} for x in node_visits]
        node_data.sort(key=lambda datum: datum['views'], reverse=True)

        node_data = [node_dict['node'] for node_dict in node_data]

        for nid in node_data:
            node = Node.load(nid)
            if node is None:
                continue
            if node.is_public and not node.is_registration and not node.is_deleted:
                if len(popular_public_projects) < max_projects_to_display:
                    popular_public_projects.append(node)
            elif node.is_public and node.is_registration and not node.is_deleted and not node.is_retracted:
                if len(popular_public_registrations) < max_projects_to_display:
                    popular_public_registrations.append(node)
            if len(popular_public_projects) >= max_projects_to_display and len(popular_public_registrations) >= max_projects_to_display:
                break

    # New and Noteworthy projects are updated manually
    new_and_noteworthy_projects = list(Node.objects.get(guids___id=settings.NEW_AND_NOTEWORTHY_LINKS_NODE, guids___id__isnull=False).nodes_pointer)

    return {
        'new_and_noteworthy_projects': new_and_noteworthy_projects,
        'recent_public_registrations': recent_public_registrations(),
        'popular_public_projects': popular_public_projects,
        'popular_public_registrations': popular_public_registrations
    }

def get_drawer_widget_position(nid,uid):
    wiz_list = []
    for x in WidgetPosition.objects.filter(node_id=nid, user_id =uid).order_by('widget_position'):
        wiz_list.append(
            { 'id': x.widget_id,
              'position': x.widget_position,
               'ul_id': x.ul_id
            }
        )
    return wiz_list

def get_widget_drawer_order(list_of_dict):
    left_list = []
    right_list = []
    for dict_item in list_of_dict:
        if dict_item['ul_id'] == 1:
            left_list.append(dict_item['id'].replace('li_',''))
        else:
            right_list.append(dict_item['id'].replace('li_',''))
    final_order_dict = {
        'left': left_list,
        'right': right_list
    }
    print(final_order_dict)
    return final_order_dict

