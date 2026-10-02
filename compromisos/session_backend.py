"""Database-backed Django sessions in registros_portal; no cookies-as-storage."""
from django.contrib.sessions.backends.base import SessionBase, CreateError, UpdateError
from django.db import IntegrityError, transaction
from django.utils import timezone
from .models import EventoCompromiso


class SessionStore(SessionBase):
    # Same class name/salt as Django's DB backend preserves already signed sessions.
    def load(self):
        row = EventoCompromiso.sesiones.filter(session_key=self.session_key, expire_date__gt=timezone.now()).first()
        if row is None:
            self._session_key = None
            return {}
        return self.decode(row.session_data)

    def exists(self, session_key):
        return EventoCompromiso.sesiones.filter(session_key=session_key).exists()

    def create(self):
        while True:
            self._session_key = self._get_new_session_key()
            try:
                self.save(must_create=True)
            except CreateError:
                continue
            self.modified = True
            return

    def save(self, must_create=False):
        if self.session_key is None:
            return self.create()
        data = self._get_session(no_load=must_create)
        values = dict(session_data=self.encode(data), expire_date=self.get_expiry_date())
        if must_create:
            try:
                with transaction.atomic():
                    EventoCompromiso.sesiones.create(session_key=self.session_key, **values)
            except IntegrityError as exc:
                raise CreateError from exc
        else:
            # An expired or concurrently logged-out session must never be recreated.
            if not EventoCompromiso.sesiones.filter(session_key=self.session_key).update(**values):
                raise UpdateError

    def delete(self, session_key=None):
        key = session_key or self.session_key
        if key:
            EventoCompromiso.sesiones.filter(session_key=key).delete()

    @classmethod
    def clear_expired(cls):
        EventoCompromiso.sesiones.filter(expire_date__lt=timezone.now()).delete()
