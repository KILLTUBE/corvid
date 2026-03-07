# taken from https://github.com/adamb70/Python-Spherical-Projection/blob/master/cube2equi.py
# rewritten with numpy for vectorized operations

import numpy as np

# Assign identifiers to the faces of the cube
FACE_Z_POS = 1  # Left
FACE_Z_NEG = 2  # Right
FACE_Y_POS = 3  # Top
FACE_Y_NEG = 4  # Bottom
FACE_X_NEG = 5  # Front
FACE_X_POS = 6  # Back

def find_corresponding_pixel(i, j, w, h, n):
    """
    :param i: X coordinate of output image pixel
    :param j: Y coordinate of output image pixel
    :param w: Width of output image
    :param h: Height of output image
    :param n: Height/Width of each square face
    :return: Pixel coordinates for the input image that a specified pixel in the output image maps to.
    """
    theta = 2.0 * i / w - 1.0
    phi = 2.0 * j / h - 1.0

    phi_rad = phi * (np.pi / 2)
    theta_rad = theta * np.pi

    # vector coordinates
    cos_phi = np.cos(phi_rad)
    x = cos_phi * np.cos(theta_rad)
    y = np.sin(phi_rad)
    z = cos_phi * np.sin(theta_rad)

    ax, ay, az = np.abs(x), np.abs(y), np.abs(z)
    largest = np.maximum(np.maximum(ax, ay), az)

    eps = 0.00001
    is_x = (largest - ax) < eps
    is_y = ~is_x & ((largest - ay) < eps)
    is_z = ~is_x & ~is_y

    face = np.where(is_x, np.where(x < 0, FACE_X_POS, FACE_X_NEG),
           np.where(is_y, np.where(y < 0, FACE_Y_POS, FACE_Y_NEG),
                          np.where(z < 0, FACE_Z_POS, FACE_Z_NEG)))

    # raw face coordinates (xc, yc, ma) per face
    xc = np.zeros_like(x)
    yc = np.zeros_like(x)
    ma = np.zeros_like(x)

    m = face == FACE_X_NEG
    xc = np.where(m, z, xc); yc = np.where(m, y, yc); ma = np.where(m, x, ma)
    m = face == FACE_X_POS
    xc = np.where(m, -z, xc); yc = np.where(m, y, yc); ma = np.where(m, x, ma)
    m = face == FACE_Y_NEG
    xc = np.where(m, z, xc); yc = np.where(m, -x, yc); ma = np.where(m, y, ma)
    m = face == FACE_Y_POS
    xc = np.where(m, z, xc); yc = np.where(m, x, yc); ma = np.where(m, y, ma)
    m = face == FACE_Z_POS
    xc = np.where(m, x, xc); yc = np.where(m, y, yc); ma = np.where(m, z, ma)
    m = face == FACE_Z_NEG
    xc = np.where(m, -x, xc); yc = np.where(m, y, yc); ma = np.where(m, z, ma)

    # raw coordinates on the face
    abs_ma = np.abs(ma)
    cube_x = (xc / abs_ma + 1.0) / 2.0
    cube_y = (yc / abs_ma + 1.0) / 2.0

    # face origin coordinates
    n_int = int(n)
    face_ox = np.zeros_like(face, dtype=np.int32)
    face_oy = np.zeros_like(face, dtype=np.int32)

    face_ox = np.where(face == FACE_X_NEG, n_int, face_ox)
    face_oy = np.where(face == FACE_X_NEG, n_int, face_oy)
    face_ox = np.where(face == FACE_X_POS, 3 * n_int, face_ox)
    face_oy = np.where(face == FACE_X_POS, n_int, face_oy)
    face_ox = np.where(face == FACE_Z_NEG, 2 * n_int, face_ox)
    face_oy = np.where(face == FACE_Z_NEG, n_int, face_oy)
    face_ox = np.where(face == FACE_Z_POS, 0, face_ox)
    face_oy = np.where(face == FACE_Z_POS, n_int, face_oy)
    face_ox = np.where(face == FACE_Y_POS, n_int, face_ox)
    face_oy = np.where(face == FACE_Y_POS, 0, face_oy)
    face_ox = np.where(face == FACE_Y_NEG, n_int, face_ox)
    face_oy = np.where(face == FACE_Y_NEG, 2 * n_int, face_oy)

    # normalized coordinates
    norm_x = np.floor(cube_x * n).astype(np.int32)
    norm_y = np.floor(cube_y * n).astype(np.int32)

    norm_x = np.clip(norm_x, 0, n_int - 1)
    norm_y = np.clip(norm_y, 0, n_int - 1)

    return face_ox + norm_x, face_oy + norm_y
