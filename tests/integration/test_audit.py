import datetime
from sqlalchemy import Column, Unicode, UnicodeText, Text, Date

from yaka.services import audit_service
from yaka.services.audit import AuditEntry, CREATION, UPDATE, DELETION
from yaka.core.entities import Entity, SEARCHABLE, AUDITABLE_HIDDEN

from .base import IntegrationTestCase


class DummyAccount(Entity):
  name = Column(UnicodeText, default=u"", info=SEARCHABLE)
  password = Column(Unicode, default=u'*', info=AUDITABLE_HIDDEN)
  website = Column(Text, default=u"")
  office_phone = Column(UnicodeText, default=u"")
  birthday = Column(Date)


class TestAudit(IntegrationTestCase):

  def setUp(self):
    audit_service.start()
    IntegrationTestCase.setUp(self)

  def tearDown(self):
    IntegrationTestCase.tearDown(self)
    if audit_service.running:
      audit_service.stop()

  def test_audit(self):
    # creation of system user(0) should have created one entry. We clear it for this test
    AuditEntry.query.delete()
    self.session.flush()
    assert len(AuditEntry.query.all()) == 0

    account = DummyAccount(name=u"John SARL")
    self.session.add(account)
    self.session.commit()
    assert len(AuditEntry.query.all()) == 1

    entry = AuditEntry.query.one()
    assert entry.type == CREATION
    assert entry.entity_class == "DummyAccount"
    assert entry.entity_id == account.id

    account.website = "http://www.john.com/"
    self.session.commit()
    assert len(AuditEntry.query.all()) == 2

    entry = AuditEntry.query.order_by(AuditEntry.happened_at).all()[1]
    assert entry.type == UPDATE
    assert entry.entity_class == "DummyAccount"
    assert entry.entity_id == account.id
    assert entry.changes == {u'website': (u'', u'http://www.john.com/')}

    account.birthday = datetime.date(2012, 12, 25)
    self.session.commit()
    assert len(AuditEntry.query.all()) == 3

    entry = AuditEntry.query.order_by(AuditEntry.happened_at).all()[2]
    assert entry.type == UPDATE
    assert entry.entity_class == "DummyAccount"
    assert entry.entity_id == account.id
    assert entry.changes == {u'birthday': (None, datetime.date(2012, 12, 25))}

    # content hiding
    account.password = u'new super secret password'
    assert account.__changes__ == {u'password': (u'******', u'******')}
    self.session.commit()

    entry = AuditEntry.query.order_by(AuditEntry.happened_at).all()[3]
    assert entry.type == UPDATE
    assert entry.entity_class == "DummyAccount"
    assert entry.entity_id == account.id
    assert entry.changes == {u'password': (u'******', u'******')}

    # deletion
    self.session.delete(account)
    self.session.commit()
    assert len(AuditEntry.query.all()) == 5

    entry = AuditEntry.query.order_by(AuditEntry.happened_at).all()[4]
    assert entry.type == DELETION
    assert entry.entity_class == "DummyAccount"
    assert entry.entity_id == account.id


