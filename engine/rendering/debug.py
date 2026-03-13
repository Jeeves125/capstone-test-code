import numpy as np
import moderngl, os
from ..constants.constants import CTX, SHADERS_PATH
from .camera import create_view_matrix, create_projection_matrix

class DebugDraw:
  __points: list[tuple[float, float, float, float, float, float]] = []
  __lines: list[tuple[float, float, float, float, float, float]] = []
  __debug_program = None
  __point_buf = None
  __point_vao = None
  
  uses_distance_based = False
  
  def get_program():
    return DebugDraw.__debug_program
  
  def setup():
    if DebugDraw.__debug_program is not None:
      return

    with open(os.path.join(SHADERS_PATH, 'debug_vert_shader.vert'), 'r') as f:
      vert_shader_src = f.read()

    with open(os.path.join(SHADERS_PATH, 'debug_frag_shader.frag'), 'r') as f:
      frag_shader_src = f.read()
      
    DebugDraw.__debug_program = CTX.program(vertex_shader=vert_shader_src, fragment_shader=frag_shader_src)
    # DebugDraw.__debug_program.ctx.point_size = 5.0
    # DebugDraw.__debug_program.ctx.line_width = 2.0
    CTX.point_size = 10.0
    CTX.line_width = 10.0
    
    CTX.enable(moderngl.PROGRAM_POINT_SIZE)
  
  def set_point_size(size: float):
    CTX.point_size = size
    
  def set_line_width(width: float):
    CTX.line_width = width

  def add_point(point: tuple[float, float, float], color: tuple[float, float, float]):
    DebugDraw.__points.append((*point, *color))
    
  def add_point_cloud(points: list[tuple[float, float, float]]):
    for point in points:
      DebugDraw.__points.append((*point, (1,1,1)))

  def add_line(start: tuple[float, float, float], start_color: tuple[float, float, float], end: tuple[float, float, float], end_color: tuple[float, float, float]):
    DebugDraw.__lines.append((*start, *start_color))
    DebugDraw.__lines.append((*end, *end_color))

  def clear():
    DebugDraw.__points.clear()
    DebugDraw.__lines.clear()
    
  def draw_point_vao(point_vao: moderngl.VertexArray):
    CTX.disable(moderngl.DEPTH_TEST)  # Disable depth test
    
    DebugDraw.__debug_program['view'].write(create_view_matrix().tobytes())
    DebugDraw.__debug_program['projection'].write(create_projection_matrix().tobytes())
    DebugDraw.__debug_program['use_distance_based'].value = True if DebugDraw.uses_distance_based else False
    
    point_vao.render(moderngl.POINTS)
      
    CTX.enable(moderngl.DEPTH_TEST)  # Re-enable depth test
    
  def draw_all(clear_points=True, clear_lines=True):
    # Create vaos
    if len(DebugDraw.__points) == 0 and len(DebugDraw.__lines) == 0:
      return
    
    CTX.disable(moderngl.DEPTH_TEST)  # Disable depth test

    DebugDraw.__debug_program['view'].write(create_view_matrix().tobytes())
    DebugDraw.__debug_program['projection'].write(create_projection_matrix().tobytes())
    DebugDraw.__debug_program['use_distance_based'].value = True if DebugDraw.uses_distance_based else False
    
    if len(DebugDraw.__points) > 0:
      if (DebugDraw.__point_buf == None or clear_points):
        DebugDraw.__point_buf = CTX.buffer(data=np.array(DebugDraw.__points, dtype=np.float32).tobytes())
      if (DebugDraw.__point_vao == None or clear_points):
        DebugDraw.__point_vao = CTX.vertex_array(DebugDraw.__debug_program, DebugDraw.__point_buf, 'in_vert', 'in_color')
      DebugDraw.__point_vao.render(moderngl.POINTS)
      if (clear_points):
        DebugDraw.__point_buf.release()
        DebugDraw.__point_vao.release()
      
    if len(DebugDraw.__lines) > 0:
      line_buf = CTX.buffer(data=np.array(DebugDraw.__lines, dtype=np.float32).tobytes())
      line_vao = CTX.vertex_array(DebugDraw.__debug_program, line_buf, 'in_vert', 'in_color')
      line_vao.render(moderngl.LINES)
      line_vao.release()
      line_buf.release()
      
    CTX.enable(moderngl.DEPTH_TEST)  # Re-enable depth test
      
    if clear_points:
      DebugDraw.__points.clear()
    if clear_lines:
      DebugDraw.__lines.clear()