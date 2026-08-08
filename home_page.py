# -*- coding: utf-8 -*-
import time, pygame
from paths import image_path

pygame.init()

screen = pygame.display.set_mode((0, 0))

running = True
fps = 60
width, height = screen.get_size()
mouse_down = False

new_off = pygame.image.load(image_path("new_off.png")).convert_alpha()
new_off = pygame.transform.scale(new_off, (150, 30))
new_on = pygame.image.load(image_path("new_on.png")).convert_alpha()
new_on = pygame.transform.scale(new_on, (150, 30))
join_off = pygame.image.load(image_path("join_off.png")).convert_alpha()
join_off = pygame.transform.scale(join_off, (150, 30))
join_on = pygame.image.load(image_path("join_on.png")).convert_alpha()
join_on = pygame.transform.scale(join_on, (150, 30))

icon = pygame.image.load(image_path("icon.png")).convert_alpha()
icon = pygame.transform.scale(icon, (1000, 600))

while running:
    clicked = False

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            clicked = True

    screen.fill((50, 50, 50))

    x, y = pygame.mouse.get_pos()

    new_rect = pygame.Rect((width//2) - 75, (height//2) - 15, 150, 30)
    join_rect = pygame.Rect((width//2) - 75, (height//2) + 30, 150, 30)

    if new_rect.collidepoint(x, y):
        screen.blit(new_on, new_rect)
        if clicked:
            running = False
            import new
    else:
        screen.blit(new_off, new_rect)

    if join_rect.collidepoint(x, y):
        screen.blit(join_on, join_rect)
        if clicked:
            running = False
            import join
    else:
        screen.blit(join_off, join_rect)

    screen.blit(icon, ((width//2) - 500, -120))

    pygame.display.flip()
    time.sleep(1/fps)

pygame.quit()