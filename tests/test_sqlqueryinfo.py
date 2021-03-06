from slim.base.sqlquery import SQLQueryInfo, SQLQueryOrder, ALL_COLUMNS
from slim.exception import SyntaxException, InvalidParams


def test_new():
    sqi = SQLQueryInfo()


def test_order():
    assert SQLQueryInfo.parse_order('a') == []
    assert SQLQueryInfo.parse_order('a,b,c') == []
    assert SQLQueryInfo.parse_order('a, b, c') == []
    assert SQLQueryInfo.parse_order('a, b,   c') == []
    assert SQLQueryInfo.parse_order('a, b,') == []
    assert SQLQueryInfo.parse_order('a.asc') == [SQLQueryOrder('a', 'asc')]
    assert SQLQueryInfo.parse_order('a.AsC') == [SQLQueryOrder('a', 'asc')]
    assert SQLQueryInfo.parse_order('a.asc, b,') == [SQLQueryOrder('a', 'asc')]
    assert SQLQueryInfo.parse_order('a.asc,b,c.desc') == [SQLQueryOrder('a', 'asc'), SQLQueryOrder('c', 'desc')]

    try:
        SQLQueryInfo.parse_order('a.a.a')
        assert False
    except Exception as e:
        assert isinstance(e, InvalidParams)

    try:
        SQLQueryInfo.parse_order('a.?sc')
        assert False
    except Exception as e:
        assert isinstance(e, InvalidParams)

    sqi = SQLQueryInfo()
    sqi.set_orders([])

    try:
        sqi.set_orders([1])
        assert False
    except Exception as e:
        assert isinstance(e, AssertionError)

    sqi.set_orders([SQLQueryOrder('A', 'asc')])
    assert sqi.orders == [SQLQueryOrder('A', 'asc')]


def test_select():
    assert SQLQueryInfo.parse_select('aa') == {'aa'}
    assert SQLQueryInfo.parse_select('aa,') == {'aa'}
    assert SQLQueryInfo.parse_select('aa,bbb') == {'aa', 'bbb'}
    assert SQLQueryInfo.parse_select('aa, bbb') == {'aa', 'bbb'}
    assert SQLQueryInfo.parse_select('aa,  \nbbb') == {'aa', 'bbb'}
    assert SQLQueryInfo.parse_select('*') == ALL_COLUMNS
    try:
        SQLQueryInfo.parse_select(',')
        assert False
    except Exception as e:
        assert isinstance(e, InvalidParams)
    try:
        SQLQueryInfo.parse_select(',,,')
        assert False
    except Exception as e:
        assert isinstance(e, InvalidParams)

    sqi = SQLQueryInfo()
    try:
        sqi.set_select([1, 2, '3'])
        assert False
    except Exception as e:
        assert isinstance(e, AssertionError)

    try:
        sqi.set_select(None)
        assert False
    except Exception as e:
        assert isinstance(e, InvalidParams)

    assert sqi.set_select(ALL_COLUMNS) is None
    assert sqi.set_select(['1', '2', '3']) is None
    assert sqi.set_select({'1', '2', '3'}) is None


if __name__ == '__main__':
    test_new()
    test_order()
    test_select()
