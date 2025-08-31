# Sarika.py
# CSE423 - Tug of Rope (Sarika's version)
# Features:
# - 3D arena/camera
# - Two players with lean feedback
# - Referee character at center
# - Rope that shifts with tug_var
# - Scoreboard (on-screen text)
# - Win/Lose animations + reset
#
# Controls:
#   Left Player:  A (pull) / D (relax)
#   Right Player: J (pull) / L (relax)
#   R: Reset round
#   Esc: Quit

from math import sin, cos, radians
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import sys
import time

# ---------- Globals ----------
win_w, win_h = 1000, 700
camera_dist = 32.0
camera_pitch = 22.0
camera_yaw = 25.0

# Tug state
tug_var = 0.0          # negative -> right winning, positive -> left winning
TUG_STEP = 0.25        # how much each key press influences tug
TUG_MAX = 10.0         # threshold to win

# Lean feedback
left_lean = 0.0
right_lean = 0.0
LEAN_MAX_DEG = 22.0

# Animation / round state
round_over = False
winner = None          # "LEFT" or "RIGHT"
win_anim_t = 0.0

# Score
left_score = 0
right_score = 0

# Timing
_last_time = None

# ---------- Utility ----------
def set_3d_camera():
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    aspect = max(1.0, win_w / float(max(1, win_h)))
    gluPerspective(60.0, aspect, 1.0, 1000.0)

    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    # Position the camera using spherical coords from pitch/yaw
    pitch = radians(camera_pitch)
    yaw = radians(camera_yaw)
    cx = camera_dist * cos(pitch) * cos(yaw)
    cy = camera_dist * sin(pitch)
    cz = camera_dist * cos(pitch) * sin(yaw)
    gluLookAt(cx, cy, cz, 0, 0, 0, 0, 1, 0)

def draw_text_2d(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
    # Simple 2D overlay text
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, win_w, 0, win_h)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glDisable(GL_LIGHTING)
    glColor3f(1, 1, 1)
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))
    glEnable(GL_LIGHTING)

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def draw_cube(w=1, h=1, d=1):
    # Centered cube scaled to w,h,d
    glPushMatrix()
    glScalef(w, h, d)
    glutSolidCube(1.0)
    glPopMatrix()

def draw_cylinder(radius=0.5, height=1.0, slices=24, stacks=1):
    quad = gluNewQuadric()
    gluCylinder(quad, radius, radius, height, slices, stacks)
    # End caps
    glPushMatrix()
    gluDisk(quad, 0, radius, slices, 1)
    glTranslatef(0, 0, height)
    gluDisk(quad, 0, radius, slices, 1)
    glPopMatrix()
    gluDeleteQuadric(quad)

def draw_arena():
    # Ground
    glDisable(GL_LIGHTING)
    glBegin(GL_QUADS)
    glColor3f(0.12, 0.14, 0.18)
    glVertex3f(-30, -2, -30)
    glVertex3f( 30, -2, -30)
    glVertex3f( 30, -2,  30)
    glVertex3f(-30, -2,  30)
    glEnd()
    glEnable(GL_LIGHTING)

    # Midline
    glDisable(GL_LIGHTING)
    glLineWidth(3)
    glColor3f(1, 1, 1)
    glBegin(GL_LINES)
    glVertex3f(0, -1.99, -20)
    glVertex3f(0, -1.99,  20)
    glEnd()
    glEnable(GL_LIGHTING)

def draw_player(side="LEFT", lean_deg=0.0):
    # Simple stick-ish figure using cubes/sphere
    # "side" -> position at x = -10 (LEFT) or x = +10 (RIGHT)
    base_x = -10 if side == "LEFT" else 10
    face_color = (1.0, 0.85, 0.7)
    shirt_color = (0.2, 0.6, 1.0) if side == "LEFT" else (1.0, 0.4, 0.3)
    pant_color = (0.1, 0.1, 0.1)

    glPushMatrix()
    glTranslatef(base_x, -2, 0)
    glRotatef(-lean_deg if side == "LEFT" else lean_deg, 0, 0, 1)

    # Torso
    glPushMatrix()
    glTranslatef(0, 3, 0)
    glMaterialfv(GL_FRONT_AND_BACK, GL_DIFFUSE, (*shirt_color, 1))
    draw_cube(2.0, 3.0, 1.2)
    glPopMatrix()

    # Head
    glPushMatrix()
    glTranslatef(0, 5, 0)
    glMaterialfv(GL_FRONT_AND_BACK, GL_DIFFUSE, (*face_color, 1))
    glutSolidSphere(0.9, 24, 18)
    glPopMatrix()

    # Legs
    glPushMatrix()
    glTranslatef(-0.5, 1.5, 0)
    glMaterialfv(GL_FRONT_AND_BACK, GL_DIFFUSE, (*pant_color, 1))
    draw_cube(0.6, 2.5, 0.8)
    glTranslatef(1.0, 0, 0)
    draw_cube(0.6, 2.5, 0.8)
    glPopMatrix()

    # Arms (simple cylinders pointing to rope direction)
    glPushMatrix()
    glTranslatef(0, 3.9, 0.7)
    glRotatef(90, 1, 0, 0)
    draw_cylinder(0.2, 1.5)
    glPopMatrix()

    glPushMatrix()
    glTranslatef(0, 3.9, -0.7)
    glRotatef(90, 1, 0, 0)
    draw_cylinder(0.2, 1.5)
    glPopMatrix()

    glPopMatrix()

def draw_rope():
    # The rope center shifts with tug_var along X
    glPushMatrix()
    glTranslatef(tug_var, 0.5, 0)   # height slightly above ground
    glMaterialfv(GL_FRONT_AND_BACK, GL_DIFFUSE, (0.8, 0.7, 0.5, 1))
    draw_cube(22.0, 0.4, 0.5)

    # Center flag on rope (to visualize midpoint)
    glTranslatef(0, 0.5, 0)
    glMaterialfv(GL_FRONT_AND_BACK, GL_DIFFUSE, (1, 0.2, 0.2, 1))
    draw_cube(0.3, 1.6, 0.1)
    glPopMatrix()

def draw_referee():
    # Simple ref at origin reacting to winner (arms up/down animation)
    glPushMatrix()
    glTranslatef(0, -2, -4)
    arm_raise = 0.0
    if round_over:
        arm_raise = 40.0 if winner == "LEFT" else -40.0

    # Body
    glTranslatef(0, 3, 0)
    glMaterialfv(GL_FRONT_AND_BACK, GL_DIFFUSE, (0.2, 0.2, 0.2, 1))
    draw_cube(1.5, 2.0, 1.2)

    # Head
    glPushMatrix()
    glTranslatef(0, 1.8, 0)
    glMaterialfv(GL_FRONT_AND_BACK, GL_DIFFUSE, (0.95, 0.85, 0.7, 1))
    glutSolidSphere(0.6, 24, 18)
    glPopMatrix()

    # Arms
    glPushMatrix()
    glTranslatef(-1.0, 0.8, 0)
    glRotatef(arm_raise, 0, 0, 1)
    draw_cylinder(0.18, 1.2)
    glPopMatrix()

    glPushMatrix()
    glTranslatef(1.0, 0.8, 0)
    glRotatef(-arm_raise, 0, 0, 1)
    draw_cylinder(0.18, 1.2)
    glPopMatrix()

    glPopMatrix()

def draw_scoreboard():
    # Top-left text HUD
    y = win_h - 30
    draw_text_2d(20, y,      f"Left Score: {left_score}")
    draw_text_2d(20, y - 24, f"Right Score: {right_score}")
    draw_text_2d(20, y - 48, f"Tug: {tug_var:+.2f}  (win at ±{TUG_MAX})")
    if round_over:
        msg = f"{winner} WINS! Press R to reset"
        # Blink the message
        if int(time.time() * 2) % 2 == 0:
            draw_text_2d(win_w//2 - 120, win_h - 30, msg)

def update_lean(dt):
    global left_lean, right_lean
    # Lean proportional to tug_var (limited)
    target_left = max(0.0, min(LEAN_MAX_DEG, 1.6 * tug_var))
    target_right = max(0.0, min(LEAN_MAX_DEG, 1.6 * -tug_var))

    # Smooth approach
    k = 8.0
    left_lean += (target_left - left_lean) * min(1.0, k * dt)
    right_lean += (target_right - right_lean) * min(1.0, k * dt)

def check_win():
    global round_over, winner, left_score, right_score, win_anim_t
    if round_over:
        return
    if tug_var >= TUG_MAX:
        round_over = True
        winner = "LEFT"
        left_score += 1
        win_anim_t = 0.0
    elif tug_var <= -TUG_MAX:
        round_over = True
        winner = "RIGHT"
        right_score += 1
        win_anim_t = 0.0

def update_win_anim(dt):
    global win_anim_t
    if round_over:
        win_anim_t += dt

def display():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    set_3d_camera()

    # Basic lighting
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glLightfv(GL_LIGHT0, GL_POSITION, (10, 20, 10, 1))
    glLightfv(GL_LIGHT0, GL_DIFFUSE,  (1, 1, 1, 1))
    glLightfv(GL_LIGHT0, GL_SPECULAR, (0.6, 0.6, 0.6, 1))
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

    draw_arena()
    draw_rope()
    draw_referee()

    # Winning bounce for the winner
    bounce = 0.0
    if round_over:
        bounce = 0.4 * sin(6 * win_anim_t)

    glPushMatrix()
    glTranslatef(0, bounce if winner == "LEFT" else 0, 0)
    draw_player("LEFT", lean_deg=left_lean)
    glPopMatrix()

    glPushMatrix()
    glTranslatef(0, bounce if winner == "RIGHT" else 0, 0)
    draw_player("RIGHT", lean_deg=right_lean)
    glPopMatrix()

    # HUD (drawn after 3D so always on top)
    draw_scoreboard()

    glutSwapBuffers()

def reshape(w, h):
    global win_w, win_h
    win_w, win_h = max(1, w), max(1, h)
    glViewport(0, 0, win_w, win_h)

def idle():
    global _last_time
    now = time.time()
    if _last_time is None:
        _last_time = now
    dt = now - _last_time
    _last_time = now

    update_lean(dt)
    check_win()
    update_win_anim(dt)

    glutPostRedisplay()

def keyboard(key, x, y):
    global tug_var
    k = key.decode("utf-8").lower() if isinstance(key, bytes) else key.lower()
    if k == '\x1b':  # ESC
        sys.exit(0)
    if round_over:
        if k == 'r':
            do_reset()
        return

    if k == 'a':      # left pulls
        tug_var = min(TUG_MAX, tug_var + TUG_STEP)
    elif k == 'd':    # left relax
        tug_var = max(-TUG_MAX, tug_var - 0.15*TUG_STEP)
    elif k == 'j':    # right pulls
        tug_var = max(-TUG_MAX, tug_var - TUG_STEP)
    elif k == 'l':    # right relax
        tug_var = min(TUG_MAX, tug_var + 0.15*TUG_STEP)
    elif k == 'r':
        do_reset()

def do_reset():
    global tug_var, left_lean, right_lean, round_over, winner, win_anim_t
    tug_var = 0.0
    left_lean = 0.0
    right_lean = 0.0
    round_over = False
    winner = None
    win_anim_t = 0.0

def init_gl():
    glEnable(GL_DEPTH_TEST)
    glClearColor(0.08, 0.09, 0.1, 1.0)
    glShadeModel(GL_SMOOTH)

def main():
    glutInit(sys.argv)
    # Double buffer + depth
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(win_w, win_h)
    glutCreateWindow(b"Tug of Rope - Sarika.py")

    init_gl()

    glutDisplayFunc(display)
    glutReshapeFunc(reshape)
    glutIdleFunc(idle)
    glutKeyboardFunc(keyboard)

    glutMainLoop()

if __name__ == "__main__":
    main()
