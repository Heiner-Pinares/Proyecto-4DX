"""Arranca el portal para el túnel; no inicia ngrok ni publica por sí solo."""
import argparse
import os
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Preparar el portal para una URL HTTPS temporal de ngrok.')
    parser.add_argument('url', help='URL HTTPS que muestra ngrok, sin rutas')
    parser.add_argument('--check', action='store_true', help='Validar configuración sin iniciar el servidor')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    os.chdir(root)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.ngrok_settings'
    os.environ['NGROK_PUBLIC_URL'] = args.url
    os.environ['DEBUG'] = 'False'
    import django
    django.setup()
    from django.core.management import call_command
    call_command('check')
    if args.check:
        print('Configuración HTTPS, dominio y CSRF válidos. No se inició ningún túnel.')
        return
    subprocess.run([sys.executable, str(root / 'run.py'), '--check'], check=True, env=os.environ)
    call_command('collectstatic', interactive=False, verbosity=0)
    print(f'Portal preparado para {args.url}. Puerto local del túnel: 8002.', flush=True)
    os.execv(sys.executable, [sys.executable, '-m', 'gunicorn', 'config.wsgi:application',
                            '--bind', '127.0.0.1:8002', '--workers', '2', '--threads', '2'])


if __name__ == '__main__':
    main()
