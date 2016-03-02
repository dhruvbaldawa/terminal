import sys
import traceback
import constants as c

from flask import Flask, render_template
from flask.ext.socketio import SocketIO
from os.path import abspath, dirname
from serial.tools.list_ports import comports
from serial.threaded import LineReader


app = Flask(__name__)
app.config['APP_ROOT'] = abspath(dirname(abspath(__file__)) + '/..')
app.debug = True
app.secret_key = 'sekrit'

DEFAULT_NAMESPACE = '/socket.io'

socket_io = SocketIO(app)
greenlet = None


# Serial communications
def serialize_ports(comport):
    return {
        'device': comport.device,
        'name': comport.name,
        'description': comport.description,
        'manufacturer': comport.manufacturer,
    }


def get_serial_ports():
    return [serialize_ports(comport) for comport in comports()]


class SerialInputHandler(LineReader):
    def connection_made(self, transport):
        super(SerialInputHandler, self).connection_made(transport)
        # @FIXME; EMIT THE PORT EMIT EVENT

    def handle_line(self, data):
        # @FIXME: ADD TO DATABASE AND EMIT DATA EVENT
        pass

    def connection_lost(self, exc):
        if exc:
            traceback.print_exc(exc)
        # @FIXME: EMIT THE DISCONNECTION EVENT


# Communication protocol
@socket_io.on('json', namespace=DEFAULT_NAMESPACE)
def handleJson(message):
    if message.type == c.JSON_RX_COMPORTS_LIST:
        sendJson(c.JSON_TX_COMPORTS_LIST, get_serial_ports())


def sendJson(type, input):
    socket_io.emit("json", {"v": 1, "type": type, "data": input},
                   json=True)


# Socket communications


@socket_io.on('connect', namespace=DEFAULT_NAMESPACE)
def connect():
    print 'connected'
    sendJson(c.JSON_TX_COMPORTS_LIST, get_serial_ports())

# Application views


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    if len(sys.argv) > 2:
        LOG = sys.argv[1]
    socket_io.run(app)
