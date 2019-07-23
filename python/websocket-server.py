#!/usr/bin/env python3

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import ptvsd

# Allow other computers to attach to ptvsd at this IP address and port, using the secret
# ptvsd.enable_attach(address=('0.0.0.0', 3000))
# Pause the program until a remote debugger is attached
# ptvsd.wait_for_attach()

import os
import sys
fileDir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(fileDir, "../build/python"))

import txaio
txaio.use_twisted()

from autobahn.twisted.websocket import WebSocketServerProtocol, \
    WebSocketServerFactory
from twisted.internet import task, reactor, threads
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.internet.ssl import DefaultOpenSSLContextFactory
from twisted.python import log

import argparse
import cv2
import imagehash
import json
import io
from io import BytesIO
from PIL import Image
import numpy as np
import base64
from datetime import datetime
from openpose import pyopenpose as op

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=9000,
                    help='WebSocket Port')
args = parser.parse_args()

class OpenPoseServerProtocol(WebSocketServerProtocol):
    def __init__(self):
        super(OpenPoseServerProtocol, self).__init__()

        params = dict()
        params["model_folder"] = "../models/"
        params["num_gpu"] = 1
        params["num_gpu_start"] = 3

        self.opWrapper = op.WrapperPython()
        self.opWrapper.configure(params)
        self.opWrapper.start()

    def onConnect(self, request):
        print("Client connecting: {0}".format(request.peer))

    def onOpen(self):
        print("WebSocket connection open.")

    def onMessage(self, payload, isBinary):
        raw = payload.decode('utf8')
        msg = json.loads(raw)

        if msg['type'] == "FRAME":
            dataURL = msg['dataURL']

            if "keyframe" in msg:
                keyframe = msg['keyframe']
            else:
                keyframe = start

            if "robotId" in msg:
                robotId = msg['robotId']
            else:
                robotId = ""

            if "videoId" in msg:
                videoId = msg['videoId']
            else:
                videoId = ""

            video_serial = robotId + "-" + videoId
            print("FRAME - {}".format(video_serial))

            head = "data:image/jpeg;base64,"
            assert(dataURL.startswith(head))
            imgData = base64.b64decode(dataURL[len(head):])
            buffer = io.BytesIO(imgData)
            imgPIL = Image.open(buffer)
            img = np.array(imgPIL.convert('RGB'))

            self.datum = op.Datum()
            self.datum.cvInputData = img
            self.opWrapper.emplaceAndPop([self.datum])
            
            msg = {
                "type": "BODY_POSE",
                "robotId": robotId,
                "videoId": videoId,
                "keyframe": keyframe,
                "poseKeypoints": self.datum.poseKeypoints.tolist(),
                "time": datetime.now().isoformat(),
            }

            self.pushMessage(msg)

    def onClose(self, wasClean, code, reason):
        print("WebSocket connection closed: {0}".format(reason))

    def pushMessage(self, msg):
        reactor.callFromThread(self.sendMessage, json.dumps(msg).encode(), sync=True)


def main(reactor):
    observer = log.startLogging(sys.stdout)
    observer.timeFormat = "%Y-%m-%d %T.%f"
    factory = WebSocketServerFactory()
    factory.setProtocolOptions(autoPingInterval=1, autoPingTimeout=2)
    factory.protocol = OpenPoseServerProtocol
    # ctx_factory = DefaultOpenSSLContextFactory(tls_key, tls_crt)
    # reactor.listenSSL(args.port, factory, ctx_factory)
    reactor.listenTCP(args.port, factory)
    reactor.run()
    return Deferred()


if __name__ == '__main__':
    task.react(main)
