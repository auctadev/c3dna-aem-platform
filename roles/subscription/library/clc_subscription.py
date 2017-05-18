#!/usr/bin/python

import datetime
import time
import sys
import json
import os
import shlex
import requests

SUBSCRIPTION_URL='https://onramp.ctl.io/api/PlatformSubscriptions'
#SUBSCRIPTION_URL='https://onramp-staging.ctl.io/api/PlatformSubscriptions'

class SubsError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def buildTime():
    t = datetime.datetime.now()
    out = str(t.year) +'-'
    if len(str(t.month)) < 2:
        out = out + '0' + str(t.month) + '-'
    else:
        out = out +str(t.month) + '-'
    if len(str(t.day)) < 2:
        out = out + '0' + str(t.day) + 'T'
    else:
        out = out +str(t.day) + 'T'
    if len(str(t.hour)) < 2:
        out = out + '0' + str(t.hour) + ':'
    else:
        out = out +str(t.hour) + ':'
    if len(str(t.minute)) < 2:
        out = out + '0' + str(t.minute) + ':'
    else:
        out = out +str(t.minute) + ':'
    if len(str(t.second)) < 2:
        out = out + '0' + str(t.second) + '.'
    else:
        out = out +str(t.second) + '.'
    out = out + str(t.microsecond) + 'Z'
    return out

def createFields(module):
    fields = {}
    fields['providerAlias'] = module.params.get('providerAlias')
    fields['accountAlias'] = module.params.get('accountAlias')
    fields['productId'] = module.params.get('productId')
    fields['startTime'] = module.params.get('startTime')
    fields['endTime'] = module.params.get('endTime')
    fields['success'] = module.params.get('success')
    fields['errorMessage'] = module.params.get('errorMessage')
    fields['executionId'] = module.params.get('executionId')
    fields['name'] = module.params.get('name')
    fields['dataCenter'] = module.params.get('dataCenter')
    fields['servers'] = module.params.get('servers')
    fields['bearerToken'] = module.params.get('bearerToken')
    fields['count'] = module.params.get('count')
    if fields['count'] is None:
        fields['count'] = 1
    fields['isActive'] = module.params.get('isActive')
    return fields

def addSubscription(fields):
    sleep = False
    if int(fields['count']) > 1:
        sleep = True
    for i in range(int(fields['count'])):
        fields['startTime'] = buildTime()
        try:
            r = requests.post(SUBSCRIPTION_URL, headers = {'Content-Type':'application/json', 'Accept' : 'application/json'}, data = json.dumps(fields))
        except Exception as err:
            raise SubsError("exception occurred while posting subscription, msg is: " + str(err))
        if not (r.status_code == 200):
            raise SubsError("error while posting subscription, http code is: " + str(r.status_code) + ', fields are ' + json.dumps(fields) + ', ' + 'content is [ ' + str(r.content) + ' ]')
        if sleep:
            time.sleep(1.1) # goal is to increment the time stamp to avoid dup key errors. dont need to if just one subscription
    return

from ansible.module_utils.basic import *
def main():
    module = AnsibleModule(argument_spec =  dict(
        providerAlias = dict(required=True),
        accountAlias = dict(required=True),
        productId = dict(required=True),  # product SKU
        startTime = dict(required=True),
        endTime = dict(required=True),
        success = dict(required=True),
        errorMessage = dict(required=True),
        executionId = dict(required=True),
        name = dict(required=True),
        dataCenter = dict(required=True),
        count = dict(required=False),
        servers = dict(required=True),  # list of server IDs'
        bearerToken= dict(required=True),
        isActive= dict(required=False, default=True)))
    try:
        addSubscription(createFields(module))  # method throws exception on anything other than a 200 return.
        module.exit_json(changed=True)
    except Exception as err:
        module.fail_json(msg="error processing subscription, msg is: " + str(err))

if __name__=="__main__":
    main()
