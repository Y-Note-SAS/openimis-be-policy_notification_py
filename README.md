# openIMIS Backend Policy Notification reference module
This repository holds the files of the openIMIS Backend Policy Notification reference module.
It is dedicated to be deployed as a module of [openimis-be_py](https://github.com/openimis/openimis-be_py).

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

## ORM mapping:
* FamilyNotification > tblFamilySMS 

## Listened Django Signals:
* After Family mutation 
    * CreateFamilyMutation - create FamilyNotification object connected with created family
    * UpdateFamilyMutation - update FamilyNotification object connected with updated family
    * DeleteFamiliesMutation - delete FamilyNotification object connected with deleted family
* Family additional filter
    * Use mode from additional_filter.PolicyNotification to additionally query families by 
    notification eligibility

## Services
### Family notification 
Create FamilyNotification object connected with family with given uuid. 
```python
create_family_notification_policy(uuid, notification_data)
```

Update FamilyNotification object connected with family with given uuid. 
```python
update_family_notification_policy(uuid, notification_data)
```

Delete FamilyNotification object connected with family with given uuid. 
```python
delete_family_notification_policy(uuid, notification_data)
```

`notification_data` is dict structured as follows: 
```python
{ 
    'approvalOfNotification': True, # boolean informing whether family allows notification comunication, default False
    'languageOfNotification': 'en', # language code determining in which language messages will be sent, default en
}
```

## Reports
### Family Policy Notification Report
Report summarizing notification eligibility. \
Available in endpoint: `policy_notification/communication_by_notification_report`
Payload: 
```json
{
    "districtUuid": "districtUUID",
    "regionUuid": "regionUUID",
    "officerUuid": "enrollmentOfficerUUID",
    "mode": 1
}
```
#### Modes: 
* 0: 'All',
* 1: 'Approval and phone number',
* 2: 'Approval only',
* 3: 'Phone number only',
* 4: 'No approval and phone number' 

## Configuration
* Providers \
  This configuration key allows to configure currently used notification provider gateways. 
  For provider to be used it has to be included in notification_gateways submodule with class name 
  same as provider config (case-insensitive). When notifications are being send only first 
  provider is used. Module tries to use another provider only when notifying with previous 
  one has failed.
  
      "providers": {
          "eGASMSGateway": {
              "GateUrl": "http://127.0.0.1:8000",
              "SmsResource": "/api/policy_notification/test_sms/",
              "PrivateKey": "",
              "UserId": "",
              "SenderId": "",
              "ServiceId": "",
              "RequestType": "",
              "HeaderKeys": "X-Auth-Request-Hash,X-Auth-Request-Id,X-Auth-Request-Type",
              "HeaderValues": "PrivateKey,UserId,RequestType"
          },
          "TextNotificationProvider": {
              "DestinationFolder": "sent_notification"
          }
      }
  
* EligibleNotificationTypes \
  Determines which types of notifications are to be sent.
  
      "eligibleNotificationTypes": {
          "activation_of_policy": False,
          "starting_of_policy": False,
          "need_for_renewal": False,
          "expiration_of_policy": False,
          "reminder_after_expiration": False,
          "renewal_of_policy": False,
          "payment_request_for_policiy_activation": False,
          "payment_request_for_policiy_activation_vulnerable": False,
          "payment_request_for_paamg": False,
          "payment_of_policy_periodic": False,
          "confirmation_of_policy_periodic_payment": False
      }


* `family_policy_notification_report_perms` - List of role right required for generating 
  report, default `["131224"]`
  

*  `trigger_time_interval_hours` - Interval between event detector calls, default 4
*  `trigger_first_call_hour` - Hour of first task execution in given day, default 8
*  `trigger_last_call_hour` - Hour of last task execution in given day, default 20

**Note:** `trigger_*` settings are only used if scheduled task `policy_notification.tasks.send_notification_messages` 
in the openimis settings.py `SCHEDULED_TASK` is not active. Task included in `SCHEDULED_TASK` should use hour param for 
execution. Either provided as list of hours at which given task is executed (e.g. hour="8, 12, 16"), 
single hour (e.g. hour=8), or the time interval when the task is executed every hour (e.g. hour='8-16'). 


*  `reminder_before_expiry_days` - Days before the expiry of un-renewed policy to send notifications, 
   default 5
*  `reminder_after_expiry_days` - Days after the expiry of un-renewed policy to send notifications, 
   default 5

## openIMIS Modules Dependencies
* openIMIS.policy
* openIMIS.insuree
