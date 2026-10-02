"""Native admin actions and history, persisted in the portal register."""
import json
from django.contrib.admin import AdminSite
from django.contrib.admin.utils import unquote
from django.contrib.admin.options import get_content_type_for_model
from django.contrib.admin.views.main import PAGE_VAR
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.utils.text import capfirst, get_text_list
from django.utils.translation import gettext
from .models import EventoCompromiso


class PortalAdminSite(AdminSite):
    def get_urls(self):
        from django.urls import path
        from functools import partial
        from .admin_estados import estado_admin
        routes = [
            path('compromisos/estado/', self.admin_view(partial(estado_admin, self)), name='compromisos_estado_changelist'),
            path('compromisos/estado/add/', self.admin_view(partial(estado_admin, self, action='add')), name='compromisos_estado_add'),
        ]
        for action in ['change', 'delete', 'history']:
            routes.append(path('compromisos/estado/<int:estado_id>/'+action+'/', self.admin_view(partial(estado_admin, self, action=action)), name='compromisos_estado_'+action))
        return routes + super().get_urls()

    def get_app_list(self, request, app_label=None):
        from django.urls import reverse
        result = super().get_app_list(request, app_label)
        perms = {v: request.user.has_perm(f'compromisos.{v}_estado') for v in ['view','add','change','delete']}
        if any(perms.values()) and app_label in [None, 'compromisos']:
            app = next((item for item in result if item['app_label']=='compromisos'), None)
            if app is None:
                app = dict(name='Compromisos', app_label='compromisos', app_url=reverse('admin:app_list', args=['compromisos']), has_module_perms=True, models=[])
                result.append(app)
            app['models'].append(dict(name='Estados', object_name='Estado', perms=perms, admin_url=reverse('admin:compromisos_estado_changelist') if perms['view'] or perms['change'] else None, add_url=reverse('admin:compromisos_estado_add') if perms['add'] else None, view_only=not perms['change']))
        return result

    def get_log_entries(self, request):
        return EventoCompromiso.auditoria.select_related('content_type', 'user')


class RegistroAdminMixin:
    def _log(self, request, obj, flag, message=''):
        return EventoCompromiso.auditoria.create(
            user=request.user, content_type=get_content_type_for_model(obj),
            object_id=str(obj.pk), object_repr=str(obj)[:200], action_flag=flag,
            change_message=json.dumps(message) if isinstance(message, list) else message,
        )

    def log_addition(self, request, obj, message):
        return self._log(request, obj, 1, message)

    def log_change(self, request, obj, message):
        return self._log(request, obj, 2, message)

    def log_deletion(self, request, obj, object_repr):
        return self._log(request, obj, 3)

    def log_deletions(self, request, queryset):
        return [self._log(request, obj, 3) for obj in queryset]

    def history_view(self, request, object_id, extra_context=None):
        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            return self._get_obj_does_not_exist_redirect(request, self.model._meta, object_id)
        if not self.has_view_or_change_permission(request, obj):
            raise PermissionDenied
        rows = EventoCompromiso.auditoria.filter(object_id=unquote(object_id), content_type=get_content_type_for_model(self.model)).select_related('user','content_type').order_by('fecha')
        paginator = self.get_paginator(request, rows, 100)
        page = paginator.get_page(request.GET.get(PAGE_VAR, 1))
        context = {
            **self.admin_site.each_context(request), 'title': gettext('Change history: %s') % obj,
            'subtitle': None, 'action_list': page, 'page_range': paginator.get_elided_page_range(page.number),
            'page_var': PAGE_VAR, 'pagination_required': paginator.count > 100,
            'module_name': str(capfirst(self.opts.verbose_name_plural)), 'object': obj, 'opts': self.opts,
            'preserved_filters': self.get_preserved_filters(request), **(extra_context or {}),
        }
        request.current_app = self.admin_site.name
        return TemplateResponse(request, self.object_history_template or 'admin/object_history.html', context)


def change_message(message):
    """
    If message is a JSON structure, interpret it as a change
    string, properly translated.
    """
    if message and message[0] == "[":
        try:
            change_message = json.loads(message)
        except json.JSONDecodeError:
            return message
        messages = []
        for sub_message in change_message:
            if "added" in sub_message:
                if sub_message["added"]:
                    sub_message["added"]["name"] = gettext(
                        sub_message["added"]["name"]
                    )
                    messages.append(
                        gettext("Added {name} “{object}”.").format(
                            **sub_message["added"]
                        )
                    )
                else:
                    messages.append(gettext("Added."))

            elif "changed" in sub_message:
                sub_message["changed"]["fields"] = get_text_list(
                    [
                        gettext(field_name)
                        for field_name in sub_message["changed"]["fields"]
                    ],
                    gettext("and"),
                )
                if "name" in sub_message["changed"]:
                    sub_message["changed"]["name"] = gettext(
                        sub_message["changed"]["name"]
                    )
                    messages.append(
                        gettext("Changed {fields} for {name} “{object}”.").format(
                            **sub_message["changed"]
                        )
                    )
                else:
                    messages.append(
                        gettext("Changed {fields}.").format(
                            **sub_message["changed"]
                        )
                    )

            elif "deleted" in sub_message:
                sub_message["deleted"]["name"] = gettext(
                    sub_message["deleted"]["name"]
                )
                messages.append(
                    gettext("Deleted {name} “{object}”.").format(
                        **sub_message["deleted"]
                    )
                )

        change_message = " ".join(msg[0].upper() + msg[1:] for msg in messages)
        return change_message or gettext("No fields changed.")
    else:
        return message

