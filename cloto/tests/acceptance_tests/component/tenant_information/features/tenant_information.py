__author__ = 'artanis'

# -*- coding: utf-8 -*-
from lettuce import step, world, before
from commons.rest_utils import RestUtils
from commons.constants import TENANT_DOC, TENANT_OWNER, TENANT_VERSION, TENANT_WSIZE
from commons.configuration import HEADERS, TENANT_ID
from commons.errors import ERROR_CODE_ERROR
import commons.utils as Utils

api_utils = RestUtils()


@before.each_scenario
def setup(scenario):

    #Set default headers with correct token before every scenario
    world.headers = HEADERS


@step(u'the tenant "([^"]*)"')
def set_tenant_id(step, tenant_id):

    world.tenant_id = tenant_id


@step(u'created tenant')
def set_default_tenant(step):

    #Set default tenant_id as a global variable
    world.tenant_id = TENANT_ID


@step(u'I retrieve the tenant information')
def retrieve_tenant_information(step):

    world.req = api_utils.retrieve_information(tenant_id=world.tenant_id, headers=world.headers)


@step(u'I get the following information:')
def check_tenant_information(step):

    assert world.req.ok, 'Invalid HTTP status code. Status Code obtained is: {}'.format(world.req.status_code)
    response = world.req.json()
    print response
    for expected_result in step.hashes:

        assert response[TENANT_DOC] == expected_result[TENANT_DOC], 'Expected {} is: {} \n Obtained {} is: ' \
                                                                    '{}'.format(TENANT_DOC, expected_result[TENANT_DOC],
                                                                                TENANT_DOC, response[TENANT_DOC])

        assert response[TENANT_OWNER] == expected_result[TENANT_OWNER], 'Expected {} is: {} \n Obtained {} is: ' \
                                                                        '{}'.format(TENANT_OWNER,
                                                                                    expected_result[TENANT_OWNER],
                                                                                    TENANT_OWNER,
                                                                                    response[TENANT_OWNER])
        response[TENANT_VERSION] = str(response[TENANT_VERSION])
        assert response[TENANT_VERSION] == expected_result[TENANT_VERSION], 'Expected {} is: {} \n Obtained {} is: ' \
                                                                            '{}'.format(TENANT_VERSION,
                                                                                        expected_result[TENANT_VERSION],
                                                                                        TENANT_VERSION,
                                                                                        response[TENANT_VERSION])
        response[TENANT_WSIZE] = str(response[TENANT_WSIZE])
        assert response[TENANT_WSIZE] == expected_result[TENANT_WSIZE], 'Expected {} is: {} \n Obtained {} is: ' \
                                                                        '{}'.format(TENANT_WSIZE,
                                                                                    expected_result[TENANT_WSIZE],
                                                                                    TENANT_WSIZE,

                                                                                    response[TENANT_WSIZE])


@step(u'I obtain an "([^"]*)" and the "([^"]*)"')
def assert_error_response(step, error_code, fault_element):

    Utils.assert_error_code_error(response=world.req, expected_error_code=error_code,
                                  expected_fault_element=fault_element)

@step(u'incorrect "([^"]*)"')
def set_incorrect_token(step, token):

    #Set and incorrect header to obtain unauthorized error
    world.headers = Utils.create_header(token=token)


@step(u'I update the "([^"]*)"')
def update_window_size(step, window_size):

    try:
        world.window_size = int(window_size)
    except ValueError:
        print 'Window Size can not be converted to integer'
        world.window_size = window_size

    world.req = api_utils.update_window_size(tenant_id=world.tenant_id, window_size=world.window_size,
                                             headers=world.headers)


@step(u'the "([^"]*)" is update in Policy Manager')
def assert_window_size(step, window_size):

    assert world.req.ok, str(world.req.status_code) + world.req.content
    response = world.req.json()
    assert str(response[TENANT_WSIZE]) == window_size
    world.req = api_utils.retrieve_information(tenant_id=world.tenant_id, headers=world.headers)
    response = world.req.json()
    print response
    assert str(response[TENANT_WSIZE]) == window_size