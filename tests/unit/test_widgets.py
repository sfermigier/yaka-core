# coding=utf-8
import os

from unittest import TestCase, skip
from flask import Flask
from wtforms import Form, TextField, IntegerField
from yaka.core.extensions import babel
from yaka.web.widgets import MainTableView, SingleView, Panel, Row, \
  linkify_url, text2html, EmailWidget

class DummyMapper(object):
  def __init__(self):
    self.c = {}

class DummyModel(object):
  """
  Mock model.
  """
  __mapper__ = DummyMapper()

  def __init__(self, **kw):
    for k, v in kw.items():
      setattr(self, k, v)

class DummyForm(Form):
  name = TextField(u'Nom du véhicule')
  price = IntegerField(u"Prix du véhicule")
  email = TextField(u'email', view_widget=EmailWidget())

class BaseTestCase(TestCase):

  def setUp(self):
    # Hack to set up the template folder properly.
    template_dir = os.path.dirname(__file__) + "/../../yaka/templates"
    template_dir = os.path.normpath(template_dir)
    self.app = Flask(__name__, template_folder=template_dir)
    babel.init_app(self.app)


class TableViewTestCase(BaseTestCase):

  def test_table_view(self):
    with self.app.test_request_context():
      columns = ['name', 'price']
      view = MainTableView(columns)

      model1 = DummyModel(name="Renault Megane", _name="toto", price=10000)
      model2 = DummyModel(name="Peugeot 308", _name="titi", price=12000)

      models = [model1, model2]

      res = view.render(models)

      assert "Renault Megane" in res
      assert "10000" in res


class ModelViewTestCase(BaseTestCase):
  # Hack to silence test harness bug
  __name__ = "ModelView test case"

  def test_single_view(self):
    with self.app.test_request_context():
      panels = [Panel('main', Row('name'), Row('price'), Row('email'))]
      view = SingleView(DummyForm, *panels)
      model = DummyModel(name="Renault Megane",
                         price=10000, email="joe@example.com")
      res = view.render(model)

      assert "Renault Megane" in res
      assert "10000" in res
      # 'mailto:' is created by EmailWidget
      assert "mailto:joe@example.com" in res

  @skip
  def test_edit_view(self):
    with self.app.test_request_context():
      panels = [Panel('main', Row('name'), Row('price'))]
      view = SingleView(DummyForm, *panels)
      model = DummyModel(name="Renault Megane", price=10000)
      form = DummyForm(obj=model)
      res = view.render_form(form)

      assert "Renault Megane" in res
      assert "10000" in res


class TestLinkify(TestCase):

  EXPECTED = '<a href="http://example.com">example.com</a><i class="icon-share-alt"></i>'

  def test_http(self):
    value = "http://example.com"
    result = linkify_url(value)
    self.assertEquals(result, self.EXPECTED)

  def test_no_http(self):
    value = "example.com"
    result = linkify_url(value)
    self.assertEquals(result, self.EXPECTED)


class TestText2Html(TestCase):

  def test1(self):
    result = text2html("a")
    self.assertEquals(result, "a")

  def test2(self):
    result = text2html("a\nb")
    self.assertEquals(str(result), "<p>a</p>\n<p>b</p>")

  def test3(self):
    result = text2html("a\n\nb")
    self.assertEquals(str(result), "<p>a</p>\n<p>b</p>")

  def test4(self):
    result = text2html("a\n<a>toto</a>")
    self.assertEquals(str(result), "<p>a</p>\n<p>&lt;a&gt;toto&lt;/a&gt;</p>")
