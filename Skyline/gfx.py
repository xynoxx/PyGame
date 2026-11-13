"""Drawing on the graphics card with ModernGL: shaders, meshes and the 2D overlay.

Pygame owns the window, the keyboard and mouse, and draws the 2D overlay
(text and panels). ModernGL draws the 3D world into the same window.
"""
import math
from array import array

import moderngl
import pygame

import mathx

WORLD_VS = """
#version 330
uniform mat4 u_vp;
uniform mat4 u_model;
in vec3 in_pos;
in vec3 in_normal;
in vec3 in_color;
out vec3 v_world;
out vec3 v_normal;
out vec3 v_color;
void main() {
    vec4 world = u_model * vec4(in_pos, 1.0);
    v_world = world.xyz;
    v_normal = mat3(u_model) * in_normal;
    v_color = in_color;
    gl_Position = u_vp * world;
}
"""

WORLD_FS = """
#version 330
uniform vec3 u_light;
uniform vec3 u_eye;
uniform vec3 u_fog;
uniform vec2 u_fog_range;
uniform vec4 u_tint;
uniform float u_grid;
in vec3 v_world;
in vec3 v_normal;
in vec3 v_color;
out vec4 f_color;
void main() {
    vec3 n = normalize(v_normal);
    float sun = max(dot(n, u_light), 0.0);
    float sky = 0.5 + 0.5 * n.y;
    // an overcast, hazy day: soft light from the sky, a weak, yellowed sun
    vec3 col = v_color * (0.36 + 0.24 * sky + vec3(0.50, 0.47, 0.40) * sun);
    float grey = dot(col, vec3(0.299, 0.587, 0.114));
    col = mix(vec3(grey), col, 0.82) * vec3(1.0, 0.99, 0.93);
    float d = distance(v_world, u_eye);
    float fog = clamp((d - u_fog_range.x) / (u_fog_range.y - u_fog_range.x), 0.0, 1.0);
    if (u_grid > 0.5 && n.y > 0.9) {
        // thin tile lines, about one pixel wide at any zoom
        vec2 w = max(fwidth(v_world.xz), vec2(1e-4));
        vec2 to_line = (0.5 - abs(fract(v_world.xz) - 0.5)) / w;
        float line = 1.0 - clamp(min(to_line.x, to_line.y) - 0.5, 0.0, 1.0);
        col *= 1.0 - 0.12 * line * (1.0 - fog);
    }
    col = mix(col, u_fog, fog);
    f_color = vec4(col * u_tint.rgb, u_tint.a);
}
"""

SCREEN_VS = """
#version 330
in vec2 in_pos;
out vec2 v_uv;
void main() {
    v_uv = in_pos * 0.5 + 0.5;
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

SKY_FS = """
#version 330
uniform vec3 u_top;
uniform vec3 u_bottom;
in vec2 v_uv;
out vec4 f_color;
void main() {
    f_color = vec4(mix(u_bottom, u_top, pow(v_uv.y, 0.8)), 1.0);
}
"""

OVERLAY_FS = """
#version 330
uniform sampler2D u_tex;
in vec2 v_uv;
out vec4 f_color;
void main() {
    f_color = texture(u_tex, v_uv);
}
"""

SKY_TOP = (0.25, 0.27, 0.27)       # heavy grey cloud
SKY_HORIZON = (0.56, 0.54, 0.46)   # smoke and dust haze
SUN = mathx.v_norm((0.45, 0.80, 0.30))


def open_window(size, title):
    """Open a pygame window with an OpenGL 3.3 context (with anti-aliasing if we can)."""
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
    pygame.display.set_caption(title)
    flags = pygame.OPENGL | pygame.DOUBLEBUF
    for samples in (4, 0):
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS, 1 if samples else 0)
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES, samples)
        try:
            return pygame.display.set_mode(size, flags, vsync=1)
        except pygame.error:
            try:
                return pygame.display.set_mode(size, flags)
            except pygame.error:
                if not samples:
                    raise
    raise RuntimeError("could not open an OpenGL window")


class MeshBuilder:
    """Collects triangles (position, normal, colour per vertex) for one mesh."""

    def __init__(self):
        self.data = array("f")

    def vertex(self, p, n, c):
        self.data.extend((p[0], p[1], p[2], n[0], n[1], n[2], c[0], c[1], c[2]))

    def tri(self, a, b, c, color, outward=None):
        """A flat triangle. `outward` is a rough direction its face should point."""
        n = mathx.v_norm(mathx.v_cross(mathx.v_sub(b, a), mathx.v_sub(c, a)))
        if outward is not None and mathx.v_dot(n, outward) < 0:
            n = (-n[0], -n[1], -n[2])
        for p in (a, b, c):
            self.vertex(p, n, color)

    def quad(self, a, b, c, d, normal, color):
        """Four corners in order. `color` is one colour or a colour per corner."""
        cols = color if isinstance(color[0], (tuple, list)) else (color,) * 4
        for p, col in ((a, cols[0]), (b, cols[1]), (c, cols[2]),
                       (a, cols[0]), (c, cols[2]), (d, cols[3])):
            self.vertex(p, normal, col)

    def box(self, x, y, z, w, h, d, color, yaw=0.0, top=None, bottom=False):
        """A box standing on (x, y, z): w wide (x), h tall, d deep (z), turned by yaw."""
        c, s = math.cos(yaw), math.sin(yaw)
        hw, hd = w / 2, d / 2

        def P(lx, ly, lz):
            return (x + lx * c + lz * s, y + ly, z - lx * s + lz * c)

        def N(nx, nz):
            return (nx * c + nz * s, 0.0, -nx * s + nz * c)

        self.quad(P(-hw, h, -hd), P(hw, h, -hd), P(hw, h, hd), P(-hw, h, hd), (0, 1, 0), top or color)
        if bottom:
            self.quad(P(-hw, 0, -hd), P(-hw, 0, hd), P(hw, 0, hd), P(hw, 0, -hd), (0, -1, 0), color)
        self.quad(P(hw, 0, -hd), P(hw, h, -hd), P(hw, h, hd), P(hw, 0, hd), N(1, 0), color)
        self.quad(P(-hw, 0, -hd), P(-hw, 0, hd), P(-hw, h, hd), P(-hw, h, -hd), N(-1, 0), color)
        self.quad(P(-hw, 0, hd), P(hw, 0, hd), P(hw, h, hd), P(-hw, h, hd), N(0, 1), color)
        self.quad(P(-hw, 0, -hd), P(-hw, h, -hd), P(hw, h, -hd), P(hw, 0, -hd), N(0, -1), color)

    def cone(self, x, y, z, radius, height, color, sides=7, yaw=0.0):
        """A low-poly cone with its base at height y. A negative height points it down."""
        apex = (x, y + height, z)
        ring = [(x + radius * math.cos(yaw + k * 2 * math.pi / sides), y,
                 z + radius * math.sin(yaw + k * 2 * math.pi / sides)) for k in range(sides)]
        for k in range(sides):
            a, b = ring[k], ring[(k + 1) % sides]
            outward = ((a[0] + b[0]) / 2 - x, 0.0, (a[2] + b[2]) / 2 - z)
            self.tri(a, b, apex, color, outward)

    def ring(self, x, y, z, r_in, r_out, color, segments=40):
        """A flat ring lying on the ground."""
        for k in range(segments):
            a0 = k * 2 * math.pi / segments
            a1 = (k + 1) * 2 * math.pi / segments
            self.quad((x + r_in * math.cos(a0), y, z + r_in * math.sin(a0)),
                      (x + r_out * math.cos(a0), y, z + r_out * math.sin(a0)),
                      (x + r_out * math.cos(a1), y, z + r_out * math.sin(a1)),
                      (x + r_in * math.cos(a1), y, z + r_in * math.sin(a1)),
                      (0, 1, 0), color)

    def disc(self, x, y, z, radius, color, segments=32):
        """A flat filled circle lying on the ground."""
        for k in range(segments):
            a0 = k * 2 * math.pi / segments
            a1 = (k + 1) * 2 * math.pi / segments
            for p in ((x, y, z),
                      (x + radius * math.cos(a0), y, z + radius * math.sin(a0)),
                      (x + radius * math.cos(a1), y, z + radius * math.sin(a1))):
                self.vertex(p, (0, 1, 0), color)


class Mesh:
    """A MeshBuilder's triangles, uploaded to the graphics card."""

    def __init__(self, ctx, program, builder):
        self.vbo = ctx.buffer(builder.data.tobytes())
        self.vao = ctx.vertex_array(program, [(self.vbo, "3f 3f 3f", "in_pos", "in_normal", "in_color")])

    def render(self):
        self.vao.render(moderngl.TRIANGLES)


def _set(program, name, value):
    """Set a shader uniform, skipping ones the shader compiler optimised away."""
    try:
        uniform = program[name]
    except KeyError:
        return
    if isinstance(value, bytes):
        uniform.write(value)
    else:
        uniform.value = value


class Renderer:
    """Owns the shaders and draws meshes, the sky and the overlay."""

    def __init__(self, ctx, size):
        self.ctx = ctx
        self.size = size
        self.world = ctx.program(vertex_shader=WORLD_VS, fragment_shader=WORLD_FS)
        self.sky = ctx.program(vertex_shader=SCREEN_VS, fragment_shader=SKY_FS)
        self.overlay = ctx.program(vertex_shader=SCREEN_VS, fragment_shader=OVERLAY_FS)

        quad = ctx.buffer(array("f", [-1, -1, 1, -1, -1, 1, 1, 1]).tobytes())
        self.sky_vao = ctx.vertex_array(self.sky, [(quad, "2f", "in_pos")])
        self.overlay_vao = ctx.vertex_array(self.overlay, [(quad, "2f", "in_pos")])
        self.overlay_tex = ctx.texture(size, 4)
        self.overlay_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)

        _set(self.sky, "u_top", SKY_TOP)
        _set(self.sky, "u_bottom", SKY_HORIZON)
        _set(self.world, "u_light", SUN)
        _set(self.world, "u_fog", SKY_HORIZON)
        ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

    def mesh(self, builder):
        return Mesh(self.ctx, self.world, builder)

    def begin(self, view_proj, eye, fog_range):
        """Clear the screen, paint the sky and set up the camera for this frame."""
        ctx = self.ctx
        ctx.viewport = (0, 0, *self.size)
        ctx.clear(*SKY_HORIZON, depth=1.0)
        ctx.disable(moderngl.DEPTH_TEST | moderngl.BLEND)
        self.sky_vao.render(moderngl.TRIANGLE_STRIP)
        ctx.enable(moderngl.DEPTH_TEST | moderngl.BLEND)
        _set(self.world, "u_vp", mathx.to_bytes(view_proj))
        _set(self.world, "u_eye", eye)
        _set(self.world, "u_fog_range", fog_range)

    def draw(self, mesh, model=None, tint=(1.0, 1.0, 1.0, 1.0), grid=False):
        _set(self.world, "u_model", mathx.to_bytes(model or mathx.identity()))
        _set(self.world, "u_tint", tint)
        _set(self.world, "u_grid", 1.0 if grid else 0.0)
        mesh.render()

    def upload_overlay(self, surface):
        """Send a pygame surface (same size as the window, with alpha) to be drawn on top."""
        self.overlay_tex.write(pygame.image.tobytes(surface, "RGBA", True))

    def draw_overlay(self):
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.ctx.enable(moderngl.BLEND)
        self.overlay_tex.use(0)
        _set(self.overlay, "u_tex", 0)
        self.overlay_vao.render(moderngl.TRIANGLE_STRIP)

    def read_pixels(self):
        """The finished frame as a pygame surface (for screenshots)."""
        data = self.ctx.screen.read(viewport=(0, 0, *self.size), components=3)
        return pygame.image.frombytes(data, self.size, "RGB", True)
