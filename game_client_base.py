# -*- coding: utf-8 -*-
import json, math, socket, threading, time
import pygame
from network import GAME_VERSION, send_json
from paths import image_path, font_path


class GameClient:
    def __init__(self, host, port, join_code, name, color):
        self.host, self.port, self.join_code, self.name, self.color = host, port, join_code, name, color
        self.sock = None
        self.running = False
        self.player_id = None
        self.state = {}
        self.lock = threading.Lock()
        self.error = ""
        self.last_shot = 0

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        send_json(self.sock, {"type": "join", "join_code": self.join_code, "name": self.name, "color": self.color, "version": GAME_VERSION})
        self.running = True
        threading.Thread(target=self.receive_loop, daemon=True).start()
        end = time.time() + 5

        while time.time() < end and self.player_id is None and not self.error:
            time.sleep(0.01)

        if self.error:
            raise ConnectionError(self.error)
        if self.player_id is None:
            raise TimeoutError("Server did not respond")

    def receive_loop(self):
        buffer = ""

        try:
            while self.running:
                data = self.sock.recv(65536)

                if not data:
                    raise ConnectionError

                buffer += data.decode()

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)

                    if not line.strip():
                        continue

                    message = json.loads(line)

                    if message.get("type") == "welcome":
                        self.player_id = message["player_id"]
                    elif message.get("type") == "state":
                        with self.lock:
                            self.state = message
                    elif message.get("type") == "error":
                        self.error = message.get("message", "Connection error")
                        self.running = False
        except Exception:
            if self.running:
                self.error = "Connection lost"
            self.running = False

    def load(self, name, size):
        return pygame.transform.scale(pygame.image.load(image_path(name)).convert_alpha(), size)

    def blit_body(self, screen, image, position, angle):
        rotated = pygame.transform.rotate(image, angle)
        offset = (pygame.Vector2(image.get_rect().center) - (53, 80)).rotate(-angle)
        screen.blit(rotated, rotated.get_rect(center=pygame.Vector2(position) + offset))

    def txt(self, screen, font, value, position, color=(240, 240, 240), anchor="topleft"):
        surface = font.render(str(value), True, color)
        rect = surface.get_rect()
        setattr(rect, anchor, position)
        screen.blit(surface, rect)
        return rect

    def transparent_box(self, screen, rect, alpha=128):
        surface = pygame.Surface(rect.size, pygame.SRCALPHA)
        surface.fill((20, 20, 20, alpha))
        screen.blit(surface, rect.topleft)
        pygame.draw.rect(screen, (220, 220, 220), rect, 2)

    def run(self):
        pygame.init()
        screen = pygame.display.set_mode((0, 0))
        width, height = screen.get_size()
        clock = pygame.time.Clock()
        font = pygame.font.Font(font_path(), 16)
        small = pygame.font.Font(font_path(), 11)
        title = pygame.font.Font(font_path(), 40)
        timer_font = pygame.font.Font(font_path(), 34)
        images = {"tread" + str(i): self.load("tread" + str(i) + ".png", (80, 80)) for i in range(1, 4)}

        for color in ["red", "orange", "yellow", "green", "blue", "purple", "pink"]:
            images[color] = self.load(color + "body.png", (106, 160))

        for i in range(1, 5):
            images["grass" + str(i)] = self.load("grass" + str(i) + ".png", (100, 100))

        images["edge"] = self.load("edge.png", (100, 100))
        images["corner"] = self.load("corner.png", (100, 100))
        images["bullet"] = self.load("bullet.png", (10, 16))
        images["bullet_break"] = self.load("bullet_break.png", (10, 16))
        images["ammo"] = self.load("ammo_box.png", (60, 30))
        images["scrap"] = self.load("scrap.png", (34, 34))
        images["health"] = self.load("health_pot.png", (34, 34))
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        field_surface = None
        field_text = None
        input_timer = 0

        while self.running:
            dt = clock.tick(60) / 1000
            clicked = False
            mouse = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    clicked = True

            with self.lock:
                state = dict(self.state)

            players = {player["id"]: player for player in state.get("players", [])}
            you = players.get(self.player_id)

            if not you:
                screen.fill((50, 50, 50))
                self.txt(screen, font, "CONNECTING...", (width // 2, height // 2), anchor="center")
                pygame.display.flip()
                continue

            field = state.get("field", [])
            key = str(field)

            if field and key != field_text:
                field_surface = pygame.Surface((len(field[0]) * 100, len(field) * 100), pygame.SRCALPHA)

                for row_index, row in enumerate(field):
                    for column_index, (name, rot) in enumerate(row):
                        field_surface.blit(pygame.transform.rotate(images[name], -rot * 90), (column_index * 100, row_index * 100))

                field_text = key

            camera_x, camera_y = you["x"], you["y"]
            target = pygame.Vector2(0, -1).angle_to((width // 2 - mouse[0], mouse[1] - height // 2))
            keys = pygame.key.get_pressed()
            over = state.get("match_over", False)
            input_timer += dt

            if input_timer >= 1 / 30 and not over:
                send_json(self.sock, {
                    "type": "input",
                    "left": keys[pygame.K_a] or keys[pygame.K_LEFT],
                    "right": keys[pygame.K_d] or keys[pygame.K_RIGHT],
                    "forward": keys[pygame.K_w] or keys[pygame.K_UP],
                    "backward": keys[pygame.K_s] or keys[pygame.K_DOWN],
                    "aim": target
                })
                input_timer = 0

            if clicked and you["alive"] and not over and time.time() - self.last_shot >= 0.5:
                send_json(self.sock, {"type": "shoot"})
                self.last_shot = time.time()

            screen.fill((50, 50, 50))

            if field_surface:
                screen.blit(field_surface, (width // 2 - 150 - camera_x * 100, height // 2 - 150 - camera_y * 100))

            for ammo in state.get("ammo_positions", []):
                position = ((ammo[0] - camera_x) * 100 + width // 2, (ammo[1] - camera_y) * 100 + height // 2)
                screen.blit(images["ammo"], images["ammo"].get_rect(center=position))

            for scrap in state.get("scrap_positions", []):
                position = ((scrap[0] - camera_x) * 100 + width // 2, (scrap[1] - camera_y) * 100 + height // 2)
                screen.blit(images["scrap"], images["scrap"].get_rect(center=position))

            for health in state.get("health_positions", []):
                position = ((health[0] - camera_x) * 100 + width // 2, (health[1] - camera_y) * 100 + height // 2)
                screen.blit(images["health"], images["health"].get_rect(center=position))

            for bullet in state.get("bullets", []):
                image = pygame.transform.rotate(images["bullet"], bullet["direction"])
                position = ((bullet["x"] - camera_x) * 100 + width // 2, (bullet["y"] - camera_y) * 100 + height // 2)
                screen.blit(image, image.get_rect(center=position))

            for impact in state.get("impacts", []):
                image = pygame.transform.rotate(images["bullet_break"], impact["direction"])
                position = ((impact["x"] - camera_x) * 100 + width // 2, (impact["y"] - camera_y) * 100 + height // 2)
                screen.blit(image, image.get_rect(center=position))

            for player in players.values():
                if not player["alive"]:
                    continue

                player_x = (player["x"] - camera_x) * 100 + width // 2
                player_y = (player["y"] - camera_y) * 100 + height // 2
                tread = pygame.transform.rotate(images["tread" + str(int(player.get("tread_frame", 0)) % 3 + 1)], player["tread_rot"])
                screen.blit(tread, tread.get_rect(center=(player_x, player_y)))
                self.blit_body(screen, images[player["color"]], (player_x, player_y), player["head_rot"])
                name_color = (100, 200, 255) if player["team"] == you["team"] else (255, 120, 120)
                self.txt(screen, small, player["name"], (player_x, player_y + 58), name_color, "midtop")

            stats_rect = pygame.Rect(15, 15, 330, 142)
            self.transparent_box(screen, stats_rect, 128)
            self.txt(screen, font, "HEALTH: " + str(you["health"]), (30, 28))
            self.txt(screen, font, "YOUR AMMO: " + str(you["ammo"]), (30, 58))
            self.txt(screen, font, "YOUR SCRAP: " + str(you.get("scrap", 0)), (30, 88))
            self.txt(screen, font, "TEAM SCRAP: " + str(state.get("team_scrap", 0)), (30, 118))

            remaining = max(0, int(math.ceil(state.get("time_remaining", 0))))
            minutes = remaining // 60
            seconds = remaining % 60
            timer_text = str(minutes) + ":" + str(seconds).zfill(2)
            self.txt(screen, timer_font, timer_text, (width // 2, 38), anchor="midtop")

            if not state.get("match_started", False):
                self.txt(screen, small, "WAITING FOR BOTH TEAMS", (width // 2, 82), (255, 220, 120), "midtop")

            join_code = state.get("join_code", self.join_code)
            self.txt(screen, small, "JOIN CODE: " + join_code, (width - 20, 20), (220, 220, 220), "topright")

            chat = pygame.Rect(width - 490, height - 190, 470, 170)
            self.transparent_box(screen, chat, 128)
            self.txt(screen, small, "GAME CHAT", (chat.x + 12, chat.y + 10))

            for index, message in enumerate(state.get("chat", [])[-7:]):
                self.txt(screen, small, message, (chat.x + 12, chat.y + 35 + index * 18))

            alpha = max(0, min(100, int(100 * (1 - you["health"] / 100))))
            overlay.fill((255, 0, 0, alpha))
            screen.blit(overlay, (0, 0))

            if not you["alive"] and not over:
                self.txt(screen, title, "YOU DIED!", (width // 2, height // 2 - 90), anchor="center")
                rect = pygame.Rect(width // 2 - 170, height // 2 + 45, 340, 52)
                pygame.draw.rect(screen, (100, 100, 100) if rect.collidepoint(mouse) else (70, 70, 70), rect)
                pygame.draw.rect(screen, (230, 230, 230), rect, 2)
                self.txt(screen, font, "RESPAWN", rect.center, anchor="center")

                if clicked and rect.collidepoint(mouse):
                    send_json(self.sock, {"type": "respawn"})

            if over:
                shade = pygame.Surface((width, height), pygame.SRCALPHA)
                shade.fill((0, 0, 0, 210))
                screen.blit(shade, (0, 0))
                winner = state.get("winner")
                heading = "DRAW!" if winner == -1 else ("YOUR TEAM WON!" if winner == you["team"] else "YOUR TEAM LOST!")
                self.txt(screen, title, heading, (width // 2, 55), anchor="midtop")
                rematch = max(0, int(math.ceil(state.get("rematch_time_remaining", 0))))
                self.txt(screen, small, "NEXT GAME IN " + str(rematch) + "s", (width // 2, height - 28), (210, 210, 210), "midbottom")
                scrap_totals = state.get("team_scrap_totals", [0, 0])
                self.txt(screen, font, "TEAM 1 SCRAP: " + str(scrap_totals[0]) + "   TEAM 2 SCRAP: " + str(scrap_totals[1]), (width // 2, 110), anchor="midtop")
                self.txt(screen, font, "RANKED BY KILLS - DEATHS", (width // 2, 145), anchor="midtop")
                rows = state.get("rankings", [])
                table_width = 830
                x = width // 2 - table_width // 2
                y = 185
                pygame.draw.rect(screen, (30, 30, 30), (x, y, table_width, 50 + 30 * max(1, len(rows))))
                pygame.draw.rect(screen, (220, 220, 220), (x, y, table_width, 50 + 30 * max(1, len(rows))), 2)

                for label, offset in [("RANK", 15), ("PLAYER", 105), ("TEAM", 390), ("KILLS", 500), ("DEATHS", 590), ("DIFF", 685), ("SCRAP", 760)]:
                    self.txt(screen, small, label, (x + offset, y + 15), anchor="midtop")

                for index, row in enumerate(rows):
                    row_y = y + 50 + index * 30

                    for value, offset in [(index + 1, 15), (row["name"], 105), (row["team"] + 1, 390), (row["kills"], 500), (row["deaths"], 590), (row["difference"], 685), (row.get("scrap", 0), 760)]:
                        self.txt(screen, small, value, (x + offset, row_y))

                exit_rect = pygame.Rect(width - 220, height - 80, 190, 50)
                pygame.draw.rect(screen, (105, 105, 105) if exit_rect.collidepoint(mouse) else (70, 70, 70), exit_rect)
                pygame.draw.rect(screen, (230, 230, 230), exit_rect, 2)
                self.txt(screen, font, "EXIT", exit_rect.center, anchor="center")

                if clicked and exit_rect.collidepoint(mouse):
                    self.running = False

            pygame.display.flip()

        try:
            self.sock.close()
        except OSError:
            pass

        pygame.quit()