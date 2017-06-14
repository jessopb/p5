#
# Part of p5py: A Python package based on Processing
# Copyright (C) 2017 Abhik Pal
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#

from collections import namedtuple
from ctypes import *

from pyglet.gl import *

from .. import core
from .. import sketch

from .shader import Shader
from .shader import ShaderProgram

__all__ = ['OpenGLRenderer', 'BaseRenderer']

sketch_attrs = sketch._attrs

#
# TODO (abhikpal, 2017-06-06);
#
# - Fill in the missing args for all methods (maybe after
#   OpenGLRenderer is done?)
#
class BaseRenderer:
    """Base abstraction layer for all renderers."""
    def __init__(self):
        raise NotImplementedError("Abstract")

    def initialize(self):
        """Initilization routine for the renderer."""
        raise NotImplementedError("Abstract")

    def check_support(self):
        """Check if the the system supports the current renderer.

        :returns: True if the renderer is supported.
        :rtype: bool

        :raises RuntimeError: if the renderer is not supported.
        """
        raise NotImplementedError("Abstract")

    def pre_render(self):
        """Run the pre-render routine(s).

        The pre_render is called before the renderer is used to draw
        anything in the current iteration of the draw*() loop. This
        method could, for instance:

        - reset the transformations for the viewport
        - clear the screen,
        - etc.
        """
        pass

    def render(self, shape):
        """Use the renderer to render the given shape.

        :param shape: The shape that needs to be rendered.
        :type shape: Shape
        """
        raise NotImplementedError("Abstract")

    def post_render(self):
        """Run the post-render routine(s).

        The post_render is called when we are done drawing things for
        the current iteration of the draw call. Any draw-loop specific
        cleanup steps should go here.
        """
        pass

    def clear(self):
        """Clear the screen."""
        raise NotImplementedError("Abstract")

    def cleanup(self):
        """Run the cleanup routine for the renderer.

        This is the FINAL cleanup routine for the renderer and would
        ideally be called when the program is about to exit.
        """
        pass

    def test_render(self):
        """Render the renderer's default test drawing.

        The render() methods requires a Shape object. In the absence
        of such an object/class the user should be able to check that
        the renderer is working by calling this method.
        """
        raise NotImplementedError("Abstract")

    def __repr__(self):
        print("{}( version: {} )".format(self.__class__.__name__, self.version))

    __str__ = __repr__


class OpenGLRenderer(BaseRenderer):
    """The main OpenGL renderer.

    :param sketch_attrs: The main dictionary containing all attributes
        for the sketch.
    :type sketch_attrs: dict
    """

    def __init__(self):
        #
        # TODO (abhikpal, 2017-06-06)
        #
        # - Do we want to initialize the renderer here or get the
        #   sketch to do it explicitly when it has everything else
        #   ready?
        #
        self.shader_program = ShaderProgram()

        self.geoms = {}

    def initialize(self):
        """Run the renderer initialization routine.

        For an OpenGL renderer this should setup the required buffers,
        compile the shaders, etc.
        """

        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LEQUAL)
        glViewport(0, 0, sketch_attrs['width'], sketch_attrs['height'])

        self._init_shaders()

    def _init_shaders(self):
        vertex_shader_source = """
            #version 130

            in vec3 position;

            void main()
            {
                gl_Position = vec4(position, 1.0);
            }
        """

        fragment_shader_source = """
            #version 130

            out vec4 outColor;
            uniform vec4 fill_color;

            void main()
            {
                gl_FragColor = fill_color;
            }
        """
        shaders = [
            Shader(vertex_shader_source, 'vertex'),
            Shader(fragment_shader_source, 'fragment'),
        ]

        for shader in shaders:
            shader.compile()
            shader.attach(self.shader_program)

        self.shader_program.link()
        self.shader_program.activate()

        self.shader_program.add_uniform('fill_color', glUniform4f)

    def _create_buffers(self, shape):
        """Create the required buffers for the given shape.

        :param shape: Create buffers for this shape.
        :type shape: Shape

        """

        #
        # TODO (abhikpal, 2017-06-10)
        #
        # - Ideally, this should be implemented by the Shape's
        #   __hash__ so that we can use the shape itself as the dict
        #   key and get rid of this str(__dict__(...) business.
        #
        # TODO (abhikpal, 2017-06-14)
        #
        # All of the buffer stuff needs refactoring.
        #
        shape_hash = str(shape.__dict__)
        if shape_hash in self.geoms:
            return shape_hash

        vertex_buffer = GLuint()
        glGenBuffers(1, pointer(vertex_buffer))

        index_buffer = GLuint()
        glGenBuffers(1, pointer(index_buffer))

        glBindBuffer(GL_ARRAY_BUFFER, vertex_buffer)

        vertices = [vi for vertex in shape.vertices for vi in vertex]
        vertices_typed =  (GLfloat * len(vertices))(*vertices)

        glBufferData(
            GL_ARRAY_BUFFER,
            sizeof(vertices_typed),
            vertices_typed,
            GL_STATIC_DRAW
        )

        elements = [idx for face in shape.faces for idx in face]
        elements_typed = (GLuint * len(elements))(*elements)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, index_buffer)
        glBufferData(
            GL_ELEMENT_ARRAY_BUFFER,
            sizeof(elements_typed),
            elements_typed,
            GL_STATIC_DRAW
        )

        position_attr = glGetAttribLocation(self.shader_program.pid, b"position")
        glEnableVertexAttribArray(position_attr)
        glVertexAttribPointer(position_attr, 3, GL_FLOAT, GL_FALSE, 0, 0)

        self.geoms[shape_hash] = {
            'vertex_buffer': vertex_buffer,
            'index_buffer': index_buffer,
            'num_elements': len(elements)
        }
        return shape_hash

    def _draw_buffers(self, shape_hash):
        glBindBuffer(GL_ARRAY_BUFFER, self.geoms[shape_hash]['vertex_buffer'])

        position_attr = glGetAttribLocation(self.shader_program.pid, b"position")
        glEnableVertexAttribArray(position_attr)
        glVertexAttribPointer(position_attr, 3, GL_FLOAT, GL_FALSE, 0, 0)


        if sketch_attrs['fill_enabled']:
            self.shader_program.set_uniform_data(
                'fill_color',
                *sketch_attrs['fill_color'].normalized
            )

            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.geoms[shape_hash]['index_buffer'])
            glDrawElements(
                GL_TRIANGLES,
                self.geoms[shape_hash]['num_elements'],
                GL_UNSIGNED_INT,
                0
            )

        #
        # TODO (abhikpal, 2017-06-08)
        #
        # Figure out a way to get stroke_width
        #

        if sketch_attrs['stroke_enabled']:
            self.shader_program.set_uniform_data(
                'fill_color',
                *sketch_attrs['stroke_color'].normalized
            )

            glDrawElements(
                GL_LINE_LOOP,
                self.geoms[shape_hash]['num_elements'],
                GL_UNSIGNED_INT,
                0
            )

    def render(self, shape):
        """Use the renderer to render a shape.

        :param shape: The shape to be rendered.
        :type shape: Shape

        """
        shape_hash = self._create_buffers(shape)
        self._draw_buffers(shape_hash)

    def clear(self):
        """Clear the screen."""
        glClearColor(*sketch_attrs['background_color'].normalized)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    def test_render(self):
        class Shape:
            def __init__(self):
                self.vertices = []
                self.faces = []

        class TestRect(Shape):
            def __init__(self, x, y, w, h):
                self.vertices = [
                    (x, y, 0),
                    (x + w, y, 0),
                    (x + w, y - h, 0),
                    (x, y - h, 0)
                ]
                self.faces = [(0, 1, 2), (2, 3, 0)]

            def __eq__(self, other):
                return self.__dict__ == other.__dict__

        lim = 16
        for i in range(-1*lim, lim):
            norm_i = (i + lim)/(lim * 2)

            r = TestRect(i/8, 0.95, 0.2, 0.6)
            core.fill(1 - norm_i, 0.1, norm_i)
            self.render(r)

            r = TestRect(i/8, 0.3, 0.2, 0.6)
            core.fill(0.1, norm_i, 1 - norm_i, 1.0)
            self.render(r)

            r = TestRect(i/8, -0.35, 0.2, 0.6)
            core.fill(norm_i, 1 - norm_i, 0.1, 1.0)

            self.render(r)