"""Administration of configurable states without a second model/table."""
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from .accounts import EstadoForm
from .models import EventoCompromiso


def estado_admin(site, request, estado_id=None, action='list'):
    obj = get_object_or_404(EventoCompromiso.estados, estado_id=estado_id) if estado_id is not None else None
    permission = {'list':'view', 'history':'view', 'add':'add', 'change':'change', 'delete':'delete'}[action]
    readonly = action == 'change' and not request.user.has_perm('compromisos.change_estado')
    if readonly and request.method == 'GET' and request.user.has_perm('compromisos.view_estado'):
        permission = 'view'
    if not request.user.has_perm('compromisos.'+permission+'_estado'):
        if permission != 'view' or not request.user.has_perm('compromisos.change_estado'):
            raise PermissionDenied
    ct = ContentType.objects.get(app_label='compromisos', model='estado')
    context = {**site.each_context(request), 'title':'Estados de negocio', 'obj':obj, 'action':action, 'readonly':readonly}
    if action == 'list':
        context['rows'] = EventoCompromiso.estados.order_by('estado_id')
        context['can_add'] = request.user.has_perm('compromisos.add_estado')
    elif action == 'history':
        context['history'] = EventoCompromiso.auditoria.filter(content_type=ct,object_id=str(estado_id)).select_related('user').order_by('-fecha')
    elif action in ['add','change']:
        form = EstadoForm(request.POST if request.method=='POST' else None, instance=obj or EventoCompromiso(tipo='estado'))
        if request.method == 'POST' and form.is_valid():
            from django.db import transaction
            with transaction.atomic():
                state = form.save()
                EventoCompromiso.auditoria.create(user=request.user, content_type=ct, object_id=str(state.estado_id), object_repr=str(state)[:200], action_flag=1 if action=='add' else 2, change_message='Estado guardado: '+', '.join(form.changed_data))
            messages.success(request,'Estado guardado.')
            return redirect('admin:compromisos_estado_changelist')
        context.update(form=form, can_delete=request.user.has_perm('compromisos.delete_estado'))
    elif action == 'delete' and request.method == 'POST':
        from django.db import transaction
        with transaction.atomic():
            EventoCompromiso.auditoria.create(user=request.user, content_type=ct, object_id=str(estado_id), object_repr=str(obj)[:200], action_flag=3, change_message='Estado eliminado.')
            obj.delete()
        messages.success(request,'Estado eliminado.')
        return redirect('admin:compromisos_estado_changelist')
    request.current_app = site.name
    return TemplateResponse(request,'admin/estados_portal.html',context)
