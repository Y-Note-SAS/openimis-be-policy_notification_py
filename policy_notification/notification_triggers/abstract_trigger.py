from abc import ABC

from typing import List
from policy.models import Policy, PolicyRenewal


class NotificationTriggerAbs(ABC):

    @classmethod
    def find_activated_policies(cls) -> List[type(Policy.id)]:
        raise NotImplementedError("find_new_activated_policies not implemented")

    @classmethod
    def find_newly_effective_policies(cls) -> List[type(Policy.id)]:
        raise NotImplementedError("find_new_effective_policies not implemented")

    @classmethod
    def find_renewed_policies(cls) -> List[type(Policy.id)]:
        raise NotImplementedError("find_newly_renewed_policies not implemented")

    @classmethod
    def find_soon_expiring_policies(cls) -> List[type(Policy.id)]:
        raise NotImplementedError("find_soon_expiring_policies not implemented")

    @classmethod
    def find_recently_expired_policies(cls) -> List[type(Policy.id)]:
        raise NotImplementedError("find_soon_expiring_policies not implemented")

    @classmethod
    def find_expiring_today_policies(cls) -> List[type(Policy.id)]:
        raise NotImplementedError("find_soon_expiring_policies not implemented")

    @classmethod
    def find_policies_to_pay(cls) -> List[type(Policy.id)]:
        raise NotImplementedError("find_new_created_policies not implemented")
    
    @classmethod
    def find_policies_to_pay_vulnerable(cls) -> List[type(Policy.id)]:
        raise NotImplementedError("find_new_created_policies_vulnerable not implemented")    
    
    @classmethod
    def find_paamg_policies_to_pay(cls) -> List[type(Policy.id)]:
        raise NotImplementedError("find_new_created_policies_paamg not implemented")
    
    @classmethod
    def find_periodic_payment_policies(cls) -> List[type(Policy.id)]:
        raise NotImplementedError("find_new_created_periodic_policies not implemented")
    
    @classmethod
    def find_periodic_payment_confirmed_policies(cls) -> List[type(Policy.id)]:
        raise NotImplementedError("find_new_created_periodic_confirmed_policies not implemented")
