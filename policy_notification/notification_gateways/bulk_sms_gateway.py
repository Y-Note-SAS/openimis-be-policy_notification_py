import base64
import datetime
import logging
import requests
import json
import hmac
import hashlib
from policy_notification.notification_gateways.abstract_sms_gateway import NotificationGatewayAbs, NotificationSendingResult
from policy_notification.notification_gateways.RequestBuilders import BaseSMSBuilder

logger = logging.getLogger(__name__)

class BulkSMSGateway(NotificationGatewayAbs):
    # Use utc+3 timezone
    _GATEWAY_TIMEZONE_OFFSET = 3
    
    def __init__(self, builder=BaseSMSBuilder()):
        self.builder = builder
        self.message_sent = None
        self.family_number = None
        self.sending_time = None
        
    def header_values_evaluation(self):
        return {
            'UserId': self.get_provider_config_param('UserId'),
            'RequestType': self.get_provider_config_param('RequestType'),
            'HashMessage1': self.create_request_hash()
        }

    @property
    def provider_configuration_key(self):
        return "BulkSMSGateway"

    def send_notification(self, notification_content, family_number=None, builder=None) -> NotificationSendingResult:
        self.sending_time = datetime.datetime.now(tz=datetime.timezone.utc)
        self.sending_time += datetime.timedelta(hours=self._GATEWAY_TIMEZONE_OFFSET)
        self.message_sent = notification_content
        # self.family_number = family_number
        # if family_number and not family_number.startswith('+'):
        #     family_number = f'+269{family_number}'  # Normalisation pour les Comores
        self.family_number = family_number
        builder = builder or self.builder
        request = self.build_request(builder)
        s = requests.Session()
        response = s.send(request)
        success = self._check_success(response)
        logger.info(f"BulkSMS request success: {success} "
                    f"With response: {response.content}")
        if not success:
            if response is not None:
                logger.warning(f"BulkSMS Gateway: Notification request sent, resulted in "
                               f"status {response.status_code}, "
                               f"content of response: {response.content}")
            else:
                logger.warning("BulkSMS Gateway: Notification request sent, no response")
        return NotificationSendingResult(response, success=success)

    def get_auth(self):
        return None
    
    def get_headers(self):
        header_keys = self.get_provider_config_param('HeaderKeys')
        header_values = self.get_provider_config_param('HeaderValues')
        base_headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        if header_keys and header_values:
            header_dict = dict(zip(header_keys.split(','), header_values.split(',')))
            base_headers.update(header_dict)
        return base_headers

    def get_method(self):
        return 'POST'
    
    def get_request_content(self):
        return json.dumps({
            'data': self._get_message_content(self.message_sent),
            'datetime': self.sending_time.strftime('%Y-%m-%d %H:%M:%S')
        }, separators=(',', ':'))

    def get_request_url(self):
        return self.get_provider_config_param('GateUrl')
    
    def header_value(self, header_key):
        try:
            return self.header_values_evaluation().get(header_key)
        except KeyError as e:
            logger.error(f"Failed to get header value representation for header {header_key}. Request not sent")
            raise

    def get_params(self):
        return {
            'from': self.get_provider_config_param('SenderId'),
            'phone_number': self.family_number,
            'content': self.message_sent
        }
        
    def create_request_hash(self):
        key = self.get_provider_config_param('PrivateKey')
        message = self._get_message_content(self.message_sent)

        signature = hmac.new(
            bytes(key, encoding='ascii'),
            bytes(message, encoding='ascii'),
            hashlib.sha256
        )
        header_hash = base64.b64encode(signature.digest()).decode()
        return header_hash

    def _get_message_content(self, message):
        return json.dumps({
            "message": message,
            "datetime": self.sending_time.strftime('%Y-%m-%d %H:%M:%S'),
            "sender_id": self.get_provider_config_param('SenderId'),
            "mobile_service_id": self.get_provider_config_param('ServiceId'),
            "recipients": self.family_number
        }, separators=(',', ':'))
        
    def _check_success(self, server_response):
        if not server_response or server_response.status_code != 200:
            return False
        return True
