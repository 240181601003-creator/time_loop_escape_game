"""
TIME LOOP ESCAPE — Neon Futuristic Maze
Requirements: Python 3.10+ and pygame
Install: python -m pip install pygame
Run: python time_loop_escape.py

Controls:
  WASD / Arrow keys : Move
  R                 : Rewind to the start of the current loop
  SPACE             : Pause / resume
  ENTER             : Start / restart after game over
  ESC               : Quit

Gameplay:
  Collect the glowing key, then reach the exit before the loop timer expires.
  Every loop, parts of the maze shift. A ghost replays your previous loop's
  movements, letting you see your earlier attempt.
  Rewind preserves your score but resets your position and starts a fresh loop.
"""

import math
import random
import sys
from collections import deque

import pygame

pygame.init()

# ----------------------------- Configuration -----------------------------
WIDTH, HEIGHT = 1000, 720
HUD_H = 90
CELL = 40
COLS = 21
ROWS = 15
MAZE_W = COLS * CELL
MAZE_H = ROWS * CELL
MAZE_X = (WIDTH - MAZE_W) // 2
MAZE_Y = HUD_H + (HEIGHT - HUD_H - MAZE_H) // 2
FPS = 60
LOOP_SECONDS = 30
MOVE_REPEAT = 0.115

BG = (7, 10, 25)
PANEL = (12, 19, 42)
GRID = (19, 35, 66)
WALL = (24, 38, 76)
WALL_EDGE = (30, 222, 245)
CYAN = (60, 245, 255)
PINK = (255, 62, 190)
PURPLE = (151, 92, 255)
YELLOW = (255, 224, 92)
GREEN = (93, 255, 171)
WHITE = (232, 245, 255)
MUTED = (133, 160, 194)
RED = (255, 83, 105)

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("TIME LOOP ESCAPE | Neon Maze")
clock = pygame.time.Clock()

FONT = pygame.font.SysFont("consolas", 18)
SMALL = pygame.font.SysFont("consolas", 14)
MED = pygame.font.SysFont("consolas", 23, bold=True)
BIG = pygame.font.SysFont("consolas", 38, bold=True)
TITLE = pygame.font.SysFont("consolas", 30, bold=True)

# ----------------------------- Maze generation ---------------------------
def generate_maze(seed, loop_index):
    """Generate a perfect maze with randomized extra openings and loop shifts."""
    rng = random.Random(seed + loop_index * 7919)
    grid = [[1 for _ in range(COLS)] for _ in range(ROWS)]
    start = (1, 1)
    grid[start[1]][start[0]] = 0
    stack = [start]
    visited = {start}
    dirs = [(2, 0), (-2, 0), (0, 2), (0, -2)]

    while stack:
        x, y = stack[-1]
        options = []
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if 1 <= nx < COLS - 1 and 1 <= ny < ROWS - 1 and (nx, ny) not in visited:
                options.append((nx, ny, dx, dy))
        if options:
            nx, ny, dx, dy = rng.choice(options)
            grid[ny][nx] = 0
            grid[y + dy // 2][x + dx // 2] = 0
            visited.add((nx, ny))
            stack.append((nx, ny))
        else:
            stack.pop()

    # Add extra paths so each maze is less restrictive.
    candidates = []
    for y in range(1, ROWS - 1):
        for x in range(1, COLS - 1):
            if grid[y][x] == 1:
                if (grid[y][x-1] == 0 and grid[y][x+1] == 0) or \
                   (grid[y-1][x] == 0 and grid[y+1][x] == 0):
                    candidates.append((x, y))
    rng.shuffle(candidates)
    for x, y in candidates[:max(7, 5 + loop_index % 8)]:
        grid[y][x] = 0

    # Keep the start and exit fixed, but the route changes on each loop.
    grid[1][1] = 0
    grid[ROWS - 2][COLS - 2] = 0
    return grid


def shortest_path(grid, start, goal):
    q = deque([start])
    parent = {start: None}
    while q:
        pos = q.popleft()
        if pos == goal:
            break
        x, y = pos
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (x + dx, y + dy)
            nx, ny = nxt
            if 0 <= nx < COLS and 0 <= ny < ROWS and grid[ny][nx] == 0 and nxt not in parent:
                parent[nxt] = pos
                q.append(nxt)
    if goal not in parent:
        return []
    path = []
    cur = goal
    while cur is not None:
        path.append(cur)
        cur = parent[cur]
    return list(reversed(path))


def choose_floor(grid, rng, forbidden):
    floors = [(x, y) for y in range(1, ROWS - 1) for x in range(1, COLS - 1)
              if grid[y][x] == 0 and (x, y) not in forbidden]
    return rng.choice(floors) if floors else (COLS - 2, ROWS - 2)


# ----------------------------- Game state --------------------------------
seed = random.randrange(1, 1_000_000)
loop_index = 0
score = 0
best_score = 0
lives = 3
maze = generate_maze(seed, loop_index)
start_pos = (1, 1)
exit_pos = (COLS - 2, ROWS - 2)
player = start_pos
path = [player]
ghost_path = []
ghost_index = 0
key_pos = choose_floor(maze, random.Random(seed + 10), {start_pos, exit_pos})
key_collected = False
loop_started = pygame.time.get_ticks() / 1000
move_cooldown = 0.0
paused = False
game_over = False
won = False
message = "COLLECT THE KEY. REACH THE EXIT."
message_until = 5.0
elapsed_total = 0.0
rewinds = 0


def set_message(text, seconds=2.5):
    global message, message_until
    message = text
    message_until = pygame.time.get_ticks() / 1000 + seconds


def reset_loop(keep_ghost=True, penalize=False, new_maze=True):
    global loop_index, maze, player, path, ghost_path, ghost_index
    global key_pos, key_collected, loop_started, move_cooldown, lives, rewinds
    global game_over, won, paused
    if keep_ghost and len(path) > 1:
        ghost_path = path[:]
        ghost_index = 0
    if penalize:
        lives -= 1
        if lives <= 0:
            lives = 0
            game_over = True
            won = False
            set_message("TIME FRACTURED — PRESS ENTER TO RESTART", 999)
            return
    loop_index += 1
    if new_maze:
        maze = generate_maze(seed, loop_index)
    player = start_pos
    path = [player]
    key_collected = False
    rng = random.Random(seed + loop_index * 97 + 42)
    key_pos = choose_floor(maze, rng, {start_pos, exit_pos})
    loop_started = pygame.time.get_ticks() / 1000
    move_cooldown = 0
    paused = False
    rewinds += 1
    set_message(f"LOOP {loop_index + 1}: THE MAZE HAS SHIFTED", 2.8)


def restart_game():
    global seed, loop_index, score, best_score, lives, maze, player, path
    global ghost_path, ghost_index, key_pos, key_collected, loop_started
    global move_cooldown, paused, game_over, won, rewinds
    seed = random.randrange(1, 1_000_000)
    loop_index = 0
    score = 0
    lives = 3
    maze = generate_maze(seed, loop_index)
    player = start_pos
    path = [player]
    ghost_path = []
    ghost_index = 0
    key_pos = choose_floor(maze, random.Random(seed + 10), {start_pos, exit_pos})
    key_collected = False
    loop_started = pygame.time.get_ticks() / 1000
    move_cooldown = 0
    paused = False
    game_over = False
    won = False
    rewinds = 0
    set_message("NEW TIMELINE INITIALIZED", 2.5)


def cell_center(pos):
    x, y = pos
    return MAZE_X + x * CELL + CELL // 2, MAZE_Y + y * CELL + CELL // 2


def move_player(dx, dy):
    global player, score, key_collected, won, best_score
    nx, ny = player[0] + dx, player[1] + dy
    if 0 <= nx < COLS and 0 <= ny < ROWS and maze[ny][nx] == 0:
        player = (nx, ny)
        if player != path[-1]:
            path.append(player)
        score += 1
        if player == key_pos and not key_collected:
            key_collected = True
            score += 100
            set_message("KEY ACQUIRED — EXIT UNLOCKED", 2.0)
        if player == exit_pos:
            if key_collected:
                score += 250 + max(0, int(time_left())) * 5
                best_score = max(best_score, score)
                won = True
                set_message("TIMELINE STABLE — YOU ESCAPED!", 999)
            else:
                set_message("EXIT LOCKED — FIND THE KEY!", 1.5)


def time_left():
    return max(0, LOOP_SECONDS - (pygame.time.get_ticks() / 1000 - loop_started))


def draw_glow(surface, color, center, radius, alpha=70):
    glow = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
    pygame.draw.circle(glow, (*color, alpha), (radius * 2, radius * 2), radius)
    surface.blit(glow, (center[0] - radius * 2, center[1] - radius * 2), special_flags=pygame.BLEND_PREMULTIPLIED)


def draw_text(text, font, color, x, y, center=False):
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    screen.blit(img, rect)


def draw_hud():
    pygame.draw.rect(screen, PANEL, (0, 0, WIDTH, HUD_H))
    pygame.draw.line(screen, CYAN, (0, HUD_H - 1), (WIDTH, HUD_H - 1), 2)
    draw_text("TIME LOOP", TITLE, CYAN, 22, 12)
    draw_text("ESCAPE", TITLE, PINK, 210, 12)
    draw_text(f"SCORE  {score:06d}", MED, WHITE, 22, 52)
    draw_text(f"LOOP  {loop_index + 1:02d}", FONT, PURPLE, 280, 56)
    draw_text(f"LIVES  {'♥ ' * lives}", FONT, PINK, 420, 56)
    left = time_left()
    timer_color = RED if left <= 8 else YELLOW
    draw_text(f"TIME  {left:04.1f}s", MED, timer_color, 740, 15)
    bar_x, bar_y, bar_w, bar_h = 740, 52, 220, 10
    pygame.draw.rect(screen, (32, 44, 72), (bar_x, bar_y, bar_w, bar_h), border_radius=5)
    pygame.draw.rect(screen, timer_color, (bar_x, bar_y, int(bar_w * left / LOOP_SECONDS), bar_h), border_radius=5)
    draw_text("WASD / ARROWS MOVE   R REWIND   SPACE PAUSE", SMALL, MUTED, 280, 30)


def draw_maze():
    # subtle scanline background
    for y in range(MAZE_Y, MAZE_Y + MAZE_H, 8):
        pygame.draw.line(screen, (9, 15, 33), (MAZE_X, y), (MAZE_X + MAZE_W, y), 1)
    for y in range(ROWS):
        for x in range(COLS):
            rect = pygame.Rect(MAZE_X + x * CELL, MAZE_Y + y * CELL, CELL, CELL)
            if maze[y][x] == 1:
                pygame.draw.rect(screen, WALL, rect)
                pygame.draw.rect(screen, (20, 61, 98), rect, 1)
                # neon corner accents
                if (x + y + loop_index) % 3 == 0:
                    pygame.draw.line(screen, (25, 118, 153), rect.topleft, (rect.left + 9, rect.top), 2)
            else:
                pygame.draw.rect(screen, (9, 16, 35), rect)
                pygame.draw.rect(screen, GRID, rect, 1)

    # Start marker
    sc = cell_center(start_pos)
    draw_glow(screen, PURPLE, sc, 10, 45)
    pygame.draw.circle(screen, PURPLE, sc, 5, 2)

    # Exit
    ec = cell_center(exit_pos)
    draw_glow(screen, GREEN if key_collected else RED, ec, 17, 75)
    pygame.draw.rect(screen, GREEN if key_collected else RED,
                     (ec[0] - 12, ec[1] - 12, 24, 24), 2)
    draw_text("E", SMALL, GREEN if key_collected else RED, ec[0] - 5, ec[1] - 8)

    # Key
    if not key_collected:
        kc = cell_center(key_pos)
        draw_glow(screen, YELLOW, kc, 13, 80)
        pygame.draw.circle(screen, YELLOW, kc, 7, 3)
        pygame.draw.circle(screen, YELLOW, (kc[0] + 9, kc[1]), 3, 2)
        pygame.draw.line(screen, YELLOW, (kc[0] + 3, kc[1] + 5), (kc[0] + 10, kc[1] + 12), 3)

    # Previous-loop ghost
    if ghost_path:
        ghost_pos = ghost_path[min(ghost_index, len(ghost_path) - 1)]
        gc = cell_center(ghost_pos)
        draw_glow(screen, PINK, gc, 13, 45)
        pygame.draw.circle(screen, PINK, gc, 9, 2)
        pygame.draw.circle(screen, PINK, gc, 3)

    # Current player
    pc = cell_center(player)
    draw_glow(screen, CYAN, pc, 15, 75)
    pygame.draw.circle(screen, CYAN, pc, 10)
    pygame.draw.circle(screen, WHITE, pc, 4)

    # Border
    pygame.draw.rect(screen, CYAN, (MAZE_X - 2, MAZE_Y - 2, MAZE_W + 4, MAZE_H + 4), 2)


def draw_overlay(title, subtitle, accent):
    veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    veil.fill((2, 5, 16, 205))
    screen.blit(veil, (0, 0))
    pygame.draw.rect(screen, PANEL, (170, 230, 660, 220), border_radius=12)
    pygame.draw.rect(screen, accent, (170, 230, 660, 220), 2, border_radius=12)
    draw_text(title, BIG, accent, WIDTH // 2, 285, True)
    draw_text(subtitle, FONT, WHITE, WIDTH // 2, 338, True)
    draw_text("ENTER  RESTART     ESC  QUIT", MED, MUTED, WIDTH // 2, 395, True)


# ----------------------------- Main loop ---------------------------------
running = True
while running:
    dt = clock.tick(FPS) / 1000
    now = pygame.time.get_ticks() / 1000
    keys = pygame.key.get_pressed()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_RETURN and (game_over or won):
                restart_game()
            elif event.key == pygame.K_SPACE and not game_over and not won:
                paused = not paused
            elif event.key == pygame.K_r and not game_over and not won and not paused:
                reset_loop(keep_ghost=True, penalize=False, new_maze=True)
                set_message("TIME REWIND — TIMELINE RESET", 2.0)

    if not paused and not game_over and not won:
        if time_left() <= 0:
            reset_loop(keep_ghost=True, penalize=True, new_maze=True)
            if not game_over:
                set_message("TIME EXPIRED — ONE LIFE LOST", 2.2)

        move_cooldown -= dt
        if move_cooldown <= 0:
            dx = dy = 0
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                dx = -1
            elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                dx = 1
            elif keys[pygame.K_UP] or keys[pygame.K_w]:
                dy = -1
            elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
                dy = 1
            if dx or dy:
                move_player(dx, dy)
                move_cooldown = MOVE_REPEAT

        if ghost_path and ghost_index < len(ghost_path) - 1:
            # Ghost replay speed is slightly faster than normal movement.
            ghost_index = min(len(ghost_path) - 1, int(ghost_index + dt / MOVE_REPEAT * 0.55))

    # ----------------------------- Render --------------------------------
    screen.fill(BG)
    # Decorative stars
    for i in range(45):
        sx = (i * 137 + 31) % WIDTH
        sy = (i * 83 + 17) % HEIGHT
        pygame.draw.circle(screen, (30, 62, 100), (sx, sy), 1)

    draw_hud()
    draw_maze()

    if now < message_until and not game_over and not won:
        pygame.draw.rect(screen, (12, 23, 47), (MAZE_X, HEIGHT - 31, MAZE_W, 25), border_radius=5)
        draw_text(message, SMALL, CYAN, WIDTH // 2, HEIGHT - 19, True)

    if paused:
        draw_overlay("PAUSED", "Time is frozen. Take a breath.", YELLOW)
    elif game_over:
        draw_overlay("TIME FRACTURED", f"Final score: {score}   |   Loops survived: {loop_index + 1}", RED)
    elif won:
        draw_overlay("YOU ESCAPED!", f"Final score: {score}   |   Best score this run: {best_score}", GREEN)

    pygame.display.flip()

pygame.quit()
sys.exit()
