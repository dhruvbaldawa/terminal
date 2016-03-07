import sys
import serial
import gevent
import constants as c

from os.path import abspath, dirname
from datetime import datetime
from flask import Flask, render_template
from flask.ext.socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from serial.tools.list_ports import comports


app = Flask(__name__)
app.config['APP_ROOT'] = abspath(dirname(abspath(__file__)) + '/..')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
db = SQLAlchemy(app)
app.debug = True
app.secret_key = 'sekrit'

DEFAULT_NAMESPACE = '/'


socket_io = SocketIO(app, async_mode="gevent")
readerThread = None
readerGreenlet = None


class LogEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.now)
    level = db.Column(db.Text, default=None)
    text = db.Column(db.Text, default=None)

    @staticmethod
    def makeLogEntry(intext):
        log_entry = LogEntry()
        if intext.startswith(c.LVL_DEBUG + ":"):
            log_entry.level = c.LVL_DEBUG
        elif intext.startswith(c.LVL_INFO + ":"):
            log_entry.level = c.LVL_INFO
        elif intext.startswith(c.LVL_ERROR + ":"):
            log_entry.level = c.LVL_ERROR
        else:
            log_entry.level = c.LVL_OTHER
        log_entry.text = intext
        return log_entry

    def save(self):
        db.session.add(self)
        db.session.commit()


# Communication protocol

def sendJson(type, input):
    socket_io.emit("json", {"v": 1, "type": type, "data": input},
                   json=True)


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


def read_from_port(ser):
    sys.stdout.write('start\n')
    try:
        with ser:
            sendJson(c.JSON_TX_NOTIFICATION,
                     {"type": "success", "message": "Serial port connected"})
            while True:
                data = ser.readline()
                if data:
                    handle_data(data.strip())
    except gevent.GreenletExit:
        print "closing serial port"


def start_serial_port_reader(port, baudrate):
    global readerGreenlet
    stop_serial_port_reader()
    serial_port = serial.Serial(port, baudrate, timeout=0)
    readerGreenlet = gevent.spawn(read_from_port, serial_port)


def stop_serial_port_reader():
    global readerGreenlet
    if readerGreenlet is not None:
        readerGreenlet.kill()
        readerGreenlet = None
        sendJson(c.JSON_TX_NOTIFICATION,
                 {"type": "error", "message": "Serial port disconnected"})


def handle_data(data):
    log_entry = LogEntry.makeLogEntry(data)
    log_entry.save()
    sendJson(c.JSON_TX_COMPORTS_DATA, data)


# Socket communications


@socket_io.on('connect', namespace=DEFAULT_NAMESPACE)
def connect():
    print 'connected'
    sendJson(c.JSON_TX_COMPORTS_LIST, get_serial_ports())


@socket_io.on('json', namespace=DEFAULT_NAMESPACE)
def handleJson(message):
    print "Received message", message

    if message['type'] == c.JSON_RX_COMPORTS_LIST:
        stop_serial_port_reader()
        sendJson(c.JSON_TX_COMPORTS_LIST, get_serial_ports())

    elif message['type'] == c.JSON_RX_COMPORTS_CONNECT:
        if 'data' not in message or not message['data']:
            sendJson(c.JSON_TX_NOTIFICATION,
                     {"type": "error", "message": "Invalid serial port"})
            return
        start_serial_port_reader(message['data'], c.BAUD_RATE)

    elif message['type'] == c.JSON_RX_COMPORTS_DISCONNECT:
        stop_serial_port_reader()


# Application views


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    if len(sys.argv) > 2:
        LOG = sys.argv[1]
    socket_io.run(app)
