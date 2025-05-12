from django.utils.translation import gettext as _


class DefaultNotificationTemplates:

    def get_all(self):
        output = {}
        for attr in self.__dir__():
            if attr.startswith('__') or type(getattr(self, attr, None)) != str:
                continue
            else:
                output[attr] = getattr(self, attr, None)

        return output

    @property
    def notification_on_activation(self):
        return _("policy_notification.sms_on_activation")

    @property
    def notification_on_effective(self):
        return _("policy_notification.sms_on_effective")

    @property
    def notification_before_expiry(self):
        return _("policy_notification.sms_before_expiry")

    @property
    def notification_on_expiration(self):
        return _("policy_notification.sms_on_expiration")

    @property
    def notification_after_expiry(self):
        return _("policy_notification.sms_after_expiry")

    @property
    def notification_on_renewal(self):
        return _("policy_notification.sms_on_renewal")

    @property
    def notification_control_number_assigned(self):
        return _("policy_notification.sms_control_number_assigned")

    @property
    def notification_control_number_error_bulk_payment(self):
        return _("policy_notification.sms_control_number_error_bulk_payment")

    @property
    def notification_control_number_error_single_payment(self):
        return _("policy_notification.sms_control_number_error_single_payment")

    @property
    def notification_paid_and_activated(self):
        return _("policy_notification.sms_paid_and_activated")

    @property
    def notification_paid_and_not_activated(self):
        return _("policy_notification.sms_paid_and_not_activated")

    @property
    def notification_paid_and_not_matched(self):
        return _("policy_notification.sms_paid_and_not_matched")
