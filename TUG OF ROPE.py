from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import math
import random

camera_pos = (0, 500, 300)
fovY = 120
GRID_LENGTH = 600
tug_var = 0           # A += 1, L -= 1
TUG_LIMIT = 10 
winner = None
game_paused = False 
round_enabled = True
ROUND_DURATION = 5.0
round_time_left = ROUND_DURATION
round_running = True
left_max_stam = 100.0
right_max_stam = 100.0
left_stamina = left_max_stam
right_stamina = right_max_stam
stamina_cost = 12.0 
recovery_rate = 18.0

left_presses = 0
right_presses = 0

bot_enabled = False
bot_difficulty = 0.6 
last_bot_action = 0.0

replay_mode = False
replay_index = 0
replay_speed = 1.0

animation_start = None
ANIM_DURATION = 3.0  
platform_fall_progress = 0.0
timer = 0
time_ratio = 400
rand_var = 423
tug_val = tug_var
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

def draw_player(x, z, color=(1, 0, 0), lean=0.0, falling=0.0):
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
def cheering(tug_val):
    rows, cols = 3, 10
    left_center_x, right_center_x = -320.0, 320.0 
    up_y = -100
    base_z = 120 
    row_height_step = 22
    base_side_x = 24
    spacing_in = 8
    body = (10, 10, 16)
    head = 12
    up_down = 5
    colors = [
        (0.9, 0.2, 0.65),
        (0.1, 0.6, 1),
        (0.1, 0.9, 0.5),
        (1, 0.85, 0.1),
        (0.7, 0.5, 0.95),
    ]
    def draw_person(color):
        glColor3f(*color)
        # body
        glPushMatrix()
        glScalef(body[0], body[1], body[2])
        glutSolidCube(1)
        glPopMatrix()
        glPushMatrix()
        glTranslatef(0.0, 0.0, 12)
        gluSphere(gluNewQuadric(), head, 10, 10)
        glPopMatrix()
    left_jump = 20 if tug_val< 0 else 0
    right_jump = 20 if tug_val > 0 else 0
    for side in (-1, +1):
        center_x = left_center_x if side < 0 else right_center_x
        jump = left_jump if side < 0 else right_jump
        for r in range(rows):
            side_x = base_side_x +r *spacing_in
            z_row = base_z+ r*row_height_step
            start_x =center_x- ((cols-1)*side_x)/2
            for c in range(cols):
                phase = 0.28 * r + 0.20 * c
                dz = jump *math.sin(up_down *timer/ 423 + phase)
                x, y, z = start_x+c*side_x, up_y, (z_row + dz)
                glPushMatrix()
                glTranslatef(x, y, z)
                draw_person(colors[(r*cols + c)%5])
                glPopMatrix()
def draw_rope(z, tug_value):
    rope_line = 12
    rope_half = 260
    shift = tug_value * 12 
    for i in range(rope_line):
        t = i / (rope_line - 1)
        x = -rope_half + t * (2 * rope_half)
        curve = -0.0009 * ((x-shift) ** 2) + 0.0
        glPushMatrix()
        glTranslatef(x + shift, 12+curve, z)
        glScalef(40, 6, 6)
        glRotatef(90, 0, 1, 0)
        glutSolidCube(1)
        glPopMatrix()
    glPushMatrix()
    glTranslatef(shift, 18, z)
    glScalef(18, 18, 6)
    glutSolidCube(1)
    glPopMatrix()

def keyboardListener(key, x, y):
    global fovY, tug_var, winner, game_paused, left_stamina, right_stamina
    global left_presses, right_presses, round_time_left, round_running, replay_mode
    global bot_enabled, animation_start, platform_fall_progress, replay_buffer

    if key == b'w':
        fovY += 1
    if key == b's':
        fovY -= 1

    if key == b'r':
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
        bot_enabled = False
        platform_fall_progress = 0.0
        replay_mode = False
        return

    if key == b'b':
        bot_enabled = not bot_enabled
        return

    if key == b'p':
        if game_paused and len(replay_buffer) > 0:
            replay_mode = True
            return
    if replay_mode:
        return
    
    if game_paused:
        return

    if key == b'a':
        if left_stamina >= stamina_cost:
            tug_var += 1
            left_stamina -= stamina_cost
            left_presses += 1
        else:
            '''thinking of adding penalty of 1, for more clicks. I think 
            a future vaersion, I'll implement a game hardness option then add this'''
            pass

    if key == b'l':
        if right_stamina >= stamina_cost:
            tug_var -= 1
            right_stamina -= stamina_cost
            right_presses += 1
        else:
            pass
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
    # # Left mouse button fires a bullet
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
    global timer, left_stamina, right_stamina, round_time_left, round_running
    global bot_enabled, last_bot_action, tug_var, right_presses, winner, game_paused
    global replay_buffer, replay_mode, animation_start, platform_fall_progress, tug_var, timer, rand_var
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
        left_stamina = min(left_max_stam, left_stamina + recovery_rate * dt)
        right_stamina = min(right_max_stam, right_stamina + recovery_rate * dt)

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
        interval = base_interval * (0.7 + 0.6 * (1.0 - adapt))
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

    glutPostRedisplay()

def showScreen():
    global rand_var, tug_var, winner, game_paused, left_stamina, right_stamina
    global left_presses, right_presses, round_time_left, round_running, bot_enabled
    global replay_mode, replay_index, replay_buffer, platform_fall_progress, animation_start
    global show_scores_list

    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, 1000, 800)
    setupCamera()

    #floor
    glBegin(GL_QUADS)
    glColor3f(0.12, 0.12, 0.12)
    glVertex3f(-GRID_LENGTH, -GRID_LENGTH, -1)
    glVertex3f(GRID_LENGTH, -GRID_LENGTH, -1)
    glVertex3f(GRID_LENGTH, GRID_LENGTH, -1)
    glVertex3f(-GRID_LENGTH, GRID_LENGTH, -1)
    glEnd()
    display(tug_var, 0)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, 1000, 0, 800)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    if winner is None and not replay_mode:
        bar_y = 50
        glColor3f(1, 1, 1)
        glBegin(GL_QUADS)
        glVertex2f(200, bar_y - 10)
        glVertex2f(800, bar_y - 10)
        glVertex2f(800, bar_y + 10)
        glVertex2f(200, bar_y + 10)
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
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    draw_text(10, 770, f"TUG Value: {tug_var}")
    draw_text(10, 745, f"Left (A): presses={left_presses} stamina={int(left_stamina)}/{int(left_max_stam)}")
    draw_text(10, 720, f"Right (L): presses={right_presses} stamina={int(right_stamina)}/{int(right_max_stam)} {'(BOT)' if bot_enabled else ''}")
    draw_text(10, 690, "Press 'A' to increase (+1), 'L' decrease (-1). Press 'B' to toggle bot. 'R' to reset.")
    draw_text(10, 665, f"Round time left: {int(round_time_left)}s. Round duration {int(ROUND_DURATION)}s.")

    if game_paused and not replay_mode:
        if winner:
            draw_text(350, 420, f"WINNER: {'LEFT (A)' if winner=='A' else 'RIGHT (L)'}", GLUT_BITMAP_HELVETICA_18)
            draw_text(360, 390, "Animation playing... Press 'P' to view replay after animation.")
        else:
            draw_text(420, 420, "ROUND TIED")
        draw_text(380, 360, "Press 'R' to play again.")
    
    glutSwapBuffers()

def display(tug_val, seen):
    global tug_var
    glColor3f(0.7, 0.5, 0.2)
    draw_platform(-300, 0, floor=(seen * 20) if winner=='L' else 0.0)
    draw_platform(300, 0, floor=(seen * 20) if winner=='A' else 0.0)
    for xp in (-300, 300):
        glPushMatrix()
        glTranslatef(xp, -35 - (0 if (winner == ('L' if xp<0 else 'A')) else 0.0), 0)
        glScalef(40, 40, 70)
        glColor3f(0.4, 0.3, 0.25)
        glutSolidCube(1)
        glPopMatrix()
    left_lean = min(25, tug_var * 2)
    right_lean = min(25, -tug_var * 2)
    left_fall = (seen * 20) if winner == 'L' else 0.0
    right_fall = (seen * 20) if winner == 'A' else 0.0

    draw_player(-320, 0, color=(1, 0.1, 0.1), lean=left_lean, falling=left_fall)
    draw_player(320, 0, color=(0.1, 0.3, 1.0), lean= -right_lean, falling=right_fall)

    glPushMatrix()
    glTranslatef(0, - ((seen * 20)  if winner else 0.0), 0)
    glColor3f(0.2, 0.2, 0.25)
    glScalef(80, 80, 12)
    glutSolidCube(1)
    glPopMatrix()

    if tug_val >= 0:
        glColor3f(0.95, 0.9, 0.6)
    else:
        glColor3f(0.8, 0.85, 0.95)
    draw_rope(0, tug_val)
    cheering(tug_val)


def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(1000, 800)
    glutInitWindowPosition(0, 0)
    wind = glutCreateWindow(b"TUG OF ROPE 3D")
    # glEnable(GL_DEPTH_TEST)
    glutDisplayFunc(showScreen)
    glutKeyboardFunc(keyboardListener)
    glutSpecialFunc(specialKeyListener)
    glutMouseFunc(mouseListener)
    glutIdleFunc(idle)

    glutMainLoop()

if __name__ == "__main__":
    main()
