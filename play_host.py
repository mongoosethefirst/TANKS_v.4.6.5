# -*- coding: utf-8 -*-
import pygame
from game_client_base import GameClient
from network import TCP_PORT
from new import server, host_name, host_color, host_join_code

client = GameClient("127.0.0.1", TCP_PORT, host_join_code, host_name, host_color)

try:
    client.connect()
    client.run()
finally:
    server.stop()
    pygame.quit()
