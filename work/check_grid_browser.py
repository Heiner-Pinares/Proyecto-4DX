import os,sys,secrets
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.contrib.auth.models import User,Group
from compromisos.models import Compromiso
from datetime import date
from playwright.sync_api import sync_playwright
password=secrets.token_urlsafe(25)
u=User.objects.create_user('qa_grid_'+secrets.token_hex(4),password=password)
u.groups.add(Group.objects.get(name='Editor'))
c=Compromiso.objects.create(tema='Verificación temporal',iniciativa='Prueba UI',tarea='Comprobar edición por celda',responsable_pyp='QA',status='P',fecha_de_compromiso=date(2026,9,1),primera_fecha=date(2026,9,10))
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
  page=browser.new_page(viewport={'width':1440,'height':950})
  errors=[]
  page.on('pageerror',lambda error:errors.append(str(error)))
  page.goto('http://127.0.0.1:8001/login/')
  page.locator('[name=username]').fill(u.username)
  page.locator('[name=password]').fill(password)
  page.get_by_role('button',name='Ingresar').click()
  page.goto('http://127.0.0.1:8001/compromisos/')
  row=page.locator(f'tr[data-id="{c.pk}"]')
  row.locator('[data-field=tarea] button').click()
  row.locator('textarea').fill('Edición guardada desde la hoja')
  row.locator('textarea').press('Enter')
  page.get_by_text('✓ Cambio guardado',exact=True).wait_for()
  row.locator('[data-field=fecha_real] button').click()
  row.locator('input[type=date]').fill('2026-09-11')
  row.get_by_role('button',name='Guardar',exact=True).click()
  page.get_by_text('✓ Cambio guardado',exact=True).wait_for()
  assert row.locator('[data-field=puntaje]').inner_text()=='60 %'
  row.locator('[data-field=segunda_fecha] button').click()
  row.locator('input[type=date]').fill('2026-09-15')
  row.get_by_label('Motivo del cambio').fill('Acuerdo para prueba de interfaz')
  row.get_by_role('button',name='Guardar',exact=True).click()
  page.get_by_text('✓ Cambio guardado',exact=True).wait_for()
  assert row.locator('[data-field=puntaje]').inner_text()=='80 %'
  row.locator('[data-field=tema] button').click()
  row.locator('input').fill('No debe guardarse')
  row.locator('input').press('Escape')
  assert row.locator('[data-field=tema]').inner_text()=='Verificación temporal'
  page.reload()
  assert row.locator('[data-field=tarea]').inner_text()=='Edición guardada desde la hoja'
  assert row.locator('[data-field=puntaje]').inner_text()=='80 %'
  row.locator('[data-field=fecha_real]').scroll_into_view_if_needed()
  page.screenshot(path='work/tabla-fechas.png')
  row.locator('[data-field=tema]').scroll_into_view_if_needed()
  page.screenshot(path='work/tabla-edicion.png')
  assert not errors,errors
  browser.close()
 print('Navegador: edición, guardado, 60→80, cancelación y persistencia correctos; sin errores JS.')
finally:
 Compromiso.all_objects.filter(pk=c.pk).delete()
 u.delete()
