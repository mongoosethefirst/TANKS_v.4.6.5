# -*- coding: utf-8 -*-
import json
import math
import random
import socket
import string
import threading
import time

from network import GAME_VERSION, TCP_PORT, DISCOVERY_PORT, MAX_PLAYERS, MAX_TEAM_PLAYERS, TICK_RATE, STATE_RATE, send_json

class GameServer:
    def __init__(self, host="0.0.0.0", port=TCP_PORT, match_minutes=10):
        self.host = host
        self.port = port
        self.match_minutes = max(1, min(120, int(match_minutes)))
        self.match_seconds = self.match_minutes * 60
        self.match_started = False
        self.match_start_time = None
        self.join_code = "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        self.players = {}
        self.clients = {}
        self.inputs = {}
        self.bullets = []
        self.impacts = []
        self.field = []
        self.ammo_positions = []
        self.scrap_positions = []
        self.health_positions = []
        self.chat = []
        self.next_player_id = 0
        self.next_bullet_id = 0
        self.running = False
        self.match_over = False
        self.winner = None
        self.rematch_seconds = 15
        self.rematch_start_time = None
        self.next_heal_times = {}
        self.lock = threading.RLock()
        self.server_socket = None
        self.next_scrap_spawn = time.monotonic() + random.uniform(5, 15)
        self.next_health_spawn = time.monotonic() + 30
        self.create_field()

    def create_field(self):
        self.field = []
        self.ammo_positions = []
        self.scrap_positions = []
        self.health_positions = []
        self.field.append([["corner", 0]] + [["edge", 1] for _ in range(20)] + [["corner", 1]])

        for y in range(20):
            line = [["edge", 0]]

            for x in range(20):
                line.append(["grass" + str(random.randint(1, 4)), random.randint(0, 3)])

                #if random.randint(1, 45) == 1 and not self.object_at(x, y):
                    #self.ammo_positions.append([x, y, 10])

            line.append(["edge", 2])
            self.field.append(line)

        self.field.append([["corner", 3]] + [["edge", 3] for _ in range(20)] + [["corner", 2]])

    def add_chat(self, message):
        self.chat.append(message)
        self.chat = self.chat[-8:]

    def choose_team(self):
        counts = [sum(1 for player in self.players.values() if player["team"] == team) for team in (0, 1)]

        if counts[0] >= MAX_TEAM_PLAYERS and counts[1] >= MAX_TEAM_PLAYERS:
            return None
        if counts[0] >= MAX_TEAM_PLAYERS:
            return 1
        if counts[1] >= MAX_TEAM_PLAYERS:
            return 0
        return 0 if counts[0] <= counts[1] else 1

    def spawn_for(self, player_id, team):
        slot = sum(1 for player in self.players.values() if player["team"] == team and player["id"] < player_id)
        return 6.0 + slot, 0.8 if team == 0 else 18.2, 180 if team == 0 else 0

    def add_player(self, name, color):
        with self.lock:
            if len(self.players) >= MAX_PLAYERS or self.match_over:
                return None

            team = self.choose_team()

            if team is None:
                return None

            player_id = self.next_player_id
            self.next_player_id += 1
            x, y, rot = self.spawn_for(player_id, team)
            self.players[player_id] = {
                "id": player_id,
                "name": (name.strip() or "PLAYER")[:20],
                "color": color,
                "team": team,
                "x": x,
                "y": y,
                "tread_rot": rot,
                "head_rot": rot,
                "health": 100,
                "ammo": 30,
                "scrap": 0,
                "alive": True,
                "tread_frame": 0.0,
                "kills": 0,
                "deaths": 0
            }
            self.inputs[player_id] = {"left": False, "right": False, "forward": False, "backward": False, "aim": rot}
            self.next_heal_times[player_id] = time.monotonic() + 5
            self.add_chat(self.players[player_id]["name"] + " joined!")
            self.try_start_match()
            return player_id

    def remove_player(self, player_id):
        with self.lock:
            player = self.players.pop(player_id, None)
            self.inputs.pop(player_id, None)
            self.next_heal_times.pop(player_id, None)
            client = self.clients.pop(player_id, None)

            if client:
                try:
                    client.close()
                except OSError:
                    pass

            if player and not self.match_over:
                self.add_chat(player["name"] + " left!")

    def try_start_match(self):
        if self.match_started or len(self.players) < 2:
            return

        team_counts = [sum(1 for player in self.players.values() if player["team"] == team) for team in (0, 1)]

        if team_counts[0] > 0 and team_counts[1] > 0:
            self.match_started = True
            self.match_start_time = time.monotonic()
            self.next_scrap_spawn = self.match_start_time + random.uniform(5, 15)
            self.next_health_spawn = self.match_start_time + 30
            self.add_chat("Match started!")

    def blocked_tile(self, x, y):
        item = math.floor(x + 1.5)
        row = math.floor(y + 1.5)

        if row < 0 or row >= len(self.field) or item < 0 or item >= len(self.field[row]):
            return True

        return self.field[row][item][0] in ("edge", "corner")

    def tank_blocked(self, x, y, rot):
        half = 0.4
        radians = math.radians(-rot)
        cosine = math.cos(radians)
        sine = math.sin(radians)
        points = [(-half, -half), (half, -half), (-half, half), (half, half), (0, -half), (0, half), (-half, 0), (half, 0)]

        for offset_x, offset_y in points:
            rotated_x = offset_x * cosine - offset_y * sine
            rotated_y = offset_x * sine + offset_y * cosine

            if self.blocked_tile(x + rotated_x, y + rotated_y):
                return True

        return False

    def turn_toward(self, current, target, amount):
        difference = (target - current + 180) % 360 - 180
        return (current + max(-amount, min(amount, difference))) % 360

    def object_at(self, x, y, include_players=True):
        for position in self.ammo_positions:
            if math.hypot(position[0] - x, position[1] - y) < 0.7:
                return True

        for position in self.scrap_positions:
            if math.hypot(position[0] - x, position[1] - y) < 0.7:
                return True

        for position in self.health_positions:
            if math.hypot(position[0] - x, position[1] - y) < 0.7:
                return True

        if include_players:
            for player in self.players.values():
                if player["alive"] and math.hypot(player["x"] - x, player["y"] - y) < 0.9:
                    return True

        return False

    def random_open_position(self):
        available = []

        for y in range(20):
            for x in range(20):
                if not self.object_at(x, y):
                    available.append((x, y))

        return random.choice(available) if available else None

    def open_drop_position(self, center_x, center_y, starting_radius=2):
        center_x = round(center_x)
        center_y = round(center_y)

        for radius in range(starting_radius, 21):
            available = []

            for y in range(max(0, center_y - radius), min(20, center_y + radius + 1)):
                for x in range(max(0, center_x - radius), min(20, center_x + radius + 1)):
                    if math.hypot(x - center_x, y - center_y) <= radius and not self.object_at(x, y):
                        available.append((x, y))

            if available:
                return random.choice(available)

        return None

    def spawn_scrap(self):
        position = self.random_open_position()

        if position:
            self.scrap_positions.append([position[0], position[1]])

    def spawn_ammo(self):
        position = self.random_open_position()

        if position:
            self.ammo_positions.append([position[0], position[1], 10])

    def spawn_health(self):
        position = self.random_open_position()

        if position:
            self.health_positions.append([position[0], position[1]])

    def drop_scrap(self, player):
        amount = player["scrap"]
        player["scrap"] = 0

        for _ in range(amount):
            position = self.open_drop_position(player["x"], player["y"], 2)

            if position:
                self.scrap_positions.append([position[0], position[1]])

    def shoot(self, player_id):
        player = self.players.get(player_id)

        if self.match_over or not player or not player["alive"] or player["ammo"] <= 0:
            return

        direction = player["head_rot"]
        self.bullets.append({
            "id": self.next_bullet_id,
            "owner": player_id,
            "team": player["team"],
            "x": player["x"] - math.sin(math.radians(direction)) * 0.65,
            "y": player["y"] - math.cos(math.radians(direction)) * 0.65,
            "direction": direction,
            "distance": 0.0
        })
        self.next_bullet_id += 1
        player["ammo"] -= 1

    def respawn(self, player_id):
        player = self.players.get(player_id)

        if self.match_over or not player or player["alive"]:
            return

        x, y, rot = self.spawn_for(player_id, player["team"])
        player.update({"x": x, "y": y, "tread_rot": rot, "head_rot": rot, "health": 100, "ammo": 10, "scrap": 0, "alive": True})
        self.next_heal_times[player_id] = time.monotonic() + 5

    def tank_hits_player(self, player_id, x, y):
        for other_id, other in self.players.items():
            if other_id != player_id and other["alive"] and math.hypot(other["x"] - x, other["y"] - y) < 0.82:
                return True
        return False

    def update_healing(self, now):
        for player_id, player in self.players.items():
            if not player["alive"]:
                continue

            next_heal = self.next_heal_times.get(player_id, now + 5)

            if now >= next_heal:
                if player["health"] < 100:
                    player["health"] = min(100, player["health"] + 5)
                self.next_heal_times[player_id] = now + 5

    def update_players(self, dt):
        for player_id, player in self.players.items():
            if not player["alive"]:
                continue

            controls = self.inputs.get(player_id, {})
            new_rot = player["tread_rot"]

            if controls.get("left"):
                new_rot += 120 * dt
            if controls.get("right"):
                new_rot -= 120 * dt

            new_rot %= 360

            if not self.tank_blocked(player["x"], player["y"], new_rot):
                player["tread_rot"] = new_rot

            player["head_rot"] = self.turn_toward(player["head_rot"], controls.get("aim", player["head_rot"]), 240 * dt)
            direction = int(bool(controls.get("forward"))) - int(bool(controls.get("backward")))

            if direction:
                damage_fraction = max(0.0, min(1.0, (100 - player["health"]) / 90))
                speed_multiplier = 1.0 + 0.30 * damage_fraction
                move_speed = 1.2 * speed_multiplier
                new_x = player["x"] - math.sin(math.radians(player["tread_rot"])) * move_speed * dt * direction
                new_y = player["y"] - math.cos(math.radians(player["tread_rot"])) * move_speed * dt * direction

                if not self.tank_blocked(new_x, new_y, player["tread_rot"]) and not self.tank_hits_player(player_id, new_x, new_y):
                    player["x"] = new_x
                    player["y"] = new_y
                    player["tread_frame"] -= 18 * speed_multiplier * dt * direction

            for ammo in self.ammo_positions[:]:
                if math.hypot(ammo[0] - player["x"], ammo[1] - player["y"]) < 0.8:
                    player["ammo"] += ammo[2]
                    self.ammo_positions.remove(ammo)

            for scrap in self.scrap_positions[:]:
                if math.hypot(scrap[0] - player["x"], scrap[1] - player["y"]) < 0.75:
                    player["scrap"] += 1
                    self.scrap_positions.remove(scrap)

            if player["health"] <= 50:
                for health in self.health_positions[:]:
                    if math.hypot(health[0] - player["x"], health[1] - player["y"]) < 0.75:
                        player["health"] = min(100, player["health"] + 50)
                        self.health_positions.remove(health)
                        break

    def add_bullet_impact(self, bullet):
        self.impacts.append({
            "id": bullet["id"],
            "x": bullet["x"],
            "y": bullet["y"],
            "direction": bullet["direction"],
            "ttl": 0.18
        })

    def update_impacts(self, dt):
        for impact in self.impacts:
            impact["ttl"] -= dt
        self.impacts = [impact for impact in self.impacts if impact["ttl"] > 0]

    def update_bullets(self, dt):
        remaining = []

        for bullet in self.bullets:
            bullet["x"] -= math.sin(math.radians(bullet["direction"])) * 6 * dt
            bullet["y"] -= math.cos(math.radians(bullet["direction"])) * 6 * dt
            bullet["distance"] += 6 * dt

            if bullet["distance"] >= 6 or self.blocked_tile(bullet["x"], bullet["y"]):
                self.add_bullet_impact(bullet)
                continue

            hit = None

            for player in self.players.values():
                if player["alive"] and player["team"] != bullet["team"] and math.hypot(player["x"] - bullet["x"], player["y"] - bullet["y"]) < 0.48:
                    hit = player
                    break

            if hit:
                shooter = self.players.get(bullet["owner"])
                hit["health"] = max(0, hit["health"] - 10)
                self.add_bullet_impact(bullet)

                if hit["health"] == 0:
                    hit["alive"] = False
                    hit["deaths"] += 1
                    self.drop_scrap(hit)

                    if shooter:
                        shooter["kills"] += 1
                        death_messages = [
                            shooter["name"] + " shot " + hit["name"] + "!",
                            hit["name"] + " was exploded by " + shooter["name"] + "!",
                            hit["name"] + " died.",
                            shooter["name"] + " killed " + hit["name"]
                        ]
                        self.add_chat(random.choice(death_messages))
                    else:
                        self.add_chat(hit["name"] + " died.")

                continue

            remaining.append(bullet)

        self.bullets = remaining

    def spawn_rate_multiplier(self):
        return max(1.0, len(self.players) / 2)

    def update_spawns(self, now):
        if not self.match_started or self.match_over:
            return

        multiplier = self.spawn_rate_multiplier()

        if now >= self.next_scrap_spawn:
            if random.random() < 0.7:
                self.spawn_scrap()
                self.spawn_ammo()
            self.next_scrap_spawn = now + max(3.0, random.uniform(5, 15) / multiplier)

        if now >= self.next_health_spawn:
            self.spawn_health()
            self.next_health_spawn = now + max(8.0, 30 / multiplier)

    def time_remaining(self):
        if not self.match_started or self.match_start_time is None:
            return self.match_seconds

        return max(0, self.match_seconds - (time.monotonic() - self.match_start_time))

    def team_scrap_totals(self):
        totals = [0, 0]

        for player in self.players.values():
            totals[player["team"]] += player["scrap"]

        return totals

    def determine_winner(self):
        totals = self.team_scrap_totals()

        if totals[0] > totals[1]:
            return 0
        if totals[1] > totals[0]:
            return 1

        rankings = self.get_rankings()

        if not rankings:
            return -1

        best = rankings[0]
        same_rank = [row for row in rankings if (row["difference"], row["kills"], -row["deaths"]) == (best["difference"], best["kills"], -best["deaths"])]
        teams = {row["team"] for row in same_rank}
        return best["team"] if len(teams) == 1 else -1

    def check_match_end(self):
        if self.match_over or not self.match_started:
            return

        if self.time_remaining() > 0:
            return

        self.match_over = True
        self.winner = self.determine_winner()
        self.rematch_start_time = time.monotonic()

        if self.winner == -1:
            self.add_chat("Match ended in a draw!")
        else:
            self.add_chat("Team " + str(self.winner + 1) + " wins!")


    def rematch_time_remaining(self):
        if not self.match_over or self.rematch_start_time is None:
            return 0
        return max(0, self.rematch_seconds - (time.monotonic() - self.rematch_start_time))

    def start_new_match(self):
        player_ids = list(self.players.keys())
        random.shuffle(player_ids)
        first_team = random.randint(0, 1)
        team_slots = [0, 0]

        self.create_field()
        self.bullets = []
        self.impacts = []
        self.match_over = False
        self.winner = None
        self.match_started = False
        self.match_start_time = None
        self.rematch_start_time = None
        self.next_bullet_id = 0
        self.chat = []

        for index, player_id in enumerate(player_ids):
            player = self.players[player_id]
            team = (first_team + index) % 2
            slot = team_slots[team]
            team_slots[team] += 1
            x = 6.0 + slot
            y = 0.8 if team == 0 else 18.2
            rot = 180 if team == 0 else 0
            player.update({
                "team": team,
                "x": x,
                "y": y,
                "tread_rot": rot,
                "head_rot": rot,
                "health": 100,
                "ammo": 30,
                "scrap": 0,
                "alive": True,
                "tread_frame": 0.0,
                "kills": 0,
                "deaths": 0
            })
            self.inputs[player_id] = {"left": False, "right": False, "forward": False, "backward": False, "aim": rot}
            self.next_heal_times[player_id] = time.monotonic() + 5

        self.add_chat("Teams randomized!")
        self.try_start_match()

    def get_rankings(self):
        return sorted([
            {
                "id": player["id"],
                "name": player["name"],
                "team": player["team"],
                "kills": player["kills"],
                "deaths": player["deaths"],
                "difference": player["kills"] - player["deaths"],
                "scrap": player["scrap"]
            }
            for player in self.players.values()
        ], key=lambda row: (row["difference"], row["kills"], -row["deaths"], -row["id"]), reverse=True)

    def state_for(self, player_id):
        player = self.players.get(player_id)

        if not player:
            return {}

        scrap_totals = self.team_scrap_totals()

        return {
            "type": "state",
            "you": player_id,
            "join_code": self.join_code,
            "field": self.field,
            "players": list(self.players.values()),
            "bullets": self.bullets,
            "impacts": self.impacts,
            "ammo_positions": self.ammo_positions,
            "scrap_positions": self.scrap_positions,
            "health_positions": self.health_positions,
            "chat": self.chat,
            "team_scrap": scrap_totals[player["team"]],
            "team_scrap_totals": scrap_totals,
            "match_started": self.match_started,
            "time_remaining": self.time_remaining(),
            "match_minutes": self.match_minutes,
            "match_over": self.match_over,
            "winner": self.winner,
            "rematch_time_remaining": self.rematch_time_remaining(),
            "version": GAME_VERSION,
            "rankings": self.get_rankings()
        }

    def broadcast_states(self):
        dead = []

        with self.lock:
            clients = list(self.clients.items())

        for player_id, client in clients:
            try:
                send_json(client, self.state_for(player_id))
            except OSError:
                dead.append(player_id)

        for player_id in dead:
            self.remove_player(player_id)

    def game_loop(self):
        last_time = time.perf_counter()
        state_timer = 0.0

        while self.running:
            now = time.perf_counter()
            monotonic_now = time.monotonic()
            dt = min(now - last_time, 0.05)
            last_time = now

            with self.lock:
                self.try_start_match()

                if not self.match_over:
                    self.update_players(dt)
                    self.update_healing(monotonic_now)
                    self.update_bullets(dt)
                    self.update_impacts(dt)
                    self.update_spawns(monotonic_now)
                    self.check_match_end()
                elif self.rematch_time_remaining() <= 0:
                    self.start_new_match()

            state_timer += dt

            if state_timer >= 1 / STATE_RATE:
                self.broadcast_states()
                state_timer = 0.0

            wait = 1 / TICK_RATE - (time.perf_counter() - now)

            if wait > 0:
                time.sleep(wait)

    def discovery_loop(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", DISCOVERY_PORT))
            sock.settimeout(0.5)

            while self.running:
                try:
                    data, address = sock.recvfrom(4096)

                    if data.decode("utf-8", errors="ignore").strip() == "DISCOVER " + self.join_code:
                        sock.sendto(json.dumps({"join_code": self.join_code, "port": self.port}).encode("utf-8"), address)
                except socket.timeout:
                    pass
                except OSError:
                    if self.running:
                        pass
                    break

    def handle_client(self, client, address):
        player_id = None
        buffer = ""

        try:
            client.settimeout(10)

            while "\n" not in buffer:
                data = client.recv(65536)

                if not data:
                    return

                buffer += data.decode("utf-8")

            line, buffer = buffer.split("\n", 1)
            hello = json.loads(line)

            if hello.get("type") != "join":
                send_json(client, {"type": "error", "message": "Invalid connection request"})
                return

            if hello.get("join_code", "").strip().upper() != self.join_code:
                send_json(client, {"type": "error", "message": "INVALID JOIN CODE"})
                return

            client_version = str(hello.get("version", ""))

            if client_version != GAME_VERSION:
                shown_version = client_version or "UNKNOWN"
                send_json(client, {"type": "error", "message": "VERSION MISMATCH - SERVER " + GAME_VERSION + " / YOU " + shown_version})
                return

            player_id = self.add_player(hello.get("name", "PLAYER"), hello.get("color", "red"))

            if player_id is None:
                send_json(client, {"type": "error", "message": "Game is full or already ended"})
                return

            with self.lock:
                self.clients[player_id] = client

            client.settimeout(None)
            send_json(client, {"type": "welcome", "player_id": player_id, "join_code": self.join_code, "version": GAME_VERSION})

            while self.running:
                data = client.recv(65536)

                if not data:
                    break

                buffer += data.decode("utf-8")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)

                    if not line.strip():
                        continue

                    message = json.loads(line)

                    with self.lock:
                        if message.get("type") == "input" and player_id in self.inputs:
                            self.inputs[player_id] = {
                                "left": bool(message.get("left")),
                                "right": bool(message.get("right")),
                                "forward": bool(message.get("forward")),
                                "backward": bool(message.get("backward")),
                                "aim": float(message.get("aim", 0)) % 360
                            }
                        elif message.get("type") == "shoot":
                            self.shoot(player_id)
                        elif message.get("type") == "respawn":
                            self.respawn(player_id)
        except (OSError, ConnectionError, json.JSONDecodeError, ValueError):
            pass
        finally:
            if player_id is not None:
                self.remove_player(player_id)
            else:
                try:
                    client.close()
                except OSError:
                    pass

    def accept_loop(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(MAX_PLAYERS)
        self.server_socket.settimeout(0.5)

        while self.running:
            try:
                client, address = self.server_socket.accept()
                threading.Thread(target=self.handle_client, args=(client, address), daemon=True).start()
            except socket.timeout:
                pass
            except OSError:
                break

    def start(self):
        if self.running:
            return

        self.running = True
        threading.Thread(target=self.accept_loop, daemon=True).start()
        threading.Thread(target=self.discovery_loop, daemon=True).start()
        threading.Thread(target=self.game_loop, daemon=True).start()

    def stop(self):
        self.running = False

        if self.server_socket:
            try:
                self.server_socket.close()
            except OSError:
                pass

        with self.lock:
            for client in list(self.clients.values()):
                try:
                    client.close()
                except OSError:
                    pass
            self.clients.clear()