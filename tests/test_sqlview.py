import json

import pytest
from unittest import mock
from aiohttp.test_utils import make_mocked_request
from multidict import MultiDict

from slim.retcode import RETCODE
from slim.support.peewee import PeeweeView
from peewee import *
from slim import Application
from playhouse.sqlite_ext import JSONField as SQLITE_JSONField

pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456')
db = SqliteDatabase(":memory:")


class ATestModel(Model):
    name = TextField()
    binary = BlobField()
    count = IntegerField()
    active = BooleanField(default=False)
    flt = FloatField(default=0)
    json = SQLITE_JSONField()

    class Meta:
        db_table = 'test'
        database = db


class ATestBModel(Model):
    name = TextField()
    link = ForeignKeyField(ATestModel)

    class Meta:
        db_table = 'test2'
        database = db


class ATestCModel(Model):
    name = TextField()
    link = ForeignKeyField(ATestBModel)

    class Meta:
        db_table = 'test3'
        database = db


db.create_tables([ATestModel, ATestBModel, ATestCModel])
a1 = ATestModel.create(name='Name1', binary=b'test1', count=1, json={'q': 1, 'w1': 2})
a2 = ATestModel.create(name='Name2', binary=b'test2', count=2, json={'q': 1, 'w2': 2})
a3 = ATestModel.create(name='Name3', binary=b'test3', count=3, json={'q': 1, 'w3': 2})
a4 = ATestModel.create(name='Name4', binary=b'test4', count=4, json={'q': 1, 'w4': 2})
a5 = ATestModel.create(name='Name5', binary=b'test5', count=5, json={'q': 1, 'w5': 2})

b1 = ATestBModel.create(name='NameB1', link=a1)
b2 = ATestBModel.create(name='NameB2', link=a2)
b3 = ATestBModel.create(name='NameB3', link=a3)
b4 = ATestBModel.create(name='NameB4', link=a4)
b5 = ATestBModel.create(name='NameB5', link=a5)

c1 = ATestCModel.create(name='NameC1', link=b1)
c2 = ATestCModel.create(name='NameC2', link=b2)
c3 = ATestCModel.create(name='NameC3', link=b3)
c4 = ATestCModel.create(name='NameC4', link=b4)
c5 = ATestCModel.create(name='NameC5', link=b5)


@app.route('test1')
class ATestView(PeeweeView):
    model = ATestModel


@app.route('test2')
class ATestView2(PeeweeView):
    model = ATestBModel


@app.route('test3')
class ATestView3(PeeweeView):
    model = ATestCModel


async def test_bind():
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    assert len(view.model._meta.fields) == len(view.fields)
    assert set(view.model._meta.fields.values()) == set(view.model._meta.fields.values())


async def test_get():
    # 1. success: no statement
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS

    # 2. failed: simple statement and not found
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'name': 1}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.NOT_FOUND

    # 3. failed: column not found
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'qqq': 1}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.FAILED

    # 4. failed: invalid parameter (Invalid operator)
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'qqq.a.b': 1}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.INVALID_PARAMS

    #  5. failed: invalid parameter (bad value)
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'flt': 'qq'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.INVALID_PARAMS

    #  6. success: simple statement
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'flt': '0'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS

    #  7. success: simple statement
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'flt.eq': '0'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS

    #  8. not found: simple statement
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'flt.lt': '0'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.NOT_FOUND

    #  9. success: simple statement
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'flt.le': '0'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS


async def test_get_loadfk():
    #  1. success: simple statement
    request = make_mocked_request('GET', '/api/test2', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView2(app, request)
    view._params_cache = {'name': 'NameB1'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS

    #  2. failed: syntax
    request = make_mocked_request('GET', '/api/test2', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView2(app, request)
    view._params_cache = {'name': 'NameB1', 'loadfk': {'aaa': None}}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.FAILED

    #  3. failed: column not found
    request = make_mocked_request('GET', '/api/test2', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView2(app, request)
    view._params_cache = {'name': 'NameB1', 'loadfk': json.dumps({'aaa': None})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.FAILED

    #  4. failed: column not found
    request = make_mocked_request('GET', '/api/test2', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView2(app, request)
    view._params_cache = {'name': 'NameB1', 'loadfk': json.dumps({'link_id': None})}
    await view._prepare()
    await view.get()
    print(view.ret_val)
    assert view.ret_val['code'] == RETCODE.SUCCESS


if __name__ == '__main__':
    from slim.utils.async import sync_call
    sync_call(test_bind)
    sync_call(test_get)
    sync_call(test_get_loadfk)
