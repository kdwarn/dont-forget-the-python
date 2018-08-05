#!python3

import click
import pytest

from dftp.app import Task, handle_response


# create dummy response class
class DummyResponse:

    def __init__(self, status_code, reason, rsp):
        self.status_code = status_code
        self.reason = reason
        self.rsp = rsp

    def json(self):
        ''' Mock requests.json(). '''
        return self.rsp


def test_handle_response_exits_with_invalid_status():
    invalid_status = DummyResponse(100, "Expected 200.", '')

    with pytest.raises(SystemExit) as e:
        handle_response(invalid_status)

    assert e.type == SystemExit
    assert e.value.code == 'Bad Status Code'


def test_handle_response_exits_with_not_ok_data():
    rsp = {'rsp': {'stat':'fail', 'err': {'code': '1000', 'msg': 'dummy error'}}}

    not_ok_data = DummyResponse(200, "Ok", rsp)

    with pytest.raises(SystemExit) as e:
        handle_response(not_ok_data)

    assert e.type == SystemExit
    assert e.value.code == 'Error 1000.'


def test_handle_response_returns_data():
    rsp = {'rsp': {'stat':'ok', 'dummy': 'dummy'}}

    ok_data = DummyResponse(200, "Ok", rsp)
    ok_data_response = handle_response(ok_data)
    assert ok_data_response['dummy'] == 'dummy'
