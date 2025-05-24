import json
from datetime import datetime
from unittest.mock import patch, PropertyMock
from django.test import TestCase

import requests

from policy_notification.notification_gateways import BulkSMSGateway
from policy_notification.notification_gateways.RequestBuilders import BaseSMSBuilder


class TestBulkSMSGateway(TestCase): 
    BUILDER = BaseSMSBuilder()
    MOCKED_SENDING_TIME_UTC_NOW = datetime(2025, 5, 23, 8, 16, 34)

    MESSAGE_CONTENT = json.dumps({
        'data': json.dumps({
            'message': 'test message',
            'datetime': '2025-05-23 11:16:34',
            'sender_id': 'Le-positif',
            'mobile_service_id': 'service_id',
            'recipients': '1'
        }, separators=(',', ':')),
        'datetime': "2025-05-23 11:16:34"
    }, separators=(',', ':'))

    TEST_PROVIDER_CONFIG = {
        "GateUrl": "http://127.0.0.1:8000/api/gateway_endpoint/",
        "PrivateKey": "my_private_key",
        "UserId": "test_user_id",
        "SenderId": "Le-positif",
        "ServiceId": "service_id",
        "RequestType": "api",
        "HeaderKeys": "X-API-KEY",
        "HeaderValues": "api_97f622af8eb9"
    }

    TEST_MODULE_CONFIG = {
        'providers': {
            'BulkSMSGateway': TEST_PROVIDER_CONFIG
        }
    }

    
    EXPECTED_REQUEST = {
        'url': "http://127.0.0.1:8000/api/gateway_endpoint/",
        'body': MESSAGE_CONTENT,
        'headers': {
            'X-API-KEY': 'api_97f622af8eb9',
            'Content-Length': str(len(MESSAGE_CONTENT)),
            'Content-Type': 'multipart/form-data; charset=utf-8'
        }
    }


    def setUp(self):
        super(TestBulkSMSGateway, self).setUp()
        self.maxDiff = None
        self.request_called = None

    def assign_test_output(self, output):
        self.request_called = output

    @patch('policy_notification.apps.PolicyNotificationConfig.providers', new_callable=PropertyMock)
    @patch('policy_notification.notification_gateways.bulk_sms_gateway.datetime.datetime')
    def test_gateway_send_sms(self, mocked_dt, config):
        config.return_value = self.TEST_MODULE_CONFIG['providers']
        mocked_dt.now.return_value = self.MOCKED_SENDING_TIME_UTC_NOW
        gateway = BulkSMSGateway(self.BUILDER)
        with patch.object(requests.Session, 'send', side_effect=self.assign_test_output) as mock_method:
            output = gateway.send_notification('test message', family_number="1")
            self._assert_request(self.request_called)
            mock_method.assert_called_once_with(self.request_called)

    def _assert_request(self, request):
        self.assertEqual(request.url, self.EXPECTED_REQUEST['url'])
        self.assertEqual(request.method, 'GET')
        self.assertEqual(request.body, self.EXPECTED_REQUEST['body'])
        self.assertDictEqual(dict(request.headers), self.EXPECTED_REQUEST['headers'])
