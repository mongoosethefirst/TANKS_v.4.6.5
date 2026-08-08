# -*- coding: utf-8 -*-
import time, pygame, random
from paths import image_path, font_path
from network import discover_host
from game_client_base import GameClient

pygame.init()

screen = pygame.display.set_mode((0, 0))

running = True
fps = 60
width, height = screen.get_size()
frames = 0
color = 0
colors = ["red", "orange", "yellow", "green", "blue", "purple", "pink"]
status = ""

font = pygame.font.Font(font_path(), 20)
small_font = pygame.font.Font(font_path(), 12)

tread1 = pygame.image.load(image_path("tread1.png")).convert_alpha()
tread1 = pygame.transform.scale(tread1, (80, 80))

tread2 = pygame.image.load(image_path("tread2.png")).convert_alpha()
tread2 = pygame.transform.scale(tread2, (80, 80))

tread3 = pygame.image.load(image_path("tread3.png")).convert_alpha()
tread3 = pygame.transform.scale(tread3, (80, 80))

red = pygame.image.load(image_path("redbody.png")).convert_alpha()
red = pygame.transform.scale(red, (106, 160))
red_rect = red.get_rect(center=(width // 2, height // 2 - 80))

orange = pygame.image.load(image_path("orangebody.png")).convert_alpha()
orange = pygame.transform.scale(orange, (106, 160))
orange_rect = orange.get_rect(center=(width // 2, height // 2 - 80))

yellow = pygame.image.load(image_path("yellowbody.png")).convert_alpha()
yellow = pygame.transform.scale(yellow, (106, 160))
yellow_rect = yellow.get_rect(center=(width // 2, height // 2 - 80))

green = pygame.image.load(image_path("greenbody.png")).convert_alpha()
green = pygame.transform.scale(green, (106, 160))
green_rect = green.get_rect(center=(width // 2, height // 2 - 80))

blue = pygame.image.load(image_path("bluebody.png")).convert_alpha()
blue = pygame.transform.scale(blue, (106, 160))
blue_rect = blue.get_rect(center=(width // 2, height // 2 - 80))

purple = pygame.image.load(image_path("purplebody.png")).convert_alpha()
purple = pygame.transform.scale(purple, (106, 160))
purple_rect = purple.get_rect(center=(width // 2, height // 2 - 80))

pink = pygame.image.load(image_path("pinkbody.png")).convert_alpha()
pink = pygame.transform.scale(pink, (106, 160))
pink_rect = pink.get_rect(center=(width // 2, height // 2 - 80))

left = pygame.image.load(image_path("left.png")).convert_alpha()
left = pygame.transform.scale(left, (80, 80))

right = pygame.image.load(image_path("right.png")).convert_alpha()
right = pygame.transform.scale(right, (80, 80))

play = pygame.image.load(image_path("play.png")).convert_alpha()
play = pygame.transform.scale(play, (90, 80))

username_rect = pygame.Rect((width // 2) - 205, (height // 2) + 100, 410, 30)
join_code_rect = pygame.Rect((width // 2) - 205, (height // 2) + 200, 410, 30)

username = "PLAYER" + str(random.randint(1111, 9999))
join_code = ""

active_box = None

while running:
    clicked = False

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            clicked = True

            if username_rect.collidepoint(event.pos):
                active_box = "username"
            elif join_code_rect.collidepoint(event.pos):
                active_box = "join_code"
            else:
                active_box = None

        if event.type == pygame.KEYDOWN:
            if active_box == "username":
                if event.key == pygame.K_BACKSPACE:
                    username = username[:-1]
                elif event.key == pygame.K_RETURN:
                    active_box = "join_code"
                elif len(username) < 20 and event.unicode.isprintable():
                    username += event.unicode

            elif active_box == "join_code":
                if event.key == pygame.K_BACKSPACE:
                    join_code = join_code[:-1]
                elif event.key == pygame.K_RETURN:
                    clicked = True
                elif len(join_code) < 6 and event.unicode.isalnum():
                    join_code += event.unicode.upper()

    screen.fill((50, 50, 50))

    mouse_x, mouse_y = pygame.mouse.get_pos()

    if round(frames / 20) % 3 == 2:
        screen.blit(tread1, ((width // 2) - 40, (height // 2) - 120))
    elif round(frames / 20) % 3 == 1:
        screen.blit(tread2, ((width // 2) - 40, (height // 2) - 120))
    else:
        screen.blit(tread3, ((width // 2) - 40, (height // 2) - 120))

    left_rect = pygame.Rect((width // 2) - 180, (height // 2) - 120, 80, 80)
    right_rect = pygame.Rect((width // 2) + 100, (height // 2) - 120, 80, 80)
    play_rect = pygame.Rect((width // 2) - 45, (height // 2) + 280, 90, 80)

    screen.blit(left, left_rect)
    screen.blit(right, right_rect)
    screen.blit(play, play_rect)

    if clicked:
        if left_rect.collidepoint(mouse_x, mouse_y):
            color -= 1
            color %= len(colors)

        elif right_rect.collidepoint(mouse_x, mouse_y):
            color += 1
            color %= len(colors)

        elif play_rect.collidepoint(mouse_x, mouse_y):
            if not username.strip():
                status = "ENTER A NICKNAME"

            elif len(join_code) != 6:
                status = "ENTER A 6 CHARACTER CODE"

            else:
                status = "SEARCHING FOR GAME..."
                screen.fill((50, 50, 50))

                status_surface = font.render(status, True, (255, 255, 255))
                status_rect = status_surface.get_rect(center=(width // 2, height // 2))
                screen.blit(status_surface, status_rect)
                pygame.display.flip()

                host = discover_host(join_code)

                if host is None:
                    status = "GAME NOT FOUND"
                else:
                    try:
                        client = GameClient(host[0], host[1], join_code, username, colors[color])
                        client.connect()
                        running = False
                        client.run()
                    except Exception as error:
                        status = str(error).upper()

    if color == 0:
        screen.blit(red, red_rect)
    elif color == 1:
        screen.blit(orange, orange_rect)
    elif color == 2:
        screen.blit(yellow, yellow_rect)
    elif color == 3:
        screen.blit(green, green_rect)
    elif color == 4:
        screen.blit(blue, blue_rect)
    elif color == 5:
        screen.blit(purple, purple_rect)
    elif color == 6:
        screen.blit(pink, pink_rect)

    username_color = (255, 255, 255) if active_box == "username" else (150, 150, 150)
    join_code_color = (255, 255, 255) if active_box == "join_code" else (150, 150, 150)

    pygame.draw.rect(screen, username_color, username_rect, 2)
    pygame.draw.rect(screen, join_code_color, join_code_rect, 2)

    username_surface = font.render(username, True, (255, 255, 255))
    screen.blit(username_surface, (username_rect.x + 5, username_rect.y + 5))

    shown_code = join_code
    if not shown_code and active_box != "join_code":
        shown_code = "------"

    code_surface = font.render(shown_code, True, (255, 255, 255))
    code_rect = code_surface.get_rect(center=join_code_rect.center)
    screen.blit(code_surface, code_rect)

    username_label = font.render("Enter Nickname", True, (255, 255, 255))
    username_label_rect = username_label.get_rect(center=(width // 2, username_rect.y - 30))
    screen.blit(username_label, username_label_rect)

    code_label = font.render("Enter Join Code", True, (255, 255, 255))
    code_label_rect = code_label.get_rect(center=(width // 2, join_code_rect.y - 30))
    screen.blit(code_label, code_label_rect)

    if status:
        status_surface = small_font.render(status, True, (255, 180, 120))
        status_rect = status_surface.get_rect(center=(width // 2, height // 2 + 390))
        screen.blit(status_surface, status_rect)

    pygame.display.flip()
    frames += 1
    time.sleep(1 / fps)

pygame.quit()
