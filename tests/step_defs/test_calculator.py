import pytest
from pytest_bdd import scenarios, given, when, then, parsers

scenarios('../features/calculator.feature')

import logging

logger = logging.getLogger(__name__)

@pytest.fixture
def context():
    return {}

@given(parsers.parse("我有两个数字 {x:d} 和 {y:d}"))
def start_numbers(context, x, y):
    context['x'] = x
    context['y'] = y
    logger.error("我有两个数字 {x:d} 和 {y:d}")

@when("我执行加法")
def add(context):
    logger.info("我执行加法log")
    context['result'] = context['x'] + context['y']

@when("我执行减法")
def subtract(context):
    logger.info("我执行减法")
    context['result'] = context['x'] - context['y']

@then(parsers.parse("结果应该是 {res:d}"))
def check_result(context, res):
    logger.debug("jieguoyinggaishi")
    assert context['result'] == res