from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import math
import time
import random
import json
import os

# -------------------
# Camera / scene
# -------------------
camera_pos = (0, 500, 500)
fovY = 120
GRID_LENGTH = 600

# -------------------
# Game state variables
# -------------------
tug_var = 0  # variable changed by players: A -> +1, L -> -1
TUG_LIMIT = 10  # winning threshold (crossing >+TUG_LIMIT or <-TUG_LIMIT)
winner = None  # 'A' or 'L' or None
game_paused = False  # stops inputs when round ended
round_enabled = True
ROUND_DURATION = 30.0  # seconds per round
round_time_left = ROUND_DURATION
round_running = True
left_lean = 0.0
right_lean=0.0
# Player celebration animations
winning_player_jump = 0.0  # 0.0 to 1.0 jump cycle
losing_player_fall = 0.0   # 0.0 to 1.0 fall progress
JUMP_HEIGHT = 25.0         # how high the winner jumps
FALL_SPEED = 80.0          # how fast loser falls
# Stamina mechanic
LEFT_MAX_STAM = 100.0
RIGHT_MAX_STAM = 100.0
left_stamina = LEFT_MAX_STAM
right_stamina = RIGHT_MAX_STAM
STAM_COST_PER_PRESS = 12.0  # cost per keypress
STAM_RECOVER_RATE = 18.0  # per second

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
ANIM_DURATION = 3.0  # seconds of win animation
platform_fall_progress = 0.0

# Referee and Scoreboard Features
referee_arm_animation = 0.0  # 0.0 = neutral, 1.0 = full raised arm
referee_arm_side = None  # 'left', 'right', or 'both' for winner announcement
referee_idle_sway = 0.0  # subtle idle animation
scoreboard_highlight = None  # 'left', 'right', or None for winner highlighting

# Highscore file - store last N wins as JSON lines
HIGHSCORE_FILE = "tug_highscores.jsonl"
max_saved_scores = 50
left_lean_feedback = 0.0   # current lean angle for left player
right_lean_feedback = 0.0  # current lean angle for right player
LEAN_AMOUNT = 15.0         # degrees to lean when pressing
LEAN_RECOVERY_SPEED = 60.0 # degrees per second recovery back to upright

# Key press states for lean tracking
left_key_pressed = False
right_key_pressed = False

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
    """Small simple character represented by stacked cubes and a sphere head. lean rotates the player slightly when pressing; falling lowers the player."""
    glPushMatrix()
    glTranslatef(x, 20 - falling, z)
    glRotatef(lean, 0, 0, 1)
    glColor3f(*color)
    # torso
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


def draw_scoreboard_text_3d(x, y, z, text, scale=0.12):
    """Draw 3D text on the scoreboard"""
    glPushMatrix()
    glTranslatef(x, y, z)
    glScalef(scale, scale, scale)
    glColor3f(1.0, 1.0, 1.0)  # White text for
    for char in text:
        glutStrokeCharacter(GLUT_STROKE_ROMAN, ord(char))
    glPopMatrix()


def draw_referee(x, z, arm_anim=0.0, arm_side=None, idle_sway=0.0):
    """Draw referee character with arm animations for winner announcement.
    Updated to be stylistically similar to players (legs + torso) and arms raise upward.
    """
    glPushMatrix()
    glTranslatef(x, -60, z)
    # Apply subtle idle swaying
    glRotatef(math.sin(idle_sway) * 3, 0, 0, 1)

    # Body (torso) - yellow shirt
    glColor3f(1.0, 1.0, 0.0)
    glPushMatrix()
    glScalef(18, 18, 36)
    glutSolidCube(1)
    glPopMatrix()

    # Pelvis / lower body to make him look like players
    glPushMatrix()
    glTranslatef(0, -14, -8)
    glScalef(14, 12, 12)
    glutSolidCube(1)
    glPopMatrix()

    # Legs (two small cubes)
    glPushMatrix()
    glTranslatef(-6, -28, -8)
    glScalef(8, 8, 24)
    glColor3f(0.2, 0.2, 0.2)
    glutSolidCube(1)
    glPopMatrix()

    glPushMatrix()
    glTranslatef(6, -28, -8)
    glScalef(8, 8, 24)
    glColor3f(0.2, 0.2, 0.2)
    glutSolidCube(1)
    glPopMatrix()

    # Head
    glPushMatrix()
    glTranslatef(0, 0, 30)
    glColor3f(0.95, 0.85, 0.75)  # skin tone
    glutSolidSphere(10, 10, 10)
    glPopMatrix()

    # Arms - positioned with shoulder offset, rotate around X to raise up (like a real arm raise)
    max_raise_deg = 120.0
    # Left arm
    glPushMatrix()
    glTranslatef(-20, 0, 15)  # shoulder
    # Determine animation angle
    left_angle = 0.0
    if arm_side == 'left' or arm_side == 'both':
        left_angle = -max_raise_deg * arm_anim
    elif arm_side == 'right':
        left_angle = 0.0
    # If tie (both), add a waving motion
    if arm_side == 'both':
        left_angle += math.sin(idle_sway * 3.0) * 15.0
    glRotatef(left_angle, 1, 0, 0)
    glColor3f(1.0, 1.0, 0.0)
    glTranslatef(0, -6, 0)
    glScalef(6, 6, 24)
    glutSolidCube(1)
    glPopMatrix()

    # Right arm
    glPushMatrix()
    glTranslatef(20, 0, 15)  # shoulder
    right_angle = 0.0
    if arm_side == 'right' or arm_side == 'both':
        right_angle = max_raise_deg * arm_anim
    elif arm_side == 'left':
        right_angle = 0.0
    if arm_side == 'both':
        right_angle += math.sin(idle_sway * 3.0 + 0.8) * 15.0
    glRotatef(right_angle, 1, 0, 0)
    glColor3f(1.0, 1.0, 0.0)
    glTranslatef(0, -6, 0)
    glScalef(6, 6, 24)
    glutSolidCube(1)
    glPopMatrix()
    glPopMatrix()

def draw_scoreboard(x, z, tug_val, left_stam, right_stam, left_presses, right_presses, highlight=None):
    """Draw a scoreboard showing real-time game information.
    The scoreboard is positioned just in front of the referee (closer Z) and
    during gameplay it shows a compact live indicator; after the round it
    shows a larger black board with winner/loser.
    """
    glPushMatrix()
    # place the board slightly in front of the referee (so it appears 'right before' them)
    glTranslatef(x, 60, z)

    # Scoreboard frame (black color)
    glColor3f(0.0, 0.0, 0.0)
    glPushMatrix()
    glScalef(140, 90, 8)
    glutSolidCube(1)
    glPopMatrix()

    # Screen inset (a touch recessed)
    glPushMatrix()
    glTranslatef(0, 0, 5)
    glColor3f(0.0, 0.0, 0.0)
    glScalef(130, 80, 2)
    glutSolidCube(1)
    glPopMatrix()

    glDisable(GL_LIGHTING)

    if game_paused and winner is not None:
        # Big end-of-round display: highlight winner side on the board
        # Left area
        glPushMatrix()
        glTranslatef(-38, 10, 8)
        if highlight == 'left':
            glColor3f(0.6, 0.15, 0.15)
        else:
            glColor3f(0.15, 0.15, 0.15)
        glScalef(70, 50, 1)
        glutSolidCube(1)
        glPopMatrix()
        # Right area
        glPushMatrix()
        glTranslatef(38, 10, 8)
        if highlight == 'right':
            glColor3f(0.15, 0.2, 0.6)
        else:
            glColor3f(0.15, 0.15, 0.15)
        glScalef(70, 50, 1)
        glutSolidCube(1)
        glPopMatrix()

        # Draw text for winner/loser
        # Left side text
        draw_scoreboard_text_3d(-60, 0, 12, "LEFT", scale=0.16)
        draw_scoreboard_text_3d(-60, -18, 12, f"SCORE: {left_presses}", scale=0.12)
        # Right side text
        draw_scoreboard_text_3d(14, 0, 12, "RIGHT", scale=0.16)
        draw_scoreboard_text_3d(14, -18, 12, f"SCORE: {right_presses}", scale=0.12)

        # Center winner label
        if winner == 'A':
            draw_scoreboard_text_3d(-20, 30, 12, "WINNER: LEFT", scale=0.14)
            draw_referee(0, 0, arm_anim=1.0, arm_side="left", idle_sway=glutGet(GLUT_ELAPSED_TIME)/1000.0)
        elif winner == 'L':
            draw_scoreboard_text_3d(-24, 30, 12, "WINNER: RIGHT", scale=0.14)
            draw_referee(0, 0, arm_anim=1.0, arm_side="right", idle_sway=glutGet(GLUT_ELAPSED_TIME)/1000.0)
        

    elif game_paused and winner is None:
        # Tie display
        draw_scoreboard_text_3d(-25, 10, 12, "TIE GAME", scale=0.18)
        draw_scoreboard_text_3d(-35, -10, 12, f"LEFT: {left_presses}", scale=0.12)
        draw_scoreboard_text_3d(-35, -24, 12, f"RIGHT: {right_presses}", scale=0.12)

    else:
        # During gameplay show a compact live indicator bar and stamina info
        glEnable(GL_LIGHTING)
        glPushMatrix()
        glTranslatef(0, -10, 8)
        # Base bar
        glColor3f(0.2, 0.2, 0.2)
        glScalef(100, 10, 2)
        glutSolidCube(1)
        glPopMatrix()

        # Moving indicator
        glPushMatrix()
        indicator_pos = max(-40, min(40, tug_val * 3.8))
        glTranslatef(indicator_pos, -10, 12)
        if tug_val > 0:
            glColor3f(1.0, 0.3, 0.3)
        elif tug_val < 0:
            glColor3f(0.3, 0.4, 1.0)
        else:
            glColor3f(1.0, 1.0, 0.3)
        glScalef(10, 14, 4)
        glutSolidCube(1)
        glPopMatrix()

        glDisable(GL_LIGHTING)
        # Stamina tiny texts
        draw_scoreboard_text_3d(-60, 20, 12, f"L STAM: {int(left_stam)}", scale=0.08)
        draw_scoreboard_text_3d(-60, 8, 12, f"LP: {left_presses}", scale=0.08)
        draw_scoreboard_text_3d(10, 20, 12, f"R STAM: {int(right_stam)}", scale=0.08)
        draw_scoreboard_text_3d(10, 8, 12, f"RP: {right_presses}", scale=0.08)

    glEnable(GL_LIGHTING)
    glPopMatrix()


def draw_rope(center_x, z, tug_value):
    """Draw rope as a thin long box, shifted slightly by tug_value. For more realism, draw it as several segments to suggest curvature."""
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
    global referee_arm_animation, referee_arm_side, scoreboard_highlight
    global winning_player_jump, losing_player_fall
    global left_key_pressed, right_key_pressed, left_lean_feedback, right_lean_feedback

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
        # Reset referee and scoreboard
        referee_arm_animation = 0.0
        referee_arm_side = None
        scoreboard_highlight = None
        # Reset player animations
        winning_player_jump = 0.0
        losing_player_fall = 0.0
        # Reset lean feedback
        left_lean_feedback = 0.0
        right_lean_feedback = 0.0
        left_key_pressed = False
        right_key_pressed = False
        return

    # Toggle bot
    if key == b'b' or key == b'B':
        bot_enabled = not bot_enabled
        return

    # Playback replay if round ended
    if key == b'p' or key == b'P':
        if game_paused and len(replay_buffer) > 0:
            replay_mode = True
        return

    # If replay playing, ignore inputs
    if replay_mode:
        return

    # If paused (a winner already), no inputs except reset, bot toggle, replay
    if game_paused:
        return

    # Stamina gating and lean feedback for left player (A key)
    if (key == b'a' or key == b'A'):
        if left_stamina >= STAM_COST_PER_PRESS:
            tug_var += 1
            left_stamina -= STAM_COST_PER_PRESS
            left_presses += 1
            # Trigger lean forward when successfully pulling
            left_key_pressed = True
            left_lean_feedback = LEAN_AMOUNT
        else:
            # Even if no stamina, show slight lean attempt
            left_lean_feedback = LEAN_AMOUNT * 0.3

    # Stamina gating and lean feedback for right player (L key)
    if (key == b'l' or key == b'L'):
        if right_stamina >= STAM_COST_PER_PRESS:
            tug_var -= 1
            right_stamina -= STAM_COST_PER_PRESS
            right_presses += 1
            # Trigger lean forward when successfully pulling
            right_key_pressed = True
            right_lean_feedback = LEAN_AMOUNT
        else:
            # Even if no stamina, show slight lean attempt
            right_lean_feedback = LEAN_AMOUNT * 0.3

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
        referee_arm_side = 'left'
        scoreboard_highlight = 'left'
    if tug_var < -TUG_LIMIT:
        winner = 'L'
        game_paused = True
        animation_start = time.time()
        referee_arm_side = 'right'
        scoreboard_highlight = 'right'


# -------------------
# Modified Global Variables (add these to your existing globals)
# -------------------
# Player lean feedback
left_lean_feedback = 0.0   # current lean angle for left player
right_lean_feedback = 0.0  # current lean angle for right player
LEAN_AMOUNT = 15.0         # degrees to lean when pressing
LEAN_RECOVERY_SPEED = 60.0 # degrees per second recovery back to upright

# Key press states for lean tracking
left_key_pressed = False
right_key_pressed = False

# -------------------
# Modified keyboardListener function
# -------------------
def keyboardListener(key, x, y):
    global fovY, tug_var, winner, game_paused, left_stamina, right_stamina
    global left_presses, right_presses, round_time_left, round_running, replay_mode
    global bot_enabled, animation_start, platform_fall_progress, replay_buffer
    global referee_arm_animation, referee_arm_side, scoreboard_highlight
    global winning_player_jump, losing_player_fall
    global left_key_pressed, right_key_pressed, left_lean_feedback, right_lean_feedback

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
        # Reset referee and scoreboard
        referee_arm_animation = 0.0
        referee_arm_side = None
        scoreboard_highlight = None
        # Reset player animations
        winning_player_jump = 0.0
        losing_player_fall = 0.0
        # Reset lean feedback
        left_lean_feedback = 0.0
        right_lean_feedback = 0.0
        left_key_pressed = False
        right_key_pressed = False
        return

    # Toggle bot
    if key == b'b' or key == b'B':
        bot_enabled = not bot_enabled
        return

    # Playback replay if round ended
    if key == b'p' or key == b'P':
        if game_paused and len(replay_buffer) > 0:
            replay_mode = True
        return

    # If replay playing, ignore inputs
    if replay_mode:
        return

    # If paused (a winner already), no inputs except reset, bot toggle, replay
    if game_paused:
        return

    # Stamina gating and lean feedback for left player (A key)
    if (key == b'a' or key == b'A'):
        if left_stamina >= STAM_COST_PER_PRESS:
            tug_var += 1
            left_stamina -= STAM_COST_PER_PRESS
            left_presses += 1
            # Trigger lean forward when successfully pulling
            left_key_pressed = True
            left_lean_feedback = LEAN_AMOUNT
        else:
            # Even if no stamina, show slight lean attempt
            left_lean_feedback = LEAN_AMOUNT * 0.3

    # Stamina gating and lean feedback for right player (L key)
    if (key == b'l' or key == b'L'):
        if right_stamina >= STAM_COST_PER_PRESS:
            tug_var -= 1
            right_stamina -= STAM_COST_PER_PRESS
            right_presses += 1
            # Trigger lean forward when successfully pulling
            right_key_pressed = True
            right_lean_feedback = LEAN_AMOUNT
        else:
            # Even if no stamina, show slight lean attempt
            right_lean_feedback = LEAN_AMOUNT * 0.3

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
        referee_arm_side = 'left'
        scoreboard_highlight = 'left'
    if tug_var < -TUG_LIMIT:
        winner = 'L'
        game_paused = True
        animation_start = time.time()
        referee_arm_side = 'right'
        scoreboard_highlight = 'right'


# -------------------
# New key up handler for lean recovery
# -------------------
def keyUp(key, x, y):
    global left_key_pressed, right_key_pressed
    
    # When keys are released, mark them as not pressed so lean can recover
    if key == b'a' or key == b'A':
        left_key_pressed = False
    elif key == b'l' or key == b'L':
        right_key_pressed = False




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
    gluLookAt(x, y, z, 0, 0, 0, 0, 0, 1)

# -------------------
# Idle / update (existing function)
# -------------------

def idle():
    global _last_time_ms, left_stamina, right_stamina, round_time_left, round_running
    global bot_enabled, last_bot_action, tug_var, right_presses, winner, game_paused
    global replay_buffer, replay_mode, animation_start, platform_fall_progress
    global referee_arm_animation, referee_arm_side, referee_idle_sway, scoreboard_highlight
    global winning_player_jump, losing_player_fall
    global left_lean_feedback, right_lean_feedback, left_key_pressed, right_key_pressed

    # compute delta time (seconds)
    cur_ms = glutGet(GLUT_ELAPSED_TIME)
    if _last_time_ms is None:
        _last_time_ms = cur_ms
    dt = (cur_ms - _last_time_ms) / 1000.0
    _last_time_ms = cur_ms
    if dt <= 0:
        glutPostRedisplay()
        return

    # Update referee idle sway animation
    referee_idle_sway += dt * 2.0

    # Update player lean feedback - recover to upright when not pressing keys
    if not left_key_pressed:
        if left_lean_feedback > 0:
            left_lean_feedback = max(0.0, left_lean_feedback - LEAN_RECOVERY_SPEED * dt)
        elif left_lean_feedback < 0:
            left_lean_feedback = min(0.0, left_lean_feedback + LEAN_RECOVERY_SPEED * dt)
    
    if not right_key_pressed:
        if right_lean_feedback > 0:
            right_lean_feedback = max(0.0, right_lean_feedback - LEAN_RECOVERY_SPEED * dt)
        elif right_lean_feedback < 0:
            right_lean_feedback = min(0.0, right_lean_feedback + LEAN_RECOVERY_SPEED * dt)

    # Recover stamina gradually if round running and not paused
    if not game_paused:
        left_stamina = min(LEFT_MAX_STAM, left_stamina + STAM_RECOVER_RATE * dt)
        right_stamina = min(RIGHT_MAX_STAM, right_stamina + STAM_RECOVER_RATE * dt)

    # Round timer
    if round_enabled and round_running and not game_paused and not replay_mode:
        round_time_left -= dt
        if round_time_left <= 0:
            round_running = False
            if tug_var > 0:
                winner = 'A'
                referee_arm_side = 'left'
                scoreboard_highlight = 'left'
            elif tug_var < 0:
                winner = 'L'
                referee_arm_side = 'right'
                scoreboard_highlight = 'right'
            else:
                winner = None
                referee_arm_side = 'both'
                scoreboard_highlight = None
            game_paused = True
            animation_start = time.time()

    # Bot logic with lean feedback
    if bot_enabled and not game_paused and not replay_mode:
        now = time.time()
        time_since = now - last_bot_action
        base_interval = 0.18 + (1.0 - bot_difficulty) * 0.8
        adapt = 1.0 - max(0.0, min(1.0, tug_var / float(TUG_LIMIT)))
        interval = base_interval * (0.7 + 0.6 * (1.0 - adapt))
        interval *= (0.75 + 0.5 * random.random())
        if time_since >= interval:
            if right_stamina >= STAM_COST_PER_PRESS:
                tug_var -= 1
                right_stamina -= STAM_COST_PER_PRESS
                right_presses += 1
                # Bot also gets lean feedback
                right_lean_feedback = LEAN_AMOUNT
            last_bot_action = now

    # If round ended and animation pending, update animation progress
    if animation_start is not None:
        anim_elapsed = time.time() - animation_start
        platform_fall_progress = min(1.0, anim_elapsed / ANIM_DURATION)
        
        # Animate losing player falling down
        losing_player_fall = min(1.0, anim_elapsed / 2.0) * FALL_SPEED
        
        # Animate winning player jumping (continuous bounce)
        if winner is not None:
            jump_speed = 4.0
            winning_player_jump = abs(math.sin(anim_elapsed * jump_speed * math.pi)) * JUMP_HEIGHT
        
        # Animate referee arm raising
        if referee_arm_side is not None:
            referee_arm_animation = min(1.0, anim_elapsed / 1.5)

        # After animation finishes: record highscore and freeze game fully
        if anim_elapsed >= ANIM_DURATION:
            save_score = False
            if winner is not None:
                save_score = True
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
                    with open(HIGHSCORE_FILE, "a+") as f:
                        f.write(json.dumps(entry) + "\n")
                except Exception as e:
                    print("Error saving score:", e)
            animation_start = None

    # Maintain replay buffer while playing
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

    # When replay mode active we step through buffer in time
    if replay_mode:
        replay_index_local = globals().get('replay_index', 0)
        replay_index_local += int(replay_speed * (dt * REPLAY_FPS))
        if replay_index_local >= len(replay_buffer):
            replay_index_local = 0
            globals()['replay_mode'] = False
        globals()['replay_index'] = replay_index_local

    glutPostRedisplay()
def display():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    gluLookAt(0, 60, 200, 0, 0, 0, 0, 1, 0)  # camera looking at origin
    glutSwapBuffers()

# -------------------
# Rendering / display (existing function)
# -------------------

def showScreen():
    global rand_var, tug_var, winner, game_paused, left_stamina, right_stamina
    global left_presses, right_presses, round_time_left, round_running, bot_enabled
    global replay_buffer, replay_mode, animation_start, platform_fall_progress
    global show_scores_list, referee_arm_animation, referee_arm_side, referee_idle_sway, scoreboard_highlight

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
        idx = min(len(replay_buffer) - 1, replay_index) if replay_buffer else 0
        snapshot = replay_buffer[idx] if replay_buffer else None
        if snapshot:
            draw_live_scene(snapshot["tug"], snapshot["left_stam"], snapshot["right_stam"], snapshot["left_p"], snapshot["right_p"], fake_shadow=True, anim_progress=0.0)
        else:
            draw_live_scene(tug_var, left_stamina, right_stamina, left_presses, right_presses, fake_shadow=True, anim_progress=0.0)
        # During replay, show referee in neutral pose and scoreboard without highlights
        display()
        # draw_referee(0, -40, arm_anim=0.0, arm_side=None, idle_sway=referee_idle_sway)
        draw_scoreboard(0, -60, tug_var, left_stamina, right_stamina, left_presses, right_presses, highlight=None)
    else:
        # Live scene
        draw_live_scene(tug_var, left_stamina, right_stamina, left_presses, right_presses, fake_shadow=True, anim_progress=platform_fall_progress)
        # Draw referee with current animation state (positioned in middle)
        # draw_referee(0, -40, arm_anim=referee_arm_animation, arm_side=referee_arm_side, idle_sway=referee_idle_sway)
        # draw_referee(0, 0, arm_anim=1.0, arm_side="both", idle_sway=glutGet(GLUT_ELAPSED_TIME)/1000.0)
        draw_referee(0, 0, arm_anim=1.0, arm_side="both", idle_sway=glutGet(GLUT_ELAPSED_TIME)/1000.0)
        # Draw scoreboard with current highlight (positioned just in front of referee)
        # Use z slightly forward so scoreboard appears right before referee visually
        draw_scoreboard(0, -20, tug_var, left_stamina, right_stamina, left_presses, right_presses, highlight=scoreboard_highlight)

    # HUD overlay (2D)
    glDisable(GL_LIGHTING)
    draw_text(10, 770, f"TUG Value: {tug_var}")
    draw_text(10, 745, f"Left (A): presses={left_presses} stamina={int(left_stamina)}/{int(LEFT_MAX_STAM)}")
    draw_text(10, 720, f"Right (L): presses={right_presses} stamina={int(right_stamina)}/{int(RIGHT_MAX_STAM)} {'(BOT)' if bot_enabled else ''}")
    draw_text(10, 690, f"Press 'A' to increase (+1), 'L' decrease (-1). Press 'B' to toggle bot. 'R' to reset.")
    draw_text(10, 665, f"Round time left: {int(round_time_left)}s. Round duration {int(ROUND_DURATION)}s.")

    # show simple progress bar for tug (bottom)F
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
            # Set referee to wave both arms for tie
            if referee_arm_side != 'both':
                referee_arm_side = 'both'
        draw_text(380, 360, "Press 'R' to play again.")

    # show top recent scores loaded
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

    # Add referee and scoreboard info to HUD if replay_mode:
    if replay_mode:
        draw_text(10, 640, "REPLAY MODE - Press any key to exit")

    # Show referee status if referee_arm_side and not replay_mode:
    if referee_arm_side == 'left':
        draw_text(10, 615, "Referee: Announcing LEFT winner!")
    elif referee_arm_side == 'right':
        draw_text(10, 615, "Referee: Announcing RIGHT winner!")
    elif referee_arm_side == 'both':
        draw_text(10, 615, "Referee: Signaling TIE!")

    glEnable(GL_LIGHTING)
    glutSwapBuffers()

# -------------------
# draw_live_scene (not new top-level functions in template; we reuse template names only)
# -------------------

def draw_live_scene(tug_val, left_stam, right_stam, left_p_cnt, right_p_cnt, fake_shadow=True, anim_progress=0.0):
    """Compose the 3D scene using provided parameters (live or snapshot)."""
    # Visual falling platforms when anim in progress: anim_progress 0..1
    fall_offset = anim_progress * 220.0

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

    # REPLACE THE ENTIRE PLAYER SECTION WITH THIS:
    # Players - add a small lean when pressing (visual)
    left_lean = min(25, tug_val * 2)
    right_lean = min(25, -tug_val * 2)
    
    # Calculate falling and jumping amounts
    left_fall = fall_offset if winner == 'L' else 0.0
    right_fall = fall_offset if winner == 'A' else 0.0

    # Add celebration jumping for winner and extra falling for loser
    left_jump = 0.0
    right_jump = 0.0
    if winner == 'A':  # Left player wins
        left_jump = winning_player_jump
        right_fall += losing_player_fall  # Add extra fall for losing player
    elif winner == 'L':  # Right player wins
        right_jump = winning_player_jump
        left_fall += losing_player_fall  # Add extra fall for losing player

    # Draw players with animations (subtract jump to make them go up)
    draw_player(-320, 0, color=(1, 0.1, 0.1), lean=left_lean, falling=left_fall - left_jump)
    draw_player(320, 0, color=(0.1, 0.3, 1.0), lean=-right_lean, falling=right_fall - right_jump)

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
        # referee shadow
        glBegin(GL_QUADS)
        glVertex3f(-15, -56, -0.9)
        glVertex3f(15, -56, -0.9)
        glVertex3f(15, -44, -0.9)
        glVertex3f(-15, -44, -0.9)
        glEnd()
        # scoreboard shadow
        glBegin(GL_QUADS)
        glVertex3f(-60, -106, -0.9)
        glVertex3f(60, -106, -0.9)
        glVertex3f(60, -94, -0.9)
        glVertex3f(-60, -94, -0.9)
        glEnd()
        glEnable(GL_LIGHTING)

def key_down(key, x, y):
    global left_lean, right_lean
    if key == b'a':   # Left player pulls
        left_lean = -10.0
    elif key == b'l': # Right player pulls
        right_lean = 10.0

def key_up(key, x, y):
    global left_lean, right_lean
    if key == b'a':
        left_lean = 0.0
    elif key == b'l':
        right_lean=0.0
# -------------------
# Main (existing template)
# -------------------

def main():
    glutInit()
    glutKeyboardFunc(key_down)   # normal keys pressed
    glutKeyboardUpFunc(key_up)
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(1000, 800)
    glutInitWindowPosition(0, 0)
    wind = glutCreateWindow(b"TUG OF ROPE - Enhanced with Referee & Scoreboard")
    # Enable depth testing for proper 3D overlap
    glEnable(GL_DEPTH_TEST)
    glShadeModel(GL_SMOOTH)
    glutDisplayFunc(showScreen)
    glutKeyboardFunc(keyboardListener)
    glutSpecialFunc(specialKeyListener)
    glutMouseFunc(mouseListener)
    glutIdleFunc(idle)
    glutMainLoop()
    


if _name_ == "_main_":
    main()