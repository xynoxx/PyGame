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
    col = mix(col, u_fog, fog);
    f_color = vec4(col * u_tint.rgb, u_tint.a);
}
"""

GROUND_VS = """
#version 330
uniform mat4 u_vp;
in vec2 in_pos;
out vec3 v_world;
void main() {
    v_world = vec3(in_pos.x, 0.0, in_pos.y);
    gl_Position = u_vp * vec4(v_world, 1.0);
}
"""

GROUND_FS = """
#version 330
// The ground, worked out for every pixel from where it is on the map: dead grass,
// bare dirt, puddles, burn marks, a rutted dirt track, and the concrete apron
// round the HQ. Nothing is a texture, so it's sharp at every zoom.
uniform vec3 u_light;
uniform vec3 u_eye;
uniform vec3 u_fog;
uniform vec2 u_fog_range;
uniform vec3 u_sky;
uniform float u_size;      // the map is u_size x u_size; outside it the ground fades
uniform vec4 u_apron;      // the concrete round the HQ: x0, z0, x1, z1
uniform vec4 u_hq;         // the HQ's own walls, to darken the ground at its foot
uniform vec4 u_mark;       // an outlined area (where an HQ would go), and its colour;
uniform vec4 u_mark_color; //   alpha 0 for none
in vec3 v_world;
out vec4 f_color;

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}
vec2 hash2(vec2 p) { return vec2(hash(p), hash(p + 17.17)); }

float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x),
               mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}

float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    mat2 m = mat2(1.6, 1.2, -1.2, 1.6);
    for (int k = 0; k < 5; k++) { v += a * noise(p); p = m * p; a *= 0.5; }
    return v;
}

// distance to the nearest cell wall of a Voronoi pattern: thin cracks where it's small
float cracks(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    float d1 = 8.0, d2 = 8.0;
    for (int y = -1; y <= 1; y++) for (int x = -1; x <= 1; x++) {
        vec2 g = vec2(x, y);
        float d = length(g + hash2(i + g) - f);
        if (d < d1) { d2 = d1; d1 = d; } else if (d < d2) { d2 = d; }
    }
    return d2 - d1;
}

// round scorch marks: a few cells in every hundred hold one
float scorch(vec2 p) {
    float cell = 11.0, mark = 0.0;
    vec2 i = floor(p / cell);
    for (int y = -1; y <= 1; y++) for (int x = -1; x <= 1; x++) {
        vec2 c = i + vec2(x, y);
        if (hash(c + 3.1) > 0.12) continue;
        vec2 centre = (c + 0.2 + 0.6 * hash2(c)) * cell;
        float r = 1.2 + 1.8 * hash(c + 9.7);
        float d = length(p - centre) + (fbm(p * 1.3) - 0.5) * 1.4;
        mark = max(mark, 1.0 - smoothstep(r * 0.35, r, d));
    }
    return mark;
}

float box_sdf(vec2 p, vec4 r) {
    vec2 c = (r.xy + r.zw) * 0.5, h = (r.zw - r.xy) * 0.5;
    vec2 q = abs(p - c) - h;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0);
}

// the dirt track: a gentle curve across the map, drawn to fit whatever size it is
float track_dist(vec2 p) {
    float u = p.x / u_size;
    float z = u_size * (0.72 + 0.13 * sin(u * 4.48 + 0.55) + 0.04 * sin(u * 12.2 + 2.0));
    float slope = 0.13 * 4.48 * cos(u * 4.48 + 0.55) + 0.04 * 12.2 * cos(u * 12.2 + 2.0);
    return abs(p.y - z) / sqrt(1.0 + slope * slope);
}

void main() {
    vec2 p = v_world.xz;
    float px = length(fwidth(p));                    // how much ground one pixel covers
    float fine = 1.0 - smoothstep(0.03, 0.12, px);   // fine detail fades out when zoomed out

    // ---- earth: dead grass over dirt
    float patches = fbm(p * 0.06);
    float clumps = fbm(p * 0.33 + 4.0);
    float grass = smoothstep(0.30, 0.50, patches + (clumps - 0.5) * 0.45);
    vec3 dirt = mix(vec3(0.30, 0.25, 0.19), vec3(0.40, 0.33, 0.25), fbm(p * 0.5 + 9.0));
    vec3 olive = mix(vec3(0.22, 0.25, 0.15), vec3(0.35, 0.35, 0.21), clumps);
    vec3 straw = vec3(0.50, 0.45, 0.30);
    vec3 turf = mix(olive, straw, smoothstep(0.55, 0.8, fbm(p * 0.11 + 21.0)) * 0.8);
    // tufts: soft light and dark grain at two sizes, and darker clumps
    float grain = 0.6 * noise(p * 7.0) + 0.4 * noise(p * 17.0 + 3.0);
    float tuft = smoothstep(0.55, 0.8, fbm(mat2(0.8, 0.6, -0.6, 0.8) * p * 1.6 + 13.0));
    turf *= 0.90 + 0.22 * (grain - 0.5) * fine - 0.10 * tuft;
    // dirt: fine grit, and a scatter of small pale stones
    float stone = smoothstep(0.88, 0.92, noise(mat2(0.8, -0.6, 0.6, 0.8) * p * 12.0 + 5.0)) * fine;
    dirt *= 0.94 + 0.14 * (noise(p * 11.0) - 0.5) * fine;
    dirt = mix(dirt, vec3(0.47, 0.44, 0.39), stone * 0.3);
    vec3 col = mix(dirt, turf, grass);

    // ---- the track: worn bare, two ruts
    float t = track_dist(p);
    float track = 1.0 - smoothstep(0.9, 1.6, t + (clumps - 0.5) * 0.6);
    float rut = 1.0 - smoothstep(0.08, 0.22, abs(t - 0.48));
    vec3 trackcol = mix(vec3(0.36, 0.30, 0.23), vec3(0.24, 0.20, 0.16), rut);
    col = mix(col, trackcol * (0.92 + 0.12 * noise(p * 5.0)), track);

    // ---- burn marks: black in the middle, brown at the rim
    float burn = scorch(p);
    vec3 ash = mix(vec3(0.17, 0.15, 0.13), vec3(0.36, 0.35, 0.33), smoothstep(0.6, 0.75, noise(p * 6.0)) * 0.5);
    col = mix(col, mix(vec3(0.26, 0.20, 0.15), ash, smoothstep(0.35, 0.9, burn)),
              smoothstep(0.05, 0.45, burn) * 0.85);

    // ---- the concrete apron round the HQ, its edge broken up
    float apron_d = box_sdf(p, u_apron) + (fbm(p * 0.9 + 3.0) - 0.5) * 1.3;
    float apron = 1.0 - smoothstep(-0.05, 0.05, apron_d);
    if (apron > 0.0) {
        vec3 conc = vec3(0.50, 0.49, 0.46) * (0.88 + 0.18 * fbm(p * 0.45 + 11.0));
        conc *= 0.94 + 0.10 * noise(p * 9.0) * fine;
        conc = mix(conc, vec3(0.20, 0.19, 0.18), smoothstep(0.62, 0.8, fbm(p * 0.7 + 5.0)) * 0.55);  // oil and soot
        vec2 slab = abs(fract(p * 0.5) - 0.5) * 2.0;                                    // seams every 2 m
        float seam = 1.0 - smoothstep(0.0, max(px * 1.5, 0.02), 1.0 - max(slab.x, slab.y));
        float crack = (1.0 - smoothstep(0.0, max(px, 0.015) * 2.0, cracks(p * 0.8)))
                    * smoothstep(0.45, 0.6, fbm(p * 0.35 + 30.0));
        conc *= 1.0 - 0.35 * seam - 0.45 * crack;
        float rim = smoothstep(-0.5, 0.0, apron_d);                                      // dirt washed onto the edge
        conc = mix(conc, dirt * 0.9, rim * 0.6);
        col = mix(col, conc, apron);
    }

    // ---- puddles in the low spots, off the concrete: they show the sky
    float wet = fbm(p * 0.09 + 50.0) - (1.0 - grass) * 0.05;
    float puddle = smoothstep(0.700, 0.708, wet) * (1.0 - apron);
    float mud = smoothstep(0.655, 0.700, wet) * (1.0 - apron);
    col = mix(col, col * vec3(0.68, 0.62, 0.56), mud);
    vec3 view = normalize(u_eye - v_world);
    float fres = pow(1.0 - max(view.y, 0.0), 2.0);
    float ripple = noise(p * 3.0 + 40.0);
    vec3 water = mix(vec3(0.21, 0.20, 0.18), u_sky * 1.35, 0.30 + 0.5 * fres + 0.12 * ripple);
    col = mix(col, water, puddle);

    // ---- light: the overcast sky and a weak, yellowed sun, on flat ground
    col *= 0.60 + vec3(0.50, 0.47, 0.40) * max(u_light.y, 0.0);
    float hq_d = box_sdf(p, u_hq);
    col *= 0.62 + 0.38 * smoothstep(0.0, 1.1, hq_d);   // the HQ's shade at its foot
    if (u_mark_color.a > 0.0) {                        // a lightly tinted area with a crisp outline
        float md = box_sdf(p, u_mark);
        float edge = 1.0 - smoothstep(0.05, 0.05 + max(px * 1.5, 0.02), abs(md));
        col = mix(col, u_mark_color.rgb, (edge * 0.9 + (md < 0.0 ? 0.18 : 0.0)) * u_mark_color.a);
    }
    float grey = dot(col, vec3(0.299, 0.587, 0.114));
    col = mix(vec3(grey), col, 0.82) * vec3(1.0, 0.99, 0.93);

    // ---- outside the map: darker and greyer, so the edge reads without a wall
    vec2 out2 = max(-p, p - u_size);
    float outside = smoothstep(0.0, 3.0, max(out2.x, out2.y));
    col = mix(col, vec3(grey) * 0.62, outside * 0.85);

    float d = distance(v_world, u_eye);
    float fog = clamp((d - u_fog_range.x) / (u_fog_range.y - u_fog_range.x), 0.0, 1.0);
    f_color = vec4(mix(col, u_fog, fog), 1.0);
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
        self.ground = ctx.program(vertex_shader=GROUND_VS, fragment_shader=GROUND_FS)
        self.ground_vao = None

        quad = ctx.buffer(array("f", [-1, -1, 1, -1, -1, 1, 1, 1]).tobytes())
        self.sky_vao = ctx.vertex_array(self.sky, [(quad, "2f", "in_pos")])
        self.overlay_vao = ctx.vertex_array(self.overlay, [(quad, "2f", "in_pos")])
        self.overlay_tex = ctx.texture(size, 4)
        self.overlay_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)

        _set(self.sky, "u_top", SKY_TOP)
        _set(self.sky, "u_bottom", SKY_HORIZON)
        _set(self.world, "u_light", SUN)
        _set(self.world, "u_fog", SKY_HORIZON)
        _set(self.ground, "u_light", SUN)
        _set(self.ground, "u_fog", SKY_HORIZON)
        _set(self.ground, "u_sky", SKY_TOP)
        ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

    def mesh(self, builder):
        return Mesh(self.ctx, self.world, builder)

    def set_ground(self, size, reach=400.0):
        """The ground: one big square reaching far past the map into the haze. The shader
        works out how it looks; this gives it the map's size."""
        lo, hi = -reach, size + reach
        quad = self.ctx.buffer(array("f", [lo, lo, hi, lo, lo, hi, hi, hi]).tobytes())
        self.ground_vao = self.ctx.vertex_array(self.ground, [(quad, "2f", "in_pos")])
        _set(self.ground, "u_size", float(size))
        self.set_hq_ground(None, None)
        self.set_mark(None)

    def set_hq_ground(self, apron, hq):
        """Where the HQ's concrete is, and its walls (to shade the ground at their foot). None: no HQ."""
        nowhere = (-1e4, -1e4, -1e4 + 1, -1e4 + 1)
        _set(self.ground, "u_apron", tuple(float(v) for v in (apron or nowhere)))
        _set(self.ground, "u_hq", tuple(float(v) for v in (hq or nowhere)))

    def set_mark(self, rect, color=(1.0, 1.0, 1.0), strength=1.0):
        """Outline an area of the ground in a colour (None: no outline)."""
        _set(self.ground, "u_mark", tuple(float(v) for v in (rect or (0, 0, 0, 0))))
        _set(self.ground, "u_mark_color", (*color, strength if rect else 0.0))

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
        for name, value in (("u_vp", mathx.to_bytes(view_proj)), ("u_eye", eye), ("u_fog_range", fog_range)):
            _set(self.ground, name, value)

    def draw_ground(self):
        if self.ground_vao:
            self.ground_vao.render(moderngl.TRIANGLE_STRIP)

    def draw(self, mesh, model=None, tint=(1.0, 1.0, 1.0, 1.0)):
        _set(self.world, "u_model", mathx.to_bytes(model or mathx.identity()))
        _set(self.world, "u_tint", tint)
        mesh.render()

    def draw_ghost(self, mesh, model, tint):
        """Draw a mesh see-through: first only into the depth buffer, so only its front-most
        faces show, then its colour over that."""
        ctx = self.ctx
        ctx.fbo.color_mask = (False, False, False, False)
        self.draw(mesh, model, tint)
        ctx.fbo.color_mask = (True, True, True, True)
        ctx.depth_func = "<="
        self.draw(mesh, model, tint)
        ctx.depth_func = "<"

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
