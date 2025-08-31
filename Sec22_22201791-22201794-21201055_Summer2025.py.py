from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import math
import random

camera_pos = (0, 500, 300)
fovY = 120
GRID_LENGTH = 600

tug_var = 0  # A += 1, L -= 1
TUG_LIMIT = 10   
right_lean_time = 0 
winner = None 
game_paused = False 
round_enabled = True
ROUND_DURATION = 5
round_time_left = ROUND_DURATION
round_running = True
left_max_stam = 100
right_max_stam = 100
left_stamina = left_max_stam
right_stamina = right_max_stam
stamina_cost = 12
revocery = 18
left_presses = 0
right_presses = 0
REPLAY_SECONDS = 6
REPLAY_FPS = 60
max_replay_frames = int(REPLAY_SECONDS * REPLAY_FPS)
replay_buffer = []
replay_mode= False
replay_index =0
replay_speed= 1
animation_start =None
ANIM_DURATION = 3
platform_fall_progress = 0
loser_fall_progress= 0
winner_jump_progress = 0
ANIMATION_DURATION = 2
left_lean_amount = 0
right_lean_amount =0
LEAN_MAX_ANGLE = 12
LEAN_RECOVERY_RATE = 40
left_lean_time = 0
right_lean_time = 0
LEAN_DURATION = 0.25 

referee_left_arm_angle =0
referee_right_arm_angle= 0
referee_wave_progress=0
referee_animation_type=None
referee_animation_start=None
REFEREE_ANIM_DURATION=2
bot_enabled = False
bot_difficulty = 0.6
last_bot_action = 0
recent_scores = []
timer = 0
time_ratio = 400
rand_var = 423
prev_time = None

def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
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

def draw_platform(x, z, width=220, depth=60, height=10, floor=0):
    glPushMatrix()
    glTranslatef(x, -floor, z)
    glScalef(width, depth, height)
    glutSolidCube(1)
    glPopMatrix()

def draw_player(x, z, color=(1, 0, 0), lean=0, falling=0, jumping=0, facing="right"):
    glPushMatrix()
    glTranslatef(x, -falling+jumping,z)
    if facing == "left":
        glRotatef(180, 0, 0, 1) 
    glRotatef(lean, 1, 0, 0)

    glColor3f(*color)
    for leg_x in (-8, 8):
        glPushMatrix()
        glTranslatef(leg_x, 0, 15)
        glRotatef(90, 1, 0, 0)
        gluCylinder(gluNewQuadric(), 4, 4,30, 10,10)
        glPopMatrix()
    for foot_x in (-8, 8):
        glPushMatrix()
        glTranslatef(foot_x, 8, 0)
        glScalef(8, 16, 6)
        glutSolidCube(1)
        glPopMatrix()
    glPushMatrix()
    glTranslatef(0, 0, 55)
    glScalef(20, 12, 30)
    glutSolidCube(1)
    glPopMatrix()
    arm_angle = 20
    for arm_x, side in [(-10, "left"), (10, "right")]:
        glPushMatrix()
        glTranslatef(arm_x, 0, 65)
        glRotatef(arm_angle if side == "left" else -arm_angle, 0, 0, 1)
        glRotatef(90, 0, 1, 0)
        gluCylinder(gluNewQuadric(), 3, 3, 25, 8, 8)
        glPopMatrix()
    for hand_x in (-28, 28):
        glPushMatrix()
        glTranslatef(hand_x, 0, 65)
        glutSolidSphere(5, 10, 10)
        glPopMatrix()
    glPushMatrix()
    glTranslatef(0, 0, 85)
    glutSolidSphere(10, 12, 12)
    glPopMatrix()
    glPopMatrix()

def draw_referee(x, z, winner=None, wave_progress=0):
    if winner == "left":
        left_arm_angle, right_arm_angle = 90, 0
    elif winner == "right":
        left_arm_angle, right_arm_angle = 0, 90
    elif winner == "tie":
        left_arm_angle = 30*math.sin(wave_progress * 2)
        right_arm_angle = 30 * math.sin(wave_progress * 2)
    else:
        left_arm_angle = right_arm_angle = 0
    glPushMatrix()
    base_h = 40
    glTranslatef(x, 0, z + base_h)
    for lx in (-8, 8):
        glPushMatrix()
        glTranslatef(lx, 0, 0)
        glRotatef(90, 1, 0, 0)
        gluCylinder(gluNewQuadric(), 4, 4, 40, 12, 12)
        glPopMatrix()
    for fx in (-8, 8):
        glPushMatrix()
        glTranslatef(fx, 8, -3)
        glScalef(8, 16, 6)
        glColor3f(0.2, 0.2, 0.2)
        glutSolidCube(1)
        glPopMatrix()
    glPushMatrix()
    glTranslatef(0, 0, 40)
    glScalef(22, 14, 50)
    glColor3f(1.0, 1.0, 0.0)
    glutSolidCube(1)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(-14, 0, 60)
    glRotatef(left_arm_angle + 45, 0, 0, 1)
    glRotatef(90, 0, 1, 0)
    glColor3f(1.0, 1.0, 0.0)
    gluCylinder(gluNewQuadric(), 3, 3, 35, 10, 10)
    glTranslatef(35, 0, 0)
    glColor3f(1.0, 1.0, 1.0)
    glutSolidSphere(5, 12, 12)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(14, 0, 60)
    glRotatef(-right_arm_angle - 45, 0, 0, 1)
    glRotatef(-90, 0, 1, 0)
    glColor3f(1.0, 1.0, 0.0)
    gluCylinder(gluNewQuadric(), 3, 3, 35, 10, 10)
    glTranslatef(35, 0, 0)
    glColor3f(1.0, 1.0, 1.0)
    glutSolidSphere(5, 12, 12)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(0, 0, 95)
    glColor3f(1.0, 1.0, 1.0)
    glutSolidSphere(10, 16, 16)
    glPopMatrix()
    glPopMatrix()

def draw_scoreboard(x, z, tug_val, left_stam, right_stam, left_p, right_p, round_time, winner_highlight=None):
    glPushMatrix()
    glTranslatef(x, 0, z)
    glColor3f(0.15, 0.15, 0.2)
    glPushMatrix()
    glTranslatef(0, 0, 120)
    glScalef(140, 8, 80)
    glutSolidCube(1)
    glPopMatrix()
    glColor3f(0.8, 0.8, 0.8)
    glPushMatrix()
    glTranslatef(0, 2, 120)
    glScalef(145, 6, 85)
    glutWireCube(1)
    glPopMatrix()
    glColor3f(0.3, 0.3, 0.35)
    glPushMatrix()
    glTranslatef(0, 0, 60)
    glScalef(6, 6, 110)
    glutSolidCube(1)
    glPopMatrix()
    
    if winner_highlight == 'left':
        glColor3f(1.0, 0.3, 0.3)
        glPushMatrix()
        glTranslatef(-35, 4, 135)
        glScalef(60, 4, 25)
        glutSolidCube(1)
        glPopMatrix()
    elif winner_highlight == 'right':
        glColor3f(0.3, 0.3, 1.0)
        glPushMatrix()
        glTranslatef(35, 4, 135)
        glScalef(60, 4, 25)
        glutSolidCube(1)
        glPopMatrix()
    elif winner_highlight == 'tie':
        glow = 0.5 + 0.3 * math.sin(timer * 6)
        glColor3f(glow, glow, 0.2)
        glPushMatrix()
        glTranslatef(0, 4, 135)
        glScalef(120, 4, 25)
        glutSolidCube(1)
        glPopMatrix()
    glColor3f(0.2, 0.2, 0.2)
    glPushMatrix()
    glTranslatef(0, 3, 95)
    glScalef(100, 4, 6)
    glutSolidCube(1)
    glPopMatrix()
    clamped= max(-TUG_LIMIT, min(TUG_LIMIT, tug_val))
    bar_fill =(clamped + TUG_LIMIT) / (2*TUG_LIMIT)
    fill_w = 100 *bar_fill
    fill_cx = -50 +fill_w/2
    glColor3f(0.8, 0.2, 0.2) if tug_val >= 0 else glColor3f(0.2, 0.3, 0.8)
    glPushMatrix()
    glTranslatef(fill_cx, 4, 95)
    glScalef(fill_w, 3, 5)
    glutSolidCube(1)
    glPopMatrix()
    glColor3f(0.9, 0.2, 0.2)
    glPushMatrix(); glTranslatef(-45, 3, 145); glScalef(6, 4, 6); glutSolidCube(1); glPopMatrix()
    glColor3f(0.2, 0.3, 0.9)
    glPushMatrix(); glTranslatef(45, 3, 145); glScalef(6, 4, 6); glutSolidCube(1); glPopMatrix()
    glColor3f(0.9, 0.9, 0.2)
    glPushMatrix(); glTranslatef(0, 3, 160); glScalef(20, 4, 6); glutSolidCube(1); glPopMatrix()

    glPopMatrix()

def draw_rope(z, tug_value):
    rope_line = 12
    rope_half = 260
    shift = tug_value * 12
    glColor3f(0.8, .8, 0.4)
    for i in range(rope_line):
        t = i / (rope_line - 1)
        x = -rope_half + t * (2 * rope_half)
        curve = -0.0009*((x - shift)**2)
        glPushMatrix()
        glTranslatef(x + shift, 12 + curve, z)
        glScalef(40, 6, 6)
        glRotatef(90, 0, 1, 0)
        glutSolidCube(1)
        glPopMatrix()
    glPushMatrix()
    glTranslatef(shift, 18, z)
    glScalef(18, 18, 6)
    glutSolidCube(1)
    glPopMatrix()

def cheering(tug_val):
    rows, cols = 3, 10
    left_center_x, right_center_x = -320, 320
    up_y = -100
    base_z = 120
    row_step = 22
    base_side_x = 24
    spacing_in = 8
    body = (10, 10, 16)
    head = 12
    up_down = 5
    colors = [(0.9, 0.2, 0.65),(0.1, 0.6, 1),(0.1, 0.9, 0.5),(1, 0.85, 0.1),(0.7, 0.5, 0.95)  ]
    def draw_person(color):
        glColor3f(*color)
        glPushMatrix()
        glScalef(body[0], body[1], body[2])
        glutSolidCube(1)
        glPopMatrix()
        glPushMatrix()
        glTranslatef(0, 0, 12)
        gluSphere(gluNewQuadric(), head, 10, 10)
        glPopMatrix()

    left_jump = 20 if tug_val < 0 else 0
    right_jump = 20 if tug_val > 0 else 0

    for side in (-1, +1):
        center_x = left_center_x if side < 0 else right_center_x
        jump = left_jump if side < 0 else right_jump
        for r in range(rows):
            side_x = base_side_x + r * spacing_in
            z_row = base_z + r * row_step
            start_x = center_x - ((cols - 1) * side_x) / 2
            for c in range(cols):
                phase = 0.28 *r + 0.2* c
                dz = jump * math.sin(up_down * timer / 423 + phase)
                x, y, z = start_x + c * side_x, up_y, (z_row + dz)
                glPushMatrix()
                glTranslatef(x, y, z)
                draw_person(colors[(r * cols + c) % 5])
                glPopMatrix()

def display(tug_val, left_stam, right_stam, left_p_cnt, right_p_cnt, x = True, anim_progress=0.0, left_lean=0, right_lean=0):
    fall_offset = anim_progress * 220 if animation_start else 0
    jump_offset = 0
    if animation_start is not None and winner is not None:
        jump_offset = abs(math.sin(winner_jump_progress * 3.0 * 2 * math.pi)) * 25.0
    glColor3f(0.7, 0.5, 0.2)
    draw_platform(-300, 0, floor=fall_offset if winner == 'L' else 0.0)
    draw_platform(300, 0, floor=fall_offset if winner == 'A' else 0.0)
    for xp in (-300, 300):
        glPushMatrix()
        leg_fall = fall_offset if (winner == 'L' and xp < 0) or (winner == 'A' and xp > 0) else 0.0
        glTranslatef(xp, -35 - leg_fall, 0)
        glScalef(40, 40, 70)
        glColor3f(0.4, 0.3, 0.25)
        glutSolidCube(1)
        glPopMatrix()
    left_fall  = loser_fall_progress * 150 if winner == 'A' else 0
    right_fall = loser_fall_progress * 150 if winner == 'L' else 0
    left_jump  = jump_offset if winner == 'L' else 0
    right_jump = jump_offset if winner == 'A' else 0

    draw_player(-320, 0, color=(1, 0.1, 0.1), lean=left_lean,  falling=left_fall,  jumping=left_jump,  facing="right")
    draw_player( 320, 0, color=(0.1, 0.3, 1.0), lean=right_lean, falling=right_fall, jumping=right_jump, facing="left")

    glPushMatrix()
    glTranslatef(0, -(fall_offset if winner else 0.0), 0)
    glColor3f(0.2, 0.2, 0.25)
    glScalef(80, 80, 12)
    glutSolidCube(1)
    glPopMatrix()
    draw_rope(0, tug_val)
    cheering(tug_val)
    if game_paused:
        if winner == 'L':
            draw_referee(0, -80, winner="left")
        elif winner == 'A':
            draw_referee(0, -80, winner="right")
        else:
            draw_referee(0, -80, winner="tie", wave_progress=anim_progress * 5.0)
    else:
        draw_referee(0, -80, winner=None)
    highlight = None
    if game_paused and winner == 'A':
        highlight = 'left'
    elif game_paused and winner == 'L':
        highlight = 'right'
    elif game_paused and winner is None:
        highlight = 'tie'

    draw_scoreboard(100, -80, tug_val, left_stam, right_stam,
                    left_p_cnt, right_p_cnt, round_time_left, highlight)


    for xp in (-260, 260):
        glPushMatrix()
        light_fall = fall_offset if (winner == 'L' and xp < 0) or (winner == 'A' and xp > 0) else 0.0
        glTranslatef(xp, 60 - light_fall, 20)
        glRotatef(-90, 1, 0, 0)
        glPushMatrix(); glScalef(3, 3, 100); glutSolidCube(1); glPopMatrix()
        glTranslatef(0, 0, 55); glutSolidSphere(8, 10, 10)
        glPopMatrix()

def update_referee_animation(dt):
    global referee_left_arm_angle, referee_right_arm_angle, referee_wave_progress
    global referee_animation_type, referee_animation_start
    if referee_animation_start is None:
        return
    elapsed = timer - referee_animation_start
    progress = min(1.0, elapsed / REFEREE_ANIM_DURATION)
    if referee_animation_type == 'left_win':
        referee_left_arm_angle  = 90.0 * progress
        referee_right_arm_angle = 0.0
    elif referee_animation_type == 'right_win':
        referee_right_arm_angle = 90.0 * progress
        referee_left_arm_angle  = 0.0
    elif referee_animation_type == 'tie':
        referee_wave_progress = progress
        referee_left_arm_angle  = 45.0 + 20.0 * math.sin(progress * 16 * math.pi)
        referee_right_arm_angle = 45.0 + 20.0 * math.sin(progress * 16 * math.pi + math.pi)
    if progress >= 1.0 and referee_animation_type == 'tie':
        referee_left_arm_angle = referee_right_arm_angle = referee_wave_progress = 0.0

def start_referee_animation(kind):
    global referee_animation_type, referee_animation_start
    global referee_left_arm_angle, referee_right_arm_angle, referee_wave_progress
    referee_animation_type = kind
    referee_animation_start = timer
    referee_left_arm_angle = referee_right_arm_angle = referee_wave_progress = 0.0

def reset_referee():
    global referee_left_arm_angle, referee_right_arm_angle, referee_wave_progress
    global referee_animation_type, referee_animation_start
    referee_left_arm_angle = referee_right_arm_angle = referee_wave_progress = 0.0
    referee_animation_type = None
    referee_animation_start = None

def keyboardListener(key, x, y):
    global fovY, tug_var, winner, game_paused, left_stamina, right_stamina
    global left_presses, right_presses, round_time_left, round_running, replay_mode
    global bot_enabled, animation_start, platform_fall_progress, replay_buffer
    global loser_fall_progress, winner_jump_progress
    global left_lean_amount, right_lean_amount, left_lean_time, right_lean_time
    global recent_scores
    if key == b'w':
        fovY += 1
    if key == b's':
        fovY -= 1

    if key in (b'r', b'R'):
        recent_scores.append({
            "time": timer,
            "winner": winner if winner in ('A', 'L') else ('T' if winner is None and game_paused else None),
            "tug_at_end": tug_var,
            "left_presses": left_presses,
            "right_presses": right_presses,
            "round_duration": ROUND_DURATION - max(0.0, round_time_left)})
        tug_var = 0
        winner = None
        game_paused = False
        round_time_left = ROUND_DURATION
        round_running = True
        left_stamina = left_max_stam
        right_stamina = right_max_stam
        left_presses = 0
        right_presses = 0
        animation_start = None
        platform_fall_progress = 0.0
        loser_fall_progress = 0.0
        winner_jump_progress = 0.0
        left_lean_amount = right_lean_amount = 0.0
        left_lean_time = right_lean_time = 0.0
        reset_referee()
        replay_buffer.clear()
        replay_mode = False
        return

    if key in (b'b', b'B'):
        bot_enabled = not bot_enabled
        return

    if key == b'p':
        if game_paused and len(replay_buffer) > 0:
            replay_mode = True
            return
    if key == b'a':
        if left_stamina >= stamina_cost:
            tug_var += 1
            left_stamina -= stamina_cost
            right_presses += 1
            right_lean_amount = LEAN_MAX_ANGLE
            right_lean_time = timer
        else:
            '''thinking of adding penalty of 1, for more clicks. I think 
            a future vaersion, I'll implement a game hardness option then add this'''
            pass

    if key == b'l':
        if right_stamina >= stamina_cost:
            tug_var -= 1
            right_stamina -= stamina_cost
            left_presses += 1
            left_lean_amount = LEAN_MAX_ANGLE
            left_lean_time = timer
    if tug_var > TUG_LIMIT * 3:
        tug_var = TUG_LIMIT * 3
    if tug_var < -TUG_LIMIT * 3:
        tug_var = -TUG_LIMIT * 3
        
    if tug_var > TUG_LIMIT:
        winner = 'A'
        game_paused = True
        animation_start = timer

    if tug_var < -TUG_LIMIT:
        winner = 'L'
        game_paused = True
        animation_start = timer

def specialKeyListener(key, x, y):
    global camera_pos
    x, y, a = camera_pos
    if key == GLUT_KEY_UP:
        y += 10
    if key == GLUT_KEY_DOWN:
        y -= 10
    if key == GLUT_KEY_LEFT:
        x -= 10
    if key == GLUT_KEY_RIGHT:
        x += 10
    camera_pos = (x, y, a)

def mouseListener(button, state, x, y):
    global camera_pos
    if button == GLUT_LEFT_BUTTON and state == GLUT_DOWN:
        camera_pos = (0, 500, 200)
    if button == GLUT_RIGHT_BUTTON and state == GLUT_DOWN:
        camera_pos = (100, 200, 50)
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

def idle():
    global prev_time, left_stamina, right_stamina, round_time_left, round_running
    global bot_enabled, last_bot_action, tug_var, right_presses, winner, game_paused
    global replay_buffer, replay_mode, animation_start, platform_fall_progress
    global loser_fall_progress, winner_jump_progress
    global left_lean_amount, right_lean_amount, left_lean_time, right_lean_time
    global timer, rand_var, right_lean_time
    rand_var += 2.5
    if rand_var%time_ratio== 0:
        timer +=1
        # print(timer)
    # print(tug_var)
    dt = (rand_var - timer) / 1000
    timer = rand_var

    if dt <= 0:
        glutPostRedisplay()
        return
    if not game_paused:
        left_stamina  = min(left_max_stam, left_stamina  + revocery*dt)
        right_stamina = min(right_max_stam, right_stamina + revocery *dt)

    now = timer
    if left_lean_amount  > 0 and now - left_lean_time  > LEAN_DURATION:
        left_lean_amount  = max(0, left_lean_amount  - LEAN_RECOVERY_RATE * dt)
    if right_lean_amount > 0 and now - right_lean_time > LEAN_DURATION:
        right_lean_amount = max(0, right_lean_amount - LEAN_RECOVERY_RATE * dt)
    if round_enabled and round_running and not game_paused and not replay_mode:
        round_time_left -= dt
        if round_time_left <= 0:
            round_running = False
            if tug_var > 0:
                winner = 'A'
            elif tug_var < 0:
                winner = 'L'
            else:
                winner = None 
            game_paused = True
            animation_start = timer

    if bot_enabled and not game_paused and not replay_mode:
        x = timer
        time_since = x-last_bot_action
        base_interval = 0.18 + (1 -bot_difficulty)*0.8 
        adapt =1 + max(0, min(1.0, tug_var / float(TUG_LIMIT)))
        interval = base_interval * (0.7 + 0.6*(1.0-adapt))
        interval *= (0.75 + 0.5 * random.random())
        if time_since >= interval:
            if right_stamina >= stamina_cost:
                tug_var -= 1
                right_stamina -= stamina_cost
                right_presses += 1
            if tug_var < -TUG_LIMIT:
                 winner = 'L'
                 game_paused = True
            last_bot_action = x

    if animation_start is not None:
        anim_elapsed = timer - animation_start
        platform_fall_progress = min(1.0, anim_elapsed / ANIM_DURATION)
        if winner is not None:
            winner_jump_progress = anim_elapsed
            if referee_animation_start is None:
                start_referee_animation('left_win' if winner == 'A' else 'right_win')
        else:
            if referee_animation_start is None:
                start_referee_animation('tie')
        loser_fall_progress = min(1.0, anim_elapsed / ANIMATION_DURATION)
        update_referee_animation(dt)
        if anim_elapsed >= ANIM_DURATION:
            animation_start = None
            loser_fall_progress = 0.0
            winner_jump_progress = 0.0

    if not replay_mode:
        replay_buffer.append({
            "t": timer,
            "tug": tug_var,
            "left_p": left_presses,
            "right_p": right_presses,
            "left_stam": left_stamina,
            "right_stam": right_stamina,
            "left_lean": left_lean_amount,
            "right_lean": right_lean_amount
        })
        if len(replay_buffer) > max_replay_frames:
            replay_buffer.pop(0)
    else:

        ri = globals().get('replay_index', 0)
        ri += int(replay_speed * (dt*REPLAY_FPS))
        if ri >= len(replay_buffer):
            ri = 0
            globals()['replay_mode'] = False
        globals()['replay_index'] = ri

    glutPostRedisplay()

def showScreen():
    global tug_var, winner, game_paused, left_stamina, right_stamina
    global left_presses, right_presses, round_time_left, round_running, bot_enabled
    global replay_mode, replay_index, replay_buffer, platform_fall_progress, animation_start
    global left_lean_amount, right_lean_amount, recent_scores

    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, 1000, 800)
    setupCamera()
    glBegin(GL_QUADS)
    glColor3f(0.12, 0.12, 0.12)
    glVertex3f(-GRID_LENGTH, -GRID_LENGTH, -1)
    glVertex3f( GRID_LENGTH, -GRID_LENGTH, -1)
    glVertex3f( GRID_LENGTH,  GRID_LENGTH, -1)
    glVertex3f(-GRID_LENGTH,  GRID_LENGTH, -1)
    glEnd()

    if replay_mode and replay_buffer:
        idx = min(len(replay_buffer) - 1, replay_index)
        snap = replay_buffer[idx]
        display(snap["tug"], snap["left_stam"], snap["right_stam"],
                        snap["left_p"], snap["right_p"], True, 0.0,
                        snap.get("left_lean", 0), snap.get("right_lean", 0))
    else:
        display(tug_var, left_stamina, right_stamina, left_presses, right_presses,
                        True, platform_fall_progress, left_lean_amount, right_lean_amount)


    draw_text(10, 770, f"TUG Value: {tug_var}")
    draw_text(10, 745, f"Left (A): presses={left_presses} stamina={int(left_stamina)}/{int(left_max_stam)}")
    draw_text(10, 720, f"Right (L): presses={right_presses} stamina={int(right_stamina)}/{int(right_max_stam)} {'(BOT)' if bot_enabled else ''}")
    draw_text(10, 690, "Press 'A' to pull left, 'L' to pull right. 'B' bot toggle. 'R' reset (and record score).")
    draw_text(10, 665, f"Round time left: {int(round_time_left)}s.")
    draw_text(10, 640, f"Referee: {referee_animation_type.replace('_',' ').title() if referee_animation_type else 'Ready'}")

    if winner is None and not replay_mode:
        bar_y = 50
        glColor3f(1, 1, 1)
        glBegin(GL_LINE_LOOP)
        glVertex2f(200,bar_y - 10)
        glVertex2f(800, bar_y- 10)
        glVertex2f(800, bar_y+10)
        glVertex2f(200,bar_y+10)
        glEnd()
        cljumped = max(-TUG_LIMIT, min(TUG_LIMIT, tug_var))
        portion = (cljumped + TUG_LIMIT) / (2 * TUG_LIMIT)
        filled_x = 200 + portion * (800 - 200)
        glBegin(GL_QUADS)
  
        if tug_var <= 0:
            glColor3f(0.9, 0.2, 0.2)
        else:
            glColor3f(0.2, 0.3, 0.9)
        glVertex2f(200, bar_y - 10)
        glVertex2f(filled_x, bar_y - 10)
        glVertex2f(filled_x, bar_y + 10)
        glVertex2f(200, bar_y + 10)
        glEnd()
    if game_paused and not replay_mode:
        if winner in ('A', 'L'):
            draw_text(350, 220, f"WINNER: {'LEFT (A)' if winner=='A' else 'RIGHT (L)'}")
        else:
            draw_text(420, 420, "ROUND TIED")
        draw_text(320, 360, "Press 'R' to record this result and start the next round.")

    y = 600
    draw_text(780, y, "Recent Wins:")
    y -= 20

    for s in list(reversed(recent_scores[-5:])):
        win = s.get("winner")
        if win is None: win = "-"
        draw_text(740, y, f"W:{win}  tug:{s.get('tug_at_end',0)}  Left pull:{s.get('left_presses',0)}  Right pull:{s.get('right_presses',0)}")
        y -= 20
    glutSwapBuffers()

def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(1000, 800)
    glutInitWindowPosition(0, 0)
    glutCreateWindow(b"TUG OF ROPE 3D")

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
