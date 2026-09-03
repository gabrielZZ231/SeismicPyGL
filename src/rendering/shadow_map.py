"""Shadow map direcional compacto: uma passagem de profundidade inteiramente na GPU."""

from OpenGL.GL import (
    glGenFramebuffers, glBindFramebuffer, glFramebufferTexture2D,
    glGenTextures, glBindTexture, glTexImage2D, glTexParameteri,
    glDrawBuffer, glReadBuffer, glViewport, glClear, glDeleteFramebuffers,
    glDeleteTextures, GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_TEXTURE_2D,
    GL_DEPTH_COMPONENT, GL_FLOAT, GL_NEAREST, GL_CLAMP_TO_BORDER,
    GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER, GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T, GL_NONE, GL_DEPTH_BUFFER_BIT,
)
try:
    from ..core.shader import ShaderProgram
except ImportError:
    from shader import ShaderProgram


class ShadowMap:
    def __init__(self, size=1024):
        self.size = size
        self.fbo = glGenFramebuffers(1)
        self.texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_DEPTH_COMPONENT, size, size, 0,
                     GL_DEPTH_COMPONENT, GL_FLOAT, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_BORDER)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_BORDER)

        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_TEXTURE_2D, self.texture, 0)
        glDrawBuffer(GL_NONE)
        glReadBuffer(GL_NONE)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        self.shader = ShaderProgram.from_files("assets/shaders/shadow.vert", "assets/shaders/shadow.frag")

    def begin(self, light_space_matrix):
        glViewport(0, 0, self.size, self.size)
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glClear(GL_DEPTH_BUFFER_BIT)
        self.shader.use()
        self.shader.set_uniform_mat4("u_light_space_matrix", light_space_matrix)

    def end(self, width, height):
        self.shader.stop()
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glViewport(0, 0, width, height)

    def cleanup(self):
        self.shader.cleanup()
        glDeleteFramebuffers(1, [self.fbo])
        glDeleteTextures([self.texture])
