import uuid
import json

from django.db import models
from django.forms.models import model_to_dict
# from django.conf import settings

from .utils import get_short_uuid, ExtendedEncoder


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    @property
    def short_id(self):
        return get_short_uuid(self.id)

    def attrs(self, *attrs):
        """
        get a dictionary of attr:val for a list of attrs, defaults to all fields
        """
        if attrs is None:
            attrs = (f.name for f in self._meta.fields)
        return {attr: getattr(self, attr) for attr in attrs}

    def __json__(self, *attrs):
        return {
            'id': self.id,
            'str': str(self),
            **self.attrs(*attrs),
        }

    def __str__(self):
        return f'{self.__class__.__name__}:{self.short_id}'

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.short_id}>'

    def describe(self, print_me=True):
        fields_desc = json.dumps(
            model_to_dict(self), cls=ExtendedEncoder, indent=4
        )
        output = f'{self}:\n{fields_desc}'
        if print_me:
            print(output)
        else:
            return output

    class Meta:
        abstract = True


class SingletonModel(BaseModel):
    """
    Inherit from this to create a Singleton Model, (a model for which there
    should only ever be one row)
    """
    ID = '00' * 16
    id = models.UUIDField(primary_key=True, default=ID, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # make sure the inheriting model sets a real uuid (not default value)
        if self.ID is None or str(self.ID) == '00' * 16:
            raise NotImplementedError('Please provide a default singleton ID ')

        # make sure the ID they are trying to save matches the singleton's only
        #   allowed ID
        if str(self.id) != str(self.ID):
            raise ValueError('This is intended to be a singleton.')

        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create()
        return obj

class DispatchHandlerModel:
    """
    Model-mixin that allows a model to accept events and dispatch them to
    functions with the same name
    """

    def dispatch(self, event, **kwargs):
        """
        Take an $EVENT and call the function with that on_$EVENT function
        on self
        """
        event_str = f"on_{str(event).lower()}"

        assert hasattr(self, event_str), \
                f'{event_str} is not a valid event on {self.__class__.__name__}'
        event_func = getattr(self, event_str)
        changes = event_func(**kwargs)

        for attr, new_val in changes:
            setattr(self, attr, new_val)

        return changes


### Model Locking

class ConcurrentModificationError(ValueError):
    """Base error class for write concurrency errors"""
    pass


class StaleWriteError(ConcurrentModificationError):
    """
    Tried to write a version of a model that is older than the current version
    in the database
    """
    pass


class AlreadyLockedError(ConcurrentModificationError):
    """Tried to aquire a lock on a row that is already locked"""
    pass


class WriteWithoutLockError(ConcurrentModificationError):
    """Tried to save a lock-required model row without locking it first"""
    pass


class LockedModel:
    """
    Add row-level locking backed by redis, set lock_required=True to require a
    lock on .save()
    """

    lock_required = False  # is a lock required to save this model for safety?

    def __init__(self, *args, **kwargs):
        raise NotImplementedError('Locked models are not yet implemented.')

    # @property
    # def _lock_key(self):
    #     model_name = self.__class__.__name__
    #     return f'{model_name}__locked:{self.id}'

    # def is_locked(self):
    #     return lock_table.get(self._lock_key) == b'1'

    # def lock(self):
    #     if self.is_locked():
    #         raise AlreadyLockedError('Tried to lock an already-locked row.')
    #     lock_table.set(self._lock_key, b'1')

    # def unlock(self):
    #     lock_table.set(self._lock_key, b'0')

    # def save(self, *args, **kwargs):
    #     if self.lock_required and not self.is_locked():
    #         raise WriteWithoutLockError('Tried to save a lock-required model
    #                                           row without locking it first')

    #     super(LockedModel, self).save(*args, **kwargs)
