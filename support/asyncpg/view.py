import json

import asyncio

import binascii
import peewee
from playhouse.postgres_ext import BinaryJSONField
from playhouse.shortcuts import model_to_dict

from mapi.retcode import RETCODE
from mapi.support.asyncpg import query
from mapi.utils import ResourceException, to_bin, pagination_calc
from ...base.view import MView, BaseSQLFunctions

_field_query = '''SELECT a.attname as name, col_description(a.attrelid,a.attnum) as comment,pg_type.typname as typename, a.attnotnull as notnull
  FROM pg_class as c,pg_attribute as a inner join pg_type on pg_type.oid = a.atttypid 
  where c.relname = $1 and a.attrelid = c.oid and a.attnum>0;'''


class BaseModel(peewee.Model):
    def to_dict(self):
        return model_to_dict(self)


class AsyncpgSQLFunctions(BaseSQLFunctions):
    def _get_args(self, args):
        nargs = []
        # 这里注意，args可能多次使用，不要修改其中内容
        for i in args:
            i = i[:]
            field = self.view.fields[i[0]]
            type_codec = field['typename']

            # https://www.postgresql.org/docs/9.6/static/datatype.html
            # asyncpg/protocol/protocol.pyx
            conv_func = None
            if type_codec in ['int2', 'int4', 'int8']:
                type_codec = 'int'
                conv_func = int
            elif type_codec in ['float4', 'float8']:
                type_codec = 'float'
                conv_func = float
            elif type_codec == 'bytea':
                type_codec = 'bytea'
                conv_func = to_bin

            if conv_func:
                try:
                    if i[1] == 'in':
                        i[2] = list(map(conv_func, i[2]))
                    else:
                        i[2] = conv_func(i[2])
                except binascii.Error:
                    self.err = RETCODE.INVALID_PARAMS, 'Invalid query value for blob: Odd-length string'
                    return
                except ValueError as e:
                    self.err = RETCODE.INVALID_PARAMS, ' '.join(map(str, e.args))

            nargs.append([*i, type_codec])
        return nargs

    def _get_data(self, data):
        ndata = {}
        for k, v in data.items():
            field = self.view.fields[k]
            type_codec = field['typename']

            if type_codec in ['int2', 'int4', 'int8']:
                type_codec = 'int'
                v = int(v)
            elif type_codec in ['float4', 'float8']:
                type_codec = 'float'
                v = float(v)
            elif type_codec == 'bytea':
                type_codec = 'bytea'
                v = to_bin(v)

            ndata[k] = v
        return ndata

    async def select_one(self, si):
        view = self.view
        nargs = self._get_args(si['args'])
        if self.err: return self.err

        sc = query.SelectCompiler()
        sql = sc.select_raw('*').from_table(view.table_name).simple_where_many(nargs).order_by_many(si['orders']).sql()
        ret = await view.conn.fetchrow(sql[0], *sql[1])

        ability = view.permission.request_role(view.current_user, si['role'])
        available_columns = ability.filter_record_columns_by_action(view.current_user, ret)

        if not available_columns:
            return RETCODE.NOT_FOUND, None

        if ret:
            return RETCODE.SUCCESS, dict(ret)
        else:
            return RETCODE.NOT_FOUND, None

    async def select_pagination_list(self, info, size, page):
        view = self.view
        nargs = self._get_args(info['args'])
        if self.err: return self.err

        sc = query.SelectCompiler()
        sql = sc.select_count().from_table(view.table_name).simple_where_many(nargs).order_by_many(si['orders']).sql()
        count = (await view.conn.fetchrow(sql[0], *sql[1]))['count']

        pg = pagination_calc(count, size, page)
        offset = size * (page - 1)

        sc.reset()
        get_values = lambda x: list(x.values())

        sql = sc.select_raw('*').from_table(view.table_name).simple_where_many(nargs) \
            .order_by_many(info['orders']).limit(size).offset(offset).sql()
        ret = map(get_values, await view.conn.fetch(sql[0], *sql[1]))

        pg["items"] = list(ret)
        return RETCODE.SUCCESS, pg

    async def update(self, si, data):
        view = self.view
        nargs = self._get_args(si['args'])
        if self.err: return self.err
        ndata = self._get_data(data)

        uc = query.UpdateCompiler()
        sql = uc.to_table(view.table_name).simple_where_many(nargs).set_values(ndata).sql()
        ret = await view.conn.execute(sql[0], *sql[1]) # ret == "UPDATE X"

        if ret and ret.startswith("UPDATE "):
            num = int(ret[len("UPDATE "):])
            return RETCODE.SUCCESS, {'count': num}
        else:
            return RETCODE.FAILED, None

    async def insert(self, data):
        view = self.view
        ndata = self._get_data(data)
        ic = query.InsertCompiler()
        sql = ic.into_table(view.table_name).set_values(ndata).returning().sql()
        ret = await view.conn.fetchrow(sql[0], *sql[1])
        return RETCODE.SUCCESS, dict(ret)


class AsyncpgMView(MView):
    conn = None
    table_name = None
    sql_cls = AsyncpgSQLFunctions

    @staticmethod
    async def _fetch_fields_by_table_name(conn, table_name):
        info = await conn.fetch(_field_query, table_name)
        if not info:
            raise ResourceException("Table not found: %s" % table_name)
        ret = {}
        for i in info:
            ret[i['name']] = i
        return ret

    @staticmethod
    async def _fetch_fields(cls_or_self):
        if cls_or_self.table_name:
            info = await cls_or_self.conn.fetch(_field_query, cls_or_self.table_name)
            if not info:
                raise ResourceException("Table not found: %s" % cls_or_self.table_name)
            ret = {}
            for i in info:
                ret[i['name']] = i
            cls_or_self.fields = ret
