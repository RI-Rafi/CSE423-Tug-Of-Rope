from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import math
import time
import json
import os
import random

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

# Replay buffer: store recent frames (time, tug_var, left_presses, right_presses, left_stam, right_stam)
REPLAY_SECONDS = 6.0
REPLAY_FPS = 60.0
max_replay_frames = int(REPLAY_SECONDS * REPLAY_FPS)
replay_buffer = []
replay_mode = False
replay_index = 0
replay_speed = 1.0  # play speed multiplier for replay

# Win animation
animation_start = None
ANIM_DURATION = 3.0   # seconds of win animation
platform_fall_progress = 0.0

# Highscore file - store last N wins as JSON lines
HIGHSCORE_FILE = "tug_highscores.jsonl"
max_saved_scores = 50

# Time tracking for dt updates
_last_time_ms = None

# HUD / UI
show_scores_list = []  # loaded scores to display

# Misc
rand_var = 423

# -------------------
# Utility / drawing functions (existing template functions used and extended)
# -------------------
def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
    glColor3f(1, 1, 1)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    # Set up orthographic projection that matches window coordinates
    gluOrtho2D(0, 1000, 0, 800)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    # Draw text at (x, y) in screen coords
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def draw_platform(x, z, width=220, depth=60, height=10, falling_offset=0.0):
    """Simple rectangular platform at (x, z). falling_offset moves platform down for animation"""
    glPushMatrix()
    glTranslatef(x, -falling_offset, z)
    glScalef(width, depth, height)
    glutSolidCube(1)  # scaled cube acts as platform
    glPopMatrix()

def draw_player(x, z, color=(1, 0, 0), lean=0.0, falling=0.0):
    """Small simple character represented by stacked cubes and a sphere head.
       lean rotates the player slightly when pressing; falling lowers the player."""
    glPushMatrix()
    glTranslatef(x, 20 - falling, z)
    glRotatef(lean, 0, 0, 1)
    glColor3f(*color)
    # body
    glPushMatrix()
    glScalef(18, 18, 36)
    glutSolidCube(1)
    glPopMatrix()
    # head
    glPushMatrix()
    glTranslatef(0, 0, 30)
    glutSolidSphere(10, 10, 10)
    glPopMatrix()
    glPopMatrix()

def draw_rope(center_x, z, tug_value):
    """Draw rope as a thin long box, shifted slightly by tug_value.
       For more realism, draw it as several segments to suggest curvature."""
    total_segments = 12
    rope_half = 260
    # compute shift of the knot
    shift = tug_value * 12  # visual sensitivity
    # Draw segments between left and right
    for i in range(total_segments):
        t = i / float(total_segments - 1)
        x = -rope_half + t * (2 * rope_half)
        # add slight curve (a shallow parabola) and shift by the knot
        curve = -0.0009 * ((x - shift) ** 2) + 0.0
        glPushMatrix()
        glTranslatef(x + shift, 12 + curve, z)
        glScalef(40, 6, 6)
        glRotatef(90, 0, 1, 0)
        glutSolidCube(1)
        glPopMatrix()
    # knot marker
    glPushMatrix()
    glTranslatef(shift, 18, z)
    glScalef(18, 18, 6)
    glutSolidCube(1)
    glPopMatrix()

# -------------------
# Input / keyboard (existing functions)
# -------------------
def keyboardListener(key, x, y):
    global fovY, tug_var, winner, game_paused, left_stamina, right_stamina
    global left_presses, right_presses, round_time_left, round_running, replay_mode
    global bot_enabled, animation_start, platform_fall_progress, replay_buffer

    # FOV controls (template behavior)
    if key == b'w':
        fovY += 1
    if key == b's':
        fovY -= 1

    # reset / start new round
    if key == b'r' or key == b'R':
        # reset everything
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
        return

    # Toggle bot
    if key == b'b' or key == b'B':
        bot_enabled = not bot_enabled
        return

    # Playback replay if round ended
    if key == b'p' or key == b'P':
        # Only allow when game is paused (round ended)
        if game_paused and len(replay_buffer) > 0:
            # start replay
            # set replay_mode and freeze game state; replay will run in showScreen using replay buffer
            replay_mode = True
            # replay_index will be handled inside showScreen/idle
            return

    # If replay playing, ignore inputs
    if replay_mode:
        return

    # If paused (a winner already), no inputs except reset, bot toggle, replay
    if game_paused:
        return

    # Stamina gating: A increments only if left stamina enough
    if (key == b'a' or key == b'A'):
        if left_stamina >= STAM_COST_PER_PRESS:
            tug_var += 1
            left_stamina -= STAM_COST_PER_PRESS
            left_presses += 1
        else:
            # not enough stamina -- small penalty visual could be added
            pass

    if (key == b'l' or key == b'L'):
        if right_stamina >= STAM_COST_PER_PRESS:
            tug_var -= 1
            right_stamina -= STAM_COST_PER_PRESS
            right_presses += 1
        else:
            pass

    # clamp to avoid runaway
    if tug_var > TUG_LIMIT * 3:
        tug_var = TUG_LIMIT * 3
    if tug_var < -TUG_LIMIT * 3:
        tug_var = -TUG_LIMIT * 3

    # Check win condition
    if tug_var > TUG_LIMIT:
        winner = 'A'
        game_paused = True
        animation_start = time.time()
        # Save replay snapshot end (we'll save after animation)
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
    # placeholder (left from template)
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
# Idle / update (existing function)
# -------------------
def idle():
    global _last_time_ms, left_stamina, right_stamina, round_time_left, round_running
    global bot_enabled, last_bot_action, tug_var, right_presses, winner, game_paused
    global replay_buffer, replay_mode, animation_start, platform_fall_progress

    # compute delta time (seconds)
    cur_ms = glutGet(GLUT_ELAPSED_TIME)
    if _last_time_ms is None:
        _last_time_ms = cur_ms
    dt = (cur_ms - _last_time_ms) / 1000.0
    _last_time_ms = cur_ms

    if dt <= 0:
        glutPostRedisplay()
        return

    # Recover stamina gradually if round running and not paused
    if not game_paused:
        left_stamina = min(LEFT_MAX_STAM, left_stamina + STAM_RECOVER_RATE * dt)
        right_stamina = min(RIGHT_MAX_STAM, right_stamina + STAM_RECOVER_RATE * dt)

    # Round timer
    if round_enabled and round_running and not game_paused and not replay_mode:
        round_time_left -= dt
        if round_time_left <= 0:
            # time's up -> decide winner by tug_var sign or tie
            round_running = False
            if tug_var > 0:
                winner = 'A'
            elif tug_var < 0:
                winner = 'L'
            else:
                winner = None  # tie
            game_paused = True
            animation_start = time.time()

    # Bot logic (if enabled and right side slot is bot)
    if bot_enabled and not game_paused and not replay_mode:
        # bot decides to press based on difficulty, current tug_var, and a random chance
        # more aggressive when behind
        now = time.time()
        time_since = now - last_bot_action
        # target interval depends on difficulty and current situation
        base_interval = 0.18 + (1.0 - bot_difficulty) * 0.8  # lower is more frequent
        # If behind (tug_var > 0), increase aggression
        adapt = 1.0 - max(0.0, min(1.0, tug_var / float(TUG_LIMIT)))
        interval = base_interval * (0.7 + 0.6 * (1.0 - adapt))
        # Random jitter
        interval *= (0.75 + 0.5 * random.random())
        if time_since >= interval:
            # attempt a press if have stamina
            if right_stamina >= STAM_COST_PER_PRESS:
                tug_var -= 1
                right_stamina -= STAM_COST_PER_PRESS
                right_presses += 1
            last_bot_action = now

    # If round ended and animation pending, update animation progress
    if animation_start is not None:
        anim_elapsed = time.time() - animation_start
        platform_fall_progress = min(1.0, anim_elapsed / ANIM_DURATION)
        # After animation finishes: record highscore and freeze game fully (but allow replay)
        if anim_elapsed >= ANIM_DURATION:
            # finalize highscore saving once
            save_score = False
            if winner is not None:
                save_score = True
            # save results
            if save_score:
                try:
                    entry = {
                        "time": time.time(),
                        "winner": winner,
                        "tug_at_end": tug_var,
                        "left_presses": left_presses,
                        "right_presses": right_presses,
                        "round_duration": ROUND_DURATION - max(0.0, round_time_left)
                    }
                    # append JSON line
                    with open(HIGHSCORE_FILE, "a+") as f:
                        f.write(json.dumps(entry) + "\n")
                except Exception as e:
                    print("Error saving score:", e)
            # ensure we don't run this saving repeatedly
            animation_start = None
            # leave game_paused True so user can press R to restart
    # Maintain replay buffer while playing (store only when not replaying)
    if not replay_mode:
        # store snapshot
        replay_buffer.append({
            "t": time.time(),
            "tug": tug_var,
            "left_p": left_presses,
            "right_p": right_presses,
            "left_stam": left_stamina,
            "right_stam": right_stamina
        })
        # trim buffer
        if len(replay_buffer) > max_replay_frames:
            replay_buffer.pop(0)

    # When replay mode active we step through buffer in time
    if replay_mode:
        # step index forward; when reaches end, stop replay
        replay_index_local = globals().get('replay_index', 0)
        replay_index_local += int(replay_speed * (dt * REPLAY_FPS))
        if replay_index_local >= len(replay_buffer):
            # end replay
            replay_index_local = 0
            globals()['replay_mode'] = False
            # After replay, keep the game paused (user can reset)
        globals()['replay_index'] = replay_index_local

    glutPostRedisplay()

# -------------------
# Rendering / display (existing function)
# -------------------
def showScreen():
    global rand_var, tug_var, winner, game_paused, left_stamina, right_stamina
    global left_presses, right_presses, round_time_left, round_running, bot_enabled
    global replay_mode, replay_index, replay_buffer, platform_fall_progress, animation_start
    global show_scores_list

    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, 1000, 800)
    setupCamera()

    # Lighting improvements (specular + ambient)
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_COLOR_MATERIAL)
    ambient = [0.25, 0.25, 0.25, 1.0]
    diffuse = [0.7, 0.7, 0.7, 1.0]
    specular = [0.9, 0.9, 0.9, 1.0]
    position = [200.0, 800.0, 500.0, 1.0]
    glLightfv(GL_LIGHT0, GL_AMBIENT, ambient)
    glLightfv(GL_LIGHT0, GL_DIFFUSE, diffuse)
    glLightfv(GL_LIGHT0, GL_SPECULAR, specular)
    glLightfv(GL_LIGHT0, GL_POSITION, position)
    # shininess
    glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, specular)
    glMateriali(GL_FRONT_AND_BACK, GL_SHININESS, 20)

    # Draw floor
    glBegin(GL_QUADS)
    glColor3f(0.12, 0.12, 0.12)
    glVertex3f(-GRID_LENGTH, -GRID_LENGTH, -1)
    glVertex3f(GRID_LENGTH, -GRID_LENGTH, -1)
    glVertex3f(GRID_LENGTH, GRID_LENGTH, -1)
    glVertex3f(-GRID_LENGTH, GRID_LENGTH, -1)
    glEnd()

    # If in replay mode, draw scene from recorded snapshot instead of live variables
    if replay_mode:
        # pick snapshot
        idx = min(len(replay_buffer)-1, replay_index) if replay_buffer else 0
        snapshot = replay_buffer[idx] if replay_buffer else None
        if snapshot:
            draw_live_scene(snapshot["tug"], snapshot["left_stam"], snapshot["right_stam"], snapshot["left_p"], snapshot["right_p"], fake_shadow=True, anim_progress=0.0)
        else:
            draw_live_scene(tug_var, left_stamina, right_stamina, left_presses, right_presses, fake_shadow=True, anim_progress=0.0)
    else:
        draw_live_scene(tug_var, left_stamina, right_stamina, left_presses, right_presses, fake_shadow=True, anim_progress=platform_fall_progress)

    # HUD overlay (2D)
    glDisable(GL_LIGHTING)
    # fold in basic instructions and values
    draw_text(10, 770, f"TUG Value: {tug_var}")
    draw_text(10, 745, f"Left (A): presses={left_presses} stamina={int(left_stamina)}/{int(LEFT_MAX_STAM)}")
    draw_text(10, 720, f"Right (L): presses={right_presses} stamina={int(right_stamina)}/{int(RIGHT_MAX_STAM)} {'(BOT)' if bot_enabled else ''}")
    draw_text(10, 690, f"Press 'A' to increase (+1), 'L' decrease (-1). Press 'B' to toggle bot. 'R' to reset.")
    draw_text(10, 665, f"Round time left: {int(round_time_left)}s. Round duration {int(ROUND_DURATION)}s.")

    # show simple progress bar for tug (bottom)
    if winner is None and not replay_mode:
        bar_center_x = 500
        bar_y = 50
        glColor3f(1, 1, 1)
        glBegin(GL_LINE_LOOP)
        glVertex2f(200, bar_y - 10)
        glVertex2f(800, bar_y - 10)
        glVertex2f(800, bar_y + 10)
        glVertex2f(200, bar_y + 10)
        glEnd()
        clamped = max(-TUG_LIMIT, min(TUG_LIMIT, tug_var))
        portion = (clamped + TUG_LIMIT) / (2 * TUG_LIMIT)
        filled_x = 200 + portion * (800 - 200)
        glBegin(GL_QUADS)
        # left portion red, right portion blue mixing to visualize direction
        if tug_var >= 0:
            glColor3f(0.9, 0.2, 0.2)
        else:
            glColor3f(0.2, 0.3, 0.9)
        glVertex2f(200, bar_y - 10)
        glVertex2f(filled_x, bar_y - 10)
        glVertex2f(filled_x, bar_y + 10)
        glVertex2f(200, bar_y + 10)
        glEnd()

    # When game paused and we have a winner (or tie), display large message and allow replay
    if game_paused and not replay_mode:
        if winner:
            draw_text(350, 420, f"WINNER: {'LEFT (A)' if winner=='A' else 'RIGHT (L)'}", GLUT_BITMAP_HELVETICA_18)
            draw_text(360, 390, "Animation playing... Press 'P' to view replay after animation.")
        else:
            draw_text(420, 420, "ROUND TIED")
        draw_text(380, 360, "Press 'R' to play again.")

    # show top recent scores loaded
    # load a few lines from file lazily once per draw
    try:
        if os.path.exists(HIGHSCORE_FILE):
            with open(HIGHSCORE_FILE, "r") as f:
                lines = f.readlines()[-5:]
                show_scores_list = [json.loads(l) for l in lines if l.strip()]
    except Exception:
        show_scores_list = []

    y0 = 600
    draw_text(780, y0, "Recent Wins:")
    y0 -= 20
    for s in reversed(show_scores_list):
        tlabel = time.strftime("%H:%M:%S", time.localtime(s.get("time", time.time())))
        draw_text(760, y0, f"{tlabel} {s.get('winner','?')} tg:{s.get('tug_at_end',0)} lp:{s.get('left_presses',0)} rp:{s.get('right_presses',0)}")
        y0 -= 18

    glEnable(GL_LIGHTING)
    glutSwapBuffers()

# -------------------
# draw_live_scene (not new top-level functions in template; we reuse template names only)
# -------------------
def draw_live_scene(tug_val, left_stam, right_stam, left_p_cnt, right_p_cnt, fake_shadow=True, anim_progress=0.0):
    """Compose the 3D scene using provided parameters (live or snapshot)."""
    # Visual falling platforms when anim in progress: anim_progress 0..1
    fall_offset = anim_progress * 220.0  # how much platforms sink during animation

    # Platforms (left and right)
    glColor3f(0.7, 0.5, 0.2)
    # left platform
    draw_platform(-300, 0, falling_offset=fall_offset if winner=='L' else 0.0)
    # right platform
    draw_platform(300, 0, falling_offset=fall_offset if winner=='A' else 0.0)

    # Support legs under platforms
    for xp in (-300, 300):
        glPushMatrix()
        glTranslatef(xp, -35 - (fall_offset if (winner == ('L' if xp<0 else 'A')) else 0.0), 0)
        glScalef(40, 40, 70)
        glColor3f(0.4, 0.3, 0.25)
        glutSolidCube(1)
        glPopMatrix()

    # Players - add a small lean when pressing (visual)
    left_lean = min(25, tug_val * 2)
    right_lean = min(25, -tug_val * 2)
    # falling amount per side when they lose
    left_fall = fall_offset if winner == 'L' else 0.0
    right_fall = fall_offset if winner == 'A' else 0.0

    draw_player(-320, 0, color=(1, 0.1, 0.1), lean=left_lean, falling=left_fall)
    draw_player(320, 0, color=(0.1, 0.3, 1.0), lean= -right_lean, falling=right_fall)

    # Central platform
    glPushMatrix()
    glTranslatef(0, - (fall_offset if winner else 0.0), 0)
    glColor3f(0.2, 0.2, 0.25)
    glScalef(80, 80, 12)
    glutSolidCube(1)
    glPopMatrix()

    # Rope: color changes slightly based on tug direction
    if tug_val >= 0:
        glColor3f(0.95, 0.9, 0.6)
    else:
        glColor3f(0.8, 0.85, 0.95)
    draw_rope(0, 0, tug_val)

    # Decorative lights
    for xp in (-260, 260):
        glPushMatrix()
        glTranslatef(xp, 60 - (fall_offset if (xp>0 and winner=='A') or (xp<0 and winner=='L') else 0.0), 20)
        glRotatef(-90, 1, 0, 0)
        glPushMatrix()
        glScalef(3, 3, 100)
        glutSolidCube(1)
        glPopMatrix()
        glTranslatef(0, 0, 55)
        glutSolidSphere(8, 10, 10)
        glPopMatrix()

    # Fake shadows under players and platforms for depth (simple flattened dark quads)
    if fake_shadow:
        glDisable(GL_LIGHTING)
        # left shadow
        glColor4f(0.0, 0.0, 0.0, 0.35)
        glBegin(GL_QUADS)
        glVertex3f(-360, -6, -0.9)
        glVertex3f(-280, -6, -0.9)
        glVertex3f(-280, 12, -0.9)
        glVertex3f(-360, 12, -0.9)
        glEnd()
        # right shadow
        glBegin(GL_QUADS)
        glVertex3f(240, -6, -0.9)
        glVertex3f(320, -6, -0.9)
        glVertex3f(320, 12, -0.9)
        glVertex3f(240, 12, -0.9)
        glEnd()
        glEnable(GL_LIGHTING)

# -------------------
# Main (existing template)
# -------------------
def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(1000, 800)
    glutInitWindowPosition(0, 0)
    wind = glutCreateWindow(b"TUG OF ROPE - Enhanced Beginner 3D")

    # Enable depth testing for proper 3D overlap
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
