"""UDP network discovery of Audioflow devices."""

import logging
import socket
import sys
from time import sleep


class NetworkDiscovery:
    def __init__(self, discovery_port):
        self.discovery_port = discovery_port
        self.ping = b"afping"
        self.pong = ""
        self.discovered_devices = []

    def nwk_discover_send(self):
        """Send discovery UDP packet to broadcast address"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        try:
            self.sock.bind(("0.0.0.0", self.discovery_port))
        except Exception as e:
            logging.error(f"Unable to bind port {self.discovery_port}: {e}")
            sys.exit(1)

        for x in range(3):  # Send discovery packet three times
            logging.info(f"Sending discovery broadcast {x + 1} of 3...")
            try:
                self.sock.sendto(self.ping, ("<broadcast>", 10499))
            except Exception as e:
                logging.error(f"Unable to send broadcast packet: {e}")
            sleep(3)

    def nwk_discover_receive(self):
        """Listen for discovery response from Audioflow device"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.sock.bind(("0.0.0.0", self.discovery_port))
            logging.debug(f"Opening port {self.discovery_port}")
        except Exception as e:
            logging.error(f"Unable to bind port {self.discovery_port}: {e}")
            logging.error(f"Make sure nothing is currently using port {self.discovery_port}")

        try:
            while True:
                self.pong, self.info = self.sock.recvfrom(1024)
                self.pong = self.pong.decode("utf-8")
                if self.info[0] not in self.discovered_devices:
                    self.discovered_devices.append(self.info[0])
                    logging.info(
                        f"Discovery response received from {self.info[0]}; added to list of discovered devices"
                    )
                else:
                    logging.debug(
                        f"Discovery response received from {self.info[0]}; already in list of discovered devices"
                    )

        except Exception as e:
            logging.error(f"Unable to receive: {e}")
