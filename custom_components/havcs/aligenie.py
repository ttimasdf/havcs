import json
from urllib.request import urlopen
import logging

from .util import decrypt_device_id, encrypt_device_id, deserialize_custom_actions
from .helper import VoiceControlProcessor, VoiceControlDeviceManager
from .const import ATTR_DEVICE_ACTIONS

_LOGGER = logging.getLogger(__name__)
# _LOGGER.setLevel(logging.DEBUG)
LOGGER_NAME = 'aligenie'

DOMAIN = 'aligenie'

def createHandler(hass, entry):
    mode = ['handler']
    return VoiceControlAligenie(hass, mode, entry)

class PlatformParameter:
    device_attribute_map_h2p = {
        'power_state': 'powerstate',
        'color': 'color',
        'temperature': 'temperature',
        'humidity': 'humidity',
        # '': 'windspeed',
        'brightness': 'brightness',
        # '': 'direction',
        # '': 'angle',
        'pm25': 'pm2.5',
    }
    device_action_map_h2p ={
        'turn_on': 'TurnOn',
        'turn_off': 'TurnOff',
        'increase_brightness': 'AdjustUpBrightness',
        'decrease_brightness': 'AdjustDownBrightness',
        'set_brightness': 'SetBrightness',
        'increase_temperature': 'AdjustUpTemperature',
        'decrease_temperature': 'AdjustDownTemperature',
        'set_temperature': 'SetTemperature',
        'set_color': 'SetColor',
        'pause': 'Pause',
        'query_color': 'QueryColor',
        'query_power_state': 'QueryPowerState',
        'query_temperature': 'QueryTemperature',
        'query_humidity': 'QueryHumidity',
        # '': 'QueryWindSpeed',
        # '': 'QueryBrightness',
        # '': 'QueryFog',
        # '': 'QueryMode',
        # '': 'QueryPM25',
        # '': 'QueryDirection',
        # '': 'QueryAngle'
    }
    _device_type_alias = {
        'television': '电视',
        'light': '灯',
        'camera': '摄像头',
        'aircondition': '空调',
        'airpurifier': '空气净化器',
        'outlet': '插座',
        'switch': '开关',
        'roboticvacuum': '扫地机器人',
        'curtain': '窗帘',
        'humidifier': '加湿器',
        'fan': '风扇',
        'bottlewarmer': '暖奶器',
        'soymilkmaker': '豆浆机',
        'kettle': '电热水壶',
        'waterdispenser': '饮水机',
        'camera': '摄像头',
        'router': '路由器',
        'cooker': '电饭煲',
        'waterheater': '热水器',
        'oven': '烤箱',
        'waterpurifier': '净水器',
        'fridge': '冰箱',
        'STB': '机顶盒',
        'sensor': '传感器',
        'washmachine': '洗衣机',
        'smartbed': '智能床',
        'aromamachine': '香薰机',
        'window': '窗',
        'kitchenventilator': '抽油烟机',
        'fingerprintlock': '指纹锁',
        'telecontroller': '万能遥控器',
        'dishwasher': '洗碗机',
        'dehumidifier': '除湿机',
        'dryer': '干衣机',
        'wall-hung-boiler': '壁挂炉',
        'microwaveoven': '微波炉',
        'heater': '取暖器',
        'mosquitoDispeller': '驱蚊器',
        'treadmill': '跑步机',
        'smart-gating': '智能门控',
        'smart-band': '智能手环',
        'hanger': '晾衣架',
        'bloodPressureMeter': '血压仪',
        'bloodGlucoseMeter': '血糖仪',
    }

    device_type_map_h2p = {
        'climate': 'aircondition',
        'fan': 'fan',
        'light': 'light',
        'camera': 'camera',
        'media_player': 'television',
        'remote': 'telecontroller',
        'switch': 'switch',
        'sensor': 'sensor',
        'cover': 'curtain',
        'vacuum': 'roboticvacuum',
        }

    _service_map_p2h = {
        'cover': {
            'TurnOn':  'open_cover',
            'TurnOff': 'close_cover',
            'Pause': 'stop_cover',
        },
        'vacuum': {
            'TurnOn':  'start',
            'TurnOff': 'return_to_base',
        },
        'light': {
            'TurnOn':  'turn_on',
            'TurnOff': 'turn_off',
            'SetBrightness':        lambda state, attributes, payload: (['light'], ['turn_on'], [{'brightness_pct': payload['value']}]),
            'AdjustUpBrightness':   lambda state, attributes, payload: (['light'], ['turn_on'], [{'brightness_pct': min(attributes['brightness_pct'] + payload['value'], 100)}]),
            'AdjustDownBrightness': lambda state, attributes, payload: (['light'], ['turn_on'], [{'brightness_pct': max(attributes['brightness_pct'] - payload['value'], 0)}]),
            'SetColor':             lambda state, attributes, payload: (['light'], ['turn_on'], [{"color_name": payload['value']}])
        },
        'camera':{
            'TurnOn': deserialize_custom_actions("turn_on", default_action=(['input_boolean'], ['turn_on'], [{}])),
            'TurnOff': deserialize_custom_actions("turn_off", default_action=(['input_boolean'], ['turn_off'], [{}])),
            'SetBrightness': deserialize_custom_actions("set_brightness", default_action=(['input_boolean'], ['turn_on'], [{}])),
            'AdjustUpBrightness': deserialize_custom_actions("increase_brightness", default_action=(['input_boolean'], ['turn_on'], [{}])),
            'AdjustDownBrightness': deserialize_custom_actions("decrease_brightness", default_action=(['input_boolean'], ['turn_on'], [{}])),
        },
        'havcs':{
            'TurnOn': deserialize_custom_actions("turn_on", default_action=(['input_boolean'], ['turn_on'], [{}])),
            'TurnOff': deserialize_custom_actions("turn_off", default_action=(['input_boolean'], ['turn_off'], [{}])),
            'SetBrightness': deserialize_custom_actions("set_brightness", default_action=(['input_boolean'], ['turn_on'], [{}])),
            'AdjustUpBrightness': deserialize_custom_actions("increase_brightness", default_action=(['input_boolean'], ['turn_on'], [{}])),
            'AdjustDownBrightness': deserialize_custom_actions("decrease_brightness", default_action=(['input_boolean'], ['turn_on'], [{}])),
        }
    }
    # action:[{Platfrom Attr: HA Attr},{}]
    _query_map_p2h = {

    }

class VoiceControlAligenie(PlatformParameter, VoiceControlProcessor):
    def __init__(self, hass, mode, entry):
        self._hass = hass
        self._mode = mode
        try:
            self._zone_constraints  = json.loads(urlopen('https://open.bot.tmall.com/oauth/api/placelist').read().decode('utf-8'))['data']
            self._device_name_constraints = json.loads(urlopen('https://open.bot.tmall.com/oauth/api/aliaslist').read().decode('utf-8'))['data']
            self._device_name_constraints.append({'key': '电视', 'value': ['电视机']})
            self._device_name_constraints.append({'key': '传感器', 'value': ['传感器']})
        except:
            self._zone_constraints = []
            self._device_name_constraints = []
            import traceback
            _LOGGER.info("[%s] can get places and aliases data from website, set None.\n%s", LOGGER_NAME, traceback.format_exc())
        self.vcdm = VoiceControlDeviceManager(entry, DOMAIN, self.device_action_map_h2p, self.device_attribute_map_h2p, self._service_map_p2h, self.device_type_map_h2p, self._device_type_alias, self._device_name_constraints, self._zone_constraints)

    def _errorResult(self, errorCode, messsage=None):
        """Generate error result"""
        messages = {
            'INVALIDATE_CONTROL_ORDER': 'invalidate control order',
            'SERVICE_ERROR': 'service error',
            'DEVICE_NOT_SUPPORT_FUNCTION': 'device not support',
            'INVALIDATE_PARAMS': 'invalidate params',
            'DEVICE_IS_NOT_EXIST': 'device is not exist',
            'IOT_DEVICE_OFFLINE': 'device is offline',
            'ACCESS_TOKEN_INVALIDATE': ' access_token is invalidate'
        }
        return {'errorCode': errorCode, 'message': messsage if messsage else messages[errorCode]}

    async def handleRequest(self, data, auth = False):
        """Handle request"""
        _LOGGER.info(f"[{LOGGER_NAME}] Handle Request: {data}")

        header = self._parse_command(data, 'header')
        payload = self._parse_command(data, 'payload')
        action = self._parse_command(data, 'action')
        namespace = self._parse_command(data, 'namespace')
        properties = None
        content = {}

        if auth:
            if namespace == 'AliGenie.Iot.Device.Discovery':
                err_result, discovery_devices, entity_ids = self.process_discovery_command()
                content = {'devices': discovery_devices}
            elif namespace == 'AliGenie.Iot.Device.Control':
                err_result, content = await self.process_control_command(data)
            elif namespace == 'AliGenie.Iot.Device.Query':
                err_result, content = self.process_query_command(data)
                if not err_result:
                    properties = content
                    content = {}
            else:
                err_result = self._errorResult('SERVICE_ERROR')
        else:
            err_result = self._errorResult('ACCESS_TOKEN_INVALIDATE')

        # Check error and fill response name
        if err_result:
            header['name'] = 'ErrorResponse'
            content = err_result
        else:
            header['name'] = action + 'Response'

        # Fill response deviceId
        if 'deviceId' in payload:
            content['deviceId'] = payload['deviceId']

        response = {'header': header, 'payload': content}
        if properties:
            response['properties'] = properties
        _LOGGER.info(f"[{LOGGER_NAME}] Respnose: {repr(response)[:30]}...")
        return response

    def _parse_command(self, command, arg):
        header = command['header']
        payload = command['payload']

        if arg == 'device_id':
            return payload['deviceId']
        elif arg == 'action':
            return header['name']
        elif arg == 'user_uid':
            return payload.get('openUid','')
        elif arg == 'namespace':
            return header['namespace']
        else:
            return command.get(arg)

    def _discovery_process_propertites(self, device_properties):
        properties = []
        for device_property in device_properties:
            name = self.device_attribute_map_h2p.get(device_property.get('attribute'))
            state = self._hass.states.get(device_property.get('entity_id'))
            if name and state:
                properties += [{'name': name.lower(), 'value': state.state}]
        return properties if properties else [{'name': 'powerstate', 'value': 'off'}]
    
    def _discovery_process_actions(self, device_properties, raw_actions):
        actions = []
        for device_property in device_properties:
            name = self.device_attribute_map_h2p.get(device_property.get('attribute'))
            if name:
                action = self.device_action_map_h2p.get('query_'+name)
                if action:
                    actions += [action,]
        for raw_action in raw_actions:
            action = self.device_action_map_h2p.get(raw_action)
            if action:
                actions += [action,]
        return list(set(actions))

    def _discovery_process_device_type(self, raw_device_type):
        return self.device_type_map_h2p.get(raw_device_type)

    def _discovery_process_device_info(self, device_id,  device_type, device_name, zone, properties, actions):
        return {
            'deviceId': encrypt_device_id(device_id),
            'deviceName': device_name,
            'deviceType': device_type,
            'zone': zone,
            'model': device_name,
            'brand': 'HomeAssistant',
            'icon': 'https://d33wubrfki0l68.cloudfront.net/cbf939aa9147fbe89f0a8db2707b5ffea6c192cf/c7c55/images/favicon-192x192-full.png',
            'properties': properties,
            'actions': actions
            #'extensions':{'extension1':'','extension2':''}
        }


    def _control_process_propertites(self, device_properties, action) -> None:
        return {}

    def _query_process_propertites(self, device_properties, action) -> None:
        properties = []
        action = action.replace('Request', '').replace('Get', '')
        if action in self._query_map_p2h:
            for property_name, attr_template in self._query_map_p2h[action].items():
                formattd_property = self.vcdm.format_property(self._hass, device_properties, attr_template)
                properties.append({property_name:formattd_property})
        else:
            for device_property in device_properties:
                state = self._hass.states.get(device_property.get('entity_id'))
                value = state.attributes.get(device_property.get('attribute'), state.state) if state else None
                if value:
                    if action == 'Query':
                        formattd_property = {'name': self.device_attribute_map_h2p.get(device_property.get('attribute')), 'value': value}
                        properties.append(formattd_property)
                    elif device_property.get('attribute') in action.lower():
                        formattd_property = {'name': self.device_attribute_map_h2p.get(device_property.get('attribute')), 'value': value}
                        properties = [formattd_property]
                        break
        return properties

    def _decrypt_device_id(self, device_id) -> None:
        return decrypt_device_id(device_id)