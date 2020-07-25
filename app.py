import enum

from flask import Flask
from flask_restful import Api, Resource, reqparse, marshal, fields
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from pymodbus.payload import BinaryPayloadBuilder
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian
builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)

class ModbusTypePrefix(enum.Enum):
    """Modbus types and their address prefixes."""
    DISCRETE_INPUT = 0
    COIL = 1
    INPUT_REGISTER = 3
    HOLDING_REGISTER = 4


class TCPReadAPI(Resource):
    """
    Handles TCP Read calls.
    """

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('ip', type=str, required=True, location='json',
                                   help='No IP address provided')
        self.reqparse.add_argument('port', type=int, required=True, location='json',
                                   help='No port provided')
        self.reqparse.add_argument('slave_id', type=int, required=True, location='json',
                                   help='No Modbus Slave ID provided')
        self.reqparse.add_argument('type_prefix', type=int, required=True, location='json',
                                   choices=[p.value for p in ModbusTypePrefix],
                                   help='Modbus register type prefix incorrect')
        self.reqparse.add_argument('start_address', type=int, required=True, location='json',
                                   help='No register start address provided')
        self.reqparse.add_argument('count', type=int, required=False, location='json',
                                   default=1)
        super(TCPReadAPI, self).__init__()

    def post(self):
        query = self.reqparse.parse_args()
        client = ModbusClient(query['ip'], query['port'])
        client.connect()

        data = None
        start_address = query['start_address']
        count = query['count']
        if query['type_prefix'] == ModbusTypePrefix.DISCRETE_INPUT.value:
            data = client.read_discrete_inputs(start_address, count, unit=1)
        elif query['type_prefix'] == ModbusTypePrefix.COIL.value:
            data = client.read_coils(start_address, count, unit=1)
        elif query['type_prefix'] == ModbusTypePrefix.INPUT_REGISTER.value:
            data = client.read_input_registers(start_address, count, unit=1)
        elif query['type_prefix'] == ModbusTypePrefix.HOLDING_REGISTER.value:
            data = client.read_holding_registers(start_address, count, unit=1)

        client.close()

        result = []
        
        
        if hasattr(data, 'bits'):
            d = data.bits
        else:
            d = data.registers

        decoder = BinaryPayloadDecoder.fromRegisters(result.registers, endian=Endian.Big)
        decoder.reset()
        decoded = {
            'string': decoder.decode_string(8),
            'float': decoder.decode_32bit_float(),
            '16uint': decoder.decode_16bit_uint(),
            'ignored': decoder.skip_bytes(2),
            '8int': decoder.decode_8bit_int(),
            'bits': decoder.decode_bits(),
        }

        for name, value in iteritems(decoded):
            result.append({'address': name, 'value': value})


        # for i, v in enumerate(d):
        #     result.append({'address': i+start_address, 'value': v})

        reg_fields = {'address': fields.Integer, 'value': fields.Integer}
        return {'registers': [marshal(reg, reg_fields) for reg in result]}


class TCPWriteAPI(Resource):
    """
    Handles TCP Write calls.
    """

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('ip', type=str, required=True, location='json',
                                   help='No IP address provided')
        self.reqparse.add_argument('port', type=int, required=True, location='json',
                                   help='No port provided')
        self.reqparse.add_argument('slave_id', type=int, required=True, location='json',
                                   help='No Modbus Slave ID provided')
        self.reqparse.add_argument('type_prefix', type=int, required=True, location='json',
                                   choices=[ModbusTypePrefix.COIL.value, ModbusTypePrefix.HOLDING_REGISTER.value],
                                   help='Modbus register type prefix incorrect')
        self.reqparse.add_argument('start_address', type=int, required=True, location='json',
                                   help='No register start address provided')
        self.reqparse.add_argument('data', type=int, required=True, location='json',
                                   action='append',
                                   help='No input data provided')
        super(TCPWriteAPI, self).__init__()

    def post(self):
        query = self.reqparse.parse_args()
        client = ModbusClient(query['ip'], query['port'])
        client.connect()

        data = query['data']
        start_address = query['start_address']
        builder.reset()
        for vol in data:
            print(vol)
            builder.add_32bit_float(vol)
        parsed = builder.build()
        # parsed = parsed[0::2]
        print(parsed)
        if query['type_prefix'] == ModbusTypePrefix.COIL.value:
            client.write_coils(start_address, parsed, skip_encode=True, unit=1)
        elif query['type_prefix'] == ModbusTypePrefix.HOLDING_REGISTER.value:
            client.write_registers(start_address, parsed, skip_encode=True, unit=1)

        client.close()

        return {'result': True}


app = Flask(__name__)
api = Api(app)
api.add_resource(TCPReadAPI, '/modbus-explorer/api/tcp/read')
api.add_resource(TCPWriteAPI, '/modbus-explorer/api/tcp/write')

if __name__ == '__main__':
    app.run()
