# -*- coding: utf-8 -*-
import json
import socket
import time

GAME_VERSION = "4.6.5"
TCP_PORT = 50000
DISCOVERY_PORT = 50001
MAX_PLAYERS = 16
MAX_TEAM_PLAYERS = 8
TICK_RATE = 60
STATE_RATE = 20

def send_json(sock, data):
    sock.sendall((json.dumps(data, separators=(",", ":")) + "\n").encode("utf-8"))

def discover_host(join_code, timeout=5):
    join_code = join_code.strip().upper()

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.35)
        request = ("DISCOVER " + join_code).encode("utf-8")
        end_time = time.time() + timeout

        while time.time() < end_time:
            for address in [("255.255.255.255", DISCOVERY_PORT), ("127.0.0.1", DISCOVERY_PORT)]:
                try:
                    sock.sendto(request, address)
                except OSError:
                    pass

            try:
                data, address = sock.recvfrom(4096)
                response = json.loads(data.decode("utf-8"))

                if response.get("join_code") == join_code:
                    return address[0], int(response["port"])
            except socket.timeout:
                pass
            except (OSError, ValueError, KeyError):
                pass

    return None
