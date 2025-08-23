from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import math
import time
import random
import os
import json

# -------------------
# Camera / scene
# -------------------
camera_pos = (0, 500, 500)
fovY = 120
GRID_LENGTH = 600

# -------------------
# Game state variables
# -------------------
tug_var = 0           # variable changed by players: A -> +1, L -> -1
TUG_LIMIT = 10        # winning threshold (crossing >+TUG_LIMIT or <-TUG_LIMIT)
winner = None         # 'A' or 'L' or None
game_paused = False   # stops inputs when round ended
round_enabled = True
ROUND_DURATION = 30.0  # seconds per round
round_time_left = ROUND_DURATION
round_running = True

# Stamina mechanic
LEFT_MAX_STAM = 100.0
RIGHT_MAX_STAM = 100.0
left_stamina = LEFT_MAX_STAM
right_stamina = RIGHT_MAX_STAM
STAM_COST_PER_PRESS = 12.0   # cost per keypress
STAM_RECOVER_RATE = 18.0     # per second

# Keystroke counters
left_presses = 0
right_presses = 0

# Bot opponent
bot_enabled = False
bot_difficulty = 0.6  # 0.0..1.0 aggressiveness (higher means more frequent presses)
last_bot_action = 0.0

# Replay buffer
REPLAY_SECONDS = 6.0
REPLAY_FPS = 60.0
max_replay_frames = int(REPLAY_SECONDS * REPLAY_FPS)
replay_buffer = []
replay_mode = False
replay_index = 0
replay_speed = 1.0

# Win animation
animation_start = None
ANIM_DURATION = 3.0   # seconds of win animation
platform_fall_progress = 0.0

# Highscore file
HIGHSCORE_FILE = "tug_highscores.jsonl"
max_saved_scores = 50

# Time tracking for dt updates
_last_time_ms = None

# HUD / UI
show_scores_list = []  # loaded scores to display

# Platform shake state
left_shake = 0.0
right_shake = 0.0
SHAKE_DECAY = 2.8      # decay per second
SHAKE_FREQ = 28.0      # Hz-ish oscillation
SHAKE_PIXELS = 5.0     # max pixels * shake level

# -------------------
# Utility / drawing functions (template-style)
# -------------------
def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
    glDisable(GL_LIGHTING)
    glColor3f(1, 1, 1)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, 1000, 0, 800)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_LIGHTING)

def draw_platform(x, z, width=220, depth=60, height=10, falling_offset=0.0):
    """Simple rectangular platform at (x, z). falling_offset moves platform 'down' (scene Y) for animation."""
    glPushMatrix()
    glTranslatef(x, -falling_offset, z)
    # Squid-Game-ish neon palette accents on edges
    glColor3f(0.95, 0.2, 0.65)  # hot pink
    glPushMatrix()
    glScalef(width, 6, height + 4)
    glutSolidCube(1)
    glPopMatrix()
    glColor3f(0.1, 0.8, 0.55)   # aqua green accent
    glPushMatrix()
    glTranslatef(0, depth * 0.45, 0)
    glScalef(width * 0.9, 6, height * 0.9)
    glutSolidCube(1)
    glPopMatrix()
    glPopMatrix()

def draw_player(x, z, color=(1, 0, 0), lean=0.0, falling=0.0, tumble_deg=0.0, victory_jump=0.0):
    """Stacked-cube body + sphere head. 
       lean rotates around Z while tugging.
       falling lowers (scene Y). tumble rotates around X when losing.
       victory_jump raises along Z for a celebratory hop.
    """
    glPushMatrix()
    glTranslatef(x, 20 - falling, z + victory_jump)
    if tumble_deg != 0.0:
        glRotatef(tumble_deg, 1, 0, 0)  # tumble forward/back
    if lean != 0.0:
        glRotatef(lean, 0, 0, 1)

    # body
    glColor3f(*color)
    glPushMatrix()
    glScalef(18, 18, 36)
    glutSolidCube(1)
    glPopMatrix()

    # head
    glPushMatrix()
    glTranslatef(0, 0, 30)
    glColor3f(min(1.0, color[0]+0.1), min(1.0, color[1]+0.1), min(1.0, color[2]+0.1))
    glutSolidSphere(10, 12, 12)
    glPopMatrix()

    # hands (tiny spheres) gripping rope
    glPushMatrix()
    glTranslatef(( -6 if x < 0 else 6 ), 0, 6)
    glutSolidSphere(4, 10, 10)
    glTranslatef(0, 0, 6)
    glutSolidSphere(4, 10, 10)
    glPopMatrix()

    glPopMatrix()

def draw_rope(center_x, z, tug_value):
    """Draw rope as a segmented tube with slight curvature and a colored knot."""
    total_segments = 14
    rope_half = 260
    shift = tug_value * 12  # visual sensitivity

    if tug_value >= 0:
        glColor3f(0.96, 0.86, 0.4)
    else:
        glColor3f(0.75, 0.85, 1.0)

    for i in range(total_segments):
        t = i / float(total_segments - 1)
        x = -rope_half + t * (2 * rope_half)
        curve = -0.0009 * ((x - shift) ** 2)
        glPushMatrix()
        glTranslatef(x + shift, 12 + curve, z)
        glScalef(36, 6, 6)
        glRotatef(90, 0, 1, 0)
        glutSolidCube(1)
        glPopMatrix()

    # knot marker
    glPushMatrix()
    glTranslatef(shift, 18, z)
    glColor3f(0.1, 0.9, 0.6)
    glScalef(18, 18, 6)
    glutSolidCube(1)
    glPopMatrix()

# -------------------
# Input / keyboard
# -------------------
def keyboardListener(key, x, y):
    global fovY, tug_var, winner, game_paused, left_stamina, right_stamina
    global left_presses, right_presses, round_time_left, round_running, replay_mode
    global bot_enabled, animation_start, platform_fall_progress, replay_buffer
    global left_shake, right_shake

    # FOV controls (template behavior)
    if key == b'w':
        fovY += 1
    if key == b's':
        fovY -= 1

    # reset / start new round
    if key in (b'r', b'R'):
        tug_var = 0
        winner = None
        game_paused = False
        round_time_left = ROUND_DURATION
        round_running = True
        left_stamina = LEFT_MAX_STAM
        right_stamina = RIGHT_MAX_STAM
        left_presses = 0
        right_presses = 0
        animation_start = None
        platform_fall_progress = 0.0
        replay_buffer.clear()
        replay_mode = False
        left_shake = right_shake = 0.0
        return

    # Toggle bot
    if key in (b'b', b'B'):
        bot_enabled = not bot_enabled
        return

    # Playback replay if round ended
    if key in (b'p', b'P'):
        if game_paused and len(replay_buffer) > 0:
            replay_mode = True
            return

    if replay_mode or game_paused:
        return

    # Stamina gating
    if key in (b'a', b'A'):
        if left_stamina >= STAM_COST_PER_PRESS:
            tug_var += 1
            left_stamina -= STAM_COST_PER_PRESS
            left_presses += 1
            left_shake = min(1.5, left_shake + 0.6)  # trigger shake on strong tug
    if key in (b'l', b'L'):
        if right_stamina >= STAM_COST_PER_PRESS:
            tug_var -= 1
            right_stamina -= STAM_COST_PER_PRESS
            right_presses += 1
            right_shake = min(1.5, right_shake + 0.6)

    # clamp runaway
    tug_cap = TUG_LIMIT * 3
    if tug_var > tug_cap:
        tug_var = tug_cap
    if tug_var < -tug_cap:
        tug_var = -tug_cap

    # Check win condition
    if tug_var > TUG_LIMIT:
        winner = 'A'
        game_paused = True
        animation_start = time.time()
    if tug_var < -TUG_LIMIT:
        winner = 'L'
        game_paused = True
        animation_start = time.time()

def specialKeyListener(key, x, y):
    global camera_pos
    x0, y0, z0 = camera_pos
    if key == GLUT_KEY_UP:
        y0 += 10
    if key == GLUT_KEY_DOWN:
        y0 -= 10
    if key == GLUT_KEY_LEFT:
        x0 -= 10
    if key == GLUT_KEY_RIGHT:
        x0 += 10
    camera_pos = (x0, y0, z0)

def mouseListener(button, state, x, y):
    pass

def setupCamera():
    global camera_pos
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(fovY, 1.25, 0.1, 15000)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    x, y, z = camera_pos
    gluLookAt(x, y, z,
              0, 0, 0,
              0, 0, 1)

# -------------------
# Idle / update
# -------------------
def idle():
    global _last_time_ms, left_stamina, right_stamina, round_time_left, round_running
    global bot_enabled, last_bot_action, tug_var, right_presses, winner, game_paused
    global replay_buffer, replay_mode, animation_start, platform_fall_progress
    global left_shake, right_shake

    # compute delta time (seconds)
    cur_ms = glutGet(GLUT_ELAPSED_TIME)
    if _last_time_ms is None:
        _last_time_ms = cur_ms
    dt = (cur_ms - _last_time_ms) / 1000.0
    _last_time_ms = cur_ms

    if dt <= 0:
        glutPostRedisplay()
        return

    # Recover stamina
    if not game_paused:
        left_stamina = min(LEFT_MAX_STAM, left_stamina + STAM_RECOVER_RATE * dt)
        right_stamina = min(RIGHT_MAX_STAM, right_stamina + STAM_RECOVER_RATE * dt)

    # Decay shakes
    if left_shake > 0.0:
        left_shake = max(0.0, left_shake - SHAKE_DECAY * dt)
    if right_shake > 0.0:
        right_shake = max(0.0, right_shake - SHAKE_DECAY * dt)

    # Round timer
    if round_enabled and round_running and not game_paused and not replay_mode:
        round_time_left -= dt
        if round_time_left <= 0:
            round_running = False
            if tug_var > 0:
                set_winner('A')
            elif tug_var < 0:
                set_winner('L')
            else:
                set_winner(None)  # tie

    # Bot logic
    if bot_enabled and not game_paused and not replay_mode:
        now = time.time()
        time_since = now - last_bot_action
        base_interval = 0.18 + (1.0 - bot_difficulty) * 0.8
        adapt = 1.0 - max(0.0, min(1.0, tug_var / float(TUG_LIMIT)))
        interval = base_interval * (0.7 + 0.6 * (1.0 - adapt))
        interval *= (0.75 + 0.5 * random.random())
        if time_since >= interval:
            if right_stamina >= STAM_COST_PER_PRESS:
                globals()['tug_var'] -= 1
                globals()['right_stamina'] -= STAM_COST_PER_PRESS
                globals()['right_presses'] += 1
                globals()['right_shake'] = min(1.5, globals()['right_shake'] + 0.6)
            globals()['last_bot_action'] = now

    # Win animation progress and highscore saving
    if animation_start is not None:
        anim_elapsed = time.time() - animation_start
        platform_fall_progress = min(1.0, anim_elapsed / ANIM_DURATION)
        if anim_elapsed >= ANIM_DURATION:
            try:
                entry = {
                    "time": time.time(),
                    "winner": winner,
                    "tug_at_end": tug_var,
                    "left_presses": left_presses,
                    "right_presses": right_presses,
                    "round_duration": ROUND_DURATION - max(0.0, round_time_left)
                }
                with open(HIGHSCORE_FILE, "a+") as f:
                    f.write(json.dumps(entry) + "\\n")
            except Exception as e:
                print("Error saving score:", e)
            globals()['animation_start'] = None  # prevent repeat

    # Maintain replay buffer (while not replaying)
    if not replay_mode:
        replay_buffer.append({
            "t": time.time(),
            "tug": tug_var,
            "left_p": left_presses,
            "right_p": right_presses,
            "left_stam": left_stamina,
            "right_stam": right_stamina
        })
        if len(replay_buffer) > max_replay_frames:
            replay_buffer.pop(0)

    # Replay stepping
    if replay_mode:
        replay_index_local = globals().get('replay_index', 0)
        replay_index_local += int(replay_speed * (dt * REPLAY_FPS))
        if replay_index_local >= len(replay_buffer):
            replay_index_local = 0
            globals()['replay_mode'] = False
        globals()['replay_index'] = replay_index_local

    glutPostRedisplay()

def set_winner(who):
    global winner, game_paused, animation_start
    winner = who
    game_paused = True
    animation_start = time.time()

# -------------------
# Rendering / display
# -------------------
def showScreen():
    global tug_var, winner, game_paused, left_stamina, right_stamina
    global left_presses, right_presses, round_time_left, round_running, bot_enabled
    global replay_mode, replay_index, replay_buffer, platform_fall_progress, animation_start
    global show_scores_list, left_shake, right_shake

    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, 1000, 800)
    setupCamera()

    # Lighting
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_COLOR_MATERIAL)
    ambient = [0.22, 0.22, 0.28, 1.0]
    diffuse = [0.85, 0.85, 0.9, 1.0]
    specular = [1.0, 1.0, 1.0, 1.0]
    position = [200.0, 800.0, 500.0, 1.0]
    glLightfv(GL_LIGHT0, GL_AMBIENT, ambient)
    glLightfv(GL_LIGHT0, GL_DIFFUSE, diffuse)
    glLightfv(GL_LIGHT0, GL_SPECULAR, specular)
    glLightfv(GL_LIGHT0, GL_POSITION, position)
    glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, specular)
    glMateriali(GL_FRONT_AND_BACK, GL_SHININESS, 30)

    # Floor
    glBegin(GL_QUADS)
    glColor3f(0.08, 0.08, 0.1)
    glVertex3f(-GRID_LENGTH, -GRID_LENGTH, -1)
    glVertex3f(GRID_LENGTH, -GRID_LENGTH, -1)
    glVertex3f(GRID_LENGTH, GRID_LENGTH, -1)
    glVertex3f(-GRID_LENGTH, GRID_LENGTH, -1)
    glEnd()

    # Scene snapshot if replaying
    if replay_mode:
        idx = min(len(replay_buffer)-1, replay_index) if replay_buffer else 0
        snapshot = replay_buffer[idx] if replay_buffer else None
        if snapshot:
            draw_live_scene(snapshot["tug"], snapshot["left_stam"], snapshot["right_stam"], snapshot["left_p"], snapshot["right_p"], anim_progress=0.0)
        else:
            draw_live_scene(tug_var, left_stamina, right_stamina, left_presses, right_presses, anim_progress=platform_fall_progress)
    else:
        draw_live_scene(tug_var, left_stamina, right_stamina, left_presses, right_presses, anim_progress=platform_fall_progress)

    # HUD overlay
    glDisable(GL_LIGHTING)
    draw_text(10, 770, f"TUG Value: {tug_var}")
    draw_text(10, 745, f"Left (A): presses={left_presses} stamina={int(left_stamina)}/{int(LEFT_MAX_STAM)}")
    draw_text(10, 720, f"Right (L): presses={right_presses} stamina={int(right_stamina)}/{int(RIGHT_MAX_STAM)} {'(BOT)' if bot_enabled else ''}")
    draw_text(10, 690, "Controls: A/L tug • B bot • R reset • W/S FOV • Arrows move camera • P replay (after round)")
    draw_text(10, 665, f"Round time left: {int(round_time_left)}s  (duration {int(ROUND_DURATION)}s)")

    # Tug progress bar
    if winner is None and not replay_mode:
        bar_y = 50
        glBegin(GL_LINE_LOOP)
        glColor3f(1, 1, 1)
        glVertex2f(200, bar_y - 10); glVertex2f(800, bar_y - 10)
        glVertex2f(800, bar_y + 10); glVertex2f(200, bar_y + 10)
        glEnd()
        clamped = max(-TUG_LIMIT, min(TUG_LIMIT, tug_var))
        portion = (clamped + TUG_LIMIT) / (2 * TUG_LIMIT)
        filled_x = 200 + portion * (800 - 200)
        glBegin(GL_QUADS)
        if tug_var >= 0:
            glColor3f(0.95, 0.2, 0.65)
        else:
            glColor3f(0.2, 0.35, 1.0)
        glVertex2f(200, bar_y - 10); glVertex2f(filled_x, bar_y - 10)
        glVertex2f(filled_x, bar_y + 10); glVertex2f(200, bar_y + 10)
        glEnd()

    if game_paused and not replay_mode:
        if winner:
            draw_text(350, 420, f"WINNER: {'LEFT (A)' if winner=='A' else 'RIGHT (L)'}")
            draw_text(360, 390, "Victory animation playing... Press 'P' to view replay after animation.")
        else:
            draw_text(420, 420, "ROUND TIED")
        draw_text(380, 360, "Press 'R' to play again.")

    # Recent scores
    try:
        if os.path.exists(HIGHSCORE_FILE):
            with open(HIGHSCORE_FILE, "r") as f:
                lines = f.readlines()[-5:]
                show_scores_list = [json.loads(l) for l in lines if l.strip()]
    except Exception:
        show_scores_list = []

    y0 = 600
    draw_text(780, y0, "Recent Wins:"); y0 -= 20
    for s in reversed(show_scores_list):
        tlabel = time.strftime("%H:%M:%S", time.localtime(s.get("time", time.time())))
        draw_text(760, y0, f"{tlabel} {s.get('winner','?')} tg:{s.get('tug_at_end',0)} lp:{s.get('left_presses',0)} rp:{s.get('right_presses',0)}")
        y0 -= 18
    glEnable(GL_LIGHTING)

    glutSwapBuffers()

# -------------------
# Compose 3D scene
# -------------------
def draw_live_scene(tug_val, left_stam, right_stam, left_p_cnt, right_p_cnt, anim_progress=0.0):
    """Compose the 3D scene using provided parameters (live or snapshot)."""

    # Platforms falling on loss
    fall_offset = anim_progress * 220.0
    now_sec = glutGet(GLUT_ELAPSED_TIME) / 1000.0
    # shake offsets (scene Y)
    sh_left = math.sin(now_sec * SHAKE_FREQ * 2.0) * SHAKE_PIXELS * left_shake if winner is None else 0.0
    sh_right = math.sin(now_sec * SHAKE_FREQ * 2.0 + 1.1) * SHAKE_PIXELS * right_shake if winner is None else 0.0

    # left platform (shake + fall if RIGHT wins)
    glPushMatrix()
    if sh_left != 0.0:
        glTranslatef(0, sh_left, 0)
    draw_platform(-300, 0, falling_offset=fall_offset if winner=='L' else 0.0)
    glPopMatrix()

    # right platform (shake + fall if LEFT wins)
    glPushMatrix()
    if sh_right != 0.0:
        glTranslatef(0, sh_right, 0)
    draw_platform(300, 0, falling_offset=fall_offset if winner=='A' else 0.0)
    glPopMatrix()

    # Support legs
    for xp in (-300, 300):
        glPushMatrix()
        leg_fall = (fall_offset if (winner == ('L' if xp<0 else 'A')) else 0.0)
        glTranslatef(xp, -35 - leg_fall, 0)
        glScalef(40, 40, 70)
        glColor3f(0.25, 0.2, 0.25)
        glutSolidCube(1)
        glPopMatrix()

    # Tugging lean
    left_lean = min(25, tug_val * 2)
    right_lean = min(25, -tug_val * 2)

    # Losing tumble and falling
    left_fall = fall_offset if winner == 'L' else 0.0
    right_fall = fall_offset if winner == 'A' else 0.0
    left_tumble = 50.0 * anim_progress if winner == 'L' else 0.0
    right_tumble = -50.0 * anim_progress if winner == 'A' else 0.0

    # Victory jump (sinusoidal arc)
    left_jump = 0.0
    right_jump = 0.0
    if winner == 'A':
        left_jump = 45.0 * math.sin(min(1.0, anim_progress) * math.pi)
    elif winner == 'L':
        right_jump = 45.0 * math.sin(min(1.0, anim_progress) * math.pi)

    # Players
    draw_player(-320, 0, color=(0.98, 0.15, 0.55), lean=left_lean, falling=left_fall, tumble_deg=left_tumble, victory_jump=left_jump)
    draw_player(320, 0, color=(0.1, 0.4, 1.0),  lean=-right_lean, falling=right_fall, tumble_deg=right_tumble, victory_jump=right_jump)

    # Central platform
    glPushMatrix()
    glTranslatef(0, - (fall_offset if winner else 0.0), 0)
    glColor3f(0.15, 0.15, 0.2)
    glScalef(80, 80, 12)
    glutSolidCube(1)
    glPopMatrix()

    # Rope
    draw_rope(0, 0, tug_val)

    # Decorative light pylons
    for xp in (-260, 260):
        glPushMatrix()
        lfall = (fall_offset if (xp>0 and winner=='A') or (xp<0 and winner=='L') else 0.0)
        glTranslatef(xp, 60 - lfall, 20)
        glRotatef(-90, 1, 0, 0)
        glColor3f(0.2, 0.95, 0.6)
        glPushMatrix()
        glScalef(3, 3, 100)
        glutSolidCube(1)
        glPopMatrix()
        glTranslatef(0, 0, 55)
        glColor3f(1.0, 1.0, 1.0)
        glutSolidSphere(8, 12, 12)
        glPopMatrix()

    # Simple shadows (flattened quads)
    glDisable(GL_LIGHTING)
    glColor4f(0.0, 0.0, 0.0, 0.35)
    glBegin(GL_QUADS)
    glVertex3f(-360, -6, -0.9); glVertex3f(-280, -6, -0.9); glVertex3f(-280, 12, -0.9); glVertex3f(-360, 12, -0.9)
    glEnd()
    glBegin(GL_QUADS)
    glVertex3f(240, -6, -0.9); glVertex3f(320, -6, -0.9); glVertex3f(320, 12, -0.9); glVertex3f(240, 12, -0.9)
    glEnd()
    glEnable(GL_LIGHTING)

# -------------------
# Main
# -------------------
def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(1000, 800)
    glutInitWindowPosition(0, 0)
    glutCreateWindow(b"TUG OF ROPE - Squid Neon 3D")

    glEnable(GL_DEPTH_TEST)
    glShadeModel(GL_SMOOTH)

    glutDisplayFunc(showScreen)
    glutKeyboardFunc(keyboardListener)
    glutSpecialFunc(specialKeyListener)
    glutMouseFunc(mouseListener)
    glutIdleFunc(idle)

    glutMainLoop()

if __name__ == "__main__":
    main()