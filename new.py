# -*- coding: utf-8 -*-
import random, time, pygame
from paths import image_path, font_path
from server import GameServer
from network import TCP_PORT

players = {}
field = []
ammo_positions = []
server = None
host_name = ""
host_color = "red"
host_join_code = ""
host_port = TCP_PORT

pygame.init()
screen = pygame.display.set_mode((0, 0))
running = True
fps = 60
width, height = screen.get_size()
frames = 0
color = 0
colors = ["red", "orange", "yellow", "green", "blue", "purple", "pink"]
font = pygame.font.Font(font_path(), 20)
small_font = pygame.font.Font(font_path(), 12)
images = {}

for number in range(1, 4):
    image = pygame.image.load(image_path("tread" + str(number) + ".png")).convert_alpha()
    images["tread" + str(number)] = pygame.transform.scale(image, (80, 80))

for color_name in colors:
    image = pygame.image.load(image_path(color_name + "body.png")).convert_alpha()
    images[color_name] = pygame.transform.scale(image, (106, 160))

left = pygame.transform.scale(pygame.image.load(image_path("left.png")).convert_alpha(), (80, 80))
right = pygame.transform.scale(pygame.image.load(image_path("right.png")).convert_alpha(), (80, 80))
play = pygame.transform.scale(pygame.image.load(image_path("play.png")).convert_alpha(), (90, 80))
username_rect = pygame.Rect((width // 2) - 205, (height // 2) + 170, 410, 30)
timer_rect = pygame.Rect((width // 2) - 205, (height // 2) + 260, 410, 30)
text = "PLAYER" + str(random.randint(1111, 9999))
timer_text = "10"
active = "username"
status = ""

while running:
    clicked = False

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            clicked = True

            if username_rect.collidepoint(event.pos):
                active = "username"
            elif timer_rect.collidepoint(event.pos):
                active = "timer"
            else:
                active = None

        if event.type == pygame.KEYDOWN:
            if active == "username":
                if event.key == pygame.K_BACKSPACE:
                    text = text[:-1]
                elif event.key != pygame.K_RETURN and len(text) < 20 and event.unicode.isprintable():
                    text += event.unicode
            elif active == "timer":
                if event.key == pygame.K_BACKSPACE:
                    timer_text = timer_text[:-1]
                elif event.key != pygame.K_RETURN and event.unicode.isdigit() and len(timer_text) < 3:
                    timer_text += event.unicode

    screen.fill((50, 50, 50))
    x, y = pygame.mouse.get_pos()
    tread_name = "tread" + str(round(frames / 20) % 3 + 1)
    screen.blit(images[tread_name], ((width // 2) - 40, (height // 2) - 40))

    left_rect = pygame.Rect((width // 2) - 180, (height // 2) - 40, 80, 80)
    right_rect = pygame.Rect((width // 2) + 100, (height // 2) - 40, 80, 80)
    play_rect = pygame.Rect((width // 2) - 45, (height // 2) + 340, 90, 80)
    screen.blit(left, left_rect)
    screen.blit(right, right_rect)
    screen.blit(play, play_rect)

    pygame.draw.rect(screen, (255, 255, 255) if active == "username" else (150, 150, 150), username_rect, 2)
    pygame.draw.rect(screen, (255, 255, 255) if active == "timer" else (150, 150, 150), timer_rect, 2)
    screen.blit(font.render(text, True, (255, 255, 255)), (username_rect.x + 5, username_rect.y + 5))
    timer_surface = font.render(timer_text or "0", True, (255, 255, 255))
    screen.blit(timer_surface, timer_surface.get_rect(center=timer_rect.center))
    screen.blit(font.render("Enter Nickname", True, (255, 255, 255)), font.render("Enter Nickname", True, (255, 255, 255)).get_rect(center=(width // 2, username_rect.y - 30)))
    screen.blit(font.render("Match Minutes", True, (255, 255, 255)), font.render("Match Minutes", True, (255, 255, 255)).get_rect(center=(width // 2, timer_rect.y - 30)))

    join_text = "JOIN CODE: " + (host_join_code or "------")
    join_surface = font.render(join_text, True, (255, 255, 255))
    screen.blit(join_surface, join_surface.get_rect(center=(width // 2, timer_rect.y + 60)))


    if clicked:
        if left_rect.collidepoint(x, y):
            color = (color - 1) % 7
        elif right_rect.collidepoint(x, y):
            color = (color + 1) % 7
        elif play_rect.collidepoint(x, y):
            minutes = int(timer_text or 0)

            if minutes < 1 or minutes > 120:
                status = "CHOOSE 1-120 MINUTES"
            else:
                server = GameServer(match_minutes=minutes)
                server.start()
                time.sleep(0.2)
                host_name = text or "PLAYER"
                host_color = colors[color]
                host_join_code = server.join_code
                field = server.field
                ammo_positions = server.ammo_positions
                running = False
                import play_host

    body = images[colors[color]]
    screen.blit(body, body.get_rect(center=(width // 2, height // 2)))

    if status:
        status_surface = small_font.render(status, True, (255, 180, 120))
        screen.blit(status_surface, status_surface.get_rect(center=(width // 2, height // 2 + 445)))

    pygame.display.flip()
    frames += 1
    time.sleep(1 / fps)