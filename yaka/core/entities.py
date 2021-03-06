"""
Base class for entities, objects that are managed by the Abilian framwework
(unlike SQLAlchemy models which are considered lower-level).
"""
from inspect import isclass
from datetime import datetime
import json
import sys

from flask import g

from sqlalchemy.ext.declarative import AbstractConcreteBase, declared_attr
from sqlalchemy.orm import relationship, mapper
from sqlalchemy.orm.util import class_mapper
from sqlalchemy.schema import Column, ForeignKey
from sqlalchemy.types import Integer, DateTime
from sqlalchemy import event

from .extensions import db

from .util import memoized


__all__ = ['Entity', 'all_entity_classes', 'db', 'ValidationError']


class Info(dict):

  def __init__(self, **kw):
    for k, v in kw.items():
      self[k] = v

  def __add__(self, other):
    d = self.copy()
    for k, v in other.items():
      d[k] = v
    return d


EDITABLE = Info(editable=True)
NOT_EDITABLE = Info(editable=False)
AUDITABLE = Info(auditable=True)
AUDITABLE_HIDDEN = Info(auditable=True, audit_hide_content=True)
NOT_AUDITABLE = Info(auditable=False)
SEARCHABLE = Info(searchable=True)
NOT_SEARCHABLE = Info(searchable=False)
EXPORTABLE = Info(exportable=True)
NOT_EXPORTABLE = Info(exportable=False)

#: SYSTEM properties are properties defined by the system
#: and not supposed to be changed manually.
SYSTEM = Info(editable=False, auditable=False)


#
# Manual validation
#
class ValidationError(Exception):
  pass

def validation_listener(mapper, connection, target):
  if hasattr(target, "_validate"):
    target._validate()

event.listen(mapper, 'before_insert', validation_listener)
event.listen(mapper, 'before_update', validation_listener)


#
# CRUD events. TODO: connect to signals instead?
#
def before_insert_listener(mapper, connection, target):
  if hasattr(target, "_before_insert"):
    target._before_insert()

def before_update_listener(mapper, connection, target):
  if hasattr(target, "_before_update"):
    target._before_update()

def before_delete_listener(mapper, connection, target):
  if hasattr(target, "_before_delete"):
    target._before_delete()

event.listen(mapper, 'before_insert', before_insert_listener)
event.listen(mapper, 'before_update', before_update_listener)
event.listen(mapper, 'before_delete', before_delete_listener)


class Entity(AbstractConcreteBase, db.Model):
  """Base class for Yaka entities."""

  # Default magic metadata, should not be necessary
  __editable__ = frozenset()
  __searchable__ = frozenset()
  __auditable__ = frozenset()

  base_url = None

  # Persisted attributes.
  id = Column(Integer, primary_key=True, info=SYSTEM)

  created_at = Column(DateTime, default=datetime.utcnow, info=SYSTEM)
  updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
                      info=SYSTEM)
  deleted_at = Column(DateTime, default=None, info=SYSTEM)

  creator_id = declared_attr(lambda c: Column(ForeignKey("user.id"), info=SYSTEM))
  owner_id = declared_attr(lambda c: Column(ForeignKey("user.id"), info=SYSTEM))

  @declared_attr
  def __tablename__(cls):
    return cls.__name__.lower()

  @classmethod
  def __declare_last__(cls):
    if Entity in cls.__bases__:
      # declare "owner"" and "creator"" relations only for direct
      # subclasses. Otherwise when using subclasses of direct subclasses this
      # would produce the warning:
      #
      # sqlalchemy/orm/properties.py:909: SAWarning: Warning: relationship
      # 'creator' on mapper 'Mapper|Subsubclass|table' supersedes the same
      # relationship on inherited mapper 'Mapper|Subclass|table'; this can cause
      # dependency issues during flush
      pj1 = "User.id==%s.creator_id" % cls.__name__
      cls.creator = relationship("User", primaryjoin=pj1, uselist=False)

      pj2 = "User.id==%s.owner_id" % cls.__name__
      cls.owner = relationship("User", primaryjoin=pj2,  uselist=False)

  def __init__(self, **kw):
    if hasattr(g, 'user'):
      if not self.creator:
        self.creator = g.user
      if not self.owner:
        self.owner = g.user
    self.update(kw)

  def __repr__(self):
    if hasattr(self, 'name'):
      if isinstance(self.name, unicode):
        name = self.name.encode("ascii", errors="ignore")
      else:
        name = self.name
    else:
      name = "with id=%s" % self.id
    return "<%s %s>" % (self.__class__.__name__, name)

  @property
  def column_names(self):
    return [ col.name for col in class_mapper(self.__class__).mapped_table.c ]

  def update(self, d):
    for k, v in d.items():
      assert k in self.column_names, "%s not allowed" % k
      #if type(v) == type(""):
      #  v = unicode(v)
      setattr(self, k, v)

  def to_dict(self):
    if hasattr(self, "__exportable__"):
      exported = self.__exportable__ + ['id']
    else:
      exported = self.column_names
    d = {}
    for k in exported:
      v = getattr(self, k)
      if type(v) == datetime:
        v = v.isoformat()
      d[k] = v
    return d

  def to_json(self):
    return json.dumps(self.to_dict())

  @property
  def _url(self):
    return self.base_url + "/%d" % self.id

  def _icon(self, size=12):
    return "/static/icons/%s-%d.png" % (self.__class__.__name__.lower(), size)

  @property
  def _name(self):
    if hasattr(self, 'name'):
      return self.name
    else:
      raise NotImplementedError()

  def __unicode__(self):
    return self._name


# TODO: make this unecessary
def register_metadata(cls):
  #print "register_metadata called for class", cls
  cls.__editable__ = set()
  cls.__searchable__ = set()
  cls.__auditable__ = set()

  # TODO: use SQLAlchemy 0.8 introspection
  if hasattr(cls, '__table__'):
    columns = cls.__table__.columns
  else:
    columns = [ v for k, v in vars(cls).items() if isinstance(v, Column) ]

  for column in columns:
    name = column.name
    info = column.info

    if info.get("editable", True):
      cls.__editable__.add(name)
    if info.get('searchable', False):
      cls.__searchable__.add(name)
    if info.get('auditable', True):
      cls.__auditable__.add(name)


event.listen(Entity, 'class_instrument', register_metadata)


@memoized
def all_entity_classes():
  """
  Returns the list of all concrete persistent classes that are subclasses of
  Entity.
  """
  persistent_classes = Entity._decl_class_registry.values()
  # with sqlalchemy 0.8 _decl_class_registry holds object that are not classes
  return [ cls for cls in persistent_classes
           if isclass(cls) and issubclass(cls, Entity) ]


def register_all_entity_classes():
  for cls in all_entity_classes():
    register_metadata(cls)
